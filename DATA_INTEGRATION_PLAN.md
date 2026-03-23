# ORCESTRA Data Integration Plan

**Status**: Configuration ready, data expansion in progress

**Last Updated**: Mar 19, 2026

---

## 📊 Current Data Status

### ✅ Dropsonde Data
- **Location**: `/g/data/k10/zr7147/ORCESTRA_dropsondes_categorized.zarr`
- **Status**: READY ✓
- **Size**: ~43.8 MB
- **Circles**: 89 total (62 dynamic: Top-Heavy + Bottom-Heavy)
- **Time coverage**: Aug 10 - Sep 30, 2024
- **Rendering**: Data IS visible in plots (panel left)

### ⚠️ IMERG Data
- **Location**: `/g/data/k10/zr7147/ORCESTRA_IMERG_Combined_Cropped.nc`
- **Status**: READY but domain too narrow
- **Current domain**: 5°N - 19.95°N, 65°W - 15°W
- **Required domain**: 0°N - 30°N, 70°W - 0°W (per SPEC)
- **Current size**: 482.8 MB
- **Estimated size after expansion**: ~1.3 GB

### ❌ EarthCARE Data
- **Location**: `/g/data/k10/zr7147/EarthCARE_Data/`
- **Status**: DIRECTORY CREATED - AWAITING DOWNLOAD
- **Requirement**: Must download from G-Portal

---

## 🔧 STEP 1: Re-process IMERG Data with Wider Domain

### Action
Run satellite preprocessing with updated configuration:

```bash
cd /home/565/zr7147/Proj

# Activate conda environment
source /g/data/k10/zr7147/miniconda3/etc/profile.d/conda.sh
conda activate /g/data/k10/zr7147/orcestra_env

# OPTION 1: Use default config (0-30°N, 70-0°W - already set)
python scripts/satellite_preprocessing.py

# OPTION 2: Override with env vars
export ORCESTRA_LAT_MIN=0
export ORCESTRA_LAT_MAX=30
export ORCESTRA_LON_MIN=-70
export ORCESTRA_LON_MAX=0
python scripts/satellite_preprocessing.py

# OPTION 3: Command-line args
python scripts/satellite_preprocessing.py \
  --lat-min 0 \
  --lat-max 30 \
  --lon-min -70 \
  --lon-max 0
```

### Expected Output
- **File**: `ORCESTRA_IMERG_Combined_Cropped.nc`
- **Size**: ~1.3 GB (larger than current 482.8 MB)
- **Dimensions**: 
  - Latitude: ~302 points (0°N - 30°N)
  - Longitude: ~700 points (70°W - 0°W)  
  - Time: 2496 timesteps
- **Processing time**: ~3-5 minutes

### Verification
```python
import xarray as xr
ds = xr.open_dataset('/g/data/k10/zr7147/ORCESTRA_IMERG_Combined_Cropped.nc')
print(f"Lat: {float(ds.lat.min()):.2f}° to {float(ds.lat.max()):.2f}°N")
print(f"Lon: {float(ds.lon.min()):.2f}° to {float(ds.lon.max()):.2f}°W")
ds.close()
```

---

## 🛰️ STEP 2: EarthCARE Data Integration

### Prerequisites
- G-Portal account (from JAXA)
- G-Portal credentials ready

### Files Needed
Download from G-Portal to `/g/data/k10/zr7147/EarthCARE_Data/`:
- Level 2B Precipitation (['CPR', 'MSI', 'MWRI'] products)
- Date range: Aug 10 - Sep 30, 2024
- Spatial domain: 0°N - 30°N, 70°W - 0°W

### Preprocessing Steps

```bash
# Edit credentials in config.py
vim /home/565/zr7147/Proj/scripts/config.py
# Add: EARTHCARE_USERNAME, EARTHCARE_PASSWORD

# Run EarthCARE preprocessing
cd /home/565/zr7147/Proj
conda activate /g/data/k10/zr7147/orcestra_env
python scripts/earthcare_preprocessing.py
```

### Expected Output
- **File**: `ORCESTRA_EarthCARE_Combined_Cropped.nc`
- **Structure**: Same as IMERG (standardized to NetCDF)
- **Variables**: precipitation (mm/hr), lat, lon, time
- **Size**: Depends on data availability

---

## 📈 STEP 3: Regenerate Comparison Plots

### After IMERG expansion:

```bash
cd /home/565/zr7147/Proj
conda activate /g/data/k10/zr7147/orcestra_env

# Regenerate with IMERG only (expanded domain)
python scripts/comparison_plotting.py \
  --dropsonde /g/data/k10/zr7147/ORCESTRA_dropsondes_categorized.zarr \
  --categories /g/data/k10/zr7147/ORCESTRA_dropsondes_categories.csv \
  --imerg /g/data/k10/zr7147/ORCESTRA_IMERG_Combined_Cropped.nc \
  --filter-categories "Top-Heavy" "Bottom-Heavy"

# Expected: More circles can now be plotted (especially low-latitude circles)
```

