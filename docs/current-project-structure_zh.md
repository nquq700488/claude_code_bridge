# 当前项目结构

本文档记录 agent-first provider-backend 迁移清理后的当前仓库布局。

它是有意实用的：描述当前存在的内容、哪些目录是活跃运行时的一部分，以及最大的剩余结构性债务仍位于何处。

当前运行时权威是 `ccbd`。下面一些更深的历史章节在完整文档重写尚未落地时仍提及旧的 `askd` 命名；将它们视为迁移债务，而非当前权威。

## 运行时主干

当前 agent-first 运行时流经此链：

```text
ccb
  -> lib/cli/*
  -> lib/ccbd/*
  -> lib/provider_execution/*
  -> lib/completion/*
  -> lib/storage/* + lib/project/* + lib/workspace/*
```

根入口点现在有意保持精简：

- `ccb`
  兼容性外观加 CLI 移交
- `lib/launcher/app.py`
  面向窗格/session 的旧版表面的启动器兼容性组合根
- `lib/launcher/bootstrap/`
  启动器引导契约、生命周期适配器和服务连接
- `lib/launcher/bootstrap/builders/`
  用于核心/存储/启动器/运行组装的分组服务构造构建器
- `lib/launcher/app_deps.py`
  引导依赖绑定的兼容性包装器
- `lib/launcher/app_project.py`
  项目/配置/session 路径辅助函数
- `lib/launcher/app_runtime.py`
  兼容性启动器 shell 的窗格/session/运行时辅助 mixin
- `lib/launcher/app_facade.py`
  启动器外观 mixin 的兼容性包装器
- `lib/launcher/facade/`
  按 tmux/当前窗格/Claude 关注点分组的面向 provider 的外观辅助函数和 mixin
  目标面向外观包装器现在分组在
  `launcher/facade/targets_runtime/` 下；`targets.py` 保持稳定的
  重新导出表面
- `lib/launcher/commands/`
  按 provider 划分的特定 provider 启动命令和恢复/自动配置辅助函数
- `lib/launcher/commands/providers/`
  按 provider 划分的启动器命令构建器和恢复/配置检测
- `lib/launcher/commands/factory.py`
  启动器启动命令工厂实现；顶层 `start_commands.py` 保持仅兼容性
  Codex provider 内部现在分割在历史检测、自动批准配置和命令组装之间
  OpenCode provider 内部现在分割在恢复检测、本地配置变更和命令组装之间
- `lib/launcher/ops/`
  按 tmux/当前窗格/Claude 流分割的目标启动操作
- `lib/launcher/ops/current/`
  按 codex、类 shell 目标和路由器分派分割的当前窗格目标操作
- `lib/launcher/maintenance/`
  路径规范化、shell 命令构建器、运行时辅助函数和运行时清理
- `lib/launcher/maintenance/runtime/`
  运行时环境解析、git 元数据、临时清理、运行时 GC 和日志缩减辅助函数
- `lib/launcher/session/`
  启动器 session JSON I/O、注册表负载构建器和特定 provider session 元数据辅助函数
  目标 session 写入和注册表更新路径进一步分离，使存储类保持协调聚焦
- `lib/launcher/app_bootstrap.py`
  兼容性重新导出层

Provider 层分割为：

```text
lib/provider_core/*
lib/provider_backends/<provider>/*
lib/provider_backends/pane_log_support/*
```

含义：

- `provider_core` 持有共享的 provider 元数据、运行时规范和注册表契约
- `provider_backends` 拥有后端特定的 session、协议、通信和执行辅助函数
- `provider_backends/pane_log_support/` 持有共享的原始窗格日志读取器
  和不发出结构化 session 日志的类 shell provider 的通信器基础逻辑
- `provider_execution` 是 agent-first 流使用的面向运行时的执行层

## 目录角色

### 活跃运行时目录

- `lib/cli/`
  阶段 2 解析、渲染、上下文构造和非阶段 2
  命令路由
  阶段 2 回复/邮箱/操作渲染现在分组在
  `cli/render_runtime/` 下，使 `render.py` 保持为稳定的渲染外观
  而非另一个混合的输出格式化文件
  那里的邮箱/job/跟踪/确认渲染辅助函数现在也分组在
  `cli/render_runtime/mailbox_views_runtime/` 下，使
  `render_runtime/mailbox_views.py` 保持为稳定的邮箱渲染外观
  而非一个扁平的多视图格式化器
  阶段 2 命令分派、上下文引导、重置确认和
  处理程序路由现在分组在 `cli/phase2_runtime/` 下，使
  `phase2.py` 保持为稳定的入口外观和 monkeypatch 表面
  kill 命令僵尸清理、provider session 拆卸和守护进程
  终止辅助函数现在分组在 `cli/kill_runtime/` 下，使
  `cli/kill.py` 保持为稳定的命令外观和 monkeypatch
  表面
  阶段 2 项目 kill 关闭准备、pid 所有权清理和
  关闭报告组装现在也分组在
  `cli/services/kill_runtime/` 下，使 `services/kill.py` 保持为
  稳定的项目 kill 外观和 monkeypatch 表面
  项目 kill pid 候选收集、procfs 匹配和
  终止辅助函数现在也重用共享的
  `runtime_pid_cleanup/` 包，使 CLI 关闭不拥有项目 pid 生命周期逻辑的第二个副本
  tmux 项目窗格枚举、socket 感知孤儿清理和
  当前窗格最后 kill 排序现在也分组在
  `cli/services/tmux_project_cleanup_runtime/` 下，使
  `services/tmux_project_cleanup.py` 保持为稳定的清理外观和
  tmux 可用性/当前窗格测试的 monkeypatch 表面
  CLI 安装/更新/版本辅助函数现在分组在
  `cli/management_runtime/` 下，使 `cli/management.py` 保持为
  管理命令处理程序的稳定外观
  那里的远程标签获取、发布元数据传输和本地版本格式
  辅助函数现在进一步分组在
  `cli/management_runtime/versioning_runtime/` 下，使
  `versioning.py` 保持为稳定的版本查询外观，而非另一个扁平的网络/格式化文件
  阶段 2 命令解析现在分组在 `cli/parser_runtime/` 下，
  分离 ask/启动解析、共享 argparse 辅助函数、通用
  子命令解析器和故障解析，使 `cli/parser.py` 保持为稳定的
  阶段 2 外观
  启动时项目配置验证、provider 解析、锁复用、
  和选择辅助函数现在分组在 `cli/start_runtime/` 下，
  使 `cli/start.py` 保持为稳定的启动辅助外观
  守护进程启动就绪性、keeper 移交和关闭排序现在
  分组在 `cli/services/daemon_runtime/` 下，使
  `services/daemon.py` 保持为稳定的守护进程外观和 monkeypatch
  表面，用于启动/keeper 测试
  运行时启动器窗格创建/回退和 session 文件写入现在
  分组在 `cli/services/runtime_launch_runtime/` 下，使
  `services/runtime_launch.py` 聚焦于门检查、启动器
  选择和 monkeypatch 稳定的包装辅助函数
  那里的 tmux 绑定活跃度检查和陈旧窗格清理现在
  进一步分组在
  `cli/services/runtime_launch_runtime/binding_state_runtime/` 下，使
  `binding_state.py` 保持为稳定的绑定状态外观，而非一个
  混合的活跃度/清理辅助函数
  那里的运行时绑定活跃度和陈旧窗格清理现在也
  分组在包本地运行时模块中，因此公共的
  `runtime_launch.py` 表面保持测试/兼容注入点
  而不拥有完整的分支启动门逻辑
  异步等待轮询、quorum 策略和回复缩减现在也
  分组在 `cli/services/wait_runtime/` 下，使 `services/wait.py`
  保持为稳定的等待外观和 monkeypatch 表面
  provider session 绑定查找现在将
  `services/provider_binding.py` 视为共享的 `provider_core/session_binding_evidence.py` 适配器上的薄兼容性外观，而非 CLI 拥有的权威来源
