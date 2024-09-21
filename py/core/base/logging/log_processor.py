import contextlib
import json
import logging
import statistics
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Sequence

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class LogFilterCriteria(BaseModel):
    filters: Optional[dict[str, str]] = None


class LogProcessor:
    timestamp_format = "%Y-%m-%d %H:%M:%S"

    def __init__(self, filters: Dict[str, Callable[[Dict[str, Any]], bool]]):
        self.filters = filters
        self.populations: dict = {name: [] for name in filters}

    def process_log(self, log: Dict[str, Any]):
        for name, filter_func in self.filters.items():
            if filter_func(log):
                self.populations[name].append(log)


class StatisticsCalculator:
    @staticmethod
    def calculate_statistics(
        population: List[Dict[str, Any]],
        stat_functions: Dict[str, Callable[[List[Dict[str, Any]]], Any]],
    ) -> Dict[str, Any]:
        return {
            name: func(population) for name, func in stat_functions.items()
        }


class DistributionGenerator:
    @staticmethod
    def generate_distributions(
        population: List[Dict[str, Any]],
        dist_functions: Dict[str, Callable[[List[Dict[str, Any]]], Any]],
    ) -> Dict[str, Any]:
        return {
            name: func(population) for name, func in dist_functions.items()
        }


class VisualizationPreparer:
    @staticmethod
    def prepare_visualization_data(
        data: Dict[str, Any],
        vis_functions: Dict[str, Callable[[Dict[str, Any]], Any]],
    ) -> Dict[str, Any]:
        return {name: func(data) for name, func in vis_functions.items()}


class LogAnalyticsConfig:
    def __init__(self, filters, stat_functions, dist_functions, vis_functions):
        self.filters = filters
        self.stat_functions = stat_functions
        self.dist_functions = dist_functions
        self.vis_functions = vis_functions


class AnalysisTypes(BaseModel):
    analysis_types: Optional[dict[str, Sequence[str]]] = None

    @staticmethod
    def generate_bar_chart_data(logs, key):
        chart_data = {"labels": [], "datasets": []}
        value_counts = defaultdict(int)

        for log in logs:
            if "entries" in log:
                for entry in log["entries"]:
                    if entry["key"] == key:
                        value_counts[entry["value"]] += 1
            elif "key" in log and log["key"] == key:
                value_counts[log["value"]] += 1

        for value, count in value_counts.items():
            chart_data["labels"].append(value)
            chart_data["datasets"].append({"label": key, "data": [count]})

        return chart_data

    @staticmethod
    def calculate_basic_statistics(logs, key):
        values = []
        for log in logs:
            if log["key"] == "search_results":
                results = json.loads(log["value"])
                scores = [
                    float(json.loads(result)["score"]) for result in results
                ]
                values.extend(scores)
            else:
                value = log.get("value")
                if value is not None:
                    with contextlib.suppress(ValueError):
                        values.append(float(value))

        if not values:
            return {
                "Mean": None,
                "Median": None,
                "Mode": None,
                "Standard Deviation": None,
                "Variance": None,
            }

        if len(values) == 1:
            single_value = round(values[0], 3)
            return {
                "Mean": single_value,
                "Median": single_value,
                "Mode": single_value,
                "Standard Deviation": 0,
                "Variance": 0,
            }

        mean = round(sum(values) / len(values), 3)
        median = round(statistics.median(values), 3)
        mode = (
            round(statistics.mode(values), 3)
            if len(set(values)) != len(values)
            else None
        )
        std_dev = round(statistics.stdev(values) if len(values) > 1 else 0, 3)
        variance = round(
            statistics.variance(values) if len(values) > 1 else 0, 3
        )

        return {
            "Mean": mean,
            "Median": median,
            "Mode": mode,
            "Standard Deviation": std_dev,
            "Variance": variance,
        }

    @staticmethod
    def calculate_percentile(logs, key, percentile):
        values = []
        for log in logs:
            if log["key"] == key:
                value = log.get("value")
                if value is not None:
                    with contextlib.suppress(ValueError):
                        values.append(float(value))

        if not values:
            return {"percentile": percentile, "value": None}

        values.sort()
        index = int((percentile / 100) * (len(values) - 1))
        return {"percentile": percentile, "value": round(values[index], 3)}


class LogAnalytics:
    def __init__(self, logs: List[Dict[str, Any]], config: LogAnalyticsConfig):
        self.logs = logs
        self.log_processor = LogProcessor(config.filters)
        self.statistics_calculator = StatisticsCalculator()
        self.distribution_generator = DistributionGenerator()
        self.visualization_preparer = VisualizationPreparer()
        self.config = config

    def count_logs(self) -> Dict[str, Any]:
        """Count the logs for each filter."""
        return {
            name: len(population)
            for name, population in self.log_processor.populations.items()
        }

    def process_logs(self) -> Dict[str, Any]:
        for log in self.logs:
            self.log_processor.process_log(log)

        analytics = {}
        for name, population in self.log_processor.populations.items():
            stats = self.statistics_calculator.calculate_statistics(
                population, self.config.stat_functions
            )
            dists = self.distribution_generator.generate_distributions(
                population, self.config.dist_functions
            )
            analytics[name] = {"statistics": stats, "distributions": dists}

        return self.visualization_preparer.prepare_visualization_data(
            analytics, self.config.vis_functions
        )
