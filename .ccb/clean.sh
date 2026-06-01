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
DRY_RUN=false
FORCE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            echo "Usage: $(basename "$0") [-f|--force] [-n|--dry-run]"
            echo "  -f, --force   不提示直接删除"
            echo "  -n, --dry-run 只列出将被删除的内容，不实际删除"
            exit 0
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        -n|--dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h for help"
            exit 1
            ;;
    esac
done

# 需要保留的文件和目录（白名单）
declare -A KEEP=(
    ["ccb.config"]=1
    ["README.md"]=1
    ["restart.sh"]=1
    ["start.sh"]=1
    ["stop.sh"]=1
    ["clean.sh"]=1
)

echo -e "${YELLOW}▶ 清理 .ccb 运行时文件...${NC}"
echo "  项目: $PROJECT_ROOT"
echo ""

# 检查哪些将被删除
TO_DELETE=()
TO_KEEP=()
for item in "$SCRIPT_DIR"/* "$SCRIPT_DIR"/.[!.]* "$SCRIPT_DIR"/..?*; do
    [[ -e "$item" ]] || continue
    name="$(basename "$item")"

    # 跳过 . 和 ..
    [[ "$name" == "." || "$name" == ".." ]] && continue

    if [[ -n "${KEEP[$name]:-}" ]]; then
        TO_KEEP+=("$item")
    else
        TO_DELETE+=("$item")
    fi
done

# 列出将被删除的内容
if [[ ${#TO_DELETE[@]} -eq 0 ]]; then
    echo -e "${GREEN}✓ 没有需要清理的运行时文件${NC}"
    exit 0
fi

echo -e "${YELLOW}将被删除：${NC}"
for item in "${TO_DELETE[@]}"; do
    size=$(du -sh "$item" 2>/dev/null | cut -f1 || echo "-")
    echo "  $size  $item"
done
echo ""

total_size=$(du -sh "$SCRIPT_DIR" 2>/dev/null | cut -f1 || echo "-")
echo "当前目录总大小: $total_size"

# 确认删除
if [[ "$DRY_RUN" == true ]]; then
    echo -e "${YELLOW}[dry-run] 未实际删除${NC}"
    exit 0
fi

if [[ "$FORCE" != true ]]; then
    echo ""
    read -p "确认删除以上文件？(y/N) " -r answer
    [[ "$answer" =~ ^[Yy]$ ]] || { echo "已取消"; exit 0; }
fi

# 删除
echo ""
echo -e "${YELLOW}正在删除...${NC}"
for item in "${TO_DELETE[@]}"; do
    rm -rf "$item"
    echo "  ✓ $item"
done

remaining_size=$(du -sh "$SCRIPT_DIR" 2>/dev/null | cut -f1 || echo "-")
echo ""
echo -e "${GREEN}✓ 清理完成${NC}"
echo "  剩余大小: $remaining_size"