"""纯函数单元测试（零外部依赖，pytest 可直接跑）"""
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

from card_generator import CardGenerator
from history_deduper import (
    repo_id,
    parse_day,
    select_projects,
    successful_selected_in_window,
)
from narrative_validator import (
    MIN_TOTAL,
    summarize_duration,
    validate_all,
    validate_project,
)
from pipeline import auto_narrative, _clean_text
from trending_fetcher import TrendingFetcher
from video_composer import FADE_IN, FADE_OUT, ZOOM_RATIO, VideoComposer


class TempDir:
    """项目内临时目录。不用 pytest 的 tmp_path —— 部分沙箱环境下
    /tmp 的 pytest 临时目录不可写。"""

    def __enter__(self):
        self.path = Path(tempfile.mkdtemp(prefix='trending_test_',
                                          dir=Path(__file__).resolve().parent.parent))
        return self.path

    def __exit__(self, *exc):
        shutil.rmtree(self.path, ignore_errors=True)


# ---------- repo_id ----------

def test_repo_id_from_author_name():
    assert repo_id({'author': 'foo', 'name': 'bar'}) == 'foo/bar'


def test_repo_id_from_owner_name():
    assert repo_id({'owner': 'foo', 'name': 'bar'}) == 'foo/bar'


def test_repo_id_from_url_when_no_author():
    assert repo_id({'url': 'https://github.com/foo/bar'}) == 'foo/bar'


def test_repo_id_returns_none_when_nothing_usable():
    assert repo_id({'name': 'bar'}) is None
    assert repo_id({}) is None


# ---------- parse_day ----------

def test_parse_day_passthrough():
    assert parse_day('2026-10-03') == '2026-10-03'


def test_parse_day_rejects_bad_format():
    try:
        parse_day('2026/10/03')
    except ValueError:
        return
    raise AssertionError('非法日期格式应当抛 ValueError')


# ---------- successful_selected_in_window ----------

def test_window_excludes_today():
    history = {'runs': {'2026-10-03': {'status': 'video_succeeded', 'selected': ['a/b']}}}
    assert successful_selected_in_window(history, '2026-10-03', 7) == set()


def test_window_excludes_failed_runs():
    history = {'runs': {'2026-10-01': {'status': 'failed', 'selected': ['a/b']}}}
    assert successful_selected_in_window(history, '2026-10-03', 7) == set()


def test_window_includes_recent_success():
    history = {'runs': {'2026-10-01': {'status': 'video_succeeded', 'selected': ['a/b']}}}
    assert successful_selected_in_window(history, '2026-10-03', 7) == {'a/b'}


def test_window_excludes_older_than_cooldown():
    history = {'runs': {'2026-08-01': {'status': 'upload_succeeded', 'selected': ['a/b']}}}
    assert successful_selected_in_window(history, '2026-10-03', 7) == set()


def test_window_skips_malformed_day_key():
    history = {'runs': {'not-a-date': {'status': 'video_succeeded', 'selected': ['a/b']}}}
    assert successful_selected_in_window(history, '2026-10-03', 7) == set()


# ---------- select_projects ----------

def _p(name):
    return {'author': name.split('/')[0], 'name': name.split('/')[1], 'url': f'https://github.com/{name}'}


def test_select_picks_in_order_without_dedupe():
    projects = [_p('a/1'), _p('b/2'), _p('c/3')]
    selected, fetched, selected_ids, skipped = select_projects(projects, set(), 2, False)
    assert [p['name'] for p in selected] == ['1', '2']
    assert selected_ids == ['a/1', 'b/2']
    assert skipped == []


def test_select_skips_deduped():
    projects = [_p('a/1'), _p('b/2'), _p('c/3')]
    selected, _, selected_ids, skipped = select_projects(projects, {'a/1'}, 2, False)
    assert selected_ids == ['b/2', 'c/3']
    assert skipped == ['a/1']


def test_select_backfill_removes_from_skipped():
    """回归测试：补足时同一 repo 不能同时出现在 selected 和 skipped_duplicates。"""
    projects = [_p('a/1'), _p('b/2')]
    selected, _, selected_ids, skipped = select_projects(projects, {'a/1', 'b/2'}, 2, True)

    assert selected_ids == ['a/1', 'b/2']
    # 关键断言：两者不该重叠
    assert not set(selected_ids) & set(skipped), \
        f'selected 与 skipped_duplicates 不应重叠，实测 {selected_ids} vs {skipped}'


