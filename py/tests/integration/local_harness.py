import argparse
import importlib
import json
import logging
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime

from colorama import Fore, Style, init


@dataclass
class TestResult:
    name: str
    passed: bool
    duration: float
    error: dict


class TestRunner:
    def __init__(self, base_url: str):
        init()
        self.logger = self._setup_logger()
        self.base_url = base_url
        self.results_file = (
            f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        self.test_sequences = {
            "sdk-ingestion": [
                "test_ingest_sample_file_sdk",
                "test_reingest_sample_file_sdk",
                "test_document_overview_sample_file_sdk",
                "test_document_chunks_sample_file_sdk",
                "test_delete_and_reingest_sample_file_sdk",
                "test_ingest_sample_file_with_config_sdk",
            ],
            "sdk-retrieval": [
                "test_ingest_sample_file_sdk",
                "test_vector_search_sample_file_filter_sdk",
                "test_hybrid_search_sample_file_filter_sdk",
                "test_rag_response_sample_file_sdk",
                "test_conversation_history_sdk",
            ],
            "sdk-auth": [
                "test_user_registration_and_login",
                "test_duplicate_user_registration",
                "test_token_refresh",
                "test_user_document_management",
                "test_user_search_and_rag",
                "test_user_password_management",
                "test_user_profile_management",
                "test_user_overview",
                "test_user_logout",
            ],
            "sdk-collections": [
                "test_ingest_sample_file_sdk",
                "test_user_creates_collection",
                "test_user_updates_collection",
                "test_user_lists_collections",
                "test_user_collection_document_management",
                "test_user_removes_document_from_collection",
                "test_user_lists_documents_in_collection",
                "test_pagination_and_filtering",
                "test_advanced_collection_management",
                "test_user_gets_collection_details",
                "test_user_adds_user_to_collection",
                "test_user_removes_user_from_collection",
                "test_user_lists_users_in_collection",
                "test_user_gets_collections_for_user",
                "test_user_gets_collections_for_document",
                "test_user_permissions",
                "test_ingest_chunks",
                "test_update_chunks",
                "test_delete_chunks",
            ],
            "sdk-graphrag": [
                "test_ingest_sample_file_2_sdk",
                "test_kg_create_graph_sample_file_sdk",
                "test_kg_enrich_graph_sample_file_sdk",
                "test_kg_search_sample_file_sdk",
                "test_kg_delete_graph_sample_file_sdk",
                "test_kg_delete_graph_with_cascading_sample_file_sdk",
            ],
            "sdk-prompts": [
                "test_add_prompt",
                "test_get_prompt",
                "test_get_all_prompts",
                "test_update_prompt",
                "test_prompt_error_handling",
                "test_prompt_access_control",
                "test_delete_prompt",
            ],
        }

    def _setup_logger(self):
        logger = logging.getLogger("TestRunner")
        logger.setLevel(logging.INFO)
        # fh = logging.FileHandler(f"test_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        ch = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )
        # fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        # logger.addHandler(fh)
        logger.addHandler(ch)
        return logger

    def run_all_categories(self) -> dict[str, list[TestResult]]:
        all_results = {}
        for category in self.test_sequences.keys():
            self.logger.info(
                f"\n{Fore.CYAN}Running category: {category}{Style.RESET_ALL}"
            )
            results = self.run_test_category(category)
            all_results[category] = results
        return all_results

    def run_test_category(self, category: str) -> list[TestResult]:
        results = []
        try:
            module = importlib.import_module(
                "tests.integration.runner_sdk_basic"
            )
            module.client = module.create_client(self.base_url)
        except Exception as e:
            self.logger.error(
                f"{Fore.RED}Failed to initialize module: {str(e)}{Style.RESET_ALL}"
            )
            return []

        if category not in self.test_sequences:
            self.logger.error(f"Unknown test category: {category}")
            return results

        for test_name in self.test_sequences[category]:
            try:
                self.logger.info(
                    f"{Fore.CYAN}Running test: {test_name}{Style.RESET_ALL}"
                )
                start_time = time.time()
                test_func = getattr(module, test_name)
                test_func()
                duration = time.time() - start_time
                results.append(TestResult(test_name, True, duration))
                self.logger.info(
                    f"{Fore.GREEN}✓ Test passed: {test_name} ({duration:.2f}s){Style.RESET_ALL}"
                )
            except Exception as e:
                duration = time.time() - start_time
                error_details = {
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": traceback.format_exc(),
                }
                results.append(
                    TestResult(test_name, False, duration, error_details)
                )
                self.logger.error(
                    f"{Fore.RED}✗ Test failed: {test_name} ({duration:.2f}s){Style.RESET_ALL}"
                )
                self.logger.error(
                    f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}"
                )
                self.logger.error(traceback.format_exc())

                if (
                    input("Continue with remaining tests? (y/n): ").lower()
                    != "y"
                ):
                    break

        # self._save_results(results, category)
        self._print_summary(results)
        return results

    def _save_results(self, results: list[TestResult], category: str = None):
        output = {
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "total_tests": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
            "tests": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "duration": r.duration,
                    "error": r.error,
                }
                for r in results
            ],
        }
        with open(self.results_file, "w") as f:
            json.dump(output, f, indent=2)

    def _print_summary(self, results: list[TestResult]):
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        total_duration = sum(r.duration for r in results)

        self.logger.info("\n" + "=" * 50)
        self.logger.info("Test Summary:")
        self.logger.info(f"Total tests: {total}")
        self.logger.info(f"{Fore.GREEN}Passed: {passed}{Style.RESET_ALL}")
        self.logger.info(f"{Fore.RED}Failed: {failed}{Style.RESET_ALL}")
        self.logger.info(f"Total duration: {total_duration:.2f}s")

        if failed > 0:
            self.logger.info("\nFailed tests:")
            for result in results:
                if not result.passed:
                    self.logger.error(
                        f"{Fore.RED}Test: {result.name}{Style.RESET_ALL}"
                    )
                    if result.error:
                        self.logger.error(
                            f"Error Type: {result.error['type']}"
                        )
                        self.logger.error(
                            f"Message: {result.error['message']}"
                        )


def main():
    parser = argparse.ArgumentParser(description="Run R2R integration tests")
    parser.add_argument(
        "--category",
        choices=[
            "sdk-ingestion",
            "sdk-retrieval",
            "sdk-auth",
            "sdk-collections",
            "sdk-graphrag",
            "sdk-prompts",
        ],
        help="Test category to run (optional, runs all if not specified)",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:7272",
        help="Base URL for the R2R client",
    )
    args = parser.parse_args()

    runner = TestRunner(args.base_url)
    if args.category:
        results = runner.run_test_category(args.category)
        sys.exit(0 if all(r.passed for r in results) else 1)
    else:
        all_results = runner.run_all_categories()
        sys.exit(
            0
            if all(
                all(r.passed for r in results)
                for results in all_results.values()
            )
            else 1
        )


if __name__ == "__main__":
    main()
