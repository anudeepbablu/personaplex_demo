#!/bin/bash
# Setup script for PersonaPlex server

set -e

echo "🎤 PersonaPlex Server Setup"
echo "==========================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check for NVIDIA GPU
if ! command -v nvidia-smi &> /dev/null; then
    echo -e "${YELLOW}Warning:${NC} NVIDIA GPU not detected."
    echo "PersonaPlex works best with GPU acceleration."
    echo ""
fi

# Check HF_TOKEN
if [ -z "$HF_TOKEN" ]; then
    echo -e "${RED}Error:${NC} HF_TOKEN environment variable not set."
    echo ""
    echo "To get your token:"
    echo "1. Go to https://huggingface.co/settings/tokens"
    echo "2. Create a new token with read access"
    echo "3. Accept the PersonaPlex model license"
    echo "4. Export: export HF_TOKEN=your_token_here"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓${NC} HF_TOKEN is set"

# Install system dependencies
echo ""
echo "Installing system dependencies..."

if command -v apt-get &> /dev/null; then
    sudo apt-get update
    sudo apt-get install -y libopus-dev
elif command -v yum &> /dev/null; then
    sudo yum install -y opus-devel
elif command -v brew &> /dev/null; then
    brew install opus
else
    echo -e "${YELLOW}Warning:${NC} Could not detect package manager."
    echo "Please install libopus manually."
fi

echo -e "${GREEN}✓${NC} System dependencies installed"

# Create virtual environment
echo ""
echo "Setting up Python environment..."

if [ ! -d "personaplex_env" ]; then
    python3 -m venv personaplex_env
fi

source personaplex_env/bin/activate

# Install moshi (PersonaPlex base)
pip install --upgrade pip
pip install moshi

echo -e "${GREEN}✓${NC} Moshi package installed"

# Verify installation
echo ""
echo "Verifying installation..."

python3 -c "import moshi; print('Moshi version:', moshi.__version__)" 2>/dev/null || {
    echo -e "${RED}Error:${NC} Moshi installation verification failed"
    exit 1
}

echo -e "${GREEN}✓${NC} Installation verified"

# Create launcher script
echo ""
echo "Creating launcher script..."

cat > run_personaplex.sh << 'EOF'
#!/bin/bash
# Launch PersonaPlex server

source personaplex_env/bin/activate

echo "Starting PersonaPlex server..."
echo "The server will generate a temporary SSL certificate."
echo ""

# Run with temporary SSL certs
python -m moshi.server \
    --host 0.0.0.0 \
    --port 8998 \
    --gradio-tunnel

# Alternative: without tunnel (for local use)
# python -m moshi.server --host localhost --port 8998
EOF

chmod +x run_personaplex.sh

echo -e "${GREEN}✓${NC} Launcher script created: run_personaplex.sh"

echo ""
echo "==========================="
echo -e "${GREEN}Setup complete!${NC}"
echo ""
echo "To start PersonaPlex:"
echo "  ./run_personaplex.sh"
echo ""
echo "The server will run on port 8998."
echo "A web UI link will be printed when ready."
echo ""
echo "Then start the demo backend with:"
echo "  cd ../backend && uvicorn app.main:app --port 8000"
