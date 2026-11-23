---
name: sync-local
description: 将本地 ccb 源码同步到全局安装目录（~/.local/share/ccb）；同步后需手动重启运行时，新代码才生效。
metadata:
  short-description: 同步 ccb 源码到全局安装
---

# 同步本地 CCB

将本地 ccb 源码同步到全局安装目录（`~/.local/share/ccb/`）；同步只更新文件，新代码要重启运行时才生效。

## 背景

- ccb 源码目录的根目录下包含 `sync-to-local.sh` 脚本。
- 全局安装位置为 `~/.local/share/ccb/`。
- 同步完成后，必须重启正在运行的 `ccbd` 守护进程才能加载新的 Python 代码。
- `sync-to-local.sh` **不会自动重启**：同步成功后它只打印 `请手动重启 ccb 以加载新代码: ccb kill && ccb` 提示，重启需要你自己执行。

## 用法

```text
/sync-local
```

## 执行（强制）

在 ccb 源码目录下运行同步脚本：

```bash
./sync-to-local.sh
```

如果当前目录没有该脚本，先定位到源码目录再执行（`CCB_SRC` 显式指定优先，否则从当前目录、git 根目录和常见位置自动查找）：

```bash
CCB_SRC="${CCB_SRC:-}"
if [[ -z "$CCB_SRC" ]]; then
  for d in "$PWD" "$(git rev-parse --show-toplevel 2>/dev/null)" \
           "$HOME"/Documents/study/claude_code_bridge* "$HOME"/code/claude_code_bridge*; do
    [[ -n "$d" && -x "$d/sync-to-local.sh" ]] && { CCB_SRC="$d"; break; }
  done
fi
[[ -n "$CCB_SRC" && -x "$CCB_SRC/sync-to-local.sh" ]] || { echo "找不到 ccb 源码目录，请设置 CCB_SRC" >&2; exit 1; }
cd "$CCB_SRC" && ./sync-to-local.sh
```

## 规则

- 仅在用户明确要求同步 ccb 源码到全局安装时使用此 skill。
- 同步成功后要**主动重启**才生效：在 ccb 项目目录下执行 `ccb kill && ccb`（脚本不会代劳）。当前目录不是 ccb 项目时，提示用户先切到项目目录再重启。
- 如果脚本输出了备份路径，将其报告给用户。
- 如果脚本执行失败，报告错误输出并停止。

## 示例

- `/sync-local`
- `cd /path/to/claude_code_bridge-6 && ./sync-to-local.sh`
