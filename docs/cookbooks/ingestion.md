---
title: Ingestion
subtitle: Learn how to ingest, update, and delete documents with R2R
icon: file-arrow-up
slug: cookbooks/ingestion
---

## Introduction

R2R provides a powerful and flexible ingestion to process and manage various types of documents. It supports a wide range of file formats—text, documents, PDFs, images, audio, and even video—and transforms them into searchable, analyzable content. The ingestion process includes parsing, chunking, embedding, and optionally extracting entities and relationships for knowledge graph construction.

This cookbook will guide you through:

- Ingesting files, raw text, or pre-processed chunks
- Choosing an ingestion mode (`fast`, `hi-res`, `ocr`, or `custom`)
- Updating and deleting documents and chunks

For more on configuring ingestion, see the [Ingestion Configuration Overview](/self-hosting/configuration/ingestion).

### Supported File Types

R2R supports ingestion of the following document types:
| Category          | File types                                |
|-------------------|-------------------------------------------|
| Image             | `.bmp`, `.heic`, `.jpeg`, `.png`, `.tiff` |
| MP3               | `.mp3`                                    |
| PDF               | `.pdf`                                    |
| CSV               | `.csv`                                    |
| E-mail            | `.eml`, `.msg`, `.p7s`                    |
| EPUB              | `.epub`                                   |
| Excel             | `.xls`, `.xlsx`                           |
| HTML              | `.html`                                   |
| Markdown          | `.md`                                     |
| Org Mode          | `.org`                                    |
| Open Office       | `.odt`                                    |
| Plain text        | `.txt`                                    |
| PowerPoint        | `.ppt`, `.pptx`                           |
| reStructured Text | `.rst`                                    |
| Rich Text         | `.rtf`                                    |
| TSV               | `.tsv`                                    |
| Word              | `.doc`, `.docx`                           |
| Code              | `.py`, `.js`, `.ts`, `.css`               |

## Ingestion Modes

R2R offers four primary ingestion modes to tailor the process to your requirements:

- **`fast`**:
  A speed-oriented ingestion mode that prioritizes rapid processing with minimal enrichment. Summaries and some advanced parsing are skipped, making this ideal for quickly processing large volumes of documents.

- **`hi-res`**:
  A comprehensive, high-quality ingestion mode that may leverage multimodal foundation models (visual language models) for parsing complex documents and PDFs, even integrating image-based content.
  - On a **lite** deployment, R2R uses its built-in (`r2r`) parser.
  - On a **full** deployment, it can use `unstructured_local` or `unstructured_api` for more robust parsing and advanced features.
  Choose `hi-res` mode if you need the highest quality extraction, including image-to-text analysis and richer semantic segmentation.

- **`ocr`**:
  OCR mode utilizes optical character recognition models to convert PDFs to markdown. Currently, this mode requires use of Mistral OCR.

- **`custom`**:
  For advanced users who require fine-grained control. In `custom` mode, you provide a full `ingestion_config` dict or object to specify every detail: parser options, chunking strategy, character limits, and more.

**Example Usage:**
```python
file_path = 'path/to/file.txt'
metadata = {'key1': 'value1'}

# hi-res mode for thorough extraction
client.documents.create(
    file_path=file_path,
    metadata=metadata,
    ingestion_mode="hi-res"
)

# fast mode for quick processing
client.documents.create(
    file_path=file_path,
    ingestion_mode="fast"
)

# custom mode for full control
client.documents.create(
    file_path=file_path,
    ingestion_mode="custom",
    ingestion_config={
        "provider": "unstructured_local",
        "strategy": "auto",
        "chunking_strategy": "by_title",
        "new_after_n_chars": 256,
        "max_characters": 512,
        "combine_under_n_chars": 64,
        "overlap": 100,
    }
)
```

## Ingesting Documents

A `Document` represents ingested content in R2R. When you ingest a file, text, or chunks:

1. The file (or text) is parsed into text.
2. Text is chunked into manageable units.
3. Embeddings are generated for semantic search.
4. Content is stored for retrieval and optionally linked to the knowledge graph.

In a **full** R2R installation, ingestion is asynchronous. You can monitor ingestion status and confirm when documents are ready:

