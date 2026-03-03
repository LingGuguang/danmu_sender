#!/usr/bin/env bash
# 一键运行弹幕发送工具（默认会先更新 requirements）
# 用法: ./run.sh          # 更新依赖并运行
#       ./run.sh -n       # 不更新依赖，直接运行
set -e
cd "$(dirname "$0")"

NO_UPDATE=""
ARGS=()
for arg in "$@"; do
  case "$arg" in
    --no-update|-n) NO_UPDATE=1 ;;
    *)              ARGS+=("$arg") ;;
  esac
done

if [[ -z "$NO_UPDATE" ]]; then
  echo "正在更新依赖 (pip install -r requirements.txt) ..."
  pip install -r requirements.txt -q
  echo "依赖已就绪。"
fi

echo "启动 danmu_sender ..."
exec python -m danmu_sender "${ARGS[@]}"
