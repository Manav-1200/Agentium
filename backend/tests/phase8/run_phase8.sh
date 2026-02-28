#!/bin/bash

echo "Running Phase 8.1 - Core Functionality"
python -m pytest backend/tests/phase8/test_database_stress.py \
    backend/tests/phase8/test_message_bus.py \
    backend/tests/phase8/test_voting_stress.py \
    backend/tests/phase8/test_constitutional_guard.py \
    -v --tb=short --junit-xml=/tmp/phase8_core.xml

echo "Running Phase 8.2 - Performance Benchmarks"
python -m pytest backend/tests/phase8/test_performance.py \
    -v --tb=short --junit-xml=/tmp/phase8_perf.xml

echo "Running Phase 8.3 - Chaos Testing"
python -m pytest backend/tests/phase8/test_chaos.py \
    -v --tb=short --junit-xml=/tmp/phase8_chaos.xml

echo "Running Critic Effectiveness Tests"
python -m pytest backend/tests/phase8/test_critic_effectiveness.py \
    -v --tb=short --junit-xml=/tmp/phase8_critic.xml

echo "Generating Report"
python backend/tests/phase8/generate_report.py
