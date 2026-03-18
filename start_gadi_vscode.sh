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

set -euo pipefail

NCPUS=${1:-4}
MEM=${2:-16GB}
WALLTIME=${3:-4:00:00}
PROJECT=${4:-nf33}
PROJ_PATH="/home/565/zr7147/Proj"
GADI_USER="zr7147"
GADI_HOST="gadi"   # matches 'Host gadi' in your local ~/.ssh/config
CURRENT_HOST=$(hostname 2>/dev/null || echo "")
USER_SHELL=${SHELL:-/bin/bash}

update_local_ssh_alias() {
    local ssh_config="$HOME/.ssh/config"
    local fqdn="$1"
    local tmp_file

    mkdir -p "$HOME/.ssh"
    chmod 700 "$HOME/.ssh"
    touch "$ssh_config"

    tmp_file=$(mktemp)
    awk -v fqdn="$fqdn" -v user="$GADI_USER" -v proxy_jump="$GADI_HOST" '
        BEGIN {
            in_block = 0
            replaced = 0
        }
        function print_block() {
            print "Host gadi-compute"
            print "    HostName " fqdn
            print "    User " user
            print "    ProxyJump " proxy_jump
        }
        $1 == "Host" && $2 == "gadi-compute" {
            if (!replaced) {
                print_block()
                replaced = 1
            }
            in_block = 1
            next
        }
        $1 == "Host" && in_block {
            in_block = 0
        }
        !in_block {
            print
        }
        END {
            if (!replaced) {
                if (NR > 0) {
                    print ""
                }
                print_block()
            }
        }
    ' "$ssh_config" > "$tmp_file"

    mv "$tmp_file" "$ssh_config"
    chmod 600 "$ssh_config"
}

if [[ "$CURRENT_HOST" == gadi-cpu-* ]] || [[ "$CURRENT_HOST" == gadi-cpu-*.gadi.nci.org.au ]]; then
    echo "===================================================="
    echo " Already on a Gadi compute node"
    echo "===================================================="
    echo "Current host: $CURRENT_HOST"
    if [[ "$PWD" != "$PROJ_PATH" ]]; then
        echo "Opening a project shell in $PROJ_PATH ..."
        exec "$USER_SHELL" -lc "cd '$PROJ_PATH' && exec '$USER_SHELL' -l"
    fi

    echo "Already in the project directory: $PROJ_PATH"
    echo "If you want a VS Code window, run this script on your local laptop instead:"
    echo "  bash ~/start_gadi_vscode.sh"
    exit 0
fi

if [[ "$CURRENT_HOST" == gadi-login-* ]] || [[ "$CURRENT_HOST" == gadi-login-*.gadi.nci.org.au ]]; then
    echo "===================================================="
    echo " Running on Gadi login node"
    echo "===================================================="
    echo "This script is for your local laptop, not for the Gadi login node."
    echo ""
    if ssh -o ConnectTimeout=5 gadi-compute hostname >/dev/null 2>&1; then
        echo "Active compute node alias detected: gadi-compute"
        echo "Opening terminal session on the compute node in $PROJ_PATH ..."
        exec ssh -t gadi-compute "cd '$PROJ_PATH' && exec ${USER_SHELL} -l"
    fi

    echo "No active gadi-compute alias is available yet."
    echo "Run this on Gadi first to create/update the compute node alias:"
    echo "  bash ~/gadi_compute_ssh.sh $NCPUS $MEM $WALLTIME $PROJECT"
    exit 1
fi

echo "===================================================="
echo " Starting Gadi compute session..."
echo "===================================================="

# ── 1. Run setup script on Gadi, capture the node FQDN ───────────────────────
echo "Connecting to Gadi login node..."
FQDN=$(ssh "$GADI_HOST" "bash ~/gadi_compute_ssh.sh $NCPUS $MEM $WALLTIME $PROJECT 2>&1" \
    | grep "Node allocated:" \
    | awk '{print $3}')

if [[ -z "$FQDN" ]]; then
    echo "ERROR: Could not get compute node from Gadi." >&2
    echo "Check that your local ~/.ssh/config contains this entry:" >&2
    echo "  Host gadi" >&2
    echo "      HostName gadi.nci.org.au" >&2
    echo "      User $GADI_USER" >&2
    exit 1
fi

echo "Compute node: $FQDN"

# ── 2. Update LOCAL ~/.ssh/config with new node hostname ─────────────────────
update_local_ssh_alias "$FQDN"
echo "Updated local ~/.ssh/config → gadi-compute = $FQDN"

# ── 3. Open VS Code on compute node ──────────────────────────────────────────
echo ""
echo "Opening VS Code on compute node..."
if ! command -v code >/dev/null 2>&1; then
    echo "ERROR: 'code' command is not available in this terminal." >&2
    echo "Install VS Code command line integration on your laptop, then rerun this script." >&2
    exit 127
fi

code --remote "ssh-remote+gadi-compute" "$PROJ_PATH"

echo ""
echo "===================================================="
echo " VS Code should open shortly."
echo " Kernel 'Python (ORCESTRA)' will be auto-selected."
echo "===================================================="
