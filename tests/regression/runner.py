import importlib
import os
from typing import Any, Dict, List

from test_cases.base import BaseTest, RegressionTest

from r2r.main.api.client import R2RClient


class RegressionTestRunner:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.client = R2RClient(base_url=base_url)
        self.tests: List[BaseTest] = []
        self.test_order = [
            "TestDocumentManagement",
            "TestRetrieval",
            "TestUserManagement",
            # "TestObservability",
        ]

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
        all_passed = True
        for test in self.tests:
            print(f"Running test suite: {test.__class__.__name__}")
            if test.run_suite():
                print(f"Test suite {test.__class__.__name__} passed")
            else:
                print(f"Test suite {test.__class__.__name__} failed")
                all_passed = False
        return all_passed

    def update_all_expected_outputs(self):
        for test in self.tests:
            print(
                f"Updating expected output for test suite: {test.__class__.__name__}"
            )
            test.update_expected_outputs()


def main():
    runner = RegressionTestRunner()
    runner.load_tests()

    if os.environ.get("UPDATE_EXPECTED_OUTPUTS", "").lower() == "true":
        runner.update_all_expected_outputs()
    else:
        success = runner.run_all()
        if not success:
            exit(1)


if __name__ == "__main__":
    main()