- `lib/ccbd/`
  用于启动、监督、命名空间
  生命周期、分派器流和关闭/报告的项目范围控制面
  keeper 状态记录、关闭意图持久化和重启/退避
  辅助函数现在分组在 `ccbd/keeper_runtime/` 下，使
  `keeper.py` 聚焦于项目 keeper 循环和仍需要稳定 monkeypatch 表面的测试可见进程辅助函数
  生命周期报告模型族现在分组在
  `ccbd/models_runtime/lifecycle_runtime/` 下，分离清理摘要、
  运行时快照、启动报告和关闭报告模式，使
  `models_runtime/lifecycle.py` 保持为稳定的生命周期模型
  外观，而非单个记录堆
  ping 负载组装和摘要存储读取现在分组在
  `ccbd/handlers/ping_runtime/` 下，使 `handlers/ping.py` 保持为
  稳定的 ping 处理程序外观，而非混合 agent/守护进程负载
  塑造与存储读取
  每 agent 启动准备现在分组在
  `ccbd/start_preparation.py` 中，使 `start_flow.py` 聚焦于启动
  编排、布局应用、运行时附着和清理
  启动运行时细节现在分组在 `ccbd/start_runtime/` 下，
  分离 tmux 布局门控、provider 绑定可用性检查、
  cmd 窗格引导、每 agent 运行时附着和启动时孤儿
  清理与稳定的 `start_flow.py` 外观
  那里的项目命名空间绑定验证、socket 声明读取和
  窗格重新标签/启动提示现在进一步分组在
  `ccbd/start_runtime/binding_runtime/` 下，使
  `start_runtime/binding.py` 保持为稳定的绑定外观，而非
  另一个扁平的证据文件
  监督恢复、挂载和退避逻辑现在分组在
  `ccbd/supervision/*.py` 下，使 `supervision/loop.py` 保持为稳定
  的心跳/协调外观，而非一个扁平的状态机文件
  stop-all 关闭执行和 pid/tmux 清理现在分组在
  `ccbd/stop_flow.py` 中，使 `supervisor.py` 聚焦于编排
  和生命周期报告
  监督器命名空间移交、启动/停止编排和
  启动/关闭报告组装现在也分组在
  `ccbd/supervisor_runtime/` 下，使 `supervisor.py` 保持为稳定的
  编排外观和 monkeypatch 表面，用于启动流测试
  停止时运行时选择、pid 清理、tmux 孤儿清理和
  关闭快照辅助函数现在进一步分组在
  `ccbd/stop_flow_runtime/` 下，使 `stop_flow.py` 保持为稳定的
  关闭外观，而非另一个混合的拆卸文件
  那里的守护进程停止流 pid 候选收集、procfs 读取和
  终止辅助函数现在也重用共享的
  `runtime_pid_cleanup/` 包，使 ccbd 和 CLI 关闭路径消费
  一个项目 pid 所有权实现
  用于健康监督的 provider 窗格评估现在分组在
  `ccbd/services/health_assessment/` 下，使
  `services/health_runtime.py` 保持为稳定的评估外观；健康
  监控器编排、窗格状态路由和运行时更新辅助函数
  现在分组在 `ccbd/services/health_monitor_runtime/` 下，
  使 `services/health.py` 保持为稳定的健康监控器外观
  那里的降级状态字段更新、重新绑定写入和 provider 事实
  投影现在进一步分组在
  `ccbd/services/health_monitor_runtime/updates_runtime/` 下，因此
  健康监控器外观不再混合降级窗格状态保留
  与重新绑定/更新辅助细节
  分派器启动/恢复/队列 tick 辅助函数现在分组在
  `ccbd/services/dispatcher_runtime/lifecycle_start_runtime/` 下，使
  `dispatcher_runtime/lifecycle_start.py` 保持为稳定的分派器
  启动外观，而非另一个扁平的协调文件
  完成快照写入和终端决策/状态合并现在也
  分组在 `ccbd/services/dispatcher_runtime/completion_runtime/` 下，
  使 `dispatcher_runtime/completion.py` 保持为稳定的完成
  外观，而非另一个混合的状态合并文件
  分派器重试策略评估、超时检查通知和
  重试/不可重试失败回复塑造现在也分组在
  `ccbd/services/dispatcher_runtime/finalization_retry_runtime/` 下，
  使 `dispatcher_runtime/finalization_retry.py` 保持为稳定的
  重试/回复外观
  回复交付声明、头部重写、负载格式化和终端
  重新排队/消费流现在也分组在
  `ccbd/services/dispatcher_runtime/reply_delivery_runtime/` 下，使
  `dispatcher_runtime/reply_delivery.py` 保持为稳定的回复交付
  外观，而非另一个混合的邮箱/负载文件
  运行时附着、恢复/就绪性和 provider 绑定刷新流
  现在分组在 `ccbd/services/runtime_runtime/` 下，使
  `services/runtime.py` 保持为稳定的服务外观，而非一个混合的
  生命周期/状态更新文件
  用于健康评估的 tmux 特定窗格后端/所有权/命名空间检查现在也
  分组在
  `ccbd/services/health_assessment/tmux_runtime/` 下，使
  `health_assessment/tmux.py` 保持为稳定的 tmux 评估外观
  项目命名空间 tmux 后端生命周期、状态/事件记录塑造、
  和确保/销毁流现在也分组在
  `ccbd/services/project_namespace_runtime/` 下，使
  `services/project_namespace.py` 保持为稳定的命名空间控制器
  外观
