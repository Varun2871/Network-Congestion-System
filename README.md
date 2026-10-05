# Intelligent Live Network Congestion Prediction and Closed-Loop Adaptive Traffic Management System

## 1. Project Overview

This project implements an intelligent network congestion management system that combines:

- Real-time network monitoring
- Network feature engineering
- Machine learning-based congestion assessment
- Deterministic safety validation
- Adaptive traffic management
- Closed-loop feedback
- Live monitoring dashboard
- Controlled network experiments using iPerf3

The system continuously measures network conditions, predicts the current state, validates the prediction against live safety conditions, applies an adaptive traffic policy, and then measures the network again.

## 2. Closed-Loop Architecture

```text
Network Telemetry
       |
       v
Feature Engineering
       |
       v
Machine Learning Prediction
       |
       v
Safety Validation
       |
       v
Congestion Decision
       |
       v
Adaptive Traffic Policy
       |
       v
Linux tc / HTB / SFQ / u32
       |
       v
Network Response
       |
       +--------------------+
                            |
                            v
                    Re-measure Network
                            |
                            +----> Feedback Loop

## Technology Stack

### Programming Languages
- Python
- JavaScript
- HTML
- CSS
- Bash

### Machine Learning
- Scikit-learn
- Random Forest Classifier
- Feature Engineering
- Rolling Statistical Features
- Classification and Prediction Confidence

### Data Processing
- Pandas
- NumPy
- CSV
- JSON
- JSONL

### Networking
- Linux Networking
- Linux Traffic Control (`tc`)
- HTB (Hierarchical Token Bucket)
- SFQ (Stochastic Fairness Queueing)
- u32 Packet Classification
- iPerf3
- ICMP/Ping-based Network Measurements

### Backend
- Flask
- REST-style API endpoints

### Frontend
- HTML5
- CSS3
- Vanilla JavaScript
- Canvas-based Live Charts

### Operating Environment
- Windows 11
- WSL/Linux
- Python Virtual Environment

### Project Automation
- Bash startup and shutdown scripts
- `requirements.txt`
- `run.sh`
- `stop.sh`

## System Architecture

![System Architecture](docs/diagram.png)

The system follows a closed-loop architecture:

1. **Network Monitoring** — Collect live network telemetry.
2. **Feature Engineering** — Convert raw measurements into useful ML features.
3. **Machine Learning** — Predict NORMAL, WARNING, or CONGESTED network states.
4. **Safety Validation** — Verify ML predictions against deterministic live-network conditions.
5. **Decision Engine** — Determine the validated network state and congestion score.
6. **Adaptive Traffic Management** — Dynamically adjust traffic priorities.
7. **Linux Traffic Control** — Apply bandwidth policies using `tc`, HTB, SFQ, and u32.
8. **Feedback** — Measure the network again after applying the policy.
9. **Dashboard** — Display live network conditions, predictions, policies, events, and experiments.

## Quick Start

Activate the project environment:

```bash
cd /mnt/c/Users/varun/network-congestion-system
source ~/network-congestion-venv/bin/activate

## Start the complete system:

./run.sh

## Open the dashboard:

http://127.0.0.1:5000

## Stop the system:

./stop.sh
