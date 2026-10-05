#!/bin/bash

echo "Stopping Network Congestion System..."

pkill -f "monitoring/collector.py" 2>/dev/null
pkill -f "prediction/feature_engine.py" 2>/dev/null
pkill -f "prediction/closed_loop_controller.py" 2>/dev/null
pkill -f "dashboard/app.py" 2>/dev/null

echo "All project services stopped."
