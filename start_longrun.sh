#!/bin/bash
# Helios 24h 长跑启动器
cd /home/radxa/project/helios
export OPENAI_API_KEY="RLRbFnwBOAbQUGg5F4u5Lly7Kl35DmJiVJOL_XXCB_lRg287DpTRgXqVm8riNukHEMNXB8eLRNrHuyiM5I8jSw"
export OPENAI_BASE_URL="https://router.shengsuanyun.com/api/v1"
export HELIOS_LLM_MODEL="deepseek/deepseek-v4-flash"
exec python3 demo_longrun.py --hours 24
