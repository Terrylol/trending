"""TTS 模块工厂"""
from .base import BaseTTS
from .edge_engine import EdgeTTSEngine


def get_tts_engine(engine: str, apikey: str = None, voice: str = '', speed: float = 1.0):
    """获取 TTS 引擎实例。

    edge      免费无需 key，默认引擎
    vectorengine / volcengine  需要 API key
    """
    if engine == 'edge':
        return EdgeTTSEngine(voice=voice, speed=speed)

    if engine == 'vectorengine':
        if not apikey:
            raise ValueError('vectorengine 需要 apikey（配置项 tts.apikey）')
        from .vectorengine import VectorEngineTTS
        return VectorEngineTTS(apikey)

    if engine == 'volcengine':
        if not apikey:
            raise ValueError('volcengine 需要 apikey（火山方舟 ark- 开头）')
        from .volcengine import VolcengineTTS
        return VolcengineTTS(apikey)

    raise ValueError(f'不支持的 TTS 引擎: {engine}（可选: edge / vectorengine / volcengine）')
