#!/bin/bash
# Astrosis run script
# Choose between CLI interface or full frontend+backend setup

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

echo "Astrosis Orbital Mechanics Engine"
echo "=================================="
echo ""
echo "Select run mode:"
echo "1) CLI only (command-line interface)"
echo "2) Frontend + Backend (web interface)"
echo ""
read -p "Enter choice [1-2]: " choice

case $choice in
    1)
        echo "Starting CLI mode..."
        echo "Use commands like: python main.py fetch --id 25544"
        echo "                    python main.py passes --id 25544 --lat 40.7 --lon -74.0"
        bash
        ;;
    2)
        echo "Starting Frontend + Backend..."
        echo ""
        echo "Backend (Python FastAPI) starting on http://localhost:8000"
        echo "Frontend (React) starting on http://localhost:8080"
        echo ""
        echo "Press Ctrl+C to stop both servers"
        echo ""
        
        # Kill any leftover process on port 8000 from a prior run
        kill $(ss -tlnp | grep ':8000 ' | grep -oP 'pid=\K\d+') 2>/dev/null
        sleep 1

        cleanup() {
            echo ""
            echo "Shutting down..."
            kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
            wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
            echo "Stopped."
            exit 0
        }
        trap cleanup SIGINT SIGTERM
        
        # Start backend in background
        python server.py &
        BACKEND_PID=$!
        
        # Wait a moment for backend to start
        sleep 2
        
        # Start frontend
        pnpm dev &
        FRONTEND_PID=$!
        
        # Wait for both processes
        wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
        ;;
    *)
        echo "Invalid choice. Please run again and select 1 or 2."
        exit 1
        ;;
esac
