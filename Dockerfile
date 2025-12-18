FROM mcr.microsoft.com/playwright/python:v1.57.0-jammy

WORKDIR /app

# Copy application files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .

# Create data directory
RUN mkdir -p /app/data

# Run the scraper
CMD ["python", "scraper.py"]
