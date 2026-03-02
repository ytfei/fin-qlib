# Use uv base image with Python 3.13
# FROM ghcr.io/astral-sh/uv:python3.13-trixie
FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Set working directory
WORKDIR /app

# Install system dependencies
# RUN apt-get update && apt-get install -y --no-install-recommends \
#    gcc \
#    g++ \
#    && rm -rf /var/lib/apt/lists/*

# Copy pyqlib wheel package (built in CI/CD)
# COPY pyqlib-*.whl /tmp/

# # Copy dependency files
# COPY pyproject.toml uv.lock ./

# Copy project files
# 依赖的本地pyqlib-*.whl 是在CI/CD中构建的，会在 CI/CD中自动下载到这里
COPY . .

# Install dependencies using uv
# First install from pyproject.toml for core dependencies
RUN uv sync -n --frozen \
    && uv pip install --no-cache-dir pyqlib-*.whl \
    && rm -fr pyqlib-*.whl \
    && mkdir -p data config qlib_data project_root

# Make scripts executable
RUN chmod +x scripts/*.py 2>/dev/null || true

# /app/config 是输入配置
# /app/data 是输出结果
# /app/qlib_data 是 qlib 行情数据目录
VOLUME ["/app/project_root/"]

# Set the default command
# CMD ["uv", "run", "python", "scripts/run_routine.py", "--config", "config/online_config.yaml"]
CMD ["uv", "run", "python", "scripts/run_routine.py", "--project", "./project_root"]
