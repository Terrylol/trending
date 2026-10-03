# GitHub Trending Video

> 自动生成 GitHub Trending 视频：采集 → 去重 → 文案 → 配音 → 渲染（可选上传 B站）

Python + PIL + MoviePy，无 Node/Chromium 依赖。单命令跑完整流程。

> **让 AI Agent 执行本项目**：见 [`SKILL.md`](SKILL.md)，包含完整工作流与文案质量标准。

## 快速开始

```bash
# 1. 安装依赖
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# 2. 配置（推荐用环境变量，不落盘到被提交的文件）
cp .env.example .env && 编辑填写
cp config/config.example.json config/config.json

# 3. 跑
export GITHUB_TOKEN=xxx
venv/bin/python pipeline.py
```

## 文案

两种模式，取决于你在 `auto_narrative` 还是 Agent：

**默认：规则式自动生成。** 只用采集时已在手的数据（日增星、星标、fork、
描述、语言），不需要探索任何项目：

| 字段 | 生成方式 |
|---|---|
| `hook` | 抓最亮眼的数据（日增星数 / 星标总量） |
| `body` | 中文描述直接用；英文描述按关键词转成中文概述 |
| `call_to_action` | 固定引导语 |

**推荐：Agent 轻量探索。** `auto_narrative` 的上限是"复述数据"——它说不出
项目是干什么的。要让视频有内容价值，Agent 只需读 `output/trending.json` 里
已经采集好的 `readme`（已清洗，3000 字符内）和 `topics`，回答一个问题：
**"它是干什么的？"** 然后写入 `output/projects_summary.json`。

判断标准很简单：**文案里每句话都应该是观众听榜单听不到的。** 念星标数
是无效内容（屏幕右边就写着），说"这是个帮你跨会话记住上下文的工具"才是。

### 文案质量校验

```bash
venv/bin/python -m src.narrative_validator output/projects_summary.json
```

拦截三类问题，退出码非 0 表示不达标：

| 类型 | 例子 |
|---|---|
| 套话 | 「这是一个面向 AI 智能体的工具，用 Python 编写」 |
| 数字复述 | 「目前 89,533 星，7,877 个 fork」 |
| 字数不足 | body 少于 110 字撑不起 30 秒口播 |

`--lenient` 只查字数不查套话。

文案落在 `output/projects_summary.json`，已存在的会被复用，想润色就直接编辑。

## 命令

```bash
venv/bin/python pipeline.py --draft          # 只采集 + 生成文案模板，不渲染
venv/bin/python pipeline.py                  # 渲染出视频（不上传）
venv/bin/python pipeline.py --upload         # 渲染后上传 B 站
venv/bin/python pipeline.py --limit 20       # 加大候选池
venv/bin/python pipeline.py --target 3       # 只要 3 个项目
venv/bin/python pipeline.py --skip-dedupe    # 跳过去重

# 单步调试
venv/bin/python src/trending_fetcher.py --limit 15
venv/bin/python src/history_deduper.py status --status video_succeeded

# 测试
venv/bin/python -m pytest tests/ -q
```

## 典型工作流

```
1. pipeline.py --draft      采集 + 生成文案模板
2. （编辑 output/projects_summary.json 的 narrative，或让 Agent 写）
3. pipeline.py              渲染出 mp4
4. pipeline.py --upload     重新渲染并上传（跳过第 3 步）
```

`--draft` 不会配音也不渲染，适合"今天先看看有哪些项目"。
采集结果已包含 `readme` / `topics` / `preview_image` / `license`，
写文案需要的信息都在里面。

## 取数架构（三层降级）

```
第一层  github.com/trending HTML     ← 唯一能拿到官方策展 + 真实日增 star
   ↓ 解析断言失败（空列表 / 全 0 日增 / 数量不足）
第二层  GitHub Search API 增速榜      ← 1 次请求，标注"非官方日榜"
   ↓ 网络也挂
第三层  本地缓存                      ← 标注数据日期
```

任一层的结果都会做健康度断言，**绝不返回空列表或全 0 数据**——
这是防止"GitHub 改版 → 发布一条 Top 0 视频"的硬防线。

### 已知的选择器失效风险

GitHub Trending 没有官方 API，页面结构随时会变。解析器已做防御：

| 数据 | 脆弱写法（会静默失效） | 本项目写法 |
|---|---|---|
| fork 数 | `a[href*='/network/members']` | `a[href$='/forks']`（两种兼容） |
| 日增 star | `span(string=re.search('stars today'))` | `article.get_text()` 整块正则 |
| 语言色 | `style.split(':')[1]` | 正则提取，失败用默认色 |

改版时会触发断言失败并自动降级，不会静默产出错误数据。

## 渲染

| 项 | 值 |
|---|---|
| 分辨率 | 1920×1080（`config.json` 的 `video.resolution`） |
| 帧率 | 24fps，yuv420p |
| 动效 | 入场淡入 + 1.0→1.025 微推镜 + 转场淡化 |
| 合成 | PIL 静态卡片 + MoviePy + ffmpeg |
| 时长 | 由 TTS 音频长度驱动，每段尾部留 0.8s |

