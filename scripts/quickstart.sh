#!/usr/bin/env bash
# 采集 + 生成文案模板（等价于 pipeline.py --draft，但自动处理 PATH）
#
# 用法：bash scripts/quickstart.sh [--limit 15]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# ffmpeg 兜底：如果系统 PATH 里没有，用 bin/ 下的
if ! command -v ffmpeg >/dev/null 2>&1 && [ -x bin/ffmpeg ]; then
    export PATH="$PWD/bin:$PATH"
fi

if [ ! -d venv ]; then
    echo "✗ 未找到 venv，请先运行: bash scripts/bootstrap.sh"
    exit 1
fi

# GitHub Token 优先读 .env，其次读环境变量
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

exec venv/bin/python pipeline.py --draft "$@"
