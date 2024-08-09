import json
import os
import re
from typing import Any, Callable, Dict, Optional

from deepdiff import DeepDiff

from r2r.main.api.client import R2RClient


def _to_snake_case(name: str) -> str:
    pattern = re.compile(r"(?<!^)(?=[A-Z])")
    return pattern.sub("_", name).lower()


class RegressionTest:
    def __init__(
        self,
        name: str,
        test_function: Callable[[R2RClient], Any],
        expected_output: Dict[str, Any],
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

    def _run_test(self, client: R2RClient) -> Dict[str, Any]:
        return self.test_function(client)

    def _load_expected_output(self) -> Dict[str, Any]:
        with open(self.expected_output_file, "r") as f:
            return json.load(f)

    def _save_expected_output(self, output: Dict[str, Any]):
        with open(self.expected_output_file, "w") as f:
            json.dump(output, f, indent=2)

    def _compare_output(
        self, actual: Dict[str, Any], expected: Dict[str, Any]
    ) -> bool:
        diff = self._custom_diff(expected, actual)
        if diff:
            print(f"\nTest {self.name} failed. Differences found:")
            print(json.dumps(diff, indent=2))
            print("\nExpected output:")
            print(json.dumps(expected, indent=2))
            print("\nActual output:")
            print(json.dumps(actual, indent=2))
            return False
        return True

    def _custom_diff(
        self, expected: Dict[str, Any], actual: Dict[str, Any]
    ) -> Dict[str, Any]:
        diff = {}

        expected_results = expected.get("results", {})
        actual_results = actual.get("results", {})

        # if (
        #     "search_results" in expected_results
        #     and "vector_search_results" in actual_results
        # ):
        #     # Restructure actual results to match expected
        #     actual_results["search_results"] = {
        #         "vector_search_results": actual_results.pop(
        #             "vector_search_results"
        #         ),
        #         "kg_search_results": actual_results.pop(
        #             "kg_search_results", None
        #         ),
        #     }

        if "completion" in expected_results and "completion" in actual_results:
            # Ignore specific fields
            # exclude_paths = [
            #     "id",
            #     "created",
            #     "system_fingerprint",
            #     "usage",
            #     "content",
            # ]

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
                    expected,
                    actual,
                    ignore_order=True,
                    exclude_paths=self.exclude_paths,
                )
                if deep_diff:
                    diff["other_differences"] = self._serialize_deep_diff(
                        deep_diff
                    )
            except Exception as e:
                diff["deepdiff_error"] = (
                    f"Error in DeepDiff comparison: {str(e)}"
                )
                return diff
        elif (
            "completion" in expected_results or "completion" in actual_results
        ):
            diff["content_mismatch"] = {"expected": expected, "actual": actual}
        else:

            deep_diff = DeepDiff(
                expected,
                actual,
                math_epsilon=1e-3,
                ignore_order=True,
                exclude_paths=self.exclude_paths,
            )
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

    def _get_completion_content(self, data: Dict[str, Any]) -> Optional[str]:
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

    def run_suite(self) -> bool:
        all_passed = True
        expected_outputs = self._load_expected_outputs()

        for test_name, test_func in self.get_test_cases().items():
            snake_case_name = _to_snake_case(test_name)
            print(f"  Running test: {snake_case_name}")
            exclude_paths = self.exclude_paths_map.get(snake_case_name, [])
            regression_test = RegressionTest(
                test_name,
                test_func,
                expected_outputs.get(snake_case_name, {}),
                exclude_paths,
            )
            if regression_test.run(self.client):
                print(f"  Test {snake_case_name} passed")
            else:
                print(f"  Test {snake_case_name} failed")
                all_passed = False

        return all_passed

    def update_expected_outputs(self):
        expected_outputs = {}
        for test_name, test_func in self.get_test_cases().items():
            snake_case_name = _to_snake_case(test_name)
            regression_test = RegressionTest(test_name, test_func, {})
            result = regression_test._run_test(self.client)
            expected_outputs[snake_case_name] = result

        with open(self.expected_outputs_file, "w") as f:
            json.dump(expected_outputs, f, indent=2)

    def _load_expected_outputs(self) -> Dict[str, Any]:
        if os.path.exists(self.expected_outputs_file):
            with open(self.expected_outputs_file, "r") as f:
                return json.load(f)
        return {}

    def set_exclude_paths(self, test_name: str, exclude_paths: list[str] = []):
        self.exclude_paths_map[_to_snake_case(test_name)] = exclude_paths

    def get_test_cases(self) -> Dict[str, callable]:
        raise NotImplementedError(
            "Subclasses must implement get_test_cases method"
        )

    def _load_expected_outputs(self) -> Dict[str, Any]:
        with open(self.expected_outputs_file, "r") as f:
            return json.load(f)
