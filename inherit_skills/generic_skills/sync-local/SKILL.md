---
name: sync-local
description: 将本地 ccb 源码同步到全局安装目录（~/.local/share/ccb），如果当前目录是 ccb 项目则自动重启运行时。
metadata:
  short-description: 同步 ccb 源码到全局安装
---

# 同步本地 CCB

将本地 ccb 源码同步到全局安装目录（`~/.local/share/ccb/`），并在适当时自动重启项目运行时。

## 背景

- ccb 源码目录的根目录下包含 `sync-to-local.sh` 脚本。
- 全局安装位置为 `~/.local/share/ccb/`。
- 同步完成后，必须重启正在运行的 `ccbd` 守护进程才能加载新的 Python 代码。
- 如果当前工作目录是 ccb 项目（包含 `.ccb/ccb.config`），`sync-to-local.sh` 会在同步后自动执行 `ccb kill && ccb` 重启。

## 用法

```text
/sync-local
```

## 执行（强制）

在 ccb 源码目录下运行同步脚本：

```bash
./sync-to-local.sh
```

如果当前目录没有该脚本，先定位到源码目录再执行：

```bash
CCB_SRC="/Users/zhangtao/Documents/study/claude_code_bridge-6"
cd "$CCB_SRC" && ./sync-to-local.sh
```

## 规则

- 仅在用户明确要求同步 ccb 源码到全局安装时使用此 skill。
- 不要手动运行 `ccb kill` 或 `ccb`；同步脚本在检测到 `.ccb/ccb.config` 时会自动处理重启。
- 如果脚本输出了备份路径，将其报告给用户。
- 如果脚本执行失败，报告错误输出并停止。

## 示例

- `/sync-local`
- `cd /path/to/claude_code_bridge-6 && ./sync-to-local.sh`
