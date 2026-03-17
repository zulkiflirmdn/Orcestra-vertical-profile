# Orcestra Vertical Profile Analysis

## Overview

This repository contains analysis scripts and Jupyter notebooks for processing and categorizing vertical profile data from satellite observations as part of the ORCESTRA (Ocean-Atmosphere Research Experiment in the South Atlantic) campaign. The project focuses on atmospheric and oceanic vertical profiling using satellite data to study cloud structures, precipitation, and atmospheric dynamics.

## Features

- **Data Categorization**: Automated classification of satellite data into different atmospheric regimes
- **Vertical Profile Analysis**: Processing of radar and lidar profiles for cloud and precipitation characterization
- **Visualization**: Plotting and analysis of evolutionary grids and stratiform patterns
- **Batch Processing**: PBS job scripts for high-performance computing on NCI (National Computational Infrastructure)

## Project Structure

```
├── categorization.ipynb              # Main data categorization notebook
├── new_categorisation-omega.ipynb    # Advanced categorization with omega analysis
├── satellite.ipynb                   # Satellite data processing
├── note1.ipynb                       # Additional analysis notes
├── run_orcestra.sh                   # PBS job submission script
├── notes.txt                         # Important commands and setup instructions
├── README.md                         # This file
├── Orcestra-vertical-profile/        # Subfolder with additional notebooks
│   ├── categorization.ipynb
│   ├── note1.ipynb
│   └── notes.txt
└── Plot-Figs/                        # Output figures and plots
    └── Evolutionary_Grid_Stratiform_Top-Heavy.png
```

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
   - `categorization.ipynb`: Core data categorization logic
   - `satellite.ipynb`: Satellite data ingestion and processing
   - `new_categorisation-omega.ipynb`: Advanced categorization with vertical motion analysis

### Batch Processing

For large-scale processing, use the PBS job script:

```bash
qsub run_orcestra.sh
```

The script (`run_orcestra.sh`) is configured for:
- 8 CPUs
- 32GB memory
- 5-hour walltime
- Access to k10 project storage

### Key Analysis Components

- **Stratiform Classification**: Identification of stratiform cloud structures
- **Top-Heavy Analysis**: Characterization of precipitation profiles
- **Evolutionary Grids**: Time-series analysis of cloud evolution
- **Omega Profiles**: Vertical motion analysis from model data

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

Analysis results are stored in:
- `Plot-Figs/`: Generated figures and plots
- Notebook outputs: Inline visualizations and data summaries

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and test thoroughly
4. Commit with clear messages
5. Push to your fork and create a pull request

## Contact

For questions or issues related to this project, please refer to the `notes.txt` file or contact the repository maintainer.

## License

This project is part of the ORCESTRA campaign. Please check with the campaign coordinators for data usage policies and licensing.
