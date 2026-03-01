#!/bin/bash
# Phase 9: Production Readiness — Full Test Suite Runner

set -e

echo "================================================================"
echo "  Phase 9: Production Readiness Test Suite"
echo "================================================================"

echo ""
echo "Running Phase 9.1 - Monitoring & Observability Tests"
python -m pytest backend/tests/phase9/test_phase9_monitoring.py \
    -v --tb=short --junit-xml=/tmp/phase9_monitoring.xml

echo ""
echo "Running Phase 9.2/9.3 - Maintenance & Backup Tests"
python -m pytest backend/tests/phase9/test_phase9_maintenance.py \
    -v --tb=short --junit-xml=/tmp/phase9_maintenance.xml

echo ""
echo "Running Phase 9.4 - Security Hardening Tests"
python -m pytest backend/tests/phase9/test_phase9_security.py \
    -v --tb=short --junit-xml=/tmp/phase9_security.xml

echo ""
echo "Running Phase 9.5 - API Key Resilience Tests"
python -m pytest backend/tests/phase9/test_phase9_api_keys.py \
    -v --tb=short --junit-xml=/tmp/phase9_api_keys.xml

echo ""
echo "================================================================"
echo "  Phase 9 Test Suite Complete"
echo "================================================================"
