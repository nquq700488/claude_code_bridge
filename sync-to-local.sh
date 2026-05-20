#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${HOME}/.local/share/ccb"
BACKUP_DIR="${TARGET_DIR}.backup.$(date +%Y%m%d_%H%M%S)"

echo "=== CCB Sync to Local Install ==="
echo "Source: ${SCRIPT_DIR}"
echo "Target: ${TARGET_DIR}"

if [[ ! -d "${TARGET_DIR}" ]]; then
    echo "Error: Target directory does not exist: ${TARGET_DIR}"
    echo "Please install ccb first (e.g. run install.sh)"
    exit 1
fi

# Backup existing target
echo "Creating backup: ${BACKUP_DIR}"
cp -a "${TARGET_DIR}" "${BACKUP_DIR}"

# Remove old Python cache to avoid stale .pyc issues
echo "Cleaning Python cache in target..."ind "${TARGET_DIR}" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find "${TARGET_DIR}" -name '*.pyc' -delete 2>/dev/null || true

# Sync core code directories and files
# Exclude: runtime data, git, tests, docs, assets, etc.
echo "Syncing code..."
rsync -a --delete \
    --exclude='.ccb/' \
    --exclude='.git/' \
    --exclude='.claude/' \
    --exclude='.gemini/' \
    --exclude='.loop/' \
    --exclude='test/' \
    --exclude='tests/' \
    --exclude='assets/' \
    --exclude='docs/' \
    --exclude='plans/' \
    --exclude='.github/' \
    --exclude='archive/' \
    --exclude='*.pyc' \
    --exclude='__pycache__/' \
    --exclude='.DS_Store' \
    --exclude='sync-to-local.sh' \
    "${SCRIPT_DIR}/" "${TARGET_DIR}/"

echo ""
echo "=== Sync complete ==="
echo "Backup saved to: ${BACKUP_DIR}"
echo ""
echo "Verifying CcbdLifecycleStore..."
if grep -q "class CcbdLifecycleStore" "${TARGET_DIR}/lib/ccbd/services/lifecycle.py"; then
    echo "OK: CcbdLifecycleStore found in synced code."
else
    echo "ERROR: CcbdLifecycleStore still missing!"
    exit 1
fi

# Restart ccb if current directory is a ccb project
CWD="$(pwd)"
if [[ -f "${CWD}/.ccb/ccb.config" ]]; then
    echo ""
    echo "Detected ccb project in current directory: ${CWD}"
    echo "Restarting ccb to load new code..."
    echo ""
    ccb kill 2>/dev/null || true
    sleep 1
    ccb
else
    echo ""
    echo "Note: Current directory is not a ccb project (no .ccb/ccb.config found)."
    echo "If you have a running ccb project, please cd to that directory and run:"
    echo "  ccb kill && ccb"
fi
