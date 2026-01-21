# AI Equity Research Docker Image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY pyproject.toml .

# Install Python dependencies
RUN pip install --no-cache-dir .

# Copy application code
COPY config/ config/
COPY src/ src/
COPY scheduler/ scheduler/
COPY scripts/ scripts/

# Create data directories
RUN mkdir -p data/reports data/state

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default command runs the scheduler
CMD ["python", "scheduler/runner.py"]
