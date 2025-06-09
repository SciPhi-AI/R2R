import importlib
import inspect
import logging
import os
import pkgutil
import sys
from typing import Callable, Optional, Type

from shared.abstractions.tool import Tool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Registry for discovering and managing tools from both
    built-in sources and user-defined extensions.
    """

    def __init__(
        self,
        built_in_path: str | None = None,
        user_tools_path: str | None = None,
        smolagent_tools_path: str | None = None,
    ):
        self.built_in_path = built_in_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "built_in"
        )
        self.user_tools_path = (
            user_tools_path
            or os.getenv("R2R_USER_TOOLS_PATH")
            or "../docker/user_tools"
        )
        self.smolagent_tools_path = smolagent_tools_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../../../smolagent/tools",
        )

        # Tool storage
        self._built_in_tools: dict[str, Type[Tool]] = {}
        self._user_tools: dict[str, Type[Tool]] = {}
        self._smolagent_tools: dict[str, Type[Tool]] = {}

        # Discover tools
        self._discover_built_in_tools()
        if os.path.exists(self.user_tools_path):
            self._discover_user_tools()
        else:
            logger.warning(
                f"User tools directory not found: {self.user_tools_path}"
            )
        if os.path.exists(self.smolagent_tools_path):
            self._discover_smolagent_tools()
        else:
            logger.warning(
                f"Smolagent tools directory not found: {self.smolagent_tools_path}"
            )

    def _discover_tools_from_path(
        self, path: str, registry: dict, package_prefix: str = ""
    ):
        if not os.path.exists(path):
            logger.warning(f"Tools directory not found: {path}")
            return

        # Add to Python path if needed
        if path not in sys.path:
            sys.path.append(os.path.dirname(path))

        # Import the package if a prefix is given
        prefix_valid = True
        if package_prefix:
            try:
                importlib.import_module(package_prefix)
            except ImportError as e:
                logger.warning(
                    f"Failed to import tools package with prefix only: {package_prefix}\t"
                    f"Error: {e}"
                )
                try:
                    # prefix works if it is local package, let's also fetch by path
                    tools_pkg_name = os.path.basename(path)
                    importlib.import_module(tools_pkg_name)
                    prefix_valid = False
                except ImportError as e:
                    logger.warning(
                        f"Failed to import tools package: {tools_pkg_name}\t"
                        f"Error: {e}"
                    )
                    return

        for _, module_name, is_pkg in pkgutil.iter_modules([path]):
            if is_pkg:
                continue
            try:
                module_path = f"{module_name}"
                if prefix_valid and package_prefix:
                    module_path = f"{package_prefix}.{module_name}"
                elif not prefix_valid and package_prefix:
                    module_path = f"{tools_pkg_name}.{module_name}"
                module = importlib.import_module(module_path)
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (
                        issubclass(obj, Tool)
                        and obj.__module__ == module.__name__
                        and obj != Tool
                    ):
                        try:
                            tool_instance = obj()  # type: ignore
                            registry[tool_instance.name] = obj
                            logger.debug(
                                f"Loaded tool: {tool_instance.name} from {path}"
                            )
                        except Exception as e:
                            logger.error(
                                f"Error instantiating tool {name}: {e}"
                            )
            except Exception as e:
                logger.error(f"Error loading tool module {module_name}: {e}")

    def _discover_built_in_tools(self):
        self._discover_tools_from_path(
            self.built_in_path, self._built_in_tools, "built_in"
        )

    def _discover_user_tools(self):
        """Scan the user tools directory for custom tools."""
        # Add user_tools directory to Python path if needed
        if self.user_tools_path not in sys.path:
            sys.path.append(os.path.dirname(self.user_tools_path))

        user_tools_pkg_name = os.path.basename(self.user_tools_path)

        # Check all Python files in user_tools directory
        for filename in os.listdir(self.user_tools_path):
            if (
                not filename.endswith(".py")
                or filename.startswith("_")
                or filename.startswith(".")
            ):
                continue

            module_name = filename[:-3]  # Remove .py extension

            try:
                # Import the module
                module = importlib.import_module(
                    f"{user_tools_pkg_name}.{module_name}"
                )

                # Find all tool classes in the module
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (
                        issubclass(obj, Tool)
                        and obj.__module__ == module.__name__
                        and obj != Tool
                    ):
                        try:
                            tool_instance = obj()
                            self._user_tools[tool_instance.name] = obj
                            logger.debug(
                                f"Loaded user tool: {tool_instance.name}"
                            )
                        except Exception as e:
                            logger.error(
                                f"Error instantiating user tool {name}: {e}"
                            )
            except Exception as e:
                logger.error(
                    f"Error loading user tool module {module_name}: {e}"
                )

    def _discover_smolagent_tools(self):
        self._discover_tools_from_path(
            self.smolagent_tools_path, self._smolagent_tools, "smolagent.tools"
        )

    def get_tool_class(self, tool_name: str):
        """Get a tool class by name.
        If the tool is a smolagent tool, it will return the R2R wrapper.
        """
        if tool_name in self._smolagent_tools:
            return self._smolagent_tools[tool_name]
        if tool_name in self._user_tools:
            return self._user_tools[tool_name]

        return self._built_in_tools.get(tool_name)

    def list_available_tools(
        self, include_built_in=True, include_user=True
    ) -> list[str]:
        """
        List all available tool names.
        Optionally filter by built-in or user-defined tools.
        """
        tools: set[str] = set()

        if include_built_in:
            tools.update(self._built_in_tools.keys())

        if include_user:
            tools.update(self._user_tools.keys())

        return sorted(list(tools))

    def create_tool_instance(
        self, tool_name: str, format_function: Callable, context=None
    ) -> Optional[Tool]:
        """
        Create, configure, and return an instance of the specified tool.
        Returns None if the tool doesn't exist or instantiation fails.
        """
        tool_class = self.get_tool_class(tool_name)
        if not tool_class:
            logger.warning(f"Tool class not found for '{tool_name}'")
            return None

        try:
            tool_instance = tool_class()
            if hasattr(tool_instance, "llm_format_function"):
                tool_instance.llm_format_function = format_function

            # Set the context on the specific tool instance
            tool_instance.set_context(context)

            return tool_instance

        except Exception as e:
            logger.error(
                f"Error creating or setting context for tool instance '{tool_name}': {e}"
            )
            return None
