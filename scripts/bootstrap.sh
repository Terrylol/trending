#!/usr/bin/env bash
# 首次环境准备
#
# 解决的问题：
# 1. ffmpeg 不一定在 PATH 里（brew 装不上时用 imageio-ffmpeg 的二进制）
# 2. bin/ffmpeg 不能提交 —— 它是指向本机 venv 的软链，换机器必断
# 3. 新克隆不知道要准备哪些东西
#
# 用法：bash scripts/bootstrap.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo " GitHub Trending Video · 环境准备"
echo "=============================================="
echo

# ---------- 1. Python venv ----------
if [ ! -d venv ]; then
    echo "[1/4] 创建 Python venv"
    python3 -m venv venv
else
    echo "[1/4] Python venv 已存在"
fi

if [ ! -f venv/bin/.deps_installed ]; then
    echo "      安装依赖（首次约 1-2 分钟）..."
    venv/bin/pip install -q --upgrade pip

    # 核心依赖：失败则无法渲染，必须中止
    if ! venv/bin/pip install -q -r requirements.txt; then
        echo
        echo "✗ 核心依赖安装失败。"
        echo "  常见原因：qrcode-terminal 是源码包，在部分沙箱环境会报 'mkdir EEXIST'。"
        echo "  解决办法（上传功能可跳过）："
        echo "    venv/bin/pip install moviepy Pillow requests beautifulsoup4 lxml \\"
        echo "      edge-tts imageio-ffmpeg pytest"
        echo "  然后手动补上传依赖："
        echo "    venv/bin/pip install --no-deps bilibili-api-python"
        echo "    venv/bin/pip install qrcode pycryptodomex APScheduler pyyaml pyjwt \\"
        echo "      aiohttp aiofiles numpy bcrypt brotli requests-toolbelt soupsieve"
        exit 1
    fi
    touch venv/bin/.deps_installed
    echo "      依赖安装完成"
else
    echo "      依赖已安装"
fi

# ---------- 1.5 B站上传（可选） ----------
echo
echo "[1.5/4] B站上传依赖（可选功能）"
if venv/bin/python -c "from bilibili_api import video_uploader" 2>/dev/null; then
    echo "      已可用"
else
    echo "      未安装（视频生成不受影响，仅 --upload 不可用）"
    echo "      安装：bash scripts/install_upload_deps.sh"
fi

# ---------- 2. 配置文件 ----------
echo
echo "[2/4] 配置文件"
if [ ! -f config/config.json ]; then
    cp config/config.example.json config/config.json
    echo "      已从模板创建 config/config.json"
else
    echo "      config/config.json 已存在"
fi

if [ ! -f .env ]; then
    cp .env.example .env
    chmod 600 .env
    echo "      已从模板创建 .env（记得填写 GITHUB_TOKEN）"
else
    echo "      .env 已存在"
fi

# ---------- 3. ffmpeg ----------
echo
echo "[3/4] ffmpeg"
if command -v ffmpeg >/dev/null 2>&1; then
    echo "      系统 PATH 里已有 ffmpeg，无需额外处理"
    rm -f bin/ffmpeg 2>/dev/null || true
    rmdir bin 2>/dev/null || true
else
    FFMPEG_BIN="$(venv/bin/python -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())' 2>/dev/null || true)"
    if [ -n "$FFMPEG_BIN" ] && [ -f "$FFMPEG_BIN" ]; then
        mkdir -p bin
        # 直接用绝对路径建软链。bin/ 本身不入库，换机器重跑本脚本即可。
        ln -sf "$FFMPEG_BIN" bin/ffmpeg
        echo "      已创建 bin/ffmpeg"
        echo "      ⚠ bin/ 不入库，换机器后需重跑本脚本"
        echo "      用 scripts/quickstart.sh 或 scripts/render.sh 会自动注入 PATH"
    else
        echo "      ✗ 未找到 ffmpeg，请手动安装："
        echo "        brew install ffmpeg   # macOS"
        echo "        apt install ffmpeg   # Debian/Ubuntu"
        exit 1
    fi
fi

# ---------- 4. 自检 ----------
echo
echo "[4/4] 自检"
FFPROBE_OK=0
if command -v ffprobe >/dev/null 2>&1; then
    FFPROBE_OK=1
    echo "      ✓ ffprobe 在 PATH"
elif [ -x bin/ffmpeg ]; then
    FFPROBE_OK=1
    echo "      ✓ bin/ffmpeg 可用（等价 ffprobe 功能）"
fi

# 渲染只用到 ffmpeg（ffprobe 已改用 ffmpeg -i 解析）
if [ "$FFPROBE_OK" = "0" ]; then
    echo "      · 未找到独立 ffprobe。渲染用 ffmpeg -i 解析，不影响使用"
fi

if venv/bin/python -c "from PIL import ImageFont; ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc', 20, index=1)" 2>/dev/null; then
    echo "      ✓ 中文字体可用（macOS STHeiti face=1 简体）"
else
    echo "      · 未验证到中文字体（非 macOS 或字体缺失），渲染中文可能失败"
    echo "        Linux 需安装：apt install fonts-noto-cjk"
fi

echo
echo "=============================================="
echo " 准备完成"
echo "=============================================="
echo
echo "下一步："
echo "  export GITHUB_TOKEN=xxx        # 见 .env"
echo "  bash scripts/quickstart.sh     # 采集 + 生成文案模板"
echo
echo "或直接说「做今天的视频」让 Agent 跑完整流程。"
