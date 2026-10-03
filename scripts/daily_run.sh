#!/usr/bin/env bash
# 每日自动运行（供定时任务调用）
#
# 关键设计：**不自动上传**。上传是外部发布动作，视频内容无人审阅时
# 直接发出去有风险——采集到的东西不代表都值得公开发布。
# 需要上传时手动跑：bash scripts/render.sh --upload
#
# 环境说明：定时任务的 PATH 很精简，所以：
#   - GitHub Token 从 gh CLI 自动获取（不依赖环境变量）
#   - ffmpeg 从 bin/ 软链兜底
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# 补齐 PATH（定时任务环境通常只有 /usr/bin:/bin）
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
[ -x bin/ffmpeg ] && export PATH="$PWD/bin:$PATH"

LOG_DIR="output/logs"
mkdir -p "$LOG_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$LOG_DIR/daily_$STAMP.log"

{
    echo "=============================================="
    echo " 每日自动运行 $STAMP"
    echo "=============================================="
} | tee "$LOG"

# 环境预检
if [ ! -d venv ]; then
    echo "✗ venv 不存在，自动执行 bootstrap..." | tee -a "$LOG"
    bash scripts/bootstrap.sh >>"$LOG" 2>&1 || {
        echo "✗ bootstrap 失败，见 $LOG" | tee -a "$LOG"
        exit 1
    }
fi

# 采集（GitHub Token 由 pipeline 内部从 gh CLI 获取）
echo "" | tee -a "$LOG"
echo "[1/2] 采集" | tee -a "$LOG"
if ! bash scripts/quickstart.sh >>"$LOG" 2>&1; then
    echo "✗ 采集失败，见 $LOG" | tee -a "$LOG"
    exit 1
fi

# 渲染（内含文案质量闸，不达标会中止并提示）
echo "" | tee -a "$LOG"
echo "[2/2] 渲染" | tee -a "$LOG"

# 关键：规则式兜底文案达不到内容质量标准。
# 这里先单独跑一次渲染，看是否因文案被拦下 —— 是则明确告诉用户
# 「素材已就绪，等你补文案」，而不是含糊报「渲染失败」。
if ! bash scripts/render.sh >>"$LOG" 2>&1; then
    if scripts/validate_narrative >>"$LOG" 2>&1; then
        # 校验通过但渲染失败 = 真失败
        echo "✗ 渲染失败，见 $LOG" | tee -a "$LOG"
        exit 1
    fi

    echo "" | tee -a "$LOG"
    echo "==============================================" | tee -a "$LOG"
    echo "⚠ 素材已就绪，等待补文案" | tee -a "$LOG"
    echo "" | tee -a "$LOG"
    echo "  采集与文案模板已生成：output/trending.json" | tee -a "$LOG"
    echo "  兜底文案不达标 —— 规则式生成只能复述数据，说不清项目用途。" | tee -a "$LOG"
    echo "" | tee -a "$LOG"
    echo "  下一步（在 WorkBuddy 里说「补今天的文案」即可）：" | tee -a "$LOG"
    echo "    1. 读 output/trending.json 里各项目的 readme 与 topics" | tee -a "$LOG"
    echo "    2. 填写 output/projects_summary.json 的 narrative" | tee -a "$LOG"
    echo "    3. bash scripts/render.sh" | tee -a "$LOG"
    echo "" | tee -a "$LOG"
    echo "  日志: $LOG" | tee -a "$LOG"
    echo "==============================================" | tee -a "$LOG"
    exit 2
fi

# 汇总
VIDEO="output/trending_video.mp4"
echo "" | tee -a "$LOG"
echo "==============================================" | tee -a "$LOG"
if [ -f "$VIDEO" ]; then
    SIZE=$(du -h "$VIDEO" | cut -f1)
    DURATION=$(venv/bin/python -c "
import sys; sys.path.insert(0, 'src')
from video_composer import probe_duration
d = probe_duration('$VIDEO')
print(f'{int(d)//60}分{int(d)%60}秒' if d else '未知')
" 2>/dev/null || echo "未知")
    echo "✓ 视频已生成" | tee -a "$LOG"
    echo "  文件: $VIDEO（$SIZE，$DURATION）" | tee -a "$LOG"
    echo "  封面: output/cover.png" | tee -a "$LOG"
    echo "  文案: output/projects_summary.json" | tee -a "$LOG"
else
    echo "✗ 未产出视频" | tee -a "$LOG"
    exit 1
fi
echo "" | tee -a "$LOG"
echo "  未自动上传。需要发布时手动执行：" | tee -a "$LOG"
echo "    bash scripts/render.sh --upload" | tee -a "$LOG"
echo "==============================================" | tee -a "$LOG"
echo "日志: $LOG"
