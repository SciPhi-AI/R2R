# Ellen V2: R2R Customization Guide

**Version**: 1.0

This document provides a technical specification for custom modules extending the R2R framework. These modules live in `apps/r2r_extensions` and represent Ellen V2's unique Knowledge Layer value.

## 1. Custom r2r.toml Configuration
**Location**: `apps/r2r_extensions/config/r2r.toml`

```toml
[ingestion]
chunking_strategy = "ellen_hierarchical"  # Maps to our custom provider

[parsing]
parser_providers = { 
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" = "ellen_structured_data", 
  "image/png" = "ellen_image_to_narrative" 
}

[orchestration]
provider = "ellen_tool_augmented"
```

## 2. Custom Ingestion Parsers

### 2.1. StructuredDataParser
**Purpose**: Process .xlsx/.csv files, extracting structured data and narrative summaries.

**Logic**:
1. **Heuristic Extraction**:
   - Use pandas to detect tables
   - Clean headers and normalize data
2. **LLM Fallback**:
   - Generate parser spec for complex layouts
3. **Narrative Generation**:
   - Pass tidy data to LLM to generate markdown summary
4. **Data Storage**:
   - Insert structured data into `spreadsheet_cells` table

**Output**: Narrative summary with metadata `source_type: 'spreadsheet'`

### 2.2. ImageToNarrativeParser
**Purpose**: Process images within documents (e.g., PDFs).

**Logic**:
1. Receive image binary
2. Use multimodal LLM (e.g., GPT-4o) to generate descriptive narrative

**Output**: Generated text unified with document's main text

## 3. Custom Chunking Provider

### 3.1. HierarchicalChunkingProvider
**Purpose**: Implement "Parent/Child" chunking strategy.

**Logic**:
1. **Child Chunks**:
   - Split document using recursive character splitter
2. **Parent Chunks**:
   - Group child chunks (3-5 per group)
   - Generate section summaries using LLM
3. **Linking**:
   - Save both chunk types to database
   - Set `parent_chunk_id` for child chunks

**Retrieval**:
- Parent chunks provide high-level context
- Child chunks provide detailed source text

## 4. Custom Orchestration Provider

### 4.1. ToolAugmentedOrchestrationProvider
**Purpose**: Enable Text-to-SQL retrieval within RAG pipeline.

**Logic**:
1. **Initial Search**: Perform standard hybrid vector search
2. **Metadata Inspection**: Check `source_type` in top chunks
3. **Workflow Pivot**:
   - If `source_type == 'spreadsheet'`, trigger tool workflow
4. **Text-to-SQL Generation**:
   - Generate SQL query using LLM
5. **SQL Execution**: Run query against Supabase database
6. **Result Fusion**:
   - Integrate SQL result into final context
7. **Standard Fallback**: Proceed with standard RAG if no spreadsheet chunks