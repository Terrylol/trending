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
import sys

from card_generator import CardGenerator
from tts_generator import TTSGenerator
from video_composer import VideoComposer


class VideoWorkflow:
    def __init__(self):
        self.card_generator = CardGenerator({'resolution': '1920x1080', 'fps': 24})
        self.tts_generator = TTSGenerator({'voice': 'zh-CN-XiaoxiaoNeural'})
        self.video_composer = VideoComposer({'resolution': '1920x1080', 'fps': 24})
        self.output_dir = Path('output')
        self.output_dir.mkdir(exist_ok=True)
    
    def run(self, projects: List[Dict]):
        """执行视频生成工作流"""
        
        date = datetime.now().strftime('%Y.%m.%d')
        
        print("=" * 60)
        print("GitHub Trending 视频生成")
        print("=" * 60)
        print(f"日期: {date}")
        print(f"项目数: {len(projects)}")
        print("=" * 60)
        
        # Step 1: 生成幻灯片
        slides = self._generate_slides(projects, date)
        
        # Step 2: 生成语音
        audio_files = self._generate_audio(projects, date)
        
        # Step 3: 合成视频
        video_path = self._compose_video(slides, audio_files)
        
        print("\n" + "=" * 60)
        print("✓ 视频生成完成")
        print(f"视频路径: {video_path}")
        print("=" * 60)
        
        return video_path
    
    def _generate_slides(self, projects: List[Dict], date: str) -> List[str]:
        """生成幻灯片"""
        print("\n[Step 1/3] 生成幻灯片")
        
        slides = []
        
        # 标题卡片
        title_path = str(self.output_dir / "slide_title.png")
        self.card_generator.generate_title_card(date, title_path)
        slides.append(title_path)
        
        # 加载trending.json获取preview_image
        trending_data = {}
        trending_path = self.output_dir / 'trending.json'
        if trending_path.exists():
            import json
            with open(trending_path) as f:
                trending_data = json.load(f)
                trending_projects = {p['name']: p for p in trending_data.get('projects', [])}
        
        # 项目卡片
        for i, project in enumerate(projects):
            slide_path = str(self.output_dir / f"slide_{i}.png")
            
            # 合并trending数据（preview_image等）
            project_name = project.get('name', '')
            if project_name in trending_projects:
                trending_project = trending_projects[project_name]
                # 添加preview_image
                if 'preview_image' not in project and 'preview_image' in trending_project:
                    project['preview_image'] = trending_project['preview_image']
                # 添加其他字段
                for key in ['language', 'stars', 'url', 'description']:
                    if key not in project and key in trending_project:
                        project[key] = trending_project[key]
            
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
        import asyncio
        print("\n[Step 2/3] 生成语音")
        
        audio_files = []
        
        # 标题语音
        intro_text = f"今天是{date}，让我们来看看GitHub上最热门的项目"
        intro_path = str(self.output_dir / "audio_intro.mp3")
        asyncio.run(self.tts_generator.generate_audio(intro_text, intro_path))
        audio_files.append(intro_path)
        
        # 项目语音
        for i, project in enumerate(projects):
            audio_path = str(self.output_dir / f"audio_{i}.mp3")
            
            # 使用narrative字段生成语音
            narrative = project.get('narrative', {})
            hook = narrative.get('hook', '')
            body = narrative.get('body', '')
            call_to_action = narrative.get('call_to_action', '')
            
            # 组合文本：hook + body + call_to_action
            text = f"{hook}\n{body}\n{call_to_action}" if hook else body
            
            asyncio.run(self.tts_generator.generate_audio(text, audio_path))
            audio_files.append(audio_path)
        
        # 结尾语音
        ending_text = "以上就是今天的GitHub Trending，感谢观看"
        ending_path = str(self.output_dir / "audio_ending.mp3")
        asyncio.run(self.tts_generator.generate_audio(ending_text, ending_path))
        audio_files.append(ending_path)
        
        print(f"  ✓ 语音生成完成，共{len(audio_files)}个文件")
        return audio_files
    
    def _compose_video(self, slides: List[str], audio_files: List[str]) -> str:
        """合成视频"""
        print("\n[Step 3/3] 合成视频")
        
        output_path = str(self.output_dir / "trending_video.mp4")
        self.video_composer.compose(slides, audio_files, output_path)
        
        return output_path


def main():
    """主函数"""
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