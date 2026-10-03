#!/usr/bin/env bash
# 安装 B站上传依赖（可选功能，独立于主流程）
#
# 为什么单独一个脚本：bilibili-api-python 的传递依赖 qrcode-terminal 是
# 源码包，在部分沙箱环境会报 'mkdir EEXIST' 装不上。如果放在
# requirements.txt 里，会连带阻塞整个视频生成流程 —— 但上传只是
# --upload 才用的可选功能，不该成为主流程的前置条件。
#
# qrcode-terminal 只用于二维码登录，上传视频用不到它。
# 万一装不上，可以跳过，手动装其余依赖即可。
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -d venv ]; then
    echo "✗ 未找到 venv，请先运行: bash scripts/bootstrap.sh"
    exit 1
fi

echo "=== 安装 B站上传依赖 ==="
echo

# 先装主要依赖（这些都有 wheel，能正常装）
echo "[1/3] bilibili-api-python 及传递依赖"
venv/bin/pip install -q --no-deps bilibili-api-python
venv/bin/pip install -q qrcode pycryptodomex APScheduler pyyaml pyjwt \
                      aiohttp aiofiles numpy bcrypt brotli \
                      requests-toolbelt soupsieve
echo "      ✓ 完成"

# qrcode-terminal 是源码包，可能失败
echo
echo "[2/3] qrcode-terminal（可选，仅二维码登录用）"
if venv/bin/pip install -q qrcode-terminal 2>/dev/null; then
    echo "      ✓ 完成"
else
    echo "      ⚠ 跳过（沙箱环境限制）。不影响视频上传。"
    echo "        如需修复："
    echo "        1. 从 https://pypi.org/pypi/qrcode-terminal/json 取 tar.gz 地址"
    echo "        2. curl -sL <url> -o /tmp/q.tar.gz && tar -xzf /tmp/q.tar.gz -C /tmp"
    echo "        3. cp -r /tmp/qrcode-terminal-0.8/qrcode_terminal \\"
    echo "             \$(venv/bin/python -c 'import site;print(site.getsitepackages()[0])')/"
fi

echo
echo "[3/3] 验证"
if venv/bin/python -c "from bilibili_api import video_uploader" 2>/dev/null; then
    echo "      ✓ bilibili_api 可用，--upload 已就绪"
    exit 0
else
    echo "      ✗ bilibili_api 仍不可用"
    echo "        尝试：venv/bin/pip install --force-reinstall bilibili-api-python"
    exit 1
fi
