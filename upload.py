#!/usr/bin/env python3
"""上传视频到B站"""
import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, 'src')

from bilibili_uploader import BilibiliUploader

async def main():
    # 读取配置
    config_path = Path('config/config.json')
    if not config_path.exists():
        print("错误: config/config.json 不存在")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    bilibili_config = config.get('bilibili', {})
    
    # 读取项目数据
    projects_path = Path('output/projects_summary.json')
    if not projects_path.exists():
        print("错误: output/projects_summary.json 不存在")
        sys.exit(1)
    
    with open(projects_path, 'r') as f:
        projects_data = json.load(f)
    
    projects = projects_data.get('projects', [])
    
    # 视频路径
    video_path = 'output/trending_video.mp4'
    
    print("=" * 60)
    print("上传视频到B站")
    print("=" * 60)
    
    try:
        uploader = BilibiliUploader(bilibili_config)
        result = await uploader.upload(video_path, projects)
        
        if result:
            print("\n" + "=" * 60)
            print("✓ 上传成功")
            print("=" * 60)
            print(f"标题: {result['title']}")
            print(f"标签: {','.join(result['tags'])}")
        else:
            print("\n上传返回None")
            
    except Exception as e:
        print(f"\n✗ 上传失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
