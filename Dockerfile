# Use an official Python slim image as a base.
# python:3.12-slim-bookworm uses Debian 12 (Bookworm) which has recent packages.
# You can also use python:3.11-slim-bullseye (Debian 11) if preferred.
FROM python:3.12-slim-bookworm

# Set environment variables for non-interactive apt-get and unbuffered Python output
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies:
# - Essential build tools (like gcc if any pip packages need compilation)
# - Chromium browser
# - The Chromedriver compatible with the apt version of Chromium
# - All necessary libraries for Chromium to run headlessly
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    # For Python C extensions if needed by dependencies
    gcc \
    # Chromium browser and its driver from Debian's repositories
    chromium \
    chromium-driver \
    # Libraries often needed by Chromium/Selenium
    libglib2.0-0 \
    libnss3 \
    libfontconfig1 \
    libx11-6 \
    libxcb1 \
    libxcomposite1 \
    libxrandr2 \
    libxrender1 \
    libxtst6 \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    xdg-utils \
    # Clean up apt cache to reduce image size
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy only requirements.txt first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . .

# --- Your application's Selenium code (scrape.py) should be configured to: ---
# 1. Use options.binary_location = "/usr/bin/chromium" (or "/usr/bin/chromium-browser" if that's the name apt installs)
#    To check the exact name apt installs, you can temporarily add a RUN command like:
#    RUN ls -l /usr/bin/chro*
#    Debian Bookworm usually installs it as "chromium".
# 2. Use service = ChromeService(executable_path="/usr/bin/chromedriver")
#    The chromium-driver package typically places chromedriver at /usr/bin/chromedriver.

# Command to run your application (assuming main.py is your entry point)
CMD ["python", "main.py"]