# EarthCARE CPR Vertical Velocity Download Guide

## Overview

This guide explains how to download EarthCARE Cloud Profiling Radar (CPR) vertical velocity data for the ORCESTRA campaign using the **ESA Online Dissemination Services** via the `earthcare-downloader` package.

### Key Features

✅ **No Manual G-Portal Browsing** - Fully automated API-based download
✅ **Vertical Velocity Data** - CPR_CLP_2A product contains `air_vertical_velocity`
✅ **Parallel Downloads** - Download multiple files concurrently
✅ **Resume Support** - Skip existing files, continue interrupted downloads
✅ **Integrated Logging** - Track all downloads and errors to `download_earthcare.log`
✅ **Validation** - Check file integrity after download

## Quick Start

### 1. Install Required Package

```bash
pip install earthcare-downloader xarray netCDF4 numpy
```

### 2. Create ESA Online Account

Visit: https://eoiam-idp.eo.esa.int/ and register for a free account.

### 3. Set Credentials

```bash
export ESA_EO_USERNAME="your_email@example.com"
export ESA_EO_PASSWORD="your_password"
```

Or add to your `.bashrc` or `.zshrc` for permanent configuration.

### 4. Download ORCESTRA Data

```bash
cd /home/565/zr7147/Proj
python earthcare_download.py
```

This downloads all available data for:
- **Domain**: 0°N-30°N, 70°W-0°W
- **Period**: 2024-08-10 to 2024-09-30
- **Products**: CPR_CLP_2A, CPR_ECO_2A, AC__CLP_2B

## Installation & Setup

### Full Setup Instructions

```bash
# 1. Create/activate conda environment (if needed)
conda create -n earthcare python=3.10
conda activate earthcare

# 2. Install earthcare-downloader
pip install earthcare-downloader

# 3. Install supporting packages
pip install xarray netCDF4 numpy

# 4. Create ESA Online account
# Go to: https://eoiam-idp.eo.esa.int/
# Register with your email

# 5. Set environment variables (make permanent in ~/.bashrc)
export ESA_EO_USERNAME="your_email@example.com"
export ESA_EO_PASSWORD="your_password"

# 6. Verify credentials work
cd /home/565/zr7147/Proj
python earthcare_download.py --validate-credentials
```

### Troubleshooting Installation

**Error: "earthcare-downloader not installed"**
```bash
pip install --upgrade earthcare-downloader
pip install -U xarray netCDF4
```

**Error: "No module named 'requests' or 'h5py'"**
```bash
pip install requests h5py
```

**Error: "ESA credentials not found"**
```bash
# Check credentials are set
echo $ESA_EO_USERNAME
echo $ESA_EO_PASSWORD

# If empty, add to ~/.bashrc
export ESA_EO_USERNAME="your_email@example.com"
export ESA_EO_PASSWORD="your_password"
source ~/.bashrc
```

## Command-Line Usage

### Basic Syntax

```bash
python earthcare_download.py [OPTIONS]
```

### Common Options

```bash
# Validate credentials (test-download single day)
python earthcare_download.py --validate-credentials

# List available files without downloading
python earthcare_download.py --list-only

# Control date range
python earthcare_download.py --start 2024-08-15 --end 2024-08-20

# Custom geographic domain
python earthcare_download.py --lat-range 5,20 --lon-range -65,-15

# Download single product (CPR_CLP_2A has vertical velocity)
python earthcare_download.py --products CPR_CLP_2A

# Parallel workers (higher = faster but may be unstable)
python earthcare_download.py --workers 10

# Force re-download existing files
python earthcare_download.py --force

# Validate all downloaded files after download
python earthcare_download.py --validate

# Custom output directory
python earthcare_download.py --output-dir /custom/path/EarthCARE_Data
```

### Examples

```bash
# Download all ORCESTRA data (default, ~51 days)
python earthcare_download.py

# Download August 10-15 only
python earthcare_download.py --start 2024-08-10 --end 2024-08-15

# Download narrow region (narrower than ORCESTRA domain)
python earthcare_download.py --lat-range 10,25 --lon-range -60,-30

# Download CPR_CLP_2A only (vertical velocity) with 10 workers
python earthcare_download.py --products CPR_CLP_2A --workers 10

# Download all products with validation
python earthcare_download.py --validate

# Re-download files with force flag
python earthcare_download.py --force --output-dir /g/data/k10/zr7147/EarthCARE_Data_NEW
```

