"""
视频生成工作流
- 接收Agent生成的项目总结
- 生成幻灯片、语音、视频
- 可选上传到B站
"""
from typing import List, Dict
from datetime import datetime
from pathlib import Path
import json
import os
import sys

from card_generator import CardGenerator
from tts_generator import TTSGenerator
from video_composer import VideoComposer
from remotion_composer import RemotionComposer


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()


def setup_run_logging() -> Path:
    logs_dir = Path('output') / 'logs'
    logs_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime('%Y%m%d_%H%M%S') + f'_{os.getpid()}'
    log_path = logs_dir / f'workflow_{run_id}.log'
    log_file = open(log_path, 'a', encoding='utf-8', buffering=1)
    sys.stdout = Tee(sys.__stdout__, log_file)
    sys.stderr = Tee(sys.__stderr__, log_file)
    print(f"[workflow] log_file={log_path}")
    return log_path


class VideoWorkflow:
    def __init__(self, config_path: str = None):
        config = self._load_config(config_path)
        
        self.card_generator = CardGenerator({'resolution': '1920x1080', 'fps': 24})
        
        tts_config = config.get('tts', {'engine': 'edge', 'apikey': ''})
        self.tts_generator = TTSGenerator(tts_config)
        
        video_config = config.get('video', {})
        self.video_renderer = video_config.get('renderer', 'moviepy')
        renderer_config = {'resolution': video_config.get('resolution', '1920x1080'), 'fps': video_config.get('fps', 24)}
        if self.video_renderer == 'remotion':
            self.video_composer = RemotionComposer(renderer_config)
        else:
            self.video_composer = VideoComposer(renderer_config)
        self.output_dir = Path('output')
        self.output_dir.mkdir(exist_ok=True)
    
    def _load_config(self, config_path: str = None) -> Dict:
        """加载配置文件"""
        if not config_path:
            config_path = 'config/config.json'
        
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file) as f:
                return json.load(f)
        
        return {'tts': {'engine': 'edge', 'apikey': ''}}
    
    def run(self, projects: List[Dict]):
        """执行视频生成工作流"""
        
        date = datetime.now().strftime('%Y.%m.%d')
        
        print("=" * 60)
        print("GitHub Trending 视频生成")
        print("=" * 60)
        print(f"日期: {date}")
        print(f"项目数: {len(projects)}")
        print(f"渲染器: {self.video_renderer}")
        print("=" * 60)

        projects = self._enrich_projects(projects)
        
        # Step 1: Remotion 直接使用项目数据；MoviePy 需要先生成静态幻灯片
        slides = []
        if self.video_renderer != 'remotion':
            slides = self._generate_slides(projects, date)
        
        # Step 2: 生成语音
        audio_files = self._generate_audio(projects, date)
        
        # Step 3: 合成视频
        if self.video_renderer == 'remotion':
            video_path = self._compose_remotion_video(projects, audio_files)
        else:
            video_path = self._compose_video(slides, audio_files)
        
        print("\n" + "=" * 60)
        print("✓ 视频生成完成")
        print(f"视频路径: {video_path}")
        print("=" * 60)
        
        return video_path
    
    def _enrich_projects(self, projects: List[Dict]) -> List[Dict]:
        """用 trending.json 补齐 preview_image/url/stars 等渲染必需字段。优先按 url/author+name 匹配，避免同名仓库串数据。"""
        trending_path = self.output_dir / 'trending.json'
        if not trending_path.exists():
            return projects

        with open(trending_path) as f:
            trending_data = json.load(f)

        def repo_key(project: Dict) -> str:
            url = (project.get('url') or '').rstrip('/')
            if url:
                return url.lower()
            author = (project.get('author') or project.get('owner') or '').strip().strip('/')
            name = (project.get('name') or '').strip().strip('/')
            return f'{author}/{name}'.lower() if author and name else name.lower()

        trending_projects = {}
        trending_by_name = {}
        for p in trending_data.get('projects', []):
            key = repo_key(p)
            if key:
                trending_projects[key] = p
            if p.get('name'):
                trending_by_name.setdefault(p.get('name'), p)

        enriched = []
        for project in projects:
            merged = dict(project)
            trending_project = trending_projects.get(repo_key(merged)) or trending_by_name.get(merged.get('name', ''))
            if trending_project:
                for key in ['preview_image', 'language', 'stars', 'url', 'description', 'license', 'topics', 'author', 'owner']:
                    if key not in merged and key in trending_project:
                        merged[key] = trending_project[key]
            enriched.append(merged)
        return enriched

    def _generate_slides(self, projects: List[Dict], date: str) -> List[str]:
        """生成幻灯片"""
        print("\n[Step 1/3] 生成幻灯片")
        
        slides = []
        
        # 标题卡片
        title_path = str(self.output_dir / "slide_title.png")
        self.card_generator.generate_title_card(date, title_path)
        slides.append(title_path)
        
        # 项目卡片
        for i, project in enumerate(projects):
            slide_path = str(self.output_dir / f"slide_{i}.png")
            
            # 直接传递完整的项目数据
            self.card_generator.generate_project_card(project, i, slide_path)
            slides.append(slide_path)
        
        # 结尾卡片
        ending_path = str(self.output_dir / "slide_ending.png")
        self.card_generator.generate_ending_card(ending_path)
        slides.append(ending_path)
        
        print(f"  ✓ 幻灯片生成完成，共{len(slides)}张")
        return slides
    
    def _generate_audio(self, projects: List[Dict], date: str) -> List[str]:
        """生成语音"""
        print("\n[Step 2/3] 生成语音")
        
        audio_files = self.tts_generator.generate_all_audio(projects, date)
        
        return audio_files
    
    def _compose_remotion_video(self, projects: List[Dict], audio_files: List[str]) -> str:
        """使用 Remotion 合成视频"""
        print("\n[Step 3/3] Remotion 合成视频")
        output_path = str(self.output_dir / "trending_video.mp4")
        self.video_composer.compose(projects, audio_files, output_path)
        return output_path

    def _compose_video(self, slides: List[str], audio_files: List[str]) -> str:
        """合成视频"""
        print("\n[Step 3/3] 合成视频")
        
        output_path = str(self.output_dir / "trending_video.mp4")
        self.video_composer.compose(slides, audio_files, output_path)
        
        return output_path


def main():
    """主函数"""
    setup_run_logging()

    if len(sys.argv) < 2:
        print("使用方式: python workflow.py --projects '<JSON>'")
        sys.exit(1)
    
    # 解析参数
    args = sys.argv[1:]
    
    if args[0] == '--projects':
        projects_json = args[1]
        projects = json.loads(projects_json)
        
        if isinstance(projects, dict) and 'projects' in projects:
            projects = projects['projects']
        
        # 执行工作流
        workflow = VideoWorkflow()
        video_path = workflow.run(projects)
        
        print(f"\n视频已生成: {video_path}")
    else:
        print("错误: 未知的参数")
        sys.exit(1)


if __name__ == '__main__':
    main()