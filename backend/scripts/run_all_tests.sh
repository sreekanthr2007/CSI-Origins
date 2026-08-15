#!/usr/bin/env bash
# TRACE: Full Test Suite Runner & Coverage Aggregator

set -e

echo "============================================================"
echo "🛡️ TRACE: Running Full Automated Test Suite"
echo "============================================================"

# 1. Run Unit Tests
echo "\n[Step 1/3] Running Unit Tests..."
pytest -v backend/tests/test_*.py

# 2. Run End-to-End Scenarios & Privacy Audits
echo "\n[Step 2/3] Running E2E Scenarios & Privacy Audits..."
pytest -v backend/tests/e2e/

# 3. Run E2E One-Command Demo Runner across all 4 scenarios
echo "\n[Step 3/3] Running E2E Demo Scenarios..."
python backend/scripts/demo_e2e.py --all

echo "\n============================================================"
echo "✅ All Tests & Verification Checks Complete!"
echo "============================================================"