def test_select_without_allow_repeat_returns_fewer():
    projects = [_p('a/1'), _p('b/2')]
    selected, _, selected_ids, skipped = select_projects(projects, {'a/1', 'b/2'}, 5, False)
    assert selected == []
    assert skipped == ['a/1', 'b/2']


def test_select_ignores_projects_without_id():
    projects = [{'name': 'noid'}, _p('b/2')]
    selected, fetched, selected_ids, _ = select_projects(projects, set(), 5, False)
    assert fetched == ['b/2']
    assert selected_ids == ['b/2']


# ---------- TrendingFetcher 健康度断言 ----------

def _healthy():
    return [{'name': f'p{i}', 'stars': 100, 'currentPeriodStars': 10} for i in range(5)]


def test_assert_healthy_passes():
    TrendingFetcher({})._assert_healthy(_healthy())


def test_assert_rejects_empty_list():
    try:
        TrendingFetcher({})._assert_healthy([])
    except ValueError as e:
        assert '空列表' in str(e)
        return
    raise AssertionError('空列表应当被拒绝——这正是静默产出 Top 0 视频的根因')


def test_assert_rejects_insufficient_count():
    try:
        TrendingFetcher({})._assert_healthy(_healthy()[:3])
    except ValueError as e:
        assert '最低要求' in str(e)
        return
    raise AssertionError('项目数不足应当被拒绝')


def test_assert_rejects_all_zero_period_stars():
    """回归测试：GitHub 改版导致 stars today 解析失效时，19 个项目全 0，必须拦下。"""
    projects = [{'name': f'p{i}', 'stars': 100, 'currentPeriodStars': 0} for i in range(10)]
    try:
        TrendingFetcher({})._assert_healthy(projects)
    except ValueError as e:
        assert '日增 star' in str(e)
        return
    raise AssertionError('日增 star 全为 0 应当被拒绝')


def test_assert_rejects_all_zero_stars():
    projects = [{'name': f'p{i}', 'stars': 0, 'currentPeriodStars': 5} for i in range(5)]
    try:
        TrendingFetcher({})._assert_healthy(projects)
    except ValueError as e:
        assert '星标' in str(e) or 'star' in str(e)
        return
    raise AssertionError('star 总数全 0 应当被拒绝')


# ---------- 数字解析（容忍 12k 缩写）----------

def test_parse_count_handles_k_suffix():
    f = TrendingFetcher({})
    class FakeArticle:
        @staticmethod
        def find(*args, **kwargs):
            class A:
                @staticmethod
                def get_text(*a, **k):
                    return '12k'
            return A()
    assert f._parse_count(FakeArticle(), r'/stargazers') == 12000


def test_to_int_strips_commas():
    assert TrendingFetcher._to_int('1,289') == 1289


# ---------- Star 曲线 SVG 解析 ----------

# 简化版 star-history SVG：一条贝塞尔曲线 + 两条边框。
# 刻意复刻真实数据的两个特征：
#   1. 以 "m0 423.3" 相对 moveto 开头（起点必须计入，否则整条曲线平移）
#   2. 后续贝塞尔参数省略命令字母（隐式重复，实测 112 数字仅 1 个 'c'）
_FAKE_SVG = b'''<svg xmlns="http://www.w3.org/2000/svg" width="700" height="400">
<path d="M.5.5h700" stroke="#e5e7eb"/>
<path d="m0 423.333.779-.1c13.72-1.768 27.442-1.878 41.163-2.71 13.724-.83 27.45-1.592 41.174-2.277 13.636-.681 27.272-1.08 40.908-1.823 13.72-.748 27.442-1.696 41.163-2.657 13.728-.962 27.457-2.114 41.186-3.114" stroke="#3182ce"/>
</svg>'''


def test_extract_curve_points_parses_bezier():
    """回归测试：SVG 里的连写数字（如 27.45-1.592）必须被正确切分。"""
    points = CardGenerator._extract_curve_points(_FAKE_SVG)
    assert len(points) >= 5, f'应解析出多个点，实际 {len(points)}'


