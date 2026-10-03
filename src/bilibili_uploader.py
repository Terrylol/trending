"""
B站视频上传
- Cookie 认证
- 自动填写标题、简介、标签

安全约束：凭据优先从环境变量读取（BILIBILI_SESSDATA / BILIBILI_BILI_JCT /
BILIBILI_BUVID3），配置文件只是 fallback。避免凭据落在被提交的文件里。
"""
import os
from typing import List, Dict
from datetime import datetime


class BilibiliUploader:
    def __init__(self, config: Dict):
        # 环境变量优先于配置文件
        self.sessdata = os.environ.get('BILIBILI_SESSDATA') or config.get('sessdata')
        self.bili_jct = os.environ.get('BILIBILI_BILI_JCT') or config.get('bili_jct')
        self.buvid3 = os.environ.get('BILIBILI_BUVID3') or config.get('buvid3')

        missing = [name for name, value in (
            ('sessdata/BILIBILI_SESSDATA', self.sessdata),
            ('bili_jct/BILIBILI_BILI_JCT', self.bili_jct),
            ('buvid3/BILIBILI_BUVID3', self.buvid3),
        ) if not value]
        if missing:
            raise ValueError(f'B站凭据未配置，缺失: {", ".join(missing)}')

        if str(self.sessdata).startswith('YOUR_'):
            raise ValueError(
                'B站凭据仍是模板占位值。请设置环境变量 '
                'BILIBILI_SESSDATA / BILIBILI_BILI_JCT / BILIBILI_BUVID3'
            )
    
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

        # 封面：B站推荐位依赖封面，缺失会导致没有曝光。
        # 这里显式报错而不是传空字符串 —— 静默传空会让人以为设置成功了。
        import os
        from pathlib import Path
        output_dir = Path('output')
        cover_path = output_dir / 'cover.png'
        if not cover_path.exists():
            raise FileNotFoundError(
                f'封面文件不存在: {cover_path}\n'
                f'  请先完整跑一次 pipeline 生成封面（pipeline.step_render 会自动生成）'
            )
        cover_path = str(cover_path)

        print(f"    标题: {title}")
        print(f"    标签: {','.join(tags)}")
        print(f"    封面: {cover_path}")

        try:
            # 创建元数据
            meta = video_uploader.VideoMeta(
                tid=122,  # 科技区：知识→科学→其他
                title=title[:80],  # B站标题限制80字
                desc=desc[:2000],   # B站简介限制2000字
                cover=cover_path,
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
            url = project.get('url', '')
            
            narrative = project.get('narrative', {})
            description = narrative.get('body') if narrative else None
            if not description:
                description = project.get('description', '')
            
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


async def check_credential(credential_dict: Dict) -> bool:
    """校验 B站 Cookie 是否有效。

    函数名刻意不带 test_ 前缀：pytest 会自动收集 test_ 开头的函数，
    而这里会发出真实网络请求，用 test_ 命名会导致跑测试时误触发。
    """
    try:
        from bilibili_api import user, Credential

        credential = Credential(
            sessdata=credential_dict['sessdata'],
            bili_jct=credential_dict['bili_jct'],
            buvid3=credential_dict['buvid3']
        )

        my_info = await user.get_self_info(credential)

        if my_info:
            print(f"  ✓ B站登录验证成功")
            print(f"    用户名: {my_info.get('name', 'Unknown')}")
            return True

        return False

    except Exception as e:
        print(f"  ✗ B站登录验证失败: {e}")
        return False