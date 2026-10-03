"""Edge-TTS 引擎实现

重构要点：voice / rate 不再硬编码，由 TTSGenerator 从 config 注入。
edge-tts 的 rate 用百分比字符串表示（+30% = 1.3 倍速）。
"""
import asyncio
from pathlib import Path

import edge_tts

from .base import BaseTTS


class EdgeTTSEngine(BaseTTS):
    """Microsoft Edge TTS 引擎（免费，无需 API key）"""

    def __init__(self, voice: str = 'zh-CN-XiaoxiaoNeural', speed: float = 1.0):
        self.voice = voice or 'zh-CN-XiaoxiaoNeural'
        self.speed = float(speed) if speed else 1.0
        self.volume = '+0%'

    def _rate_string(self) -> str:
        """把倍率转成 edge-tts 的百分比格式。"""
        pct = int(round((self.speed - 1.0) * 100))
        return f'{pct:+d}%'

    async def generate_audio(self, text: str, output_file: str) -> str:
        """生成 MP3 音频"""
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self._rate_string(),
            volume=self.volume,
        )
        await communicate.save(output_file)
        if not Path(output_file).exists() or Path(output_file).stat().st_size == 0:
            raise RuntimeError(f'edge-tts 未产出有效音频: {output_file}')
        return output_file

    def get_audio_format(self) -> str:
        return 'mp3'
