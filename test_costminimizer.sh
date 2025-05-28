#!/bin/bash

# Colors for better output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Log file
LOG_FILE="costminimizer_test_log.txt"

# Function for logging
log() {
    local message="$1"
    local level="${2:-INFO}"
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    echo -e "${timestamp} [${level}] ${message}" | tee -a "${LOG_FILE}"
}

# Error handling function
handle_error() {
    local exit_code=$?
    local line_number=$1
    log "Error occurred at line ${line_number} with exit code ${exit_code}" "ERROR"
    log "Test failed! Check the log file for details." "ERROR"
    exit ${exit_code}
}

# Set up error handling
trap 'handle_error $LINENO' ERR

# Define base directory for tests
BASE_DIR="~/workspace/CostMinimizer_Tests"

# Create timestamped directory
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
TEST_DIR="${BASE_DIR}/test_${TIMESTAMP}"
mkdir -p "${TEST_DIR}"
mkdir -p "~/cow"
cd "${TEST_DIR}"

# Initialize log file
echo "CostMinimizer Test Log - ${TIMESTAMP}" > "${LOG_FILE}"
log "Test directory created: ${TEST_DIR}"

# Check if git is installed
if ! command -v git &> /dev/null; then
    log "Git is not installed. Please install git and try again." "ERROR"
    exit 1
fi

# Clone the repository
log "Cloning CostMinimizer repository..."
git clone  git@ssh.gitlab.aws.dev:costminimizer/CostMinimizer.git 2>> "${LOG_FILE}"
if [ $? -ne 0 ]; then
    log "Failed to clone repository. Check your SSH keys and network connection." "ERROR"
    exit 1
fi

log "Repository cloned successfully."
cd CostMinimizer

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1)
log "Using ${PYTHON_VERSION}"

# Create and activate virtual environment
log "Setting up Python virtual environment..."
python3 -m venv .venv 2>> "${LOG_FILE}" || {
    log "Failed to create virtual environment. Make sure python3-venv is installed." "ERROR"
    exit 1
}
source .venv/bin/activate
log "Virtual environment activated."

# Install dependencies and the tool
log "Installing dependencies..."
pip install --upgrade pip 2>> "${LOG_FILE}"
pip install -r requirements.txt 2>> "${LOG_FILE}" || {
    log "Failed to install dependencies. Check requirements.txt and pip configuration." "ERROR"
    exit 1
}

log "Installing CostMinimizer..."
python3 setup.py develop 2>> "${LOG_FILE}" || {
    log "Failed to install CostMinimizer. Check setup.py." "ERROR"
    exit 1
}

# Run the tool with --a parameter
log "Running CostMinimizer with --a parameter..."
CostMinimizer --a 2>&1 | tee -a "${LOG_FILE}"
TEST_RESULT=$?

# Check if the test was successful
if [ ${TEST_RESULT} -eq 0 ]; then
    log "CostMinimizer executed successfully!" "SUCCESS"
else
    log "CostMinimizer execution failed with exit code ${TEST_RESULT}" "ERROR"
fi

# Capture version information for reference
log "CostMinimizer version information:" "INFO"
CostMinimizer --version 2>&1 | tee -a "${LOG_FILE}" || log "Could not retrieve version information" "WARNING"

# Deactivate virtual environment
deactivate
log "Virtual environment deactivated."

# Copy log file to parent directory for easy access
cp "${LOG_FILE}" "${BASE_DIR}/"

# Final status message
if [ ${TEST_RESULT} -eq 0 ]; then
    echo -e "${GREEN}Test completed successfully!${NC}"
    echo -e "Test results available at: ${TEST_DIR}"
    echo -e "Log file: ${TEST_DIR}/${LOG_FILE} (copy also at ${BASE_DIR}/${LOG_FILE})"
else
    echo -e "${RED}Test failed!${NC}"
    echo -e "Check log file for details: ${TEST_DIR}/${LOG_FILE}"
fi

exit ${TEST_RESULT}