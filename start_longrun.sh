#!/bin/bash
# Helios 24h 长跑启动器
cd /home/radxa/project/helios
export OPENAI_API_KEY="xxx"
export OPENAI_BASE_URL="xxx"
export HELIOS_LLM_MODEL="deepseek/deepseek-v4-flash"
exec python3 demo_longrun.py --hours 24
