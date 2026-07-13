#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

_resolve_target() {
    if [[ -n "${CODEX_INSTALL_PREFIX:-}" ]]; then
        echo "${CODEX_INSTALL_PREFIX}"
        return
    fi
    if command -v ccb &>/dev/null; then
        local path
        path=$(ccb --version 2>/dev/null | grep '^Install path:' | head -1 | sed 's/^Install path: *//')
        if [[ -n "${path}" && -d "${path}" ]]; then
            echo "${path}"
            return
        fi
        local bin
        bin=$(command -v ccb)
        if [[ -L "${bin}" ]]; then
            path=$(dirname "$(readlink "${bin}")")
            if [[ -d "${path}" ]]; then
                echo "${path}"
                return
            fi
        fi
    fi
    echo "${HOME}/.local/share/ccb"
}

TARGET_DIR="$(_resolve_target)"

echo "=== CCB 同步到本地安装 ==="
echo "源目录: ${SCRIPT_DIR}"
echo "目标目录: ${TARGET_DIR}"

if [[ ! -d "${TARGET_DIR}" ]]; then
    echo "错误: 目标目录不存在: ${TARGET_DIR}"
    echo "请先安装 ccb（例如运行 install.sh）或设置 CODEX_INSTALL_PREFIX"
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

# 补同步 config UI 前端原型(excluded by --exclude='docs/')
_CONFIG_UI_SRC="${SCRIPT_DIR}/docs/plantree/plans/agentic-loop-workflow/prototypes/v2-static-config-panel-demo"
_CONFIG_UI_DST="${TARGET_DIR}/docs/plantree/plans/agentic-loop-workflow/prototypes/v2-static-config-panel-demo"
if [[ -f "${_CONFIG_UI_SRC}/index.html" ]]; then
    mkdir -p "${_CONFIG_UI_DST}"
    rsync -a "${_CONFIG_UI_SRC}/" "${_CONFIG_UI_DST}/"
fi

echo ""
echo "=== 同步完成 ==="
if [ -f "${TARGET_DIR}/lib/ccbd/services/lifecycle.py" ] && [ -f "${TARGET_DIR}/lib/agents/models_runtime/layout_runtime/parser.py" ]; then
    echo "验证通过: 核心模块存在。"
else
    echo "警告: 部分核心模块缺失，请检查同步结果。"
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
