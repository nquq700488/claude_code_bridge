#!/usr/bin/env bash
set -euo pipefail

# 自动推断项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 解析参数
FORCE=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        -f|--force)
            FORCE=true
            shift
            ;;
        -h|--help)
            echo "Usage: $(basename "$0") [-f|--force]"
            echo "  -f, --force  强制清理后停止"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h for help"
            exit 1
            ;;
    esac
done

# ── 收集属于当前项目的守护进程 PID ──
_collect_pids() {
    # 使用 -F 固定字符串匹配项目路径，避免正则特殊字符或前缀重叠导致误杀
    ps aux \
        | grep -E 'ccbd/(keeper_main|main)\.py' \
        | grep -F -- "--project ${PROJECT_ROOT}" \
        | grep -v grep \
        | awk '{print $2}' \
        | sort -u
}

# ── 方式1：通过 ccb CLI 停止（首选）──
if command -v ccb &> /dev/null; then
    if ccb --project "$PROJECT_ROOT" ping ccbd 2>/dev/null | grep -q "pid_alive: True"; then
        echo -e "${YELLOW}▶ 正在停止 ccb...${NC}"
        echo "  项目: $PROJECT_ROOT"
        cd "$PROJECT_ROOT"
        if [[ "$FORCE" == true ]]; then
            ccb --project "$PROJECT_ROOT" kill -f
            echo -e "${GREEN}✓ ccb 已强制停止${NC}"
        else
            ccb --project "$PROJECT_ROOT" kill
            echo -e "${GREEN}✓ ccb 已停止${NC}"
        fi
        exit 0
    fi
fi

# ── 方式2：直接查找并终止残留进程（ccb 不可用或 ping 不通时）──
PIDS=$(_collect_pids)
if [[ -z "$PIDS" ]]; then
    echo -e "${YELLOW}⚠ ccb 未运行${NC}"
    echo "  项目: $PROJECT_ROOT"
    exit 0
fi

echo -e "${YELLOW}▶ 发现残留守护进程，正在停止...${NC}"
echo "  项目: $PROJECT_ROOT"

# 先尝试优雅终止
for pid in $PIDS; do
    if [[ "$FORCE" == true ]]; then
        kill -9 "$pid" 2>/dev/null || true
    else
        kill -15 "$pid" 2>/dev/null || true
    fi
done

# 等待进程退出
sleep 1

# 验证
STILL_ALIVE=0
for pid in $PIDS; do
    if kill -0 "$pid" 2>/dev/null; then
        ((STILL_ALIVE++)) || true
    fi
done

if [[ $STILL_ALIVE -eq 0 ]]; then
    echo -e "${GREEN}✓ 守护进程已停止${NC}"
else
    echo -e "${RED}✗ $STILL_ALIVE 个进程未能停止，请使用 -f 强制停止${NC}" >&2
    exit 1
fi
