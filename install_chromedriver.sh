#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

echo "INSTALL_SCRIPT: Starting Chromedriver installation..."

# !!! USER ACTION: YOU MUST REPLACE THIS URL WITH A VALID CHROMEDRIVER URL !!!
# 1. Go to: https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json
# 2. Find a recent "Stable" version (e.g., for Chrome/Chromium 125 or 126).
# 3. Copy the URL for the "chromedriver" -> "linux64" download.
# Example (this URL will likely be outdated or specific, VERIFY AND REPLACE IT):
CHROMEDRIVER_URL="https://storage.googleapis.com/chrome-for-testing-public/125.0.6422.76/linux64/chromedriver-linux64.zip"

echo "INSTALL_SCRIPT: Downloading Chromedriver from ${CHROMEDRIVER_URL}..."
# Using curl with flags: -s (silent), -S (show error), -L (follow redirects), -f (fail on server error), -o (output)
curl -sSLf -o /tmp/chromedriver_linux64.zip "${CHROMEDRIVER_URL}"
if [ $? -ne 0 ]; then
    echo "INSTALL_SCRIPT: FATAL ERROR - Chromedriver download failed. Check URL (${CHROMEDRIVER_URL}) and network."
    exit 1
fi

echo "INSTALL_SCRIPT: Unzipping Chromedriver to /tmp/chromedriver_extracted_temp..."
# Using sudo because /usr/local/bin is system-owned. Unzip to a temp location first.
sudo unzip -o /tmp/chromedriver_linux64.zip -d /tmp/chromedriver_extracted_temp
if [ $? -ne 0 ]; then
    echo "INSTALL_SCRIPT: FATAL ERROR - Chromedriver unzip failed."
    echo "INSTALL_SCRIPT: Listing /tmp contents:"
    sudo ls -l /tmp # List /tmp content for debugging
    exit 1
fi

echo "INSTALL_SCRIPT: Searching for chromedriver executable in extracted files..."
# Find the chromedriver executable, robust to it being in a subdirectory (like chromedriver-linux64) or at the root
CHROME_DRIVER_EXECUTABLE_PATH=$(sudo find /tmp/chromedriver_extracted_temp -name chromedriver -type f -print -quit)

if [ -n "${CHROME_DRIVER_EXECUTABLE_PATH}" ]; then
    echo "INSTALL_SCRIPT: Found chromedriver executable at ${CHROME_DRIVER_EXECUTABLE_PATH}"
    echo "INSTALL_SCRIPT: Moving to /usr/local/bin/chromedriver and setting permissions..."
    sudo mv "${CHROME_DRIVER_EXECUTABLE_PATH}" /usr/local/bin/chromedriver
    sudo chmod +x /usr/local/bin/chromedriver
    echo "INSTALL_SCRIPT: Chromedriver moved and permissions set."
else
    echo "INSTALL_SCRIPT: FATAL ERROR - chromedriver executable NOT FOUND in extracted files!"
    echo "INSTALL_SCRIPT: Listing contents of /tmp/chromedriver_extracted_temp/ for debugging:"
    sudo ls -lR /tmp/chromedriver_extracted_temp
    exit 1
fi

# Clean up
rm -rf /tmp/chromedriver_extracted_temp /tmp/chromedriver_linux64.zip

echo "INSTALL_SCRIPT: Chromedriver manual installation process complete. Verifying installation:"
# This verification is crucial. It should print the version of the manually installed chromedriver.
/usr/local/bin/chromedriver --version