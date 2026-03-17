#!/bin/bash
#PBS -N OrcestraProcessing
#PBS -q normal
#PBS -l ncpus=16
#PBS -l mem=32GB
#PBS -l walltime=05:00:00
#PBS -l storage=gdata/k10
#PBS -l wd

# Load your environment
source /home/565/zr7147/.bashrc
conda activate /g/data/k10/zr7147/orcestra_env

# Run your analysis
python my_analysis_script.py