def test_extract_curve_points_honors_relative_start():
    """回归测试：曲线以 "m0 423.3" 相对 moveto 开头。

    漏掉这个起点会让所有 y 变成负数（曾发生），因为 SVG 的
    绝对坐标是基于它累加出来的。
    """
    points = CardGenerator._extract_curve_points(_FAKE_SVG)
    first_y = points[0][1]
    assert first_y > 400, f'首点 y 应接近 423（SVG 里的起点），实际 {first_y:.1f}'
    assert all(y > 0 for _, y in points), '所有 y 都应为正值（真实 SVG 坐标系）'


def test_extract_curve_points_handles_implicit_repeats():
    """回归测试：同命令的后续参数组省略命令字母，必须按数字个数分组。

    真实 SVG 实测 112 个数字但只有 1 个 'c'，若按命令字母切分会漏掉大部分点。
    """
    # 造一个 >200 字符的 path，只有 1 个 m + 1 个 c，后续全靠隐式重复
    filler = ' '.join(['13.72-1.768 27.442-1.878 41.163-2.71'] * 8)
    svg = f'<svg><path d="m0 423.333.779-.1c{filler}"/></svg>'.encode()
    points = CardGenerator._extract_curve_points(svg)

    # 1 个 m + 8 组 c = 至少 9 个点（若按字母切分只会得到 2 个）
    assert len(points) >= 9, \
        f'隐式重复未正确处理，只解析出 {len(points)} 个点'


def test_extract_curve_points_returns_empty_on_bad_input():
    assert CardGenerator._extract_curve_points(b'<html>error</html>') == []
    assert CardGenerator._extract_curve_points(b'') == []


def test_extract_curve_points_ignores_short_paths():
    """边框/刻度线都是短 path，不应被当成曲线。"""
    svg = b'<svg><path d="M.5.5h700"/><path d="M-1 423.833H.5V.5H-1"/></svg>'
    assert CardGenerator._extract_curve_points(svg) == []
def test_render_curve_creates_valid_png():
    """渲染出的 PNG 必须是合法图片且非空白。"""
    with TempDir() as tmp:
        card = CardGenerator({'resolution': '1920x1080', 'output_dir': str(tmp)})
        points = CardGenerator._extract_curve_points(_FAKE_SVG)
        assert points, '前置条件：应能解析出曲线点'

        out = tmp / 'spark.png'
        card._render_curve(points, {'stars': 12345}, out)

        assert out.exists() and out.stat().st_size > 0

        img = Image.open(out)
        assert img.width > 0 and img.height > 0
        # 检查不是纯空白：曲线、填充、端点标记、文字至少产生多种颜色
        colors = img.convert('RGB').getcolors(maxcolors=100000)
        assert colors and len(colors) > 3, \
            f'曲线图不应是纯色块，实际只有 {len(colors or [])} 种颜色'


def test_fetch_star_history_returns_none_when_svg_unparseable(monkeypatch):
    """拿不到真实曲线时必须返回 None（走占位），绝不返回假曲线。"""
    with TempDir() as tmp:
        card = CardGenerator({'resolution': '1920x1080', 'output_dir': str(tmp)})
        monkeypatch.setattr(card, '_download_svg', lambda *a, **k: b'<html>error</html>')

        project = {'url': 'https://github.com/some/repo', 'stars': 999}
        result = card.fetch_star_history(project)
        assert result is None, '解析失败必须返回 None，不能用推测数据冒充真实曲线'


def test_chaikin_smooth_preserves_endpoints():
    pts = [(0.0, 0.0), (10.0, 5.0), (20.0, 1.0), (30.0, 8.0)]
    out = CardGenerator._chaikin_smooth(pts, iterations=2)
    assert out[0] == pts[0]
    assert out[-1] == pts[-1]
    assert len(out) > len(pts), '平滑后点数应增加'


def test_chaikin_smooth_handles_degenerate_input():
    assert CardGenerator._chaikin_smooth([(1.0, 2.0)]) == [(1.0, 2.0)]
    assert CardGenerator._chaikin_smooth([]) == []


# ---------- 自动文案生成 ----------

