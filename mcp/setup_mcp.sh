#!/bin/bash
# Setup MCP Server for R2R Enhanced Template

echo "🔧 Setting up R2R Enhanced MCP Server..."

# Install MCP requirements
echo "📦 Installing MCP dependencies..."
pip install -r mcp/requirements.txt

# Make the MCP server executable
chmod +x mcp/r2r_mcp_server.py

# Create MCP configuration directory if it doesn't exist
mkdir -p ~/.config/mcp

# Copy MCP configuration
echo "⚙️ Setting up MCP configuration..."
cp mcp/mcp_config.json ~/.config/mcp/

# Update the config with the correct path
CURRENT_DIR=$(pwd)
sed -i.bak "s|/Users/chrisgscott/projects/r2r-test|$CURRENT_DIR|g" ~/.config/mcp/mcp_config.json

echo "✅ MCP Server setup complete!"
echo ""
echo "🎯 Next Steps:"
echo "1. Make sure R2R is running: ./setup-new-project.sh"
echo "2. Test MCP server: python mcp/r2r_mcp_server.py"
echo "3. Use in your applications via MCP protocol"
echo ""
echo "📚 Available MCP Tools:"
echo "- upload_document: Upload and process documents"
echo "- enhanced_search: Advanced RAG with multiple strategies"
echo "- graph_search: Knowledge graph exploration"
echo "- query_spreadsheet: Natural language spreadsheet queries"
echo "- agent_chat: Multi-step reasoning agent"
echo "- get_analytics: Usage and performance metrics"
echo "- system_health: Check R2R system status"
