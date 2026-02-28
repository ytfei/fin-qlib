#!/usr/bin/zsh

cd /root/codebase/fin-qlib
uv run python scripts/run_routine.py --config config/online_config.yaml

# >> data/logs/routine.log 2>&1