def test_auto_narrative_uses_real_data():
    project = {
        'name': 'demo', 'url': 'https://github.com/a/demo',
        'description': '一个用于测试的中文项目描述。',
        'language': 'Go', 'stars': 12345, 'forks': 678,
        'currentPeriodStars': 900, 'topics': ['ai', 'agent'],
    }
    n = auto_narrative(project)

    assert n['hook'] and n['body'] and n['call_to_action']
    # 数据必须来自真实采集值，不能编造
    assert '900' in n['hook'] or '900' in n['body']
    assert '12,345' in n['body']
    assert '678' in n['body']
    # 中文描述应被直接采用
    assert '测试' in n['body']


def test_auto_narrative_handles_english_description():
    project = {
        'name': 'demo', 'url': 'https://github.com/a/demo',
        'description': 'A CLI tool for AI agents with token optimization.',
        'language': 'Go', 'stars': 100, 'forks': 10,
        'currentPeriodStars': 0, 'topics': ['ai'],
    }
    n = auto_narrative(project)
    # 英文描述不应原样出现在中文文案里
    assert 'A CLI tool' not in n['body']
    assert len(n['body']) > 20


def test_auto_narrative_truncates_at_sentence_boundary():
    project = {
        'name': 'x', 'url': 'https://github.com/a/x',
        'description': '中文描述。' * 60,
        'language': 'Python', 'stars': 10, 'forks': 1,
        'currentPeriodStars': 1, 'topics': [],
    }
    n = auto_narrative(project)
    assert len(n['body']) <= 175, f'超长文案应被截断，实际 {len(n["body"])}'


def test_clean_text_strips_html_and_emoji():
    assert '<b>' not in _clean_text('<b>hello</b>')
    assert '\U0001F680' not in _clean_text('launch \U0001F680')


def test_auto_narrative_survives_missing_fields():
    """数据缺失时不能崩，且不编造数据。"""
    n = auto_narrative({'name': 'empty', 'url': ''})
    assert n['body']
    assert 'NaN' not in n['body'] and 'None' not in n['body']


# ---------- 片段动效 ----------

def _sample_clip(path: str, duration: float = 4.0):
    from moviepy import ImageClip
    return ImageClip(path, duration=duration)


def _fixture_image(tmp, name='frame.png', size=(1920, 1080)):
    p = tmp / name
    Image.new('RGB', size, (30, 41, 59)).save(p)
    return str(p)


def test_animate_preserves_resolution():
    """回归测试：缩放动效曾让输出变成 1967x1107（未裁回原尺寸）。"""
    with TempDir() as tmp:
        img = _fixture_image(tmp)
        composer = VideoComposer({'resolution': '1920x1080', 'fps': 24,
                                  'output_dir': str(tmp)})
        for is_first, is_last, label in [(True, False, 'first'),
                                         (False, False, 'middle'),
                                         (False, True, 'last')]:
            clip = composer._animate(_sample_clip(img), is_first, is_last)
            assert (clip.w, clip.h) == (1920, 1080), \
                f'{label} 段动效后分辨率变了: {clip.w}x{clip.h}'


def test_animate_preserves_duration():
    """动效不得让片段时长缩水（淡入消耗的时间要从尾部补回来）。"""
    with TempDir() as tmp:
        img = _fixture_image(tmp)
        composer = VideoComposer({'resolution': '1920x1080', 'fps': 24,
                                  'output_dir': str(tmp)})
        base = _sample_clip(img, duration=6.0)
        for is_first, is_last in [(True, False), (False, False), (False, True)]:
            out = composer._animate(base.copy(), is_first, is_last)
            assert abs(out.duration - 6.0) < 0.05, \
                f'动效改变了时长: {out.duration} != 6.0'


def test_animate_actually_changes_frame():
    """回归测试：早期用两次 resized 裁回原尺寸，因 lambda 收到的是时间 t
    导致尺寸算成 0（ValueError: height and width must be > 0）。"""
    with TempDir() as tmp:
        img = _fixture_image(tmp)
        composer = VideoComposer({'resolution': '1920x1080', 'fps': 24,
                                  'output_dir': str(tmp)})
        out = composer._animate(_sample_clip(img, duration=5.0), False, False)

        # 真正渲染几帧，确保不会在渲染期才崩
        first_frame = out.get_frame(0.5)
        mid_frame = out.get_frame(2.5)
        assert first_frame is not None and mid_frame is not None
        assert first_frame.shape == mid_frame.shape, '推镜过程中尺寸应保持不变'


