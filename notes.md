# Orcestra Vertical Profile Project Notes

## Environment Setup

### Install ipykernel into the conda environment
```bash
conda install -p /g/data/k10/zr7147/orcestra_env ipykernel --yes
```

### Register the kernel for Jupyter
```bash
/g/data/k10/zr7147/orcestra_env/bin/python -m ipykernel install --user --name orcestra_env --display-name "Python (ORCESTRA)"
```

### Activate the conda environment
```bash
conda activate /g/data/k10/zr7147/orcestra_env
```

---

## Job Submission on NCI

### Submit a batch job
```bash
qsub run_orcestra.sh
```

### Request interactive compute node
```bash
qsub -I -P k10 -q normal -l ncpus=8,mem=32GB,jobfs=10GB,walltime=04:00:00,storage=gdata/k10
```

---

## Check Compute & Storage Resources on Gadi

### Account & CPU allocation
```bash
nci_account -v
```

### Storage quota
```bash
lquota
```

### Job queue status
```bash
qstat -u $USER
```

### Recent job history & usage
```bash
nvlog
```

### Project details
```bash
nci_account
```

---

## Git Commands

### Check repository status
```bash
git status
```

### Add files to staging
```bash
git add <file>
git add .  # Add all changes
```

### Commit changes
```bash
git commit -m "Your commit message"
```

### Pull latest changes from remote
```bash
git pull --no-rebase  # Use merge strategy for divergent branches
```

### Push commits to remote
```bash
git push
```

### View commit history
```bash
git log --oneline
```

### Clone the repository (if starting fresh)
```bash
git clone https://github.com/zulkiflirmdn/Orcestra-vertical-profile.git
```

---

## Running the Project

### Run the analysis script via PBS job
See `run_orcestra.sh` for batch job configuration

### Or run directly in environment
```bash
python my_analysis_script.py
```

### Use Jupyter notebooks for data exploration
Open notebooks like `categorization.ipynb`, `satellite.ipynb`, etc.

---

## Important Notes

- ✅ Ensure conda environment is activated before running Python scripts or notebooks
- ✅ Use `qsub` for compute-intensive tasks on NCI
- ✅ Commit and push changes regularly to GitHub
- ✅ For divergent branches, use `git pull --no-rebase` to merge