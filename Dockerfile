FROM python:3.11-slim

# System dependencies: FFmpeg, yt-dlp prerequisites, Playwright browser deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    wget \
    gnupg \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libgtk-3-0 \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

# Copy application code
COPY . .

# Create directories for videos
RUN mkdir -p videos/raw videos/processed logs auth

# Railway uses $PORT env var
EXPOSE ${PORT:-8000}

CMD uvicorn api_server:app --host 0.0.0.0 --port ${PORT:-8000}
