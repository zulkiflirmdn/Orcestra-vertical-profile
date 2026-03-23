#!/bin/bash
# Quick-start setup script for EarthCARE downloader
# Validates installation and starts download process

echo "════════════════════════════════════════════════════════════════════"
echo "EarthCARE CPR Downloader - ORCESTRA Campaign Setup"
echo "════════════════════════════════════════════════════════════════════"
echo

# 1. Check Python installation
echo "[1/5] Checking Python..."
if ! command -v python &> /dev/null; then
    echo "✗ Python not found. Install with: conda install python=3.10"
    exit 1
fi
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo "✓ Python $PYTHON_VERSION found"
echo

# 2. Check earthcare-downloader installation
echo "[2/5] Checking earthcare-downloader..."
if ! python -c "import earthcare_downloader" 2>/dev/null; then
    echo "✗ earthcare-downloader not installed"
    echo "  Install with: pip install earthcare-downloader"
    read -p "  Install now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pip install earthcare-downloader xarray netCDF4 numpy
        echo "✓ Installation complete"
    else
        exit 1
    fi
else
    echo "✓ earthcare-downloader installed"
fi
echo

# 3. Check ESA credentials
echo "[3/5] Checking ESA credentials..."
if [[ -z "$ESA_EO_USERNAME" ]] || [[ -z "$ESA_EO_PASSWORD" ]]; then
    echo "✗ ESA credentials not set"
    echo
    echo "  Set with:"
    echo "    export ESA_EO_USERNAME='your_email@example.com'"
    echo "    export ESA_EO_PASSWORD='your_password'"
    echo
    read -p "  Enter ESA username: " username
    read -sp "  Enter ESA password: " password
    echo
    export ESA_EO_USERNAME="$username"
    export ESA_EO_PASSWORD="$password"
    echo "✓ Credentials set for this session"
else
    echo "✓ ESA credentials found"
fi
echo

# 4. Validate credentials
echo "[4/5] Validating ESA credentials..."
cd /home/565/zr7147/Proj
if python earthcare_download.py --validate-credentials 2>&1 | grep -q "Credentials valid"; then
    echo "✓ Credentials valid"
else
    echo "✗ Credential validation failed"
    echo "  Check your ESA Online account: https://eoiam-idp.eo.esa.int/"
    exit 1
fi
echo

# 5. Start download
echo "[5/5] Starting EarthCARE download..."
echo "════════════════════════════════════════════════════════════════════"
echo

read -p "Start download of ORCESTRA data (Aug 10 - Sep 30, 2024)? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python earthcare_download.py
else
    echo "Download cancelled. You can start manually with:"
    echo "  python earthcare_download.py"
fi
