#!/usr/bin/env bash
# 清除 git 历史中的 B站凭据
#
# 背景：本仓库首个提交起，test_upload.py 里就明文写着
# sessdata / bili_jct / buvid3。该提交已 push 到 GitHub 公开仓库，
# 任何 clone 的人都能拿到这些登录凭据。
#
# 实现方式：**替换凭据值**，而不是删除整个文件。
# 原因：`--invert-paths --path test_upload.py` 会把后续 commit 中
# 「删除该文件」这个改动也一并扭曲 —— 那次重构的主体就包含删除动作。
#
# 不可逆，执行前请确认。
#
# 用法：
#   1) 先吊销凭据（最重要）：在 B 站登出相关设备、重置会话
#   2) bash scripts/purge_bilibili_credentials.sh
#   3) git push --force origin master
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PY="$REPO_ROOT/venv/bin/python"
ORIGIN_URL="$(git remote get-url origin 2>/dev/null || echo '')"
[ -n "$ORIGIN_URL" ] || { echo "✗ 没有 origin 远端"; exit 1; }

echo "=============================================="
echo " 清除 git 历史中的 B站凭据"
echo "=============================================="
echo
echo "远端: $ORIGIN_URL"
echo "警告：不可逆，且需要 force push。"
echo "所有 clone 过此仓库的人都必须重新 clone。"
echo
read -r -p "确认已吊销 B 站凭据并继续？(yes/no) " answer
[ "$answer" = "yes" ] || { echo "已取消"; exit 1; }

# ---------- 备份 ----------
BACKUP="../trending-backup-$(date +%Y%m%d%H%M%S)"
echo
echo "[1/5] 创建本地镜像备份"
git clone --mirror . "$BACKUP" 2>/dev/null
echo "      → $BACKUP"
echo "      回滚：git push --force '$BACKUP' --all"

# ---------- 定位凭据 ----------
# 关键：不能只靠正则。实测踩过的坑——
#   sessdata 值长 222 字符且含 %2C 编码组合，宽松正则只能匹配 0 字符，
#   导致「脚本报告已清理」但实际还有 2 处残留。
# 正确做法：用引号边界精确提取完整字面量，再做 literal 替换。
echo
echo "[2/5] 从历史中精确提取凭据字面量"
"$PY" - <<'PYEOF'
import re
import subprocess

out = subprocess.run(['git', 'log', '-p', '--all'],
                     capture_output=True, text=True).stdout

creds = {}
for key, pat in [
    ('SESSDATA', r"'sessdata':\s*'([^']+)'"),
    ('BILI_JCT', r"'bili_jct':\s*'([^']+)'"),
    ('BUVID3',   r"'buvid3':\s*'([^']+)'"),
]:
    m = re.search(pat, out)
    if m and 'REMOVED' not in m.group(1):
        creds[key] = m.group(1)

with open('/tmp/purge_replace.txt', 'w') as f:
    for k, v in creds.items():
        f.write(f'literal:{v}==>***REMOVED***\n')
        print(f'      {k}: {len(v)} 字符')
    # 正则兜底：覆盖格式不规范的残留
    f.write(r'regex:[0-9a-f]{8}(?:%2C[A-Za-z0-9%_-]+){2,}%2A[A-Za-z0-9%_-]+==>***REMOVED***' + '\n')
    f.write(r'regex:[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}[A-Z]*infoc==>***REMOVED***' + '\n')

print('      未找到明文凭据（可能已清理过）' if not creds else '')
PYEOF

# ---------- 改写 ----------
echo
echo "[3/5] 改写历史"
export PATH="$REPO_ROOT/venv/bin:$PATH"
git filter-repo --replace-text /tmp/purge_replace.txt --force

# filter-repo 会删掉 origin（它的默认行为），必须恢复，否则后续 push 失败
if ! git remote get-url origin >/dev/null 2>&1; then
    git remote add origin "$ORIGIN_URL"
    echo "      已恢复 origin 远端"
fi
rm -f /tmp/purge_replace.txt

# ---------- 校验 ----------
echo
echo "[4/5] 校验历史（不是只看脚本报告）"
REMAINING="$("$PY" - <<'PYEOF'
import re
import subprocess

out = subprocess.run(['git', 'log', '-p', '--all'],
                     capture_output=True, text=True).stdout

bad = []
for name, pat in [
    ('SESSDATA', r"'sessdata':\s*'([^']+)'"),
    ('BILI_JCT', r"'bili_jct':\s*'([^']+)'"),
    ('BUVID3',   r"'buvid3':\s*'([^']+)'"),
]:
    m = re.search(pat, out)
    if m and 'REMOVED' not in m.group(1):
        bad.append(f'{name}({len(m.group(1))}字符)')

for pat, label in [
    (r"[0-9a-f]{8}(?:%2C[A-Za-z0-9%_-]+){2,}%2A[A-Za-z0-9%_-]{40,}", 'URL编码凭据'),
    (r"'bili_jct':\s*'[0-9a-f]{32}'", 'bili_jct'),
]:
    if re.search(pat, out):
        bad.append(label)

print('|'.join(bad) if bad else '')
PYEOF
)"

if [ -z "$REMAINING" ]; then
    echo "      ✓ 历史已彻底脱敏"
else
    echo "      ✗ 仍有残留：$REMAINING"
    echo "        人工检查：git log -p --all | grep -iE 'sessdata|bili_jct|buvid3'"
    exit 1
fi

# ---------- 确认代码没被破坏 ----------
echo
echo "[5/5] 确认代码完好"
if "$PY" -m pytest tests/ -q >/dev/null 2>&1; then
    echo "      ✓ 测试通过"
else
    echo "      ⚠ 测试未通过，请检查是否改写破坏了内容"
fi
if git log --all --oneline -- test_upload.py | grep -q .; then
    echo "      ✓ test_upload.py 仍在历史中（内容已脱敏，结构保留）"
fi

echo
echo "=============================================="
echo " 改写完成，剩余操作："
echo "=============================================="
echo
echo "  git push --force origin master"
echo
echo "注意：用 --force 而非 --force-with-lease ——"
echo "  filter-repo 重写了历史，远端旧 commit 已不在本地，"
echo "  --force-with-lease 会报 'stale info' 而拒绝。"
echo
echo "备份: $BACKUP"
echo "⚠ 确认远端已清除后删除：rm -rf $BACKUP"
