# Use uv base image with Python 3.13
FROM ghcr.io/astral-sh/uv:python3.13-trixie

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
# 重命名 pyqlib-2026.2.8.whl
COPY pyproject.toml uv.lock pyqlib-2026.2.8.whl ./

# Install dependencies using uv
# First install from pyproject.toml for core dependencies
RUN uv sync --frozen || uv pip install -e . || echo "Continuing with requirements.txt"

# Then install from requirements.txt for additional dependencies
RUN uv pip install pyqlib-2026.2.8.whl && rm -fr pyqlib-2026.2.8.whl

# Copy project files
COPY . .

# Create necessary directories
RUN mkdir -p checkpoints logs signals config mlruns

# Make scripts executable
RUN chmod +x scripts/*.py 2>/dev/null || true

# Set the default command
CMD ["python", "scripts/run_routine.py", "--config", "config/online_config.yaml"]
