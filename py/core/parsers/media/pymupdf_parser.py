# type: ignore
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parents[4]))

import logging
import string
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)
from uuid import UUID, uuid4

import fitz

logger = logging.getLogger()


T = TypeVar("T")


class AsyncParser(ABC, Generic[T]):
    @abstractmethod
    async def ingest(self, data: T, **kwargs) -> AsyncGenerator[str, None]:
        pass


@dataclass
class DocumentChunk:
    id: UUID
    document_id: UUID
    owner_id: UUID
    collection_ids: List[UUID]
    data: str
    metadata: Dict


@dataclass
class Document:
    id: UUID
    owner_id: UUID
    collection_ids: List[UUID]


@dataclass
class FontAnalysis:
    sizes: Dict[float, int]
    body_size: float
    header_levels: Dict[float, int]


class PDFAnalyzer:
    def __init__(self, doc: fitz.Document):
        self.doc = doc
        self.analysis = self._analyze_document()

    def _analyze_document(self) -> FontAnalysis:
        sizes = self._collect_font_sizes()
        body_size = self._determine_body_size(sizes)
        header_levels = self._create_header_levels(sizes, body_size)
        return FontAnalysis(sizes, body_size, header_levels)

    def _collect_font_sizes(self) -> Dict[float, int]:
        sizes: Dict[float, int] = {}
        for page in self.doc:
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") != 0:
                    continue
                self._process_block_fonts(block, sizes)
        return sizes

    def _process_block_fonts(self, block: Dict, sizes: Dict[float, int]) -> None:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if text := span.get("text", "").strip():
                    size = round(span["size"], 1)
                    sizes[size] = sizes.get(size, 0) + len(text)

    def _determine_body_size(self, sizes: Dict[float, int]) -> float:
        return max(sizes.items(), key=lambda x: x[1])[0]

    def _create_header_levels(
        self, sizes: Dict[float, int], body_size: float
    ) -> Dict[float, int]:
        larger_sizes = sorted(
            [size for size in sizes if size > body_size], reverse=True
        )[:6]
        return {size: level for level, size in enumerate(larger_sizes, start=1)}

    def get_header_level(self, span: Dict) -> Optional[int]:
        return self.analysis.header_levels.get(round(span["size"], 1))


class RectHelper:
    @staticmethod
    def merge_rects(rect1: fitz.Rect, rect2: fitz.Rect) -> fitz.Rect:
        return fitz.Rect(
            min(rect1.x0, rect2.x0),
            min(rect1.y0, rect2.y0),
            max(rect1.x1, rect2.x1),
            max(rect1.y1, rect2.y1),
        )

    @staticmethod
    def normalize_rects(
        rects: List[fitz.Rect], page_rect: fitz.Rect
    ) -> List[fitz.Rect]:
        return [fitz.Rect(r.x0, page_rect.y0, r.x1, page_rect.y1) for r in rects]


