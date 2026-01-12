# Video Worker - Dedicated Video Generation Service
FROM python:3.11-slim

# Install FFmpeg and required system packages
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for caching
COPY video_worker/requirements.txt /app/video_worker/
RUN pip install --no-cache-dir -r /app/video_worker/requirements.txt

# Copy the entire project (needed for video_generator.py and app modules)
COPY . /app/

# Set Python path
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8080

# Run the video worker
CMD ["python", "video_worker/main.py"]
