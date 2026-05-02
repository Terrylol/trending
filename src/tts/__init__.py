"""TTS 模块"""
from .base import BaseTTS
from .edge_engine import EdgeTTSEngine
from .vectorengine import VectorEngineTTS

def get_tts_engine(engine: str, apikey: str = None):
    """获取 TTS 引擎"""
    if engine == "edge":
        return EdgeTTSEngine()
    elif engine == "vectorengine":
        if not apikey:
            raise ValueError("vectorengine 需要 apikey")
        return VectorEngineTTS(apikey)
    else:
        raise ValueError(f"不支持的 TTS 引擎: {engine}")