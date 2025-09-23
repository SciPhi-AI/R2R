# R2R Enhanced Template Version

**Version**: 1.0.0  
**Date**: September 22, 2025  
**Base R2R Version**: Latest (with GPT-5 support)

## 🔧 Enhancements

### Bug Fixes Applied
- **Graph Extraction Message Formatting** - Fixed `'dict' object has no attribute 'role'` error
- **Audio Transcription Parameter Filtering** - Fixed parameter passing for modern OpenAI models
- **Enhanced Debug Logging** - Comprehensive logging for troubleshooting

### Model Configuration
- **Quality LLM**: `gpt-5-mini` - Latest OpenAI model for RAG responses
- **Reasoning LLM**: `o3-mini` - Advanced reasoning for research agent  
- **Planning LLM**: `anthropic/claude-3-7-sonnet` - Strategic planning
- **Vision LLM**: `gpt-o4-mini` - Image analysis capabilities
- **Audio LLM**: `gpt-4o-mini-transcribe` - High-quality transcription
- **Fast LLM**: `gpt-5-nano` - Quick internal operations

### Embeddings
- **Model**: `openai/text-embedding-3-large`
- **Dimensions**: 3072 (high quality)
- **Binary Quantization**: Enabled for performance

### Security Enhancements
- **Enhanced .gitignore** - Prevents API key exposure
- **Environment templates** - Safe configuration management
- **Pre-commit safety checks** - Automated secret detection

### Configuration Optimizations
- **Upload Limit**: 200GB for large document processing
- **Chunk Size**: 1024 tokens with 512 overlap
- **Automatic Graph Extraction**: Enabled by default
- **Entity Deduplication**: Automatic cleanup

## 📊 Compatibility

### Tested With
- ✅ **OpenAI GPT-5** and **GPT-4o** models
- ✅ **Anthropic Claude-3.7-Sonnet**
- ✅ **OpenAI O3-mini** reasoning model
- ✅ **Modern audio transcription** models
- ✅ **Multi-modal document processing**

### Requirements
- **Docker** and **Docker Compose**
- **OpenAI API Key** (required)
- **Anthropic API Key** (required for planning agent)
- **Optional**: Serper/Tavily API keys for web search

## 🚀 Performance Improvements

- **Faster graph extraction** with bug fixes
- **Improved audio processing** with modern models
- **Enhanced embeddings** for better search quality
- **Optimized chunking** for better context retention

## 🔄 Update History

### v1.0.0 (September 22, 2025)
- Initial enhanced template release
- All core bug fixes applied
- Modern AI model integration
- Production-ready configuration
- Comprehensive documentation and testing

---

**Maintained by**: Chris Scott  
**Repository**: https://github.com/chrisgscott/R2R  
**Original R2R**: https://github.com/SciPhi-AI/R2R
