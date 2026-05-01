#!/usr/bin/env python3
"""测试B站视频上传"""
import asyncio
import sys
sys.path.insert(0, 'src')

from bilibili_uploader import BilibiliUploader

async def test_upload():
    # Cookie配置
    config = {
        'sessdata': '***REMOVED***',
        'bili_jct': '***REMOVED***',
        'buvid3': '***REMOVED***'
    }
    
    # 模拟项目数据（用于生成标题和简介）
    projects = [
        {
            'name': 'DeepSeek-R1',
            'url': 'https://github.com/deepseek-ai/DeepSeek-R1',
            'description': '开源推理模型',
            'stars': 45000
        }
    ]
    
    # 视频路径
    video_path = 'output/trending_video.mp4'
    
    print("=" * 60)
    print("测试B站视频上传")
    print("=" * 60)
    
    try:
        uploader = BilibiliUploader(config)
        result = await uploader.upload(video_path, projects)
        
        if result:
            print("\n" + "=" * 60)
            print("✓ 上传测试成功")
            print("=" * 60)
            print(f"标题: {result['title']}")
            print(f"标签: {','.join(result['tags'])}")
        else:
            print("\n上传返回None")
            
    except Exception as e:
        print(f"\n✗ 上传失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_upload())
