#!/bin/bash

PROJECT_DIR="/mnt/c/Users/varun/network-congestion-system"
VENV="$HOME/network-congestion-venv"

cd "$PROJECT_DIR" || exit 1

if [ ! -d "$VENV" ]; then
    echo "ERROR: Python virtual environment not found at $VENV"
    exit 1
fi

source "$VENV/bin/activate"

echo "=============================================="
echo " Intelligent Network Congestion System"
echo " Starting all services..."
echo "=============================================="

echo "[1/4] Starting network collector..."
python monitoring/collector.py > /tmp/network_collector.log 2>&1 &
COLLECTOR_PID=$!

sleep 2

echo "[2/4] Starting feature engine..."
python prediction/feature_engine.py > /tmp/network_features.log 2>&1 &
FEATURE_PID=$!

sleep 2

echo "[3/4] Starting closed-loop controller..."
python prediction/closed_loop_controller.py > /tmp/network_controller.log 2>&1 &
CONTROLLER_PID=$!

sleep 3

echo "[4/4] Starting dashboard..."
python dashboard/app.py > /tmp/network_dashboard.log 2>&1 &
DASHBOARD_PID=$!

echo
echo "=============================================="
echo " All services started"
echo "=============================================="
echo "Collector PID:   $COLLECTOR_PID"
echo "Feature PID:     $FEATURE_PID"
echo "Controller PID:  $CONTROLLER_PID"
echo "Dashboard PID:   $DASHBOARD_PID"
echo
echo "Dashboard: http://127.0.0.1:5000"
echo
echo "To stop everything:"
echo "    ./stop.sh"
echo
echo "Logs:"
echo "    /tmp/network_collector.log"
echo "    /tmp/network_features.log"
echo "    /tmp/network_controller.log"
echo "    /tmp/network_dashboard.log"
echo "=============================================="
