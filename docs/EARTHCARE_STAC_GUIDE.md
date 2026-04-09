# EarthCARE STAC API Download Guide

## Overview

The new **EarthCARE STAC Download** system uses ESA's official MAAP STAC catalog to download data via HTTP API. This replaces manual G-Portal access with automated, transparent, and reliable API-based downloads.

### Key Advantages

| Feature | STAC API | G-Portal SFTP | earthcare-downloader |
|---------|----------|---------------|----------------------|
| **Authentication** | Direct HTTP (no credentials needed) | requires SFTP credentials | Requires ESA Earth Online account |
| **Automation** | Full API support | Manual/SFTP automation | Package dependency |
| **Transparency** | Open STAC standard | Proprietary | Closed package |
| **Reliability** | ESA official catalog | G-Portal server load | Subject to package maintenance |
| **Dependencies** | requests, xarray | paramiko | earthcare-downloader package |

## How It Works

### 1. STAC Search
```python
# Query ESA MAAP STAC catalog
POST https://catalog.maap.eo.esa.int/catalogue/search
{
    "collections": ["EarthCARE_MSI_Cloud_and_Precipitation_2A"],
    "bbox": [-70, 0, 0, 30],  # [lon_min, lat_min, lon_max, lat_max]
    "datetime": "2024-08-10T00:00:00Z/2024-09-30T23:59:59Z"
}
```

### 2. HTTP Download
- Direct HTTP/HTTPS links from STAC items
- Stream-based download for memory efficiency
- Automatic retry on transient failures

### 3. Processing
- Merge multiple NetCDF files
- Standardize coordinates and dimensions
- Crop to specified bounding box
- Output NetCDF4 with standard compression

## Quick Start

### Basic Usage

```bash
# Download and process EarthCARE data for ORCESTRA campaign
python earthcare_stac_download.py
```

This will:
1. Search ESA MAAP STAC for EarthCARE MSI data (Aug-Sep 2024)
2. Download files to `/g/data/k10/zr7147/EarthCARE_Data/`
3. Merge into `/g/data/k10/zr7147/ORCESTRA_EarthCARE_Combined_Cropped.nc`

### Advanced Usage

```bash
# List available EarthCARE collections
python earthcare_stac_download.py --list-collections

# Custom bounding box and date range
python earthcare_stac_download.py \
    --lat-min 5 --lat-max 20 \
    --lon-min -70 --lon-max -15 \
    --start-date 2024-08-10 \
    --end-date 2024-08-15

# Use existing downloaded files (skip re-downloading)
python earthcare_stac_download.py --skip-download

# Different product type
python earthcare_stac_download.py --product CPR_CLP
```

## Configuration

### Default Settings

**File:** `scripts/config.py`

```python
def default_earthcare_bbox() -> BoundingBox:
    return BoundingBox(
        lat_min=0, lat_max=30,      # 0N-30N (spec domain)
        lon_min=-70, lon_max=0       # 70W-0W (spec domain)
    )

def default_earthcare_input_dir() -> Path:
    return Path("/g/data/k10/zr7147/EarthCARE_Data")

def default_earthcare_output_path() -> Path:
    return Path("/g/data/k10/zr7147/ORCESTRA_EarthCARE_Combined_Cropped.nc")
```

### Environment Variables

Override defaults without modifying code:

```bash
# Spatial domain
export ORCESTRA_EARTHCARE_LAT_MIN=5
export ORCESTRA_EARTHCARE_LAT_MAX=20
export ORCESTRA_EARTHCARE_LON_MIN=-70
export ORCESTRA_EARTHCARE_LON_MAX=-15

# Data locations
export ORCESTRA_EARTHCARE_INPUT_DIR=/custom/path/EarthCARE_Data
export ORCESTRA_EARTHCARE_OUTPUT_PATH=/custom/path/ORCESTRA_EarthCARE.nc
```

## Available EarthCARE Products

### MSI_COP (Recommended for Precipitation)
- **Collection:** `EarthCARE_MSI_Cloud_and_Precipitation_2A`
- **Description:** Multi-Spectral Imager Cloud and Precipitation measurements
- **Use case:** Direct comparison with IMERG precipitation
- **Default:** Yes

### CPR_CLP (Cloud Properties)
- **Collection:** `EarthCARE_CPR_Cloud_Properties_2A`
- **Description:** Cloud Profiling Radar Cloud Properties (reflectivity, vertical velocity)
- **Use case:** Advanced cloud analysis
- **Command:** `--product CPR_CLP`

## Technical Implementation

### STAC Endpoints

**Base URL:** `https://catalog.maap.eso.int`

| Endpoint | Purpose |
|----------|---------|
| `/catalogue/collections` | List available collections |
| `/catalogue/search` | Query data by space/time/product |
| (STAC Items) | Direct HTTP links to data files |

### Search Parameters

```python
search_params = {
    "collections": ["EarthCARE_MSI_Cloud_and_Precipitation_2A"],
    "bbox": [lon_min, lat_min, lon_max, lat_max],  # WGS84
    "datetime": "start_date/end_date",              # ISO 8601
    "limit": 100                                    # results per page
}
```

