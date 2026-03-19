#!/bin/bash
#PBS -N OrcestraProcessing
#PBS -P k10
#PBS -q normal
#PBS -l ncpus=16
#PBS -l mem=32GB
#PBS -l walltime=05:00:00
#PBS -l jobfs=10GB
#PBS -l storage=gdata/k10+scratch/k10
#PBS -l wd

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="${1:-scripts/satellite_preprocessing.py}"
ENV_PREFIX="/g/data/k10/zr7147/orcestra_env"
PYTHON_BIN="$ENV_PREFIX/bin/python"

cd "$SCRIPT_DIR"

if [[ ! -x "$PYTHON_BIN" ]]; then
	echo "ERROR: Python environment not found at $ENV_PREFIX" >&2
	exit 1
fi

if [[ ! -f "$PYTHON_SCRIPT" ]]; then
	echo "ERROR: Python script not found: $SCRIPT_DIR/$PYTHON_SCRIPT" >&2
	echo "Usage: qsub run_orcestra.sh" >&2
	echo "   or: qsub -F 'your_script.py' run_orcestra.sh" >&2
	exit 1
fi

echo "Running $PYTHON_SCRIPT from $SCRIPT_DIR"
echo "Using Python: $PYTHON_BIN"

export ORCESTRA_DASK_WORKERS="${ORCESTRA_DASK_WORKERS:-${PBS_NCPUS:-16}}"
export ORCESTRA_DASK_MEMORY_LIMIT="${ORCESTRA_DASK_MEMORY_LIMIT:-1800MiB}"

echo "Dask workers: $ORCESTRA_DASK_WORKERS"
echo "Dask memory limit per worker: $ORCESTRA_DASK_MEMORY_LIMIT"

exec "$PYTHON_BIN" "$PYTHON_SCRIPT"