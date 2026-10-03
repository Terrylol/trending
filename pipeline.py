#!/usr/bin/env python3
"""GitHub Trending 视频生成流水线（单命令编排）

用法：
    venv/bin/python pipeline.py                 # 完整流程，生成视频（不上传）
    venv/bin/python pipeline.py --upload        # 生成后上传 B 站
    venv/bin/python pipeline.py --steps fetch,dedupe   # 只跑指定步骤

重构说明：
- 原流程只活在 SKILL.md 散文里，靠 Agent 手动逐步调 CLI。
  现在 5 步串成一个命令，Agent 只需负责"写文案"这一步（需要真实探索项目）。
- 配置文件缺失时显式报错，不再静默降级到默认配置。
- 上传是外部发布动作，默认关闭，必须 --upload 显式开启。
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

from card_generator import CardGenerator, FontError
from history_deduper import repo_id
from trending_fetcher import FetchError, TrendingFetcher
from tts_generator import TTSGenerator
from video_composer import VideoComposer

CONFIG_PATH = ROOT / 'config' / 'config.json'
CONFIG_EXAMPLE = ROOT / 'config' / 'config.example.json'
OUTPUT_DIR = ROOT / 'output'
HISTORY_PATH = ROOT / 'data' / 'projects_history.json'


class Tee:
    """同时输出到 stdout 和日志文件。"""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()


def setup_logging() -> Path:
    logs = OUTPUT_DIR / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_path = logs / f'pipeline_{stamp}_{os.getpid()}.log'
    log_file = log_path.open('a', encoding='utf-8', buffering=1)
    sys.stdout = Tee(sys.__stdout__, log_file)
    sys.stderr = Tee(sys.__stderr__, log_file)
    print(f'[pipeline] 日志: {log_path}')
    return log_path


def load_config() -> Dict:
    """加载配置。缺失时显式报错——静默降级是新用户最难诊断的问题。"""
    if not CONFIG_PATH.exists():
        print('✗ 未找到 config/config.json')
        print(f'  请先复制模板: cp {CONFIG_EXAMPLE.relative_to(ROOT)} config/config.json')
        raise SystemExit(1)

    try:
        config = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        print(f'✗ config/config.json 格式错误: {e}')
        raise SystemExit(1)

    # GitHub Token 支持环境变量覆盖（推荐，避免明文写在配置文件里）
    env_token = os.environ.get('GITHUB_TOKEN')
    if env_token:
        config.setdefault('github', {})['personal_access_token'] = env_token
        print('  · 使用环境变量 GITHUB_TOKEN')

    return config


def run(cmd: List[str], label: str) -> None:
    """执行外部命令，失败直接抛错（不静默继续）。"""
    print(f'  $ {label}')
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        raise RuntimeError(f'{label} 失败（exit {result.returncode}）')


def step_fetch(config: Dict, limit: int) -> List[Dict]:
    print('\n[1/4] 采集 GitHub Trending（三层降级）')
    fetcher = TrendingFetcher({
        **config.get('github', {}),
        'project_root': str(ROOT),
    })
    try:
        projects = fetcher.fetch(limit=limit, since='daily')
    except FetchError as e:
        print(f'✗ 采集失败: {e}')
        raise SystemExit(1)

    out = OUTPUT_DIR / 'trending_candidates.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'projects': projects}, ensure_ascii=False, indent=2),
                   encoding='utf-8')

    source = projects[0].get('data_source', 'unknown')
    print(f'  ✓ 采集 {len(projects)} 个项目（来源: {source}）→ {out.name}')

    # 采集健康度检查：静默失效必须在这里被看见
    total_today = sum(int(p.get('currentPeriodStars') or 0) for p in projects)
    print(f'  · 今日增星总计: {total_today:,}')
    if total_today == 0:
        print('  ⚠ 所有项目的今日增星均为 0，可能解析器已失效')
    return projects


def step_dedupe(limit: int, target: int) -> List[Dict]:
    print(f'\n[2/4] 历史去重（7 天冷却，目标 {target} 个）')
    run([
        'venv/bin/python', 'src/history_deduper.py',
        '--history', str(HISTORY_PATH.relative_to(ROOT)),
        'select',
        '--input', 'output/trending_candidates.json',
        '--output', 'output/trending.json',
        '--target-count', str(target),
        '--cooldown-days', '7',
        '--allow-repeat-if-insufficient',
    ], 'history_deduper select')

    data = json.loads((OUTPUT_DIR / 'trending.json').read_text(encoding='utf-8'))
    projects = data.get('projects', [])
    if not projects:
        print('✗ 去重后无项目，无法继续')
        raise SystemExit(1)

    print(f'  ✓ 选中 {len(projects)} 个项目')
    for i, p in enumerate(projects):
        print(f'     {i + 1}. {p.get("full_name", p.get("name"))}')
    return projects


def step_summarize(projects: List[Dict], target: int) -> List[Dict]:
    """合并采集数据与文案。

    关键：narrative 必须存在，否则语音会是空洞的一句话。
    缺少文案时明确提示，而不是静默产出低质量口播。
    """
    print(f'\n[3/4] 准备文案')
    summary_path = OUTPUT_DIR / 'projects_summary.json'

    if summary_path.exists():
        try:
            data = json.loads(summary_path.read_text(encoding='utf-8'))
            summaries = data.get('projects', [])
        except json.JSONDecodeError:
            summaries = []

        # 按 url 匹配，避免同名仓库串数据
        by_url = {s.get('url'): s for s in summaries if s.get('url')}
        merged = []
        for project in projects:
            url = project.get('url')
            summary = by_url.get(url)
            if summary and (summary.get('narrative') or {}).get('body'):
                item = dict(project)
                item['narrative'] = summary['narrative']
                merged.append(item)
            else:
                item = dict(project)
                item['narrative'] = {}
                merged.append(item)

        missing = [p['full_name'] for p in merged if not p['narrative'].get('body')]
        if not missing:
            print(f'  ✓ 复用已有文案（{len(merged)} 个项目）')
            summary_path.write_text(
                json.dumps({'projects': merged}, ensure_ascii=False, indent=2),
                encoding='utf-8')
            return merged

        # 缺失的文案基于已采集数据自动生成，不再强制人工填写。
        print(f'  · {len(missing)} 个项目缺文案，基于描述自动生成')
        for item in merged:
            if not item['narrative'].get('body'):
                item['narrative'] = auto_narrative(item)

        still_missing = [p['full_name'] for p in merged if not p['narrative'].get('body')]
        summary_path.write_text(
            json.dumps({'projects': merged}, ensure_ascii=False, indent=2),
            encoding='utf-8')

        if still_missing:
            print(f'  ⚠ 仍缺文案（采集数据不足）: {", ".join(still_missing)}')
            raise SystemExit(1)

        print(f'  ✓ 文案就绪（{len(merged)} 个项目）')
        print(f'    如需更好的文案，可编辑 {summary_path.relative_to(ROOT)} 后重跑')
        return merged

    # 首次运行：用采集数据生成初始文案
    if not summary_path.exists():
        generated = [dict(p, narrative=auto_narrative(p)) for p in projects]
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps({'projects': generated}, ensure_ascii=False, indent=2),
            encoding='utf-8')
        print(f'  ✓ 已生成初始文案 {summary_path.relative_to(ROOT)}')
        print('    可直接编辑优化后重跑，或直接继续渲染')
        return generated


def _clean_text(text: str) -> str:
    """清洗描述：去掉 HTML 标签、emoji、多余符号。"""
    text = re.sub(r'<[^>]+>', ' ', text or '')
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[\U0001F300-\U0001FAFF☀-➿]', '', text)
    text = re.sub(r'[^\w\s一-鿿,.!?、。，！？：:；;\-—()]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _is_chinese(text: str) -> bool:
    return bool(re.search(r'[一-鿿]', text or ''))


def _en_to_zh_summary(desc: str, name: str, language: str,
                      topics: List[str]) -> str:
    """描述是英文时的兜底文案。

    不做机器翻译（会引入不可靠的翻译质量），而是根据英文描述的结构
    提取可信信息，用中文重新组织成一段介绍。topic 只用来判断项目类型，
    不直接罗列 —— 英文 topic（agent-infrastructure 之类）放进中文句子
    会导致断行混乱，且信息价值低。
    """
    lowered = desc.lower()
    lowered_topics = ' '.join(topics).lower()

    if 'skill' in lowered or 'agent' in lowered_topics:
        parts = ['这是一个面向 AI 智能体的工具']
    elif 'design' in lowered:
        parts = ['这是一个前端设计方向的工具']
    elif 'library' in lowered or 'production-ready' in lowered or 'production-ready' in lowered:
        parts = ['这是一个用于构建生产级应用的库']
    elif 'proxy' in lowered or 'token' in lowered:
        parts = ['这是一个 AI 工具链的优化工具']
    elif 'cli' in lowered or 'tui' in lowered:
        parts = ['这是一个命令行工具']
    else:
        parts = ['这是一个开源项目']

    parts.append(f'用 {language} 编写')

    return '，'.join(parts) + '。'


def auto_narrative(project: Dict) -> Dict[str, str]:
    """基于采集到的真实数据自动生成项目介绍。

    只用 description / language / star 数 / topics，无需逐个项目深度研究。
    中文描述直接用，英文描述转为可信的中文概述（不做机器翻译）。
    """
    name = project.get('name', '')
    desc = _clean_text(project.get('description', ''))
    language = project.get('language') or '多种语言'
    stars = int(project.get('stars') or 0)
    forks = int(project.get('forks') or 0)
    today = int(project.get('currentPeriodStars') or 0)
    topics = [t for t in (project.get('topics') or []) if isinstance(t, str)]

    # hook：用最能抓眼的数据开场
    if today >= 500:
        hook = f'一天涨了 {today:,} 星，现在有 {stars:,} 人关注。'
    elif today > 0:
        hook = f'今天新增 {today:,} 星，累计 {stars:,}。'
    else:
        hook = f'{stars:,} 星的项目，{language} 写的。'

    # body：中文描述直接用；英文描述转成中文概述
    if desc and _is_chinese(desc):
        intro = desc
        if not intro.endswith(('。', '！', '？', '.')):
            intro += '。'
    else:
        intro = _en_to_zh_summary(desc, name, language, topics)

    detail = [f'{stars:,} 星']
    if forks:
        detail.append(f'{forks:,} 个 fork')
    parts = [intro, f'目前 {"，".join(detail)}。']

    if today > 0:
        parts.append(f'今天单日新增 {today:,} 星。')

    body = ''.join(parts)
    # 在句子边界截断，避免断在半个词上
    if len(body) > 170:
        cut = body[:170]
        for sep in ('。', '，'):
            pos = cut.rfind(sep)
            if pos > 100:
                cut = cut[:pos + 1]
                break
        body = cut

    cta = f'完整介绍看 README，仓库地址在简介里。'

    return {'hook': hook, 'body': body, 'call_to_action': cta}


def step_render(config: Dict, projects: List[Dict]) -> str:
    print('\n[4/4] 生成视频')
    video_config = config.get('video', {})
    tts_config = config.get('tts', {})

    date_display = datetime.now().strftime('%Y.%m.%d')
    source = projects[0].get('data_source', 'github_trending')
    source_label = {
        'github_trending': '数据来源: GitHub 官方 Trending',
        'search_api': '数据来源: GitHub Search API 增速榜（非官方日榜）',
        'cache': '数据来源: 本地缓存（非最新）',
    }.get(source, '数据来源: 未知')

    card_config = {
        'resolution': video_config.get('resolution', '1920x1080'),
        'output_dir': str(OUTPUT_DIR),
        'star_history': config.get('star_history', {}),
    }

    try:
        cards = CardGenerator(card_config)
    except FontError as e:
        print(f'✗ {e}')
        raise SystemExit(1)

    # 语音（greeting 同时用于片头画面和语音，两处保持一致）
    tts_config = {**config.get('tts', {}), 'output_dir': str(OUTPUT_DIR)}
    tts = TTSGenerator(tts_config)
    greeting = tts.pick_greeting()
    print(f'  · 片头问候语: {greeting}')
    audio_files = tts.generate_all_audio(projects, greeting=greeting)

    # Star 趋势图并发预取（有硬超时，不阻塞渲染）。
    # star-history 对超大仓库（如 27 万星的 ECC）会返回 1360 字节的错误页，
    # 此时显示占位而不是假曲线。SVG 体积可达 60KB+，超时给足 20s。
    star_config = config.get('star_history', {})
    star_images = cards.prefetch_star_histories(
        projects,
        timeout=int(star_config.get('timeout', 20)),
        concurrency=int(star_config.get('concurrency', 2)),
    )
    print(f'  · Star 趋势图获取 {len(star_images)}/{len(projects)}'
          f'（失败项显示占位，不使用推测数据）')

    # 卡片
    slides = []
    title_slide = OUTPUT_DIR / 'slide_title.png'
    cards.generate_title_card(date_display, str(title_slide),
                              greeting=greeting, source_label=source_label)
    slides.append(str(title_slide))

    for i, project in enumerate(projects):
        slide = OUTPUT_DIR / f'slide_{i}.png'
        key = project.get('full_name') or project.get('url', '')
        cards.generate_project_card(
            project, i, str(slide),
            star_history_image=star_images.get(key, ''),
        )
        slides.append(str(slide))

    ending_slide = OUTPUT_DIR / 'slide_ending.png'
    cards.generate_ending_card(str(ending_slide))
    slides.append(str(ending_slide))
    print(f'  ✓ 卡片生成完成，共 {len(slides)} 张')

    # B站封面：缺失会直接影响推荐量，所以单独生成
    cover_path = OUTPUT_DIR / 'cover.png'
    cards.generate_cover(date_display, str(cover_path), projects=projects)
    print(f'  ✓ 封面: {cover_path.name}')

    # 合成
    composer = VideoComposer({
        'fps': int(video_config.get('fps', 24)),
        'resolution': video_config.get('resolution', '1920x1080'),
        'output_dir': str(OUTPUT_DIR),
    })
    output_path = OUTPUT_DIR / 'trending_video.mp4'
    composer.compose(
        slides, audio_files, str(output_path),
        animate=bool(video_config.get('animate', True)),
    )
    return str(output_path)


def step_upload(projects: List[Dict]) -> None:
    """上传前必须做完整性校验——这是外部发布动作的最后一道闸。"""
    print('\n[附加] 上传 B 站')

    video_path = OUTPUT_DIR / 'trending_video.mp4'
    if not video_path.exists():
        print('✗ 视频文件不存在，拒绝上传')
        raise SystemExit(1)

    size_mb = video_path.stat().st_size / 1024 / 1024
    print(f'  · 视频大小 {size_mb:.1f} MB')

    if len(projects) < 3:
        print(f'✗ 仅 {len(projects)} 个项目，拒绝上传（内容可能不完整）')
        raise SystemExit(1)

    if not (OUTPUT_DIR / 'cover.png').exists():
        print('✗ 封面不存在，拒绝上传（无封面不会有推荐量）')
        raise SystemExit(1)

    # 凭据校验交给 BilibiliUploader（它读环境变量 + 配置，且只在一处判断）
    config = load_config()
    from bilibili_uploader import BilibiliUploader
    import asyncio

    try:
        uploader = BilibiliUploader(config.get('bilibili', {}))
    except ValueError as e:
        print(f'✗ {e}')
        raise SystemExit(1)

    result = asyncio.run(uploader.upload(str(video_path), projects))
    if not result:
        raise SystemExit('✗ 上传未返回结果')

    print(f'  ✓ 上传成功: {result.get("title")}')
    # bvid 是确认发了什么的唯一凭据 —— 拿不到就无法核对与后续管理
    url = result.get('url')
    if url:
        print(f'    {url}')
        record = OUTPUT_DIR / 'last_upload.json'
        record.write_text(json.dumps({
            'bvid': result.get('bvid'),
            'aid': result.get('aid'),
            'title': result.get('title'),
            'url': url,
            'uploaded_at': datetime.now().isoformat(timespec='seconds'),
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'    记录: {record.relative_to(ROOT)}')
    else:
        print('    ⚠ 未拿到 BV 号，无法确认投稿内容')


def update_history(status: str) -> None:
    result = subprocess.run([
        'venv/bin/python', 'src/history_deduper.py',
        '--history', str(HISTORY_PATH.relative_to(ROOT)),
        'status', '--status', status,
    ], cwd=ROOT, capture_output=True, text=True)
    if result.returncode == 0:
        print(f'  ✓ 历史状态已更新: {status}')
    else:
        print(f'  ⚠ 历史状态更新失败: {result.stdout.strip()}')


def main() -> int:
    parser = argparse.ArgumentParser(
        description='GitHub Trending 视频生成流水线',
        epilog='''
典型用法：
  %(prog)s --draft          只采集 + 生成文案模板，不渲染（攒素材）
  （编辑 output/projects_summary.json 的 narrative 后）
  %(prog)s                 渲染出视频
  %(prog)s --upload        渲染后上传 B 站

文案质量说明：auto_narrative 是规则式兜底，上限有限。
想要"这项目是干什么的"这种内容，编辑 projects_summary.json 的 narrative 字段，
或让 Agent 读 README 后填写 —— 采集到的 readme/topics 字段已经足够。
        ''')
    parser.add_argument('--upload', action='store_true',
                        help='生成后上传到 B 站（外部发布动作，默认不上传）')
    parser.add_argument('--draft', action='store_true',
                        help='只采集 + 生成文案模板，不配音不渲染')
    parser.add_argument('--limit', type=int, default=None, help='采集候选数量')
    parser.add_argument('--target', type=int, default=None, help='最终视频内项目数')
    parser.add_argument('--skip-dedupe', action='store_true', help='跳过历史去重')
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    setup_logging()
    config = load_config()

    video_config = config.get('video', {})
    limit = args.limit or int(video_config.get('limit', 15))
    target = args.target or int(video_config.get('target_count', 5))

    print('=' * 64)
    print('GitHub Trending 视频生成流水线')
    print('=' * 64)
    print(f'  分辨率: {video_config.get("resolution", "1920x1080")} @ {video_config.get("fps", 24)}fps')
    print(f'  TTS: {config.get("tts", {}).get("engine", "edge")}')
    print(f'  模式: {"草稿（不渲染）" if args.draft else "完整渲染"}')
    print(f'  上传: {"是" if args.upload else "否"}')
    print('=' * 64)

    if args.draft and args.upload:
        print('✗ --draft 与 --upload 不能同时使用（草稿不产出视频）')
        return 1

    try:
        step_fetch(config, limit)

        if args.skip_dedupe:
            data = json.loads((OUTPUT_DIR / 'trending_candidates.json').read_text(encoding='utf-8'))
            projects = data['projects'][:target]
            (OUTPUT_DIR / 'trending.json').write_text(
                json.dumps({'projects': projects}, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'\n[2/4] 跳过去重，直接取前 {len(projects)} 个')
        else:
            projects = step_dedupe(limit, target)

        projects = step_summarize(projects, target)

        if args.draft:
            print('\n' + '=' * 64)
            print('✓ 草稿完成（未渲染）')
            print(f'  文案: output/projects_summary.json')
            print(f'  素材: output/trending.json（含 readme / topics / preview_image）')
            print('=' * 64)
            print('\n下一步：编辑 projects_summary.json 的 narrative 字段后运行')
            print(f'  {sys.executable} pipeline.py')
            # 草稿模式不改历史状态，避免把"未产出视频"记成成功
            return 0

        video_path = step_render(config, projects)
    except SystemExit:
        raise
    except Exception as e:
        print(f'\n✗ 流水线失败: {e}')
        update_history('failed')
        return 1

    print('\n' + '=' * 64)
    print('✓ 视频生成完成')
    print(f'  {video_path}')
    if video_path:
        size_mb = Path(video_path).stat().st_size / 1024 / 1024
        print(f'  大小: {size_mb:.1f} MB')
    print('=' * 64)

    update_history('video_succeeded')

    if args.upload:
        step_upload(projects)
        update_history('upload_succeeded')
    else:
        print('\n提示: 如需上传 B 站，加 --upload 参数')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
