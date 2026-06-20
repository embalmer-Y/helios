#!/bin/bash
# P-TEMPORAL turing re-run progress monitor.
# Reads /tmp/helios_turing_ptemporal_eval.log and reports ticks-done / rate / ETA.
# Idempotent: safe to run repeatedly.

LOG=/tmp/helios_turing_ptemporal_eval.log
PID_FILE=/tmp/helios_turing_ptemporal_eval.pid
TRACE=/tmp/helios_turing_ptemporal_trace_1129.jsonl
TOTAL=1129

if [[ ! -f $LOG ]]; then
    echo "log not found: $LOG"
    exit 1
fi

if [[ -f $PID_FILE ]]; then
    PID=$(cat $PID_FILE)
    if ps -p $PID > /dev/null 2>&1; then
        echo "=== process status (pid $PID) ==="
        ps -p $PID -o pid,etime,pcpu,pmem,cmd | head -3
    else
        echo "=== process $PID not running ==="
    fi
else
    echo "no pid file at $PID_FILE"
fi

echo
echo "=== last 6 log lines ==="
tail -6 $LOG 2>&1

echo
echo "=== trace progress ==="
if [[ -f $TRACE ]]; then
    N=$(wc -l < $TRACE)
    echo "trace lines: $N / $TOTAL"
    PCT=$(awk "BEGIN{printf \"%.2f\", $N * 100.0 / $TOTAL}")
    echo "progress: $PCT %"
else
    echo "trace file not yet created: $TRACE"
fi
