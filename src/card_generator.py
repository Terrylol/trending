"""视频卡片渲染（PIL 静态排版）

设计约束（重构后）：
- 分辨率解耦：所有尺寸基于画布宽高按比例计算，不硬编码 720p 假设
- 中文简体：.ttc 字体必须显式指定 face index，否则取到繁体（Heiti TC）
- 无裸 except：字体加载失败要报错而不是静默回落到 6px 位图字体（中文会变方块）
"""
import json
import os
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------- 设计系统 ----------

# 深色主题：日更号在 B 站的知识区，深色底 + 高对比在移动端小屏上更抓眼
PALETTE = {
    'bg_top': (13, 20, 36),
    'bg_bottom': (22, 34, 58),
    'card': (255, 255, 255),
    'accent': (56, 189, 248),      # sky-400
    'accent_alt': (129, 140, 248), # indigo-400
    'text_primary': (15, 23, 42),
    'text_body': (51, 65, 85),
    'text_muted': (100, 116, 139),
    'text_on_dark': (248, 250, 252),
    'text_on_dark_muted': (148, 163, 184),
    'chip_bg': (241, 245, 249),
    'positive': (16, 185, 129),
}

ACCENTS = [
    (56, 189, 248), (129, 140, 248), (244, 114, 182),
    (251, 146, 60), (52, 211, 153), (167, 139, 250),
]


class FontError(Exception):
    """找不到可用字体"""


