# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

RUN pip install uv

# Copy app code
COPY . .

RUN uv sync

# Expose port
EXPOSE 8000