### After EarthCARE download:

```bash
# Regenerate with both IMERG and EarthCARE
python scripts/comparison_plotting.py \
  --dropsonde /g/data/k10/zr7147/ORCESTRA_dropsondes_categorized.zarr \
  --categories /g/data/k10/zr7147/ORCESTRA_dropsondes_categories.csv \
  --imerg /g/data/k10/zr7147/ORCESTRA_IMERG_Combined_Cropped.nc \
  --earthcare /g/data/k10/zr7147/ORCESTRA_EarthCARE_Combined_Cropped.nc \
  --filter-categories "Top-Heavy" "Bottom-Heavy"

# Expected: 3-panel figures with EarthCARE on bottom-right
```

---

## 📋 Configuration Reference

### Current config.py Settings

```python
def default_imerg_bbox() -> BoundingBox:
    """IMERG domain: 0°N-30°N, 70°W-0°W"""
    return BoundingBox(
        lat_min=0.0,      # Can override: ORCESTRA_LAT_MIN
        lat_max=30.0,     # Can override: ORCESTRA_LAT_MAX
        lon_min=-70.0,    # Can override: ORCESTRA_LON_MIN
        lon_max=0.0,      # Can override: ORCESTRA_LON_MAX
    )

def default_earthcare_bbox() -> BoundingBox:
    """EarthCARE domain: same as IMERG"""
    return default_imerg_bbox()

def earthcare_credentials() -> dict:
    return {
        "username": os.environ.get("EARTHCARE_USERNAME", "YOUR_USERNAME"),
        "password": os.environ.get("EARTHCARE_PASSWORD", "YOUR_PASSWORD"),
        "gportal_url": os.environ.get("EARTHCARE_GPORTAL_URL", "https://gportal.jaxa.jp/gw/"),
    }
```

### Environment Variable Overrides

```bash
# IMERG domain
export ORCESTRA_LAT_MIN=0
export ORCESTRA_LAT_MAX=30
export ORCESTRA_LON_MIN=-70
export ORCESTRA_LON_MAX=0

# EarthCARE credentials
export EARTHCARE_USERNAME="your_username"
export EARTHCARE_PASSWORD="your_password"
export EARTHCARE_GPORTAL_URL="https://gportal.jaxa.jp/gw/"
```

---

## ✅ Checklist for Complete Integration

- [ ] Re-process IMERG with domain 0-30°N, 70-0°W
- [ ] Verify new ORCESTRA_IMERG_Combined_Cropped.nc file (~1.3 GB)
- [ ] Regenerate plots with expanded IMERG data
- [ ] Verify 60+ plots (potentially more circles working)
- [ ] Obtain G-Portal account credentials
- [ ] Download EarthCARE data to `/g/data/k10/zr7147/EarthCARE_Data/`
- [ ] Edit config.py with EarthCARE credentials
- [ ] Run earthcare_preprocessing.py
- [ ] Regenerate plots with both IMERG + EarthCARE (3-panel)
- [ ] Verify final figure quality and SPEC compliance

---

## 📁 Data Directory Structure

```
/g/data/k10/zr7147/
├── GPM_IMERG_Data/                         (Raw HDF5 files, 18.9 GB)
│   └── 3B-HHR.MS.MRG.3IMERG.*.HDF5        (2,496 files)
├── ORCESTRA_IMERG_Combined_Cropped.nc     (Current: 482.8 MB → New: ~1.3 GB)
├── EarthCARE_Data/                         (For downloaded files)
│   └── [EarthCARE L2B products]
├── ORCESTRA_EarthCARE_Combined_Cropped.nc (Awaiting data)
├── ORCESTRA_dropsondes_categorized.zarr   (✓ Ready)
└── ORCESTRA_dropsondes_categories.csv     (✓ Ready)
```

---

## 🚀 Quick Start Commands

### Re-process IMERG (wider domain)
```bash
cd /home/565/zr7147/Proj
source /g/data/k10/zr7147/miniconda3/etc/profile.d/conda.sh
conda activate /g/data/k10/zr7147/orcestra_env
python scripts/satellite_preprocessing.py
```

### Regenerate plots (IMERG only)
```bash
python scripts/comparison_plotting.py
```

### Regenerate plots (IMERG + EarthCARE - after data available)
```bash
python scripts/comparison_plotting.py \
  --earthcare /g/data/k10/zr7147/ORCESTRA_EarthCARE_Combined_Cropped.nc
```

---

**Next Action**: Run IMERG re-processing with expanded domain (0-30°N, 70-0°W)
