import http.client
import json
import os


# TODO - Move process json to dedicated data processing module
def process_json(json_object, indent=0):
    """
    Recursively traverses the JSON object (dicts and lists) to create an unstructured text blob.
    """
    text_blob = ""
    if isinstance(json_object, dict):
        for key, value in json_object.items():
            padding = "  " * indent
            if isinstance(value, (dict, list)):
                text_blob += (
                    f"{padding}{key}:\n{process_json(value, indent + 1)}"
                )
            else:
                text_blob += f"{padding}{key}: {value}\n"
    elif isinstance(json_object, list):
        for index, item in enumerate(json_object):
            padding = "  " * indent
            if isinstance(item, (dict, list)):
                text_blob += f"{padding}Item {index + 1}:\n{process_json(item, indent + 1)}"
            else:
                text_blob += f"{padding}Item {index + 1}: {item}\n"
    return text_blob


# TODO - Introduce abstract "Integration" ABC.
class SerperClient:
    def __init__(self, api_base: str = "google.serper.dev") -> None:
        api_key = os.getenv("SERPER_API_KEY")
        if not api_key:
            raise ValueError(
                "Please set the `SERPER_API_KEY` environment variable to use `SerperClient`."
            )

        self.api_base = api_base
        self.headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _extract_results(result_data: dict) -> list:
        formatted_results = []

        for key, value in result_data.items():
            # Skip searchParameters as it's not a result entry
            if key == "searchParameters":
                continue

            # Handle 'answerBox' as a single item
            if key == "answerBox":
                value["type"] = key  # Add the type key to the dictionary
                formatted_results.append(value)
            # Handle lists of results
            elif isinstance(value, list):
                for item in value:
                    item["type"] = key  # Add the type key to the dictionary
                    formatted_results.append(item)
            # Handle 'peopleAlsoAsk' and potentially other single item formats
            elif isinstance(value, dict):
                value["type"] = key  # Add the type key to the dictionary
                formatted_results.append(value)

        return formatted_results

    # TODO - Add explicit typing for the return value
    def get_raw(self, query: str, limit: int = 10) -> list:
        connection = http.client.HTTPSConnection(self.api_base)
        payload = json.dumps({"q": query, "num_outputs": limit})
        connection.request("POST", "/search", payload, self.headers)
        response = connection.getresponse()
        data = response.read()
        json_data = json.loads(data.decode("utf-8"))
        return SerperClient._extract_results(json_data)

    @staticmethod
    def construct_context(results: list) -> str:
        # Organize results by type
        organized_results = {}
        for result in results:
            result_type = result.metadata.pop(
                "type", "Unknown"
            )  # Pop the type and use as key
            if result_type not in organized_results:
                organized_results[result_type] = [result.metadata]
            else:
                organized_results[result_type].append(result.metadata)

        context = ""
        # Iterate over each result type
        for result_type, items in organized_results.items():
            context += f"# {result_type} Results:\n"
            for index, item in enumerate(items, start=1):
                # Process each item under the current type
                context += f"Item {index}:\n"
                context += process_json(item) + "\n"

        return context
