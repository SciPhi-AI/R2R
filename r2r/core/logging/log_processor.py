import json
import re
from datetime import datetime
import logging
from collections import defaultdict
from typing import List, Dict, Any, Callable, Union

logger = logging.getLogger(__name__)

class LogProcessor:
    timestamp_format = "%Y-%m-%d %H:%M:%S"

    def __init__(self, filters: Dict[str, Callable[[Dict[str, Any]], bool]]):
        self.filters = filters
        self.populations = {name: [] for name in filters}

    def process_log(self, log: Dict[str, Any]):
        for name, filter_func in self.filters.items():
            if filter_func(log):
                self.populations[name].append(log)

class StatisticsCalculator:
    @staticmethod
    def calculate_statistics(population: List[Dict[str, Any]], stat_functions: Dict[str, Callable[[List[Dict[str, Any]]], Any]]) -> Dict[str, Any]:
        return {name: func(population) for name, func in stat_functions.items()}

class DistributionGenerator:
    @staticmethod
    def generate_distributions(population: List[Dict[str, Any]], dist_functions: Dict[str, Callable[[List[Dict[str, Any]]], Any]]) -> Dict[str, Any]:
        return {name: func(population) for name, func in dist_functions.items()}

class VisualizationPreparer:
    @staticmethod
    def prepare_visualization_data(data: Dict[str, Any], vis_functions: Dict[str, Callable[[Dict[str, Any]], Any]]) -> Dict[str, Any]:
        return {name: func(data) for name, func in vis_functions.items()}

class LogAnalyticsConfig:
    def __init__(self, filters, stat_functions, dist_functions, vis_functions):
        self.filters = filters
        self.stat_functions = stat_functions
        self.dist_functions = dist_functions
        self.vis_functions = vis_functions

class LogAnalytics:
    def __init__(self, logs: List[Dict[str, Any]], config: LogAnalyticsConfig):
        self.logs = logs
        self.log_processor = LogProcessor(config.filters)
        self.statistics_calculator = StatisticsCalculator()
        self.distribution_generator = DistributionGenerator()
        self.visualization_preparer = VisualizationPreparer()
        self.config = config

    def process_logs(self) -> Dict[str, Any]:
        for log in self.logs:
            self.log_processor.process_log(log)

        analytics = {}
        for name, population in self.log_processor.populations.items():
            stats = self.statistics_calculator.calculate_statistics(population, self.config.stat_functions)
            dists = self.distribution_generator.generate_distributions(population, self.config.dist_functions)
            analytics[name] = {
                "statistics": stats,
                "distributions": dists
            }

        return self.visualization_preparer.prepare_visualization_data(analytics, self.config.vis_functions)

# Example filters
filters = {
    "error_logs": lambda log: log["key"] == "error",
    "search_results": lambda log: log["key"] == "search_results",
    "vector_search_latency": lambda log: log["key"] == "vector_search_latency"
}

# Example statistics functions
stat_functions = {
    "error_count": lambda population: len(population),
    "average_latency": lambda population: sum(float(log["value"]) for log in population) / len(population) if population else 0
}

# Example distribution functions
dist_functions = {
    "error_distribution": lambda population: defaultdict(int, {re.findall(r'\b\d{3}\b', log["value"])[-1]: 1 for log in population if re.findall(r'\b\d{3}\b', log["value"])}),
    "latency_distribution": lambda population: [float(log["value"]) for log in population]
}

# Example visualization functions
vis_functions = {
    "stacked_bar_chart": lambda data: {
        "labels": list(data.keys()),
        "datasets": [{"label": name, "data": [stats["average_latency"] for stats in data.values()]} for name in data.keys()]
    },
    "pie_chart": lambda data: [{"error_type": k, "count": v} for k, v in data["error_logs"]["distributions"]["error_distribution"].items()]
}

# Configuration
config = LogAnalyticsConfig(filters, stat_functions, dist_functions, vis_functions)

# Example usage
logs = [
    {"key": "error", "value": "404", "timestamp": "2024-05-30 10:00:00"},
    {"key": "error", "value": "500", "timestamp": "2024-05-30 11:00:00"},
    {"key": "search_results", "value": "0.9", "timestamp": "2024-05-30 12:00:00"},
    {"key": "vector_search_latency", "value": "0.05", "timestamp": "2024-05-30 13:00:00"},
]

log_analytics = LogAnalytics(logs, config)
result = log_analytics.process_logs()

print(result)
