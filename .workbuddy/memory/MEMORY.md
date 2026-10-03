# 项目长期记忆 — trending

## 项目定位
GitHub Trending 视频自动生成流水线：采集 → 去重 → 文案 → 配音 → 渲染（可选上传 B站）。
仓库：github.com/Terrylol/trending（克隆于 /Users/chengshang/WorkBuddy/trending）

## 当前状态（2026-10-03 重构已完成）
**入口：`venv/bin/python pipeline.py`**。已删除 Remotion 全链、SKILL.md、run_workflow.py、
test_upload.py。当前是 MoviePy/PIL 纯渲染架构，详见 README.md。

## 文案流程（用户明确要求简化）
**不需要逐个项目深度研究。** `pipeline.auto_narrative()` 纯规则式生成：
- hook 抓最亮眼数据（日增星 / 星标总量）
- body = 中文描述直接用；英文描述按关键词转中文概述 + 星标/fork/日增数据
- 落盘到 `output/projects_summary.json`，**可手工编辑后重跑复用**
- 不要用机器翻译，翻译质量不可靠；英文 topic 不罗列进中文句子（会断行混乱）
- 用户想润色时编辑该 JSON 即可，不必重新研究

## Star 趋势图（踩过坑，别走回头路）
- **绝不能自绘假曲线冒充真实数据**。之前 cairosvg 装不上就画装饰曲线，是错的。
- 现在做法：从 star-history.com 的 SVG 里**解析真实曲线数据点**再用 PIL 重绘
- 相关测试：`test_extract_curve_points_*` / `test_render_curve_*` / `test_chaikin_*`

### SVG path 解析的两个必坑（都实际踩过）
1. **隐式命令重复**：同命令的后续参数组省略命令字母。
   实测 star-history 曲线是 `m0 423.3` + 112 个数字却只有 **1 个字母 `c`**。
   必须按"每 N 个数字一组"（ARITY 表）推进，**不能按命令字母切分**。
   我最初按字母切分，112 个数字只解析出 18 个点（漏了 82%）。
2. **相对命令要累加**：`c`/`m` 参数是相对当前点的偏移。
   起点 `m0 423.3` 必须计入，否则整条曲线平移、y 全为负。

### 如何验证曲线是真数据（重要方法）
不要只看形状像不像，**用 SVG 里的 Y 轴刻度反推星数**：
```bash
# 1. 提取刻度（形如 5K/10K/15K）及其 translate 坐标
re.findall(r'<text[^>]*transform="translate\(([\d.]+)[, ]+([\d.]+)\)"[^>]*>' + label, svg)
# 2. 两点定斜率，校验线性度必须一致
# 3. 用曲线端点 y 反推星数，与 GitHub API 实际值对比
```
实测验证结果：effect 曲线最高点 y=2.7 → 换算 **16,638 星**，
GitHub API 实际 **16,724 星**，误差 0.5%（star-history 有小时级延迟）。
**这就是"数据真实"的硬证据**，不是靠肉眼判断。

### Y 轴方向
star-history 的 y 越小 = 星越多（顶部=最大值）。
渲染时归一化要用 `ratio = (y - min_y) / span_y` 再映射到屏幕高度。

### 视觉调优
- Y 轴归一化**留 12% 顶部余量**，否则曲线贴住顶端、填充区糊成一片实色
- 填充用 alpha 70（不是 38），线条用 (125,211,252)
- 只有 ~20 个月的数据点，必须用 `_chaikin_smooth` 平滑否则折线生硬
- star-history 对超大仓库偶发返回错误页（<2KB），需串行重试

## 重构决策（用户拍板）
- **定位**：个人日更号（量取胜，稳定 > 惊艳，流水线可靠性优先级最高）
- **渲染**：MoviePy/Pillow 纯渲染。ImageClip 走 ffmpeg 底层合成不逐帧迭代像素，1080p 可行
- **样式**：静态排版优先。不做动态效果迭代（spring/clip-path/光晕全部移除）
- **规格**：1920x1080 横屏 24fps，布局按 `unit = width/1920` 等比缩放
- **TTS**：edge-tts（免费无需 key），voice/speed 已真正接入配置
- **Star 图**：继续用 star-history.com（8s 超时 + 并发预取 + 失败降级为自绘曲线）
- **上传**：显式 `--upload`，默认不上传，上传前校验视频存在/项目数≥3/凭据完整
- **去重**：7 天冷却
- **明确不做**：竖屏、动态效果、RSSHub 降级层

## 关键事实（实测，非推测，勿再重复调研）
- **fork 与日增 star 曾长期静默失效**：GitHub 把 `/network/members` 改为 `/forks`；
  `find(string=...)` 因 `stars today` 文本被包在 `<svg>` 兄弟节点而恒返回 None。
  现已修复，实测 8,196 forks / +1,289 today。
- **无官方 Trending API**，2026 年状态未变。第三方源全挂（RSSHub 公共实例、
  各类镜像 API、bonfy 归档均实测不可用）；可用归档仓库也爬 HTML，不独立于 GitHub DOM。
- **search API 无法替代 Trending**：实测 Top10 零重叠。search 索引无 star 时间序列，
  存量排序 ≠ 增速排序。
