# User-Defined Tools Directory

## Overview
This directory is mounted inside the R2R Docker container and is intended for custom tool files. Any files placed here will be accessible to the application running in the container.

## Usage
1. Place your custom tool definitions in this directory. Utilize the template structure demonstrated here.
2. Add any additional dependencies that you may need to the user_requirements.txt file in this directory.
3. Include the tool in your agent configuration.

## Creating a tool
```python
from core.base.agent.tools.base import Tool


class ToolNameTool(Tool):
    """
    A user defined tool.
    """

    def __init__(self):
        super().__init__(
            name="tool_name",
            description="A natural language tool description that is shown to the agent.",
            parameters={
                "type": "object",
                "properties": {
                    "input_parameter": {
                        "type": "string",
                        "description": "Define any input parameters by their name and type",
                    },
                },
                "required": ["input_parameter"],
            },
            results_function=self.execute,
            llm_format_function=None,
        )

    async def execute(self, input_parameter: str, *args, **kwargs):
        """
        Implementation of the tool.
        """

        # Any custom tool logic can go here

        output_response = some_method(input_parameter)

        result = AggregateSearchResult(
            generic_tool_result=[web_response],
        )

        # Add to results collector if context is provided
        if context and hasattr(context, "search_results_collector"):
            context.search_results_collector.add_aggregate_result(result)

        return result
```

## Troubleshooting

For more detailed configuration information, see the main documentation.
