"""
现代化卡片生成器
- 清晰的左右布局
- 美观的排版
- 支持项目截图
- 支持 Star 历史趋势图（左下角）
- 1080p分辨率
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import requests
import subprocess
import tempfile
import os

class CardGenerator:
    def __init__(self, config: Dict):
        self.width = 1920
        self.height = 1080
        
        output_dir = config.get('output_dir', 'output/')
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Star 历史图缓存目录
        self.star_history_dir = self.output_dir / 'star_history'
        self.star_history_dir.mkdir(exist_ok=True)
        
        # 加载字体
        self._load_fonts()
    
    def _load_fonts(self):
        """加载字体（跨平台支持）"""
        sizes = {
            'title': 80,
            'subtitle': 52,
            'content': 42,
            'tag': 34,
            'number': 260
        }
        
        font_paths = self._get_font_paths()
        loaded = False
        for font_name, font_path in font_paths.items():
            try:
                self.font_title = ImageFont.truetype(font_path, sizes['title'])
                self.font_subtitle = ImageFont.truetype(font_path, sizes['subtitle'])
                self.font_content = ImageFont.truetype(font_path, sizes['content'])
                self.font_tag = ImageFont.truetype(font_path, sizes['tag'])
                
                number_font = self._get_number_font()
                self.font_number = ImageFont.truetype(number_font, sizes['number'])
                
                print(f"    ✓ 字体加载成功: {font_name}")
                loaded = True
                break
            except:
                continue
        
        if not loaded:
            print("    ⚠ 未找到合适字体，使用默认字体")
            self.font_title = ImageFont.load_default()
            self.font_subtitle = ImageFont.load_default()
            self.font_content = ImageFont.load_default()
            self.font_tag = ImageFont.load_default()
            self.font_number = ImageFont.load_default()
    
    def _get_font_paths(self) -> Dict[str, str]:
        """获取跨平台字体路径"""
        import platform
        system = platform.system()
        
        fonts = {}
        if system == 'Darwin':
            fonts = {
                'PingFang': '/System/Library/Fonts/PingFang.ttc',
                'STHeiti': '/System/Library/Fonts/STHeiti Medium.ttc',
            }
        elif system == 'Windows':
            fonts = {
                'Microsoft YaHei': 'C:/Windows/Fonts/msyh.ttc',
                'SimHei': 'C:/Windows/Fonts/simhei.ttf',
            }
        elif system == 'Linux':
            fonts = {
                'Noto Sans CJK': '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
                'WenQuanYi': '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
            }
        return fonts
    
    def _get_number_font(self) -> str:
        """获取数字/英文字体"""
        import platform
        system = platform.system()
        if system == 'Darwin':
            return '/System/Library/Fonts/Helvetica.ttc'
        elif system == 'Windows':
            return 'C:/Windows/Fonts/arial.ttf'
        else:
            return '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    
    def generate_title_card(self, date: str, output_path: str):
        """生成标题卡片"""
        img = self._create_gradient_bg((30, 58, 138), (66, 153, 225))
        draw = ImageDraw.Draw(img)
        
        title = "GitHub Trending"
        bbox = draw.textbbox((0, 0), title, font=self.font_title)
        title_width = bbox[2] - bbox[0]
        draw.text(((self.width - title_width) // 2, 280), title, 
                  fill=(255, 255, 255), font=self.font_title)
        
        subtitle = f"今日热门项目推荐 · {date}"
        bbox = draw.textbbox((0, 0), subtitle, font=self.font_subtitle)
        subtitle_width = bbox[2] - bbox[0]
        draw.text(((self.width - subtitle_width) // 2, 420), subtitle, 
                  fill=(237, 242, 247), font=self.font_subtitle)
        
        line_width = 450
        draw.rectangle([((self.width - line_width) // 2, 540), 
                        ((self.width + line_width) // 2, 546)], 
                       fill=(255, 255, 255))
        
        img.save(output_path)
        print(f"    ✓ 标题卡片: {output_path}")
    
    def _fetch_star_history_image(self, owner: str, repo: str) -> Optional[str]:
        """获取 Star 历史趋势图并转换为 PNG"""
        try:
            url = f"https://api.star-history.com/chart?repos={owner}/{repo}&type=date&theme=light"
            
            cache_file = self.star_history_dir / f"{owner}_{repo}.png"
            if cache_file.exists():
                return str(cache_file)
            
            response = requests.get(url, timeout=30)
            if response.status_code != 200:
                print(f"      Star 历史图获取失败: HTTP {response.status_code}")
                return None
            
            svg_content = response.content
            svg_temp = tempfile.NamedTemporaryFile(suffix='.svg', delete=False)
            svg_temp.write(svg_content)
            svg_temp.close()
            
            width = 550
            height = 360
            
            # 尝试 cairosvg
            try:
                import cairosvg
                cairosvg.svg2png(
                    url=svg_temp.name,
                    write_to=str(cache_file),
                    output_width=width,
                    output_height=height
                )
                if cache_file.exists():
                    os.unlink(svg_temp.name)
                    return str(cache_file)
            except ImportError:
                pass
            
            # 尝试 rsvg-convert
            try:
                result = subprocess.run([
                    'rsvg-convert',
                    '-w', str(width),
                    '-h', str(height),
                    '-o', str(cache_file),
                    svg_temp.name
                ], capture_output=True, timeout=30)
                
                if result.returncode == 0 and cache_file.exists():
                    os.unlink(svg_temp.name)
                    return str(cache_file)
            except (subprocess.SubprocessError, FileNotFoundError):
                pass
            
            # 尝试 inkscape
            try:
                result = subprocess.run([
                    'inkscape', svg_temp.name,
                    '--export-type=png',
                    f'--export-filename={cache_file}',
                    f'--export-width={width}',
                    f'--export-height={height}'
                ], capture_output=True, timeout=30)
                
                if result.returncode == 0 and cache_file.exists():
                    os.unlink(svg_temp.name)
                    return str(cache_file)
            except (subprocess.SubprocessError, FileNotFoundError):
                pass
            
            if os.path.exists(svg_temp.name):
                os.unlink(svg_temp.name)
            
            print(f"      Star 历史图转换失败: 需要 cairosvg/rsvg-convert/inkscape")
            return None
            
        except Exception as e:
            print(f"      Star 历史图获取失败: {e}")
            return None
    
    def generate_project_card(self, project: Dict, index: int, output_path: str):
        """生成项目卡片（包含 Star 历史趋势图）"""
        colors = [
            (66, 153, 225),   # 蓝色
            (72, 187, 120),   # 绿色
            (237, 100, 166),  # 粉色
            (159, 122, 234),  # 紫色
            (246, 173, 85),   # 橙色
        ]
        accent_color = colors[index % len(colors)]
        
        img = Image.new('RGB', (self.width, self.height), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        
        # 左侧彩色条
        draw.rectangle([0, 0, 16, self.height], fill=accent_color)
        
        # 项目编号（右上角）
        number_text = f"0{index + 1}"
        bbox = self.font_number.getbbox(number_text)
        number_width = bbox[2] - bbox[0]
        draw.text((self.width - number_width - 80, 60), number_text,
                  fill=(240, 240, 240), font=self.font_number)
        
        # 顶部信息区域
        name = project.get('name', 'Unknown')
        draw.text((80, 60), name, fill=(26, 32, 44), font=self.font_title)
        
        language = project.get('language', 'Unknown')
        stars = project.get('stars', 0)
        license_name = project.get('license', '')
        topics = project.get('topics', [])
        
        tag_y = 180
        tag_h = 40  # 标签高度
        current_x = 80
        
        # 语言标签（彩色）
        tag_text = language
        tag_bbox = self.font_tag.getbbox(tag_text)
        tag_text_width = tag_bbox[2] - tag_bbox[0]
        tag_w = tag_text_width + 24
        draw.rectangle([current_x, tag_y, current_x + tag_w, tag_y + tag_h], fill=accent_color)
        text_offset_y = (tag_h - (tag_bbox[3] - tag_bbox[1])) // 2 - tag_bbox[1]
        draw.text((current_x + 12, tag_y + text_offset_y), tag_text, fill=(255, 255, 255), font=self.font_tag)
        current_x += tag_w + 12
        
        # Star 数
        draw.text((current_x, tag_y + text_offset_y), f"★ {stars:,}", fill=(113, 128, 150), font=self.font_tag)
        current_x += draw.textlength(f"★ {stars:,}", font=self.font_tag) + 20
        
        # License 标签
        if license_name:
            lic_bbox = self.font_tag.getbbox(license_name)
            lic_w = lic_bbox[2] - lic_bbox[0] + 20
            draw.rectangle([current_x, tag_y, current_x + lic_w, tag_y + tag_h], fill=(226, 232, 240))
            draw.text((current_x + 10, tag_y + text_offset_y), license_name, fill=(100, 116, 139), font=self.font_tag)
            current_x += lic_w + 12
        
        # Topics 标签
        if topics:
            for topic in topics[:4]:  # 最多显示4个
                topic_bbox = self.font_tag.getbbox(topic)
                topic_w = topic_bbox[2] - topic_bbox[0] + 16
                if current_x + topic_w > self.width - 80:
                    break
                draw.rectangle([current_x, tag_y, current_x + topic_w, tag_y + tag_h], fill=(241, 245, 249))
                draw.text((current_x + 8, tag_y + text_offset_y), topic, fill=(71, 85, 105), font=self.font_tag)
                current_x += topic_w + 8
        
        # 分隔线
        draw.rectangle([80, 240, self.width - 80, 243], fill=(237, 242, 247))
        
        # === Star 历史图参数 ===
        # Star 历史图宽度 550px，在截图下方左对齐（偏移50px）
        star_chart_width = 550
        star_chart_height = 360
        star_chart_x = 130
        star_chart_y = self.height - star_chart_height - 75
        
        # 获取 Star 历史图
        star_chart_path = None
        url = project.get('url', '')
        if url:
            parts = url.split('/')
            if len(parts) >= 5 and parts[3] and parts[4]:
                owner = parts[3]
                repo = parts[4]
                star_chart_path = self._fetch_star_history_image(owner, repo)
                if star_chart_path:
                    # 绘制背景框
                    draw.rectangle([
                        star_chart_x - 3, 
                        star_chart_y - 3,
                        star_chart_x + star_chart_width + 3,
                        star_chart_y + star_chart_height + 3
                    ], fill=(255, 255, 255), outline=(220, 225, 230), width=1)
                    
                    try:
                        star_chart = Image.open(star_chart_path)
                        star_chart = star_chart.resize((star_chart_width, star_chart_height))
                        # 处理 RGBA 格式，确保背景不透明
                        if star_chart.mode == 'RGBA':
                            bg = Image.new('RGB', star_chart.size, (255, 255, 255))
                            bg.paste(star_chart, mask=star_chart.split()[3])
                            star_chart = bg
                        img.paste(star_chart, (star_chart_x, star_chart_y))
                    except Exception as e:
                        print(f"      Star 历史图粘贴失败: {e}")
                        star_chart_path = None
        
        # === 内容区域 ===
        content_y = 270
        
        # 左侧：项目截图（为 Star 历史图留空间）
        screenshot_width = 0
        screenshot_height = 0
        max_screenshot_height = star_chart_y - content_y - 30 if star_chart_path else 520
        
        if project.get('preview_image'):
            try:
                screenshot = Image.open(project['preview_image'])
                screenshot_width = 700
                screenshot_height = int(screenshot.height * (screenshot_width / screenshot.width))
                
                if screenshot_height > max_screenshot_height:
                    screenshot_height = max_screenshot_height
                    screenshot_width = int(screenshot.width * (screenshot_height / screenshot.height))
                
                screenshot = screenshot.resize((screenshot_width, screenshot_height))
                
                border_size = 3
                shadow_offset = 12
                shadow = Image.new('RGB', (screenshot_width + border_size * 2 + shadow_offset, 
                                          screenshot_height + border_size * 2 + shadow_offset), 
                                  (200, 200, 200))
                shadow = shadow.filter(ImageFilter.GaussianBlur(8))
                img.paste(shadow, (80 + border_size, content_y + border_size))
                
                border_box = Image.new('RGB', (screenshot_width + border_size * 2, 
                                               screenshot_height + border_size * 2), 
                                      (255, 255, 255))
                img.paste(border_box, (80, content_y))
                img.paste(screenshot, (80 + border_size, content_y + border_size))
            except Exception as e:
                print(f"      截图加载失败: {e}")
                screenshot_width = 0
        
        # 右侧：文字内容
        text_x = 820 if screenshot_width > 0 else 80
        text_width = self.width - text_x - 100
        y = content_y
        
        # 右边文字区域不受 Star 历史图影响，可以延伸到画面底部
        max_y = self.height - 100
        
        narrative = project.get('narrative', {})
        hook = narrative.get('hook', '')
        body = narrative.get('body', '')
        
        if not hook and not body:
            desc = project.get('description', '')
            hook = desc[:60] + '...' if len(desc) > 60 else desc
        
        if hook:
            # 标签背景和文字居中（使用 subtitle 字体，更大）
            label_text = "亮点"
            label_bbox = self.font_subtitle.getbbox(label_text)
            label_w = label_bbox[2] - label_bbox[0] + 36
            label_h = 55  # 增加 5px
            draw.rectangle([text_x, y, text_x + label_w, y + label_h], fill=accent_color)
            label_offset_x = (label_w - (label_bbox[2] - label_bbox[0])) // 2
            label_offset_y = (label_h - (label_bbox[3] - label_bbox[1])) // 2 - label_bbox[1]
            draw.text((text_x + label_offset_x, y + label_offset_y), label_text, fill=(255, 255, 255), font=self.font_subtitle)
            y += 72
            
            lines = self._wrap_text(hook, self.font_content, text_width)
            for line in lines:
                if y + 55 > max_y:
                    break
                draw.text((text_x, y), line, fill=(45, 55, 72), font=self.font_content)
                y += 55
            y += 45
        
        if body:
            # 标签背景和文字居中（使用 subtitle 字体，更大）
            label_text = "介绍"
            label_bbox = self.font_subtitle.getbbox(label_text)
            label_w = label_bbox[2] - label_bbox[0] + 36
            label_h = 55  # 增加 5px
            draw.rectangle([text_x, y, text_x + label_w, y + label_h], fill=accent_color)
            label_offset_x = (label_w - (label_bbox[2] - label_bbox[0])) // 2
            label_offset_y = (label_h - (label_bbox[3] - label_bbox[1])) // 2 - label_bbox[1]
            draw.text((text_x + label_offset_x, y + label_offset_y), label_text, fill=(255, 255, 255), font=self.font_subtitle)
            y += 72
            
            lines = self._wrap_text(body, self.font_content, text_width)
            for line in lines:
                if y + 55 > max_y:
                    break
                draw.text((text_x, y), line, fill=(74, 85, 104), font=self.font_content)
                y += 55
        
        if url:
            # GitHub logo + URL
            try:
                logo = Image.open('assets/github_logo.png')
                logo_size = 45
                logo = logo.resize((logo_size, logo_size))
                # 处理 RGBA 格式
                if logo.mode == 'RGBA':
                    bg = Image.new('RGB', logo.size, (255, 255, 255))
                    bg.paste(logo, mask=logo.split()[3])
                    logo = bg
                # 文字 y 位置
                text_y = self.height - 70
                # logo 往下移，和文字视觉居中
                logo_y = text_y + 2
                img.paste(logo, (80, logo_y))
                draw.text((80 + logo_size + 10, text_y), url, fill=(160, 174, 192), font=self.font_tag)
            except:
                draw.text((80, self.height - 70), url, fill=(160, 174, 192), font=self.font_tag)
        
        img.save(output_path)
        print(f"    ✓ 项目卡片 [{index + 1}]: {output_path}")
    
    def generate_ending_card(self, output_path: str):
        """生成结尾卡片"""
        img = self._create_gradient_bg((66, 153, 225), (30, 58, 138))
        draw = ImageDraw.Draw(img)
        
        text = "感谢观看"
        bbox = draw.textbbox((0, 0), text, font=self.font_title)
        text_width = bbox[2] - bbox[0]
        draw.text(((self.width - text_width) // 2, 350), text,
                  fill=(255, 255, 255), font=self.font_title)
        
        subtitle = "每日更新 GitHub Trending"
        bbox = draw.textbbox((0, 0), subtitle, font=self.font_subtitle)
        subtitle_width = bbox[2] - bbox[0]
        draw.text(((self.width - subtitle_width) // 2, 480), subtitle,
                  fill=(237, 242, 247), font=self.font_subtitle)
        
        img.save(output_path)
        print(f"    ✓ 结尾卡片: {output_path}")
    
    def _create_gradient_bg(self, color1: Tuple[int, int, int], 
                            color2: Tuple[int, int, int]) -> Image.Image:
        """创建渐变背景"""
        img = Image.new('RGB', (self.width, self.height))
        draw = ImageDraw.Draw(img)
        
        for y in range(self.height):
            ratio = y / self.height
            r = int(color1[0] + (color2[0] - color1[0]) * ratio)
            g = int(color1[1] + (color2[1] - color1[1]) * ratio)
            b = int(color1[2] + (color2[2] - color1[2]) * ratio)
            draw.line([(0, y), (self.width, y)], fill=(r, g, b))
        
        return img
    
    def _wrap_text(self, text: str, font, max_width: int) -> List[str]:
        """文字自动换行"""
        lines = []
        line = ""
        
        for char in text:
            test_line = line + char
            bbox = font.getbbox(test_line)
            if bbox[2] <= max_width:
                line = test_line
            else:
                if line:
                    lines.append(line)
                line = char
        
        if line:
            lines.append(line)
        
        return lines
