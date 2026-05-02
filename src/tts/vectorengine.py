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
        self.base_url = "https://api.vectorengine.ai/v1beta/models/gemini-3.1-flash-tts-preview:generateContent"
        self.voice = "Fenrir"
        self.max_retries = 3
        self.retry_delay = 5
    
    async def generate_audio(self, text: str, output_file: str) -> str:
        """生成 WAV 音频"""
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
                
                with wave.open(output_file, "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(24000)
                    wav_file.writeframes(audio_data)
                
                return output_file
                
            except requests.exceptions.Timeout:
                if attempt < self.max_retries - 1:
                    print(f"      请求超时，{self.retry_delay}秒后重试 ({attempt + 1}/{self.max_retries})...")
                    time.sleep(self.retry_delay)
                    continue
                raise RuntimeError(f"TTS 生成超时，已重试{self.max_retries}次")
        
        raise RuntimeError("TTS 生成失败")
    
    def get_audio_format(self) -> str:
        """返回 wav"""
        return "wav"