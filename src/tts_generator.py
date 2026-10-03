"""TTS 语音生成

重构要点：
- 默认 edge-tts（免费、无需 API key）
- 不再用可变实例状态 self.audio_format 传递降级结果——降级信息随返回值走
- voice / speed 真正从 config 读取（此前是死配置）
"""
import asyncio
import json
import random
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tts import get_tts_engine

# 各引擎的默认音色（配置未指定 voice 时使用）
ENGINE_DEFAULTS = {
    'edge': ('zh-CN-XiaoxiaoNeural', 'mp3'),
    'vectorengine': ('Aoede', 'wav'),
    'volcengine': ('', 'mp3'),
}


class TTSGenerator:
    def __init__(self, config: Dict):
        self.engine_name = config.get('engine', 'edge')
        self.apikey = config.get('apikey')
        default_voice, default_format = ENGINE_DEFAULTS.get(
            self.engine_name, ('zh-CN-XiaoxiaoNeural', 'mp3'))
        self.voice = config.get('voice') or default_voice
        self.speed = float(config.get('speed', 1.0))

        self.tts_engine = get_tts_engine(self.engine_name, self.apikey, self.voice, self.speed)
        self.audio_format = self.tts_engine.get_audio_format()

        # 降级引擎：付费引擎失败时自动降级到 edge
        self.fallback_engine = None
        self.fallback_format = 'mp3'
        if self.engine_name in ('vectorengine', 'volcengine'):
            self.fallback_engine = get_tts_engine('edge', voice=self.voice, speed=self.speed)

        self.output_dir = Path(config.get('output_dir', 'output/'))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        print(f'  · TTS 引擎={self.engine_name} 音色={self.voice} 语速={self.speed}')

    async def _generate_one(self, text: str, output_file: str) -> str:
        """生成单条语音。返回实际写出的文件路径（可能是降级后的）。

        重构点：降级后的路径直接作为返回值传出，不再写回 self.audio_format，
        避免实例级共享状态污染后续所有片段的扩展名。
        """
        if not self.fallback_engine:
            return await self.tts_engine.generate_audio(text, output_file)

        try:
            return await self.tts_engine.generate_audio(text, output_file)
        except Exception as e:
            fallback_file = str(Path(output_file).with_suffix(f'.{self.fallback_format}'))
            print(f'      ⚠ {self.engine_name} 失败（{e}），降级到 edge-tts')
            return await self.fallback_engine.generate_audio(text, fallback_file)

    def _load_greetings(self) -> List[str]:
        path = Path('config/greetings.json')
        if path.exists():
            try:
                return json.loads(path.read_text(encoding='utf-8')).get('greetings', [])
            except (OSError, json.JSONDecodeError):
                pass
        return []

    def pick_greeting(self) -> str:
        """随机选一条问候语。片头画面与语音共用同一个结果。"""
        greetings = self._load_greetings()
        return random.choice(greetings) if greetings \
            else '欢迎收看今天的 GitHub Trending 热门项目推荐。'

    def generate_intro_audio(self, greeting: str, output_file: str) -> str:
        """片头语音。greeting 由调用方随机选定并传入，日期不含在语音里。"""
        print(f'  ✓ 片头语音: {output_file}')
        return asyncio.run(self._generate_one(greeting, output_file))

    def generate_project_audio(self, project: Dict, index: int, output_file: str) -> str:
        """项目介绍语音。缺 narrative 时明确报错，而不是静默产出空洞口播。"""
        if not project.get('name'):
            raise ValueError(f'第 {index + 1} 个项目缺少 name 字段，无法生成语音')

        narrative = project.get('narrative') or {}
        if not narrative.get('body'):
            raise ValueError(
                f'项目 {project["name"]} 缺少 narrative.body，无法生成有内容的语音'
            )

        parts = [f"第{index + 1}个项目是{project['name']}。"]
        for key in ('hook', 'body', 'call_to_action'):
            value = narrative.get(key)
            if value:
                parts.append(value)

        actual = asyncio.run(self._generate_one(' '.join(parts), output_file))
        print(f'  ✓ 项目语音 [{index + 1}]: {actual}')
        return actual

    def generate_ending_audio(self, output_file: str) -> str:
        print(f'  ✓ 结尾语音: {output_file}')
        return asyncio.run(self._generate_one('感谢观看，我们明天见。', output_file))

    def generate_all_audio(self, projects: List[Dict], greeting: str) -> List[str]:
        """生成全部音频：片头 + N 个项目 + 片尾。

        注意：即使某个片段降级成不同格式，后续片段也各自用自己的目标扩展名，
        不受前一次降级影响（这正是旧实现的 bug）。
        """
        print(f'  生成语音 (引擎: {self.engine_name})...')

        greeting = greeting or self.pick_greeting()

        intro_ext = self.audio_format
        audio_files = [self.generate_intro_audio(
            greeting, str(self.output_dir / f'audio_intro.{intro_ext}'))]

        for i, project in enumerate(projects):
            audio_files.append(self.generate_project_audio(
                project, i, str(self.output_dir / f'audio_{i}.{self.audio_format}')))

        audio_files.append(self.generate_ending_audio(
            str(self.output_dir / f'audio_ending.{self.audio_format}')))

        print(f'  ✓ 语音生成完成，共 {len(audio_files)} 个文件')
        return audio_files
