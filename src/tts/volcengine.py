"""火山方舟 Volcengine Seed-TTS 引擎实现

对应火山方舟 Agent Plan / Coding Plan 的 TTS v3 plan 接口。
Endpoint: https://openspeech.bytedance.com/api/v3/plan/tts/unidirectional
Resource ID: seed-tts-2.0（必须与 speaker 匹配）
Speaker: zh_female_tianmeixiaoyuan_uranus_bigtts（Doubao uranus 系列，跟 seed-tts-2.0 匹配）

协议要点（与 OpenClaw 内部 volcengineTTS 一致）：
- 请求 header：X-Api-Key / X-Api-Resource-Id / X-Api-App-Key
- 请求体：{user: {uid}, req_params: {text, speaker, audio_params: {format, sample_rate}, speed_ratio}}
- 响应是 SSE-style 多帧：每行一个 JSON {code, data, message}，code=0 的 data 是 base64 编码的音频片段
- 需把所有 code=0 帧的 data 拼起来 base64 解码
"""
import json
import time
import base64
import requests
from typing import Dict
from .base import BaseTTS


class VolcengineTTS(BaseTTS):
    """火山方舟 Seed-TTS 引擎"""

    # 国内 endpoint（OpenClaw 默认是 byteplus 东南亚，这个是火山方舟国内版本）
    ENDPOINT = "https://openspeech.bytedance.com/api/v3/plan/tts/unidirectional"
    RESOURCE_ID = "seed-tts-2.0"
    VOICE = "zh_female_tianmeixiaoyuan_uranus_bigtts"
    APP_KEY = "aGjiRDfUWi"  # OpenClaw 内部 volcengine TTS 默认占位
    SAMPLE_RATE = 24000
    SPEED_RATIO = 1.0  # 火山方舟端直接接受 speed_ratio 参数，无需 ffmpeg 后处理

    def __init__(self, apikey: str):
        if not apikey:
            raise ValueError("volcengine 需要 apikey（火山方舟 ark- 开头）")
        self.apikey = apikey
        self.max_retries = 3
        self.retry_delay = 5
        self.timeout = 30  # 单次请求超时（实测单段通常 < 3 秒）

    def _build_request_body(self, text: str) -> Dict:
        """构造 TTS 请求体"""
        return {
            "user": {"uid": "github-trending-video"},
            "req_params": {
                "text": text,
                "speaker": self.VOICE,
                "audio_params": {
                    "format": "mp3",
                    "sample_rate": self.SAMPLE_RATE,
                },
                "speed_ratio": self.SPEED_RATIO,
            },
        }

    def _parse_sse_response(self, response_text: str) -> bytes:
        """解析火山方舟 TTS 的 SSE 帧响应，合并所有 code=0 帧的 base64 音频

        响应格式：每行一个 JSON 对象，{code, data, message}。
        - code=0 且 data 非空：data 是 base64 编码的音频片段
        - code=2_000_000：结束帧，跳过
        - 其他 code：抛错
        """
        chunks = []
        for line in response_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                frame = json.loads(line)
            except json.JSONDecodeError:
                continue

            code = frame.get("code")
            if code == 0:
                data = frame.get("data")
                if data:
                    chunks.append(base64.b64decode(data))
            elif code == 20000000:
                # 结束帧（"OK"）
                continue
            else:
                msg = frame.get("message", "unknown error")
                raise RuntimeError(f"火山方舟 TTS 错误 code={code}: {msg}")

        if not chunks:
            raise RuntimeError("火山方舟 TTS 响应中没有音频数据")

        return b"".join(chunks)

    async def generate_audio(self, text: str, output_file: str) -> str:
        """生成 MP3 音频

        Args:
            text: 要转换的文本
            output_file: 输出 .mp3 文件路径

        Returns:
            写入的文件路径
        """
        body = self._build_request_body(text)
        headers = {
            "Content-Type": "application/json",
            "Connection": "keep-alive",
            "X-Api-Key": self.apikey,
            "X-Api-Resource-Id": self.RESOURCE_ID,
            "X-Api-App-Key": self.APP_KEY,
        }

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.ENDPOINT,
                    headers=headers,
                    data=json.dumps(body),
                    timeout=self.timeout,
                )

                if response.status_code != 200:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    # 401/403 是鉴权错，重试无意义直接抛
                    if response.status_code in (401, 403):
                        raise RuntimeError(f"火山方舟 TTS 鉴权失败: {last_error}")
                    raise RuntimeError(f"火山方舟 TTS HTTP 错误: {last_error}")

                audio_bytes = self._parse_sse_response(response.text)

                with open(output_file, "wb") as f:
                    f.write(audio_bytes)

                return output_file

            except requests.exceptions.Timeout:
                last_error = f"请求超时（{self.timeout}s）"
            except requests.exceptions.RequestException as e:
                last_error = f"网络错误: {e}"
            except RuntimeError:
                # 业务错误（鉴权/SSE 解析/code 非 0）直接抛，不重试
                raise

            # 可重试错误（超时/网络）走重试
            if attempt < self.max_retries - 1:
                print(
                    f"      ⚠ 火山方舟 TTS {last_error}，"
                    f"{self.retry_delay}秒后重试 ({attempt + 1}/{self.max_retries})..."
                )
                time.sleep(self.retry_delay)

        raise RuntimeError(
            f"火山方舟 TTS 生成失败，已重试 {self.max_retries} 次: {last_error}"
        )

    def get_audio_format(self) -> str:
        """返回 mp3（火山方舟直接输出 mp3 bytes）"""
        return "mp3"
