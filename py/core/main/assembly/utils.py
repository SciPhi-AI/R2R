import logging
import os
import subprocess
import sys

logger = logging.getLogger()

def install_user_tool_dependencies(user_tools_path: str):
    """
    Installs dependencies listed in user_requirements.txt within the user tools directory.
    """
    requirements_path = os.path.join(user_tools_path, "user_requirements.txt")

    if os.path.exists(requirements_path):
        logger.info(f"Found user requirements file at: {requirements_path}. Attempting to install user tool dependencies...")
        try:
            # Use subprocess to run pip install
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", requirements_path],
                check=True,
                capture_output=True,
                text=True
            )
            logger.info("Successfully installed user tool dependencies.")
            logger.debug(f"pip install output:\n{result.stdout}")

            # Add the user tools path to sys.path AFTER successful installation
            parent_dir = os.path.dirname(user_tools_path)
            if parent_dir not in sys.path:
                sys.path.append(parent_dir)
                logger.info(f"Added '{parent_dir}' to sys.path for user tool imports.")
            # Also add the directory itself if tools are directly inside
            if user_tools_path not in sys.path:
                 sys.path.append(user_tools_path)
                 logger.info(f"Added '{user_tools_path}' to sys.path for user tool imports.")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install user tool dependencies from {requirements_path}.\nReturn code: {e.returncode}\nstdout:\n{e.stdout}stderr:\n{e.stderr}")
            raise RuntimeError(f"Failed to install user dependencies from {requirements_path}") from e
        except FileNotFoundError:
             logger.error(f"Error: '{sys.executable} -m pip' command not found. Make sure pip is installed in the Python environment.")
             raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during pip install: {e}")
            raise
    else:
        logger.warning(
            f"User requirements file not found at: {requirements_path}. Skipping user dependency installation."
        )
        
        # If the requirements file is not found, add the user tools path to sys.path
        parent_dir = os.path.dirname(user_tools_path)
        if parent_dir not in sys.path:
            sys.path.append(parent_dir)
            logger.info(f"Added '{parent_dir}' to sys.path for user tool imports (no requirements found).")
        if user_tools_path not in sys.path:
             sys.path.append(user_tools_path)
             logger.info(f"Added '{user_tools_path}' to sys.path for user tool imports (no requirements found).")