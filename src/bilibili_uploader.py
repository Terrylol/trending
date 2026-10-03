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

# B站标题上限 80 字。留 3 字余量，避免边界情况被截断。
TITLE_MAX_LENGTH = 77


class BilibiliUploader:
    def __init__(self, config: Dict):
        # 环境变量优先于配置文件
        self.sessdata = os.environ.get('BILIBILI_SESSDATA') or config.get('sessdata')
        self.bili_jct = os.environ.get('BILIBILI_BILI_JCT') or config.get('bili_jct')
        self.buvid3 = os.environ.get('BILIBILI_BUVID3') or config.get('buvid3')
        # 分区：122 = 科技区 → 知识 → 科学 → 其他
        self.tid = int(config.get('tid', 122))

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

    def _build_title(self, projects: List[Dict]) -> str:
        """生成标题。

        优先级：
        1. Agent 标注的 title_hook（它有判断力，知道哪句最吸引人）
        2. 真实日增最多的项目做钩子（降级数据不参与，那是日均值不是日增）
        3. 兜底文案

        原实现是 `GitHub 今日热榜 Top 5 (20261004)` —— 只有日期没有钩子。
        后来试过「项目名 + 日增数字」，发现"Agent-Reach 一天涨了 1683 星"
        对不认识该项目的人毫无吸引力，而 narrative.hook 是专门写的钩子文案，
        传播力强得多。
        """
        date = datetime.now().strftime('%m月%d日')
        if not projects:
            return f'GitHub 今日热榜 ({date})'

        # ---- 优先：Agent 标注的标题钩子 ----
        best = self._pick_title_hook(projects)
        if best:
            return best[:TITLE_MAX_LENGTH]

        # ---- 次选：真实日增最多的项目 ----
        real_growth = [p for p in projects if not p.get('growth_estimated')]
        if real_growth:
            hottest = max(real_growth,
                          key=lambda p: int(p.get('currentPeriodStars') or 0))
            name = str(hottest.get('name') or '').strip()
            today = int(hottest.get('currentPeriodStars') or 0)
            if name and today > 0:
                return f'GitHub 今日热榜｜{name} 一天涨了 {today:,} 星'

        # ---- 兜底 ----
        return f'GitHub 热门项目 {len(projects)} 个｜{date}'

    def _pick_title_hook(self, projects: List[Dict]) -> str:
        """挑出最适合做标题的 hook。

        两级策略：
        1. Agent 显式标注 title_hook 的项目（`narrative.title_hook: true`）
        2. 否则从所有 hook 里挑最长的（长通常意味着信息更完整）
        """
        # Agent 可能显式指定某个项目的 hook 最适合当标题
        marked = []
        for p in projects:
            narrative = p.get('narrative') or {}
            if narrative.get('title_hook'):
                hook = (narrative.get('hook') or '').strip()
                if hook:
                    marked.append(hook)
        if marked:
            return self._with_brand(marked[0])

        # 未标注时：取最长的 hook（信息量通常更大）
        hooks = [(p.get('narrative') or {}).get('hook', '').strip()
                 for p in projects]
        hooks = [h for h in hooks if h]
        if not hooks:
            return ''
        return self._with_brand(max(hooks, key=len))

    @staticmethod
    def _with_brand(hook: str) -> str:
        """给 hook 加上品牌前缀。

        B站搜索流量依赖关键词，`GitHub` 能带来长尾流量，
        所以即便 hook 本身够吸引人，也保留前缀。
        """
        hook = hook.rstrip('。！？!?…')
        if hook.startswith('GitHub'):
            return hook
        return f'GitHub 今日热榜｜{hook}'
    
    async def upload(self, video_path: str, projects: List[Dict]):
        """上传视频到B站"""
        print(f"  上传视频到B站...")

        # 导入bilibili_api
        try:
            from bilibili_api import video_uploader, Credential
        except ImportError as e:
            raise ImportError(
                '未安装 bilibili-api-python。\n'
                '  安装：venv/bin/pip install bilibili-api-python\n'
                f'  原始错误: {e}'
            ) from e

        # 创建凭证
        credential = Credential(
            sessdata=self.sessdata,
            bili_jct=self.bili_jct,
            buvid3=self.buvid3
        )

        # 标题：用「涨星最多」的项目名做钩子，比纯日期的点击率高
        title = self._build_title(projects)

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
                tid=self.tid,
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
            # start() 的返回值就是投稿信息（含 aid/bvid），
            # 丢掉它就拿不到视频 ID —— 无法确认发了什么，也无法后续管理
            result = await uploader.start()

            bvid = ''
            aid = ''
            if isinstance(result, dict):
                bvid = result.get('bvid', '')
                aid = result.get('aid', '')
            elif hasattr(result, 'bvid'):
                bvid = result.bvid
                aid = getattr(result, 'aid', '')

            print(f"  ✓ 上传成功")
            if bvid:
                print(f"    BV 号: {bvid}")
                print(f"    https://www.bilibili.com/video/{bvid}")

            return {
                'title': title,
                'desc': desc,
                'tags': tags,
                'bvid': bvid,
                'aid': aid,
                'url': f'https://www.bilibili.com/video/{bvid}' if bvid else '',
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