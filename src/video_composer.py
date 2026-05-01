"""
视频合成
- 音频驱动时长
- MoviePy合成
- 1080p输出
"""
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
from typing import List, Dict
from pathlib import Path

class VideoComposer:
    def __init__(self, config: Dict):
        self.fps = config.get('fps', 24)
        self.resolution = config.get('resolution', '1920x1080')
        
        output_dir = Path(config.get('output_dir', 'output/'))
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
    
    def compose(self, slides: List[str], audio_files: List[str], output_path: str):
        """合成视频"""
        print(f"  合成视频...")
        print(f"    幻灯片: {len(slides)}张")
        print(f"    音频: {len(audio_files)}个")
        
        if len(slides) != len(audio_files):
            print(f"    ✗ 错误: 幻灯片和音频数量不匹配")
            raise ValueError(f"幻灯片数量({len(slides)})与音频数量({len(audio_files)})不匹配")
        
        clips = []
        
        for i, (slide_path, audio_path) in enumerate(zip(slides, audio_files)):
            print(f"    处理片段 [{i + 1}/{len(slides)}]: {slide_path}")
            
            # 加载音频
            try:
                audio = AudioFileClip(audio_path)
            except Exception as e:
                print(f"      ✗ 音频加载失败: {e}")
                continue
            
            # 幻灯片时长 = 音频时长 + 缓冲时间(0.8秒)
            slide_duration = audio.duration + 0.8
            
            print(f"      音频时长: {audio.duration:.2f}s")
            print(f"      幻灯片时长: {slide_duration:.2f}s")
            
            # 创建视频片段
            try:
                video_clip = ImageClip(slide_path, duration=slide_duration)
                
                # 添加音频
                video_clip = video_clip.with_audio(audio)
                
                clips.append(video_clip)
            except Exception as e:
                print(f"      ✗ 片段创建失败: {e}")
                continue
        
        if not clips:
            raise ValueError("没有有效的视频片段")
        
        # 合并所有片段
        print(f"    合并 {len(clips)} 个片段...")
        final_video = concatenate_videoclips(clips)
        
        # 输出视频
        print(f"    渲染视频: {output_path}")
        
        final_video.write_videofile(
            output_path,
            fps=self.fps,
            codec='libx264',
            audio_codec='aac',
            threads=4,
            preset='medium',
            bitrate='5000k'
        )
        
        print(f"  ✓ 视频合成完成: {output_path}")
        print(f"  总时长: {final_video.duration:.2f}秒")
        
        return output_path
    
    def get_video_info(self, video_path: str) -> dict:
        """获取视频信息"""
        from moviepy import VideoFileClip
        
        video = VideoFileClip(video_path)
        
        info = {
            'duration': video.duration,
            'fps': video.fps,
            'size': video.size
        }
        
        video.close()
        
        return info