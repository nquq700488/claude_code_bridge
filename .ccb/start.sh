#!/usr/bin/env bash
set -euo pipefail

# 自动推断项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查 ccb 是否已安装
if ! command -v ccb &> /dev/null; then
    echo -e "${RED}✗ ccb 未安装或不在 PATH 中${NC}" >&2
    exit 1
fi

# 切换到项目目录（后续命令依赖项目上下文）
cd "$PROJECT_ROOT"

# 检查 ccb 是否已在运行
if ccb ping ccbd 2>/dev/null | grep -q "pid_alive: True"; then
    echo -e "${GREEN}✓ ccb 已运行${NC}"
    echo "  项目: $PROJECT_ROOT"
    ccb ps 2>/dev/null || true
    exit 0
fi

# 未运行，启动 ccb
echo -e "${YELLOW}▶ ccb 未运行，正在启动...${NC}"
echo "  项目: $PROJECT_ROOT"

# exec 接管当前终端显示 tmux 界面
exec ccb "$@"