- **star-history.com 只有 SVG**，延迟 2.5-25s，偶发 403，cli/cli 拒。无 JSON 端点。
- **元数据从 45 次请求砍到 1 次**：GraphQL alias（`r0`..`r14`，alias 不能含 `-`）。
  README 走 raw.githubusercontent.com 零配额。逗号批量端点 `/repos/a,b` 已废弃（404）。
- **cairosvg 在本机装不上**（缺原生 libcairo，brew 被 sandbox 阻塞），
  故 Star 图 SVG 转换实际走自绘回退。

## MoviePy 动效踩坑（务必记住）
- **`clip.resized(lambda t: X)` 的 lambda 收到的是时间 t，不是倍率。**
  所以不能用两次 resized 做"放大再缩回" —— 第二次会拿到 t=0 算出尺寸 0，
  报 `ValueError: height and width must be > 0`。
  正确做法：`resized(lambda t: ZOOM).cropped(...)` 居中裁回原尺寸。
- 缩放会改变画布尺寸（1920 → 1967），**必须裁回**，否则输出分辨率异常。
  `_validate_video` 里加了分辨率断言，改渲染参数时出问题会立刻暴露。
- 缩放还会让 MoviePy 推断出 **yuv444p** 采样，B站兼容性差。
  `write_videofile` 必须显式 `ffmpeg_params=['-pix_fmt', 'yuv420p']`。
- `AudioFileClip.close()` 必须在 `concatenate_videoclips` **之后**，
  否则 reader 变 None → `'NoneType' object has no attribute 'get_frame'`。
- 动效测试要点：**必须 `get_frame()` 真渲染几帧**，只看尺寸断言抓不到
  渲染期才崩的问题。

## 内容和动效决策（2026-10-04 用户拍板）
- **内容定位：它是"内容"，不是工具副产品。观众看完就走。**
  ⇒ 质量标准不是"讲得深"，而是**每 15 秒必须给一个观众听榜单听不到的点**。
  ⇒ 文案判断标准：不能复述屏幕已有的数字（星标数/日增数），必须说"它是干什么的"。
- **文案**：Agent 轻量探索（读 README 前 2000 字 + topics），不做深度研究。
  我执行探索+写文案，pipeline 负责渲染。`auto_narrative` 只是无探索时的兜底，
  质量上限低（对任何 AI 工具都会输出同一句话）。
- **动效**：保守档 —— 入场淡入 0.4s + 1.0→1.025 微推镜 + 转场淡化 0.25s。
  配置项 `video.animate` 可关。
- **时长**：总时长约 3 分钟（用户指定）。注意这与"每项目 20 秒 × 5"冲突
  （只到 2 分钟），实际按每项目 25-30 秒来做。
- **上传暂不动**（封面缺失/标题无钩子的问题仍在，用户明确说先不动）。
  `output/cover.png` 从未生成，`bilibili_uploader.py:68` 找不到 → 封面为空。

## 待办 P0（需用户操作）
- [ ] **用户需在 B站登出设备并重置会话** —— 旧凭据自首个提交 6467e5c 起就在历史里，
      共 20 个提交受影响，HEAD 完好
- [ ] **改写 git 历史** —— 已备好 `scripts/purge_bilibili_credentials.sh`
      （git filter-repo + 镜像备份 + 交互确认 + 校验）。
      需 force push，等用户确认时机后执行。
      注意：只删文件不够，GitHub 可能缓存旧对象，需通知所有 clone 者重新克隆。
- [x] 代码侧防护：凭据走环境变量 + pre-commit 钩子 + .env.example
- [x] B站封面：`generate_cover()` 生成 1280x800，缺失时上传器显式报错
      （此前 cover='' 静默降级，视频无推荐量但调用方以为设置成功）

## Git 状态
- 重构已提交：`851f682`（重构主体）+ `6c297f6`（封面 + 凭据清除脚本）
- 本地领先 origin/master 2 个提交，**尚未 push**

## 字体坑（macOS，已在代码中修复）
- `/System/Library/Fonts/PingFang.ttc` 在现代 macOS **不存在**
- `STHeiti Medium.ttc` face 0 = Heiti TC（繁体），**face 1 = Heiti SC（简体）才对**
- `CardGenerator._find_cjk_font()` 会自动探测并显式选简体 face

## 环境事实
- **ffmpeg 来源**：`brew install` 被 sandbox 阻塞，改用 `imageio-ffmpeg` 的二进制 +
  `bin/ffmpeg` 软链（`bin/` 已 gitignore）。用 `PATH="$PWD/bin:$PATH"` 注入
- **本机没有真 ffprobe**（别再写依赖它的代码，用 ffmpeg -i 解析 stderr）
- gh CLI 已登录，PAT 40 字符；用 `GITHUB_TOKEN` 环境变量传入
- Python: /Users/chengshang/.workbuddy/binaries/python/versions/3.13.12/bin/python3

## 约定
- 新增纯函数后**必须补单测**到 `tests/test_core.py`（当前 35 个，`pytest tests/ -q`）
  ——本次测试就抓出了多个我自己引入的 bug
- 采集数据必须过 `TrendingFetcher._assert_healthy()` 断言，绝不允许返回空列表或全 0 数据
- **测试临时目录用项目内 `TempDir` 上下文管理器，不要用 pytest 的 `tmp_path`**
  ——本机沙箱下 /tmp 的 pytest 临时目录不可写（PermissionError）
- 展示数据时宁可显示占位，也**绝不用推测/装饰数据冒充真实数据**
