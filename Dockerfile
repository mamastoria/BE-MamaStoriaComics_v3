# Video Worker - Dedicated Video Generation Service
FROM python:3.11-slim

# Install FFmpeg and required system packages
# Note: libgl1-mesa-glx replaced with libgl1 for Debian Trixie
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Install additional dependencies for video worker
RUN pip install --no-cache-dir uvicorn

# Copy the entire project
COPY . /app/

# Set Python path and environment
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose port
EXPOSE 8080

# Run the video worker
CMD ["python", "video_worker/main.py"]
