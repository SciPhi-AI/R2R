"""
Frontend Integration Example for Web Search Control
Shows how to integrate web search controls in your frontend application.
"""

from r2r import R2RClient
from typing import Dict, Any, Optional

class EnhancedR2RClient:
    """
    Enhanced R2R client with web search controls for frontend integration.
    """
    
    def __init__(self, base_url: str = "http://localhost:7272"):
        self.client = R2RClient(base_url)
    
    async def enhanced_search(
        self,
        query: str,
        use_web_search: bool = False,
        force_web_search: bool = False,
        web_search_provider: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Enhanced search with web search controls.
        
        Args:
            query: The search query
            use_web_search: Enable web search if RAG results are insufficient
            force_web_search: Always use web search regardless of RAG quality
            web_search_provider: Override default provider ("serper" or "tavily")
        """
        
        # Prepare search parameters
        search_params = {
            "use_web_search": use_web_search,
            "force_web_search": force_web_search,
            **kwargs
        }
        
        if web_search_provider:
            search_params["web_search_provider"] = web_search_provider
        
        # Execute enhanced RAG search
        response = await self.client.retrieval.search(
            query=query,
            **search_params
        )
        
        return response

# Frontend Integration Examples

class WebSearchControls:
    """
    Example web search control implementations for different frontend frameworks.
    """
    
    @staticmethod
    def react_component_example():
        """
        React component example with web search toggle.
        """
        return """
        // React Component Example
        import React, { useState } from 'react';
        
        function SearchInterface() {
            const [query, setQuery] = useState('');
            const [useWebSearch, setUseWebSearch] = useState(false);
            const [forceWebSearch, setForceWebSearch] = useState(false);
            const [provider, setProvider] = useState('serper');
            
            const handleSearch = async () => {
                const response = await fetch('/api/search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query,
                        use_web_search: useWebSearch,
                        force_web_search: forceWebSearch,
                        web_search_provider: provider
                    })
                });
                
                const result = await response.json();
                // Handle response with web search attribution
                displayResults(result);
            };
            
            return (
                <div className="search-interface">
                    <input 
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Ask a question..."
                    />
                    
                    <div className="search-controls">
                        <label>
                            <input 
                                type="checkbox"
                                checked={useWebSearch}
                                onChange={(e) => setUseWebSearch(e.target.checked)}
                            />
                            Enable web search fallback
                        </label>
                        
                        <label>
                            <input 
                                type="checkbox"
                                checked={forceWebSearch}
                                onChange={(e) => setForceWebSearch(e.target.checked)}
                            />
                            Always use web search
                        </label>
                        
                        <select 
                            value={provider}
                            onChange={(e) => setProvider(e.target.value)}
                        >
                            <option value="serper">Google (Serper)</option>
                            <option value="tavily">Tavily</option>
                        </select>
                    </div>
                    
                    <button onClick={handleSearch}>Search</button>
                </div>
            );
        }
        """
    
    @staticmethod
    def nextjs_api_route_example():
        """
        Next.js API route example.
        """
        return """
        // pages/api/search.js or app/api/search/route.js
        import { EnhancedR2RClient } from '../../../lib/r2r-client';
        
        export default async function handler(req, res) {
            if (req.method !== 'POST') {
                return res.status(405).json({ error: 'Method not allowed' });
            }
            
            const { 
                query, 
                use_web_search = false, 
                force_web_search = false,
                web_search_provider = 'serper'
            } = req.body;
            
            try {
                const client = new EnhancedR2RClient();
                
                const result = await client.enhanced_search(
                    query,
                    use_web_search,
                    force_web_search,
                    web_search_provider
                );
                
                // Add metadata about search strategy
                const response = {
                    ...result,
                    search_metadata: {
                        web_search_used: result.web_search_used,
                        web_search_reason: result.web_search_reason,
                        source_breakdown: {
                            internal: result.sources?.filter(s => s.source_type === 'internal_knowledge').length || 0,
                            web: result.sources?.filter(s => s.source_type === 'web_search').length || 0
                        }
                    }
                };
                
                res.status(200).json(response);
            } catch (error) {
                res.status(500).json({ error: error.message });
            }
        }
        """
    
    @staticmethod
    def vue_component_example():
        """
        Vue.js component example.
        """
        return """
        <!-- Vue Component Example -->
        <template>
            <div class="search-interface">
                <input 
                    v-model="query"
                    placeholder="Ask a question..."
                    @keyup.enter="handleSearch"
                />
                
                <div class="search-controls">
                    <label>
                        <input 
                            type="checkbox"
                            v-model="searchSettings.useWebSearch"
                        />
                        Smart web search fallback
                    </label>
                    
                    <label>
                        <input 
                            type="checkbox"
                            v-model="searchSettings.forceWebSearch"
                        />
                        Always include web results
                    </label>
                    
                    <select v-model="searchSettings.provider">
                        <option value="serper">Google Search</option>
                        <option value="tavily">Tavily Search</option>
                    </select>
                </div>
                
                <button @click="handleSearch" :disabled="loading">
                    {{ loading ? 'Searching...' : 'Search' }}
                </button>
                
                <div v-if="result" class="results">
                    <div class="response">{{ result.response }}</div>
                    
                    <div class="source-attribution">
                        <span v-if="result.search_metadata.source_breakdown.internal > 0">
                            📚 {{ result.search_metadata.source_breakdown.internal }} internal sources
                        </span>
                        <span v-if="result.search_metadata.source_breakdown.web > 0">
                            🌐 {{ result.search_metadata.source_breakdown.web }} web sources
                        </span>
                    </div>
                </div>
            </div>
        </template>
        
        <script>
        export default {
            data() {
                return {
                    query: '',
                    loading: false,
                    result: null,
                    searchSettings: {
                        useWebSearch: true,
                        forceWebSearch: false,
                        provider: 'serper'
                    }
                };
            },
            methods: {
                async handleSearch() {
                    this.loading = true;
                    try {
                        const response = await this.$http.post('/api/search', {
                            query: this.query,
                            ...this.searchSettings
                        });
                        this.result = response.data;
                    } catch (error) {
                        console.error('Search error:', error);
                    } finally {
                        this.loading = false;
                    }
                }
            }
        };
        </script>
        """

# Usage Examples

def smart_fallback_example():
    """
    Example: Automatic web search fallback
    """
    client = EnhancedR2RClient()
    
    # Smart fallback - uses web search only if RAG results are insufficient
    result = client.enhanced_search(
        query="What happened in the news today?",
        use_web_search=True  # Enable smart fallback
    )
    
    return result

def user_controlled_example():
    """
    Example: User-controlled web search
    """
    client = EnhancedR2RClient()
    
    # User explicitly wants web search
    result = client.enhanced_search(
        query="Latest developments in AI",
        force_web_search=True,  # Always use web search
        web_search_provider="tavily"
    )
    
    return result

def hybrid_approach_example():
    """
    Example: Hybrid approach with intelligent routing
    """
    client = EnhancedR2RClient()
    
    # Query about internal company data - no web search needed
    internal_result = client.enhanced_search(
        query="What was our Q3 revenue?",
        use_web_search=False  # Internal data only
    )
    
    # Query about external market data - enable web search
    market_result = client.enhanced_search(
        query="What are the current market trends in AI?",
        use_web_search=True,  # Smart fallback enabled
        force_web_search=False  # But try RAG first
    )
    
    return internal_result, market_result