def test_zoom_ratio_is_sane():
    assert 1.0 < ZOOM_RATIO < 1.2, '缩放幅度应轻微，过大会明显失真'
    assert FADE_IN > 0 and FADE_OUT > 0
    assert FADE_IN + FADE_OUT < 3.0, '淡化时长不应过长'


def test_compose_rejects_mismatched_counts():
    with TempDir() as tmp:
        composer = VideoComposer({'resolution': '1920x1080', 'fps': 24,
                                  'output_dir': str(tmp)})
        with_temp = tmp / 'x.mp4'
        try:
            composer.compose(['a.png'], [], str(with_temp))
        except ValueError as e:
            assert '不匹配' in str(e)
            return
        raise AssertionError('幻灯片与音频数量不匹配时应当抛错')


def test_compose_rejects_empty_slides():
    """回归测试：曾经存在"采集全失败 → 生成 Top 0 视频"的静默链。"""
    with TempDir() as tmp:
        composer = VideoComposer({'resolution': '1920x1080', 'fps': 24,
                                  'output_dir': str(tmp)})
        try:
            composer.compose([], [], str(tmp / 'x.mp4'))
        except ValueError as e:
            assert '没有可渲染' in str(e)
            return
        raise AssertionError('空内容必须被拒绝')



# ---------- 文案质量校验 ----------

def _narrative(hook, body, cta):
    return {'name': 'x', 'full_name': 'a/x',
            'narrative': {'hook': hook, 'body': body, 'call_to_action': cta}}


_GOOD_BODY = ('现在的 AI Agent 想读推特、看 B 站、刷小红书，都得一个个接 API，'
              '还得付费。这个项目把它收拢成一条命令，装好之后你的 Agent 就能直接'
              '读这些平台的内容。它的定位很实在——接入方式以后会换代，但它会替你'
              '选好、装好、体检好，你不用操心。')


def test_validator_accepts_good_narrative():
    issues = validate_project(_narrative(
        '让 AI Agent 能刷 B站和小红书，不花一分钱',
        _GOOD_BODY,
        '想给 Agent 加联网能力，可以先看看。'))
    assert issues == [], f'合格文案不该有 issue: {issues}'


def test_validator_rejects_cliche():
    """回归测试：'这是一个面向 AI 的工具，用 X 编写' 是典型的无效文案。"""
    issues = validate_project(_narrative(
        '今天新增 1,683 星',
        '这是一个面向 AI 智能体的工具，用 Python 编写。目前 89,533 星，7,877 个 fork。',
        '快去试试吧'))
    joined = ' '.join(issues)
    assert '套话' in joined or '有效内容过少' in joined, f'应识别为套话: {issues}'
    assert '没有说明项目能做什么' in joined


def test_validator_rejects_number_recitation():
    """回归测试：复述屏幕已有的数字是零信息量。"""
    issues = validate_project(_narrative(
        '89,533',
        '89,533 stars, 7,877 forks, MIT, Python, TypeScript, AI, agent, cli.',
        '值得一看'))
    joined = ' '.join(issues)
    assert 'hook 只有数字' in joined
    assert '有效内容过少' in joined


def test_validator_catches_empty_fields():
    issues = validate_project(_narrative('', '', ''))
    assert sum('为空' in i for i in issues) == 3


def test_validator_lenient_mode_skips_cliche_check():
    strict = validate_project(_narrative(
        '今天新增 1,683 星',
        '这是一个面向 AI 智能体的工具，用 Python 编写。目前 89,533 星，7,877 个 fork。',
        '快去试试吧'), strict=True)
    lenient = validate_project(_narrative(
        '今天新增 1,683 星',
        '这是一个面向 AI 智能体的工具，用 Python 编写。目前 89,533 星，7,877 个 fork。',
        '快去试试吧'), strict=False)
    assert len(strict) > len(lenient), 'lenient 模式应更宽松'


