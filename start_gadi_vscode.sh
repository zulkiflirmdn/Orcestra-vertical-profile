#!/bin/bash
# ============================================================
# start_gadi_vscode.sh  — run this on your LOCAL LAPTOP
#
# What it does:
#   1. SSH into Gadi → runs ~/gadi_compute_ssh.sh (submits PBS job, waits for node)
#   2. Updates your LOCAL ~/.ssh/config with the new node hostname
#   3. Opens VS Code directly connected to the compute node + project folder
#
# Requirements (local laptop):
#   - SSH key configured for gadi.nci.org.au
#   - VS Code with Remote - SSH extension (ms-vscode-remote.remote-ssh)
#   - ~/.ssh/config with 'Host gadi' entry (see notes.md)
#
# Usage:
#   bash start_gadi_vscode.sh [ncpus] [mem] [walltime] [project]
# ============================================================

NCPUS=${1:-4}
MEM=${2:-16GB}
WALLTIME=${3:-4:00:00}
PROJECT=${4:-nf33}
PROJ_PATH="/home/565/zr7147/Proj"
GADI_USER="zr7147"
GADI_HOST="gadi"   # matches 'Host gadi' in your local ~/.ssh/config

echo "===================================================="
echo " Starting Gadi compute session..."
echo "===================================================="

# ── 1. Run setup script on Gadi, capture the node FQDN ───────────────────────
echo "Connecting to Gadi login node..."
FQDN=$(ssh "$GADI_HOST" "bash ~/gadi_compute_ssh.sh $NCPUS $MEM $WALLTIME $PROJECT 2>&1" \
    | grep "Node allocated:" \
    | awk '{print $3}')

if [[ -z "$FQDN" ]]; then
    echo "ERROR: Could not get compute node from Gadi. Check SSH connection." >&2
    exit 1
fi

echo "Compute node: $FQDN"

# ── 2. Update LOCAL ~/.ssh/config with new node hostname ─────────────────────
SSH_CONFIG="$HOME/.ssh/config"

if grep -q "^Host gadi-compute" "$SSH_CONFIG" 2>/dev/null; then
    # macOS needs empty string after -i; Linux doesn't — this handles both
    sed -i.bak "/^Host gadi-compute/,/^Host / s|HostName .*gadi-cpu.*|HostName $FQDN|" "$SSH_CONFIG"
    echo "Updated local ~/.ssh/config → gadi-compute = $FQDN"
else
    cat >> "$SSH_CONFIG" << EOF

Host gadi-compute
    HostName $FQDN
    User $GADI_USER
    ProxyJump $GADI_HOST
EOF
    echo "Added gadi-compute to local ~/.ssh/config"
fi

# ── 3. Open VS Code on compute node ──────────────────────────────────────────
echo ""
echo "Opening VS Code on compute node..."
code --remote "ssh-remote+gadi-compute" "$PROJ_PATH"

echo ""
echo "===================================================="
echo " VS Code should open shortly."
echo " Kernel 'Python (ORCESTRA)' will be auto-selected."
echo "===================================================="