- `lib/askd/`
  项目范围的 ask 守护进程应用、socket 服务器/客户端、处理程序、挂载
  状态和恢复路径
  `askd.client` 现在主要是 `askd/client_runtime/` 上的旧版外观；provider 包装器主路径已移至
  原生 askd socket job，剩余的外观使用被隔离到
  待退役的兼容/诊断表面
  `askd.server` 现在是 `askd/server_runtime/` 上的包外观
  环境、处理程序、状态写入、服务器引导和生命周期
  监控器模块
  独立的 askd 工作器路由、请求处理和运行时
  状态清理现在位于 `askd/daemon_runtime/` 下，使
  `askd/daemon.py` 保持为独立的 askd 入口外观
  分派器协调内部现在分组在
  `askd/services/dispatcher_runtime/` 下，使 `services/dispatcher.py`
  保持聚焦于提交/tick/完成编排；轮询、恢复
  重播、观察目标路由和完成状态辅助函数现在存在于
  那里的包本地运行时模块中
  提交/tick 生命周期编排和取消终端化辅助函数
  现在进一步分离到专用的 `dispatcher_runtime/`
  模块中，减少 `services/dispatcher.py` 为分派器外观
  和共享存储/运行时辅助函数
  Claude 适配器回复塑造和等待/最终化辅助函数现在分组
  在 `askd/adapters/claude_runtime/` 下，使
  `askd/adapters/claude.py` 保持为面向 provider 的编排外观
  那里的 Claude 回复后处理现在进一步分离为意图
  检测、表规范化和格式修复模块，使
  `claude_runtime/reply_postprocess.py` 保持为编排
  外观，而非单个规则堆
  Codex 和 Gemini ask 守护进程等待/最终化流现在也分组
  在 `askd/adapters/codex_runtime/` 和
  `askd/adapters/gemini_runtime/` 下，使它们的适配器模块聚焦于
  session/后端连接
  OpenCode 和 Droid ask 守护进程等待/最终化流现在也分组
  在 `askd/adapters/opencode_runtime/` 和
  `askd/adapters/droid_runtime/` 下，使它们的适配器模块聚焦于
  session/后端连接
  CodeBuddy、Qwen 和 Copilot ask 守护进程等待/最终化流现在也
  分组在 `askd/adapters/codebuddy_runtime/`、
  `askd/adapters/qwen_runtime/` 和 `askd/adapters/copilot_runtime/` 下，
  使它们的适配器模块聚焦于 session/后端连接
  那里的 Codex ask 守护进程等待循环、回复清理和完成钩子通知
  辅助函数现在进一步拆分为专用的任务运行时
  辅助模块，使 `codex_runtime/task_runtime.py` 保持为稳定的
  导入外观，而非另一个扁平的循环堆
  ask 守护进程 RPC/数据类负载族现在位于
  `askd/api_models_runtime/` 下，使 `askd/api_models.py` 保持为稳定的
  导入外观，而非单个记录堆
  ask 守护进程租约和恢复报告数据类现在也位于
  `askd/models_runtime/` 下，使 `askd/models.py` 保持为稳定的模式
  外观
  `lib/ask_cli/` 现在仅为别名：`ask_cli.main` 将 `ask` 转发到
  规范的 `ccb ask` 阶段 2 路径，编程调用者不再
  使用单独的 `ask_cli.runtime` 辅助层
  遗留顶层 `askd_client.py`、`askd_runtime.py` 和
  `askd_server.py` 现在保持仅作为兼容性垫片
- `lib/agents/`
  agent 配置模式、运行时状态记录、恢复检查点、
  策略默认值和持久化存储
  `agents.models` 现在是 `agents/models_runtime/` 上的稳定外观，
  名称规范化、枚举、配置数据类和运行时
  数据类分离到包本地模块中
  那里的 agent 规范规范化和项目布局验证现在也
  进一步分组在 `agents/models_runtime/config_runtime/` 下，使
  `models_runtime/config.py` 保持为稳定的配置外观，而非一个
  重度验证的数据类文件
  `agents.config_loader` 现在是 `agents/config_loader_runtime/` 上的稳定外观，
  紧凑配置加载、验证、
  默认模板渲染和配置路径辅助函数分离到
  专用模块中
  那里的配置语法验证和引导/残留恢复现在也
  进一步分组在 `agents/config_loader_runtime/parsing_runtime/`
  和 `agents/config_loader_runtime/io_runtime/` 下，使
  `parsing.py` 和 `io.py` 保持为稳定的加载器外观，而非混合的
  文档/引导模块