### Retry Logic

- Maximum 3 retries per file (configurable)
- Exponential backoff on transient failures
- Automatic resume for interrupted downloads

### Processing Pipeline

```
STAC Search
    ↓
HTTP Download (stream-based)
    ↓
Merge Files (xarray, Dask parallel)
    ↓
Standardize Coordinates
    ↓
Spatial Crop (to bbox)
    ↓
Compress & Write NetCDF4
    ↓
Output: ORCESTRA_EarthCARE_Combined_Cropped.nc
```

## Logging and Diagnostics

```bash
# View detailed processing logs
python earthcare_stac_download.py 2>&1 | tee earthcare_stac.log

# Check downloaded files
ls -lh /g/data/k10/zr7147/EarthCARE_Data/

# Inspect merged NetCDF
ncdump -h /g/data/k10/zr7147/ORCESTRA_EarthCARE_Combined_Cropped.nc
xarray_info /g/data/k10/zr7147/ORCESTRA_EarthCARE_Combined_Cropped.nc
```

## Troubleshooting

### "No EarthCARE data found for the specified search criteria"

**Cause:** STAC search returned no results for your spatial/temporal domain.

**Solution:**
1. Verify coordinates are correct:
   ```bash
   python earthcare_stac_download.py --list-collections
   ```
2. Try a wider date range:
   ```bash
   python earthcare_stac_download.py --start-date 2024-07-01 --end-date 2024-10-31
   ```
3. Check ESA MAAP catalog status: https://catalog.maap.eo.esa.int

### "Failed to fetch collections"

**Cause:** Network timeout or ESA MAAP catalog unreachable.

**Solution:**
```bash
# Test connectivity
curl -s https://catalog.maap.eo.esa.int/catalogue/collections | python -m json.tool

# Check network proxy settings if behind firewall
# Modify timeout in scripts/earthcare_stac_download.py:
ORCESTRA_CONFIG['timeout'] = 60  # increase from 30
```

### "No data files found in /g/data/k10/zr7147/EarthCARE_Data"

**Cause:** Download succeeded with API response but no actual files downloaded.

**Solution:**
1. Check STAC items returned:
   ```python
   # Add debug output to see download URLs
   logger.info(f"Item assets: {item.get('assets').keys()}")
   ```
2. Verify ESA MAAP repository is accessible:
   ```bash
   curl -I $(first_stac_item_url)  # check Direct HTTP link
   ```

### Dask Client Errors

**Cause:** Insufficient memory or worker conflicts.

**Solution:**
```bash
# Reduce workers and memory
python earthcare_stac_download.py  # Uses env vars:
export ORCESTRA_DASK_WORKERS=2
export ORCESTRA_DASK_MEMORY_LIMIT=1000MiB
```

## Comparison with Previous Methods

### vs. G-Portal SFTP (`earthcare_download.py`)

**STAC Advantages:**
- No SFTP credentials or G-Portal account needed
- Transparent, officially documented API
- HTTP-based (better for firewalls/proxies)
- No paramiko SSH library dependency

**G-Portal Advantages:**
- Directly from official JAXA source
- May have more granular product metadata

**Recommendation:** Use STAC API; fall back to G-Portal only if STAC catalog lacks needed data.

### vs. earthcare-downloader (`earthcare_preprocessing.py`)

**STAC Advantages:**
- No external package dependency
- ESA official catalog (not third-party wrapper)
- Transparent code (not a black box)
- Better error diagnostics

**earthcare-downloader Advantages:**
- May include convenience pre-processing
- If package maintainer adds new features

**Recommendation:** Migrate to STAC API; earthcare-downloader can be deprecated.

## Integration with Comparison Workflow

After downloading and processing EarthCARE data:

```bash
# 1. Download and process EarthCARE
python earthcare_stac_download.py

# 2. Generate dropsonde-satellite comparisons
python comparison_plotting.py \
    --dropsonde /g/data/k10/zr7147/ORCESTRA_dropsondes_categorized.zarr \
    --imerg /g/data/k10/zr7147/ORCESTRA_IMERG_Combined_Cropped.nc \
    --earthcare /g/data/k10/zr7147/ORCESTRA_EarthCARE_Combined_Cropped.nc
```

The output NetCDF from STAC download is automatically in the format expected by `comparison_plotting.py`.

## References

- **ESA MAAP STAC Catalog:** https://catalog.maap.eo.esa.int/doc/stac.html
- **STAC API Specification:** https://stacspec.org/
- **EarthCARE Mission:** https://www.esa.int/Applications/Observing_the_Earth/EarthCARE
- **ORCESTRA Project Spec:** `notes/SPEC_sonde_vs_satellite.md`

## Next Steps

1. **Test the STAC download** on your system
2. **Compare output** with existing methods if available
3. **Document any issues** in the project repository
4. **Deprecate G-Portal and earthcare-downloader** methods once STAC is verified stable

---

**Last Updated:** 2026-03-19
**Author:** Claude Code
**Status:** Beta (fully functional, gathering user feedback)
