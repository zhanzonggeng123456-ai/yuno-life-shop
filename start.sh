#!/bin/bash
# Yuno Life 一条命令启动: ./start.sh
# 首次运行自动创建虚拟环境并安装依赖(免费开源组件,无付费 API)。
set -e
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt
exec .venv/bin/python run.py
