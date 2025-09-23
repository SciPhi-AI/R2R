# R2R Enhanced Template

This is an enhanced R2R template with bug fixes, modern AI models, and production-ready configuration.

## 🎯 What's Included

### ✅ **Bug Fixes**
- **Graph extraction** - Fixed message formatting bug preventing entity extraction
- **Audio transcription** - Fixed parameter filtering for modern OpenAI models
- **Enhanced debugging** - Comprehensive logging for troubleshooting

### 🤖 **Modern AI Models**
- **GPT-5** - Latest OpenAI models for quality responses
- **O3-mini** - Advanced reasoning for research agent
- **Claude-3.7-Sonnet** - Strategic planning capabilities
- **Whisper-1** - High-quality audio transcription
- **text-embedding-3-large** - Superior embeddings (3072 dimensions)

### ⚙️ **Enhanced Configuration**
- **MCP Integration** - Model Context Protocol server for standardized API access
- **Supabase-ready** - Optimized for Supabase with enhanced schema and features
- **Automatic graph extraction** - Entities and relationships extracted automatically
- **High upload limits** - 200GB for large document processing
- **Advanced chunking strategies** - Recursive and hierarchical chunking options
- **Enhanced citation system** - Precise source attribution with deep links
- **Multi-modal processing** - Text, images, and audio support
- **Security hardened** - Proper .gitignore and API key protection

## 🚀 Quick Start

### 1. Clone and Setup
```bash
git clone https://github.com/chrisgscott/R2R.git my-r2r-project
cd my-r2r-project
```

### 2. Setup Supabase (Recommended)
1. Create a [Supabase project](https://supabase.com)
2. Run the SQL in `supabase/setup.sql` in your Supabase SQL editor
3. Get your credentials from Supabase dashboard

### 3. Add API Keys
Edit `docker/env/r2r-full.env` and add your keys:
```bash
# Supabase Database
POSTGRES_HOST=your-project-ref.supabase.co
POSTGRES_PASSWORD=your_supabase_password
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key

# AI Models
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
# Optional: SERPER_API_KEY, TAVILY_API_KEY for web search
```

### 4. Start R2R
```bash
./setup-new-project.sh
# OR manually:
docker compose -f docker/compose.full.yaml --profile postgres up -d
```

### 5. Setup MCP Server (Optional)
```bash
./mcp/setup_mcp.sh
```

### 6. Access R2R
- **API**: http://localhost:7272
- **Dashboard**: http://localhost:7273
- **MCP Server**: Available for any MCP-compatible application

## 🧪 Test All Features

```python
from r2r import R2RClient

client = R2RClient('http://localhost:7272')

# Test document upload and RAG
response = client.documents.create(file_path="test.txt")
search_result = client.retrieval.search("your query")

# Test graph extraction (automatic)
entities = client.graphs.list_entities()
relationships = client.graphs.list_relationships()

# Test agent mode
agent_response = client.agent.chat("Analyze this document")

# Test via MCP (if setup)
# Use any MCP-compatible client to access all features
```

## 🔧 Customization

### Model Configuration
Edit `py/r2r/r2r.toml` to change models:
```toml
quality_llm = "gpt-5-mini"              # Main model
reasoning_llm = "o3-mini"                # Research agent
planning_llm = "anthropic/claude-3-7-sonnet"  # Planning
```

### Advanced Chunking
Choose between chunking strategies:
```toml
[ingestion]
chunking_strategy = "hierarchical"  # or "recursive"
child_chunk_size = 512
children_per_parent = 4
generate_summaries = true
```

### Citation System
Configure citation style and behavior:
```toml
[orchestration.citation_settings]
citation_style = "detailed"  # "detailed", "compact", "academic"
max_citations = 5
generate_deep_links = true
```

### Graph Extraction
Customize entity and relationship types:
```toml
[database.graph_creation_settings]
entity_types = ["Person", "Organization", "Technology"]
relation_types = ["WORKS_FOR", "FOUNDED", "USES"]
```

## 🛡️ Security Features

- **API keys never committed** - Enhanced .gitignore protection
- **Local-only secrets** - Environment files ignored by git
- **Safety checks** - Pre-commit scripts to prevent key exposure

## 📊 What Works Out of Box

- ✅ **Text processing** with GPT-5
- ✅ **Image analysis** with vision models
- ✅ **Audio transcription** with Whisper
- ✅ **Spreadsheet processing** with narrative summaries + structured data
- ✅ **Tool-augmented RAG** with automatic Text-to-SQL for precise queries
- ✅ **Graph extraction** with automatic entity detection
- ✅ **Research agent** with O3 reasoning
- ✅ **Multi-modal RAG** across all content types
- ✅ **Web search integration** (with API keys)
- ✅ **MCP server** for standardized application integration

## 🆘 Troubleshooting

### Graph Extraction Issues
Check logs: `docker logs docker-r2r-1 | grep "GRAPH EXTRACTION"`

### Audio Transcription Issues  
Ensure audio files are supported formats (mp3, wav, m4a)

### Model Issues
Verify API keys are set correctly in `docker/env/r2r-full.env`

## 🤝 Contributing

This template includes bug fixes that benefit the R2R community. Consider contributing back to the main project!

---

**Built with ❤️ using R2R + Modern AI Models**
