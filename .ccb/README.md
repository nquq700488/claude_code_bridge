# CCB 项目脚本模板

本目录包含 `ccb` 的启动/停止/重启脚本，与项目配置一起作为模板使用。

## 使用

```bash
# 通过 .ccb/ 目录调用
./.ccb/start.sh       # 启动 ccb（已运行则提示）
./.ccb/stop.sh        # 停止 ccb
./.ccb/stop.sh -f     # 强制停止
./.ccb/restart.sh     # 重启 ccb
./.ccb/restart.sh -f  # 强制清理后重启
```

## 参数说明

| 脚本 | 参数 | 说明 |
|------|------|------|
| `start.sh` | `-s` / `--safe` | 安全模式启动 |
| `start.sh` | `-n` / `--new` | 重建后启动 |
| `stop.sh` | `-f` / `--force` | 强制清理后停止 |
| `restart.sh` | `-f` | 强制清理后重启 |
| `restart.sh` | `-s` | 安全模式重启 |
| `restart.sh` | `-n` | 重建后重启 |

## 前提条件

- 已全局安装 `ccb`
- 本项目已创建 `ccb.config`
