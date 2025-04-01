import os
from pathlib import Path, PurePath

from shared.abstractions import DocumentType


class RecursiveDirectoryFileScanner:
    """
    A class to recursively scan directories and filter files based on various criteria.
    """

    def __init__(
        self,
        root_dir,
        ignore_dirs: list[str] | str | None = None,
        accepted_exts: list[str] | None = None,
        ignore_exts: list[str] | str | None = None,
        include_file_at_specific_path=None,
        ignore_filenames=None,
        ignore_file_paths=None,
    ):
        # Check if root_dir is a valid path
        try:
            if PurePath(root_dir):
                self.root_dir = root_dir
        except (AttributeError, TypeError) as e:
            # Add "from e" to properly chain exceptions
            raise ValueError(
                f"Invalid root_dir: {root_dir}. Error: {e}. Does root_dir exist?"
            ) from e

        # If ignore_dirs is None. Initialize template variables for generic Python codebases
        self.ignore_dirs = ignore_dirs or [
            "__pycache__",
            ".vscode",
            ".github",
            "venv",
            ".venv",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
        ]

        # Convert accepted_exts to proper format
        if accepted_exts is None:
            # Get file extensions from DocumentType enum
            self.accepted_exts = []
            for doc_type in DocumentType:
                # Add the extension with a leading dot
                self.accepted_exts.append(f".{doc_type.value.lower()}")
        else:
            self.accepted_exts = accepted_exts

        # If ignore_exts is None. The file extension will not ignore any file
        # extensions declared in accepted_exts.
        self.ignore_exts = ignore_exts or []

        # If include_file_at_specific_path is None. Usefull for when you want to
        # ignore a whole directory but include a specific file or files within that directory.
        self.include_file_at_specific_path = (
            include_file_at_specific_path or []
        )

        # If ignore_filenames is set it will ignore the file names declared in the list[str] | str.
        self.ignore_filenames = ignore_filenames or []

        # This will ignore the ./dir/dir/file.ext path declared in the list[str] | str.
        self.ignore_file_paths = ignore_file_paths or []

    def scan(self) -> list[str] | None:
        """
        Scan the directory and return a list of files that match the criteria.

        Returns:
            list[str] or None: A list of file paths that match the criteria, None if no matches
        """
        matched_files = []

        # Normalize the ignore file paths for consistent comparison
        normalized_ignore_paths = [
            os.path.normpath(ignore) for ignore in self.ignore_file_paths
        ]

        # Special case: If include_file_at_specific_path is specified, we need to do a full scan first
        if self.include_file_at_specific_path:
            # Do a full scan to find special files, even in ignored directories
            for root, _, files in os.walk(self.root_dir):
                for filename in files:
                    if filename in self.include_file_at_specific_path:
                        file_path = os.path.join(root, filename)
                        matched_files.append(file_path)

        # Regular scan with directory filtering
        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            # Skip directories in the ignore list
            dirnames[:] = [d for d in dirnames if d not in self.ignore_dirs]

            for filename in filenames:
                # Skip files with ignored filenames
                if filename in self.ignore_filenames:
                    continue

                file_path = os.path.join(dirpath, filename)

                # Compute the relative path and normalize it
                rel_path = os.path.normpath(
                    os.path.relpath(file_path, self.root_dir)
                )

                # If this relative path is in the ignore list, skip this file
                if rel_path in normalized_ignore_paths:
                    continue

                # Check if file should be excluded based on extension
                if any(
                    filename.lower().endswith(ext.lower())
                    for ext in self.ignore_exts
                ):
                    continue

                # Include file if it meets either extension or name criteria
                ext_match = any(
                    filename.lower().endswith(ext.lower())
                    for ext in self.accepted_exts
                )
                name_match = filename in self.include_file_at_specific_path

                # If no filters are provided, include all files
                include_all = not (
                    self.accepted_exts or self.include_file_at_specific_path
                )

                if include_all or ext_match or name_match:
                    # Don't add duplicates from the special scan
                    if file_path not in matched_files:
                        matched_files.append(file_path)

        if matched_files == []:
            return None
        else:
            return matched_files


if __name__ == "__main__":
    # root_directory = f"f{Path.cwd().parent.parent.parent}"
    # ignore_dirs = ["__pycache__", ".vscode", ".github", "venv", ".venv", ".mypy_cache", ".pytest_cache", ".ruff_cache"]
    # ignore_files = ["docker/config/.env", ".git", ".gitignore"]
    # extensions = [".txt", ".py", ".md", ".conf", ".pdf", ".mdx", ".js", ".html", ".rst", ".json"]
    # filenames = ["Dockerfile"]
    # results = RecursiveDirectoryFileScanner(
    #     root_directory,
    #     ignore_dirs=ignore_dirs,
    #     ignore_file_paths=ignore_files,
    #     accepted_exts=extensions,
    #     include_file_at_specific_path=filenames
    # ).scan()

    root_directory = f"{Path.cwd()}"
    scanner = RecursiveDirectoryFileScanner(
        root_directory,
    )
    results = scanner.scan()

    # client = R2RClient("http://localhost:7272")

    # for file_path in results:
    #     # Ingest the file
    #     try:
    #         ingest_response = client.documents.create(file_path=file_path)
    #     except Exception as e:
    #         continue

    #     document_id = ingest_response.results.document_id
    #     # Extract entities and relationships
    #     extract_response = client.documents.extract(document_id)

    #     # View extracted knowledge
    #     # entities = client.documents.list_entities(document_id)
    #     # relationships = client.documents.list_relationships(document_id)
