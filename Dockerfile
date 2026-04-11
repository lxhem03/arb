FROM python:3.10-slim

# Install system dependencies: FFmpeg + git
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "bot.py"]
