# Fin-Qlib: Production-Ready Qlib Online Manager

A production-ready framework for managing online quant trading models with Qlib.

## Features

- **Configuration-Driven**: YAML-based configuration for easy management
- **Dynamic Strategy Management**: Add, remove, or update strategies without code changes
- **Multiple Ensemble Methods**: Average, weighted, dynamic, voting, etc.
- **Automatic Checkpointing**: Save and restore manager state
- **Signal Export**: Export signals in CSV/Parquet format
- **Performance Evaluation**: Built-in strategy comparison and recommendation
- **Hot Reload**: Update strategies without restarting services
- **Production-Ready**: Logging, error handling, cron integration

## Project Structure

```
fin-qlib/
├── config/                     # Configuration files
│   ├── online_config_template.yaml   # Full template
│   └── online_config_simple.yaml     # Simple config for testing
├── scripts/                    # Executable scripts
│   ├── first_run.py           # Initial setup and training
│   ├── run_routine.py         # Daily/weekly routine (cron)
│   ├── evaluate.py            # Strategy evaluation
│   ├── get_signals.py         # Export trading signals
│   └── upgrade_strategy.py    # Add/remove strategies
├── src/                        # Source code
│   ├── __init__.py
│   ├── managed_manager.py     # Main ManagedOnlineManager class
│   └── ensemble.py            # Ensemble methods
├── checkpoints/               # Manager checkpoints (created automatically)
├── logs/                      # Log files (created automatically)
└── signals/                   # Exported signals (created automatically)
```

## Quick Start

### 1. Installation

```bash
# Install Qlib
uv pip install ../qlib/dist/pyqlib-2026.2.8.dev3-cp313-cp313-macosx_15_0_arm64.whl

# Install additional dependencies
pip install pyyaml pandas numpy
```

### 2. Prepare Configuration

```bash
# Copy template
cp config/online_config_simple.yaml config/online_config.yaml

# Edit configuration
nano config/online_config.yaml
```

### 3. Initialize and First Run

```bash
# Run initial setup and training
python scripts/first_run.py --config config/online_config.yaml
```

This will:
- Initialize Qlib
- Create the OnlineManager
- Train initial models
- Save checkpoint

### 4. Set Up Cron Job

```bash
# Edit crontab
crontab -e

# Add line for daily routine at 16:30 (weekdays)
30 16 * * 1-5 cd /path/to/fin-qlib && python scripts/run_routine.py --config config/online_config.yaml >> logs/routine.log 2>&1
```

## Usage

### Daily Routine (Manual)

```bash
# Run routine with latest data
python scripts/run_routine.py --config config/online_config.yaml

# Run for specific date
python scripts/run_routine.py --config config/online_config.yaml --cur-time 2024-01-15

# Sync strategies before running
python scripts/run_routine.py --config config/online_config.yaml --sync
```

### Get Trading Signals

```bash
# Get latest signals
python scripts/get_signals.py --config config/online_config.yaml

# Get signals for specific date
python scripts/get_signals.py --config config/online_config.yaml --date 2024-01-15

# Get top 30 stocks
python scripts/get_signals.py --config config/online_config.yaml --top 30

# Export to CSV
python scripts/get_signals.py --config config/online_config.yaml --format csv --output signals.csv
```

### Evaluate Strategies

```bash
# Compare strategy performance
python scripts/evaluate.py --config config/online_config.yaml --start 2023-01-01 --end 2024-01-01

# Get ensemble method recommendation
python scripts/evaluate.py --config config/online_config.yaml --start 2023-01-01 --end 2024-01-01 --recommend
```

### Manage Strategies

```bash
# List all strategies
python scripts/upgrade_strategy.py --config config/online_config.yaml list

# Add new strategies from config
python scripts/upgrade_strategy.py --config config/online_config.yaml add

# Enable a strategy
python scripts/upgrade_strategy.py --config config/online_config.yaml enable XGB_Alpha158

# Disable a strategy
python scripts/upgrade_strategy.py --config config/online_config.yaml disable LGB_Old
```

## Configuration

### Basic Configuration

```yaml
online_manager:
  manager_path: "checkpoints/online_manager.pkl"
  freq: "day"

  trainer:
    type: "TrainerR"

  strategies:
    - name: "LGB_Alpha158"
      enabled: true
      type: "RollingStrategy"
      task_template:
        model:
          class: "LGBModel"
          module_path: "qlib.contrib.model.gbdt"
        dataset:
          class: "DatasetH"
          module_path: "qlib.data.dataset"
          kwargs:
            handler:
              class: "Alpha158"
              module_path: "qlib.contrib.data.handler"
            segments:
              train: ("2020-01-01", "2022-01-01")
              valid: ("2022-01-01", "2022-07-01")
              test: ("2022-07-01", "2023-01-01")
      rolling_config:
        step: 550
        rtype: "ROLL_SD"

  signal_config:
    ensemble_method: "average"  # average, weighted, dynamic, voting, best
    weights:
      LGB_Alpha158: 0.5
      XGB_Alpha158: 0.5

  signal_export:
    enabled: true
    dir: "signals"
    format: "csv"

qlib_config:
  provider_uri: "~/.qlib/qlib_data/cn_data"
  region: "cn"
```