def test_validate_all_reports_only_bad_ones():
    projects = [
        _narrative('让 AI Agent 能刷 B站', _GOOD_BODY, '可以先看看。'),
        _narrative('89,533', '89,533 stars, 7,877 forks, MIT, Python.', '看看'),
    ]
    result = validate_all(projects)
    assert len(result) == 1
    assert 'a/x' in result


def test_summarize_duration_scales_with_text():
    short = [_narrative('短', _GOOD_BODY[:40], '看看')]
    long = [_narrative('长', _GOOD_BODY * 2, '看看看看。')]
    assert summarize_duration(long) > summarize_duration(short)


def test_auto_narrative_output_fails_strict_validation():
    """规则式兜底文案本来就达不到内容质量标准——
    这正是需要 Agent 介入的原因，测试固化了这一事实。"""
    issues = validate_project({
        'name': 'x', 'full_name': 'a/x',
        'narrative': auto_narrative({
            'name': 'x', 'url': 'https://github.com/a/x',
            'description': 'A CLI tool for AI agents with token optimization.',
            'language': 'Go', 'stars': 100, 'forks': 10,
            'currentPeriodStars': 0, 'topics': ['ai'],
        }),
    })
    assert issues, 'auto_narrative 的产物应无法通过严格校验（说明它只是兜底）'


# ---------- README 清洗 ----------

def test_clean_markdown_strips_html_and_badges():
    raw = ('<h1 align="center">Title</h1>\n'
           '<p align="center"><img src="badge.svg" alt="badge"></p>\n'
           '<p>Real content here.</p>\n'
           '[link](https://example.com)\n')
    out = TrendingFetcher._clean_markdown(raw)
    assert '<h1' not in out and '<p' not in out and 'img src' not in out
    assert 'Real content here.' in out
    assert 'link' in out, '链接文字应保留'
    assert 'https://' not in out, '裸 URL 应被移除'


def test_clean_markdown_preserves_chinese():
    raw = '## 标题\n\n这是中文内容，用于测试清洗逻辑。\n\n```bash\ncode block\n```\n'
    out = TrendingFetcher._clean_markdown(raw)
    assert '这是中文内容' in out


# ---------- 降级数据的增速语义（回归）----------

def test_search_api_marks_growth_as_estimated():
    """降级路径的 currentPeriodStars 是日均值，必须打 estimated 标记。

    GitHub search 索引里没有 star 时间序列，拿不到真实日增。
    这个标记决定展示层能否写「today」——写错就是假标题。
    """
    f = TrendingFetcher({'github': {'personal_access_token': 'fake'}})

    class FakeResp:
        status_code = 200
        @staticmethod
        def json():
            return {'items': [{
                'owner': {'login': 'a', 'avatar_url': 'x'},
                'name': 'b', 'full_name': 'a/b', 'html_url': 'https://github.com/a/b',
                'description': 'd', 'language': 'Python',
                'stargazers_count': 1000, 'forks_count': 10,
                'created_at': '2026-09-01T00:00:00Z',
                'fork': False, 'archived': False,
            }]}

    f._get = lambda *a, **k: FakeResp()
    result = f._fetch_via_search_api(limit=5)

    assert result, '降级路径应返回结果'
    assert result[0].get('growth_estimated') is True, \
        'search API 的增速必须标记为估算值'


def test_trending_html_marks_growth_as_real():
    """第一层是真实日增，必须显式标记为非估算。"""
    card = {
        'author': 'a', 'name': 'b', 'full_name': 'a/b',
        'avatar': '', 'url': 'https://github.com/a/b',
        'description': 'd', 'language': 'Python', 'languageColor': '#fff',
        'stars': 100, 'forks': 5, 'currentPeriodStars': 77,
    }
    html = ('<article class="Box-row"><h2><a href="/a/b">a/b</a></h2>'
            '<p class="col-9">desc</p>'
            '<span itemprop="programmingLanguage">Python</span>'
            '<span class="repo-language-color" style="background-color: #f00"></span>'
            '<a href="/a/b/stargazers">100</a>'
            '<a href="/a/b/forks">5</a>'
            '<span>77 stars today</span></article>')

    import bs4
    f = TrendingFetcher({})
    parsed = f._parse_article(bs4.BeautifulSoup(html, 'html.parser'))
    assert parsed is not None
    assert parsed['currentPeriodStars'] == 77, '真实日增应正确解析'
    assert parsed.get('growth_estimated') is False, \
        '第一层必须标记为真实日增（growth_estimated=False）'


