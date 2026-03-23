# ORCESTRA Satellite Data Download Guide

This guide explains how to download IMERG and EarthCARE satellite precipitation data for the ORCESTRA campaign.

## Quick Start

### IMERG (NASA Earthdata)

```bash
# From project root
cd /home/565/zr7147/Proj

# Download using default configuration (0N-30N, 70W-0W, Aug 10-Sep 30 2024)
python imerg_download.py

# Or with custom bounding box
python imerg_download.py --lat-min 5 --lat-max 20 --lon-min -65 --lon-max -15
```

### EarthCARE (G-Portal)

```bash
# From project root
cd /home/565/zr7147/Proj

# First, update credentials in scripts/config.py
# Then download:
python earthcare_download.py
```

## Configuration

Both download scripts use settings from `scripts/config.py`:

### IMERG Configuration
```python
def default_imerg_bbox() -> BoundingBox:
    # Default: 0N-30N, 70W-0W
    return BoundingBox(
        lat_min=0.0, lat_max=30.0,
        lon_min=-70.0, lon_max=0.0
    )

def default_imerg_input_dir() -> Path:
    # Default: /g/data/k10/zr7147/GPM_IMERG_Data
    return Path("/g/data/k10/zr7147/GPM_IMERG_Data")
```

### EarthCARE Configuration
```python
def default_earthcare_bbox() -> BoundingBox:
    # Same default as IMERG
    return BoundingBox(
        lat_min=0.0, lat_max=30.0,
        lon_min=-70.0, lon_max=0.0
    )

def default_earthcare_input_dir() -> Path:
    # Default: /g/data/k10/zr7147/EarthCARE_Data
    return Path("/g/data/k10/zr7147/EarthCARE_Data")

def earthcare_credentials() -> dict:
    # UPDATE THESE WITH YOUR CREDENTIALS
    return {
        "username": "your_username",
        "password": "your_password",
        "gportal_url": "https://gportal.jaxa.jp/",
    }
```

Override with environment variables or command-line arguments.

## IMERG Setup (One-time)

1. **Create NASA Earthdata account** (free):
   - https://urs.earthdata.nasa.gov

2. **Create `~/.netrc` file**:
   ```
   machine urs.earthdata.nasa.gov
   login <your_username>
   password <your_password>
   ```

3. **Secure credentials**:
   ```bash
   chmod 600 ~/.netrc
   ```

4. **Verify**: `earthaccess` will auto-detect credentials from `~/.netrc`

## EarthCARE Setup (One-time)

1. **Create G-Portal account**:
   - https://gportal.jaxa.jp/

2. **Register for EarthCARE data access** via G-Portal

3. **Update `scripts/config.py`**:
   ```python
   def earthcare_credentials() -> dict:
       return {
           "username": "your_gportal_username",
           "password": "your_gportal_password",
           "gportal_url": "https://gportal.jaxa.jp/",
       }
   ```

4. **Or use environment variables**:
   ```bash
   export EARTHCARE_USERNAME=your_username
   export EARTHCARE_PASSWORD=your_password
   export EARTHCARE_GPORTAL_URL=https://gportal.jaxa.jp/
   ```

5. **Implement G-Portal API calls**:
   - See `scripts/earthcare_download.py` (template with placeholder)
   - Reference: `GPortalUserManual_en.pdf`
   - Add actual API implementation in the placeholder section

## File Formats

### IMERG
- **Product**: GPM_3IMERGHH (Half-Hourly Final Run)
- **Format**: HDF5
- **Variable**: `precipitation` (mm/hr) in `/Grid` group
- **Location**: Downloaded to `/g/data/k10/zr7147/GPM_IMERG_Data/`

### EarthCARE
- **Product**: MSI_L2_PRE (Precipitation, Level 2)
- **Format**: NetCDF
- **Location**: Downloaded to `/g/data/k10/zr7147/EarthCARE_Data/`

## Next Steps

After downloading:

1. **Combine and crop satellite data**:
   ```bash
   python scripts/satellite_preprocessing.py
   ```
   - Combines all HDF5 files into single NetCDF
   - Crops to ORCESTRA region
   - Outputs: `/g/data/k10/zr7147/ORCESTRA_IMERG_Combined_Cropped.nc`

2. **Generate comparison plots**:
   ```bash
   python scripts/comparison_plotting.py
   ```
   - Plots dropsonde vs satellite precipitation
   - Matches data by time and location
   - Outputs to `outputs/figures/dropsonde_satellite_comparison/`

## Troubleshooting

### IMERG: "ModuleNotFoundError: No module named 'xarray'"
```bash
# Ensure you're in project root and use conda python
cd /home/565/zr7147/Proj
python imerg_download.py  # Uses conda python with xarray
```

### IMERG: "earthaccess not found"
```bash
# Install dependencies
conda install -y earthaccess xarray dask h5netcdf netcdf4
```

### EarthCARE: "Missing credentials"
1. Check `scripts/config.py` earthcare_credentials()
2. Or set environment variables (see above)
3. Verify G-Portal account is active

## Links

- **SPEC**: `notes/SPEC_sonde_vs_satellite.md`
- **NASA Earthdata**: https://urs.earthdata.nasa.gov/
- **G-Portal**: https://gportal.jaxa.jp/
- **GPortalUserManual**: `GPortalUserManual_en.pdf`
- **Jupyter Notebook**: `notebooks/download_gpm.ipynb`