- `lib/memory/`
  session 解析、去重、传输编排和传输上下文
  格式化
  那里的格式化辅助函数现在分组在
  `memory/formatter_runtime/` 下，分离 provider 标签/时间戳
  辅助函数、工具/统计渲染和格式特定的输出组装，使
  `formatter.py` 保持为稳定的格式化器外观
  那里的格式化工具输入塑造、工具执行渲染和统计
  块组装现在也分组在
  `memory/formatter_runtime/tools_runtime/` 下，使 `tools.py` 保持为
  稳定的工具格式化外观，而非另一个混合的辅助文件
  那里的 session 统计提取现在也分组在
  `memory/session_parser_runtime/stats_runtime/` 下，分离 session 文件
  迭代与工具/文件/任务聚合，使 `stats.py` 保持为
  稳定的统计外观，而非另一个混合的解析文件
- `lib/mail/`
  邮件入口、路由、轮询、发送和 ask 桥集成
  邮件 ask 提交/上下文辅助函数现在分组在
  `mail/ask_runtime/` 下，使 `mail/ask_handler.py` 聚焦于
  消息规范化和编排，而非混合上下文
  持久化、环境组装和 ask 提交细节
- `lib/mailbox_kernel/`
  每 agent 交付的邮箱事件、租约和邮箱状态协调
  事件查询、声明/确认转换和邮箱刷新投影
  现在分组在 `mailbox_kernel/service_runtime/` 下，使
  `service.py` 保持为稳定的邮箱内核外观，而非一个混合的
  状态机/投影文件
- `lib/message_bureau/`
  管理局控制/报告视图、队列检查、回复和跟踪
  组装
  队列/收件箱/确认视图辅助函数现在分组在
  `message_bureau/control_queue_runtime/` 下，分离邮箱目标
  解析、待处理事件塑造、摘要视图和确认完成
  使 `control_queue.py` 保持为稳定的外观
- `lib/provider_execution/`
  执行注册表、provider 适配器、状态持久化和恢复
  编排
  执行服务重播/持久化/恢复流现在位于
  `provider_execution/service_runtime/` 下，使 `service.py` 保持为
  稳定的协调外观，而非完整的状态机主体
  共享的活跃运行时启动/轮询/恢复守卫现在位于
  `provider_execution/active_runtime/` 下，使 `active.py` 保持为
  稳定的外观，而启动准备、轮询守卫、窗格活跃度
  检查和恢复连接保持在共享执行内部
  契约
  假 provider 指令解析、默认脚本生成和
  负载/终端决策辅助函数现在位于
  `provider_execution/fake_runtime/` 下，使 `fake.py` 保持为稳定的
  适配器外观，用于执行服务测试和 provider 注册表
  连接
  共享项构建、运行时状态序列化、路径/session
  偏好和窗格目标终端辅助函数现在也位于
  `provider_execution/common_runtime/` 下，使 `common.py` 保持为
  稳定的共享辅助外观，而非累积不相关的实用
  契约
- `lib/provider_hooks/`
  provider 完成钩子命令构建和工作区设置/信任
  安装
  provider 钩子环境合并、每 provider 命令安装和信任
  写入器现在位于 `provider_hooks/settings_runtime/` 下，使
  `settings.py` 保持为稳定的钩子设置外观，而非一个混合的
  JSON/环境变更文件
- `lib/provider_sessions/`
  共享项目 session 路径查找、可写检查和原子
  session 文件写入
  路径解析、绑定感知 session 发现、可写状态
  验证和安全写入辅助函数现在分组在
  `provider_sessions/files_runtime/` 下，使 `files.py` 保持为稳定的
  session 文件外观
- `lib/provider_core/`
  共享 provider 清单、注册表面、路径/session 命名和
  兼容性胶水
  内置后端组装和假 provider 后端组装现在位于
  `provider_core/registry_runtime/` 下，使 `registry.py`
  聚焦于公共注册表面和默认构建器入口点
  provider session 证据提取和窗格所有权支持的绑定
  事实现在也位于 `provider_core/session_binding_evidence.py` 下
  因此 `ccbd` 启动/健康和 CLI 兼容性表面消费
  相同的适配器，而非分别解释 provider session 文件
  provider session 字段提取、窗格状态检查、根/session
  加载和可用绑定验证现在也进一步分组在
  `provider_core/session_binding_evidence_runtime/` 下，使
  `session_binding_evidence.py` 保持为稳定的共享证据外观
  tmux session 身份提取、标题解析、所有权
  检查和失配文本渲染现在也分组在
  `provider_core/tmux_ownership_runtime/` 下，使
  `tmux_ownership.py` 保持为稳定的窗格所有权外观
