#!/bin/bash
# P-TEMPORAL Daemon launcher for turing eval re-run.
# 2026-06-20 启动: Phase 2c 真实 wire ship 后 1129 tick 8h 复跑, 验证 D2/D8/D10 提升.
# Output: /tmp/helios_turing_ptemporal_trace_1129.jsonl
# Log: /tmp/helios_turing_ptemporal_eval.log
# PID: /tmp/helios_turing_ptemporal_eval.pid

cd /root/project/helios/helios_v2
set -a
. /root/project/helios/.env
set +a

nohup env PYTHONPATH=src /root/project/helios/helios_v2/.venv/bin/python3 -u \
    scripts/helios_turing_system_runner.py \
    --output /tmp/helios_turing_ptemporal_trace_1129.jsonl \
    > /tmp/helios_turing_ptemporal_eval.log 2>&1 < /dev/null &

echo $! > /tmp/helios_turing_ptemporal_eval.pid
disown
exit 0
