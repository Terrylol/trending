"""Edge-TTS 引擎实现"""
import edge_tts
import asyncio
from .base import BaseTTS

class EdgeTTSEngine(BaseTTS):
    """Microsoft Edge TTS 引擎"""
    
    def __init__(self):
        self.voice = "zh-CN-XiaoxiaoNeural"
        self.rate = "+0%"
        self.volume = "+0%"
    
    async def generate_audio(self, text: str, output_file: str) -> str:
        """生成 MP3 音频"""
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            volume=self.volume
        )
        await communicate.save(output_file)
        return output_file
    
    def get_audio_format(self) -> str:
        """返回 mp3"""
        return "mp3"