- `lib/provider_backends/`
  codex、claude、gemini、opencode、
  droid、codebuddy、copilot 和 qwen 的后端自有实现
  Codex 日志绑定和 JSONL 解析支持现在分组在
  `provider_backends/codex/comm_runtime/` 下；session 发现、tmux
  健康检查、通信器 session 状态/发送流、绑定
  持久化、JSONL 解析、增量日志读取器轮询和
  看门狗回调处理现在位于那里，使 `codex/comm.py` 被
  缩减为面向 provider 的外观和稳定的 monkeypatch 表面；
  `CodexCommunicator` 和 `CodexLogReader` 类体现在也位于
  那里的运行时本地外观模块中
  那里的 Codex 通信器内部现在进一步分离为
  session 状态、终端健康和发送/等待模块，使
  `comm_runtime/communicator.py` 保持为稳定的导入外观
  Codex 读取器内部现在在那里进一步分离为调试
  辅助函数、日志路径/工作目录选择、状态快照、尾部内容
  读取和增量轮询模块，使 `comm_runtime/log_reader.py`
  保持为薄的导入表面，而非另一个巨石
  Codex 日志条目规范化和助手/用户消息提取
  现在也分组在 `comm_runtime/log_entries_runtime/` 下，
  使 `log_entries.py` 保持为稳定的解析外观，而非
  混合条目强制与消息塑造
  那里的 Codex 轮询读取循环状态现在也分组在
  `comm_runtime/polling_runtime/` 下，分离读取游标状态、
  行解码/匹配提取和日志切换处理，使
  `polling.py` 保持为稳定的外观
  Codex 活跃执行启动/恢复连接和协议轮询逻辑
  现在分组在 `provider_backends/codex/execution_runtime/` 下，
  使 `codex/execution.py` 保持为适配器外观和稳定的
  monkeypatch 表面，用于执行测试
  Codex provider 启动运行时准备、恢复 session 查找、
  home/配置文件隔离和桥接生成辅助函数现在也位于
  `provider_backends/codex/launcher_runtime/` 下，使
  `codex/launcher.py` 保持为稳定的启动器外观，而非另一个
  provider 特定的协调文件
  那里的 Codex 执行轮询现在进一步分离为条目
  读取、回复选择辅助函数和轮询状态转换模块，使
  `execution_runtime/polling.py` 保持为编排外观
  Codex 执行轮询状态处理现在也分组在
  `provider_backends/codex/execution_runtime/state_machine_runtime/` 下，分离轮询状态、
  绑定更新、用户/助手/终端条目处理和
  最终化，使 `state_machine.py` 保持为稳定的外观
  那里的 Codex 项目 session 绑定更新现在也分组在
  `comm_runtime/binding_update_runtime/` 下，分离项目 session
  变更、旧绑定传输、注册表发布和持久化
  使 `binding_update.py` 保持为稳定的外观，而非另一个
  混合的运行时文件
  Codex 桥接环境/session 辅助函数、绑定追踪器刷新和桥接
  服务生命周期现在也分组在
  `provider_backends/codex/bridge_runtime/` 下，使 `codex/bridge.py`
  保持为稳定的桥接外观，用于运行时入口点和测试
  Codex 工作区 session 尾部扫描和最新日志选择现在也
  分组在 `comm_runtime/session_selection_runtime/` 下，
  分离反向尾部读取、工作区 session 跟随状态和
  扫描策略，使 `session_selection.py` 保持为稳定的外观
  Codex 项目 session 文件查找、窗格自愈和日志绑定
  持久化现在也位于
  `provider_backends/codex/session_runtime/` 下，使 `codex/session.py`
  保持为稳定的 session 外观
  Codex 恢复命令解析、命令重写和持久化
  启动命令字段选择现在也分组在
  `provider_backends/codex/start_cmd_runtime/` 下，使
  `codex/start_cmd.py` 保持为稳定的恢复命令外观
  Gemini 项目哈希检测、session 选择、JSON session 文件
  读取、增量轮询和看门狗更新支持现在
  分组在 `provider_backends/gemini/comm_runtime/` 下，使
  `gemini/comm.py` 保持为面向 provider 的外观和稳定的 monkeypatch
  表面；`GeminiCommunicator` 和 `GeminiLogReader` 类体现在
  也位于那里的运行时本地外观模块中，而通信器
  生命周期、健康检查、session 绑定更新和发送/等待
  编排保留在该运行时包中
  那里的 Gemini 通信器内部现在进一步分组在
  `comm_runtime/communicator_runtime/` 下，分离通信器状态、
  绑定发布、健康检查和 ask/消费流，使
  `comm_runtime/communicator.py` 保持为稳定的导入外观
  那里的 Gemini 项目 session 绑定更新现在也分组
  在 `comm_runtime/binding_update_runtime/` 下，分离
  项目 session 变更、旧绑定传输、注册表发布、
  和持久化，使 `binding_update.py` 保持为稳定的外观
  Gemini 读取器内部现在在那里进一步分离为调试、
  状态初始化、session 选择、session 内容读取和
  轮询模块，使 `comm_runtime/log_reader.py` 保持为薄的导入
  表面，使 `gemini/comm.py` 不再承载完整的读取器主体
  那里的 Gemini 项目哈希规范化、候选派生、注册表
  工作目录查找和 session id 读取现在也分组
  在 `comm_runtime/project_hash_runtime/` 下，使
  `project_hash.py` 保持为稳定的外观，而非另一个混合的路径
  和文件系统辅助文件
  Gemini session 选择现在也分组在
  `comm_runtime/session_selection_runtime/` 下，分离项目范围
  检查、首选 session 采用和扫描策略，使
  `session_selection.py` 保持为稳定的外观
  Gemini 轮询现在进一步在回复轮询和
  回复变更检测辅助函数之间分割，使 `comm_runtime/polling.py` 保持为
  稳定的外观
  Gemini 轮询读取循环状态现在也分组在
  `comm_runtime/polling_loop_runtime/` 下，分离循环游标状态、
  超时处理和主读取编排，使 `polling_loop.py`
  保持为稳定的外观
  Gemini 活跃执行启动/恢复连接、就绪状态等待、
  钩子产物偏好和快照轮询现在位于
  `provider_backends/gemini/execution_runtime/` 下，使
  `gemini/execution.py` 保持为适配器外观和稳定的 monkeypatch
  表面，用于执行测试
  Gemini 执行轮询现在也分组在
  `provider_backends/gemini/execution_runtime/polling_runtime/` 下，
  分离钩子产物读取、回复清理和快照轮询
  编排，使 `execution_runtime/polling.py` 保持为稳定的外观
  和钩子注入表面
  Gemini 项目 session 文件查找、窗格恢复和 session 绑定
  持久化现在也位于
  `provider_backends/gemini/session_runtime/` 下，使
  `gemini/session.py` 保持为稳定的 session 外观
  Claude 项目 session 选择、JSONL 读取器轮询、子 agent 日志
  处理、日志条目解析和 session/注册表绑定支持现在
  分组在 `provider_backends/claude/comm_runtime/` 下，而
  `claude/comm.py` 被缩减为稳定的顶层外观和
  `ClaudeCommunicator`/`ClaudeLogReader` 类体现在位于
  那里的运行时本地外观模块中；共享路径选择辅助函数保留
  在 `claude/registry_support/` 下
  Claude 读取器内部现在在那里进一步分离为 session
  选择、增量 JSONL I/O、对话提取、子 agent
  日志处理和轮询模块，使 `comm_runtime/log_reader.py`
  保持为薄的导入表面，而非一个巨石
  Claude 轮询读取循环现在也分组在
  `comm_runtime/polling_runtime/` 下，分离 session 等待循环与
  增量条目/事件/消息塑造，使 `polling.py` 保持为
  稳定的读取器外观
  Claude 通信器内部现在也分组在
  `comm_runtime/communicator_runtime/` 下，分离 session 状态设置、
  日志读取器绑定、注册表发布和 ask/ping 流，使
  `communicator.py` 保持为稳定的导入外观
  Claude session 选择现在进一步分组在
  `comm_runtime/session_selection_runtime/` 下，分离读取器设置、
  项目成员身份、session 索引解析和扫描回退，使
  `session_selection.py` 保持为稳定的外观
  Claude 结构化条目/内容解析现在也分组
  在 `comm_runtime/parsing_runtime/` 下，分离内容文本
  提取、条目类型消息提取和结构化事件
  塑造，使 `parsing.py` 保持为稳定的外观
  Claude 活跃执行启动/轮询/恢复辅助函数现在分组
  在 `provider_backends/claude/execution_runtime/` 下，使
  `claude/execution.py` 保持为面向适配器的外观和稳定的
  monkeypatch 表面，用于执行测试
  Claude 执行轮询状态更新现在进一步分组
  在 `execution_runtime/state_machine_runtime/` 下，分离轮询
  状态、助手/系统事件处理和最终化，使
  `state_machine.py` 保持为稳定的外观
  Claude session 解析现在位于
  `provider_backends/claude/resolver_runtime/` 下，分割注册表
  记录扩展、项目路径查找和最终回退选择，使
  `claude/resolver.py` 保持为稳定的外观
  Claude 项目 session 模型、加载/回退选择和键
  派生现在也位于 `provider_backends/claude/session_runtime/` 下，
  使 `claude/session.py` 保持为稳定的 session 外观，而非
  混合模型方法与实例范围加载和解析器回退
  Claude session 注册表状态、直接 session 文件更新辅助函数和
  日志/session 索引监视器回调现在分组在
  `provider_backends/claude/registry_runtime/` 下，使
  `claude/registry.py` 保持为稳定的外观，而注册表设置、
  askd 日志桥接、单例访问和监控器编排现在
  从那里的运行时实现模块中分离；
  session 缓存重新加载逻辑、监控器循环检查和监视器生命周期
  管理现在分离到那里的专用运行时模块中
  Claude 注册表事件处理现在也分组在
  `registry_runtime/events_runtime/` 下，分离全局日志发现、
  项目监视器日志处理和 session 索引应用，使
  `events.py` 保持为稳定的事件外观
  Claude 注册表监控器生命周期、session 刷新扫描和
  每 session 绑定刷新检查现在也分组在
  `registry_runtime/monitoring_runtime/` 下，使 `monitoring.py` 保持为
  稳定的监控器外观，而非另一个混合的循环/检查文件
  Claude 注册表日志发现辅助函数现在进一步分组在
  `provider_backends/claude/registry_support/logs_runtime/` 下，分离
  环境解析、session 索引读取、日志元数据读取、绑定刷新
  策略和日志发现，使 `registry_support/logs.py` 保持为
  稳定的外观
  Claude 注册表项目路径候选枚举和路径
  规范化现在也分组在
  `provider_backends/claude/registry_support/pathing_runtime/` 下，使
  `registry_support/pathing.py` 保持为共享路径的稳定外观
  辅助函数，而非将候选选择、路径匹配和
  session 工作目录修复混合在一个文件中
  OpenCode session 文件/运行时连接和读取器支持辅助函数现在
  位于 `provider_backends/opencode/runtime/` 下，使
  `opencode/comm.py` 更聚焦于通信器编排，而
  存储支持的 session 选择、消息/部件读取、轮询和
  取消检测辅助函数位于该运行时包中
  OpenCode 存储读取器内部现在在那里进一步分离为
  session 查找、消息/部件读取器和增量状态捕获
  模块，使 `runtime/storage_reader.py` 保持为稳定的外观，而非
  直接累积所有存储关注点
  OpenCode 轮询现在进一步在回复轮询、
  对话视图和取消跟踪之间分割，使 `runtime/polling.py`
  保持为稳定的外观，而非直接持有所有实时读取行为
  OpenCode 取消跟踪现在也分组在
  `runtime/cancel_tracking_runtime/` 下，分离已中止助手
  匹配与日志游标监控，使 `cancel_tracking.py` 保持为
  稳定的外观，而非另一个混合的实时状态文件
  OpenCode 通信器初始化、健康检查和发送/等待
  流现在也位于那里，使 `opencode/comm.py` 保持为稳定的
  外观，暴露 `OpenCodeLogReader` 和 `OpenCodeCommunicator`
  OpenCode 活跃执行启动/轮询连接现在也位于
  `provider_backends/opencode/execution_runtime/` 下，使
  `opencode/execution.py` 保持为稳定的适配器外观，而
  启动流设置、状态/session 辅助函数和轮询保持分离在
  运行时本地模块中
  OpenCode 项目 session 查找、窗格恢复和存储绑定
  持久化现在也位于
  `provider_backends/opencode/session_runtime/` 下，使
  `opencode/session.py` 保持为稳定的 session 外观
  Droid 日志解析、session 发现和绑定/注册表支持现在
  位于 `provider_backends/droid/comm_runtime/` 下，使
  `droid/comm.py` 更聚焦于读取器和通信器编排
  Droid session 扫描/增量 JSONL 读取现在位于
  `provider_backends/droid/comm_runtime/log_reader.py` 下，而看门狗
  启动和 session 绑定回调位于
  `provider_backends/droid/comm_runtime/watchdog.py` 下
  Droid 读取器内部现在在那里进一步分离为 session
  选择、内容提取和增量轮询模块，使
  `comm_runtime/log_reader.py` 保持为稳定的读取器外观，而非
  直接持有所有读取器行为
  Droid 解析辅助函数现在也分组在
  `comm_runtime/parsing_runtime/` 下，分离路径匹配、
  session 启动读取和消息内容提取，使 `parsing.py`
  保持为稳定的外观
  Droid 活跃执行启动/轮询连接现在也位于
  `provider_backends/droid/execution_runtime/` 下，使
  `droid/execution.py` 保持为稳定的适配器外观，而启动流
  设置、状态/session 辅助函数和轮询保持分离在
  运行时本地模块中
  Droid session id/首选 session 状态和最新 session 选择
  现在也位于 `provider_backends/droid/comm_runtime/session_selection_runtime/` 下，
  使 `session_selection.py` 保持为稳定的选择外观
  那里的 Droid session 选择辅助函数现在进一步拆分为
  显式 id 查找、候选扫描和最终选择模块，使
  `session_selection_runtime/lookup.py` 不再累积选择流水线的
  每个分支
  Droid 轮询读取循环和增量条目/事件/消息塑造
  现在也分组在
  `provider_backends/droid/comm_runtime/polling_runtime/` 下，使
  `polling.py` 保持为稳定的读取器外观
  Droid 项目 session 查找、窗格恢复和绑定持久化
  现在也位于 `provider_backends/droid/session_runtime/` 下，
  使 `droid/session.py` 保持为稳定的 session 外观
  Qwen、Copilot 和 CodeBuddy 窗格日志解析和 session 通信器
  机制现在整合在
  `provider_backends/pane_log_support/` 下，使每个 provider 的
  `comm.py` 成为共享窗格日志支持层上的薄 provider 命名外观
