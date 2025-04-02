import os
from pathlib import Path, PurePath

from shared.abstractions import DocumentType


def scan_directory(
    root_dir,
    ignore_dirs=None,
    accepted_exts=None,
    ignore_exts=None,
    include_file_at_specific_path=None,
    ignore_filenames=None,
    ignore_file_paths=None,
) -> list[str] | None:
    """
    Recursively scan a directory and filter files based on various criteria.

    Args:
        root_dir: Directory path to scan
        ignore_dirs: List of directory names to ignore
        accepted_exts: List of file extensions to include (e.g., [".py", ".txt"])
        ignore_exts: List of file extensions to exclude
        include_file_at_specific_path: List of filenames to include even in ignored dirs
        ignore_filenames: List of filenames to ignore
        ignore_file_paths: List of relative file paths to ignore

    Returns:
        list[str] or None: A list of file paths that match the criteria, None if no matches
    """
    # Check if root_dir is a valid path
    try:
        if root_dir is None:
            raise ValueError(
                "Invalid root_dir: None. Root directory cannot be None."
            )
        if PurePath(root_dir):
            pass
    except (AttributeError, TypeError) as e:
        # Add "from e" to properly chain exceptions
        raise ValueError(
            f"Invalid root_dir: {root_dir}. Error: {e}. Does root_dir exist?"
        ) from e

    # Set default values for parameters
    ignore_dirs = ignore_dirs or [
        "__pycache__",
        ".vscode",
        ".github",
        "venv",
        ".venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    ]

    # Handle accepted extensions
    if accepted_exts is None:
        # Get file extensions from DocumentType enum
        accepted_exts = []
        for doc_type in DocumentType:
            accepted_exts.append(f".{doc_type.value.lower()}")

    ignore_exts = ignore_exts or []
    include_file_at_specific_path = include_file_at_specific_path or []
    ignore_filenames = ignore_filenames or []
    ignore_file_paths = ignore_file_paths or []

    # Begin scanning
    matched_files = []

    # Normalize the ignore file paths for consistent comparison
    normalized_ignore_paths = [
        os.path.normpath(ignore) for ignore in ignore_file_paths
    ]

    # Special case: If include_file_at_specific_path is specified, we need to do a full scan first
    if include_file_at_specific_path:
        # Do a full scan to find special files, even in ignored directories
        for root, _, files in os.walk(root_dir):
            for filename in files:
                if filename in include_file_at_specific_path:
                    file_path = os.path.join(root, filename)
                    matched_files.append(file_path)

    # Regular scan with directory filtering
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip directories in the ignore list
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs]

        for filename in filenames:
            # Skip files with ignored filenames
            if filename in ignore_filenames:
                continue

            file_path = os.path.join(dirpath, filename)

            # Compute the relative path and normalize it
            rel_path = os.path.normpath(os.path.relpath(file_path, root_dir))

            # If this relative path is in the ignore list, skip this file
            if rel_path in normalized_ignore_paths:
                continue

            # Check if file should be excluded based on extension
            if any(
                filename.lower().endswith(ext.lower()) for ext in ignore_exts
            ):
                continue

            # Include file if it meets either extension or name criteria
            ext_match = any(
                filename.lower().endswith(ext.lower()) for ext in accepted_exts
            )
            name_match = filename in include_file_at_specific_path

            # If no filters are provided, include all files
            include_all = not (accepted_exts or include_file_at_specific_path)

            if include_all or ext_match or name_match:
                # Don't add duplicates from the special scan
                if file_path not in matched_files:
                    matched_files.append(file_path)

    if matched_files == []:
        return None
    else:
        return matched_files


if __name__ == "__main__":
    root_directory = f"{Path.cwd()}"
    results = scan_directory(
        root_directory,
    )

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
