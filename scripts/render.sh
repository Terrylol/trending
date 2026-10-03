#!/usr/bin/env bash
# 完整渲染（配音 + 动效 + 封面），可选 --upload
#
# 用法：
#   bash scripts/render.sh
#   bash scripts/render.sh --upload
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v ffmpeg >/dev/null 2>&1 && [ -x bin/ffmpeg ]; then
    export PATH="$PWD/bin:$PATH"
fi

if [ ! -d venv ]; then
    echo "✗ 未找到 venv，请先运行: bash scripts/bootstrap.sh"
    exit 1
fi

# 文案质量闸：不达标就不渲染，避免产出套话视频
# --draft 是例外：草稿模式本就不渲染，跳过校验
if [ -f output/projects_summary.json ] && [ "${1:-}" != "--draft" ]; then
    echo "→ 校验文案质量"
    if ! venv/bin/python -m src.narrative_validator output/projects_summary.json; then
        echo
        echo "✗ 文案不达标，已中止渲染。"
        echo "  按上面的提示修改 output/projects_summary.json 的 narrative 字段。"
        exit 1
    fi
    echo
fi

if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

echo "→ 开始渲染（约 6 分钟，动效逐帧缩放较慢）"
echo
exec venv/bin/python pipeline.py "$@"
