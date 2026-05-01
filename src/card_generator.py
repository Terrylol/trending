"""
现代化卡片生成器
- 清晰的左右布局
- 美观的排版
- 支持项目截图
- 1080p分辨率
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from typing import Dict, List, Tuple
from pathlib import Path

class CardGenerator:
    def __init__(self, config: Dict):
        self.width = 1920
        self.height = 1080
        
        output_dir = config.get('output_dir', 'output/')
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # 加载字体
        self._load_fonts()
    
    def _load_fonts(self):
        """加载字体（跨平台支持）"""
        # 字体大小
        sizes = {
            'title': 80,
            'subtitle': 52,
            'content': 42,
            'tag': 34,
            'number': 260
        }
        
        # 跨平台字体路径（按优先级）
        font_paths = self._get_font_paths()
        
        # 尝试加载字体
        loaded = False
        for font_name, font_path in font_paths.items():
            try:
                self.font_title = ImageFont.truetype(font_path, sizes['title'])
                self.font_subtitle = ImageFont.truetype(font_path, sizes['subtitle'])
                self.font_content = ImageFont.truetype(font_path, sizes['content'])
                self.font_tag = ImageFont.truetype(font_path, sizes['tag'])
                
                # 数字字体（使用系统英文字体）
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
        
        if system == 'Darwin':  # macOS
            fonts = {
                'PingFang': '/System/Library/Fonts/PingFang.ttc',
                'STHeiti': '/System/Library/Fonts/STHeiti Medium.ttc',
                'Hiragino': '/System/Library/Fonts/Hiragino Sans GB.ttc',
            }
        elif system == 'Windows':
            fonts = {
                'Microsoft YaHei': 'C:/Windows/Fonts/msyh.ttc',
                'SimHei': 'C:/Windows/Fonts/simhei.ttf',
                'SimSun': 'C:/Windows/Fonts/simsun.ttc',
            }
        elif system == 'Linux':
            fonts = {
                'Noto Sans CJK': '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
                'WenQuanYi': '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
                'Droid Sans Fallback': '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf',
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
        elif system == 'Linux':
            return '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
        else:
            return '/System/Library/Fonts/Helvetica.ttc'
    
    def generate_title_card(self, date: str, output_path: str):
        """生成标题卡片"""
        # 深色渐变背景
        img = self._create_gradient_bg((30, 58, 138), (66, 153, 225))
        draw = ImageDraw.Draw(img)
        
        # 主标题（增加顶部间距）
        title = "GitHub Trending"
        bbox = draw.textbbox((0, 0), title, font=self.font_title)
        title_width = bbox[2] - bbox[0]
        draw.text(((self.width - title_width) // 2, 280), title, 
                  fill=(255, 255, 255), font=self.font_title)
        
        # 副标题（增加间距）
        subtitle = f"今日热门项目推荐 · {date}"
        bbox = draw.textbbox((0, 0), subtitle, font=self.font_subtitle)
        subtitle_width = bbox[2] - bbox[0]
        draw.text(((self.width - subtitle_width) // 2, 420), subtitle, 
                  fill=(237, 242, 247), font=self.font_subtitle)
        
        # 装饰线（增加间距）
        line_width = 450
        draw.rectangle([((self.width - line_width) // 2, 540), 
                        ((self.width + line_width) // 2, 546)], 
                       fill=(255, 255, 255))
        
        img.save(output_path)
        print(f"    ✓ 标题卡片: {output_path}")
    
    def generate_project_card(self, project: Dict, index: int, output_path: str):
        """生成项目卡片"""
        # 配色方案
        colors = [
            (66, 153, 225),   # 蓝色
            (72, 187, 120),   # 绿色
            (237, 100, 166),  # 粉色
            (159, 122, 234),  # 紫色
            (246, 173, 85),   # 橙色
        ]
        accent_color = colors[index % len(colors)]
        
        # 白色背景
        img = Image.new('RGB', (self.width, self.height), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        
        # 左侧彩色条（更宽一些）
        draw.rectangle([0, 0, 16, self.height], fill=accent_color)
        
        # 项目编号（右上角，半透明）
        number_text = f"0{index + 1}"
        bbox = self.font_number.getbbox(number_text)
        number_width = bbox[2] - bbox[0]
        draw.text((self.width - number_width - 80, 60), number_text,
                  fill=(240, 240, 240), font=self.font_number)
        
        # 顶部信息区域（增加边距）
        # 项目名称
        name = project.get('name', 'Unknown')
        draw.text((80, 70), name, fill=(26, 32, 44), font=self.font_title)
        
        # 元信息标签（增加垂直间距）
        language = project.get('language', 'Unknown')
        stars = project.get('stars', 0)
        
        tag_y = 165
        tag_text = language
        tag_bbox = self.font_tag.getbbox(tag_text)
        tag_w = tag_bbox[2] - tag_bbox[0] + 28
        draw.rectangle([80, tag_y, 80 + tag_w, tag_y + 40], fill=accent_color)
        draw.text((94, tag_y + 6), tag_text, fill=(255, 255, 255), font=self.font_tag)
        
        # 星标数
        draw.text((100 + tag_w, tag_y + 6), f"⭐ {stars:,}", 
                  fill=(113, 128, 150), font=self.font_tag)
        
        # 分隔线（增加上下间距）
        draw.rectangle([80, 230, self.width - 80, 233], fill=(237, 242, 247))
        
        # 内容区域（增加顶部间距）
        content_y = 270
        
        # 左侧：项目截图
        screenshot_width = 0
        if project.get('preview_image'):
            try:
                screenshot = Image.open(project['preview_image'])
                # 截图宽度调整为700px，给文字更多空间
                screenshot_width = 700
                screenshot_height = int(screenshot.height * (screenshot_width / screenshot.width))
                
                # 限制截图高度，不超过520px
                if screenshot_height > 520:
                    screenshot_height = 520
                    screenshot_width = int(screenshot.width * (screenshot_height / screenshot.height))
                
                screenshot = screenshot.resize((screenshot_width, screenshot_height))
                
                # 添加边框和阴影
                border_size = 3
                shadow_offset = 12
                shadow = Image.new('RGB', (screenshot_width + border_size * 2 + shadow_offset, 
                                          screenshot.height + border_size * 2 + shadow_offset), 
                                  (200, 200, 200))
                shadow = shadow.filter(ImageFilter.GaussianBlur(8))
                img.paste(shadow, (80 + border_size, content_y + border_size))
                
                # 绘制白色边框
                border_box = Image.new('RGB', (screenshot_width + border_size * 2, 
                                               screenshot.height + border_size * 2), 
                                      (255, 255, 255))
                img.paste(border_box, (80, content_y))
                
                # 粘贴截图
                img.paste(screenshot, (80 + border_size, content_y + border_size))
            except Exception as e:
                print(f"      截图加载失败: {e}")
                screenshot_width = 0
        
        # 右侧：文字内容（增加左边距）
        text_x = 820 if screenshot_width > 0 else 80
        text_width = self.width - text_x - 100
        y = content_y
        
        # 计算可用垂直空间
        max_y = self.height - 120  # 底部留120px
        
        # 获取 narrative 数据
        narrative = project.get('narrative', {})
        hook = narrative.get('hook', '')
        body = narrative.get('body', '')
        
        # 如果没有 narrative，使用 description
        if not hook and not body:
            hook = project.get('description', '')[:60] + '...'
        
        # 亮点部分（增加间距）
        if hook:
            # 小标题
            draw.rectangle([text_x, y, text_x + 110, y + 38], fill=accent_color)
            draw.text((text_x + 16, y + 4), "亮点", fill=(255, 255, 255), font=self.font_tag)
            y += 65
            
            # 内容（增加行间距）
            lines = self._wrap_text(hook, self.font_content, text_width)
            for line in lines:
                if y + 55 > max_y:
                    break
                draw.text((text_x, y), line, fill=(45, 55, 72), font=self.font_content)
                y += 55
            y += 45
        
        # 介绍部分（增加间距）
        if body:
            # 小标题
            draw.rectangle([text_x, y, text_x + 110, y + 38], fill=accent_color)
            draw.text((text_x + 16, y + 4), "介绍", fill=(255, 255, 255), font=self.font_tag)
            y += 65
            
            # 内容（增加行间距）
            lines = self._wrap_text(body, self.font_content, text_width)
            for line in lines:
                if y + 55 > max_y:
                    break
                draw.text((text_x, y), line, fill=(74, 85, 104), font=self.font_content)
                y += 55
        
        # 底部：项目链接（增加底部间距）
        url = project.get('url', '')
        if url:
            draw.text((80, self.height - 70), 
                      f"🔗 {url}", 
                      fill=(160, 174, 192), 
                      font=self.font_tag)
        
        img.save(output_path)
        print(f"    ✓ 项目卡片 [{index + 1}]: {output_path}")
    
    def generate_ending_card(self, output_path: str):
        """生成结尾卡片"""
        # 深色渐变背景
        img = self._create_gradient_bg((66, 153, 225), (30, 58, 138))
        draw = ImageDraw.Draw(img)
        
        # 主标题
        text = "感谢观看"
        bbox = draw.textbbox((0, 0), text, font=self.font_title)
        text_width = bbox[2] - bbox[0]
        draw.text(((self.width - text_width) // 2, 350), text,
                  fill=(255, 255, 255), font=self.font_title)
        
        # 副标题
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