class PDFExtractor:
    def __init__(self):
        self.text_flags = (
            fitz.TEXT_DEHYPHENATE
            | fitz.TEXT_PRESERVE_LIGATURES
            | fitz.TEXT_PRESERVE_WHITESPACE
        )
        self.processed_content: Set[int] = set()
        self._white = set(string.whitespace)
        self.rect_helper = RectHelper()

    def _is_white(self, text: str) -> bool:
        return self._white.issuperset(text)

    def _get_raw_lines(
        self,
        textpage: fitz.TextPage,
        clip: Optional[fitz.Rect] = None,
        tolerance: float = 3,
    ) -> List[Tuple[fitz.Rect, List[Dict]]]:
        if clip is None:
            clip = textpage.rect

        blocks = [
            b
            for b in textpage.extractDICT()["blocks"]
            if b["type"] == 0 and not fitz.Rect(b["bbox"]).is_empty
        ]

        spans = []
        for bno, block in enumerate(blocks):
            for lno, line in enumerate(block["lines"]):
                for span in line["spans"]:
                    span_rect = fitz.Rect(span["bbox"])
                    if abs(span_rect & clip) < abs(span_rect) * 0.8:
                        continue
                    if self._is_white(span["text"]):
                        continue
                    span["bbox"] = span_rect
                    span["line"] = lno
                    span["block"] = bno
                    spans.append(span)

        if not spans:
            return []

        spans.sort(key=lambda s: s["bbox"].y1)
        lines = []
        current_line = [spans[0]]
        line_rect = spans[0]["bbox"]

        for span in spans[1:]:
            span_rect = span["bbox"]
            prev_rect = current_line[-1]["bbox"]

            if (
                abs(span_rect.y1 - prev_rect.y1) <= tolerance
                or abs(span_rect.y0 - prev_rect.y0) <= tolerance
            ):
                current_line.append(span)
                line_rect |= span_rect
                continue

            current_line.sort(key=lambda s: s["bbox"].x0)
            lines.append([line_rect, current_line])

            current_line = [span]
            line_rect = span_rect

        current_line.sort(key=lambda s: s["bbox"].x0)
        lines.append([line_rect, current_line])

        return lines

    def _get_header_margin(self, page: fitz.Page) -> float:
        # not using atm
        header_margin = 0
        for item in page.get_drawings():
            if item["type"] == "line":
                x_start, y_start, x_end, y_end = item["points"]
                if y_start == y_end and (header_margin == 0 or y_start < header_margin):
                    header_margin = y_start
        return header_margin

    def extract_line_spans(
        self, textpage: fitz.TextPage, clip: Optional[fitz.Rect] = None
    ) -> List[Tuple[fitz.Rect, List[Dict]]]:
        return self._get_raw_lines(textpage, clip=clip)

    def extract_columns(
        self, page: fitz.Page, exclude_areas: List[fitz.Rect] = None
    ) -> List[fitz.Rect]:
        blocks = [
            (fitz.Rect(b[:4]), b[4]) for b in page.get_text("blocks") if b[6] == 0
        ]

        if len(blocks) < 2:
            return [page.rect]

        page_center = page.rect.width / 2
        min_width = page.rect.width * 0.2

        left_blocks = []
        right_blocks = []

        for block_rect, text in blocks:
            if block_rect.width < min_width:
                continue

            if block_rect.x0 < page_center and block_rect.x1 < (page_center + 50):
                left_blocks.append(block_rect)
            elif block_rect.x0 > (page_center - 50):
                right_blocks.append(block_rect)

        if not left_blocks or not right_blocks:
            return [page.rect]

        left_x0 = min(b.x0 for b in left_blocks)
        left_x1 = max(b.x1 for b in left_blocks)
        right_x0 = min(b.x0 for b in right_blocks)
        right_x1 = max(b.x1 for b in right_blocks)

        margin = 5
        columns = [
            fitz.Rect(left_x0 - margin, page.rect.y0, left_x1 + margin, page.rect.y1),
            fitz.Rect(right_x0 - margin, page.rect.y0, right_x1 + margin, page.rect.y1),
        ]

        return columns

    def _get_column_boxes(self, page: fitz.Page, **kwargs) -> List[fitz.Rect]:
        return self._column_boxes(page, **kwargs)

    def _merge_overlapping_columns(self, boxes: List[fitz.Rect]) -> List[fitz.Rect]:
        if not boxes:
            return []

        merged = []
        current = boxes[0]

        for box in boxes[1:]:
            if self._boxes_overlap_horizontally(current, box):
                current = self.rect_helper.merge_rects(current, box)
            else:
                merged.append(current)
                current = box

        merged.append(current)
        return merged

    def _boxes_overlap_horizontally(self, box1: fitz.Rect, box2: fitz.Rect) -> bool:
        overlap_threshold = 0.3
        overlap = min(box1.x1, box2.x1) - max(box1.x0, box2.x0)
        width = min(box1.width, box2.width)
        return overlap > width * overlap_threshold

    def _can_extend(
        self,
        temp: fitz.Rect,
        bb: fitz.Rect,
        bboxlist: List[fitz.Rect],
        vert_bboxes: List[fitz.Rect],
    ) -> bool:
        return all(
            b is None or b == bb or (temp & b).is_empty
            for b in bboxlist
            if not self._intersects_bboxes(temp, vert_bboxes)
        )

    def _in_bbox(self, bb: fitz.Rect, bboxes: List[fitz.Rect]) -> int:
        return next((i + 1 for i, bbox in enumerate(bboxes) if bb in bbox), 0)

    def _intersects_bboxes(self, bb: fitz.Rect, bboxes: List[fitz.Rect]) -> bool:
        return any(not (bb & bbox).is_empty for bbox in bboxes)

    def _extend_bbox(
        self,
        bboxes: List[fitz.Rect],
        path_bboxes: List[fitz.Rect],
        vert_bboxes: List[fitz.Rect],
        img_bboxes: List[fitz.Rect],
        extend_right: bool = True,
        width: Optional[int] = None,
    ) -> List[fitz.Rect]:
        result = []
        for bb in bboxes:
            if (
                bb is None
                or self._in_bbox(bb, path_bboxes)
                or self._in_bbox(bb, img_bboxes)
            ):
                continue

            temp = +bb
            if extend_right:
                temp.x1 = width
            else:
                temp.x0 = 0

            if self._intersects_bboxes(temp, path_bboxes + vert_bboxes + img_bboxes):
                result.append(bb)
                continue

            if self._can_extend(temp, bb, bboxes, vert_bboxes):
                result.append(temp)
            else:
                result.append(bb)
        return [b for b in result if b is not None]

    def _clean_blocks(self, blocks: List[fitz.Rect]) -> List[fitz.Rect]:
        if len(blocks) < 2:
            return blocks

        blocks = [b for i, b in enumerate(blocks) if i == 0 or b != blocks[i - 1]]

        y1 = blocks[0].y1
        i0 = 0
        i1 = -1

        for i in range(1, len(blocks)):
            b1 = blocks[i]
            if abs(b1.y1 - y1) > 10:
                if i1 > i0:
                    blocks[i0 : i1 + 1] = sorted(
                        blocks[i0 : i1 + 1], key=lambda b: b.x0
                    )
                y1 = b1.y1
                i0 = i
            i1 = i

        if i1 > i0:
            blocks[i0 : i1 + 1] = sorted(blocks[i0 : i1 + 1], key=lambda b: b.x0)
        return blocks

    def _column_boxes(
        self,
        page: fitz.Page,
        *,
        footer_margin: int = 50,
        header_margin: int = 50,
        no_image_text: bool = True,
        textpage: Optional[fitz.TextPage] = None,
        paths: Optional[List] = None,
        avoid: Optional[List[fitz.Rect]] = None,
    ) -> List[fitz.Rect]:
        clip = +page.rect
        clip.y1 -= footer_margin
        clip.y0 += header_margin

        paths = paths or page.get_drawings()
        textpage = textpage or page.get_textpage(clip=clip, flags=fitz.TEXTFLAGS_TEXT)

        bboxes = []
        path_bboxes = [p["rect"].irect for p in paths]
        path_bboxes.sort(key=lambda b: (b.y0, b.x0))

        img_bboxes = list(avoid or [])
        for item in page.get_images():
            img_bboxes.extend(page.get_image_rects(item[0]))

        vert_bboxes = []
        blocks = textpage.extractDICT()["blocks"]

        for block in blocks:
            bbox = fitz.IRect(block["bbox"])
            if no_image_text and self._in_bbox(bbox, img_bboxes):
                continue

            if block["lines"][0]["dir"] != (1, 0):
                vert_bboxes.append(bbox)
                continue

            srect = fitz.EMPTY_IRECT()
            for line in block["lines"]:
                text = "".join([s["text"].strip() for s in line["spans"]])
                if len(text) > 1:
                    srect |= fitz.IRect(line["bbox"])

            if not srect.is_empty:
                bboxes.append(+srect)

        if not bboxes:
            return []

        bboxes.sort(key=lambda k: (self._in_bbox(k, path_bboxes), k.y0, k.x0))
        bboxes = self._extend_bbox(
            bboxes, path_bboxes, vert_bboxes, img_bboxes, True, int(page.rect.width)
        )
        bboxes = self._extend_bbox(bboxes, path_bboxes, vert_bboxes, img_bboxes, False)

        nblocks = [bboxes[0]]
        remaining_bboxes = bboxes[1:]

        for i, bb in enumerate(remaining_bboxes):
            check = False
            for j, nbb in enumerate(nblocks):
                if (
                    bb is None
                    or nbb.x1 < bb.x0
                    or bb.x1 < nbb.x0
                    or self._in_bbox(nbb, path_bboxes) != self._in_bbox(bb, path_bboxes)
                ):
                    continue

                temp = bb | nbb
                if self._can_extend(temp, nbb, nblocks, vert_bboxes):
                    check = True
                    break

            if not check:
                nblocks.append(bb)
                j = len(nblocks) - 1
                temp = nblocks[j]

            if self._can_extend(temp, bb, remaining_bboxes, vert_bboxes):
                nblocks[j] = temp
            else:
                nblocks.append(bb)
            remaining_bboxes[i] = None

        return self._clean_blocks(nblocks)

    def extract_tables(self, page: fitz.Page) -> Tuple[List[Any], Dict[int, fitz.Rect]]:
        tabs = page.find_tables(strategy="lines_strict")
        tab_rects = {}
        tables = []

        for i, t in enumerate(tabs):
            tab_rects[i] = fitz.Rect(t.bbox) | fitz.Rect(t.header.bbox)
            tab_dict = {
                "bbox": tuple(tab_rects[i]),
                "rows": t.row_count,
                "columns": t.col_count,
            }
            tables.append(tab_dict)

        return tabs, tab_rects

    def process_text_span(self, span: Dict) -> str:
        text = span["text"].strip()
        if not text:
            return ""

        flags = span.get("flags", 0)
        modifiers = {
            16: "**{}**",  # bold
            2: "_{}_",  # italic
            8: "`{}`",  # monospace
        }

        for flag, format_str in modifiers.items():
            if flags & flag:
                text = format_str.format(text)

        return text


