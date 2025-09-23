"""
Enhanced Metadata Provider for R2R
Generates rich metadata to support precise citations and deep linking.
"""

import os
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

from core.base import IngestionProvider


class EnhancedMetadataProvider(IngestionProvider):
    """
    Enhanced metadata generation for better citations and source tracking.
    
    Generates:
    - Document fingerprints for deduplication
    - Rich file metadata (author, creation date, etc.)
    - Section and page tracking
    - Citation-ready identifiers
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.extract_file_metadata = config.get("extract_file_metadata", True)
        self.generate_fingerprints = config.get("generate_fingerprints", True)
        self.track_sections = config.get("track_sections", True)
    
    async def enhance_document_metadata(
        self, 
        document_data: Dict[str, Any],
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enhance document with rich metadata for citations.
        """
        enhanced_metadata = document_data.get("metadata", {})
        
        # Basic file information
        if file_path and os.path.exists(file_path):
            enhanced_metadata.update(await self._extract_file_metadata(file_path))
        
        # Document fingerprint for deduplication
        if self.generate_fingerprints:
            enhanced_metadata["document_fingerprint"] = self._generate_document_fingerprint(
                document_data.get("content", "")
            )
        
        # Processing metadata
        enhanced_metadata.update({
            "processed_at": datetime.utcnow().isoformat(),
            "processor_version": "enhanced_r2r_v1.0",
            "citation_ready": True
        })
        
        # Content analysis
        content = document_data.get("content", "")
        enhanced_metadata.update(await self._analyze_content_structure(content))
        
        document_data["metadata"] = enhanced_metadata
        return document_data
    
    async def _extract_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract comprehensive file metadata.
        """
        file_path = Path(file_path)
        stat = file_path.stat()
        
        metadata = {
            "filename": file_path.name,
            "file_extension": file_path.suffix.lower(),
            "file_size": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "file_path": str(file_path.absolute())
        }
        
        # Try to extract additional metadata based on file type
        if file_path.suffix.lower() == '.pdf':
            metadata.update(await self._extract_pdf_metadata(file_path))
        elif file_path.suffix.lower() in ['.docx', '.doc']:
            metadata.update(await self._extract_docx_metadata(file_path))
        elif file_path.suffix.lower() in ['.xlsx', '.xls', '.csv']:
            metadata.update(await self._extract_spreadsheet_metadata(file_path))
        
        return metadata
    
    async def _extract_pdf_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract PDF-specific metadata.
        """
        try:
            import PyPDF2
            
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                metadata = {
                    "page_count": len(pdf_reader.pages),
                    "source_type": "pdf"
                }
                
                # Extract PDF metadata if available
                if pdf_reader.metadata:
                    pdf_meta = pdf_reader.metadata
                    if pdf_meta.get('/Title'):
                        metadata["title"] = str(pdf_meta['/Title'])
                    if pdf_meta.get('/Author'):
                        metadata["author"] = str(pdf_meta['/Author'])
                    if pdf_meta.get('/Subject'):
                        metadata["subject"] = str(pdf_meta['/Subject'])
                    if pdf_meta.get('/Creator'):
                        metadata["creator"] = str(pdf_meta['/Creator'])
                    if pdf_meta.get('/CreationDate'):
                        metadata["pdf_creation_date"] = str(pdf_meta['/CreationDate'])
                
                return metadata
                
        except ImportError:
            return {"source_type": "pdf", "metadata_extraction": "PyPDF2 not available"}
        except Exception as e:
            return {"source_type": "pdf", "metadata_extraction_error": str(e)}
    
    async def _extract_docx_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract Word document metadata.
        """
        try:
            from docx import Document
            
            doc = Document(file_path)
            
            metadata = {
                "source_type": "docx",
                "paragraph_count": len(doc.paragraphs)
            }
            
            # Extract document properties
            props = doc.core_properties
            if props.title:
                metadata["title"] = props.title
            if props.author:
                metadata["author"] = props.author
            if props.subject:
                metadata["subject"] = props.subject
            if props.created:
                metadata["document_created"] = props.created.isoformat()
            if props.modified:
                metadata["document_modified"] = props.modified.isoformat()
            
            return metadata
            
        except ImportError:
            return {"source_type": "docx", "metadata_extraction": "python-docx not available"}
        except Exception as e:
            return {"source_type": "docx", "metadata_extraction_error": str(e)}
    
    async def _extract_spreadsheet_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract spreadsheet metadata.
        """
        try:
            import pandas as pd
            
            if file_path.suffix.lower() in ['.xlsx', '.xls']:
                # Get sheet names
                excel_file = pd.ExcelFile(file_path)
                sheet_names = excel_file.sheet_names
                
                # Read first sheet for basic info
                df = pd.read_excel(file_path, sheet_name=0)
                
                metadata = {
                    "source_type": "spreadsheet",
                    "sheet_count": len(sheet_names),
                    "sheet_names": sheet_names,
                    "row_count": len(df),
                    "column_count": len(df.columns),
                    "columns": list(df.columns)
                }
            else:  # CSV
                df = pd.read_csv(file_path)
                metadata = {
                    "source_type": "csv",
                    "row_count": len(df),
                    "column_count": len(df.columns),
                    "columns": list(df.columns)
                }
            
            return metadata
            
        except ImportError:
            return {"source_type": "spreadsheet", "metadata_extraction": "pandas not available"}
        except Exception as e:
            return {"source_type": "spreadsheet", "metadata_extraction_error": str(e)}
    
    def _generate_document_fingerprint(self, content: str) -> str:
        """
        Generate a unique fingerprint for the document content.
        """
        # Normalize content for fingerprinting
        normalized = content.lower().strip()
        normalized = " ".join(normalized.split())  # Normalize whitespace
        
        # Generate hash
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    async def _analyze_content_structure(self, content: str) -> Dict[str, Any]:
        """
        Analyze content structure for better chunking and citations.
        """
        lines = content.split('\n')
        
        # Basic structure analysis
        structure_metadata = {
            "line_count": len(lines),
            "word_count": len(content.split()),
            "character_count": len(content),
            "paragraph_count": len([line for line in lines if line.strip()])
        }
        
        # Detect potential sections/headers
        headers = []
        for i, line in enumerate(lines):
            line = line.strip()
            # Simple heuristics for headers
            if (line and 
                (line.isupper() or 
                 line.startswith('#') or 
                 (len(line) < 100 and not line.endswith('.')))):
                headers.append({
                    "line_number": i + 1,
                    "text": line,
                    "type": "potential_header"
                })
        
        if headers:
            structure_metadata["detected_headers"] = headers[:10]  # Limit for performance
            structure_metadata["section_count"] = len(headers)
        
        return structure_metadata
    
    async def enhance_chunk_metadata(
        self, 
        chunk_data: Dict[str, Any], 
        chunk_index: int,
        document_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Enhance individual chunk metadata for precise citations.
        """
        chunk_metadata = chunk_data.get("metadata", {})
        
        # Inherit document metadata
        chunk_metadata.update({
            "document_id": document_metadata.get("document_id"),
            "filename": document_metadata.get("filename"),
            "source_type": document_metadata.get("source_type"),
            "author": document_metadata.get("author"),
            "created_at": document_metadata.get("created_at"),
            "chunk_index": chunk_index,
            "chunk_id": f"{document_metadata.get('document_id', 'unknown')}_{chunk_index}"
        })
        
        # Estimate page number (rough heuristic)
        if document_metadata.get("page_count"):
            estimated_page = min(
                int((chunk_index / 10) + 1),  # Rough estimate: ~10 chunks per page
                document_metadata["page_count"]
            )
            chunk_metadata["estimated_page"] = estimated_page
        
        # Try to detect section from content
        content = chunk_data.get("content", "")
        if self.track_sections:
            section = await self._detect_chunk_section(content, document_metadata)
            if section:
                chunk_metadata["section"] = section
        
        chunk_data["metadata"] = chunk_metadata
        return chunk_data
    
    async def _detect_chunk_section(
        self, content: str, document_metadata: Dict[str, Any]
    ) -> Optional[str]:
        """
        Try to detect which section this chunk belongs to.
        """
        # Look for headers in the chunk content
        lines = content.split('\n')
        for line in lines[:3]:  # Check first few lines
            line = line.strip()
            if (line and 
                (line.isupper() or 
                 line.startswith('#') or 
                 (len(line) < 100 and not line.endswith('.')))):
                return line
        
        # Use detected headers from document metadata
        headers = document_metadata.get("detected_headers", [])
        if headers:
            # Simple heuristic: return the first header (could be improved)
            return headers[0]["text"]
        
        return None
