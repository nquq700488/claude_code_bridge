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

# 检查 ccb 是否已安装
if ! command -v ccb &> /dev/null; then
    echo -e "${RED}✗ ccb 未安装或不在 PATH 中${NC}" >&2
    exit 1
fi

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

# 检查 ccb 是否正在运行（需确认进程实际存活，而非仅项目已注册）
if ! ccb --project "$PROJECT_ROOT" ping ccbd 2>/dev/null | grep -q "pid_alive: True"; then
    echo -e "${YELLOW}⚠ ccb 未运行${NC}"
    echo "  项目: $PROJECT_ROOT"
    exit 0
fi

# 停止 ccb
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
