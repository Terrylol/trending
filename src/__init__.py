"""GitHub Trending 视频生成 · 业务模块。

作为正规包（而非 namespace package）存在，这样 `python -m src.xxx`
在任何目录下都能解析 —— 定时任务、cron、CI 里的工作目录不固定，
不能依赖"当前目录恰好是项目根"。
"""
