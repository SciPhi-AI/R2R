# type: ignore
import xml.etree.ElementTree as ET
import zipfile
from typing import AsyncGenerator

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class ODTParser(AsyncParser[str | bytes]):
    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config
        self.zipfile = zipfile
        self.ET = ET

    async def ingest(
        self, data: str | bytes, **kwargs
    ) -> AsyncGenerator[str, None]:
        if isinstance(data, str):
            raise ValueError("ODT data must be in bytes format.")

        from io import BytesIO

        file_obj = BytesIO(data)

        try:
            with self.zipfile.ZipFile(file_obj) as odt:
                # ODT files are zip archives containing content.xml
                content = odt.read("content.xml")
                root = self.ET.fromstring(content)

                # ODT XML namespace
                ns = {"text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0"}

                # Extract paragraphs and headers
                for p in root.findall(".//text:p", ns):
                    text = "".join(p.itertext())
                    if text.strip():
                        yield text.strip()

                for h in root.findall(".//text:h", ns):
                    text = "".join(h.itertext())
                    if text.strip():
                        yield text.strip()

        except Exception as e:
            raise ValueError(f"Error processing ODT file: {str(e)}") from e
        finally:
            file_obj.close()