class CardGenerator:
    """基于 PIL 的卡片渲染器。所有尺寸按画布比例计算，与分辨率解耦。"""

    star_history_config: Dict
    """Star 趋势图配置（由外部注入，避免与 output_dir 等其他配置耦合）"""

    def __init__(self, config: Optional[Dict] = None):
        config = config or {}
        resolution = config.get('resolution', '1920x1080')
        try:
            self.width, self.height = (int(x) for x in resolution.split('x'))
        except (ValueError, AttributeError):
            raise ValueError(f'无效分辨率 "{resolution}"，应为 WIDTHxHEIGHT')

        self.star_history_config = config.get('star_history', {}) or {}
        self.output_dir = Path(config.get('output_dir', 'output'))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.star_history_dir = self.output_dir / 'star_history'
        self.star_history_dir.mkdir(parents=True, exist_ok=True)

        # 基准设计尺寸：按 1920x1080 设计，其他分辨率等比缩放
        self.unit = self.width / 1920.0
        self._fonts = {}
        self._load_fonts()

    # ---------- 字体 ----------

    def _load_fonts(self):
        """加载字体。

        关键：.ttc 字体集合必须显式指定 face index。
        macOS 的 STHeiti Medium.ttc 中 face 0 是 Heiti TC（繁体），
        face 1 才是 Heiti SC（简体）。不指定 index 会导致中文渲染成繁体。
        """
        zh_path, zh_index = self._find_cjk_font()
        if not zh_path:
            raise FontError(
                '未找到可用的中文字体。macOS 请确认存在 STHeiti 或 PingFang，'
                'Linux 请安装 fonts-noto-cjk。'
            )

        scale = self.unit
        specs = {
            'title': (zh_path, zh_index, 96),
            'project_name': (zh_path, zh_index, 68),
            'section': (zh_path, zh_index, 40),
            'body': (zh_path, zh_index, 34),
            'cta': (zh_path, zh_index, 38),
            'tag': (zh_path, zh_index, 28),
            'meta': (zh_path, zh_index, 32),
            'badge': (zh_path, zh_index, 26),
            'hero': (zh_path, zh_index, 120),
            'date': (zh_path, zh_index, 44),
        }

        for name, (path, index, size) in specs.items():
            scaled = max(int(size * scale), 12)
            try:
                self._fonts[name] = ImageFont.truetype(path, scaled, index=index)
            except OSError as e:
                raise FontError(f'字体加载失败 {path} (index={index}): {e}') from e

        print(f'  ✓ 字体加载成功（{zh_path}, face={zh_index}, {self.width}x{self.height}）')

    def _find_cjk_font(self) -> Tuple[Optional[str], int]:
        """探测可用的中文字体，返回 (路径, face index)。

        .ttc 是字体集合，一个文件里有多个 face。macOS 的 STHeiti Medium.ttc 中
        face 0 是 Heiti TC（繁体），face 1 才是 Heiti SC（简体）。
        必须显式选对，否则中文会渲染成繁体字形。
        """
        override = os.environ.get('TRENDING_CJK_FONT')
        if override and Path(override).exists():
            return override, int(os.environ.get('TRENDING_CJK_FONT_INDEX', 0))

        candidates = [
            ('/System/Library/Fonts/STHeiti Medium.ttc', 'Darwin'),
            ('/System/Library/Fonts/PingFang.ttc', 'Darwin'),
            ('/System/Library/Fonts/Hiragino Sans GB.ttc', 'Darwin'),
            ('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', None),
            ('/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf', None),
            ('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', None),
            ('C:/Windows/Fonts/msyh.ttc', 'Windows'),
            ('C:/Windows/Fonts/simhei.ttf', 'Windows'),
        ]

        platform_name = os.uname().sysname
        for path, required_platform in candidates:
            if required_platform and platform_name != required_platform:
                continue
            if not Path(path).exists():
                continue

            if not path.lower().endswith(('.ttc', '.otc')):
                return path, 0

            # 字体集合：优先挑简体（SC / Simplified）face，找不到就用 index 0
            fallback = None
            for probe in range(6):
                try:
                    probe_font = ImageFont.truetype(path, 20, index=probe)
                except (OSError, ValueError):
                    break
                face_name = ' '.join(probe_font.getname())
                if 'SC' in face_name or 'Simplified' in face_name or 'GB' in face_name:
                    return path, probe
                if fallback is None:
                    fallback = (path, probe)
            if fallback:
                return fallback

        return None, 0

    def _f(self, name: str) -> ImageFont.FreeTypeFont:
        return self._fonts[name]

    def _u(self, px: float) -> int:
        """设计像素 → 实际像素"""
        return max(int(px * self.unit), 1)

    # ---------- 绘图基元 ----------

    def _gradient_bg(self, top: Tuple[int, int, int], bottom: Tuple[int, int, int]) -> Image.Image:
        """垂直渐变背景。用 numpy-free 的方式：逐行绘制后在 1080p 下也足够快。"""
        img = Image.new('RGB', (self.width, self.height), top)
        draw = ImageDraw.Draw(img)
        for y in range(self.height):
            ratio = y / max(self.height - 1, 1)
            color = tuple(int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3))
            draw.line([(0, y), (self.width, y)], fill=color)
        return img

    def _radial_glow(self, img: Image.Image, center: Tuple[int, int], radius: int,
                     color: Tuple[int, int, int], alpha: int = 26):
        """径向光晕。用模糊化的实心圆模拟，比真渐变快得多。"""
        layer = Image.new('RGB', img.size, (0, 0, 0))
        mask = Image.new('L', img.size, 0)
        md = ImageDraw.Draw(mask)
        cx, cy = center
        md.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=alpha)
        mask = mask.filter(ImageFilter.GaussianBlur(radius // 3))
        layer.paste(color, (0, 0), mask)
        return Image.blend(img, Image.blend(img, layer, 0.5), 0.55)

    def _rounded_rect(self, draw: ImageDraw.ImageDraw, box, radius: int, fill):
        draw.rounded_rectangle(box, radius=radius, fill=fill)

    def _text_width(self, draw: ImageDraw.ImageDraw, text: str, font) -> int:
        """测量文本宽度，正确处理中英文混排。"""
        if not text:
            return 0
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]

    def _wrap_text(self, draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> List[str]:
        """按像素宽度折行，处理中英文混排（中文字符按 1 个字宽计）。"""
        if not text:
            return []

        lines = []
        current = ''
        for char in text:
            if char == '\n':
                lines.append(current)
                current = ''
                continue
            trial = current + char
            if self._text_width(draw, trial, font) > max_width and current:
                lines.append(current)
                current = char
            else:
                current = trial
        if current:
            lines.append(current)
        return lines

    def _fit_text(self, draw: ImageDraw.ImageDraw, text: str, font_name: str,
                   max_width: int, max_height: int, line_gap: float = 1.45) -> Tuple[List[str], Any]:
        """把文本塞进给定区域：超出则逐步缩小字号重试。

        保证返回行数一定放得进 max_height——放不下就截断。
        旧实现在所有字号都不够时返回超量行数，导致文字画出容器甚至画面。
        """
        base_size = self._fonts[font_name].size
        lines: List[str] = []
        font = self._fonts[font_name]
        max_lines = 1

        for shrink in (1.0, 0.94, 0.88, 0.82, 0.76, 0.70, 0.64, 0.58):
            size = max(int(base_size * shrink), 12)
            try:
                font = ImageFont.truetype(
                    self._fonts[font_name].path, size,
                    index=self._fonts[font_name].index or 0,
                )
            except (OSError, ValueError, AttributeError):
                font = self._fonts[font_name]

            line_height = int(size * line_gap)
            max_lines = max(int(max_height // line_height), 1)

            lines = self._wrap_text(draw, text, font, max_width)
            if len(lines) <= max_lines:
                return lines, font

        return lines[:max_lines], font

    def _chip(self, draw: ImageDraw.ImageDraw, xy, text: str, font, fill, text_color):
        x, y = xy
        pad_x, pad_y = self._u(18), self._u(9)
        w = self._text_width(draw, text, font) + pad_x * 2
        h = font.size + pad_y * 2
        self._rounded_rect(draw, [x, y, x + w, y + h], h // 2, fill)
        draw.text((x + pad_x, y + pad_y), text, font=font, fill=text_color)
        return x + w, y

    # ---------- Star 趋势图 ----------

    def fetch_star_history(self, project: Dict, timeout: int = 8) -> Optional[str]:
        """获取 Star 趋势图。

        实现方式：从 star-history.com 的 SVG 里**解析真实曲线数据点**，
        再用 PIL 重绘。不依赖 cairosvg/rsvg/inkscape——macOS 上这三者常缺，
        而 SVG 转 PNG 的工具链是这条链路最大的脆弱点。

        解析失败就返回 None 显示占位，绝不用假数据冒充真实曲线。
        """
        if not self.star_history_config.get('enabled', True):
            return None

        owner, repo = self._parse_repo(project.get('url', ''))
        if not owner:
            return None

        safe = f'{owner}_{repo}'.lower()
        cache_file = self.star_history_dir / f'{safe}.png'
        # 缓存 12 小时，避免同一天重复请求
        if cache_file.exists() and cache_file.stat().st_size > 0:
            age_h = (time.time() - cache_file.stat().st_mtime) / 3600
            if age_h < 12:
                return str(cache_file)

        svg = self._download_svg(owner, repo, timeout)
        if not svg:
            return None

        points = self._extract_curve_points(svg)
        if len(points) < 4:
            return None

        self._render_curve(points, project, cache_file)
        return str(cache_file)

    def _download_svg(self, owner: str, repo: str, timeout: int) -> Optional[bytes]:
        url = f'https://api.star-history.com/svg?repos={owner}/{repo}&type=Date'
        try:
            result = subprocess.run(
                ['curl', '-sL', '--max-time', str(timeout), url],
                capture_output=True, timeout=timeout + 3,
            )
            if result.returncode == 0 and b'<svg' in result.stdout[:3000]:
                return result.stdout
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            pass
        return None

    # SVG path 解析：命令字母与数字要分开 token 匹配，否则 "27.45-1.592"
    # 这种连写数字会被切错。
    _PATH_TOKEN = re.compile(r'([MmLlCcSsQqTtAaZzHhVv])|(-?\d*\.?\d+(?:e-?\d+)?)')

    @classmethod
    def _extract_curve_points(cls, svg: bytes) -> List[Tuple[float, float]]:
        """从 star-history 的 SVG 中提取曲线数据点。

        两个必须处理的 SVG path 细节（都是实测踩过的坑）：

        1. **隐式命令重复**：同一条命令的后续参数组会省略命令字母。
           曲线通常写成 `m0 423.3` + 一长串贝塞尔参数（实测 112 个数字
           却只有 1 个字母 c），每组都是完整的 6 个数字。
           必须按"每 N 个数字一组"推进，而不是按命令字母切分。

        2. **相对命令要累加**：`c` / `m` 的参数是相对当前点的偏移。
           起点 `m0 423.3` 必须计入，否则整条曲线平移（曾导致 y 全为负）。
        """
        try:
            text = svg.decode('utf-8', errors='ignore')
        except AttributeError:
            return []

        # 曲线是唯一一条长度远超其它 path 的（其余是边框、刻度线）
        paths = re.findall(r'<path[^>]*?d="([^"]{200,})"', text)
        if not paths:
            return []

        d = max(paths, key=len)
        points: List[Tuple[float, float]] = []
        cur = [0.0, 0.0]
        cmd = None
        nums: List[float] = []

        # 各命令消费的数字个数；贝塞尔 c=6, s=4（平滑版少一个控制点）
        ARITY = {'m': 2, 'l': 2, 't': 2, 'h': 1, 'v': 1,
                 'c': 6, 's': 4, 'q': 4, 'a': 7}
        RELATIVE = set('mltsqca')

        def apply() -> None:
            """把累积的数字按当前命令转成一个绝对坐标端点。"""
            need = ARITY.get(cmd, 2)
            if not nums or len(nums) < need:
                return
            rel = cmd in RELATIVE

            if cmd in ('c', 's'):
                dx, dy = nums[-2], nums[-1]
                cur[0] += dx if rel else 0
                cur[1] += dy if rel else 0
            elif cmd in ('m', 'l', 't'):
                dx, dy = nums[-2], nums[-1]
                cur[0] = cur[0] + dx if rel else dx
                cur[1] = cur[1] + dy if rel else dy
            elif cmd == 'h':
                cur[0] = cur[0] + nums[-1] if rel else nums[-1]
            elif cmd == 'v':
                cur[1] = cur[1] + nums[-1] if rel else nums[-1]
            else:
                return

            points.append((cur[0], cur[1]))

        for match in cls._PATH_TOKEN.finditer(d):
            if match.group(1):
                # 出现新命令字母：先把手上这组用旧命令结算，再切命令
                apply()
                nums.clear()
                cmd = match.group(1)
            else:
                nums.append(float(match.group(2)))
            # 攒够一组就结算并清空 —— 这就是隐式命令重复的处理方式
            apply_if_full = ARITY.get(cmd, 2)
            if len(nums) >= apply_if_full:
                apply()
                nums.clear()
        apply()

        return points

    @staticmethod
    def _chaikin_smooth(points: List[Tuple[float, float]],
                        iterations: int = 2) -> List[Tuple[float, float]]:
        """Chaikin 角点切割平滑：每段插入两个 1/4 与 3/4 处的点。

        用来消除折线感，端点保持不动。
        """
        pts = list(points)
        for _ in range(iterations):
            if len(pts) < 3:
                break
            new_pts = [pts[0]]
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                new_pts.append((x0 * 0.75 + x1 * 0.25, y0 * 0.75 + y1 * 0.25))
                new_pts.append((x0 * 0.25 + x1 * 0.75, y0 * 0.25 + y1 * 0.75))
            new_pts.append(pts[-1])
            pts = new_pts
        return pts

    def _render_curve(self, points: List[Tuple[float, float]],
                      project: Dict, cache_file: Path) -> None:
        """把解析出的真实曲线数据点画成 PNG。"""
        width, height = self._u(620), self._u(190)
        pad_top, pad_bottom = self._u(16), self._u(14)

        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        min_x, max_x = min(xs), max(xs)
        span_x = (max_x - min_x) or 1.0

        # Y 轴不要从数据最小值开始铺满 —— 那样曲线会贴住画面顶端，
        # 填充区变成一大片实色。留出 12% 顶部余量，曲线才有"上升空间"。
        raw_min, raw_max = min(ys), max(ys)
        headroom = (raw_max - raw_min) * 0.12
        min_y = raw_min - headroom
        max_y = raw_max + headroom * 0.5
        span_y = (max_y - min_y) or 1.0

        screen = []
        for x, y in points:
            px = (x - min_x) / span_x * (width - self._u(8)) + self._u(4)
            # SVG 里 y 越小星越多 → 映射到屏幕时上下翻转
            ratio = (y - min_y) / span_y          # 0 = 星最多 = 顶部
            py = pad_top + ratio * (height - pad_top - pad_bottom)
            screen.append((px, py))

        # star-history 只返回有限个月的数据点，直接连线会显得折线生硬
        smoothed = self._chaikin_smooth(screen, iterations=3)

        img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 面积填充：竖向渐变，底部更淡，避免糊成一片实色
        fill_pts = smoothed + [(smoothed[-1][0], height), (smoothed[0][0], height)]
        fill_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        fdraw = ImageDraw.Draw(fill_layer)
        fdraw.polygon(fill_pts, fill=(56, 189, 248, 70))

        # 逐行降低 alpha 做渐变
        alpha_mask = fill_layer.split()[3]
        faded = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        faded.paste(Image.new('RGBA', (width, height), (56, 189, 248, 255)),
                    (0, 0), alpha_mask)
        img.alpha_composite(faded)

        # 曲线线
        draw = ImageDraw.Draw(img)
        draw.line(smoothed, fill=(125, 211, 252, 255),
                  width=max(self._u(2), 2), joint='curve')

        # 终点标记（当前星数所在位置）
        last = smoothed[-1]
        r = max(self._u(3), 3)
        draw.ellipse([last[0] - r, last[1] - r, last[0] + r, last[1] + r],
                     fill=(186, 230, 253, 255))

        # 标注真实的星标总数（数据来自 GitHub API，非估算）
        stars = int(project.get('stars') or 0)
        label = f'★ {stars:,}' if stars else ''
        if label:
            try:
                draw.text((self._u(14), self._u(6)), label,
                          font=self._fonts.get('badge'),
                          fill=(226, 232, 240, 255))
            except Exception:
                pass

        cache_file.parent.mkdir(parents=True, exist_ok=True)
        img.save(cache_file)

    @staticmethod
    def _parse_repo(url: str) -> Tuple[Optional[str], Optional[str]]:
        if not url or 'github.com' not in url:
            return None, None
        parts = url.rstrip('/').split('/')
        if len(parts) >= 5 and parts[2] == 'github.com':
            return parts[3], parts[4]
        return None, None

    def prefetch_star_histories(self, projects: List[Dict], timeout: int = 5,
                                concurrency: int = 5) -> Dict[str, str]:
        """并发预取所有项目的 Star 趋势图，避免串行阻塞。"""
        results = {}

        def fetch_one(project: Dict) -> Tuple[str, Optional[str]]:
            key = project.get('full_name', project.get('url', ''))
            try:
                return key, self.fetch_star_history(project, timeout)
            except Exception:
                return key, None

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(fetch_one, p) for p in projects]
            done = {}
            for future in as_completed(futures):
                key, path = future.result()
                done[key] = path

        # 串行重试一轮：并发时的偶发超时不代表真的取不到（SVG 可达 60KB+）
        retry = [p for p in projects
                 if not done.get(p.get('full_name', p.get('url', '')))]
        if retry:
            print(f'    · {len(retry)} 个超时，串行重试一次')
            for project in retry:
                key, path = fetch_one(project)
                done[key] = path

        for key, path in done.items():
            if path:
                results[key] = path
        return results

    # ---------- 卡片 ----------

    def generate_title_card(self, date: str, output_path: str,
                            greeting: str = '', source_label: str = '') -> str:
        img = self._gradient_bg(PALETTE['bg_top'], PALETTE['bg_bottom'])
        img = self._radial_glow(img, (int(self.width * 0.22), int(self.height * 0.18)),
                                self._u(520), PALETTE['accent'], 30)
        img = self._radial_glow(img, (int(self.width * 0.82), int(self.height * 0.85)),
                                self._u(460), PALETTE['accent_alt'], 24)
        draw = ImageDraw.Draw(img)

        margin = self._u(140)
        y = self._u(300)

        # 主标题
        draw.text((margin, y), 'GitHub Trending', font=self._f('hero'),
                  fill=PALETTE['text_on_dark'])
        y += self._u(150)

        draw.text((margin, y), date, font=self._f('date'),
                  fill=PALETTE['accent'])
        y += self._u(90)

        if greeting:
            lines, font = self._fit_text(draw, greeting, 'body',
                                         self.width - margin * 2, self._u(160))
            for line in lines:
                draw.text((margin, y), line, font=font,
                          fill=PALETTE['text_on_dark_muted'])
                y += int(font.size * 1.5)

        if source_label:
            y = self.height - self._u(180)
            self._chip(draw, (margin, y), source_label, self._f('badge'),
                       PALETTE['chip_bg'], PALETTE['text_muted'])

        img.save(output_path)
        return output_path

    def generate_project_card(self, project: Dict, index: int, output_path: str,
                              star_history_image: str = '') -> str:
        accent = ACCENTS[index % len(ACCENTS)]
        img = self._gradient_bg(PALETTE['bg_top'], PALETTE['bg_bottom'])
        img = self._radial_glow(img, (int(self.width * 0.15), int(self.height * 0.12)),
                                self._u(480), accent, 28)
        draw = ImageDraw.Draw(img)

        margin = self._u(96)

        # 左侧强调条
        draw.rectangle([0, 0, self._u(14), self.height], fill=accent)

        # 排名水印
        draw.text((self.width - self._u(290), self._u(40)), f'{index + 1:02d}',
                  font=ImageFont.truetype(self._fonts['hero'].path,
                                          self._u(200), index=self._fonts['hero'].index or 0),
                  fill=(30, 41, 59))

        # 标题区
        y = self._u(70)
        name = project.get('name', '')
        repo_label = project.get('full_name') or f"{project.get('author','')}/{name}"
        name_lines, name_font = self._fit_text(draw, name, 'project_name',
                                               self._u(1000), self._u(90), line_gap=1.15)
        for line in name_lines[:2]:
            draw.text((margin, y), line, font=name_font, fill=PALETTE['text_on_dark'])
            y += int(name_font.size * 1.15)

        y += self._u(6)
        draw.text((margin, y), repo_label, font=self._f('meta'),
                  fill=PALETTE['text_on_dark_muted'])
        y += self._u(66)

        # 数据芯片：语言 / star / fork / 日增
        chip_y = y
        x = margin
        chips = []
        if project.get('language'):
            chips.append((project['language'], accent, (255, 255, 255)))
        chips.append((f"{int(project.get('stars') or 0):,} stars", PALETTE['chip_bg'], PALETTE['text_body']))
        if project.get('forks'):
            chips.append((f"{int(project['forks']):,} forks", PALETTE['chip_bg'], PALETTE['text_body']))
        if project.get('currentPeriodStars'):
            # growth_estimated=True 表示这个数字是「总星数 ÷ 项目年龄」的日均值，
            # 不是真实日增。必须如实标注，不能写成 "today" 误导观众。
            if project.get('growth_estimated'):
                chips.append((f"日均 +{int(project['currentPeriodStars']):,}*",
                              PALETTE['chip_bg'], PALETTE['text_muted']))
            else:
                chips.append((f"+{int(project['currentPeriodStars']):,} today",
                              PALETTE['chip_bg'], PALETTE['positive']))
        if project.get('license') and project['license'] != 'NOASSERTION':
            chips.append((project['license'], PALETTE['chip_bg'], PALETTE['text_body']))

        for text, bg, fg in chips:
            if x + self._u(280) > self.width - margin:
                break
            x, _ = self._chip(draw, (x, chip_y), text, self._f('badge'), bg, fg)
            x += self._u(12)

        y = chip_y + self._u(78)

        # 分栏：左图右文。左栏收窄，给文案更多横向空间（避免折行成细条）
        col_gap = self._u(48)
        left_w = self._u(600)
        right_x = margin + left_w + col_gap
        right_w = self.width - right_x - margin

        # 左侧：预览图 + Star 趋势
        preview_path = project.get('preview_image') or ''
        img_top = y
        img_h = self._u(340)
        self._draw_preview(draw, [margin, img_top, margin + left_w, img_top + img_h],
                           preview_path, accent)

        if star_history_image:
            chart_top = img_top + img_h + self._u(24)
            chart_h = self._u(210)
            self._draw_star_chart(draw, [margin, chart_top, margin + left_w, chart_top + chart_h],
                                  star_history_image, accent)

        # 右侧：文案。底部留白给 CTA，避免贴边或溢出
        narrative = project.get('narrative', {}) or {}
        cta = narrative.get('call_to_action', '')
        bottom_limit = self.height - self._u(70) - (self._u(70) if cta else 0)

        sections = [
            ('亮点', narrative.get('hook') or project.get('description', '')),
            ('介绍', narrative.get('body', '')),
        ]

        text_y = y
        for title, body in sections:
            if not body:
                continue
            remaining = bottom_limit - text_y
            if remaining <= self._u(80):
                break
            text_y = self._draw_section(draw, right_x, text_y, right_w,
                                        title, body, accent, remaining)
            text_y += self._u(30)

        if cta:
            cta_lines, cta_font = self._fit_text(draw, cta, 'cta', right_w, self._u(90))
            cta_y = min(text_y, self.height - self._u(80) - len(cta_lines) * int(cta_font.size * 1.4))
            for line in cta_lines[:2]:
                draw.text((right_x, cta_y), line, font=cta_font, fill=accent)
                cta_y += int(cta_font.size * 1.4)

        img.save(output_path)
        return output_path

    def _draw_preview(self, draw, box, path: str, accent):
        x0, y0, x1, y1 = box
        self._rounded_rect(draw, box, self._u(20), PALETTE['card'])
        inner_pad = self._u(10)
        if path and Path(path).exists():
            try:
                photo = Image.open(path).convert('RGB')
                avail_w = x1 - x0 - inner_pad * 2
                avail_h = y1 - y0 - inner_pad * 2
                photo.thumbnail((avail_w, avail_h), Image.LANCZOS)
                px = x0 + (x1 - x0 - photo.width) // 2
                py = y0 + (y1 - y0 - photo.height) // 2
                mask = Image.new('L', photo.size, 0)
                ImageDraw.Draw(mask).rounded_rectangle(
                    [0, 0, photo.width - 1, photo.height - 1],
                    radius=self._u(14), fill=255)
                img_tmp = Image.new('RGB', photo.size, (0, 0, 0))
                # 直接贴到主图需要索引，改用 paste 到临时再贴：这里用返回值简化
                self._paste_rounded(draw, photo, mask, px, py)
            except (OSError, ValueError):
                self._placeholder(draw, box, accent, '预览图不可用')
        else:
            self._placeholder(draw, box, accent, 'No Preview')

    def _paste_rounded(self, draw, photo, mask, px, py):
        # PIL 的 ImageDraw 没有直接贴图能力，借用 draw._image 走底层
        target = draw._image
        tmp = Image.new('RGBA', photo.size, (0, 0, 0, 0))
        tmp.paste(photo, (0, 0), mask)
        target.paste(tmp, (px, py), tmp)

    def _placeholder(self, draw, box, accent, label: str):
        x0, y0, x1, y1 = box
        self._rounded_rect(draw, box, self._u(20), PALETTE['chip_bg'])
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        font = self._f('tag')
        w = self._text_width(draw, label, font)
        draw.text((cx - w // 2, cy - font.size // 2), label,
                  font=font, fill=PALETTE['text_muted'])

    def _draw_star_chart(self, draw, box, path: str, accent):
        x0, y0, x1, y1 = box
        self._rounded_rect(draw, box, self._u(18), (30, 41, 59))
        pad = self._u(18)
        draw.text((x0 + pad, y0 + pad - self._u(4)), 'Star 趋势',
                  font=self._f('badge'), fill=PALETTE['text_on_dark_muted'])

        chart_top = y0 + pad + self._u(34)
        chart_box = [x0 + pad, chart_top, x1 - pad, y1 - pad]

        if Path(path).exists():
            try:
                chart = Image.open(path).convert('RGBA')
                chart.thumbnail((chart_box[2] - chart_box[0], chart_box[3] - chart_box[1]),
                                Image.LANCZOS)
                px = chart_box[0] + (chart_box[2] - chart_box[0] - chart.width) // 2
                py = chart_top + (chart_box[3] - chart_top - chart.height) // 2
                # 把 SVG 透明底压到深色卡片上：先合成再贴
                flat = Image.new('RGB', chart.size, (30, 41, 59))
                flat.paste(chart, (0, 0), chart)
                draw._image.paste(flat, (px, py))
            except (OSError, ValueError):
                self._chart_placeholder(draw, chart_box)
        else:
            self._chart_placeholder(draw, chart_box)

    def _chart_placeholder(self, draw, box):
        cx = (box[0] + box[2]) // 2
        cy = (box[1] + box[3]) // 2
        label = '趋势图暂不可用'
        font = self._f('tag')
        w = self._text_width(draw, label, font)
        draw.text((cx - w // 2, cy - font.size // 2), label,
                  font=font, fill=PALETTE['text_on_dark_muted'])

    def _draw_section(self, draw, x: int, y: int, width: int, title: str,
                      body: str, accent, max_h: Optional[int] = None) -> int:
        title_font = self._f('section')
        tag_w = self._text_width(draw, title, title_font) + self._u(44)
        tag_h = title_font.size + self._u(20)
        self._rounded_rect(draw, [x, y, x + tag_w, y + tag_h], self._u(10), accent)
        draw.text((x + self._u(22), y + self._u(10)), title,
                  font=title_font, fill=(255, 255, 255))
        y += tag_h + self._u(20)

        # 传入剩余空间自适应；留出标签块高度
        avail = (max_h - self._u(60)) if max_h else self._u(230)
        lines, body_font = self._fit_text(draw, body, 'body', width, max(avail, self._u(90)),
                                          line_gap=1.5)
        for line in lines:
            draw.text((x, y), line, font=body_font, fill=PALETTE['text_on_dark'])
            y += int(body_font.size * 1.5)
        return y

    def generate_ending_card(self, output_path: str) -> str:
        img = self._gradient_bg(PALETTE['bg_top'], PALETTE['bg_bottom'])
        img = self._radial_glow(img, (int(self.width * 0.5), int(self.height * 0.5)),
                                self._u(560), PALETTE['accent'], 26)
        draw = ImageDraw.Draw(img)

        lines = ['感谢观看', '我们明天见']
        y = self.height // 2 - self._u(110)
        for i, text in enumerate(lines):
            font = self._f('hero') if i == 0 else self._f('date')
            color = PALETTE['text_on_dark'] if i == 0 else PALETTE['text_on_dark_muted']
            w = self._text_width(draw, text, font)
            draw.text(((self.width - w) // 2, y), text, font=font, fill=color)
            y += int(font.size * 1.5)

        img.save(output_path)
        return output_path

    def generate_cover(self, date: str, output_path: str,
                       projects: Optional[List[Dict]] = None) -> str:
        """生成 B站封面。

        B站封面是视频曝光的关键，缺失会直接导致没有推荐量。
        比例用 16:10（B站推荐位常见比例），内容突出标题和日期。
        """
        width = self._u(1280)
        height = self._u(800)
        accent = PALETTE['accent']

        img = Image.new('RGB', (width, height), PALETTE['bg_top'])
        draw = ImageDraw.Draw(img)
        for y in range(height):
            ratio = y / max(height - 1, 1)
            color = tuple(
                int(PALETTE['bg_top'][i] + (PALETTE['bg_bottom'][i] - PALETTE['bg_top'][i]) * ratio)
                for i in range(3)
            )
            draw.line([(0, y), (width, y)], fill=color)

        # 光晕
        glow = Image.new('RGB', (width, height), (0, 0, 0))
        mask = Image.new('L', (width, height), 0)
        ImageDraw.Draw(mask).ellipse(
            [int(width * 0.55), int(-height * 0.2),
             int(width * 1.25), int(height * 0.85)], fill=44)
        mask = mask.filter(ImageFilter.GaussianBlur(int(width * 0.09)))
        glow.paste(accent, (0, 0), mask)
        img = Image.blend(img, Image.blend(img, glow, 0.5), 0.5)
        draw = ImageDraw.Draw(img)

        margin = self._u(90)
        # 顶部条
        draw.rectangle([0, 0, self._u(14), height], fill=accent)

        y = self._u(170)
        draw.text((margin, y), 'GitHub', font=self._f('hero'),
                  fill=PALETTE['text_on_dark'])
        y += self._u(150)

        # 「今日热榜」用强调色，制造层次
        cjk = self._cjk_font()
        title_font = self._scaled_font(cjk[0], cjk[1], self._u(130))
        draw.text((margin, y), '今日热榜', font=title_font, fill=accent)
        y += self._u(160)

        draw.text((margin, y), date, font=self._f('date'),
                  fill=PALETTE['text_on_dark_muted'])

        # 底部列出项目名，让人一眼知道本期内容
        if projects:
            names = [p.get('name', '') for p in projects[:5] if p.get('name')]
            y = height - self._u(150)
            x = margin
            chip_font = self._f('badge')
            for name in names:
                text_w = self._text_width(draw, name, chip_font)
                chip_w = text_w + self._u(34)
                if x + chip_w > width - margin:
                    break
                self._rounded_rect(draw, [x, y, x + chip_w, y + self._u(52)],
                                   self._u(10), (30, 41, 59))
                draw.text((x + self._u(17), y + self._u(13)), name,
                          font=chip_font, fill=PALETTE['text_on_dark'])
                x += chip_w + self._u(14)

        img.save(output_path)
        return output_path

    def _cjk_font(self):
        """返回当前使用的中文字体路径和 face index。"""
        font = self._fonts['body']
        return font.path, (font.index or 0)

    def _scaled_font(self, path: str, index: int, size: int) -> ImageFont.FreeTypeFont:
        try:
            return ImageFont.truetype(path, size, index=index)
        except (OSError, ValueError):
            return self._fonts['body']
