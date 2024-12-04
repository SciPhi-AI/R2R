import json
import os
import re
from typing import Any, Callable, Optional

from colorama import Fore, Style
from deepdiff import DeepDiff

# TODO: need to import this from the package, not from the local directory
from r2r import R2RClient


def _to_snake_case(name: str) -> str:
    pattern = re.compile(r"(?<!^)(?=[A-Z])")
    return pattern.sub("_", name).lower()


class RegressionTest:
    def __init__(
        self,
        name: str,
        test_function: Callable[[R2RClient], Any],
        expected_output: dict[str, Any],
        exclude_paths: list[str] = [],
    ):
        self.name = name
        self.test_function = test_function
        self.expected_output = expected_output
        self.exclude_paths = exclude_paths

    def run(self, client: R2RClient) -> bool:
        result = self._run_test(client)
        return self._compare_output(result, self.expected_output)

    def update_expected_output(self, client: R2RClient):
        result = self._run_test(client)
        self._save_expected_output(result)

    def _run_test(self, client: R2RClient) -> dict[str, Any]:
        return self.test_function(client)

    def _load_expected_output(self) -> dict[str, Any]:
        with open(self.expected_output_file, "r") as f:
            return json.load(f)

    def _save_expected_output(self, output: dict[str, Any]):
        with open(self.expected_output_file, "w") as f:
            json.dump(output, f, indent=2)

    def _compare_output(
        self, actual: dict[str, Any], expected: dict[str, Any]
    ) -> bool:
        diff = self._custom_diff(expected, actual)
        if diff:
            print(f"\nTest {self.name} failed. Differences found:")
            print(json.dumps(diff, indent=2))
            return False
        return True

    def _custom_diff(
        self, expected: dict[str, Any], actual: dict[str, Any]
    ) -> dict[str, Any]:
        diff = {}

        expected_results = expected.get("results", {})
        actual_results = actual.get("results", {})

        if "completion" in expected_results and "completion" in actual_results:
            # Custom comparison for content field
            expected_completion = self._get_completion_content(
                expected_results
            )
            actual_completion = self._get_completion_content(actual_results)
            if (
                expected_completion
                and actual_completion
                and not self._fuzzy_content_match(
                    expected_completion, actual_completion
                )
            ):
                diff["content_mismatch"] = {
                    "expected": expected_completion,
                    "actual": actual_completion,
                }

            # Use DeepDiff for the rest, ignoring specified fields
            try:
                deep_diff = DeepDiff(
                    expected_results,
                    actual_results,
                    ignore_order=True,
                    exclude_paths=self.exclude_paths,
                )
                if deep_diff:
                    diff["other_differences"] = self._serialize_deep_diff(
                        deep_diff
                    )
                    # Print the specific fields that are different
                    for change_type, changes in deep_diff.items():
                        if change_type == "values_changed":
                            for path, change in changes.items():
                                print(f"Field '{path}' changed:")
                                print(f"  Expected: {change['old_value']}")
                                print(f"  Actual: {change['new_value']}")

            except Exception as e:
                diff["deepdiff_error"] = (
                    f"Error in DeepDiff comparison: {str(e)}"
                )
                return diff
        elif (
            "completion" in expected_results or "completion" in actual_results
        ):
            diff["content_mismatch"] = {
                "expected_results": expected_results,
                "actual_results": actual_results,
            }
        else:
            deep_diff = DeepDiff(
                expected_results,
                actual_results,
                ignore_order=True,
                exclude_paths=self.exclude_paths,
            )

            if deep_diff:
                diff["other_differences"] = self._serialize_deep_diff(
                    deep_diff
                )
                # Print the specific fields that are different
                for change_type, changes in deep_diff.items():
                    if change_type == "values_changed":
                        for path, change in changes.items():
                            print(f"Field '{path}' changed:")
                            print(f"  Expected: {change['old_value']}")
                            print(f"  Actual: {change['new_value']}")

            return self._serialize_deep_diff(deep_diff)

        return diff

    def _serialize_deep_diff(self, deep_diff):
        if isinstance(deep_diff, dict):
            serializable_diff = {}
            for key, value in deep_diff.items():
                if isinstance(value, (dict, list)):
                    serializable_diff[key] = self._serialize_deep_diff(value)
                elif isinstance(value, (int, float, str, bool, type(None))):
                    serializable_diff[key] = value
                else:
                    serializable_diff[key] = str(value)
            return serializable_diff
        elif isinstance(deep_diff, list):
            return [self._serialize_deep_diff(item) for item in deep_diff]
        elif isinstance(deep_diff, (int, float, str, bool, type(None))):
            return deep_diff
        else:
            return str(deep_diff)

    def _get_completion_content(self, data: dict[str, Any]) -> Optional[str]:
        try:
            return data["completion"]["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            return None

    def _fuzzy_content_match(
        self, expected: str, actual: str, threshold: float = 0.6
    ) -> bool:
        expected_words = set(re.findall(r"\w+", expected.lower()))
        actual_words = set(re.findall(r"\w+", actual.lower()))
        common_words = expected_words.intersection(actual_words)
        similarity = len(common_words) / max(
            len(expected_words), len(actual_words)
        )
        return similarity >= threshold


class BaseTest:
    def __init__(self, client: R2RClient):
        self.client = client
        self.expected_outputs_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "expected_outputs",
            f"{_to_snake_case(self.__class__.__name__)}.json",
        )
        self.exclude_paths_map = {}

    def run_and_save_outputs(self, actual_outputs_dir: str):
        actual_outputs = {}
        for test_name, test_func in self.get_test_cases().items():
            snake_case_name = _to_snake_case(test_name)
            print(f"  Running test: {snake_case_name}")
            result = test_func(self.client)
            actual_outputs[snake_case_name] = result

        actual_outputs_file = os.path.join(
            actual_outputs_dir,
            f"{_to_snake_case(self.__class__.__name__)}.json",
        )
        with open(actual_outputs_file, "w") as f:
            json.dump(actual_outputs, f, indent=2)

    def compare_outputs(
        self, observed_outputs_dir: str, expected_outputs_dir: str
    ) -> bool:
        all_passed = True
        expected_outputs_file = os.path.join(
            expected_outputs_dir,
            f"{_to_snake_case(self.__class__.__name__)}.json",
        )
        observed_outputs_file = os.path.join(
            observed_outputs_dir,
            f"{_to_snake_case(self.__class__.__name__)}.json",
        )

        with open(expected_outputs_file, "r") as f:
            expected_outputs = json.load(f)

        with open(observed_outputs_file, "r") as f:
            observed_outputs = json.load(f)

        for test_name in self.get_test_cases().keys():
            snake_case_name = _to_snake_case(test_name)
            exclude_paths = self.exclude_paths_map.get(snake_case_name, [])
            regression_test = RegressionTest(
                test_name,
                lambda x: x,
                expected_outputs.get(snake_case_name, {}),
                exclude_paths,
            )
            if regression_test._compare_output(
                observed_outputs.get(snake_case_name, {}),
                expected_outputs.get(snake_case_name, {}),
            ):
                print(
                    f"{Fore.GREEN}  Test {snake_case_name} passed ✓{Style.RESET_ALL}"
                )
            else:
                print(
                    f"{Fore.RED}  Test {snake_case_name} failed ✗{Style.RESET_ALL}"
                )
                all_passed = False

        return all_passed

    def update_expected_outputs(self, actual_outputs_dir: str):
        actual_outputs_file = os.path.join(
            actual_outputs_dir,
            f"{_to_snake_case(self.__class__.__name__)}.json",
        )
        with open(actual_outputs_file, "r") as f:
            actual_outputs = json.load(f)

        with open(self.expected_outputs_file, "w") as f:
            json.dump(actual_outputs, f, indent=2)

    def _load_expected_outputs(self) -> dict[str, Any]:
        if os.path.exists(self.expected_outputs_file):
            with open(self.expected_outputs_file, "r") as f:
                return json.load(f)
        return {}

    def set_exclude_paths(self, test_name: str, exclude_paths: list[str] = []):
        self.exclude_paths_map[_to_snake_case(test_name)] = exclude_paths

    def get_test_cases(self) -> dict[str, callable]:
        raise NotImplementedError(
            "Subclasses must implement get_test_cases method"
        )

    def _load_expected_outputs(self) -> dict[str, Any]:
        with open(self.expected_outputs_file, "r") as f:
            return json.load(f)
