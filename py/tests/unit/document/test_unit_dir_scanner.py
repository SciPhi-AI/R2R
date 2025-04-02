import os
import sys
import pytest
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.utils import scan_directory  # Updated import
from shared.abstractions import DocumentType

class TestScanDirectory:
    """Tests for the scan_directory function"""

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

    def test_invalid_directory(self):
        """Test providing an invalid directory"""
        with pytest.raises(ValueError):
            scan_directory(None)

    def test_scan_default_params(self, setup_test_directory):
        """Test scanning with default parameters"""
        results = scan_directory(setup_test_directory)

        # Should find files but exclude __pycache__ directory
        assert results is not None
        assert len(results) > 0
        assert not any("__pycache__" in result for result in results)
        assert not any(".git" in result for result in results)

    def test_scan_with_ignore_dirs(self, setup_test_directory):
        """Test scanning with custom ignored directories"""
        results = scan_directory(
            setup_test_directory,
            ignore_dirs=["dir1", "__pycache__", ".git"]
        )

        # Should not contain any files from dir1
        assert results is not None
        assert not any("dir1" in result for result in results)
        assert any("dir2" in result for result in results)

    def test_scan_with_accepted_exts(self, setup_test_directory):
        """Test scanning with accepted extensions"""
        results = scan_directory(
            setup_test_directory,
            accepted_exts=[".py", ".js"]
        )

        # Should only include .py and .js files
        assert results is not None
        assert all(result.endswith((".py", ".js")) for result in results)
        assert not any(result.endswith(".txt") for result in results)
        assert not any(result.endswith(".pdf") for result in results)

    def test_scan_with_ignore_exts(self, setup_test_directory):
        """Test scanning with ignored extensions"""
        results = scan_directory(
            setup_test_directory,
            ignore_exts=[".log", ".pyc"]
        )

        # Should not include .log or .pyc files
        assert results is not None
        assert not any(result.endswith(".log") for result in results)
        assert not any(result.endswith(".pyc") for result in results)

    def test_scan_with_wildcards(self, setup_test_directory):
        """Test scanning with wildcard extensions from DocumentType"""
        # Create a PDF file to ensure it's picked up by wildcard
        (setup_test_directory / "special.PDF").write_text("uppercase pdf")

        results = scan_directory(setup_test_directory)

        # Both lowercase and uppercase PDF files should be included
        assert results is not None
        pdf_files = [r for r in results if os.path.basename(r).lower().endswith(".pdf")]
        assert len(pdf_files) >= 2

    def test_scan_with_include_specific_files(self, setup_test_directory):
        """Test including specific files even if they would otherwise be excluded"""
        # Create a file in an ignored directory
        special_file = "__pycache__/important.conf"
        (setup_test_directory / "__pycache__" / "important.conf").write_text("important config")

        results = scan_directory(
            setup_test_directory,
            include_file_at_specific_path=["important.conf"]
        )

        # Should find the important.conf file even though it's in an ignored directory
        assert results is not None
        assert any("important.conf" in result for result in results)

    def test_scan_with_ignore_filenames(self, setup_test_directory):
        """Test ignoring specific filenames"""
        results = scan_directory(
            setup_test_directory,
            ignore_filenames=["file1.txt", "file2.py"]
        )

        # These files should be excluded
        assert results is not None
        assert not any(result.endswith("file1.txt") for result in results)
        assert not any(result.endswith("file2.py") for result in results)

    def test_scan_with_ignore_paths(self, setup_test_directory):
        """Test ignoring specific file paths"""
        # Convert paths to relative for proper comparison
        ignore_path = os.path.join("dir1", "subdir1", "file7.py")

        results = scan_directory(
            setup_test_directory,
            ignore_file_paths=[ignore_path]
        )

        # This specific path should be excluded
        assert results is not None
        assert not any(result.endswith(ignore_path) for result in results)

    def test_scan_empty_result(self, setup_test_directory):
        """Test scanning with filters that result in no matches"""
        # Filter out everything
        results = scan_directory(
            setup_test_directory,
            accepted_exts=[".xyz"]  # Extension that doesn't exist
        )

        # Should return None when no files match
        assert results is None

    def test_scan_combination_filters(self, setup_test_directory):
        """Test scanning with a combination of filters"""
        results = scan_directory(
            setup_test_directory,
            ignore_dirs=["__pycache__"],
            accepted_exts=[".py"],
            ignore_filenames=["file2.py"]
        )

        # Should only include .py files that are not file2.py and not in __pycache__
        assert results is not None
        assert all(result.endswith(".py") for result in results)
        assert not any(result.endswith("file2.py") for result in results)
        assert not any("__pycache__" in result for result in results)