def test_title_avoids_fake_daily_growth():
    """回归测试：降级数据下标题不能写「一天涨了 N 星」——那是日均值不是日增。"""
    import os as _os
    _os.environ.setdefault('BILIBILI_SESSDATA', 'x' * 30)
    _os.environ.setdefault('BILIBILI_BILI_JCT', 'y' * 32)
    _os.environ.setdefault('BILIBILI_BUVID3', 'z' * 30)

    from bilibili_uploader import BilibiliUploader
    uploader = BilibiliUploader({'tid': 122})

    estimated = [{
        'name': 'laya', 'currentPeriodStars': 2027, 'growth_estimated': True,
    }]
    title = uploader._build_title(estimated)
    assert '一天涨了' not in title, f'降级数据不能产生日增钩子: {title}'
    assert '2027' not in title, f'降级数据不能把日均值当日增写进标题: {title}'

    real = [{
        'name': 'ponytail', 'currentPeriodStars': 1289, 'growth_estimated': False,
    }]
    real_title = uploader._build_title(real)
    assert '一天涨了 1,289 星' in real_title, f'真实日增应正常做钩子: {real_title}'


# ---------- 标题生成（Agent hook 优先）----------

def _uploader():
    import os as _os
    _os.environ.setdefault('BILIBILI_SESSDATA', 'x' * 30)
    _os.environ.setdefault('BILIBILI_BILI_JCT', 'y' * 32)
    _os.environ.setdefault('BILIBILI_BUVID3', 'z' * 30)
    from bilibili_uploader import BilibiliUploader
    return BilibiliUploader({'tid': 122})


def _proj(name, hook='', title_hook=False, growth=0, estimated=False):
    return {'name': name, 'currentPeriodStars': growth,
            'growth_estimated': estimated,
            'narrative': {'hook': hook, 'title_hook': title_hook}}


def test_title_prefers_agent_marked_hook():
    """"Agent-Reach 一天涨了 1683 星" 对不认识项目的人没吸引力，
    narrative.hook 才是专门写的钩子。Agent 标注的优先。"""
    u = _uploader()
    projects = [
        _proj('short', '今天新增很多星', growth=9999),
        _proj('marked', 'Google 的工程师把工作方法打包给 AI 用了', title_hook=True),
    ]
    title = u._build_title(projects)
    assert 'Google 的工程师' in title, f'应采用 Agent 标注的 hook: {title}'
    assert '9999' not in title, '不应被日增数字带偏'


def test_title_falls_back_to_longest_hook():
    u = _uploader()
    projects = [
        _proj('a', '短'),
        _proj('b', '这个 hook 明显更长，信息也更完整，适合做标题'),
    ]
    title = u._build_title(projects)
    assert '明显更长' in title, f'未标注时应取最长 hook: {title}'


def test_title_keeps_github_keyword():
    """B站搜索流量依赖关键词，前缀必须保留。"""
    u = _uploader()
    title = u._build_title([_proj('x', '让 AI Agent 能刷 B站')])
    assert 'GitHub' in title, f'标题应保留 GitHub 关键词: {title}'


def test_title_strips_trailing_punctuation():
    u = _uploader()
    title = u._build_title([_proj('x', '让 AI Agent 能刷 B站。')])
    assert not title.endswith('。'), f'应去掉句尾标点: {title}'


def test_title_respects_length_limit():
    u = _uploader()
    title = u._build_title([_proj('x', '很长的钩子' * 40)])
    assert len(title) <= 80, f'标题不能超过 B站 80 字限制: {len(title)}'


def test_title_without_narrative_uses_growth():
    """没有 narrative 时回退到日增钩子（脚本判断不了质量，只有数据可用）。"""
    u = _uploader()
    projects = [{'name': 'ponytail', 'currentPeriodStars': 1289,
                 'growth_estimated': False, 'narrative': {}}]
    title = u._build_title(projects)
    assert 'ponytail' in title and '1,289' in title, f'应回退到日增钩子: {title}'
