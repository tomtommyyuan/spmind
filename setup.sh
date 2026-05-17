#!/bin/bash
# =============================================================================
# SP-Mind Agent - Setup Script
# =============================================================================

echo "Setting up SP-Mind Agent..."

# -----------------------------------------------------------------------------
# Step 1: Create conda environment (if not exists)
# -----------------------------------------------------------------------------
if ! conda info --envs | grep -q "spmind"; then
    echo "Creating conda environment 'spmind'..."
    conda create -n spmind python=3.11 -y
fi

echo "Activating spmind environment..."
eval "$(conda shell.bash hook)"
conda activate spmind

# -----------------------------------------------------------------------------
# Step 2: Install SP-Mind package (includes all Python dependencies)
# -----------------------------------------------------------------------------
echo "Installing SP-Mind package..."
pip install -e .

# -----------------------------------------------------------------------------
# Step 3: Install Claude Code CLI (requires npm)
# -----------------------------------------------------------------------------
if command -v npm &> /dev/null; then
    echo "Installing Claude Code CLI..."
    npm install -g @anthropic-ai/claude-code
else
    echo "WARNING: npm not found. Please install Node.js first, then run:"
    echo "    npm install -g @anthropic-ai/claude-code"
fi

# -----------------------------------------------------------------------------
# Step 4: Verify installation
# -----------------------------------------------------------------------------
echo ""
echo "Verifying installation..."
python -c "from spmind.agent import SPMindAgent; print('  SPMindAgent imported successfully')" || echo "  SP-Mind package import failed"
python -c "import claude_agent_sdk; print('  claude-agent-sdk imported successfully')" || echo "  Claude SDK import failed"

# -----------------------------------------------------------------------------
# Step 5: Next steps
# -----------------------------------------------------------------------------
echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Set your API key:"
echo "       export ANTHROPIC_API_KEY='your-api-key'"
echo ""
echo "  2. Log in to Claude Code CLI:"
echo "       claude login"
echo ""
echo "  3. Run the agent:"
echo "       conda activate spmind"
echo "       python run_agent.py 'Your task here' --output-dir your_output_dir"
