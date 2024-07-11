from typing import AsyncGenerator, TypeVar
from r2r.base.parsers.base_parser import AsyncParser
from r2r.base.abstractions.document import DataType

class LayoutExtraction(AsyncParser[DataType]):
    # a parser that extracts layout from an image
    def __init__(self):
        try: 
            import layoutparser as lp
            model = lp.AutoLayoutModel("lp://EfficientDtet/PubLayNet")
            self.model = model

        except ImportError:
            raise ValueError("Error, `layoutparser` is required to run `SubParserLayoutExtraction`. Please install it using `pip install layoutparser")

    async def ingest(self, data: DataType) -> AsyncGenerator[str, None]:
        if isinstance(data, str):
            raise ValueError("PDF data must be in bytes format.")
        
        layout = self.model.detect(data)
        yield layout


