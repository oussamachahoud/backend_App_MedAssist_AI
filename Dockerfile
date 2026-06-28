FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Memory Tuning for PyTorch & CPU-only environments (6GB RAM VPS)
# Prevent excessive memory fragmentation
ENV MALLOC_ARENA_MAX=2
# Match thread count to vCPU allocation (adjust if VPS has 1 or 3+ cores).
# Directly affects TTA×8 latency — 1 thread on a 2-core box wastes ~40% throughput.
ENV OMP_NUM_THREADS=2
ENV MKL_NUM_THREADS=2

WORKDIR /app

# Install system dependencies needed for OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy only the requirements first to leverage Docker cache
COPY requirements.txt .

# Install PyTorch CPU-only via the dedicated index URL.
# Each package in its own RUN to:
#   1. Reduce peak memory during build (avoids Bus error on constrained WSL2)
#   2. Isolate failures — easy to see which package crashes
#   3. Better Docker layer caching — torch layer survives torchvision bumps
RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    torch

RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    torchvision

# Pre-install heavy ML/math dependencies individually to prevent memory spikes
# (SciPy and Scikit-Learn wheels are large and memory-intensive to unpack/install)
RUN pip install --no-cache-dir numpy
RUN pip install --no-cache-dir scipy
RUN pip install --no-cache-dir scikit-learn
RUN pip install --no-cache-dir timm
RUN pip install --no-cache-dir opencv-python-headless

# Install remaining dependencies (FastAPI, Settings, Logging, Testing, etc.)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create a non-root user for security
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Start Uvicorn. Single worker — the PyTorch model takes ~1-2GB in RAM.
# Even with 6GB, multiple workers would duplicate the model and risk OOM.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