- `lib/completion/`
  完成检测器、来源、选择器和编排
  共享枚举、数据类记录和完成实用辅助函数现在
  分组在 `completion/models_runtime/` 下，使
  `completion/models.py` 保持为运行时其余部分的稳定导入外观
  那里的完成记录数据类现在进一步分组在
  `completion/models_runtime/records_runtime/` 下，使
  `models_runtime/records.py` 保持为稳定的重新导出外观，而非
  单个扁平的数据类堆
- `lib/terminal_runtime/`
  v2 路径使用的面向窗格的 tmux 运行时辅助函数
  `terminal.py` 保持 monkeypatch 稳定的外观，而后端
  选择和布局连接现在位于 `terminal_facade/` 下
  tmux 后端编排现在进一步分组在
  `terminal_runtime/tmux_backend_runtime/` 下，分离服务构建器
  和窗格/session 动作，使 `tmux_backend.py` 保持为稳定的
  后端外观，而非单个广泛的协调文件
  tmux 窗格查找、窗格元数据读取和窗格变更辅助函数现在
  也分组在 `terminal_runtime/tmux_panes_runtime/` 下，使
  `tmux_panes.py` 保持为稳定的窗格服务外观，而非另一个
  混合的查询/动作文件
  窗格日志根/路径选择、修剪策略和陈旧日志清理现在
  也分组在 `terminal_runtime/pane_logs_runtime/` 下，使
  `pane_logs.py` 保持为稳定的窗格日志外观，而非混合路径
  策略与修剪/清理细节
