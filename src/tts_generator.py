"""
TTS 语音生成
支持多种引擎: edge-tts, vectorengine (Gemini TTS)
支持降级：vectorengine 失败后自动降级到 edge-tts
"""
import asyncio
from typing import List, Dict
from pathlib import Path
import sys
sys.path.insert(0, 'src')
from tts import get_tts_engine

class TTSGenerator:
    def __init__(self, config: Dict):
        self.engine_name = config.get('engine', 'edge')
        self.apikey = config.get('apikey')
        
        self.tts_engine = get_tts_engine(self.engine_name, self.apikey)
        self.audio_format = self.tts_engine.get_audio_format()
        
        # 降级引擎（仅 vectorengine 需要降级）
        self.fallback_engine = None
        self.fallback_format = None
        if self.engine_name == 'vectorengine':
            self.fallback_engine = get_tts_engine('edge')
            self.fallback_format = self.fallback_engine.get_audio_format()
        
        output_dir = Path(config.get('output_dir', 'output/'))
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
    
    async def generate_audio(self, text: str, output_file: str):
        """生成单个音频文件，失败时自动降级"""
        try:
            await self.tts_engine.generate_audio(text, output_file)
        except Exception as e:
            if self.fallback_engine:
                print(f"      ⚠ {self.engine_name} 失败，降级到 edge-tts...")
                # 修改输出文件扩展名
                output_path = Path(output_file)
                fallback_file = str(output_path.with_suffix(f'.{self.fallback_format}'))
                await self.fallback_engine.generate_audio(text, fallback_file)
                # 更新文件路径
                return fallback_file
            else:
                raise e
    
    def generate_intro_audio(self, date: str, output_file: str) -> str:
        """生成标题介绍语音"""
        text = f"欢迎收看今天的 GitHub Trending 热门项目推荐。{date}"
        
        actual_file = asyncio.run(self.generate_audio(text, output_file))
        
        if actual_file and actual_file != output_file:
            self.audio_format = self.fallback_format
        
        print(f"    ✓ 标题语音: {actual_file or output_file}")
        
        return actual_file or output_file
    
    def generate_project_audio(self, project: Dict, index: int, output_file: str) -> str:
        """生成项目介绍语音"""
        parts = []
        
        narrative = project.get('narrative', {})
        
        parts.append(f"第{index + 1}个项目是{project['name']}。")
        
        if narrative.get('hook'):
            parts.append(narrative['hook'])
        
        if narrative.get('body'):
            parts.append(narrative['body'])
        
        if narrative.get('call_to_action'):
            parts.append(narrative['call_to_action'])
        
        stars = project.get('stars', 0)
        if stars:
            parts.append(f"目前已获得{stars}个Star。")
        
        text = " ".join(parts)
        
        actual_file = asyncio.run(self.generate_audio(text, output_file))
        
        # 如果降级了，更新实际文件路径
        if actual_file and actual_file != output_file:
            self.audio_format = self.fallback_format
        
        print(f"    ✓ 项目语音 [{index + 1}]: {actual_file or output_file}")
        
        return actual_file or output_file
    
    def generate_ending_audio(self, output_file: str) -> str:
        """生成结尾语音"""
        text = "感谢观看，我们明天见。"
        
        actual_file = asyncio.run(self.generate_audio(text, output_file))
        
        if actual_file and actual_file != output_file:
            self.audio_format = self.fallback_format
        
        print(f"    ✓ 结尾语音: {actual_file or output_file}")
        
        return actual_file or output_file
    
    def generate_all_audio(self, projects: List[Dict], date: str) -> List[str]:
        """生成所有音频"""
        print(f"  生成语音 (引擎: {self.engine_name})...")
        
        audio_files = []
        
        intro_path = str(self.output_dir / f"audio_intro.{self.audio_format}")
        actual_intro = self.generate_intro_audio(date, intro_path)
        audio_files.append(actual_intro)
        
        for i, project in enumerate(projects):
            audio_path = str(self.output_dir / f"audio_{i}.{self.audio_format}")
            actual_audio = self.generate_project_audio(project, i, audio_path)
            audio_files.append(actual_audio)
        
        ending_path = str(self.output_dir / f"audio_ending.{self.audio_format}")
        actual_ending = self.generate_ending_audio(ending_path)
        audio_files.append(actual_ending)
        
        print(f"  ✓ 语音生成完成，共{len(audio_files)}个文件")
        
        return audio_files
