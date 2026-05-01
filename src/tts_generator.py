"""
TTS语音生成
使用Edge-TTS（微软免费）
"""
import edge_tts
import asyncio
from typing import List, Dict
from pathlib import Path

class TTSGenerator:
    def __init__(self, config: Dict):
        self.voice = config.get('voice', 'zh-CN-XiaoxiaoNeural')
        self.rate = config.get('rate', '+0%')
        self.volume = config.get('volume', '+0%')
        
        output_dir = Path(config.get('output_dir', 'output/'))
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
    
    async def generate_audio(self, text: str, output_file: str):
        """生成单个音频文件"""
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            volume=self.volume
        )
        await communicate.save(output_file)
    
    def generate_intro_audio(self, date: str, output_file: str) -> str:
        """生成标题介绍语音"""
        text = f"欢迎收看今天的 GitHub Trending 热门项目推荐。{date}"
        
        asyncio.run(self.generate_audio(text, output_file))
        print(f"    ✓ 标题语音: {output_file}")
        
        return output_file
    
    def generate_project_audio(self, project: Dict, index: int, output_file: str) -> str:
        """生成项目介绍语音"""
        parts = []
        
        # 项目名
        parts.append(f"第{index + 1}个项目是{project['name']}。")
        
        # 项目概述
        if project.get('intro', {}).get('summary'):
            parts.append(project['intro']['summary'])
        
        # 技术分析
        if project.get('intro', {}).get('tech_analysis'):
            parts.append(project['intro']['tech_analysis'])
        
        # 使用指南（可选）
        if project.get('intro', {}).get('usage_guide'):
            # 使用指南太长可能使音频过长，这里可以选择性添加
            parts.append(project['intro']['usage_guide'])
        
        # Star数
        stars = project.get('stars', 0)
        if stars:
            parts.append(f"目前已获得{stars}个Star。")
        
        text = " ".join(parts)
        
        asyncio.run(self.generate_audio(text, output_file))
        print(f"    ✓ 项目语音 [{index + 1}]: {output_file}")
        
        return output_file
    
    def generate_ending_audio(self, output_file: str) -> str:
        """生成结尾语音"""
        text = "感谢观看，我们明天见。"
        
        asyncio.run(self.generate_audio(text, output_file))
        print(f"    ✓ 结尾语音: {output_file}")
        
        return output_file
    
    def generate_all_audio(self, projects: List[Dict], date: str) -> List[str]:
        """生成所有音频"""
        print(f"  生成语音...")
        
        audio_files = []
        
        # 标题语音
        intro_path = str(self.output_dir / "audio_intro.mp3")
        self.generate_intro_audio(date, intro_path)
        audio_files.append(intro_path)
        
        # 项目语音
        for i, project in enumerate(projects):
            audio_path = str(self.output_dir / f"audio_{i}.mp3")
            self.generate_project_audio(project, i, audio_path)
            audio_files.append(audio_path)
        
        # 结尾语音
        ending_path = str(self.output_dir / "audio_ending.mp3")
        self.generate_ending_audio(ending_path)
        audio_files.append(ending_path)
        
        print(f"  ✓ 语音生成完成，共{len(audio_files)}个文件")
        
        return audio_files


def get_mock_audio(project: Dict, index: int, output_dir: Path) -> str:
    """生成Mock音频（用于调试）"""
    # Mock音频实际上就是创建一个占位文件
    # 在实际调试时，应该使用真实的TTS生成
    audio_path = str(output_dir / f"audio_{index}.mp3")
    
    # 如果真实生成，可以这样：
    # tts = TTSGenerator({'voice': 'zh-CN-XiaoxiaoNeural'})
    # tts.generate_project_audio(project, index, audio_path)
    
    return audio_path