## EarthCARE Products

### CPR_CLP_2A (Cloud Properties) ⭐ PRIMARY

**Contains vertical velocity data:**
- `air_vertical_velocity` (Pa/s) - **w** parameter
- `radar_reflectivity` (dBZ)
- `cloud_type_classification` (WMO codes)
- Quality flags

**Use for:** Dropsonde vertical velocity comparison

### CPR_ECO_2A (Echo Properties)

**Contains:**
- Echo classification
- Reflectivity profiles
- Quality indicators

**Use for:** Cross-validation, cloud type analysis

### AC__CLP_2B (Synergistic Cloud Properties)

**Contains:**
- Multi-sensor combined properties
- Enhanced quality metrics
- Synergistic cloud classification

**Use for:** Advanced analysis, multi-sensor comparison

## Data Organization

### Directory Structure After Download

```
/g/data/k10/zr7147/
├── EarthCARE_Data/
│   ├── CPR_CLP_2A/
│   │   ├── ECA_JXBB_CPR_CLP_2A_2024-08-10T*.nc
│   │   ├── ECA_JXBB_CPR_CLP_2A_2024-08-11T*.nc
│   │   └── ... (one file per orbit pass)
│   ├── CPR_ECO_2A/
│   │   └── ... (echo properties files)
│   └── AC__CLP_2B/
│       └── ... (synergistic properties files)
```

### File Naming Convention

```
ECA_JXBB_CPR_CLP_2A_[YYYY-MM-DDTHH:MM:SS]_[version]_[collection].nc
```

Example: `ECA_JXBB_CPR_CLP_2A_2024-08-10T14:32:15_r00000_c00105.nc`

## Monitoring Downloads

### Real-Time Progress

The downloader prints progress for each file:

```
  ↓ ECA_JXBB_CPR_CLP_2A_2024-08-10T14:32:15_r00000_c00105.nc (847.3 MB)... ✓
  ↓ ECA_JXBB_CPR_CLP_2A_2024-08-10T15:45:22_r00001_c00106.nc (923.5 MB)... ✓
```

### Log Files

```bash
# Main download log
tail -f download_earthcare.log

# Summary CSV with file counts and sizes
cat earthcare_files_downloaded.csv
```

### Check Download Status

```bash
# Count files downloaded per product
ls -1 /g/data/k10/zr7147/EarthCARE_Data/CPR_CLP_2A/*.nc | wc -l

# Total size of downloaded data
du -sh /g/data/k10/zr7147/EarthCARE_Data/

# Check file sizes
ls -lh /g/data/k10/zr7147/EarthCARE_Data/CPR_CLP_2A/ | head -20
```

## Data Validation

### Automatic Validation

```bash
python earthcare_download.py --validate
```

This checks:
- File integrity (NetCDF4/HDF5 headers readable)
- Minimum file size (>1 MB)
- Dataset structure and variables

### Manual Validation

```bash
# Check file structure
ncdump -h /g/data/k10/zr7147/EarthCARE_Data/CPR_CLP_2A/*.nc | head -50

# List available variables
python -c "
import xarray as xr
ds = xr.open_dataset('/g/data/k10/zr7147/EarthCARE_Data/CPR_CLP_2A/[filename].nc')
print(ds)
"

# Check vertical velocity data exists
python -c "
import xarray as xr
ds = xr.open_dataset('/g/data/k10/zr7147/EarthCARE_Data/CPR_CLP_2A/[filename].nc')
print(ds['air_vertical_velocity'])
"
```

## Advanced Configuration

### Environment Variables for Download Tuning

```bash
# Set number of workers (concurrent downloads)
export ORCESTRA_EARTHCARE_WORKERS=10

# Force re-download
export ORCESTRA_EARTHCARE_FORCE=true

# Auto-unzip downloaded files
export ORCESTRA_EARTHCARE_UNZIP=true

# Custom output directory
export ORCESTRA_EARTHCARE_INPUT_DIR=/g/data/k10/zr7147/EarthCARE_Data

# Custom start/end dates
export ORCESTRA_EARTHCARE_START=2024-08-15
export ORCESTRA_EARTHCARE_END=2024-08-20
```

### Example with Environment Variables

