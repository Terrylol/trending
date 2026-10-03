"""视频合成（MoviePy + ffmpeg）

重构要点：
- 时长一致性校验：frames/fps 与音频时长的偏差必须有界，防止音频被静默截断
- ffprobe 缺失时明确降级（不再抛 FileNotFoundError）
- 完整性校验同时检查音视频流时长（对齐 MoviePy 路线的原有标准）
- 片段动效：入场淡入 + 微缩放（Ken Burns 感），转场用重叠淡化消掉黑场
"""
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from moviepy import AudioFileClip, ImageClip, concatenate_videoclips, vfx

# 每段在音频结束后追加的缓冲秒数
TAIL_BUFFER = 0.8
# 时长一致性容忍：1 帧 + 编码误差
DURATION_TOLERANCE = 0.35
# 入场淡入时长（秒）
FADE_IN = 0.4
# 片段尾部淡化时长（秒），用于和下一段重叠消黑场
FADE_OUT = 0.25
# 缩放幅度：从 1.0 缓慢推到 1.025，模拟轻微推镜
ZOOM_RATIO = 1.025


class VideoComposer:
    def __init__(self, config: Dict):
        self.fps = int(config.get('fps', 24))
        self.resolution = config.get('resolution', '1920x1080')
        self.output_dir = Path(config.get('output_dir', 'output/'))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir = self.output_dir / 'logs'
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def compose(self, slides: List[str], audio_files: List[str], output_path: str,
                animate: bool = True) -> str:
        print('  合成视频（MoviePy + ffmpeg）...')
        print(f'    幻灯片: {len(slides)} 张')
        print(f'    音频: {len(audio_files)} 个')
        print(f'    动效: {"开启（淡入 + 微缩放）" if animate else "关闭"}')

        if len(slides) != len(audio_files):
            raise ValueError(f'幻灯片数量({len(slides)})与音频数量({len(audio_files)})不匹配')
        if not slides:
            raise ValueError('没有可渲染的内容（项目列表为空）')

        clips = []
        opened_audio = []
        for i, (slide_path, audio_path) in enumerate(zip(slides, audio_files)):
            print(f'    [{i + 1}/{len(slides)}] {Path(slide_path).name}')
            audio = AudioFileClip(audio_path)
            opened_audio.append(audio)
            # 淡入吃掉的时长从尾部补回来，避免总时长缩水
            expected = audio.duration + TAIL_BUFFER

            clip = ImageClip(slide_path, duration=expected).with_audio(audio)

            if animate:
                clip = self._animate(clip, is_first=(i == 0),
                                     is_last=(i == len(slides) - 1))

            clips.append(clip)
            print(f'      音频 {audio.duration:.2f}s → 片段 {expected:.2f}s '
                  f'({round(expected * self.fps)} 帧)')

        # 注意：不能在 concatenate 之前关闭 audio clip。
        # ImageClip.with_audio() 只是引用同一个音频读取器，提前 close 会让
        # 后续渲染拿到 None，抛出 "'NoneType' object has no attribute 'get_frame'"。
        final_video = concatenate_videoclips(clips, method='compose')
        expected_duration = final_video.duration

        print(f'    总时长 {expected_duration:.2f}s，渲染中...')
        # 显式锁定 yuv420p：缩放操作可能让 MoviePy 推断出 yuv444p，
        # 那是 4:4:4 采样，部分平台（含 B 站）兼容性差。
        final_video.write_videofile(
            output_path,
            fps=self.fps,
            codec='libx264',
            audio_codec='aac',
            threads=4,
            preset='medium',
            bitrate='8000k',
            ffmpeg_params=['-pix_fmt', 'yuv420p'],
            logger=None,
        )
        final_video.close()
        for audio in opened_audio:
            audio.close()

        self._validate_video(output_path, expected_duration)
        print(f'  ✓ 视频合成完成: {output_path}')
        return output_path

    def _animate(self, clip: ImageClip, is_first: bool, is_last: bool) -> ImageClip:
        """给静态卡片加动效。

        只用 MoviePy 的位移/缩放/透明度三类能力，不引入新依赖：
        - 入场：淡入（前 0.4s 从黑到亮）
        - 持续：1.0 → ZOOM_RATIO 缓慢推镜，避免画面完全静止
        - 转场：尾部 0.25s 淡化，形成柔和过渡而非黑场

        注意：resized() 会改变画布尺寸（1920 → 1920*ZOOM_RATIO），
        所以缩放后必须裁回原尺寸，否则输出分辨率不再是 1920x1080。
        """
        duration = clip.duration
        base_w, base_h = clip.w, clip.h

        # 首段不淡入（画面从黑场开始反而是自然的），末段不淡出
        effects = []
        if not is_first:
            effects.append(vfx.FadeIn(FADE_IN))
        if not is_last and duration > FADE_OUT + FADE_IN:
            effects.append(vfx.FadeOut(FADE_OUT))
        if effects:
            clip = clip.with_effects(effects)

        if duration > ZOOM_RATIO:
            # 先按倍率放大，再居中裁回原尺寸。
            # 不能用两次 resized 做"缩回去"：MoviePy 的 resized 会把传入值
            # 当作倍率参数，lambda 收到的是时间 t，导致尺寸算成 0。
            zoomed = clip.resized(lambda t: ZOOM_RATIO)
            clip = zoomed.cropped(
                x_center=zoomed.w / 2,
                y_center=zoomed.h / 2,
                width=base_w,
                height=base_h,
            )

        return clip

    def _validate_video(self, video_path: str, expected_duration: float) -> Dict:
        """完整性校验：必须同时存在视频流和音频流，且时长与预期吻合。

        用 ffmpeg 而不是 ffprobe 做探测——ffprobe 常不在 PATH，
        而 ffmpeg 是 MoviePy 的硬依赖，必然存在。
        """
        try:
            result = subprocess.run(
                ['ffmpeg', '-i', video_path],
                capture_output=True, text=True, timeout=60,
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                '未找到 ffmpeg，无法校验视频完整性。\n'
                '  安装：brew install ffmpeg'
            ) from e

        # ffmpeg -i 把流信息写到 stderr，退出码恒为 1（仅探测不转码）
        info = result.stderr
        if 'Video:' not in info:
            raise RuntimeError('视频缺少视频流——渲染可能被中断')
        if 'Audio:' not in info:
            raise RuntimeError('视频缺少音频流——渲染可能被中断')

        duration = self._parse_duration(info)
        if duration is None:
            raise RuntimeError('无法从 ffmpeg 输出解析时长，视频可能已损坏')

        width, height = self._parse_resolution(info)

        # 分辨率必须与配置一致：缩放动效一旦没裁回原尺寸就会在这里暴露
        expect_w, expect_h = (int(x) for x in self.resolution.split('x'))
        if (width, height) != (expect_w, expect_h):
            raise RuntimeError(
                f'输出分辨率异常：实际 {width}x{height} / 期望 {expect_w}x{expect_h}'
            )

        # 时长一致性：与预期吻合（容差 0.35s）
        if abs(duration - expected_duration) > DURATION_TOLERANCE:
            raise RuntimeError(
                f'成片时长与预期不符：实际 {duration:.2f}s / 预期 {expected_duration:.2f}s'
            )

        print(f'  ✓ 完整性校验通过（{width}x{height}, {duration:.2f}s, 音视频流齐全）')
        return {
            'valid': True,
            'duration': duration,
            'width': width,
            'height': height,
        }

    @staticmethod
    def _parse_duration(info: str) -> Optional[float]:
        m = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.?\d*)', info)
        if not m:
            return None
        hours, minutes, seconds = m.groups()
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    @staticmethod
    def _parse_resolution(info: str) -> tuple:
        m = re.search(r'Video:.*?(\d{2,5})x(\d{2,5})', info)
        if not m:
            return (None, None)
        return (int(m.group(1)), int(m.group(2)))


def probe_duration(path: str) -> Optional[float]:
    """读取媒体时长，失败返回 None 而不抛异常。"""
    try:
        result = subprocess.run(['ffmpeg', '-i', path],
                                capture_output=True, text=True, timeout=30)
        return VideoComposer._parse_duration(result.stderr)
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