- `lib/runtime_pid_cleanup/`
  共享项目拥有的 pid 收集、procfs 证据读取、路径
  所有权匹配、pid 文件清理和终止辅助函数，由
  CLI kill 和 ccbd 停止流运行时路径使用
- `lib/storage/`、`lib/project/`、`lib/workspace/`
  项目发现、路径布局、存储和工作区隔离
- `lib/opencode_runtime/`
  OpenCode 存储/日志根、session 监视、回复提取和
  SQLite 支持的 session 辅助函数
  那里的路径/项目 id 辅助函数现在分组在
  `opencode_runtime/paths_runtime/` 下，使 `paths.py` 保持为稳定的
  外观，用于项目 id、路径匹配和默认根导出
- `lib/memory/`
  上下文传输解析、去重、格式化和跨 provider
  session 重播辅助函数
  Claude session 解析、JSONL 条目解析和 session 统计
  提取现在分组在 `memory/session_parser_runtime/` 下，
  使 `memory/session_parser.py` 保持为解析器外观
  特定 provider 的传输提取和保存/发送辅助函数现在位于
  `memory/transfer_runtime/` 下，使 `memory/transfer.py` 保持为
  编排外观
  自动传输匹配、状态捕获、工作器执行和保存/发送
  服务协调现在也进一步分组在
  `memory/transfer_runtime/auto_transfer_runtime/` 下，使
  `transfer_runtime/auto_transfer.py` 保持为稳定的自动传输外观
  而非单个混合的重播文件
  那里的特定 provider 传输提取器现在进一步分组
  在 `memory/transfer_runtime/providers_runtime/` 下，使
  `transfer_runtime/providers.py` 保持为稳定的提取器外观，而非
  一个扁平的多 provider 分支文件
- `lib/pane_registry_runtime/`
  用于 provider 窗格/session 发现的注册表查找/写入辅助函数；
  顶层 `pane_registry.py` 保持仅兼容性
  那里的注册表文件 IO、调试输出、路径匹配和 provider 条目
  活跃度现在分组在
  `pane_registry_runtime/common_runtime/` 下，使 `common.py` 保持为
  稳定的注册表辅助外观，而非一个混合的分支繁重的辅助
- `lib/web/`
  FastAPI 仪表板/运行时辅助函数现在显式绑定到一个解析的
  项目根，而非假设全局守护进程上下文
  特定路由的守护进程/provider 状态逻辑现在分组在
  `web/route_support/` 下，使路由模块保持 API 导向
  邮件路由模式、钩子/服务辅助函数和守护进程控制辅助函数
  现在分组在 `web/route_support/mail/` 下，使
  `web/routes/mail.py` 保持为仅路由外观

### 仍共存但不属于纯净核心

- `claude_skills/`、`codex_skills/`、`droid_skills/`
  特定 provider 的 prompt/技能资源
- `bin/`
  旧版 provider 包装器加当前辅助脚本
- `mcp/ccb-delegation/`
  stdio MCP 兼容性服务器；模式、工具调用处理和
  JSON-RPC 协议辅助函数现在拆分为本地运行时辅助
  模块，使 `server.py` 保持为入口外观

## 当前文件系统读取

仓库比以前实质更干净，但仍有三个明显的
形态问题：

1. 根目录混合运行时代码、provider 脚本、prompt
   资源、长期设计文档和生成的分析产物。
2. 活跃运行时是模块化的，但启动器引导和终端
   编排与其余运行时相比仍然密集。
3. 测试广泛且有价值，但黑盒覆盖率集中在
   单个巨型文件中：`test/test_v2_phase2_entrypoint.py`。

## 静态热点

