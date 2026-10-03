#!/usr/bin/env bash
# 清除 git 历史中的 B站凭据
#
# 背景：本仓库首个提交 6467e5c 起，test_upload.py 里就明文写着
# sessdata / bili_jct / buvid3。该提交已 push 到 GitHub 公开仓库，
# 任何 clone 的人都能拿到这些登录凭据。
#
# 这个脚本用 git filter-repo 从所有提交中移除该文件的敏感内容。
# 不可逆，执行前请确认。
#
# 用法：
#   1) 先吊销凭据（最重要）：在 B 站登出相关设备、重置会话
#   2) pip install git-filter-repo
#   3) bash scripts/purge_bilibili_credentials.sh
#   4) git push --force-with-lease origin master
#   5) 通知所有 clone 过此仓库的人重新 clone（历史仍可能被 GitHub 缓存）
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=============================================="
echo " 清除 git 历史中的 B站凭据"
echo "=============================================="
echo
echo "警告：这是不可逆操作，且需要 force push。"
echo "所有 clone 过此仓库的人都必须重新 clone。"
echo
read -r -p "确认已吊销 B 站凭据并继续？(yes/no) " answer
[ "$answer" = "yes" ] || { echo "已取消"; exit 1; }

# 备份（仅本地，务必在确认改写成功后删除）
BACKUP="../trending-backup-$(date +%Y%m%d%H%M%S)"
echo
echo "[1/5] 创建本地备份: $BACKUP"
git clone --mirror . "$BACKUP" 2>/dev/null
echo "      备份完成。若改写出错可用 git push --force \"$BACKUP\" --all"

echo "[2/5] 检查依赖"
if ! command -v git-filter-repo >/dev/null 2>&1 && ! git filter-repo --help >/dev/null 2>&1; then
    echo "      未安装 git-filter-repo，尝试安装"
    venv/bin/pip install git-filter-repo 2>/dev/null || pip3 install --user git-filter-repo
    export PATH="$PATH:$HOME/Library/Python/3.13/bin"
fi

echo "[3/5] 从全部 20 个提交中移除 test_upload.py"
# --invert-paths 表示"删除"这个文件（而不是保留它）
git filter-repo --invert-paths --path test_upload.py --force

echo "[4/5] 校验历史中不再有凭据"
if git log -p --all 2>/dev/null | grep -iE 'sessdata|bili_jct|buvid3' | grep -vE 'YOUR_|SESSDATA|BILI_JCT|BUVID3|sessdata/BILIBILI' | head -5 | grep -q .; then
    echo "      ⚠ 仍检测到疑似凭据，请手动检查：git log -p --all | grep -i sessdata"
else
    echo "      ✓ 历史中已无明文凭据"
fi

echo "[5/5] 后续操作"
echo
echo "  git push --force-with-lease origin master"
echo
echo "  备份位置: $BACKUP"
echo "  ⚠ 确认远端已清除后，删除备份：rm -rf $BACKUP"
