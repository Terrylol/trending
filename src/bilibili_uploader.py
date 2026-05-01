"""
B站视频上传
- Cookie认证
- 自动填写标题、简介、标签
"""
from typing import List, Dict
from datetime import datetime
import asyncio

class BilibiliUploader:
    def __init__(self, config: Dict):
        self.sessdata = config.get('sessdata')
        self.bili_jct = config.get('bili_jct')
        self.buvid3 = config.get('buvid3')
        
        if not all([self.sessdata, self.bili_jct, self.buvid3]):
            raise ValueError("B站Cookie未完整配置，需要sessdata, bili_jct, buvid3")
        
        if self.sessdata.startswith('YOUR_'):
            raise ValueError("B站Cookie未配置，请在config.json中填写真实值")
    
    async def upload(self, video_path: str, projects: List[Dict]):
        """上传视频到B站"""
        print(f"  上传视频到B站...")
        
        # 导入bilibili_api
        try:
            from bilibili_api import video_uploader, Credential
        except ImportError:
            print(f"  ✗ 未安装bilibili-api-python")
            print(f"    请运行: pip install bilibili-api-python")
            return None
        
        # 创建凭证
        credential = Credential(
            sessdata=self.sessdata,
            bili_jct=self.bili_jct,
            buvid3=self.buvid3
        )
        
        # 生成标题
        date = datetime.now().strftime('%Y%m%d')
        title = f"GitHub 今日热榜 Top {len(projects)} ({date})"
        
        # 生成简介
        desc = self._generate_description(projects)
        
        # 生成标签
        tags = ["GitHub", "开源项目", "编程", "技术分享", "AI"]
        
        # 使用第一张幻灯片作为封面
        import os
        from pathlib import Path
        output_dir = Path('output')
        cover_path = str(output_dir / 'slide_0.png') if (output_dir / 'slide_0.png').exists() else None
        
        print(f"    标题: {title}")
        print(f"    标签: {','.join(tags)}")
        
        try:
            # 创建元数据
            meta = video_uploader.VideoMeta(
                tid=122,  # 科技区：知识→科学→其他
                title=title[:80],  # B站标题限制80字
                desc=desc[:2000],   # B站简介限制2000字
                cover=cover_path or '',  # 使用幻灯片作为封面
                tags=tags
            )
            
            # 创建上传器
            uploader = video_uploader.VideoUploader(
                pages=[video_uploader.VideoUploaderPage(path=video_path, title=title[:80])],
                meta=meta,
                credential=credential
            )
            
            # 上传
            print(f"    上传中...")
            await uploader.start()
            
            print(f"  ✓ 上传成功")
            
            return {
                'title': title,
                'desc': desc,
                'tags': tags
            }
            
        except Exception as e:
            print(f"  ✗ 上传失败: {e}")
            raise
    
    def _generate_description(self, projects: List[Dict]) -> str:
        """生成视频简介"""
        date = datetime.now().strftime('%Y年%m月%d日')
        
        desc = f"📅 {date} GitHub Trending 热门项目推荐\n\n"
        desc += "🔥 本期精选项目：\n\n"
        
        for i, project in enumerate(projects, 1):
            name = project.get('name', 'Unknown')
            description = project.get('description', '')
            url = project.get('url', '')
            
            desc += f"{i}. {name}\n"
            desc += f"   {description}\n"
            if url:
                desc += f"   {url}\n"
            desc += "\n"
        
        desc += "\n"
        desc += "📌 关于本视频：\n"
        desc += "- 每日自动更新\n"
        desc += "- 欢迎关注获取最新技术动态\n\n"
        
        desc += "#GitHub #开源 #编程 #技术 #AI"
        
        return desc


async def test_credential(credential_dict: Dict) -> bool:
    """测试B站Cookie是否有效"""
    try:
        from bilibili_api import user, Credential
        
        credential = Credential(
            sessdata=credential_dict['sessdata'],
            bili_jct=credential_dict['bili_jct'],
            buvid3=credential_dict['buvid3']
        )
        
        # 尝试获取用户信息
        my_info = await user.get_self_info(credential)
        
        if my_info:
            print(f"  ✓ B站登录验证成功")
            print(f"    用户名: {my_info.get('name', 'Unknown')}")
            return True
        
        return False
        
    except Exception as e:
        print(f"  ✗ B站登录验证失败: {e}")
        return False