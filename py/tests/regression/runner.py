import argparse
import importlib
import os

from colorama import Fore, Style, init
from test_cases.base import BaseTest, RegressionTest

# TODO: need to import this from the package, not from the local directory
from r2r import R2RClient


class RegressionTestRunner:
    def __init__(
        self,
        check_only: bool = False,
        update_expected: bool = False,
        base_url: str = "http://localhost:7272",
    ):
        self.client = R2RClient(base_url=base_url)
        self.tests: list[BaseTest] = []
        self.test_order = [
            "TestDocumentManagement",
            "TestRetrieval",
            "TestUserManagement",
            "TestObservability",
            "TestGroupManagement",
        ]
        self.check_only = check_only
        self.update_expected = update_expected

        if not check_only:
            self.outputs_dir = os.path.join(
                os.path.dirname(__file__),
                (
                    "expected_outputs"
                    if self.update_expected
                    else "observed_outputs"
                ),
            )
            os.makedirs(self.outputs_dir, exist_ok=True)

    def load_tests(self):
        test_dir = os.path.join(os.path.dirname(__file__), "test_cases")
        for class_name in self.test_order:
            # Convert camel case to snake case
            snake_case = "".join(
                ["_" + c.lower() if c.isupper() else c for c in class_name]
            ).lstrip("_")
            filename = f"test_{snake_case[5:]}.py"  # Remove "test_" prefix
            if filename in os.listdir(test_dir):
                module_name = f"tests.regression.test_cases.{filename[:-3]}"
                module = importlib.import_module(module_name)
                test_class = getattr(module, class_name)
                self.tests.append(test_class(self.client))

    def run_all(self) -> bool:
        for test in self.tests:
            print(
                f"{Fore.CYAN}Running test suite: {test.__class__.__name__}{Style.RESET_ALL}"
            )
            test.run_and_save_outputs(self.outputs_dir)

        return self.compare_all() if not self.update_expected else True

    def compare_all(self) -> bool:
        all_passed = True
        expected_outputs_dir = os.path.join(
            os.path.dirname(__file__), "expected_outputs"
        )
        observed_outputs_dir = os.path.join(
            os.path.dirname(__file__), "observed_outputs"
        )
        print(
            f"\n{Fore.CYAN}Comparing results for test suites:{Style.RESET_ALL}"
        )
        for test in self.tests:
            if test.compare_outputs(
                observed_outputs_dir, expected_outputs_dir
            ):
                print(
                    f"{Fore.GREEN}{test.__class__.__name__} ✓{Style.RESET_ALL}"
                )
            else:
                print(
                    f"{Fore.RED}{test.__class__.__name__} ✗{Style.RESET_ALL}"
                )
                all_passed = False
        return all_passed

    def update_all_expected_outputs(self):
        for test in self.tests:
            print(
                f"{Fore.YELLOW}Updating expected output for test suite: {test.__class__.__name__}{Style.RESET_ALL}"
            )
            test.update_expected_outputs(self.outputs_dir)


def main():
    parser = argparse.ArgumentParser(description="Run regression tests")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Run in check mode (compare existing outputs without running tests)",
    )
    parser.add_argument(
        "--update-expected",
        action="store_true",
        help="Run in update mode (update expected outputs)",
    )
    args = parser.parse_args()

    runner = RegressionTestRunner(args.check_only)
    runner.load_tests()

    if args.check_only:
        print(f"{Fore.CYAN}Running in check-only mode{Style.RESET_ALL}")
        success = runner.compare_all()
    elif runner.update_expected:
        print(f"{Fore.YELLOW}Updating expected outputs{Style.RESET_ALL}")
        runner.run_all()  # Run tests to generate outputs
        runner.update_all_expected_outputs()
        if os.environ.get("CHECK_UPDATED_OUTPUTS", "").lower() != "true":
            success = runner.compare_all()
    else:
        print(f"{Fore.CYAN}Running all tests{Style.RESET_ALL}")
        success = runner.run_all()

    if success:
        print(f"\n{Fore.GREEN}All tests passed successfully!{Style.RESET_ALL}")
    else:
        print(
            f"\n{Fore.RED}Some tests failed. Please check the output above for details.{Style.RESET_ALL}"
        )
        exit(1)


if __name__ == "__main__":
    main()
