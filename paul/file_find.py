import os
import requests
from r2r import R2RClient
from time import sleep

def scan_directory(root_dir, ignore_dirs=None, accepted_exts=None, accepted_names=None, ignore_file_paths=None):
    """
    Scan through the directory structure starting at root_dir.

    Parameters:
        root_dir (str): The root directory to start scanning.
        ignore_dirs (list, optional): Directory names to ignore.
        accepted_exts (list, optional): File extensions to accept (e.g., ['.txt', '.py']).
        accepted_names (list, optional): Specific file names to accept.
        ignore_file_paths (list, optional): Specific file paths (relative to root_dir) to ignore.

    Returns:
        list: A list of file paths that match the criteria.
    """
    if ignore_dirs is None:
        ignore_dirs = []
    if accepted_exts is None:
        accepted_exts = []
    if accepted_names is None:
        accepted_names = []
    if ignore_file_paths is None:
        ignore_file_paths = []

    matched_files = []

    # Normalize the ignore file paths for consistent comparison
    normalized_ignore_paths = [os.path.normpath(ignore) for ignore in ignore_file_paths]

    # Walk through the directory tree
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip directories in the ignore list
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs]

        for file in filenames:
            file_path = os.path.join(dirpath, file)
            # Compute the relative path and normalize it
            rel_path = os.path.normpath(os.path.relpath(file_path, root_dir))

            # If this relative path is in the ignore list, skip this file.
            if rel_path in normalized_ignore_paths:
                continue

            # Check if the file's extension or file name matches accepted criteria
            ext_match = any(file.lower().endswith(ext.lower()) for ext in accepted_exts)
            name_match = file in accepted_names

            if ext_match or name_match:
                matched_files.append(file_path)

    return matched_files

 
if __name__ == "__main__":
    root_directory = "/home/win/Documents/code/DisBot/"
    ignore_specific_files = ["config/.env"]
    ignore = [".git", ".gitignore", "__pycache__", ".vscode", ".github", "venv", ".venv", "envdisbot"]
    extensions = [".txt", ".py", ".md", ".sh", ".yml", ".yaml", ".ini", ".mdx", ".toml", ".rst", ".conf"]
    filenames = ["Dockerfile"]
    results = scan_directory(root_directory, ignore_dirs=ignore, accepted_exts=extensions, accepted_names=filenames)

    client = R2RClient("http://localhost:7272")

    for file_path in results:
        # Ingest the file
        print(f"In Processing Loop: {file_path}")
        try:
            ingest_response = client.documents.create(file_path=file_path)
        except Exception as e:
            print(f"Error: {e}")
            continue 

        print(f"Processing {file_path}")
        
        document_id = ingest_response.results.document_id
        print(f'Added Doc: {document_id}')
        # Extract entities and relationships
        extract_response = client.documents.extract(document_id)

        # View extracted knowledge
        # entities = client.documents.list_entities(document_id)
        # relationships = client.documents.list_relationships(document_id)

        # print(f"entities: {entities}\n")
        # print (f"relationships: {relationships}\n\n")
