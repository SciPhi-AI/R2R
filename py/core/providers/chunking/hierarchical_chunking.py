"""
Hierarchical Chunking Provider for R2R
Implements Parent/Child chunking strategy for better context retention.
"""

from typing import Any, Dict, List, Optional
from core.base import ChunkingProvider, DocumentChunk
from shared.abstractions import GenerationConfig


class HierarchicalChunkingProvider(ChunkingProvider):
    """
    Hierarchical chunking that creates both parent and child chunks.
    
    - Child chunks: Standard recursive character splitting
    - Parent chunks: Grouped child chunks with LLM-generated summaries
    - Linking: Parent-child relationships for multi-level context
    """
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *args,
        **kwargs
    ):
        super().__init__(config, *args, **kwargs)
        self.child_chunk_size = config.get("child_chunk_size", 512)
        self.child_overlap = config.get("child_overlap", 50)
        self.children_per_parent = config.get("children_per_parent", 4)
        self.generate_summaries = config.get("generate_summaries", True)
    
    async def chunk(
        self,
        parsed_document: Dict[str, Any],
        generation_config: Optional[GenerationConfig] = None,
    ) -> List[DocumentChunk]:
        """
        Create hierarchical chunks with parent-child relationships.
        """
        text = parsed_document.get("content", "")
        document_id = parsed_document.get("document_id")
        
        # Step 1: Create child chunks using recursive character splitting
        child_chunks = await self._create_child_chunks(text, document_id)
        
        # Step 2: Group child chunks and create parent chunks
        parent_chunks = await self._create_parent_chunks(
            child_chunks, document_id, generation_config
        )
        
        # Step 3: Set parent-child relationships
        all_chunks = []
        
        for i, parent_chunk in enumerate(parent_chunks):
            # Add parent chunk
            all_chunks.append(parent_chunk)
            
            # Add associated child chunks with parent reference
            start_idx = i * self.children_per_parent
            end_idx = min(start_idx + self.children_per_parent, len(child_chunks))
            
            for child_chunk in child_chunks[start_idx:end_idx]:
                child_chunk.metadata["parent_chunk_id"] = parent_chunk.chunk_id
                child_chunk.metadata["chunk_type"] = "child"
                all_chunks.append(child_chunk)
        
        return all_chunks
    
    async def _create_child_chunks(
        self, text: str, document_id: str
    ) -> List[DocumentChunk]:
        """Create standard child chunks using recursive character splitting."""
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.child_chunk_size,
            chunk_overlap=self.child_overlap,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        chunks = splitter.split_text(text)
        child_chunks = []
        
        for i, chunk_text in enumerate(chunks):
            chunk = DocumentChunk(
                chunk_id=f"{document_id}_child_{i}",
                document_id=document_id,
                content=chunk_text,
                metadata={
                    "chunk_index": i,
                    "chunk_type": "child",
                    "chunk_size": len(chunk_text)
                }
            )
            child_chunks.append(chunk)
        
        return child_chunks
    
    async def _create_parent_chunks(
        self, 
        child_chunks: List[DocumentChunk], 
        document_id: str,
        generation_config: Optional[GenerationConfig] = None
    ) -> List[DocumentChunk]:
        """Create parent chunks by grouping child chunks and generating summaries."""
        parent_chunks = []
        
        for i in range(0, len(child_chunks), self.children_per_parent):
            group = child_chunks[i:i + self.children_per_parent]
            
            # Combine child chunk content
            combined_content = "\n\n".join([chunk.content for chunk in group])
            
            # Generate summary if LLM is available and enabled
            if self.generate_summaries and hasattr(self, 'llm_provider'):
                try:
                    summary = await self._generate_section_summary(
                        combined_content, generation_config
                    )
                except Exception:
                    # Fallback to truncated content if summary generation fails
                    summary = combined_content[:500] + "..." if len(combined_content) > 500 else combined_content
            else:
                # Use truncated content as summary
                summary = combined_content[:500] + "..." if len(combined_content) > 500 else combined_content
            
            parent_chunk = DocumentChunk(
                chunk_id=f"{document_id}_parent_{i // self.children_per_parent}",
                document_id=document_id,
                content=summary,
                metadata={
                    "chunk_type": "parent",
                    "child_count": len(group),
                    "child_chunk_ids": [chunk.chunk_id for chunk in group],
                    "section_index": i // self.children_per_parent
                }
            )
            parent_chunks.append(parent_chunk)
        
        return parent_chunks
    
    async def _generate_section_summary(
        self, content: str, generation_config: Optional[GenerationConfig] = None
    ) -> str:
        """Generate a summary of the section content using LLM."""
        if not hasattr(self, 'llm_provider') or not self.llm_provider:
            return content[:500] + "..." if len(content) > 500 else content
        
        prompt = f"""
        Please provide a concise summary of the following text section. 
        Focus on the main topics, key information, and important details.
        Keep the summary informative but concise (2-3 sentences).
        
        Text:
        {content}
        
        Summary:
        """
        
        try:
            response = await self.llm_provider.aget_completion(
                messages=[{"role": "user", "content": prompt}],
                generation_config=generation_config or GenerationConfig(max_tokens=150)
            )
            return response.choices[0].message.content.strip()
        except Exception:
            # Fallback to truncated content
            return content[:500] + "..." if len(content) > 500 else content
