#!/bin/bash
# Deployment script for fin-qlib

set -e

echo "======================================"
echo "Fin-Qlib Deployment Script"
echo "======================================"

# Configuration
PROJECT_DIR="/path/to/fin-qlib"  # Change this
PYTHON_CMD="python3"
LOG_DIR="logs"
CHECKPOINT_DIR="checkpoints"
SIGNAL_DIR="signals"

# Create directories
echo "Creating directories..."
mkdir -p "$LOG_DIR"
mkdir -p "$CHECKPOINT_DIR"
mkdir -p "$SIGNAL_DIR"

# Make scripts executable
echo "Making scripts executable..."
chmod +x scripts/*.py

# Check if config exists
if [ ! -f "config/online_config.yaml" ]; then
    echo "Configuration file not found!"
    echo "Copying template..."
    cp config/online_config_simple.yaml config/online_config.yaml
    echo "Please edit config/online_config.yaml with your settings"
    exit 1
fi

# Setup cron job
echo ""
echo "======================================"
echo "Cron Job Setup"
echo "======================================"
echo "Current crontab:"
crontab -l 2>/dev/null || true

echo ""
read -p "Do you want to add a cron job for daily routine? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    CRON_LINE="30 16 * * 1-5 cd $PROJECT_DIR && $PYTHON_CMD scripts/run_routine.py --config config/online_config.yaml >> $LOG_DIR/routine.log 2>&1"

    # Check if already exists
    if crontab -l 2>/dev/null | grep -q "run_routine.py"; then
        echo "Cron job already exists"
    else
        # Add to crontab
        (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
        echo "Cron job added:"
        echo "  $CRON_LINE"
    fi
fi

# Test run
echo ""
echo "======================================"
echo "Test Run"
echo "======================================"
read -p "Do you want to run first training now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    $PYTHON_CMD scripts/first_run.py --config config/online_config.yaml
fi

echo ""
echo "======================================"
echo "Deployment Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Review configuration: config/online_config.yaml"
echo "2. Check logs: tail -f $LOG_DIR/online_manager_*.log"
echo "3. Get signals: $PYTHON_CMD scripts/get_signals.py --config config/online_config.yaml"
echo ""
echo "For manual routine:"
echo "  $PYTHON_CMD scripts/run_routine.py --config config/online_config.yaml"