```bash
# Download with custom settings
export ESA_EO_USERNAME="user@example.com"
export ESA_EO_PASSWORD="password"
export ORCESTRA_EARTHCARE_WORKERS=5
export ORCESTRA_EARTHCARE_INPUT_DIR=/g/data/k10/zr7147/EarthCARE_Data_v2

python earthcare_download.py --start 2024-08-10 --end 2024-08-15
```

## Troubleshooting

### "Credential validation failed"

**Cause:** ESA Online credentials are incorrect or account doesn't exist.

**Solution:**
1. Verify account: https://eoiam-idp.eo.esa.int/
2. Test credentials:
   ```bash
   python -c "from earthcare_downloader import search; search(product='CPR_CLP_2A', start='2024-08-10', stop='2024-08-11', lat_range=(0,30), lon_range=(-70,0))"
   ```
3. If error, check if account needs approval (check email)

### "No files found for CPR_CLP_2A"

**Cause:** Either no data exists for your domain/dates, or your credentials don't have access.

**Solution:**
1. Try broader date range:
   ```bash
   python earthcare_download.py --start 2024-07-01 --end 2024-10-31
   ```
2. Test with default ORCESTRA domain:
   ```bash
   python earthcare_download.py --list-only
   ```
3. Check ESA MAAP catalog status: https://catalog.maap.eo.esa.int/

### Download Speed is Slow

**Cause:** Network bandwidth or ESA server load.

**Solutions:**
1. Reduce workers to avoid congestion:
   ```bash
   python earthcare_download.py --workers 2
   ```
2. Download smaller date range first
3. Try during off-peak hours

### "Disk space" warning

**Cause:** Insufficient space for full download (~400-1000 GB for ORCESTRA).

**Expected sizes:**
- CPR_CLP_2A: ~500 files, 400-600 GB
- CPR_ECO_2A: ~300 files, 300-450 GB
- AC__CLP_2B: pending

**Solutions:**
1. Use external storage: `--output-dir /mnt/external/EarthCARE_Data`
2. Download partial data: `--start 2024-08-10 --end 2024-08-20`
3. Download single product: `--products CPR_CLP_2A`

### Download Interrupted/Needs Resume

The downloader automatically skips existing files:

```bash
# Continue from where it left off
python earthcare_download.py

# Files already downloaded won't be re-fetched
# New files will be added
```

## Performance Tips

### Optimal Settings for Different Scenarios

**Fastest (requires stable connection):**
```bash
python earthcare_download.py --workers 10
```

**Most Stable:**
```bash
python earthcare_download.py --workers 2
```

**Balanced (recommended):**
```bash
python earthcare_download.py --workers 5
```

### Network Optimization

```bash
# For systems behind proxy
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
python earthcare_download.py
```

## Integration with ORCESTRA Workflow

### After Downloading

1. **Merge and preprocess EarthCARE data:**
   ```bash
   python scripts/earthcare_preprocessing.py
   ```

2. **Generate comparison figures:**
   ```bash
   python scripts/comparison_plotting.py \
       --earthcare /g/data/k10/zr7147/ORCESTRA_EarthCARE_Combined_Cropped.nc
   ```

3. **Analyze vertical velocity:**
   ```python
   import xarray as xr

   # Load CPR vertical velocity
   ds = xr.open_mfdataset(
       '/g/data/k10/zr7147/EarthCARE_Data/CPR_CLP_2A/*.nc',
       combine='by_coords'
   )

   omega = ds['air_vertical_velocity']  # Pa/s
   print(f"Vertical velocity range: {omega.min().values:.2f} to {omega.max().values:.2f} Pa/s")
   ```

## Reference

- **earthcare-downloader GitHub:** https://github.com/espdev/earthcare-dist
- **EarthCARE Mission:** https://www.esa.int/Applications/Observing_the_Earth/EarthCARE
- **ESA Online Account:** https://eoiam-idp.eo.esa.int/
- **ORCESTRA Campaign:** NOAA/NSF field campaign Aug-Sep 2024

## Support

For issues or questions:

1. Check this guide's troubleshooting section
2. Review `download_earthcare.log` for detailed error messages
3. Consult `earthcare_files_downloaded.csv` for download summary
4. See `scripts/earthcare_download.py` for implementation details

---

**Last Updated:** 2026-03-19
**Status:** Production Ready
**Version:** 1.0 (ESA Online Dissemination Services)
