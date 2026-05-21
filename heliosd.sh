#!/bin/bash
# Helios 生命体 — 守护进程管理脚本
# 
# 用法:
#   ./heliosd.sh start   → 启动 (后台)
#   ./heliosd.sh stop    → 优雅停止
#   ./heliosd.sh status  → 查看状态
#   ./heliosd.sh log     → 实时尾随日志
#   ./heliosd.sh attach  → 前台模式 (Ctrl+C 退出)

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$PROJECT_DIR/heliosd.pid"
LOG_DIR="$PROJECT_DIR/logs"

# 确保目录存在
mkdir -p "$LOG_DIR"

_pid() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE"
    fi
}

_running() {
    local pid=$(_pid)
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

status() {
    if _running; then
        local pid=$(_pid)
        echo "🟢 Helios 运行中 (PID: $pid)"
        return 0
    else
        echo "⚫ Helios 未运行"
        return 1
    fi
}

start() {
    if _running; then
        echo "⚠ Helios 已经在运行 (PID: $(_pid))"
        return 1
    fi

    cd "$PROJECT_DIR"

    # 自动加载 .env
    if [ -f .env ]; then
        set -a; source .env; set +a
    fi

    nohup python3 helios_main.py \
        >> "$LOG_DIR/heliosd.log" 2>&1 &

    echo $! > "$PID_FILE"
    sleep 1

    if _running; then
        echo "🟢 Helios 已启动 (PID: $(cat $PID_FILE))"
    else
        echo "❌ 启动失败，查看日志: $LOG_DIR/heliosd.log"
        return 1
    fi
}

stop() {
    if ! _running; then
        echo "⚫ Helios 未在运行"
        rm -f "$PID_FILE"
        return 0
    fi

    local pid=$(_pid)
    echo "⏳ 发送 SIGTERM → PID $pid ..."
    kill "$pid"

    # 等待最多 10 秒
    for i in $(seq 1 10); do
        if ! kill -0 "$pid" 2>/dev/null; then
            echo "✅ Helios 已优雅退出"
            rm -f "$PID_FILE"
            return 0
        fi
        sleep 1
    done

    echo "⚠ 超时，强制终止..."
    kill -9 "$pid" 2>/dev/null || true
    rm -f "$PID_FILE"
    echo "💀 已强制终止"
}

log() {
    tail -f "$LOG_DIR/helios_$(date +%Y%m%d).log"
}

attach() {
    if _running; then
        echo "⚠ Helios 已在后台运行，请先 stop"
        return 1
    fi
    cd "$PROJECT_DIR"
    if [ -f .env ]; then
        set -a; source .env; set +a
    fi
    echo "🟢 Helios 前台模式 (Ctrl+C 退出)"
    python3 helios_main.py
}

case "${1:-}" in
    start)   start ;;
    stop)    stop ;;
    restart) stop; sleep 1; start ;;
    status)  status ;;
    log)     log ;;
    attach)  attach ;;
    *)       echo "用法: $0 {start|stop|restart|status|log|attach}" ;;
esac
