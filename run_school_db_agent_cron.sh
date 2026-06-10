#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# ==========================================
# CONFIGURATION BOUNDARIES
# ==========================================
# Automatically capture the absolute directory path of the active script
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/sync_$(date +'%Y-%m-%d_%H%M%S').log"
ENV_FILE="${PROJECT_DIR}/.env"

# Create the logs repository folder if it doesn't exist
mkdir -p "${LOG_DIR}"

# Redirect all script outputs (stdout and stderr) directly into the timed log file
exec > >(tee -i "${LOG_FILE}") 2>&1

echo "=================================================="
echo "      DUBAI GRAPH AGENT CRON EXECUTION PASS        "
echo "      Timestamp: $(date +'%Y-%m-%d %H:%M:%S')      "
echo "=================================================="

# Move execution context directly into your project workspace
cd "${PROJECT_DIR}"

# 1. Verify existence of the secure configuration environment definitions
if [ ! -f "${ENV_FILE}" ]; then
    echo "🚨 Critical Error: Configuration file '.env' is missing in ${PROJECT_DIR}."
    exit 1
fi

# Load environment variables securely
export $(grep -v '^#' "${ENV_FILE}" | xargs)

# 2. Assert and check for 'uv' system availability globally
if ! command -v uv &> /dev/null; then
    echo "⚠️ Warning: 'uv' runtime binary not found in standard system PATH."
    echo "Attempting standard fallback checks to local user binary allocations..."
    export PATH="${HOME}/.local/bin:${PATH}"
    
    if ! command -v uv &> /dev/null; then
        echo "🚨 Critical Error: 'uv' package manager engine is missing. Cannot continue."
        exit 1
    fi
fi

# 3. Synchronize package updates silently before execution runs
echo "Ensuring project state dependencies are locked..."
uv sync --quiet

# 4. Trigger the atomic state machine sync execution
echo "Spawning LangGraph database processing thread..."
uv run python -m dubai

# 5. Clean up old historical log files (Keeps only the last 30 runs)
echo "Executing systematic log retention sweep..."
find "${LOG_DIR}" -name "sync_*.log" -type f -mtime +30 -delete

echo "=================================================="
echo "    SYNC RUN SECURELY PROCESSED AND COMPLETED      "
echo "=================================================="

