#!/bin/bash
# Daemon launcher for turing eval — properly disowns
cd /root/project/helios/helios_v2
nohup env PYTHONPATH=src /root/project/helios/helios_v2/.venv/bin/python3 -u scripts/helios_turing_system_runner.py --output /tmp/helios_turing_trace_1129.jsonl > /tmp/helios_turing_eval.log 2>&1 < /dev/null &
echo $! > /tmp/helios_turing_eval.pid
disown
exit 0
