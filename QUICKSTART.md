# Quick Start Guide

This guide will help you get started with fin-qlib in 5 minutes.

## Prerequisites

- Python 3.7+
- Qlib data installed (see [Qlib Documentation](https://qlib.readthedocs.io/))

## Installation

```bash
cd /Users/mason/codebase/NexTech/qlib/fin-qlib

# Install dependencies
pip install -r requirements.txt
```

## Step 1: Create Configuration

```bash
# Use simple template for quick start
cp config/online_config_simple.yaml config/online_config.yaml

# Edit the configuration file with your settings
nano config/online_config.yaml
```

Key settings to verify:
- `provider_uri`: Path to your qlib data
- `region`: Your market region (cn, us, etc.)
- `task_template`: Model and dataset configuration

## Step 2: Initial Training

```bash
# Make scripts executable
bash scripts/make_executable.sh

# Run first training (this may take a while)
python scripts/first_run.py --config config/online_config.yaml
```

This will:
1. Initialize Qlib
2. Create the OnlineManager
3. Train initial models
4. Save checkpoint to `checkpoints/online_manager.pkl`

## Step 3: Run Routine

```bash
# Run daily routine
python scripts/run_routine.py --config config/online_config.yaml
```

## Step 4: Get Trading Signals

```bash
# View latest signals
python scripts/get_signals.py --config config/online_config.yaml

# Get top 30 stocks
python scripts/get_signals.py --config config/online_config.yaml --top 30

# Export to CSV
python scripts/get_signals.py --config config/online_config.yaml --format csv --output my_signals.csv
```

## Step 5: Set Up Automation

### Option A: Cron (Recommended)

```bash
# Edit crontab
crontab -e

# Add this line (runs at 16:30 every weekday)
30 16 * * 1-5 cd /Users/mason/codebase/NexTech/qlib/fin-qlib && python scripts/run_routine.py --config config/online_config.yaml >> logs/routine.log 2>&1
```

### Option B: Manual

Run this command daily after market close:
```bash
python scripts/run_routine.py --config config/online_config.yaml
```

## Common Tasks

### Add a New Strategy

1. Edit `config/online_config.yaml`:
```yaml
strategies:
  - name: "MyNewModel"
    enabled: true
    type: "RollingStrategy"
    task_template:
      # ... your model config
```

2. Add to manager:
```bash
python scripts/upgrade_strategy.py --config config/online_config.yaml add
```

### Compare Strategy Performance

```bash
python scripts/evaluate.py --config config/online_config.yaml --start 2023-01-01 --end 2024-01-01
```

### Change Ensemble Method

Edit `config/online_config.yaml`:
```yaml
signal_config:
  ensemble_method: "weighted"  # or "dynamic", "voting", "best"
  weights:
    LGB_Alpha158: 0.6
    XGB_Alpha158: 0.4
```

Next routine will use the new method.

## Troubleshooting

### "Configuration file not found"
```bash
# Copy template first
cp config/online_config_simple.yaml config/online_config.yaml
```

### "Manager checkpoint not found"
```bash
# Run first training
python scripts/first_run.py --config config/online_config.yaml
```

### "No signals available"
```bash
# Run routine to generate signals
python scripts/run_routine.py --config config/online_config.yaml
```

### Reset Everything
```bash
# WARNING: Deletes all models
python scripts/first_run.py --config config/online_config.yaml --reset
```

## Next Steps

1. Read [README.md](README.md) for detailed documentation
2. Explore different ensemble methods
3. Add multiple strategies
4. Set up monitoring and alerts

## Directory Structure After Setup

```
fin-qlib/
├── checkpoints/
│   └── online_manager.pkl      # Manager checkpoint
├── config/
│   └── online_config.yaml      # Your configuration
├── logs/
│   └── online_manager_*.log    # Log files
└── signals/
    ├── signals_latest.csv      # Latest signals
    └── signals_YYYYMMDD.csv    # Historical signals
```

## Getting Help

- Check logs: `tail -f logs/online_manager_*.log`
- View status: `python scripts/run_routine.py --config config/online_config.yaml --status`
- List strategies: `python scripts/upgrade_strategy.py --config config/online_config.yaml list`
