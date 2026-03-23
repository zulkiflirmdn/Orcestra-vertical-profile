# ORCESTRA Download Quick Reference

## 📥 IMERG (NASA - Ready to Use)

```bash
cd /home/565/zr7147/Proj
python imerg_download.py

# Status: ✅ 2496 files already downloaded (19GB)
# Preprocessing: python scripts/satellite_preprocessing.py
```

## 📥 EarthCARE (JAXA - Manual SFTP)

```bash
# 1. Get search results
cd /home/565/zr7147/Proj
python earthcare_download.py

# 2. Download via SFTP (choose one method below)
```

### Quick SFTP (Linux/Mac)
```bash
sftp -oPort=2051 zulkiflirmdn@gmail.com@ftp.gportal.jaxa.jp
cd /EarthCARE/L2_PRE/
get *.nc
bye
```

### Batch SFTP (lftp)
```bash
lftp sftp://zulkiflirmdn@gmail.com@ftp.gportal.jaxa.jp:2051
mirror /EarthCARE/L2_PRE/ /g/data/k10/zr7147/EarthCARE_Data/
quit
```

### Graphical (Windows/Mac/Linux)
1. Download WinSCP: http://winscp.net/
2. Connect: `ftp.gportal.jaxa.jp:2051`
3. Drag-drop files from `/EarthCARE/L2_PRE/`

## 🔗 Authentication

**IMERG**: NASA Earthdata credentials in `~/.netrc`
```
machine urs.earthdata.nasa.gov
login <username>
password <password>
```

**EarthCARE**: G-Portal credentials in `scripts/config.py`
```python
def earthcare_credentials() -> dict:
    return {
        "username": "zulkiflirmdn@gmail.com",
        "password": "YOUR_PASSWORD",
    }
```

## 📊 After Download

```bash
# Combine IMERG files
python scripts/satellite_preprocessing.py

# Combine EarthCARE files (when available)
python scripts/earthcare_preprocessing.py

# Generate comparison plots
python scripts/comparison_plotting.py
```

## 📁 Output Locations

- **Downloaded data**: `/g/data/k10/zr7147/GPM_IMERG_Data/` (IMERG)
- **Downloaded data**: `/g/data/k10/zr7147/EarthCARE_Data/` (EarthCARE)
- **Processed IMERG**: `/g/data/k10/zr7147/ORCESTRA_IMERG_Combined_Cropped.nc`
- **Processed EarthCARE**: `/g/data/k10/zr7147/ORCESTRA_EarthCARE_Combined_Cropped.nc`
- **Comparison plots**: `/home/565/zr7147/Proj/outputs/figures/dropsonde_satellite_comparison/`

## 📚 Documentation

- **DOWNLOAD_SATELLITES.md**: Full download guide
- **EARTHCARE_DOWNLOAD_GUIDE.md**: EarthCARE detailed guide
- **GPortalUserManual_en.pdf**: G-Portal official manual
- **SPEC_sonde_vs_satellite.md**: Project specification

## ❓ Troubleshooting

### IMERG issues?
→ Run: `PYTHONPATH=/home/565/zr7147/Proj:$PYTHONPATH python scripts/satellite_preprocessing.py`

### EarthCARE SFTP not connecting?
→ Check: telnet ftp.gportal.jaxa.jp 2051
→ Verify: Username/password in config.py

### Missing dependencies?
→ Install: `pip install earthaccess xarray h5netcdf netcdf4 requests`
