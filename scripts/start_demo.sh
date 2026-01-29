#!/bin/bash
# Start the PersonaPlex Restaurant Receptionist Demo

set -e

echo "🍽️  PersonaPlex Restaurant Receptionist Demo"
echo "============================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo "Error: Please run this script from the personaplex_demo directory"
    exit 1
fi

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo "Checking prerequisites..."

if ! command_exists python3; then
    echo "Error: Python 3 is required"
    exit 1
fi

if ! command_exists node; then
    echo "Error: Node.js is required"
    exit 1
fi

echo -e "${GREEN}✓${NC} Prerequisites OK"
echo ""

# Start backend
echo "Starting backend..."
cd backend

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt

echo -e "${GREEN}✓${NC} Backend dependencies installed"

# Start backend in background
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo -e "${GREEN}✓${NC} Backend started (PID: $BACKEND_PID)"

cd ..

# Start frontend
echo ""
echo "Starting frontend..."
cd frontend

if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

echo -e "${GREEN}✓${NC} Frontend dependencies installed"

# Start frontend in background
npm run dev &
FRONTEND_PID=$!
echo -e "${GREEN}✓${NC} Frontend started (PID: $FRONTEND_PID)"

cd ..

echo ""
echo "============================================"
echo -e "${GREEN}Demo is running!${NC}"
echo ""
echo "  Frontend:  http://localhost:3000"
echo "  Backend:   http://localhost:8000"
echo "  API Docs:  http://localhost:8000/docs"
echo ""
echo -e "${YELLOW}Note:${NC} PersonaPlex server must be started separately."
echo "Without PersonaPlex, the demo runs in simulation mode."
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Trap Ctrl+C to clean up
cleanup() {
    echo ""
    echo "Stopping services..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo "Done."
    exit 0
}

trap cleanup INT

# Wait
wait
