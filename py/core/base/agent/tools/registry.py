import os
import sys
import importlib
import inspect
import logging
import pkgutil
from typing import Dict, List, Optional, Type, Callable
from .base import Tool

logger = logging.getLogger(__name__)

class ToolRegistry:
    """
    Registry for discovering and managing tools from both
    built-in sources and user-defined extensions.
    """
    
    def __init__(
        self, 
        built_in_path: str | None = None,
        user_tools_path: str | None = None
    ):
        self.built_in_path = built_in_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "built_in"
        )
        self.user_tools_path = user_tools_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "user_tools"
        )
        
        # Tool storage
        self._built_in_tools: Dict[str, Type[Tool]] = {}
        self._user_tools: Dict[str, Type[Tool]] = {}
        
        # Discover tools
        self._discover_built_in_tools()
        if os.path.exists(self.user_tools_path):
            self._discover_user_tools()
        else:
            logger.warning(f"User tools directory not found: {self.user_tools_path}")
    
    def _discover_built_in_tools(self):
        """Load all built-in tools from the built_in directory."""
        if not os.path.exists(self.built_in_path):
            logger.warning(f"Built-in tools directory not found: {self.built_in_path}")
            return
            
        # Add to Python path if needed
        if self.built_in_path not in sys.path:
            sys.path.append(os.path.dirname(self.built_in_path))
            
        # Import the built_in package
        try:
            built_in_pkg = importlib.import_module("built_in")
        except ImportError:
            logger.error("Failed to import built_in tools package")
            return
            
        # Discover all modules in the package
        for _, module_name, is_pkg in pkgutil.iter_modules([self.built_in_path]):
            if is_pkg:  # Skip subpackages
                continue
                
            try:
                module = importlib.import_module(f"built_in.{module_name}")
                
                # Find all tool classes in the module
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (issubclass(obj, Tool) and 
                        obj.__module__ == module.__name__ and 
                        obj != Tool):
                        try:
                            tool_instance = obj()
                            self._built_in_tools[tool_instance.name] = obj
                            logger.info(f"Loaded built-in tool: {tool_instance.name}")
                        except Exception as e:
                            logger.error(f"Error instantiating built-in tool {name}: {e}")
            except Exception as e:
                logger.error(f"Error loading built-in tool module {module_name}: {e}")
    
    def _discover_user_tools(self):
        """Scan the user tools directory for custom tools."""
        # Add user_tools directory to Python path if needed
        if self.user_tools_path not in sys.path:
            sys.path.append(os.path.dirname(self.user_tools_path))
        
        user_tools_pkg_name = os.path.basename(self.user_tools_path)
        
        # Check all Python files in user_tools directory
        for filename in os.listdir(self.user_tools_path):
            if not filename.endswith('.py') or filename.startswith('_') or filename.startswith('.'):
                continue
                
            module_name = filename[:-3]  # Remove .py extension
            
            try:
                # Import the module
                module = importlib.import_module(f"{user_tools_pkg_name}.{module_name}")
                
                # Find all tool classes in the module
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (issubclass(obj, Tool) and 
                        obj.__module__ == module.__name__ and 
                        obj != Tool):
                        try:
                            tool_instance = obj()
                            self._user_tools[tool_instance.name] = obj
                            logger.info(f"Loaded user tool: {tool_instance.name}")
                        except Exception as e:
                            logger.error(f"Error instantiating user tool {name}: {e}")
            except Exception as e:
                logger.error(f"Error loading user tool module {module_name}: {e}")
    
    def get_tool_class(self, tool_name: str):
        """Get a tool class by name."""
        # Check user tools first (they override built-ins)
        if tool_name in self._user_tools:
            return self._user_tools[tool_name]
            
        # Then check built-in tools
        return self._built_in_tools.get(tool_name)
    
    def list_available_tools(self, include_built_in=True, include_user=True) -> List[str]:
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
    
    def create_tool_instance(self, tool_name: str, format_function: Callable) -> Optional[Tool]:
        """
        Create and return a Tool instance for the specified tool.
        Returns None if the tool doesn't exist.
        """
        tool_class = self.get_tool_class(tool_name)
        if not tool_class:
            return None
            
        try:
            tool_instance = tool_class()
            return tool_instance.create_tool(format_function)
        except Exception as e:
            logger.error(f"Error creating tool instance for {tool_name}: {e}")
            return None