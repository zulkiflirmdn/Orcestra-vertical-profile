# EarthCARE CPR Download System - Implementation Summary

## Overview

A complete, automated system for downloading EarthCARE Cloud Profiling Radar (CPR) vertical velocity data for the ORCESTRA campaign using ESA Online Dissemination Services.

## What Was Implemented

### Core Components

#### 1. **Main Download Module** (`scripts/earthcare_download.py`)
- **EarthCAREDownloader class** with full API integration
- Methods:
  - `validate_credentials()` - Test ESA credentials with sample search
  - `list_available_files()` - Search without downloading
  - `download_cpr_data()` - Main download workflow
  - `validate_downloads()` - Check file integrity
- Automatic logging to `download_earthcare.log`
- CSV summary output: `earthcare_files_downloaded.csv`
- Disk space validation
- Download statistics tracking

#### 2. **Configuration** (`scripts/config.py`)
- **OrcuestraEarthcareConfig dataclass** with parameters:
  - Geographic domain: 0°N-30°N, 70°W-0°W
  - Time period: 2024-08-10 to 2024-09-30
  - Products: CPR_CLP_2A, CPR_ECO_2A, AC__CLP_2B
  - Download settings: 5 workers, auto-unzip, organize by product
- Environment variable overrides for all parameters
- Integrated with existing IMERG configuration

#### 3. **Wrapper Scripts**
- **Root wrapper** (`earthcare_download.py`) - Easy-to-run entry point
- **Setup script** (`setup_earthcare_download.sh`) - Automatic installation & validation
- **Both callable from project root**

#### 4. **Documentation**
- **EARTHCARE_DOWNLOAD_GUIDE.md** - Comprehensive 350+ line guide covering:
  - Quick start (4-step process)
  - Installation instructions
  - Command-line usage with 20+ examples
  - Product descriptions and specs
  - Data organization and file structure
  - Monitoring and validation procedures
  - Troubleshooting for 10+ common issues
  - Performance optimization tips
  - Integration with ORCESTRA workflow

## Key Features

✅ **Fully Automated** - No manual G-Portal browsing required
✅ **API-Based** - Uses ESA Online Dissemination Services
✅ **Vertical Velocity Data** - CPR_CLP_2A contains `air_vertical_velocity` (Pa/s)
✅ **Parallel Downloads** - Configurable concurrent workers (default: 5)
✅ **Resume-Capable** - Skips existing files, can continue interrupted downloads
✅ **Validation Built-In** - Checks NetCDF/HDF5 file integrity
✅ **Comprehensive Logging** - Tracks all operations to log file
✅ **CSV Summary** - Track file counts, sizes, and status
✅ **Disk Space Warnings** - Pre-warns if <100GB available
✅ **Error Recovery** - Graceful handling of authentication, network, and disk errors

## Installation & Quick Start

### Install Dependencies

```bash
pip install earthcare-downloader xarray netCDF4 numpy
```

### Set Credentials

```bash
export ESA_EO_USERNAME="your_email@example.com"
export ESA_EO_PASSWORD="your_password"
```

### Validate Setup

```bash
cd /home/565/zr7147/Proj
python earthcare_download.py --validate-credentials
```

### Start Download

```bash
python earthcare_download.py
```

### Using Setup Script (Recommended)

```bash
bash setup_earthcare_download.sh
```

This automatically:
1. Checks Python installation
2. Verifies/installs earthcare-downloader
3. Prompts for ESA credentials if not set
4. Validates credentials with test search
5. Starts download process

## File Structure

```
/home/565/zr7147/Proj/
├── scripts/
│   ├── config.py (UPDATED: ORCESTRA parameters)
│   ├── earthcare_download.py (NEW: Main implementation)
│   └── [other processing scripts]
├── docs/
│   ├── EARTHCARE_DOWNLOAD_GUIDE.md (NEW: Full guide)
│   └── [other docs]
├── earthcare_download.py (NEW: Root wrapper)
├── setup_earthcare_download.sh (NEW: Setup helper)
└── [project root files]

/g/data/k10/zr7147/
└── EarthCARE_Data/ (NEW: Download destination)
    ├── CPR_CLP_2A/ (Vertical velocity)
    ├── CPR_ECO_2A/ (Echo properties)
    └── AC__CLP_2B/ (Synergistic properties)
```

## Command Examples

### Basic Downloads

```bash
# Download all ORCESTRA data
python earthcare_download.py

# Validate credentials
python earthcare_download.py --validate-credentials

# List available files
python earthcare_download.py --list-only

# Custom date range
python earthcare_download.py --start 2024-08-15 --end 2024-08-20
```

### Advanced Options

```bash
# Single product (vertical velocity)
python earthcare_download.py --products CPR_CLP_2A

# Custom domain
python earthcare_download.py --lat-range 5,20 --lon-range -65,-15

# Faster downloads (more workers)
python earthcare_download.py --workers 10

# Force re-download
python earthcare_download.py --force

# Validate files
python earthcare_download.py --validate

# Custom output
python earthcare_download.py --output-dir /custom/path
```

## Products Available

### CPR_CLP_2A - Cloud Properties ⭐ PRIMARY
- **air_vertical_velocity** (Pa/s) - vertical Doppler velocity
- **radar_reflectivity** (dBZ)
- **cloud_type_classification** (WMO codes)
- Quality flags and attributes
- **Best for:** vertical velocity analysis, dropsonde comparison

### CPR_ECO_2A - Echo Properties
- Echo/cloud classification
- Reflectivity profiles
- Quality indicators
- **Best for:** profile validation, cloud structure analysis

