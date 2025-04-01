import os
import sys
import pytest
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.utils.upload_directories_files import RecursiveDirectoryFileScanner
from shared.abstractions import DocumentType

class TestRecursiveDirectoryFileScanner:
    """Tests for the RecursiveDirectoryFileScanner class"""

    @pytest.fixture
    def setup_test_directory(self, tmp_path):
        """Create a test directory structure for scanning tests"""
        # Create directories
        (tmp_path / "dir1").mkdir()
        (tmp_path / "dir2").mkdir()
        (tmp_path / "dir1" / "subdir1").mkdir()
        (tmp_path / ".git").mkdir()
        (tmp_path / "__pycache__").mkdir()

        # Create files with various extensions
        (tmp_path / "file1.txt").write_text("test content")
        (tmp_path / "file2.py").write_text("print('hello')")
        (tmp_path / "file3.pdf").write_text("PDF content")
        (tmp_path / "file4.PDF").write_text("PDF content uppercase")
        (tmp_path / ".gitignore").write_text("*.pyc")
        (tmp_path / "dir1" / "file5.txt").write_text("nested text file")
        (tmp_path / "dir1" / "file6.log").write_text("log file")
        (tmp_path / "dir1" / "subdir1" / "file7.py").write_text("nested python file")
        (tmp_path / "dir2" / "file8.js").write_text("javascript file")
        (tmp_path / "dir2" / "file9.py").write_text("another python file")
        (tmp_path / "__pycache__" / "file10.pyc").write_text("compiled python")

        return tmp_path

    def test_initialization(self):
        """Test basic initialization of the scanner"""
        scanner = RecursiveDirectoryFileScanner(".")
        assert scanner.root_dir == "."
        assert "__pycache__" in scanner.ignore_dirs
        assert isinstance(scanner.accepted_exts, list)
        assert scanner.ignore_exts == []
        assert scanner.include_file_at_specific_path == []
        assert scanner.ignore_filenames == []
        assert scanner.ignore_file_paths == []

    def test_initialization_with_invalid_dir(self):
        """Test initialization with invalid directory"""
        with pytest.raises(ValueError):
            RecursiveDirectoryFileScanner(None)

    def test_scan_default_params(self, setup_test_directory):
        """Test scanning with default parameters"""
        scanner = RecursiveDirectoryFileScanner(setup_test_directory)
        results = scanner.scan()

        # Should find files but exclude __pycache__ directory
        assert len(results) > 0
        assert not any("__pycache__" in result for result in results)
        assert not any(".git" in result for result in results)

    def test_scan_with_ignore_dirs(self, setup_test_directory):
        """Test scanning with custom ignored directories"""
        scanner = RecursiveDirectoryFileScanner(
            setup_test_directory,
            ignore_dirs=["dir1", "__pycache__", ".git"]
        )
        results = scanner.scan()

        # Should not contain any files from dir1
        assert not any("dir1" in result for result in results)
        assert any("dir2" in result for result in results)

    def test_scan_with_accepted_exts(self, setup_test_directory):
        """Test scanning with accepted extensions"""
        scanner = RecursiveDirectoryFileScanner(
            setup_test_directory,
            accepted_exts=[".py", ".js"]
        )
        results = scanner.scan()

        # Should only include .py and .js files
        assert all(result.endswith((".py", ".js")) for result in results)
        assert not any(result.endswith(".txt") for result in results)
        assert not any(result.endswith(".pdf") for result in results)

    def test_scan_with_ignore_exts(self, setup_test_directory):
        """Test scanning with ignored extensions"""
        scanner = RecursiveDirectoryFileScanner(
            setup_test_directory,
            ignore_exts=[".log", ".pyc"]
        )
        results = scanner.scan()

        # Should not include .log or .pyc files
        assert not any(result.endswith(".log") for result in results)
        assert not any(result.endswith(".pyc") for result in results)

    def test_scan_with_wildcards(self, setup_test_directory):
        """Test scanning with wildcard extensions from DocumentType"""
        # Create a PDF file to ensure it's picked up by wildcard
        (setup_test_directory / "special.PDF").write_text("uppercase pdf")

        scanner = RecursiveDirectoryFileScanner(setup_test_directory)
        results = scanner.scan()

        # Both lowercase and uppercase PDF files should be included
        pdf_files = [r for r in results if os.path.basename(r).lower().endswith(".pdf")]
        assert len(pdf_files) >= 2

    def test_scan_with_include_specific_files(self, setup_test_directory):
        """Test including specific files even if they would otherwise be excluded"""
        # Create a file in an ignored directory
        special_file = "__pycache__/important.conf"
        (setup_test_directory / "__pycache__" / "important.conf").write_text("important config")

        scanner = RecursiveDirectoryFileScanner(
            setup_test_directory,
            include_file_at_specific_path=["important.conf"]
        )
        results = scanner.scan()

        # Should find the important.conf file even though it's in an ignored directory
        assert any("important.conf" in result for result in results)

    def test_scan_with_ignore_filenames(self, setup_test_directory):
        """Test ignoring specific filenames"""
        scanner = RecursiveDirectoryFileScanner(
            setup_test_directory,
            ignore_filenames=["file1.txt", "file2.py"]
        )
        results = scanner.scan()

        # These files should be excluded
        assert not any(result.endswith("file1.txt") for result in results)
        assert not any(result.endswith("file2.py") for result in results)

    def test_scan_with_ignore_paths(self, setup_test_directory):
        """Test ignoring specific file paths"""
        # Convert paths to relative for proper comparison
        ignore_path = os.path.join("dir1", "subdir1", "file7.py")

        scanner = RecursiveDirectoryFileScanner(
            setup_test_directory,
            ignore_file_paths=[ignore_path]
        )
        results = scanner.scan()

        # This specific path should be excluded
        assert not any(result.endswith(ignore_path) for result in results)

    def test_scan_empty_result(self, setup_test_directory):
        """Test scanning with filters that result in no matches"""
        # Filter out everything
        scanner = RecursiveDirectoryFileScanner(
            setup_test_directory,
            accepted_exts=[".xyz"]  # Extension that doesn't exist
        )
        results = scanner.scan()

        # Should return None when no files match
        assert results is None

    def test_scan_combination_filters(self, setup_test_directory):
        """Test scanning with a combination of filters"""
        scanner = RecursiveDirectoryFileScanner(
            setup_test_directory,
            ignore_dirs=["__pycache__"],
            accepted_exts=[".py"],
            ignore_filenames=["file2.py"]
        )
        results = scanner.scan()

        # Should only include .py files that are not file2.py and not in __pycache__
        assert all(result.endswith(".py") for result in results)
        assert not any(result.endswith("file2.py") for result in results)
        assert not any("__pycache__" in result for result in results)
