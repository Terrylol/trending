"""GitHub Trending 采集
架构：三层降级
  第一层  爬 Trending HTML（唯一能拿到官方策展结果和日增 star 的源）
  第二层  search API 按 star 增速近似（解析断言失败时降级）
  第三层  本地缓存（网络也挂时兜底）

关键约束：绝不允许返回空列表或全 0 数据。任何一层失败都必须显式降级。
"""
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from PIL import Image

# 采集健康度断言：低于这些值说明解析器漂了，绝不放行
MIN_PROJECTS = 5
MIN_TOTAL_PERIOD_STARS = 1


class FetchError(Exception):
    """采集失败（已尝试所有降级路径）"""


class TrendingFetcher:
    def __init__(self, config: Optional[Dict] = None):
        config = config or {}
        self.trending_url = 'https://github.com/trending'
        self.preview_url = 'https://opengraph.githubassets.com/1'
        self.github_token = config.get('personal_access_token') or os.environ.get('GITHUB_TOKEN', '')
        self.max_retries = int(config.get('max_retries', 3))
        self.timeout = int(config.get('timeout', 20))

        self.root = Path(config.get('project_root', Path.cwd()))
        self.screenshots_dir = self.root / 'screenshots'
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = self.root / 'output' / 'cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 复用连接，避免每次请求重建 TCP+TLS
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept-Language': 'en',
        })
        if self.github_token:
            # 注意：GitHub API 用 Bearer，不是早期的 token 前缀
            self.session.headers['Authorization'] = f'Bearer {self.github_token}'

    # ---------- 对外入口 ----------

    def fetch(self, limit: int = 15, since: str = 'daily') -> List[Dict]:
        """采集热门项目，三层降级。全失败抛 FetchError。"""
        errors = []

        # 第一层：Trending HTML
        try:
            projects = self._fetch_trending_html(limit=limit, since=since)
            self._assert_healthy(projects)
            source = 'github_trending'
            print(f'  ✓ 第一层成功：Trending HTML，{len(projects)} 个项目')
        except Exception as e:
            errors.append(f'第一层(Trending HTML): {e}')
            print(f'  ⚠ 第一层失败：{e}')

            # 第二层：search API
            try:
                projects = self._fetch_via_search_api(limit=limit)
                self._assert_healthy(projects)
                source = 'search_api'
                print(f'  ✓ 第二层成功：search API 增速榜，{len(projects)} 个项目')
            except Exception as e2:
                errors.append(f'第二层(search API): {e2}')
                print(f'  ⚠ 第二层失败：{e2}')

                # 第三层：本地缓存
                projects = self._load_cache()
                if not projects:
                    errors.append('第三层(本地缓存): 无可用缓存')
                    raise FetchError('三层采集全部失败:\n  - ' + '\n  - '.join(errors))
                source = 'cache'
                print(f'  ✓ 第三层成功：本地缓存，{len(projects)} 个项目（数据可能不是最新的）')

        for p in projects:
            p['data_source'] = source

        self._save_cache(projects)
        self._enrich_metadata(projects)
        return projects

    # ---------- 健康度断言（核心防线）----------

    def _assert_healthy(self, projects: List[Dict]):
        """采集结果必须非空且含日增 star，否则判定解析器失效。"""
        if not projects:
            raise ValueError('采集结果为空列表——选择器很可能已失效')

        if len(projects) < MIN_PROJECTS:
            raise ValueError(f'采集数量 {len(projects)} < 最低要求 {MIN_PROJECTS}')

        total = sum(int(p.get('currentPeriodStars') or 0) for p in projects)
        if total < MIN_TOTAL_PERIOD_STARS:
            raise ValueError(
                f'全部项目的日增 star 总和为 {total}，疑似 stars today 解析失效'
            )

        # 数据健全性检查：全零 stars 说明数字解析也漂了
        total_stars = sum(int(p.get('stars') or 0) for p in projects)
        if total_stars == 0:
            raise ValueError('全部项目的 star 总数为 0，疑似星标解析失效')

    # ---------- 第一层：Trending HTML ----------

    def _fetch_trending_html(self, limit: int, since: str) -> List[Dict]:
        response = self._get(f'{self.trending_url}?since={since}', context='Trending 页面')
        soup = BeautifulSoup(response.text, 'html.parser')
        articles = soup.find_all('article', class_='Box-row')[:limit]

        projects = []
        for article in articles:
            project = self._parse_article(article)
            if project:
                projects.append(project)
        return projects

    def _parse_article(self, article) -> Optional[Dict]:
        """解析单个 Trending 卡片。

        选择器失效历史（2026-10 实测）：
          - fork 链接 GitHub 已从 /network/members 改为 /forks
          - "N stars today" 被包在 <svg> 兄弟节点里，find(string=) 必然返回 None
        因此这里一律走 href 后缀匹配和整块文本正则，不依赖易碎的结构。
        """
        try:
            h2 = article.find('h2')
            a_tag = h2.find('a') if h2 else None
            if not a_tag or not a_tag.get('href'):
                return None

            parts = a_tag['href'].strip('/').split('/')
            if len(parts) < 2:
                return None
            owner, repo = parts[0], parts[1]

            # 描述：class 已从 col-9 变为 "col-9 color-fg-muted ..."，按 class token 匹配更稳
            desc_tag = article.find('p', class_='col-9')
            description = desc_tag.get_text(strip=True) if desc_tag else ''

            lang_span = article.find('span', attrs={'itemprop': 'programmingLanguage'})
            language = lang_span.get_text(strip=True) if lang_span else ''

            # 语言色块：style 可能没有冒号（旧代码这里会 IndexError 然后静默丢整个项目）
            language_color = '#cccccc'
            color_span = article.find('span', class_='repo-language-color')
            if color_span:
                m = re.search(r'(?:background-color\s*:\s*|:\s*)(#[0-9a-fA-F]{3,6})',
                              color_span.get('style', ''))
                if m:
                    language_color = m.group(1)

            # star 数：href 仍是 /stargazers
            stars = self._parse_count(article, r'/stargazers')

            # fork 数：GitHub 已从 /network/members 改为 /forks，两种都兼容
            forks = self._parse_count(article, r'/(?:network/members|forks)$')

            # 日增 star：不能依赖 find(string=)，必须走整块文本
            text = article.get_text(' ', strip=True)
            m = re.search(r'([\d,]+)\s+stars?\s+today', text)
            stars_today = self._to_int(m.group(1)) if m else 0

            return {
                'author': owner,
                'name': repo,
                'full_name': f'{owner}/{repo}',
                'avatar': f'https://github.com/{owner}.png',
                'url': f'https://github.com/{owner}/{repo}',
                'description': description,
                'language': language,
                'languageColor': language_color,
                'stars': stars,
                'forks': forks,
                'currentPeriodStars': stars_today,
                'readme': '',
            }
        except Exception as e:
            print(f'      ⚠ 卡片解析失败（已跳过）: {e}')
            return None

    def _parse_count(self, article, href_pattern: str) -> int:
        """从匹配 href 的链接里取数字，容忍 12k / 1.2m 这类缩写格式。"""
        a_tag = article.find('a', href=re.compile(href_pattern))
        if not a_tag:
            return 0
        text = a_tag.get_text(strip=True).replace(',', '')
        # 必须先匹配完整的 数字+单位，k/m 不能再被小数点拆开
        m = re.search(r'([\d.]+)\s*([km])?', text, re.I)
        if not m:
            return 0
        raw, unit = m.group(1), (m.group(2) or '').lower()
        try:
            value = float(raw)
        except ValueError:
            return 0
        multiplier = {'k': 1000, 'm': 1_000_000}.get(unit, 1)
        return int(value * multiplier)

    @staticmethod
    def _to_int(text: str) -> int:
        return int(text.replace(',', ''))

    # ---------- 第二层：search API ----------

    def _fetch_via_search_api(self, limit: int) -> List[Dict]:
        """降级路径：用 search API 近似"近期热门"。

        已知局限（实测 Top10 与官方日榜零重叠）：
          - GitHub search 索引里没有 star 时间序列，只能用总星数排序
          - 抓不到"老项目突然翻红"
        因此结果必须标注为增速榜，不能伪装成官方日榜。
        """
        since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime('%Y-%m-%d')
        query = f'created:>{since} stars:>200'
        url = f'https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page={min(limit * 2, 100)}'

        response = self._get(url, context='search API')
        items = response.json().get('items', [])
        if not items:
            raise ValueError('search API 返回空结果')

        now = datetime.now(timezone.utc)
        candidates = []
        for item in items:
            if item.get('fork') or item.get('archived'):
                continue
            created = item.get('created_at')
            if not created:
                continue
            age_days = max((now - datetime.fromisoformat(created.replace('Z', '+00:00'))).days, 1)
            stars = item.get('stargazers_count', 0)
            candidates.append({
                'author': item['owner']['login'],
                'name': item['name'],
                'full_name': item['full_name'],
                'avatar': item['owner']['avatar_url'],
                'url': item['html_url'],
                'description': item.get('description') or '',
                'language': item.get('language') or '',
                'stars': stars,
                'forks': item.get('forks_count', 0),
                # 用 stars/age 近似增速，让字段语义保持一致
                'currentPeriodStars': int(stars / age_days),
                'languageColor': '#cccccc',
                'readme': '',
            })

        # 按增速排序（近似），而非总星数
        candidates.sort(key=lambda p: p['currentPeriodStars'], reverse=True)
        return candidates[:limit]

    # ---------- 元数据补全（GraphQL 批量）----------

    def _enrich_metadata(self, projects: List[Dict]):
        """一次 GraphQL 请求拉全部仓库元数据，替代原来每项目 1 次 API 调用。"""
        if not projects:
            return

        meta = self._fetch_metadata_graphql([p['full_name'] for p in projects])

        for p in projects:
            info = meta.get(p['full_name'])
            if not info:
                p.setdefault('license', '')
                p.setdefault('topics', [])
                continue
            p['license'] = info.get('license') or ''
            p['topics'] = info.get('topics') or []
            # 分支补齐：GitHub 官方榜有这些字段，search 降级路径没有
            if not p.get('description'):
                p['description'] = info.get('description') or ''
            if not p.get('stars'):
                p['stars'] = info.get('stars', 0)

        self._fetch_preview_images(projects)
        self._fetch_readmes(projects)

    def _fetch_metadata_graphql(self, full_names: List[str]) -> Dict[str, Dict]:
        """用 GraphQL alias 一次拉多个仓库元数据。

        坑：alias 不能包含 '-'，必须用 r0/r1/r2 下标形式。
        未认证时 GraphQL 返回 403，此时静默跳过（不阻断主流程）。
        """
        if not self.github_token:
            print('    · 未配置 GitHub Token，跳过元数据补全（license/topics 为空）')
            return {}

        fields = ('nameWithOwner stargazerCount forkCount description '
                  'primaryLanguage{name} licenseInfo{spdxId} '
                  'repositoryTopics(first:8){nodes{topic{name}}}')

        parts = []
        for i, full_name in enumerate(full_names):
            owner, _, name = full_name.partition('/')
            parts.append(
                f'r{i}: repository(owner: "{owner}", name: "{name}") {{ {fields} }}'
            )
        query = '{ ' + ' '.join(parts) + ' }'

        try:
            response = self.session.post(
                'https://api.github.com/graphql',
                json={'query': query},
                timeout=self.timeout,
            )
            if response.status_code != 200:
                print(f'    · GraphQL 返回 {response.status_code}，跳过元数据补全')
                return {}
            payload = response.json()
            if 'errors' in payload and not payload.get('data'):
                print(f'    · GraphQL 返回错误，跳过元数据补全')
                return {}
        except requests.RequestException as e:
            print(f'    · GraphQL 请求失败，跳过元数据补全: {e}')
            return {}

        result = {}
        for node in (payload.get('data') or {}).values():
            if not node:
                continue
            topics_node = node.get('repositoryTopics') or {}
            result[node['nameWithOwner']] = {
                'stars': node.get('stargazerCount', 0),
                'forks': node.get('forkCount', 0),
                'description': node.get('description') or '',
                'license': ((node.get('licenseInfo') or {}).get('spdxId')) or '',
                'topics': [t['topic']['name'] for t in (topics_node.get('nodes') or []) if t.get('topic')],
            }
        print(f'    · GraphQL 补全 {len(result)}/{len(full_names)} 个仓库元数据')
        return result

    def _fetch_preview_images(self, projects: List[Dict]):
        """抓 opengraph 预览图。文件名带 owner 前缀，避免跨 owner 撞名。"""
        for p in projects:
            try:
                response = self._get(
                    f"{self.preview_url}/{p['author']}/{p['name']}",
                    timeout=10, context=f"预览图 {p['full_name']}",
                )
                img = Image.open(BytesIO(response.content)).convert('RGB')
                # 文件名加 owner 前缀 + 全部小写，规避 macOS 大小写不敏感文件系统覆盖
                safe = f"{p['author']}_{p['name']}".replace('/', '_').lower()
                img.save(self.screenshots_dir / f'{safe}.png')
                p['preview_image'] = f'screenshots/{safe}.png'
            except Exception as e:
                print(f"      ⚠ 预览图获取失败 {p['full_name']}: {e}")
                p['preview_image'] = ''

    def _fetch_readmes(self, projects: List[Dict]):
        """README 走 raw.githubusercontent.com，零 API 配额。"""
        for p in projects:
            try:
                response = self.session.get(
                    f"https://raw.githubusercontent.com/{p['full_name']}/HEAD/README.md",
                    timeout=10,
                )
                if response.status_code == 200:
                    p['readme'] = response.text[:800]
            except requests.RequestException:
                pass
            if not p.get('readme'):
                p['readme'] = p.get('description', '')

    # ---------- 第三层：缓存 ----------

    def _save_cache(self, projects: List[Dict]):
        if not projects:
            return
        try:
            payload = {'date': datetime.now().strftime('%Y%m%d'), 'projects': projects}
            (self.cache_dir / 'trending_cache.json').write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError as e:
            print(f'    · 缓存写入失败: {e}')

    def _load_cache(self) -> List[Dict]:
        cache_file = self.cache_dir / 'trending_cache.json'
        if not cache_file.exists():
            return []
        try:
            data = json.loads(cache_file.read_text(encoding='utf-8'))
            date = data.get('date', '?')
            print(f'    · 使用 {date} 的缓存数据')
            return data.get('projects', [])
        except (OSError, json.JSONDecodeError):
            return []

    # ---------- HTTP ----------

    def _get(self, url: str, *, timeout: Optional[int] = None, context: str = '请求'):
        """统一 GET：失败最多重试 max_retries 次，方法不变。"""
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, timeout=timeout or self.timeout)
                if response.status_code == 200:
                    return response
                last_error = Exception(f'HTTP {response.status_code}')
                retryable = response.status_code in (403, 408, 429) or response.status_code >= 500
                if not retryable or attempt == self.max_retries:
                    return response
            except requests.RequestException as e:
                last_error = e
                if attempt == self.max_retries:
                    raise
            print(f'      ⚠ {context} 失败，重试 {attempt}/{self.max_retries}: {last_error}')
            time.sleep(min(2 * attempt, 6))

        if last_error:
            raise last_error
        raise RuntimeError(f'{context}失败')


def main():
    import argparse
    parser = argparse.ArgumentParser(description='GitHub Trending 采集（三层降级）')
    parser.add_argument('--limit', type=int, default=15, help='候选项目数量')
    parser.add_argument('--since', choices=['daily', 'weekly', 'monthly'], default='daily')
    parser.add_argument('--output', type=str, help='输出文件路径')
    args = parser.parse_args()

    print(f'采集 GitHub Trending (limit={args.limit}, since={args.since})...')
    fetcher = TrendingFetcher()
    try:
        projects = fetcher.fetch(limit=args.limit, since=args.since)
    except FetchError as e:
        print(f'✗ {e}')
        raise SystemExit(1)

    print(f'\n采集结果：{len(projects)} 个项目（来源: {projects[0]["data_source"]}）')
    for p in projects[:8]:
        print(f'  {p["full_name"]:<45} ★{p["stars"]:<7} +{p["currentPeriodStars"]:<6} '
              f'{p["language"]:<12} forks={p["forks"]}')

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({'projects': projects}, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'\n✓ 已保存到 {args.output}')


if __name__ == '__main__':
    main()
