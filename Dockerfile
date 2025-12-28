# Use slim for smaller image
FROM python:3.11-slim

# Prevent Python from writing .pyc files & enable unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Cloud Run listens on 8080
ENV PORT=8080
# Fallback Defaults to prevent startup crash
ENV GOOGLE_CLOUD_PROJECT=nanobananacomic-482111
ENV GOOGLE_PROJECT_ID=nanobananacomic-482111
ENV VERTEX_LOCATION=asia-southeast2
ENV APP_ENV=production

WORKDIR /app

# System deps for Pillow (jpeg/png), and CA certs
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libpng-dev \
    libwebp-dev \
    libtiff5-dev \
    libopenjp2-7-dev \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Install Python deps first (better layer caching)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . /app

# Optional: if you have static/ folder, it will be copied too
EXPOSE 8080

# Start FastAPI
CMD ["uvicorn", "main:app", "--host=0.0.0.0", "--port=8080"]
