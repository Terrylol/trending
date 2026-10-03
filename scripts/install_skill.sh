#!/usr/bin/env bash
# 把本项目注册为 WorkBuddy Skill
#
# 采用软链而非复制：项目代码保持单一来源，改完立刻生效，
# 不会出现「skill 目录里的代码和项目目录不一致」的问题。
#
# 用法：
#   bash scripts/install_skill.sh            # 安装（已安装则提示）
#   bash scripts/install_skill.sh --force    # 覆盖已有软链
#   bash scripts/install_skill.sh --uninstall # 卸载
#   bash scripts/install_skill.sh --status   # 查看状态
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_DIR="${WORKBUDDY_SKILLS_DIR:-$HOME/.workbuddy/skills}"
SKILL_NAME="github-trending-video"
LINK="$SKILLS_DIR/$SKILL_NAME"

FORCE=0
UNINSTALL=0
STATUS_ONLY=0
for arg in "$@"; do
    case "$arg" in
        --force) FORCE=1 ;;
        --uninstall) UNINSTALL=1 ;;
        --status) STATUS_ONLY=1 ;;
        *) echo "未知参数: $arg"; exit 2 ;;
    esac
done

show_status() {
    echo "Skill 目录: $SKILLS_DIR"
    echo "Skill 名称: $SKILL_NAME"
    echo "项目位置:   $ROOT"
    echo
    if [ -L "$LINK" ]; then
        target="$(readlink "$LINK")"
        if [ -d "$LINK" ]; then
            echo "状态: ✓ 已安装（软链）"
            echo "  → $target"
            [ -f "$LINK/SKILL.md" ] && echo "  ✓ SKILL.md 存在" || echo "  ✗ SKILL.md 缺失"
            [ -d "$LINK/scripts" ] && echo "  ✓ scripts/ 存在" || echo "  ✗ scripts/ 缺失"
            [ -x "$LINK/venv/bin/python" ] && echo "  ✓ venv 就绪" || echo "  ⚠ venv 未初始化（跑 bootstrap.sh）"
        else
            echo "状态: ✗ 软链失效（目标不存在）"
            echo "  → $target"
        fi
    elif [ -d "$LINK" ]; then
        echo "状态: ⚠ 是真实目录，不是软链"
        echo "  内容: $(ls "$LINK" | tr '\n' ' ')"
        echo "  建议: 备份后删除，改用软链"
    else
        echo "状态: ✗ 未安装"
    fi
}

if [ "$STATUS_ONLY" = "1" ]; then
    show_status
    exit 0
fi

if [ "$UNINSTALL" = "1" ]; then
    if [ -L "$LINK" ]; then
        rm "$LINK"
        echo "✓ 已卸载（软链已删除，项目文件未受影响）"
    elif [ -d "$LINK" ]; then
        echo "✗ $LINK 是真实目录，未删除。请手动处理："
        echo "  ls -la '$LINK'"
    else
        echo "· 未安装，无需卸载"
    fi
    exit 0
fi

# ---------- 安装 ----------
mkdir -p "$SKILLS_DIR"

if [ -e "$LINK" ] || [ -L "$LINK" ]; then
    if [ "$FORCE" != "1" ]; then
        echo "✗ $LINK 已存在"
        echo "  覆盖：bash scripts/install_skill.sh --force"
        echo "  卸载：bash scripts/install_skill.sh --uninstall"
        exit 1
    fi
    if [ -d "$LINK" ] && [ ! -L "$LINK" ]; then
        echo "✗ $LINK 是真实目录，--force 不会覆盖以免丢数据"
        echo "  请手动处理后重试"
        exit 1
    fi
    rm -f "$LINK"
    echo "已移除旧软链"
fi

ln -s "$ROOT" "$LINK"
echo "✓ 已安装软链：$LINK"
echo "  → $ROOT"
echo

# 自检
if [ ! -f "$LINK/SKILL.md" ]; then
    echo "✗ 安装后找不到 SKILL.md，软链可能有问题"
    exit 1
fi

# 提示未初始化的环境
if [ ! -d "$ROOT/venv" ]; then
    echo
    echo "⚠ 项目尚未初始化环境，请运行："
    echo "  bash scripts/bootstrap.sh"
fi

echo
echo "使用方式："
echo "  在 WorkBuddy 里说「做今天的视频」即可触发"
echo "  或指定触发词：做今天的视频 / GitHub 热榜 / trending 视频 / 出今天的视频"
echo
echo "查看状态：bash scripts/install_skill.sh --status"
echo "卸载：    bash scripts/install_skill.sh --uninstall"