动效只用 MoviePy 的位移/缩放/透明度三类能力，不需要 Node 或额外依赖。
缩放后强制裁回原尺寸并锁定 `yuv420p`，否则会输出 1967x1107 的异常分辨率
和 4:4:4 采样（B站兼容性差）。完整性校验里有一条分辨率断言，改动渲染参数时
出问题会立刻暴露。

配置 `"animate": false` 可关闭全部动效，回到纯静态。

渲染器会校验音视频流是否齐全、时长是否与预期吻合，防止进程中断产出半截视频。

### 中文字体

macOS 上 `PingFang.ttc` 在新版本已移除。本项目自动探测可用中文字体，
并且对 `.ttc` 字体集合**显式选择简体 face**（`STHeiti Medium.ttc` 的
face 0 是繁体 Heiti TC，face 1 才是简体 Heiti SC）。

可用 `TRENDING_CJK_FONT` 环境变量手动指定字体。

### Star 趋势图

实现方式是**从 star-history.com 返回的 SVG 里解析真实曲线数据点**，再用 PIL
重绘——不依赖 cairosvg / rsvg-convert / inkscape，因为 macOS 上这三者常缺，
而"SVG 转 PNG"是这条链路最大的脆弱点。

- 12 秒硬超时，失败项**串行重试一次**（SVG 可达 60KB+，并发时容易超时）
- 12 小时缓存，避免同一天重复请求
- 解析不到真实曲线时显示占位，**绝不用推测数据冒充真实曲线**

如果 star-history 对某个仓库返回错误页（超大仓库如 27 万星的 ECC 偶发），
该项目的图会显示占位，不影响视频产出。

## 配置

`config/config.example.json`：

| 配置项 | 说明 | 默认 |
|---|---|---|
| `video.resolution` | 视频分辨率 | `1920x1080` |
| `video.fps` | 帧率 | `24` |
| `video.limit` | 候选池大小 | `15` |
| `video.target_count` | 最终视频内项目数 | `5` |
| `tts.engine` | `edge` / `vectorengine` / `volcengine` | `edge` |
| `tts.voice` | 音色 | `zh-CN-XiaoxiaoNeural` |
| `tts.speed` | 语速倍率 | `1.3` |
| `github.personal_access_token` | GitHub Token | 空（建议用 `GITHUB_TOKEN` 环境变量） |
| `star_history.enabled` | 是否启用趋势图 | `true` |
| `star_history.timeout` | 单个请求超时秒数 | `20` |
| `star_history.concurrency` | 并发数 | `2` |

## 安全

**凭据一律走环境变量**，不写进被 git 跟踪的文件：

```bash
export GITHUB_TOKEN=xxx
export BILIBILI_SESSDATA=xxx
export BILIBILI_BILI_JCT=xxx
export BILIBILI_BUVID3=xxx
```

仓库内置 pre-commit 钩子拦截凭据入库：

```bash
cp scripts/guard_secrets.py .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

> ⚠️ 本仓库历史上曾提交过明文 B站凭据。如你 clone 过早期版本，
> 请立即在 B站登出相关设备并重置会话——删文件不能清除 git 历史。

## B站上传

上传是**外部发布动作，默认关闭**。需显式加 `--upload`。

上传前会校验：视频存在、项目数 ≥3、封面存在、凭据完整。

标题用「今日涨星最多」的项目做钩子，而不是纯日期：

```
GitHub 今日热榜｜Agent-Reach 一天涨了 1,683 星
```

凭据走环境变量：

```bash
export BILIBILI_SESSDATA=xxx
export BILIBILI_BILI_JCT=xxx
export BILIBILI_BUVID3=xxx
```

分区默认 122（科技区 → 知识 → 科学 → 其他），可在 `config.json` 的
`bilibili.tid` 修改。封面由 `pipeline.step_render` 自动生成到
`output/cover.png`（1280×800）。

> ⚠️ `qrcode-terminal` 在部分沙箱环境会安装失败（pip 报 mkdir EEXIST）。
> 失败时从 PyPI 下载 tar.gz 解包到 `site-packages/` 即可。

## 项目结构

```
.
├── pipeline.py               # 主流水线（单命令）
├── requirements.txt
├── config/
│   └── config.example.json
├── data/projects_history.json  # 去重历史
├── assets/github_logo.png
├── docs/PLAN.md             # 重构方案（历史文档）
├── SKILL.md                 # Agent 执行指令（给 AI 读）
├── scripts/
│   ├── guard_secrets.py     # pre-commit 凭据拦截
│   └── purge_bilibili_credentials.sh  # 清除 git 历史中的凭据
├── tests/test_core.py       # 单元测试
└── src/
    ├── trending_fetcher.py    # 取数（三层降级）
    ├── history_deduper.py     # 去重
    ├── card_generator.py      # 卡片排版 + 封面 + Star 趋势图
    ├── narrative_validator.py # 文案质量校验
    ├── tts_generator.py       # 语音调度
    ├── video_composer.py      # 合成 + 动效 + 校验
    ├── bilibili_uploader.py   # B站上传
    └── tts/                   # 多引擎 TTS
```

## 许可证

MIT
