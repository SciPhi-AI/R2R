# R2R Enhanced Template - MCP Integration

This template includes a **Model Context Protocol (MCP) server** that provides standardized access to all R2R enhanced features. Any application can interact with your R2R system through the MCP protocol.

## 🎯 Why MCP Integration?

### **Benefits:**
- ✅ **Standardized Interface** - Consistent API across all applications
- ✅ **Tool Discovery** - Applications can discover available R2R capabilities
- ✅ **Type Safety** - Structured schemas for all operations
- ✅ **Easy Integration** - Works with any MCP-compatible client
- ✅ **Future-Proof** - Standard protocol for AI tool integration

### **Use Cases:**
- **Frontend Applications** - React, Vue, Next.js apps
- **AI Assistants** - Claude Desktop, custom AI agents
- **Workflow Tools** - Zapier, n8n, custom automation
- **Analytics Dashboards** - Business intelligence applications
- **Mobile Apps** - iOS, Android applications

## 🚀 Quick Setup

### 1. Install MCP Server
```bash
./mcp/setup_mcp.sh
```

### 2. Start R2R System
```bash
./setup-new-project.sh
```

### 3. Test MCP Server
```bash
python mcp/r2r_mcp_server.py
```

## 🛠️ Available MCP Tools

### **Document Management**
#### `upload_document`
Upload and process documents with enhanced features.
```json
{
  "file_path": "/path/to/document.pdf",
  "metadata": {"author": "John Doe", "category": "research"},
  "chunking_strategy": "hierarchical"
}
```

#### `list_documents`
List all documents in the system with metadata.
```json
{
  "limit": 50,
  "offset": 0
}
```

### **Advanced Search**
#### `enhanced_search`
Perform sophisticated RAG queries with multiple strategies.
```json
{
  "query": "What are the benefits of renewable energy?",
  "search_strategy": "rag_fusion",
  "use_web_search": true,
  "include_citations": true,
  "limit": 10
}
```

**Search Strategies:**
- `vanilla` - Standard vector search
- `rag_fusion` - Multi-query decomposition with result fusion
- `hyde` - Hypothetical document embeddings

### **Knowledge Graph**
#### `graph_search`
Explore entities and relationships in your knowledge graph.
```json
{
  "query": "companies in renewable energy",
  "entity_types": ["Organization", "Technology"],
  "limit": 20
}
```

#### `get_entity_details`
Get detailed information about specific entities.
```json
{
  "entity_name": "Tesla",
  "include_relationships": true
}
```

### **Structured Data**
#### `query_spreadsheet`
Query spreadsheet data using natural language.
```json
{
  "query": "What was the revenue in Q3?",
  "filename": "financial_report.xlsx"
}
```

### **AI Agent**
#### `agent_chat`
Interact with R2R's multi-step reasoning agent.
```json
{
  "message": "Analyze the market trends for electric vehicles",
  "conversation_id": "conv_123"
}
```

### **Analytics & Monitoring**
#### `get_analytics`
Get usage analytics and system insights.
```json
{
  "metric_type": "usage",
  "days": 30
}
```

#### `system_health`
Check R2R system health and feature status.
```json
{}
```

## 🔌 Integration Examples

### **Claude Desktop Integration**
Add to your Claude Desktop MCP configuration:
```json
{
  "mcpServers": {
    "r2r-enhanced": {
      "command": "python",
      "args": ["/path/to/your/r2r-test/mcp/r2r_mcp_server.py"],
      "env": {
        "R2R_BASE_URL": "http://localhost:7272"
      }
    }
  }
}
```

### **Next.js Frontend Integration**
```javascript
// lib/mcp-client.js
import { MCPClient } from '@modelcontextprotocol/client';

class R2RMCPClient {
  constructor() {
    this.client = new MCPClient({
      serverCommand: 'python',
      serverArgs: ['/path/to/mcp/r2r_mcp_server.py']
    });
  }

  async searchDocuments(query, options = {}) {
    return await this.client.callTool('enhanced_search', {
      query,
      search_strategy: options.strategy || 'rag_fusion',
      use_web_search: options.useWebSearch || false,
      include_citations: options.includeCitations !== false
    });
  }

  async uploadDocument(filePath, metadata = {}) {
    return await this.client.callTool('upload_document', {
      file_path: filePath,
      metadata,
      chunking_strategy: 'hierarchical'
    });
  }

  async querySpreadsheet(query, filename) {
    return await this.client.callTool('query_spreadsheet', {
      query,
      filename
    });
  }
}

export default R2RMCPClient;
```

