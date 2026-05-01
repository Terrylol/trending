"""
GitHub Trending采集
- 直接爬取GitHub Trending页面
- 获取项目预览图（GitHub Open Graph）
- 可选使用GitHub Token提高限制
"""
from typing import List, Dict
import requests
from PIL import Image
from io import BytesIO
from pathlib import Path
from bs4 import BeautifulSoup
import re

class TrendingFetcher:
    def __init__(self, config: Dict):
        self.trending_url = 'https://github.com/trending'
        self.preview_url = config.get('preview_image_url', 'https://opengraph.githubassets.com/1')
        self.github_token = config.get('personal_access_token')
        self.screenshots_dir = Path('screenshots')
        self.screenshots_dir.mkdir(exist_ok=True)
    
    def fetch(self, limit: int = 15, since: str = 'daily') -> List[Dict]:
        """采集热门项目"""
        print(f"  采集 GitHub Trending (limit={limit}, since={since})...")
        
        url = f"{self.trending_url}?since={since}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        if self.github_token:
            headers['Authorization'] = f'token {self.github_token}'
        
        response = requests.get(url, headers=headers, timeout=20)
        
        if response.status_code != 200:
            raise Exception(f"请求失败: {response.status_code}")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        articles = soup.find_all('article', class_='Box-row')[:limit]
        
        projects = []
        
        for article in articles:
            project = self._parse_article(article)
            if project:
                projects.append(project)
        
        print(f"  ✓ 获取 {len(projects)} 个项目")
        
        # 补充预览图和README
        for i, project in enumerate(projects):
            print(f"    处理项目 [{i+1}/{len(projects)}]: {project['name']}")
            project['preview_image'] = self._fetch_preview_image(project)
            project['readme'] = self._fetch_readme(project)
        
        return projects
    
    def _parse_article(self, article) -> Dict:
        """解析单个项目"""
        try:
            # 项目名称和链接
            h2 = article.find('h2', class_='h3')
            a_tag = h2.find('a')
            href = a_tag['href'].strip('/')
            
            # 分离owner和repo
            parts = href.split('/')
            owner = parts[0]
            repo = parts[1] if len(parts) > 1 else parts[0]
            
            # 描述
            p_tag = article.find('p', class_='col-9')
            description = p_tag.get_text(strip=True) if p_tag else ''
            
            # 语言
            lang_span = article.find('span', itemprop='programmingLanguage')
            language = lang_span.get_text(strip=True) if lang_span else ''
            
            # 语言颜色
            lang_color_span = article.find('span', class_='repo-language-color')
            language_color = lang_color_span['style'].split(':')[1].strip('; ') if lang_color_span else '#ccc'
            
            # 星标数
            stars_a = article.find('a', href=re.compile(r'/stargazers'))
            stars_text = stars_a.get_text(strip=True).replace(',', '') if stars_a else '0'
            stars = int(stars_text) if stars_text.isdigit() else 0
            
            # Fork数
            forks_a = article.find('a', href=re.compile(r'/network/members'))
            forks_text = forks_a.get_text(strip=True).replace(',', '') if forks_a else '0'
            forks = int(forks_text) if forks_text.isdigit() else 0
            
            # 今日新增星标
            stars_today_span = article.find('span', string=re.compile(r'stars today'))
            stars_today = 0
            if stars_today_span:
                match = re.search(r'(\d+,?\d*)', stars_today_span.get_text())
                if match:
                    stars_today = int(match.group(1).replace(',', ''))
            
            return {
                'author': owner,
                'name': repo,
                'avatar': f'https://github.com/{owner}.png',
                'url': f'https://github.com/{owner}/{repo}',
                'description': description,
                'language': language,
                'languageColor': language_color,
                'stars': stars,
                'forks': forks,
                'currentPeriodStars': stars_today,
                'preview_image': '',
                'readme': ''
            }
        except Exception as e:
            print(f"      解析失败: {e}")
            return None
    
    def _fetch_preview_image(self, project: Dict) -> str:
        """获取项目预览图"""
        owner, repo = self._parse_url(project['url'])
        image_url = f"{self.preview_url}/{owner}/{repo}"
        
        try:
            response = requests.get(image_url, timeout=10)
            img = Image.open(BytesIO(response.content))
            
            # 缩放至适合卡片尺寸 (保持宽高比)
            img = img.resize((750, 394))
            
            image_path = self.screenshots_dir / f"{repo}.png"
            img.save(image_path)
            return str(image_path)
        except Exception as e:
            print(f"      获取预览图失败: {e}")
            return ""
    
    def _fetch_readme(self, project: Dict) -> str:
        """获取README"""
        owner, repo = self._parse_url(project['url'])
        readme_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        
        headers = {}
        if self.github_token:
            headers['Authorization'] = f'token {self.github_token}'
        
        try:
            response = requests.get(readme_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                import base64
                content = base64.b64decode(response.json()['content']).decode()
                return content[:500]  # 只取前500字符
        except:
            pass
        
        return project.get('description', '')
    
    def _parse_url(self, url: str):
        """解析URL获取owner和repo"""
        parts = url.rstrip('/').split('/')
        return parts[-2], parts[-1]


def get_mock_projects(count: int = 3) -> List[Dict]:
    """生成Mock项目数据（用于调试）"""
    mock_data = [
        {
            "author": "deepseek-ai",
            "name": "DeepSeek-R1",
            "avatar": "https://github.com/deepseek-ai.png",
            "url": "https://github.com/deepseek-ai/DeepSeek-R1",
            "description": "开源的推理模型，媲美 O1，支持本地部署",
            "language": "Python",
            "languageColor": "#3572A5",
            "stars": 45800,
            "forks": 1200,
            "currentPeriodStars": 3200,
            "preview_image": "",
            "readme": "DeepSeek-R1 是一个开源的推理模型..."
        },
        {
            "author": "cline",
            "name": "cline",
            "avatar": "https://github.com/cline.png",
            "url": "https://github.com/cline/cline",
            "description": "VS Code 中的 AI 编程助手，支持 Claude 和 GPT",
            "language": "TypeScript",
            "languageColor": "#2b7489",
            "stars": 28300,
            "forks": 890,
            "currentPeriodStars": 2100,
            "preview_image": "",
            "readme": "Cline 是一个 VS Code 扩展..."
        },
        {
            "author": "meta-llama",
            "name": "llama3.3",
            "avatar": "https://github.com/meta-llama.png",
            "url": "https://github.com/meta-llama/llama3.3",
            "description": "Meta 最新开源模型，70B 参数，性能强劲",
            "language": "Python",
            "languageColor": "#3572A5",
            "stars": 52100,
            "forks": 2100,
            "currentPeriodStars": 4500,
            "preview_image": "",
            "readme": "Llama 3.3 是 Meta 的最新开源模型..."
        }
    ]
    
    return mock_data[:count]


def main():
    """主函数 - 命令行接口"""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='GitHub Trending采集工具')
    parser.add_argument('--limit', type=int, default=5, help='项目数量')
    parser.add_argument('--since', choices=['daily', 'weekly', 'monthly'], default='daily', help='时间范围')
    parser.add_argument('--output', type=str, help='输出文件路径')
    
    args = parser.parse_args()
    
    print(f"正在采集 GitHub Trending (limit={args.limit}, since={args.since})...")
    
    fetcher = TrendingFetcher({})
    projects = fetcher.fetch(limit=args.limit, since=args.since)
    
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({"projects": projects}, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 已保存到 {args.output}")
    else:
        print(json.dumps({"projects": projects}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()