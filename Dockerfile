FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create directories
RUN mkdir -p checkpoints logs signals config

# Make scripts executable
RUN chmod +x scripts/*.py

# Default command
CMD ["python", "scripts/run_routine.py", "--config", "config/online_config.yaml"]
