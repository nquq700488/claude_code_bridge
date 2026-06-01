#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${HOME}/.local/share/ccb"

echo "=== CCB 同步到本地安装 ==="
echo "源目录: ${SCRIPT_DIR}"
echo "目标目录: ${TARGET_DIR}"

if [[ ! -d "${TARGET_DIR}" ]]; then
    echo "错误: 目标目录不存在: ${TARGET_DIR}"
    echo "请先安装 ccb（例如运行 install.sh）"
    exit 1
fi

# 清除旧的 Python 缓存，避免陈旧的 .pyc 文件问题
echo "正在清理目标目录中的 Python 缓存..."
find "${TARGET_DIR}" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find "${TARGET_DIR}" -name '*.pyc' -delete 2>/dev/null || true

# 同步核心代码目录和文件
# 排除：运行时数据、git、测试、文档、资源等
echo "正在同步代码..."
rsync -a --delete \
    --exclude='.ccb/' \
    --exclude='.git/' \
    --exclude='.claude/' \
    --exclude='.gemini/' \
    --exclude='.loop/' \
    --exclude='test/' \
    --exclude='tests/' \
    --exclude='assets/' \
    --exclude='docs/' \
    --exclude='plans/' \
    --exclude='.github/' \
    --exclude='archive/' \
    --exclude='*.pyc' \
    --exclude='__pycache__/' \
    --exclude='.DS_Store' \
    --exclude='sync-to-local.sh' \
    "${SCRIPT_DIR}/" "${TARGET_DIR}/"

echo ""
echo "=== 同步完成 ==="
echo "正在验证 CcbdLifecycleStore..."
if grep -q "class CcbdLifecycleStore" "${TARGET_DIR}/lib/ccbd/services/lifecycle.py"; then
    echo "成功: 在同步后的代码中找到了 CcbdLifecycleStore。"
else
    echo "错误: CcbdLifecycleStore 仍然缺失！"
    exit 1
fi

# 提示手动重启 ccb
CWD="$(pwd)"
if [[ -f "${CWD}/.ccb/ccb.config" ]]; then
    echo ""
    echo "检测到当前目录中有 ccb 项目: ${CWD}"
    echo "同步完成，请手动重启 ccb 以加载新代码:"
    echo "  ccb kill && ccb"
else
    echo ""
    echo "注意: 当前目录不是 ccb 项目（未找到 .ccb/ccb.config）。"
    echo "如果您有正在运行的 ccb 项目，请切换到该目录并运行:"
    echo "  ccb kill && ccb"
fi
