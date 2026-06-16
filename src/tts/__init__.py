"""TTS 模块"""
from .base import BaseTTS
from .edge_engine import EdgeTTSEngine
from .vectorengine import VectorEngineTTS
from .volcengine import VolcengineTTS

def get_tts_engine(engine: str, apikey: str = None):
    """获取 TTS 引擎"""
    if engine == "edge":
        return EdgeTTSEngine()
    elif engine == "vectorengine":
        if not apikey:
            raise ValueError("vectorengine 需要 apikey")
        return VectorEngineTTS(apikey)
    elif engine == "volcengine":
        if not apikey:
            raise ValueError("volcengine 需要 apikey（火山方舟 ark- 开头）")
        return VolcengineTTS(apikey)
    else:
        raise ValueError(f"不支持的 TTS 引擎: {engine}")