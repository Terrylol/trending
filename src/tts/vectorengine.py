"""VectorEngine Gemini TTS 引擎实现"""
import requests
import base64
import wave
import os
import time
from typing import Dict
from .base import BaseTTS

class VectorEngineTTS(BaseTTS):
    """VectorEngine Gemini TTS 引擎"""
    
    def __init__(self, apikey: str):
        self.apikey = apikey
        self.base_url = "https://api.vectorengine.ai/v1beta/models/gemini-2.5-pro-preview-tts:generateContent"
        self.voice = "Aoede"
        self.speed = 1.3  # 语速倍率 (1.0=正常, 1.3=快30%) — 通过 ffmpeg atempo 后处理实现
        self.max_retries = 3
        self.retry_delay = 5
    
    async def generate_audio(self, text: str, output_file: str) -> str:
        """生成 WAV 音频，速度 > 1.0 时用 ffmpeg atempo 加速"""
        raw_file = output_file
        need_temp = self.speed > 1.0 and abs(self.speed - 1.0) > 0.01
        if need_temp:
            raw_file = output_file + ".raw.wav"
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}?key={self.apikey}",
                    json={
                        "contents": [{"parts": [{"text": text}]}],
                        "generationConfig": {
                            "responseModalities": ["AUDIO"],
                            "speechConfig": {
                                "voiceConfig": {
                                    "prebuiltVoiceConfig": {
                                        "voiceName": self.voice
                                    }
                                }
                            }
                        }
                    },
                    timeout=120
                )
                
                data = response.json()
                
                if "candidates" not in data:
                    error_msg = data.get("error", {}).get("message", "Unknown error")
                    if "负载已饱和" in error_msg or "稍后再试" in error_msg:
                        if attempt < self.max_retries - 1:
                            print(f"      API 限流，{self.retry_delay}秒后重试 ({attempt + 1}/{self.max_retries})...")
                            time.sleep(self.retry_delay)
                            continue
                    raise RuntimeError(f"TTS 生成失败: {error_msg}")
                
                audio_data = base64.b64decode(
                    data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
                )
                
                with wave.open(raw_file, "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(24000)
                    wav_file.writeframes(audio_data)
                
                # ffmpeg atempo 加速
                if need_temp:
                    self._apply_atempo(raw_file, output_file)
                    os.remove(raw_file)
                
                return output_file
                
            except requests.exceptions.Timeout:
                if attempt < self.max_retries - 1:
                    print(f"      请求超时，{self.retry_delay}秒后重试 ({attempt + 1}/{self.max_retries})...")
                    time.sleep(self.retry_delay)
                    continue
                raise RuntimeError(f"TTS 生成超时，已重试{self.max_retries}次")
        
        raise RuntimeError("TTS 生成失败")
    
    def _apply_atempo(self, input_path: str, output_path: str):
        """用 ffmpeg atempo 滤镜变速音频，不改变音调"""
        # atempo 范围 0.5~2.0；超出时链式串联
        speed = self.speed
        filters = []
        while speed > 2.0:
            filters.append("atempo=2.0")
            speed /= 2.0
        filters.append(f"atempo={speed:.4f}")
        atempo_filter = ",".join(filters)
        
        import subprocess
        result = subprocess.run([
            'ffmpeg', '-y', '-i', input_path,
            '-filter:a', atempo_filter,
            '-ar', '24000',
            output_path
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            # atempo 失败时降级：直接重命名原文件
            print(f"      ⚠ ffmpeg atempo 失败，使用原始语速: {result.stderr[:200]}")
            import shutil
            shutil.move(input_path, output_path)
    
    def get_audio_format(self) -> str:
        """返回 wav"""
        return "wav"