class PyMuPDFParser(AsyncParser[str | bytes]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_section = None
        self.current_font_size = None
        self.last_bbox = None
        self._verify_fitz_version()
        self.text_flags = (
            fitz.TEXT_DEHYPHENATE
            | fitz.TEXT_PRESERVE_LIGATURES
            | fitz.TEXT_PRESERVE_WHITESPACE
        )
        self.processed_content: Set[int] = set()
        self.previous_chunk = None

    def _verify_fitz_version(self):
        if fitz.pymupdf_version_tuple < (1, 24, 2):
            raise ImportError("PyMuPDF version 1.24.2 or later required")

    def _process_tables(
        self,
        tables: List[Any],
        tab_rects: Dict[int, fitz.Rect],
        line_rect: Optional[fitz.Rect],
        clip: fitz.Rect,
    ) -> str:
        out_string = ""
        for i, _ in sorted(
            [
                j
                for j in tab_rects.items()
                if j[1].y1 <= line_rect.y0 and not (j[1] & clip).is_empty
            ],
            key=lambda j: (j[1].y1, j[1].x0),
        ):
            out_string += "\n" + tables[i].to_markdown(clean=False) + "\n"
            del tab_rects[i]

        return out_string

    async def _process_page(
        self,
        page: fitz.Page,
        page_num: int,
        analyzer: PDFAnalyzer,
        extractor: PDFExtractor,
        document: Document,
    ) -> AsyncGenerator[DocumentChunk, None]:
        textpage = page.get_textpage(flags=self.text_flags)
        raw_tables, tab_rects = extractor.extract_tables(page)
        columns = extractor.extract_columns(page)
        processed_tables = set()

        def is_within_table(rect: fitz.Rect) -> bool:
            return any(table_rect.intersects(rect) for table_rect in tab_rects.values())

        for col_idx, column in enumerate(columns):
            lines = extractor.extract_line_spans(textpage, clip=column)

            for line_rect, spans in lines:
                if not spans:
                    continue

                content_hash = hash(
                    f"{column}_{line_rect}_{[s['text'] for s in spans]}"
                )
                if content_hash in self.processed_content:
                    continue

                span = spans[0]
                header_level = analyzer.get_header_level(span)
                span_font_size = round(span["size"], 1)

                if (
                    self.current_section is None
                    or header_level
                    or (
                        self.current_font_size
                        and span_font_size != self.current_font_size
                        and not (
                            self.last_bbox
                            and abs(line_rect.y0 - self.last_bbox.y1) < 15
                            and (
                                len(columns) == 1
                                or abs(line_rect.x0 - self.last_bbox.x0) < 50
                            )
                        )
                    )
                ):
                    if self.current_section and self.current_section["text"]:
                        chunk = await self._create_chunk(
                            self.current_section, document, page_num
                        )
                        if chunk:
                            yield chunk

                    self.current_section = {
                        "text": [],
                        "metadata": {
                            "page_number": page_num + 1,
                            "header_level": header_level,
                            "column": col_idx + 1,
                            "bbox": tuple(line_rect),
                            "tables": [],
                            "graphics": [],
                        },
                    }

                if not is_within_table(line_rect):
                    text_content = " ".join(
                        extractor.process_text_span(s) for s in spans
                    ).strip()
                    if text_content:
                        self.current_section["text"].append(text_content)
                        self.processed_content.add(content_hash)

                for table_idx, table in enumerate(raw_tables):
                    table_rect = tab_rects[table_idx]
                    if (
                        table_idx not in processed_tables
                        and line_rect.y0 <= table_rect.y1
                        and line_rect.y1 >= table_rect.y0
                    ):
                        table_md = table.to_markdown(clean=True)
                        if table_md:
                            self.current_section["text"].append(f"\n{table_md}\n")
                            self.current_section["metadata"]["tables"].append(
                                {
                                    "id": table_idx,
                                    "bbox": tuple(table_rect),
                                    "rows": table.row_count,
                                    "cols": table.col_count,
                                }
                            )
                            processed_tables.add(table_idx)

                self.current_font_size = span_font_size
                self.last_bbox = line_rect

        if self.current_section and self.current_section["text"]:
            chunk = await self._create_chunk(self.current_section, document, page_num)
            if chunk:
                yield chunk

    def _is_sequential_text(
        self, line_rect: fitz.Rect, columns: List[fitz.Rect]
    ) -> bool:
        return (
            self.last_bbox
            and abs(line_rect.y0 - self.last_bbox.y1) < 15
            and (len(columns) == 1 or abs(line_rect.x0 - self.last_bbox.x0) < 50)
        )

    async def ingest(
        self, data: Union[str, bytes], **kwargs
    ) -> AsyncGenerator[DocumentChunk, None]:
        document = kwargs.get("document")
        if not document:
            raise ValueError("document instance required in kwargs")

        doc = None
        try:
            doc = fitz.open(stream=data) if isinstance(data, bytes) else fitz.open(data)

            if doc.needs_pass and not doc.authenticate(""):
                raise ValueError("Encrypted PDF requires password")

            if doc.page_count == 0:
                raise ValueError("Document contains no pages")

            analyzer = PDFAnalyzer(doc)
            extractor = PDFExtractor()

            logger.info(
                f"Processing document {document.id} with {doc.page_count} pages"
            )

            for page_num in range(doc.page_count):
                try:
                    async for chunk in self._process_page(
                        doc[page_num], page_num, analyzer, extractor, document
                    ):
                        yield chunk
                except Exception as e:
                    logger.error(f"Error processing page {page_num}: {str(e)}")

            if self.previous_chunk:
                yield self.previous_chunk
                self.previous_chunk = None

        except Exception as e:
            logger.error(f"Error processing document {document.id}: {str(e)}")
            raise
        finally:
            if doc:
                doc.close()

    async def _create_chunk(
        self, section: Dict, document: Document, page_num: int
    ) -> Optional[DocumentChunk]:
        content = "\n".join(section["text"]).strip()
        if not content:
            return None

        if self.previous_chunk and content.startswith(self.previous_chunk.data):
            self.previous_chunk = None
            chunk_id = uuid4()
            chunk = DocumentChunk(
                id=chunk_id,
                document_id=document.id,
                owner_id=document.owner_id,
                collection_ids=document.collection_ids,
                data=content,
                metadata=section["metadata"],
            )
            return chunk

        chunk_id = uuid4()
        chunk = DocumentChunk(
            id=chunk_id,
            document_id=document.id,
            owner_id=document.owner_id,
            collection_ids=document.collection_ids,
            data=content,
            metadata=section["metadata"],
        )

        if self.previous_chunk:
            prev_chunk = self.previous_chunk
            self.previous_chunk = chunk
            return prev_chunk

        self.previous_chunk = chunk
        return None


# Local testing of PyMuPDFParser:
#
# 1. Create a PyMuPDFParser instance and Document:
#    parser = PyMuPDFParser()
#    document = Document(id=uuid4(), owner_id=uuid4(), collection_ids=[uuid4()])
#
# 2. Process PDF and get chunks:
#    async for chunk in parser.ingest("path/to/pdf", document=document):
#        # Each chunk contains:
#        # - chunk.id: UUID of the chunk
#        # - chunk.document_id: ID of source document
#        # - chunk.owner_id: Owner ID
#        # - chunk.collection_ids: List of collection IDs
#        # - chunk.data: Actual text content
#        # - chunk.metadata: Dict with page_number, header_level etc
#
# 3. Save chunks to JSON:
#    chunks_data = []
#    for chunk in chunks:
#        chunks_data.append({
#            "id": str(chunk.id),
#            "document_id": str(chunk.document_id),
#            "owner_id": str(chunk.owner_id),
#            "collection_ids": [str(id) for id in chunk.collection_ids],
#            "data": chunk.data,
#            "metadata": chunk.metadata
#        })
#
#    with open("output.json", "w") as f:
#        json.dump({"chunks": chunks_data}, f, indent=2)
#
# 4. Run with asyncio:
#    asyncio.run(process_pdf())
