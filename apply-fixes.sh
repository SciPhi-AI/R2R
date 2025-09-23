#!/bin/bash
# Apply R2R bug fixes to a fresh installation

echo "🔧 Applying R2R bug fixes..."

# Check if we're in an R2R directory
if [ ! -d "py/core" ]; then
    echo "❌ Error: Not in an R2R directory. Please run from R2R root."
    exit 1
fi

# Apply the patch
if [ -f "r2r-bugfixes.patch" ]; then
    echo "📋 Applying patch file..."
    git apply r2r-bugfixes.patch
    echo "✅ Bug fixes applied successfully!"
else
    echo "❌ Error: r2r-bugfixes.patch not found"
    exit 1
fi

# Copy configuration
if [ -f "py/r2r/r2r.toml" ]; then
    echo "⚙️ Configuration already exists"
else
    echo "📝 Copy your custom r2r.toml to py/r2r/r2r.toml"
fi

echo "🎉 Setup complete! Your R2R instance now includes the bug fixes."
