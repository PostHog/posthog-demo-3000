FROM python:3.12.5-slim-bookworm

# Set the working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose the port Flask listens on (5000 to match README and local runs)
EXPOSE 5000

# Command to run the app with Gunicorn on port 5000
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]