缓存的 `.architec` 输出现在报告一个仍然较弱但结构上
更干净的基线：

- 总体分数：`45.04`
- 治理总体：`29.38`
- 结构：`60.70`
- 最大债务维度：`cyclomatic_complexity`、`governance`、`wide_component`

顶级缓存热点：

1. `lib/ccbd/client_runtime/resolution.py`
2. `lib/ccbd/runtime.py`
3. `lib/ccbd/services/dispatcher_runtime/lifecycle_start_runtime/recovery.py`
4. `lib/ccbd/services/dispatcher_runtime/restore.py`
5. `lib/ccbd/services/runtime_runtime/restore.py`

最新热点轮次淘汰了 `lib/ccbd/keeper.py`、
`lib/agents/config_loader_runtime/io.py`、
`lib/provider_backends/claude/registry_support/pathing.py`、
`lib/provider_backends/claude/session.py` 和
`lib/pane_registry_runtime/common.py`，使其不再出现在当前前五列表中。
此时剩余的拖累集中在活跃的 `ccbd`
分支路径中，而非缺失的包边界。

## 最大的剩余结构性债务

基于当前树和本地扫描，下一个清理优先级是：

1. 收敛
   `lib/provider_backends/*/execution.py` 中重复的执行/运行时语义，特别是在 provider
   仍在共享执行契约周围复制钩子排序、恢复决策和活跃 session
   守卫的地方；其中大部分现在
   移入 provider 本地 `execution_runtime/` 包中，但
   剩余的重复应在重新累积前被关注。
2. 在新的循环复杂度热点重新累积
   分支债务之前重构它们，特别是
   `lib/ccbd/client_runtime/resolution.py`、
   `lib/ccbd/runtime.py`、
   `lib/ccbd/services/dispatcher_runtime/lifecycle_start_runtime/recovery.py`、
   `lib/ccbd/services/dispatcher_runtime/restore.py` 和
   `lib/ccbd/services/runtime_runtime/restore.py`。
3. 保持剩余的 large provider/运行时模块受控，使
   新的编排工作不再重新创建另一个扁平阻塞点，
   特别是在 `lib/terminal_runtime/tmux_backend.py`、
   `lib/opencode_runtime/paths_runtime/` 和终端管理下创建的任何新运行时本地
   包中。
4. 关注新的 `agents/config_loader_runtime/`、
   `agents/config_loader_runtime/io_runtime/`、
   `agents/config_loader_runtime/parsing_runtime/`、
   `ccbd/keeper_runtime/`、`cli/services/daemon_runtime/`、
   `pane_registry_runtime/common_runtime/`、
   `provider_backends/claude/session_runtime/`、
   `provider_backends/claude/registry_support/pathing_runtime/`、
   `askd/services/dispatcher_runtime/` 和
   `completion/models_runtime/records_runtime/` 包的
   二阶热点；同样的关注现在也适用于
   `cli/kill_runtime/`、`cli/services/kill_runtime/`、
   `askd/models_runtime/`、`askd/adapters/codex_runtime/`、
   `provider_execution/active_runtime/`、
   `terminal_runtime/tmux_backend_runtime/`、
   `terminal_runtime/tmux_panes_runtime/`、
   `provider_backends/codex/comm_runtime/binding_update_runtime/`、
   `provider_backends/codex/comm_runtime/polling_runtime/`、
   `provider_backends/codex/execution_runtime/state_machine_runtime/`、
   `provider_backends/claude/registry_runtime/`、
   `provider_backends/claude/registry_runtime/events_runtime/`、
   `provider_backends/claude/registry_support/logs_runtime/`、
   `provider_backends/claude/comm_runtime/communicator_runtime/`、
   `provider_backends/claude/comm_runtime/parsing_runtime/`、
   `provider_backends/claude/comm_runtime/session_selection_runtime/`、
   `provider_backends/claude/execution_runtime/state_machine_runtime/`、
   `provider_backends/gemini/comm_runtime/binding_update_runtime/`、
   `provider_backends/gemini/comm_runtime/communicator_runtime/`、
   `provider_backends/gemini/comm_runtime/session_selection_runtime/`、
   和 `provider_backends/gemini/comm_runtime/polling_loop_runtime/`、
   `provider_backends/droid/comm_runtime/parsing_runtime/`、
   `provider_backends/opencode/runtime/cancel_tracking_runtime/`、
   `provider_backends/droid/execution_runtime/`、
   `provider_backends/opencode/execution_runtime/`、
   `opencode_runtime/paths_runtime/`。如果新的策略、恢复或
   序列化逻辑落在那里，按领域拆分，在这些运行时
   包开始重新累积混合职责之前。
5. 保持新薄的顶层外观稳定；如果需要更多
   通信层清理，优先拆分运行时本地
   辅助模块，而非重新增长 `provider_backends/*/comm.py`。
6. 将历史文档与当前基线文档分离，使读者不会
   将旧的迁移说明与当前的运行时结构混淆。

## 实用导航指南

如果你正在更改 agent-first 运行时行为，从这里开始：

- `ccb`
- `lib/cli/phase2.py`
- `lib/cli/services/`
- `lib/askd/app.py`
- `lib/askd/services/`
- `lib/provider_execution/service.py`
- `lib/provider_execution/registry.py`
- `lib/provider_backends/<provider>/`

如果你正在更改启动和窗格编排，从这里开始：

- `ccb`
- `lib/cli/start.py`
- `lib/launcher/`
- `lib/launcher/app_bootstrap.py`
- `lib/terminal.py`
- `lib/terminal_runtime/`

如果你正在更改持久化或项目绑定，从这里开始：

- `lib/project/`
- `lib/storage/`
- `lib/workspace/`
- `lib/pane_registry_runtime/`
- `lib/pane_registry.py`
- `lib/session_utils.py`

## 维护规则

- 保持 agent-first 路径显式且简短。
- 优先选择包本地模块，而非重新引入巨大的顶层辅助
  文件。
- 当模块成为稳定包表面的一部分时，从包 `__init__.py` 显式导出它。
- 将生成的产物和缓存保持在仓库根之外，并脱离 git
  跟踪。
