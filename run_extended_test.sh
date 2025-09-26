#!/bin/bash

# Extended Connector Test Runner
# This script ensures proper Python path setup for running the Extended connector test

echo "Running Extended Connector Test..."
python3 -m test_extended_real "$@"