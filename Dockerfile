# Dockerfile for Railway deployment
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies first (for caching)
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY src/ src/

# Default command - Railway will set PORT env var
CMD ["python", "-m", "src.main", "--server", "--host", "0.0.0.0"]