### **React Component Example**
```jsx
// components/R2RSearch.jsx
import { useState } from 'react';
import R2RMCPClient from '../lib/mcp-client';

export default function R2RSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  
  const client = new R2RMCPClient();

  const handleSearch = async () => {
    setLoading(true);
    try {
      const response = await client.searchDocuments(query, {
        strategy: 'rag_fusion',
        useWebSearch: true,
        includeCitations: true
      });
      setResults(response);
    } catch (error) {
      console.error('Search error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="r2r-search">
      <div className="search-input">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask anything..."
          onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
        />
        <button onClick={handleSearch} disabled={loading}>
          {loading ? 'Searching...' : 'Search'}
        </button>
      </div>
      
      {results && (
        <div className="search-results">
          <h3>Results</h3>
          <div dangerouslySetInnerHTML={{ __html: results.content }} />
        </div>
      )}
    </div>
  );
}
```

### **Python Client Example**
```python
# client_example.py
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    server_params = StdioServerParameters(
        command="python",
        args=["mcp/r2r_mcp_server.py"]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the session
            await session.initialize()
            
            # Search documents
            result = await session.call_tool(
                "enhanced_search",
                {
                    "query": "What are the latest AI developments?",
                    "search_strategy": "rag_fusion",
                    "use_web_search": True
                }
            )
            
            print("Search Results:")
            for content in result.content:
                print(content.text)
            
            # Upload a document
            upload_result = await session.call_tool(
                "upload_document",
                {
                    "file_path": "/path/to/document.pdf",
                    "metadata": {"category": "research"},
                    "chunking_strategy": "hierarchical"
                }
            )
            
            print("Upload Result:")
            for content in upload_result.content:
                print(content.text)

if __name__ == "__main__":
    asyncio.run(main())
```

## 🔧 Configuration

### **Environment Variables**
Set these in your MCP server environment:
```bash
R2R_BASE_URL=http://localhost:7272
PYTHONPATH=/path/to/your/r2r-test/py
```

### **Custom Configuration**
Edit `mcp/mcp_config.json` to customize:
```json
{
  "mcpServers": {
    "r2r-enhanced": {
      "command": "python",
      "args": ["/path/to/mcp/r2r_mcp_server.py"],
      "env": {
        "R2R_BASE_URL": "http://localhost:7272",
        "R2R_TIMEOUT": "30",
        "R2R_MAX_RETRIES": "3"
      }
    }
  }
}
```

## 📊 Response Formats

### **Search Response**
```json
{
  "content": [
    {
      "type": "text",
      "text": "# Enhanced Search Results\n**Query:** renewable energy\n**Strategy:** rag_fusion\n**Results:** 8 chunks found\n\n## Citations\n- [1] Solar_Energy_Report.pdf, page 15 (2023-10-15)\n- [2] Wind_Power_Analysis.xlsx, Revenue sheet\n\n## Top Results\n### Result 1\n**Score:** 0.95\n**Content:** Solar energy has become increasingly cost-effective...\n\n🌐 **Web search was used:** Limited internal knowledge, supplemented with web search"
    }
  ]
}
```

### **System Health Response**
```json
{
  "content": [
    {
      "type": "text",
      "text": "# R2R System Health\n**Status:** ✅ Healthy\n**Timestamp:** 2023-10-15 14:30:00\n\n## Enhanced Features Status\n- ✅ **Hierarchical Chunking:** Available\n- ✅ **Citation System:** Active\n- ✅ **Tool-Augmented Orchestration:** Ready\n- ✅ **Web Search Integration:** Configured"
    }
  ]
}
```

## 🚀 Production Deployment

### **Docker Integration**
Add MCP server to your Docker setup:
```dockerfile
# Add to your R2R Dockerfile
COPY mcp/ /app/mcp/
RUN pip install -r /app/mcp/requirements.txt
EXPOSE 8080
CMD ["python", "/app/mcp/r2r_mcp_server.py"]
```

### **Load Balancing**
For high-traffic applications:
```yaml
# docker-compose.yml
services:
  r2r-mcp-1:
    build: .
    command: python mcp/r2r_mcp_server.py
    environment:
      - R2R_BASE_URL=http://r2r:7272
  
  r2r-mcp-2:
    build: .
    command: python mcp/r2r_mcp_server.py
    environment:
      - R2R_BASE_URL=http://r2r:7272
  
  nginx:
    image: nginx
    ports:
      - "8080:80"
    depends_on:
      - r2r-mcp-1
      - r2r-mcp-2
```

## 🔒 Security Considerations

### **Authentication**
Add authentication to your MCP server:
```python
# In your MCP server
async def authenticate_request(headers):
    api_key = headers.get('Authorization')
    if not api_key or not validate_api_key(api_key):
        raise Exception("Unauthorized")
```

### **Rate Limiting**
Implement rate limiting for production:
```python
from asyncio import Semaphore

class RateLimiter:
    def __init__(self, max_concurrent=10):
        self.semaphore = Semaphore(max_concurrent)
    
    async def __aenter__(self):
        await self.semaphore.acquire()
    
    async def __aexit__(self, *args):
        self.semaphore.release()
```

---

**Your R2R Enhanced Template now provides a complete MCP interface for all applications!** 🎊

This enables any MCP-compatible application to access your enhanced R2R features through a standardized protocol, making it easy to build sophisticated AI-powered applications on top of your RAG system.
