#!/usr/bin/env bash
# switch-ccb-config — 切换 CCB 布局模式
# usage: bash .ccb/switch-config.sh [compact|multi]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="$SCRIPT_DIR/configs"
TARGET="$SCRIPT_DIR/ccb.config"

MODE="${1:-}"

if [[ -z "$MODE" ]]; then
  # 检测当前模式
  if grep -q '^version = 2' "$TARGET" 2>/dev/null; then
    CURRENT="multi-window"
  else
    CURRENT="compact"
  fi
  echo "当前: $CURRENT"
  echo "用法: bash .ccb/switch-config.sh [compact|multi]"
  exit 0
fi

case "$MODE" in
  compact)
    cp "$CONFIG_DIR/compact.config" "$TARGET"
    echo "✓ 已切换到 compact（单窗口）布局"
    echo "  运行 ccb reload 或重启 ccb 生效"
    ;;
  multi)
    cp "$CONFIG_DIR/multi-window.config" "$TARGET"
    echo "✓ 已切换到 multi-window（多窗口）布局"
    echo "  运行 ccb reload 或重启 ccb 生效"
    ;;
  *)
    echo "用法: bash .ccb/switch-config.sh [compact|multi]"
    exit 1
    ;;
esac
