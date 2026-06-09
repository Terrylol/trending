"""Remotion 视频合成器
- 读取幻灯片/音频列表
- 复制静态资源到 remotion/public/generated
- 生成 output/remotion_input.json
- 调用 Remotion 分段渲染 mp4 segment
- 用 ffmpeg concat copy 合并为最终视频
"""
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from card_generator import CardGenerator


class RemotionComposer:
    def __init__(self, config: Dict):
        self.fps = int(config.get('fps', 24))
        self.output_dir = Path(config.get('output_dir', 'output/'))
        self.output_dir.mkdir(exist_ok=True)
        self.root_dir = Path.cwd()
        self.remotion_dir = self.root_dir / 'remotion'
        self.public_dir = self.remotion_dir / 'public' / 'generated'
        self.public_dir.mkdir(parents=True, exist_ok=True)
        self.star_history_dir = self.output_dir / 'star_history'
        self.star_history_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir = self.output_dir / 'logs'
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = datetime.now().strftime('%Y%m%d_%H%M%S') + f'_{os.getpid()}'
        # 分辨率：从 config 读取，格式 "WIDTHxHEIGHT"，默认 1280x720
        resolution = config.get('resolution', '1280x720')
        try:
            self.width, self.height = [int(x) for x in resolution.split('x')]
        except (ValueError, AttributeError):
            print(f'    ⚠ 无效分辨率 "{resolution}"，降级为 1280x720')
            self.width, self.height = 1280, 720

        self.card_generator = CardGenerator({'resolution': f'{self.width}x{self.height}', 'fps': self.fps})

    def compose(self, projects: List[Dict], audio_files: List[str], output_path: str) -> str:
        print('  Remotion 生成场景画面 + ffmpeg 合成视频...')
        print(f'    项目: {len(projects)}个')
        print(f'    音频: {len(audio_files)}个')
        if len(audio_files) != len(projects) + 2:
            raise ValueError(f'音频数量({len(audio_files)})应为项目数+2({len(projects)+2})')
        self._ensure_dependencies()
        self._clean_generated()
        self._copy_github_logo()

        date = datetime.now().strftime('%Y.%m.%d')
        scenes = []
        scenes.append(self._make_scene('title', audio_files[0], None, None))
        for i, project in enumerate(projects):
            public_project = self._prepare_project_assets(project)
            scenes.append(self._make_scene('project', audio_files[i + 1], public_project, i))
        scenes.append(self._make_scene('ending', audio_files[-1], None, None))

        payload = {'date': date, 'fps': self.fps, 'scenes': scenes}
        input_path = self.output_dir / 'remotion_input.json'
        input_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'    ✓ Remotion 输入: {input_path}')

        segment_dir = self.output_dir / 'remotion_segments'
        self._archive_existing_segment_dir(segment_dir)
        segment_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            'node', 'render_segments.mjs',
            '--input', str((self.root_dir / input_path).resolve()),
            '--out-dir', str((self.root_dir / segment_dir).resolve()),
            '--width', str(self.width),
            '--height', str(self.height),
            '--concurrency', '1',
            '--crf', '18',
            '--x264-preset', 'medium',
            '--segment-retries', '3',
            '--clean-out-dir',
        ]
        print('    Remotion 分段渲染动态视频...')
        remotion_log = self.logs_dir / f'remotion_render_{self.run_id}.log'
        print(f'    Remotion 日志: {remotion_log}')
        with open(remotion_log, 'w', encoding='utf-8') as log:
            log.write('$ ' + ' '.join(cmd) + '\n')
            log.flush()
            result = subprocess.run(cmd, cwd=self.remotion_dir, stdout=log, stderr=subprocess.STDOUT, text=True)
        if result.returncode != 0:
            tail = self._tail_file(remotion_log)
            raise RuntimeError(f'Remotion 分段渲染失败: exit {result.returncode}\n日志: {remotion_log}\n--- log tail ---\n{tail}')

        self._ffmpeg_concat(segment_dir, scenes, output_path)
        self._validate_video(output_path)
        print(f'  ✓ 视频合成完成: {output_path}')
        return output_path

    def _ffmpeg_concat(self, segment_dir: Path, scenes: List[Dict], output_path: str):
        segments = []
        for i in range(len(scenes)):
            segment = segment_dir / f'segment_{i:02d}.mp4'
            if not segment.exists():
                raise FileNotFoundError(f'Remotion segment 不存在: {segment}')
            segments.append(segment)
        list_file = segment_dir / 'concat.txt'
        list_file.write_text(''.join(f"file '{p.resolve()}'\n" for p in segments), encoding='utf-8')
        cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(list_file), '-c', 'copy', output_path]
        print('    ffmpeg concat 合并视频片段（不二压）...')
        concat_log = self.logs_dir / f'ffmpeg_concat_{self.run_id}.log'
        print(f'    ffmpeg 日志: {concat_log}')
        with open(concat_log, 'w', encoding='utf-8') as log:
            log.write('$ ' + ' '.join(cmd) + '\n')
            log.flush()
            result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, text=True)
        if result.returncode != 0:
            tail = self._tail_file(concat_log)
            raise RuntimeError(f'视频合并失败: exit {result.returncode}\n日志: {concat_log}\n--- log tail ---\n{tail}')

    def _archive_existing_segment_dir(self, segment_dir: Path):
        if not segment_dir.exists():
            return
        archive_root = self.output_dir / 'remotion_segments_archive'
        archive_root.mkdir(parents=True, exist_ok=True)
        archived = archive_root / f'{segment_dir.name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{os.getpid()}'
        counter = 1
        while archived.exists():
            archived = archive_root / f'{segment_dir.name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{os.getpid()}_{counter}'
            counter += 1
        shutil.move(str(segment_dir), str(archived))
        print(f'    已归档旧 Remotion segments: {archived}')

    def _tail_file(self, path: Path, max_chars: int = 4000) -> str:
        try:
            text = path.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            return f'<读取日志失败: {e}>'
        return text[-max_chars:]

    def _make_scene(self, scene_type: str, audio_file: str, project, index):
        duration = self._audio_duration(audio_file) + 0.8
        frames = max(1, round(duration * self.fps))
        scene = {
            'type': scene_type,
            'durationSeconds': duration,
            'durationFrames': frames,
            'audio': self._copy_public_asset(audio_file),
        }
        if project is not None:
            scene['project'] = project
        if index is not None:
            scene['index'] = index
        print(f"    片段 {scene_type}: {duration:.2f}s / {frames} frames")
        return scene

    def _audio_duration(self, path: str) -> float:
        result = subprocess.run([
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', path
        ], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f'读取音频时长失败: {path}\n{result.stderr}')
        return float(result.stdout.strip())

    def _copy_public_asset(self, src: str, subdir: str = '') -> str:
        src_path = Path(src)
        if not src_path.is_absolute():
            src_path = self.root_dir / src_path
        if not src_path.exists():
            raise FileNotFoundError(str(src_path))
        safe_name = ''.join(c if c.isalnum() or c in '._-' else '_' for c in src_path.name)
        dest_dir = self.public_dir / subdir if subdir else self.public_dir
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / safe_name
        counter = 1
        while dest.exists() and src_path.resolve() != dest.resolve():
            dest = dest_dir / f'{src_path.stem}_{counter}{src_path.suffix}'
            counter += 1
        shutil.copy2(src_path, dest)
        public_path = Path('generated') / subdir / dest.name if subdir else Path('generated') / dest.name
        return public_path.as_posix()

    def _copy_github_logo(self) -> str:
        logo = self.root_dir / 'assets' / 'github_logo.png'
        if not logo.exists():
            raise FileNotFoundError(f'GitHub logo 不存在: {logo}')
        return self._copy_public_asset(str(logo))

    def _prepare_project_assets(self, project: Dict) -> Dict:
        public_project = dict(project)
        preview = project.get('preview_image')
        if preview:
            public_project['public_preview_image'] = self._copy_public_asset(preview)

        star_history = self._get_star_history_image(project)
        if star_history:
            public_project['star_history_image'] = self._copy_public_asset(star_history, 'star_history')
        return public_project

    def _parse_github_repo(self, url: str) -> Optional[Tuple[str, str]]:
        if not url:
            return None
        parts = url.rstrip('/').split('/')
        if len(parts) >= 5 and parts[2] == 'github.com' and parts[3] and parts[4]:
            return parts[3], parts[4]
        return None

    def _get_star_history_image(self, project: Dict) -> Optional[str]:
        parsed = self._parse_github_repo(project.get('url', ''))
        if not parsed:
            return None
        owner, repo = parsed
        cache_file = self.star_history_dir / f'{owner}_{repo}.png'
        if cache_file.exists():
            return str(cache_file)

        # 复用旧 PIL/card_generator 的 Star History 获取与 SVG->PNG 转换逻辑，避免 Remotion 流程重复造轮子。
        try:
            return self.card_generator._fetch_star_history_image(owner, repo)
        except Exception as e:
            print(f'      Star 历史图获取失败: {owner}/{repo}: {e}')
            return None

    def _clean_generated(self):
        if self.public_dir.exists():
            shutil.rmtree(self.public_dir)
        self.public_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_dependencies(self):
        required = [
            self.remotion_dir / 'node_modules' / '@remotion' / 'renderer',
            self.remotion_dir / 'node_modules' / '@remotion' / 'bundler',
            self.remotion_dir / 'node_modules' / 'remotion',
            self.remotion_dir / 'node_modules' / 'typescript',
        ]
        if not all(path.exists() for path in required):
            print('    安装 Remotion npm 依赖...')
            result = subprocess.run(['npm', 'install'], cwd=self.remotion_dir, text=True)
            if result.returncode != 0:
                raise RuntimeError(f'npm install 失败: exit {result.returncode}')

    def _validate_video(self, video_path: str):
        result = subprocess.run([
            'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', video_path
        ], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f'ffprobe 验证失败: {video_path}')
        info = json.loads(result.stdout)
        streams = info.get('streams', [])
        has_video = any(s.get('codec_type') == 'video' for s in streams)
        has_audio = any(s.get('codec_type') == 'audio' for s in streams)
        if not has_video or not has_audio:
            raise RuntimeError(f'视频缺少流: video={has_video}, audio={has_audio}')
