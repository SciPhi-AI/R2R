import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest
from core.parsers.media.docx_parser import DOCXParser
from core.parsers.media.pdf_parser import PDFParser
from core.parsers.media.ppt_parser import PPTParser
from core.parsers.structured.csv_parser import CSVParser
from core.parsers.structured.json_parser import JSONParser
from core.parsers.structured.xlsx_parser import XLSXParser
from core.parsers.text.html_parser import HTMLParser
from core.parsers.text.md_parser import MDParser
from core.parsers.text.text_parser import TextParser


@pytest.fixture(scope="session", autouse=True)
def event_loop_policy():
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())


@pytest.fixture(scope="function", autouse=True)
async def cleanup_tasks():
    yield
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_text_parser():
    try:
        parser = TextParser()
        data = "Simple text"
        async for result in parser.ingest(data):
            assert result == "Simple text"
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_json_parser():
    try:
        parser = JSONParser()
        data = json.dumps({"key": "value", "null_key": None})
        async for result in parser.ingest(data):
            assert "key: value" in result
            assert "null_key" not in result
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_html_parser():
    try:
        parser = HTMLParser()
        data = "<html><body><p>Hello World</p></body></html>"
        async for result in parser.ingest(data):
            assert result.strip() == "Hello World"
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
@patch("pypdf.PdfReader")
async def test_pdf_parser(mock_pdf_reader):
    try:
        parser = PDFParser()
        mock_pdf_reader.return_value.pages = [
            MagicMock(extract_text=lambda: "Page text")
        ]
        data = b"fake PDF data"
        async for result in parser.ingest(data):
            assert result == "Page text"
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
@patch("pptx.Presentation")
async def test_ppt_parser(mock_presentation):
    try:
        mock_slide = MagicMock()
        mock_shape = MagicMock(text="Slide text")
        mock_slide.shapes = [mock_shape]
        mock_presentation.return_value.slides = [mock_slide]
        parser = PPTParser()
        data = b"fake PPT data"
        async for result in parser.ingest(data):
            assert result == "Slide text"
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
@patch("docx.Document")
async def test_docx_parser(mock_document):
    try:
        mock_paragraph = MagicMock(text="Paragraph text")
        mock_document.return_value.paragraphs = [mock_paragraph]
        parser = DOCXParser()
        data = b"fake DOCX data"
        async for result in parser.ingest(data):
            assert result == "Paragraph text"
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_csv_parser():
    try:
        parser = CSVParser()
        data = "col1,col2\nvalue1,value2"
        async for result in parser.ingest(data):
            assert result == "col1, col2"
            break
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
@patch("openpyxl.load_workbook")
async def test_xlsx_parser(mock_load_workbook):
    try:
        mock_sheet = MagicMock()
        mock_sheet.iter_rows.return_value = [(1, 2), (3, 4)]
        mock_workbook = MagicMock(worksheets=[mock_sheet])
        mock_load_workbook.return_value = mock_workbook
        parser = XLSXParser()
        data = b"fake XLSX data"
        async for result in parser.ingest(data):
            assert result == "1, 2"
            break
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_markdown_parser():
    try:
        parser = MDParser()
        data = "# Header\nContent"
        async for result in parser.ingest(data):
            assert result.strip() == "Header\nContent"
    except asyncio.CancelledError:
        pass
