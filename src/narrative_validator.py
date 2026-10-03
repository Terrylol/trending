"""文案质量校验

为什么需要这个：`auto_narrative` 是规则式兜底，对任何 AI 工具都会输出
「这是一个面向 AI 智能体的工具」这类套话。人工/Agent 写的文案也可能偷懒
复述屏幕已有的数字（星标数、日增数），这在视频里是零信息增量 ——
观众的眼睛已经在屏幕右边看到那些数字了。

校验不追求文学性，只卡三件事：
1. 该说的说没说（说清项目是干什么的）
2. 有没有在复述屏幕数字（无效内容）
3. 字数是否够（不够就撑不起 30 秒口播）
"""
import re
from typing import Dict, List

# 各字段的建议字数区间（按 edge-tts 1.3 倍速 ≈ 每秒 4.5 字估算）
LENGTH_RULES = {
    'hook': (15, 40),
    'body': (110, 190),
    'call_to_action': (12, 35),
}

# 口播总字数下限：低于此值撑不起 25 秒片段
MIN_TOTAL = 140

# 复述数字的模式：hook 里只有数字 = 无信息
NUMBER_ONLY = re.compile(r'^[\d\s,、.＋+第个项目的是\-]+$')
HAS_DIGIT = re.compile(r'\d')

# 套话模板：这些句式说明没读 README
CLICHES = [
    '这是一个开源项目',
    '这是一个工具',
    '用.{0,12}编写',
    '目前.{0,20}星',
    '个fork',
    '个 fork',
    '今日新增',
    '今天新增',
    '日增',
]

# 说明项目用途的高质量信号（出现任意一个即认为说清了"干什么"）
PURPOSE_SIGNALS = [
    '解决', '让你', '帮你', '把', '帮', '用于', '用来', '支持',
    '可以', '能够', '负责', '代替', '省', '免', '不用', '自动',
    '从', '到', '接入', '生成', '管理', '控制', '记录', '压缩',
    '让', '使', '提供', '实现', '做', '跑', '抓', '读',
]


class NarrativeIssue(Exception):
    """文案质量不达标。message 里列出所有问题。"""

    def __init__(self, issues: List[str]):
        self.issues = issues
        super().__init__('；'.join(issues))


def validate_project(project: Dict, *, strict: bool = True) -> List[str]:
    """校验单个项目的文案，返回问题列表（空列表 = 通过）。"""
    issues = []
    narrative = project.get('narrative') or {}

    for field, (lo, hi) in LENGTH_RULES.items():
        text = (narrative.get(field) or '').strip()
        if not text:
            issues.append(f'{field} 为空')
            continue
        if len(text) < lo:
            issues.append(f'{field} 太短（{len(text)} 字，建议 {lo}-{hi}）')
        elif len(text) > hi:
            issues.append(f'{field} 太长（{len(text)} 字，建议 {lo}-{hi}）')

    hook = (narrative.get('hook') or '').strip()
    body = (narrative.get('body') or '').strip()

    # hook 只有数字 = 零信息
    if hook and NUMBER_ONLY.match(hook):
        issues.append('hook 只有数字，没有信息量')

    # body 复述屏幕数字 = 零信息增量
    if body:
        # 去掉数字和标点后，看还剩多少实质文字。
        # 注意要去掉英文标签词（stars/forks/MIT/Python 之类），
        # 否则 "89,533 stars, 7,877 forks, MIT, Python" 去掉数字后
        # 还剩 12 个字母，会被误判为"有内容"。
        stripped = re.sub(r'[\d,，.。、:：;；()（）%+-]+', '', body)
        stripped = re.sub(
            r'\b(stars?|forks?|watch|issues?|license|spdx|mit|apache|bsd|gpl)\b',
            '', stripped, flags=re.I)
        stripped = re.sub(r'\b[A-Za-z0-9+#.-]{1,20}\b', '', stripped)  # 其余英文词
        stripped = re.sub(r'[\s,，.。、:：;；()（）%+和与的]+', '', stripped)
        if len(stripped) < 40:
            issues.append(
                f'body 有效内容过少（去掉数字和标签后仅剩 {len(stripped)} 字），'
                f'缺少对项目的介绍')

    if not strict:
        return issues

    # 套话检测：body 里出现「用 X 编写」且没有其他实质描述
    if body:
        cliches = [c for c in CLICHES if re.search(c, body)]
        # 「用 X 编写」单独出现时算套话
        if any('编写' in c for c in cliches):
            meaningful = re.sub(r'用[^，。]{0,12}编写[，。]?', '', body)
            meaningful = re.sub(r'[\d,，.。、:：;；()（）%+和与的\s]+', '', meaningful)
            if len(meaningful) < 45:
                issues.append('body 是「用 X 编写」式套话，没有说明项目做什么')

        # 完全没有意图动词 → 大概率只是描述性堆砌
        if not any(re.search(sig, body) for sig in PURPOSE_SIGNALS):
            issues.append('body 没有说明项目能做什么（缺少「解决/让你/帮你/支持」这类表述）')

    return issues


def validate_all(projects: List[Dict], *, strict: bool = True) -> Dict[str, List[str]]:
    """校验所有项目，返回 {项目名: [问题]}。空字典 = 全部通过。"""
    result = {}
    for p in projects:
        issues = validate_project(p, strict=strict)
        if issues:
            result[p.get('full_name') or p.get('name', '?')] = issues
    return result


def summarize_duration(projects: List[Dict]) -> float:
    """估算成片时长（秒）。按 edge-tts 1.3 倍速约 4.5 字/秒。"""
    chars_per_second = 4.5
    total = 0.0
    for p in projects:
        n = p.get('narrative') or {}
        total += sum(len(n.get(k) or '') for k in LENGTH_RULES)
    return total / chars_per_second


def main() -> int:
    """CLI 入口：venv/bin/python -m src.narrative_validator <summary.json>"""
    import argparse
    import json
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description='文案质量校验：拦套话、拦数字复述、查字数')
    parser.add_argument('summary', nargs='?', default='output/projects_summary.json',
                        help='projects_summary.json 路径')
    parser.add_argument('--lenient', action='store_true',
                        help='只查字数，不查套话')
    parser.add_argument('--quiet', action='store_true', help='只输出结论')
    args = parser.parse_args()

    path = Path(args.summary)
    if not path.exists():
        print(f'✗ 文件不存在: {path}', file=sys.stderr)
        return 2

    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        print(f'✗ JSON 格式错误: {e}', file=sys.stderr)
        return 2

    projects = data.get('projects', [])
    if not projects:
        print(f'✗ {path} 里没有项目', file=sys.stderr)
        return 2

    result = validate_all(projects, strict=not args.lenient)

    if not args.quiet:
        print(f'校验 {len(projects)} 个项目的文案\n')

    if result:
        print(f'✗ {len(result)}/{len(projects)} 个项目不达标\n')
        for name, issues in result.items():
            print(f'  {name}')
            for issue in issues:
                print(f'    - {issue}')
            print()
        print('修改建议：body 要回答「这项目是干什么的」，')
        print('          不要复述卡片上已有的星标数 / fork 数 / 日增数。')
        return 1

    duration = summarize_duration(projects)
    print(f'✓ 全部通过（{len(projects)} 个项目）')
    print(f'  预计口播时长: {duration:.0f} 秒')
    if duration < 120:
        print(f'  ⚠ 口播偏短（{duration:.0f}s），撑不起 3 分钟视频')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
