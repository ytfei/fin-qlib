#!/bin/bash
# Make all scripts executable

chmod +x scripts/*.py
echo "All scripts made executable"

# List scripts
echo ""
echo "Executable scripts:"
ls -la scripts/*.py
