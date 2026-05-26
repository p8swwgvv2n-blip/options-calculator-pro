#!/bin/bash
# 期权 IV 定时导出 — Mac 安装脚本
# 运行此脚本后，每天 9:00 自动导出 IV 数据
#
# 用法：chmod +x setup-cron-mac.sh && ./setup-cron-mac.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/定时导出期权IV.py"

# Check Python 3 exists
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3，请先安装 Python 3"
    exit 1
fi

# Add to crontab (weekday 9:00 AM)
CRON_LINE="0 9 * * 1-5 cd \"$SCRIPT_DIR\" && python3 \"$PYTHON_SCRIPT\" >> \"$SCRIPT_DIR/iv-cron.log\" 2>&1"

# Check if already in crontab
if crontab -l 2>/dev/null | grep -q "定时导出期权IV.py"; then
    echo "定时任务已存在，跳过安装"
else
    (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
    echo "已安装定时任务：每周一至周五 9:00 自动导出"
fi

# Run once to test
echo "运行一次测试..."
python3 "$PYTHON_SCRIPT"

echo ""
echo "安装完成！"
echo "查看日志: cat $SCRIPT_DIR/iv-cron.log"
echo "查看任务: crontab -l"
echo "删除任务: crontab -e  然后删除对应行"
