"""TTS 抽象基类"""
from abc import ABC, abstractmethod
from typing import Dict

class BaseTTS(ABC):
    """TTS 引擎基类"""
    
    @abstractmethod
    async def generate_audio(self, text: str, output_file: str) -> str:
        """生成音频文件
        
        Args:
            text: 要转换的文本
            output_file: 输出文件路径
        
        Returns:
            生成的音频文件路径
        """
        pass
    
    @abstractmethod
    def get_audio_format(self) -> str:
        """返回音频格式 (mp3/wav)"""
        pass