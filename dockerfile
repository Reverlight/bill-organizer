# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

RUN pip install uv

RUN apt-get update && apt-get install -y poppler-utils tesseract-ocr && rm -rf /var/lib/apt/lists/*

# Copy app code
COPY . .

RUN uv sync

# Expose port
EXPOSE 8000