```zsh
client.documents.list()

# [
#  DocumentResponse(
#    id=UUID('e43864f5-a36f-548e-aacd-6f8d48b30c7f'),
#    collection_ids=[UUID('122fdf6a-e116-546b-a8f6-e4cb2e2c0a09')],
#    owner_id=UUID('2acb499e-8428-543b-bd85-0d9098718220'),
#    document_type=<DocumentType.PDF: 'pdf'>,
#    metadata={'title': 'DeepSeek_R1.pdf', 'version': 'v0'},
#    version='v0',
#    size_in_bytes=1768572,
#    ingestion_status=<IngestionStatus.SUCCESS: 'success'>,
#    extraction_status=<GraphExtractionStatus.PENDING: 'pending'>,
#    created_at=datetime.datetime(2025, 2, 8, 3, 31, 39, 126759, tzinfo=TzInfo(UTC)),
#    updated_at=datetime.datetime(2025, 2, 8, 3, 31, 39, 160114, tzinfo=TzInfo(UTC)),
#    ingestion_attempt_number=None,
#    summary="The document contains a comprehensive overview of DeepSeek-R1, a series of reasoning models developed by DeepSeek-AI, which includes DeepSeek-R1-Zero and DeepSeek-R1. DeepSeek-R1-Zero utilizes large-scale reinforcement learning (RL) without supervised fine-tuning, showcasing impressive reasoning capabilities but facing challenges like readability and language mixing. To enhance performance, DeepSeek-R1 incorporates multi-stage training and cold-start data, achieving results comparable to OpenAI's models on various reasoning tasks. The document details the models' training processes, evaluation results across multiple benchmarks, and the introduction of distilled models that maintain reasoning capabilities while being smaller and more efficient. It also discusses the limitations of current models, such as language mixing and sensitivity to prompts, and outlines future research directions to improve general capabilities and efficiency in software engineering tasks. The findings emphasize the potential of RL in developing reasoning abilities in large language models and the effectiveness of distillation techniques for smaller models.", summary_embedding=None, total_tokens=29673)] total_entries=1
#   ), ...
# ]
```

An `ingestion_status` of `"success"` confirms the document is fully ingested. You can also check the R2R dashboard at http://localhost:7273 for ingestion progress and status.

For more details on creating documents, [refer to the Create Document API](/api-and-sdks/documents/create-document).

## Ingesting Pre-Processed Chunks

If you have pre-processed chunks from your own pipeline, you can directly ingest them. This is especially useful if you've already divided content into logical segments.

```python
chunks = ["This is my first parsed chunk", "This is my second parsed chunk"]
client.documents.create(
    chunks=chunks,
    ingestion_mode="fast"  # use fast for a quick chunk ingestion
)
```

## Deleting Documents and Chunks

To remove documents or chunks, call their respective `delete` methods:

```python
# Delete a document
delete_response = client.documents.delete(document_id)

# Delete a chunk
delete_response = client.chunks.delete(chunk_id)
```

You can also delete documents by specifying filters using the [`by-filter`](/api-and-sdks/documents/delete-document-by-filter) route.

## Additional Configuration & Concepts

- **Light vs. Full Deployments:**
  - Light (default) uses R2R's built-in parser and supports synchronous ingestion.
  - Full deployments orchestrate ingestion tasks asynchronously and integrate with more complex providers like `unstructured_local`.

- **Provider Configuration:**
  Settings in `r2r.toml` or at runtime (`ingestion_config`) can adjust parsing and chunking strategies:
  - `fast` and `hi-res` modes are influenced by strategies like `"auto"` or `"hi_res"` in the unstructured provider.
  - `custom` mode allows you to override chunk size, overlap, excluded parsers, and more at runtime.

For detailed configuration options, see:
- [Data Ingestion Configuration](/self-hosting/configuration/ingestion)

## Conclusion

R2R's ingestion is flexible and efficient, allowing you to tailor ingestion to your needs:
- Use `fast` for quick processing.
- Use `hi-res` for high-quality, multimodal analysis.
- Use `custom` for advanced, granular control.

You can easily ingest documents or pre-processed chunks, update their content, and delete them when no longer needed. Combined with powerful retrieval and knowledge graph capabilities, R2R enables seamless integration of advanced document management into your applications.
