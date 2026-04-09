# Orcestra Vertical Profile Analysis

Analysis of dropsonde vertical velocity profiles and their comparison with satellite precipitation products (GPM/IMERG and EarthCARE) from the ORCESTRA field campaign.

## What this project does

- Categorises dropsonde profiles by vertical motion structure (top-heavy vs bottom-heavy)
- Produces comparison figures: dropsonde profile alongside collocated satellite precipitation maps

## Structure

```
notebooks/    — Jupyter notebooks for exploration and analysis
scripts/      — Python scripts for downloading and processing data
outputs/      — Generated figures
data/         — Local data staging (lightweight only)
```

Large data files (NetCDF, HDF5, Zarr) are stored on gadi `/g/data/k10/zr7147/`, not in this repository.

## Environment

```bash
conda activate /g/data/k10/zr7147/orcestra_env
```
