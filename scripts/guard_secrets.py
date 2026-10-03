#!/usr/bin/env python3
"""pre-commit 钩子：拦截敏感凭据进入 git 历史。

背景：本仓库曾把 B站 SESSDATA 明文提交在 test_upload.py 中，且从首个提交
起就存在于历史里。任何 clone 都能拿到登录态。此钩子防止复发。

安装：ln -s ../../scripts/guard_secrets.py .git/hooks/pre-commit
或手动复制到 .git/hooks/pre-commit 并 chmod +x
"""
import re
import subprocess
import sys
from pathlib import Path

# 明确不检查的文件（模板、示例、本文件自身）
EXCLUDE_NAMES = {'config.example.json', 'guard_secrets.py', '.env.example'}

# 高置信度密钥模式：命中即阻断
PATTERNS = [
    (re.compile(r'sessdata\s*[=:]\s*["\']?[A-Za-z0-9%_\-]{20,}', re.I),
     'B站 SESSDATA'),
    (re.compile(r'bili_jct\s*[=:]\s*["\']?[a-f0-9]{32}', re.I),
     'B站 bili_jct'),
    (re.compile(r'buvid3\s*[=:]\s*["\']?[A-F0-9\-]{20,}', re.I),
     'B站 buvid3'),
    (re.compile(r'\bghp_[A-Za-z0-9]{36}\b'),
     'GitHub Personal Access Token'),
    (re.compile(r'\bgithub_pat_[A-Za-z0-9_]{50,}\b'),
     'GitHub Fine-grained Token'),
    (re.compile(r'\bsk-[A-Za-z0-9]{32,}\b'),
     'OpenAI 风格 API Key'),
    (re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
     'AWS Access Key ID'),
    # 占位值不算密钥
]

PLACEHOLDERS = {'YOUR_', 'xxx', 'your_', '<', 'PLACEHOLDER'}


def is_placeholder(line: str) -> bool:
    lowered = line.lower()
    return any(p in lowered for p in PLACEHOLDERS)


def staged_files() -> list:
    try:
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM'],
            capture_output=True, text=True, timeout=30,
        )
        return [f for f in result.stdout.split() if f.strip()]
    except (subprocess.SubprocessError, FileNotFoundError):
        return []


def scan(path: Path) -> list:
    try:
        content = path.read_text(encoding='utf-8', errors='ignore')
    except OSError:
        return []

    findings = []
    for lineno, line in enumerate(content.splitlines(), 1):
        if is_placeholder(line):
            continue
        for pattern, label in PATTERNS:
            if pattern.search(line):
                # 只报告位置和类型，绝不回显凭据原文
                findings.append(f'  {path}:{lineno} 疑似 {label}')
    return findings


def main() -> int:
    files = staged_files()
    if not files:
        return 0

    findings = []
    for name in files:
        path = Path(name)
        if path.name in EXCLUDE_NAMES or not path.is_file():
            continue
        findings.extend(scan(path))

    if findings:
        print('\n✗ 提交被拦截：检测到敏感凭据\n', file=sys.stderr)
        for item in findings:
            print(item, file=sys.stderr)
        print(
            '\n处理方式：\n'
            '  1. 不要把凭据写进文件——用环境变量\n'
            '     export GITHUB_TOKEN=xxx\n'
            '     export BILIBILI_SESSDATA=xxx\n'
            '  2. 如果这是误报，确认不是占位值后可用 --no-verify 跳过\n'
            '  3. 若凭据已提交过，仅删除文件不够，必须重写 git 历史\n',
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