### Ensemble Methods

#### 1. Average (Default)
```yaml
signal_config:
  ensemble_method: "average"
```
All models have equal weight.

#### 2. Weighted
```yaml
signal_config:
  ensemble_method: "weighted"
  weights:
    LGB_Alpha158: 0.6
    XGB_Alpha158: 0.4
```

#### 3. Dynamic Weighting
```yaml
signal_config:
  ensemble_method: "dynamic"
  lookback_days: 30  # Use recent 30 days performance
  metric: "ic"  # ic, rank_ic, sharpe
```
Weights automatically adjust based on recent performance.

#### 4. Voting
```yaml
signal_config:
  ensemble_method: "voting"
  top_n: 50  # Each model selects top 50 stocks
  min_votes: 2  # Stock needs at least 2 votes
  return_type: "weighted"  # weighted or uniform
```

#### 5. Best Model
```yaml
signal_config:
  ensemble_method: "best"
  best_strategy: "LGB_Alpha158"
```
Use only the specified strategy.

## Architecture

### Workflow

```
┌─────────────────┐
│   Cron/Airflow │  (Trigger daily/weekly)
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│    run_routine.py                   │
│  1. Load manager from checkpoint    │
│  2. Sync strategies (optional)      │
│  3. Execute routine()               │
│     - prepare_tasks()               │
│     - train()                       │
│     - prepare_online_models()       │
│     - update_online_pred()          │
│     - prepare_signals()             │
│  4. Save checkpoint                 │
│  5. Export signals                  │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Outputs:                           │
│  - checkpoints/online_manager.pkl   │
│  - signals/signals_YYYYMMDD.csv     │
│  - logs/routine_YYYYMMDD.log        │
└─────────────────────────────────────┘
```

### Adding New Strategies

1. **Development Phase**:
   ```bash
   # Test new model locally
   python scripts/evaluate.py --start 2023-01-01 --end 2024-01-01
   ```

2. **Shadow Mode** (Disabled in config):
   ```yaml
   strategies:
     - name: "New_Model"
       enabled: false  # Not participating in signals
   ```

3. **Canary Release** (Low weight):
   ```yaml
   signal_config:
     ensemble_method: "weighted"
     weights:
       Old_Model: 0.9
       New_Model: 0.1  # 10% weight
   ```

4. **Full Rollout**:
   ```yaml
   signal_config:
     ensemble_method: "dynamic"  # Auto-adjust weights
   ```

## Advanced Topics

### Custom Strategy

```yaml
strategies:
  - name: "MyStrategy"
    enabled: true
    type: "Custom"
    class: "MyStrategyClass"
    module_path: "my_module.strategies"
    init_params:
      param1: value1
```

### MongoDB Integration

For distributed training:

```yaml
qlib_config:
  mongo:
    enabled: true
    task_url: "mongodb://localhost:27017/"
    task_db_name: "qlib_online"

online_manager:
  trainer:
    type: "TrainerRM"  # Use MongoDB
```

### MLflow Integration

```yaml
qlib_config:
  mlflow_tracking_uri: "http://mlflow-server:5000"
```

Then view experiments:
```bash
mlflow ui
```

## Troubleshooting

### No signals available

```bash
# Check if manager exists and has signals
python scripts/get_signals.py --config config/online_config.yaml

# If not, run routine first
python scripts/run_routine.py --config config/online_config.yaml
```

### Model training failed

```bash
# Check logs
cat logs/online_manager_*.log

# Run with --sync to ensure strategies are loaded
python scripts/run_routine.py --config config/online_config.yaml --sync
```

### Reset everything

```bash
# WARNING: Deletes all models and predictions
python scripts/first_run.py --config config/online_config.yaml --reset
```

## Production Deployment

### Systemd Service

Create `/etc/systemd/system/fin-qlib.service`:

```ini
[Unit]
Description=Fin-Qlib Online Manager
After=network.target

[Service]
Type=oneshot
User=qlib
WorkingDirectory=/path/to/fin-qlib
ExecStart=/usr/bin/python scripts/run_routine.py --config config/online_config.yaml

[Install]
WantedBy=multi-user.target
```

Enable with timer:
```bash
systemctl enable fin-qlib.timer
systemctl start fin-qlib.timer
```

### Docker Deployment

```bash
# Build image
docker build -t fin-qlib .

# Run container
docker run -d \
  --name fin-qlib \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/checkpoints:/app/checkpoints \
  -v $(pwd)/signals:/app/signals \
  fin-qlib
```

## License

MIT License

## Contributing

Contributions welcome! Please submit pull requests to the repository.
