"""
Citation-Enhanced Orchestration Provider for R2R
Provides precise, deep-linked citations for all generated information.
"""

import json
import hashlib
from typing import Any, Dict, List, Optional, AsyncGenerator
from urllib.parse import quote

from core.base import OrchestrationProvider, VectorSearchResult
from shared.abstractions import GenerationConfig


class CitationEnhancedOrchestrationProvider(OrchestrationProvider):
    """
    Enhanced orchestration that provides precise citations with deep links.
    
    Features:
    - Chunk-level citations with page/section references
    - Deep-link generation for precise source location
    - Citation confidence scoring
    - Source deduplication and ranking
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.citation_style = config.get("citation_style", "detailed")  # "detailed", "compact", "academic"
        self.max_citations = config.get("max_citations", 5)
        self.min_citation_score = config.get("min_citation_score", 0.7)
        self.generate_deep_links = config.get("generate_deep_links", True)
    
    async def arun_rag_pipeline(
        self,
        message: str,
        vector_search_settings: Dict[str, Any],
        kg_search_settings: Dict[str, Any],
        rag_generation_config: GenerationConfig,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run RAG pipeline with enhanced citation generation.
        """
        # Step 1: Perform vector search
        search_results = await self._perform_vector_search(
            message, vector_search_settings
        )
        
        # Step 2: Enhance results with citation metadata
        enhanced_results = await self._enhance_with_citations(search_results)
        
        # Step 3: Generate response with citations
        response = await self._generate_cited_response(
            message, enhanced_results, rag_generation_config
        )
        
        # Step 4: Format final output with citation details
        return await self._format_response_with_citations(response, enhanced_results)
    
    async def _enhance_with_citations(
        self, search_results: List[VectorSearchResult], web_results: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Enhance search results with detailed citation metadata.
        Supports both RAG results and web search results.
        """
        enhanced_results = []
        citation_index = 1
        
        # Process RAG results
        for result in search_results:
            # Extract metadata
            metadata = result.metadata or {}
            
            # Generate citation ID
            citation_id = self._generate_citation_id(result)
            
            # Create deep link
            deep_link = await self._generate_deep_link(result) if self.generate_deep_links else None
            
            # Calculate citation confidence
            confidence = self._calculate_citation_confidence(result)
            
            # Skip low-confidence citations
            if confidence < self.min_citation_score:
                continue
            
            enhanced_result = {
                "content": result.content,
                "score": result.score,
                "citation_id": citation_id,
                "citation_index": citation_index,
                "confidence": confidence,
                "source_type": "internal_knowledge",
                "source_metadata": {
                    "document_id": metadata.get("document_id"),
                    "filename": metadata.get("filename", "Unknown Document"),
                    "page_number": metadata.get("page_number"),
                    "section": metadata.get("section"),
                    "chunk_index": metadata.get("chunk_index"),
                    "source_type": metadata.get("source_type", "document"),
                    "created_at": metadata.get("created_at"),
                    "file_size": metadata.get("file_size"),
                    "author": metadata.get("author")
                },
                "deep_link": deep_link,
                "citation_text": await self._format_citation_text(result, citation_index, "internal")
            }
            
            enhanced_results.append(enhanced_result)
            citation_index += 1
            
            # Limit number of RAG citations
            if len(enhanced_results) >= self.max_citations:
                break
        
        # Process web search results
        if web_results:
            remaining_slots = self.max_citations - len(enhanced_results)
            for i, web_result in enumerate(web_results[:remaining_slots]):
                
                # Generate web citation
                web_citation = {
                    "content": web_result.get("content", ""),
                    "score": web_result.get("score", 0.8),
                    "citation_id": f"web_{i}",
                    "citation_index": citation_index,
                    "confidence": web_result.get("score", 0.8),
                    "source_type": "web_search",
                    "source_metadata": {
                        "title": web_result.get("title", "Web Result"),
                        "url": web_result.get("url", ""),
                        "web_source": web_result.get("source", "web"),
                        "search_provider": web_result.get("source", "unknown")
                    },
                    "deep_link": web_result.get("url", ""),
                    "citation_text": await self._format_web_citation_text(web_result, citation_index)
                }
                
                enhanced_results.append(web_citation)
                citation_index += 1
        
        return enhanced_results
    
    def _generate_citation_id(self, result: VectorSearchResult) -> str:
        """
        Generate a unique citation ID for the result.
        """
        content_hash = hashlib.md5(result.content.encode()).hexdigest()[:8]
        doc_id = result.metadata.get("document_id", "unknown")[:8]
        return f"cite_{doc_id}_{content_hash}"
    
    async def _generate_deep_link(self, result: VectorSearchResult) -> Optional[str]:
        """
        Generate a deep link to the specific location in the source document.
        """
        metadata = result.metadata or {}
        
        # Base URL for document viewer (configurable)
        base_url = "/documents/view"
        
        # Document identifier
        doc_id = metadata.get("document_id")
        if not doc_id:
            return None
        
        # Build query parameters for precise location
        params = []
        
        if metadata.get("page_number"):
            params.append(f"page={metadata['page_number']}")
        
        if metadata.get("chunk_index"):
            params.append(f"chunk={metadata['chunk_index']}")
        
        if metadata.get("section"):
            params.append(f"section={quote(str(metadata['section']))}")
        
        # Highlight the specific content
        if result.content:
            # Use first few words as highlight anchor
            highlight_text = " ".join(result.content.split()[:5])
            params.append(f"highlight={quote(highlight_text)}")
        
        query_string = "&".join(params)
        return f"{base_url}/{doc_id}?{query_string}" if query_string else f"{base_url}/{doc_id}"
    
    def _calculate_citation_confidence(self, result: VectorSearchResult) -> float:
        """
        Calculate confidence score for citation quality.
        """
        confidence = result.score  # Base on search relevance score
        
        metadata = result.metadata or {}
        
        # Boost confidence for complete metadata
        if metadata.get("page_number"):
            confidence += 0.1
        if metadata.get("section"):
            confidence += 0.1
        if metadata.get("author"):
            confidence += 0.05
        if metadata.get("created_at"):
            confidence += 0.05
        
        # Boost confidence for longer, more substantial content
        content_length = len(result.content.split())
        if content_length > 50:
            confidence += 0.1
        elif content_length < 10:
            confidence -= 0.2
        
        return min(confidence, 1.0)
    
    async def _format_citation_text(self, result: VectorSearchResult, index: int, source_type: str = "internal") -> str:
        """
        Format citation text based on citation style.
        """
        metadata = result.metadata or {}
        filename = metadata.get("filename", "Unknown Document")
        
        if self.citation_style == "academic":
            # Academic style: Author (Year). Title. Page X.
            author = metadata.get("author", "Unknown Author")
            year = metadata.get("created_at", "n.d.")[:4] if metadata.get("created_at") else "n.d."
            page = f", p. {metadata['page_number']}" if metadata.get("page_number") else ""
            return f"[{index}] {author} ({year}). {filename}{page}."
        
        elif self.citation_style == "compact":
            # Compact style: [1] Document.pdf, p.5
            page = f", p.{metadata['page_number']}" if metadata.get("page_number") else ""
            return f"[{index}] {filename}{page}"
        
        else:  # detailed
            # Detailed style with all available metadata
            parts = [f"[{index}] {filename}"]
            
            if metadata.get("author"):
                parts.append(f"by {metadata['author']}")
            
            if metadata.get("page_number"):
                parts.append(f"page {metadata['page_number']}")
            
            if metadata.get("section"):
                parts.append(f"section '{metadata['section']}'")
            
            if metadata.get("created_at"):
                parts.append(f"({metadata['created_at'][:10]})")
            
            return ", ".join(parts)
    
    async def _format_web_citation_text(self, web_result: Dict[str, Any], index: int) -> str:
        """
        Format web search result citation text.
        """
        title = web_result.get("title", "Web Result")
        url = web_result.get("url", "")
        source = web_result.get("source", "web")
        
        if self.citation_style == "academic":
            # Academic style for web sources
            return f"[W{index}] {title}. Retrieved from web search ({source}). {url}"
        
        elif self.citation_style == "compact":
            # Compact style for web sources
            domain = url.split("//")[-1].split("/")[0] if url else "web"
            return f"[W{index}] {title} ({domain})"
        
        else:  # detailed
            # Detailed style with clear web attribution
            parts = [f"[W{index}] {title}"]
            
            if url:
                domain = url.split("//")[-1].split("/")[0]
                parts.append(f"from {domain}")
            
            parts.append(f"via {source.title()} search")
            
            if url:
                parts.append(f"({url})")
            
            return ", ".join(parts)
    
    async def _generate_cited_response(
        self,
        message: str,
        enhanced_results: List[Dict[str, Any]],
        generation_config: GenerationConfig
    ) -> str:
        """
        Generate response with inline citations.
        """
        # Prepare context with citation markers
        context_parts = []
        for result in enhanced_results:
            if result['source_type'] == 'web_search':
                citation_marker = f"[W{result['citation_index']}]"
            else:
                citation_marker = f"[{result['citation_index']}]"
            context_parts.append(f"{result['content']} {citation_marker}")
        
        context = "\n\n".join(context_parts)
        
        # Enhanced prompt for citation-aware generation
        prompt = f"""
        Answer the following question based on the provided context. 
        
        IMPORTANT CITATION RULES:
        1. Include citation numbers [1], [2] for internal sources and [W1], [W2] for web sources
        2. Use multiple citations [1,W1] when combining internal and web information
        3. Clearly distinguish between internal knowledge and web search results
        4. Only make claims that are supported by the provided context
        5. If information is not in the context, clearly state this
        
        Question: {message}
        
        Context with Citations:
        {context}
        
        Answer with proper citations:
        """
        
        # Generate response using LLM
        if hasattr(self, 'llm_provider') and self.llm_provider:
            response = await self.llm_provider.aget_completion(
                messages=[{"role": "user", "content": prompt}],
                generation_config=generation_config
            )
            return response.choices[0].message.content
        else:
            return f"Based on the provided sources: {context[:500]}..."
    
    async def _format_response_with_citations(
        self, response: str, enhanced_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Format final response with complete citation information.
        """
        # Build citation list
        citations = []
        for result in enhanced_results:
            citation = {
                "id": result["citation_id"],
                "index": result["citation_index"],
                "text": result["citation_text"],
                "confidence": result["confidence"],
                "deep_link": result["deep_link"],
                "source_metadata": result["source_metadata"],
                "excerpt": result["content"][:200] + "..." if len(result["content"]) > 200 else result["content"]
            }
            citations.append(citation)
        
        # Calculate source breakdown
        internal_sources = [r for r in enhanced_results if r["source_type"] != "web_search"]
        web_sources = [r for r in enhanced_results if r["source_type"] == "web_search"]
        
        return {
            "response": response,
            "citations": citations,
            "citation_count": len(citations),
            "citation_style": self.citation_style,
            "metadata": {
                "total_sources": len(enhanced_results),
                "internal_sources": len(internal_sources),
                "web_sources": len(web_sources),
                "avg_confidence": sum(r["confidence"] for r in enhanced_results) / len(enhanced_results) if enhanced_results else 0,
                "has_deep_links": self.generate_deep_links,
                "source_breakdown": {
                    "internal_knowledge": len(internal_sources),
                    "web_search": len(web_sources)
                }
            }
        }
