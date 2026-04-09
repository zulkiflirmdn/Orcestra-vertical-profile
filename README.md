# Orcestra Vertical Profile Analysis

## Overview

This repository contains analysis scripts and Jupyter notebooks for processing and categorizing vertical profile data from satellite observations as part of the ORCESTRA (Ocean-Atmosphere Research Experiment in the South Atlantic) campaign. The project focuses on atmospheric and oceanic vertical profiling using satellite data to study cloud structures, precipitation, and atmospheric dynamics.

## Features

- **Data Categorization**: Automated classification of satellite data into different atmospheric regimes
- **Vertical Profile Analysis**: Processing of radar and lidar profiles for cloud and precipitation characterization
- **Visualization**: Plotting and analysis of evolutionary grids and stratiform patterns
- **Batch Processing**: PBS job scripts for high-performance computing on NCI (National Computational Infrastructure)

## Project Structure

### Repository Code (stored at `/home/565/zr7147/Proj/`)
```
├── notebooks/                               # Main Jupyter notebooks
│   ├── categorization.ipynb                # Dropsonde categorization
│   ├── satellite.ipynb                     # IMERG satellite processing
│   ├── new_categorisation-omega.ipynb      # Vertical motion analysis
│   ├── note1.ipynb                         # Analysis notes
│   └── legacy/                             # Preserved older notebook copies
├── notes/                                  # Project notes and task specs
│   ├── SPEC_sonde_vs_satellite.md         # Requirements specification
│   ├── notes.md                           # Setup & workflow documentation
│   └── legacy/                            # Archived documentation
├── scripts/                                # Python processing scripts
│   ├── config.py                          # Configuration & paths
│   ├── satellite_preprocessing.py         # IMERG download & preprocessing
│   └── earthcare_preprocessing.py         # EarthCARE download & preprocessing (NEW)
├── outputs/                                # Generated outputs
│   ├── figures/
│   │   ├── plots/                        # Main figure outputs (formerly Plot-Figs/)
│   │   │   └── omega_satellite_pairs/    # Dropsonde-IMERG comparison figures
│   │   ├── dropsonde_satellite_comparison/  # 3-panel comparison figures (NEW)
│   │   └── legacy/                       # Archived figure outputs
│   └── logs/                             # Batch job logs
├── data/                                   # Local data staging (optional)
│   ├── raw/
│   └── processed/
├── GPortalUserManual_en.pdf                # EarthCARE reference documentation
├── satellite_preprocessing.py              # Backward-compatible wrapper
├── run_orcestra.sh                         # PBS job submission script
└── README.md                               # This file
```

### External Data Storage (stored at `/g/data/k10/zr7147/`)
```
/g/data/k10/zr7147/
├── GPM_IMERG_Data/                        # Raw IMERG HDF5 downloads
├── ORCESTRA_IMERG_Combined_Cropped.nc     # Processed IMERG (0N-30N, 70W-0W)
├── EarthCARE_Data/                        # Raw EarthCARE downloads (NEW)
├── ORCESTRA_EarthCARE_Combined_Cropped.nc # Processed EarthCARE (NEW)
├── ORCESTRA_dropsondes_categorized.zarr   # Processed dropsonde data
├── ORCESTRA_dropsondes_categories.csv     # Dropsonde category metadata
├── orcestra_env/                          # Conda environment
└── miniconda3/                            # Base conda installation
```

**Important**: All large data files are stored on `/g/data/k10/zr7147/` to comply with NCI storage policies. The repository contains only code, notebooks, lightweight metadata, and documentation.

## Setup and Installation

### Prerequisites

- Access to NCI Gadi supercomputer
- Conda environment management
- Python 3.x with scientific computing packages

### Environment Setup

1. **Activate the Conda Environment**:
   ```bash
   conda activate /g/data/k10/zr7147/orcestra_env
   ```

2. **Install Jupyter Kernel** (if not already done):
   ```bash
   conda install -p /g/data/k10/zr7147/orcestra_env ipykernel --yes
   /g/data/k10/zr7147/orcestra_env/bin/python -m ipykernel install --user --name orcestra_env --display-name "Python (ORCESTRA)"
   ```

### Data Access

- Satellite data is stored on NCI's `/g/data` filesystem
- Ensure you have appropriate project storage access (`gdata/k10`)

## Usage

### Running Jupyter Notebooks

1. Start Jupyter on a compute node:
   ```bash
   qsub -I -P k10 -q normal -l ncpus=8,mem=32GB,jobfs=10GB,walltime=04:00:00,storage=gdata/k10
   ```

2. Launch Jupyter:
   ```bash
   jupyter notebook
   ```

3. Open and run the analysis notebooks:
   - `notebooks/categorization.ipynb`: Core data categorization logic
   - `notebooks/satellite.ipynb`: Satellite data ingestion and processing
   - `notebooks/new_categorisation-omega.ipynb`: Advanced categorization with vertical motion analysis

### Batch Processing

For large-scale processing, use the PBS job script:

```bash
qsub run_orcestra.sh
```

The script (`run_orcestra.sh`) is configured to run `scripts/satellite_preprocessing.py` by default. You can override the target script with `qsub -F 'your_script.py' run_orcestra.sh`.

It is configured for:
- 16 CPUs
- 32GB memory
- 5-hour walltime
- Access to k10 project storage

### Key Analysis Components

- **Stratiform Classification**: Identification of stratiform cloud structures
- **Top-Heavy Analysis**: Characterization of precipitation profiles
- **Evolutionary Grids**: Time-series analysis of cloud evolution
- **Omega Profiles**: Vertical motion analysis from dropsonde data
- **IMERG Preprocessing**: GPM/IMERG satellite precipitation (domain: 0N-30N, 70W-0W)
- **EarthCARE Processing**: CloudSat/EarthCARE satellite precipitation (domain: 0N-30N, 70W-0W)
- **Dropsonde-Satellite Comparison**: Three-panel figures matching dropsonde profiles with satellite precipitation

## Git Workflow

### Cloning the Repository

```bash
git clone https://github.com/zulkiflirmdn/Orcestra-vertical-profile.git
cd Orcestra-vertical-profile
```

### Regular Workflow

```bash
# Check status
git status

# Pull latest changes
git pull --no-rebase

# Add and commit changes
git add .
git commit -m "Descriptive commit message"

# Push to remote
git push
```

**Note**: This repository uses merge strategy for handling divergent branches. If you encounter merge conflicts, resolve them manually or contact the repository maintainer.

## Dependencies

The conda environment includes packages for:
- Scientific computing (NumPy, SciPy, Pandas)
- Data visualization (Matplotlib, Cartopy)
- Atmospheric science (xarray, netCDF4)
- Machine learning (scikit-learn, if applicable)

## Output and Results

Analysis results are stored in organized directories:

- **Main Figures**: `outputs/figures/plots/` - All generated plots including omega-satellite pairs
- **Dropsonde-Satellite Comparison**: `outputs/figures/dropsonde_satellite_comparison/` - Three-panel comparison figures
- **Legacy Figures**: `outputs/figures/legacy/` - Archived output products
- **Job Logs**: `outputs/logs/` - Batch job execution logs

All large data files (NetCDF, HDF5) are retained on `/g/data/k10/zr7147/`:
- processed IMERG products
- processed EarthCARE products (after download)
- raw satellite data downloads

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and test thoroughly
4. Commit with clear messages
5. Push to your fork and create a pull request

## Contact

For questions or issues related to this project, please refer to the `notes/notes.txt` file or contact the repository maintainer.

## License

This project is part of the ORCESTRA campaign. Please check with the campaign coordinators for data usage policies and licensing.
