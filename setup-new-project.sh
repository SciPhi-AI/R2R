#!/bin/bash
# Enhanced R2R Template Setup Script

echo "🚀 R2R Enhanced Template Setup"
echo "================================"

# Check if env file exists
if [ ! -f "docker/env/r2r-full.env" ]; then
    echo "📋 Creating environment file from template..."
    cp docker/env/r2r-full.env.template docker/env/r2r-full.env
    echo "⚠️  Please edit docker/env/r2r-full.env and add your API keys:"
    echo "   REQUIRED: OPENAI_API_KEY, ANTHROPIC_API_KEY"
    echo "   OPTIONAL: SERPER_API_KEY, TAVILY_API_KEY (for web search)"
    echo ""
    echo "Then run this script again."
    exit 1
fi

# Check if API keys are set
if ! grep -q "OPENAI_API_KEY=sk-" docker/env/r2r-full.env; then
    echo "❌ Missing OpenAI API key in docker/env/r2r-full.env"
    exit 1
fi

if ! grep -q "ANTHROPIC_API_KEY=sk-ant-" docker/env/r2r-full.env; then
    echo "❌ Missing Anthropic API key in docker/env/r2r-full.env"
    exit 1
fi

echo "✅ API keys configured"

# Check Docker
if ! docker --version > /dev/null 2>&1; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi

echo "✅ Docker available"
echo ""
echo "🐳 Starting R2R Enhanced Template..."

# Start R2R
docker compose -f docker/compose.full.yaml --profile postgres up -d

echo ""
echo "🎉 R2R Enhanced Template is starting!"
echo "=================================="
echo "✅ Graph extraction bug fixes applied"
echo "✅ Audio transcription bug fixes applied"
echo "✅ Modern AI models configured:"
echo "   • GPT-5 for quality responses"
echo "   • O3-mini for reasoning"
echo "   • Claude-3.7-Sonnet for planning"
echo "   • Whisper-1 for audio transcription"
echo "✅ High-quality embeddings (3072 dimensions)"
echo "✅ Automatic entity/relationship extraction"
echo "✅ Enhanced security and configuration"
echo ""
echo "🌐 Access Points:"
echo "   • R2R API: http://localhost:7272"
echo "   • Dashboard: http://localhost:7273"
echo ""
echo "📚 Next Steps:"
echo "   1. Test with: python -c \"from r2r import R2RClient; print('R2R Ready!')\""
echo "   2. Upload documents and try RAG queries"
echo "   3. Check graph extraction in the dashboard"
echo "   4. Try agent mode for advanced interactions"
