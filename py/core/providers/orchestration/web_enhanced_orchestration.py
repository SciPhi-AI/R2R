"""
Web-Enhanced Orchestration Provider for R2R
Integrates web search as both automatic fallback and user-controlled option.
"""

import json
from typing import Any, Dict, List, Optional
from core.base import OrchestrationProvider, VectorSearchResult
from shared.abstractions import GenerationConfig


class WebEnhancedOrchestrationProvider(OrchestrationProvider):
    """
    Enhanced orchestration with intelligent web search integration.
    
    Features:
    - Automatic fallback when RAG results are insufficient
    - User-controlled web search toggle
    - Confidence-based decision making
    - Source attribution for web results
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # Web search configuration
        self.enable_web_fallback = config.get("enable_web_fallback", True)
        self.web_confidence_threshold = config.get("web_confidence_threshold", 0.6)
        self.min_rag_results = config.get("min_rag_results", 2)
        self.web_search_provider = config.get("web_search_provider", "serper")  # serper, tavily
        self.max_web_results = config.get("max_web_results", 5)
        
        # Quality thresholds
        self.low_confidence_threshold = config.get("low_confidence_threshold", 0.5)
        self.insufficient_content_threshold = config.get("insufficient_content_threshold", 200)
    
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
        Run RAG pipeline with intelligent web search integration.
        """
        # Check for user-controlled web search flag
        use_web_search = kwargs.get("use_web_search", False)
        force_web_search = kwargs.get("force_web_search", False)
        
        # Step 1: Perform standard RAG pipeline
        rag_results = await self._perform_rag_search(
            message, vector_search_settings, kg_search_settings
        )
        
        # Step 2: Assess RAG result quality
        rag_assessment = await self._assess_rag_quality(rag_results, message)
        
        # Step 3: Decide if web search is needed
        should_use_web = await self._should_use_web_search(
            rag_assessment, use_web_search, force_web_search
        )
        
        web_results = []
        if should_use_web:
            # Step 4: Perform web search
            web_results = await self._perform_web_search(message, rag_assessment)
        
        # Step 5: Fuse RAG and web results
        combined_results = await self._fuse_rag_and_web_results(
            rag_results, web_results, rag_assessment
        )
        
        # Step 6: Generate comprehensive response
        response = await self._generate_enhanced_response(
            message, combined_results, rag_generation_config
        )
        
        return {
            "response": response["content"],
            "sources": combined_results,
            "rag_quality": rag_assessment,
            "web_search_used": bool(web_results),
            "web_search_reason": response.get("web_search_reason"),
            "confidence_score": response.get("confidence_score", 0.0)
        }
    
    async def _assess_rag_quality(
        self, rag_results: List[VectorSearchResult], query: str
    ) -> Dict[str, Any]:
        """
        Assess the quality and completeness of RAG results.
        """
        if not rag_results:
            return {
                "quality": "insufficient",
                "reason": "no_results",
                "confidence": 0.0,
                "content_length": 0,
                "result_count": 0
            }
        
        # Calculate metrics
        avg_score = sum(r.score for r in rag_results) / len(rag_results)
        total_content_length = sum(len(r.content) for r in rag_results)
        result_count = len(rag_results)
        
        # Assess quality
        if result_count < self.min_rag_results:
            quality = "insufficient"
            reason = "too_few_results"
        elif avg_score < self.low_confidence_threshold:
            quality = "low_confidence"
            reason = "low_relevance_scores"
        elif total_content_length < self.insufficient_content_threshold:
            quality = "insufficient_content"
            reason = "limited_content"
        elif avg_score > self.web_confidence_threshold:
            quality = "good"
            reason = "sufficient_rag_results"
        else:
            quality = "moderate"
            reason = "moderate_confidence"
        
        return {
            "quality": quality,
            "reason": reason,
            "confidence": avg_score,
            "content_length": total_content_length,
            "result_count": result_count,
            "avg_score": avg_score
        }
    
    async def _should_use_web_search(
        self, 
        rag_assessment: Dict[str, Any], 
        user_requested: bool, 
        force_web: bool
    ) -> bool:
        """
        Determine if web search should be used.
        """
        # Force web search if explicitly requested
        if force_web:
            return True
        
        # User explicitly requested web search
        if user_requested:
            return True
        
        # Automatic fallback logic
        if not self.enable_web_fallback:
            return False
        
        quality = rag_assessment.get("quality", "good")
        
        # Use web search for insufficient or low-confidence results
        return quality in ["insufficient", "low_confidence", "insufficient_content"]
    
    async def _perform_web_search(
        self, query: str, rag_assessment: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Perform web search using configured provider.
        """
        try:
            if self.web_search_provider == "serper":
                return await self._serper_search(query)
            elif self.web_search_provider == "tavily":
                return await self._tavily_search(query)
            else:
                return await self._fallback_web_search(query)
        except Exception as e:
            print(f"Web search error: {e}")
            return []
    
    async def _serper_search(self, query: str) -> List[Dict[str, Any]]:
        """
        Perform web search using Serper API.
        """
        import aiohttp
        import os
        
        api_key = os.getenv("SERPER_API_KEY")
        if not api_key:
            return []
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "q": query,
                    "num": self.max_web_results
                }
                headers = {
                    "X-API-KEY": api_key,
                    "Content-Type": "application/json"
                }
                
                async with session.post(
                    "https://google.serper.dev/search",
                    json=payload,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return await self._format_serper_results(data)
                    else:
                        return []
        except Exception as e:
            print(f"Serper search error: {e}")
            return []
    
    async def _tavily_search(self, query: str) -> List[Dict[str, Any]]:
        """
        Perform web search using Tavily API.
        """
        import aiohttp
        import os
        
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return []
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "basic",
                    "include_answer": True,
                    "include_raw_content": False,
                    "max_results": self.max_web_results
                }
                
                async with session.post(
                    "https://api.tavily.com/search",
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return await self._format_tavily_results(data)
                    else:
                        return []
        except Exception as e:
            print(f"Tavily search error: {e}")
            return []
    
    async def _format_serper_results(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format Serper API results."""
        results = []
        
        # Add organic results
        for item in data.get("organic", []):
            results.append({
                "type": "web_search",
                "title": item.get("title", ""),
                "content": item.get("snippet", ""),
                "url": item.get("link", ""),
                "source": "serper",
                "score": 0.8  # Default web search score
            })
        
        # Add answer box if available
        if "answerBox" in data:
            answer = data["answerBox"]
            results.insert(0, {
                "type": "web_answer",
                "title": "Direct Answer",
                "content": answer.get("answer", "") or answer.get("snippet", ""),
                "url": answer.get("link", ""),
                "source": "serper_answer",
                "score": 0.9  # Higher score for direct answers
            })
        
        return results
    
    async def _format_tavily_results(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format Tavily API results."""
        results = []
        
        # Add search results
        for item in data.get("results", []):
            results.append({
                "type": "web_search",
                "title": item.get("title", ""),
                "content": item.get("content", ""),
                "url": item.get("url", ""),
                "source": "tavily",
                "score": item.get("score", 0.8)
            })
        
        # Add direct answer if available
        if "answer" in data and data["answer"]:
            results.insert(0, {
                "type": "web_answer",
                "title": "Direct Answer",
                "content": data["answer"],
                "url": "",
                "source": "tavily_answer",
                "score": 0.9
            })
        
        return results
    
    async def _fallback_web_search(self, query: str) -> List[Dict[str, Any]]:
        """
        Fallback web search when no API keys are available.
        """
        return [{
            "type": "web_fallback",
            "title": "Web Search Unavailable",
            "content": f"Web search for '{query}' is not available. Please configure SERPER_API_KEY or TAVILY_API_KEY.",
            "url": "",
            "source": "fallback",
            "score": 0.1
        }]
    
    async def _fuse_rag_and_web_results(
        self,
        rag_results: List[VectorSearchResult],
        web_results: List[Dict[str, Any]],
        rag_assessment: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Intelligently fuse RAG and web search results.
        """
        combined_results = []
        
        # Add RAG results with source attribution
        for result in rag_results:
            combined_results.append({
                "type": "rag",
                "content": result.content,
                "score": result.score,
                "metadata": result.metadata,
                "source_type": "internal_knowledge"
            })
        
        # Add web results with clear attribution
        for result in web_results:
            combined_results.append({
                "type": "web",
                "content": result["content"],
                "score": result["score"],
                "title": result["title"],
                "url": result["url"],
                "source_type": "web_search",
                "web_source": result["source"]
            })
        
        # Sort by relevance score (descending)
        combined_results.sort(key=lambda x: x["score"], reverse=True)
        
        return combined_results
    
    async def _generate_enhanced_response(
        self,
        message: str,
        combined_results: List[Dict[str, Any]],
        generation_config: GenerationConfig
    ) -> Dict[str, Any]:
        """
        Generate response using both RAG and web results.
        """
        if not hasattr(self, 'llm_provider') or not self.llm_provider:
            return {
                "content": "Enhanced response generation not available.",
                "confidence_score": 0.0
            }
        
        # Separate sources
        rag_sources = [r for r in combined_results if r["type"] == "rag"]
        web_sources = [r for r in combined_results if r["type"] == "web"]
        
        # Build context
        context_parts = []
        
        if rag_sources:
            context_parts.append("Internal Knowledge Base:")
            for i, source in enumerate(rag_sources[:3]):
                context_parts.append(f"[{i+1}] {source['content'][:300]}...")
        
        if web_sources:
            context_parts.append("\nWeb Search Results:")
            for i, source in enumerate(web_sources[:3]):
                context_parts.append(f"[W{i+1}] {source['content'][:300]}...")
                context_parts.append(f"    Source: {source.get('title', 'Web Result')} ({source.get('url', 'N/A')})")
        
        context = "\n".join(context_parts)
        
        # Determine web search reason
        web_search_reason = None
        if web_sources:
            if not rag_sources:
                web_search_reason = "No relevant internal knowledge found"
            elif len(rag_sources) < 2:
                web_search_reason = "Limited internal knowledge, supplemented with web search"
            else:
                web_search_reason = "User requested web search or automatic enhancement"
        
        prompt = f"""
        Answer the following question using the available information sources.
        
        Question: {message}
        
        Available Sources:
        {context}
        
        Instructions:
        - Provide a comprehensive answer using all relevant sources
        - Clearly indicate when information comes from internal knowledge vs. web search
        - Use [1], [2] for internal sources and [W1], [W2] for web sources
        - If web sources contradict internal knowledge, note the discrepancy
        - Be transparent about source limitations
        
        Answer:
        """
        
        try:
            response = await self.llm_provider.aget_completion(
                messages=[{"role": "user", "content": prompt}],
                generation_config=generation_config
            )
            
            # Calculate confidence based on source mix
            confidence = 0.8 if rag_sources else 0.6
            if web_sources and rag_sources:
                confidence = 0.9  # Higher confidence with multiple source types
            
            return {
                "content": response.choices[0].message.content,
                "confidence_score": confidence,
                "web_search_reason": web_search_reason
            }
        except Exception as e:
            return {
                "content": f"Error generating enhanced response: {e}",
                "confidence_score": 0.0
            }