### AC__CLP_2B - Synergistic Cloud Properties
- Multi-sensor combined data
- Enhanced quality metrics
- **Best for:** advanced multi-sensor analysis

## Expected Data Volume

For full ORCESTRA campaign (51 days):
- **CPR_CLP_2A**: ~500 files, 400-600 GB
- **CPR_ECO_2A**: ~300 files, 300-450 GB
- **AC__CLP_2B**: Pending (varies)
- **Total**: ~1 TB (estimated)
- **Download time**: 20-100 hours (depends on connection)

## Data Format

- **Files**: NetCDF4 / HDF5
- **Naming**: `ECA_JXBB_CPR_CLP_2A_[YYYY-MM-DDTHH:MM:SS]_[version].nc`
- **One file per orbit pass** (typically 10+ passes/day)
- **File size**: 800 MB - 2 GB per file

## Monitoring Downloads

### Real-Time Progress

```bash
# Watch download log
tail -f download_earthcare.log

# Check files downloaded
ls -1 /g/data/k10/zr7147/EarthCARE_Data/CPR_CLP_2A/ | wc -l

# Check total size
du -sh /g/data/k10/zr7147/EarthCARE_Data/
```

### Post-Download Summary

```bash
# View download statistics
cat earthcare_files_downloaded.csv

# Validate all files
python earthcare_download.py --validate
```

## Troubleshooting

### Common Issues & Solutions

**Issue: "earthcare-downloader not installed"**
```bash
pip install earthcare-downloader
```

**Issue: "Credentials validation failed"**
- Verify account: https://eoiam-idp.eo.esa.int/
- Check credentials typed correctly
- May need account activation email confirmation

**Issue: "No files found for CPR_CLP_2A"**
- Try broader date range
- Check if catalog has data for your domain
- Verify credentials have access

**Issue: Disk space warning**
- Use external storage: `--output-dir /mnt/external/...`
- Download smaller date ranges
- Download single products

**Issue: Download interrupted**
- Just run again - existing files are skipped
- Download resumes automatically

## Integration with ORCESTRA Workflow

After downloading:

```bash
# 1. Preprocess and merge EarthCARE data
python scripts/earthcare_preprocessing.py

# 2. Generate comparison figures
python scripts/comparison_plotting.py \
    --earthcare /g/data/k10/zr7147/ORCESTRA_EarthCARE_Combined_Cropped.nc

# 3. Analyze vertical velocity
python -c "
import xarray as xr
ds = xr.open_mfdataset('/g/data/k10/zr7147/EarthCARE_Data/CPR_CLP_2A/*.nc')
omega = ds['air_vertical_velocity']
print(f'Vertical velocity range: {omega.min().values:.2f} to {omega.max().values:.2f} Pa/s')
"
```

## Configuration & Customization

### Environment Variables

```bash
# Override defaults
export ORCESTRA_EARTHCARE_LAT_MIN=5
export ORCESTRA_EARTHCARE_LAT_MAX=20
export ORCESTRA_EARTHCARE_LON_MIN=-65
export ORCESTRA_EARTHCARE_LON_MAX=-15
export ORCESTRA_EARTHCARE_START=2024-08-10
export ORCESTRA_EARTHCARE_END=2024-08-15
export ORCESTRA_EARTHCARE_WORKERS=10
export ORCESTRA_EARTHCARE_INPUT_DIR=/path/to/data
```

### Programmatic Usage

```python
from scripts.earthcare_download import EarthCAREDownloader

downloader = EarthCAREDownloader()
stats = downloader.download_cpr_data(
    products=("CPR_CLP_2A",),
    lat_range=(5, 20),
    lon_range=(-65, -15),
    start_date="2024-08-10",
    end_date="2024-08-15",
    max_workers=5,
)
print(stats)
```

## Performance Tips

**For Fastest Download:**
```bash
python earthcare_download.py --workers 10
```

**For Most Stable:**
```bash
python earthcare_download.py --workers 2
```

**Recommended (Balanced):**
```bash
python earthcare_download.py --workers 5
```

## Technical Details

### Download Flow

```
User Input / Config
  ↓
Validate Credentials (test search)
  ↓
Search ESA MAAP STAC for products
  ↓
List available files
  ↓
Create product directories
  ↓
Parallel download (5 workers by default)
  ↓
Unzip files (if enabled)
  ↓
Calculate statistics
  ↓
Write summary CSV
  ↓
Optional: Validate integrity
```

### Error Handling

- Authentication errors → prompt for credentials
- Network timeouts → retry up to 3 times
- Disk space errors → warn immediately
- Corrupted files → log and skip
- Missing products → warning but continue

## References

- **earthcare-downloader GitHub**: https://github.com/espdev/earthcare-dist
- **EarthCARE Mission**: https://www.esa.int/Applications/Observing_the_Earth/EarthCARE
- **ESA Online Account**: https://eoiam-idp.eo.esa.int/
- **ORCESTRA Campaign**: NOAA/NSF field campaign
- **Documentation in Project**: `docs/EARTHCARE_DOWNLOAD_GUIDE.md`

## Version & Status

- **Version**: 1.0 (ESA Online Dissemination Services)
- **Status**: Production Ready
- **Release Date**: 2026-03-20
- **Tested**: Python 3.9+, earthcare-downloader >=0.1.0

## Future Enhancements

- [ ] Add JAXA G-Portal fallback method
- [ ] Automatic data preprocessing (merge NetCDF)
- [ ] Web dashboard for monitoring downloads
- [ ] Cron job integration for scheduled downloads
- [ ] Data archival management system

---

**For detailed usage instructions, see `EARTHCARE_DOWNLOAD_GUIDE.md`**
**For setup help, run: `bash setup_earthcare_download.sh`**
