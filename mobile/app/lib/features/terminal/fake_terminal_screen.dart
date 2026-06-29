import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:xterm/xterm.dart';

import '../../models/ccb_terminal_target.dart';
import '../../models/ccb_project_view.dart';
import '../../repository/mobile_ccb_repository.dart';
import '../../tmux/tmux_command_builder.dart';
import '../../transport/gateway_terminal_transport.dart';
import '../../transport/terminal_transport.dart';

class FakeTerminalScreen extends StatefulWidget {
  const FakeTerminalScreen({
    required this.repository,
    required this.projectId,
    this.agentName,
    this.windowName,
    this.terminalTransport,
    this.gatewayTerminal = false,
    super.key,
  }) : assert(
         (agentName == null) != (windowName == null),
         'Provide exactly one terminal target identity.',
       );

  final MobileCcbRepository repository;
  final String projectId;
  final String? agentName;
  final String? windowName;
  final TerminalTransport? terminalTransport;
  final bool gatewayTerminal;

  @override
  State<FakeTerminalScreen> createState() => _FakeTerminalScreenState();
}

class _FakeTerminalScreenState extends State<FakeTerminalScreen> {
  late final Future<_FakeTerminalModel> _modelFuture;

  @override
  void initState() {
    super.initState();
    _modelFuture = _loadModel();
  }

  Future<_FakeTerminalModel> _loadModel() async {
    final view = await widget.repository.getProjectView(widget.projectId);
    final target =
        widget.agentName != null
            ? view.terminalTargetForAgent(widget.agentName!)
            : view.terminalTargetForWindow(widget.windowName!);
    final attachCommand =
        target.hasDirectTmuxAttachEvidence
            ? TmuxCommandBuilder.shellCommand(
              TmuxCommandBuilder.forTarget(target).attachSession(),
            )
            : 'gateway terminal stream ${target.projectId}/${target.agent ?? target.window ?? 'terminal'}';
    return _FakeTerminalModel(
      view: view,
      target: target,
      attachCommand: attachCommand,
    );
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<_FakeTerminalModel>(
      future: _modelFuture,
      builder: (context, snapshot) {
        final model = snapshot.data;
        return Scaffold(
          appBar: AppBar(
            title: Text(model?.title ?? widget.agentName ?? widget.windowName!),
          ),
          body:
              model == null
                  ? const Center(child: CircularProgressIndicator())
                  : widget.terminalTransport == null
                  ? _FakeTerminalPane(model: model)
                  : _LiveTerminalPane(
                    model: model,
                    transport: widget.terminalTransport!,
                    gatewayTerminal: widget.gatewayTerminal,
                  ),
        );
      },
    );
  }
}

class _FakeTerminalPane extends StatefulWidget {
  const _FakeTerminalPane({required this.model});

  final _FakeTerminalModel model;

  @override
  State<_FakeTerminalPane> createState() => _FakeTerminalPaneState();
}

class _FakeTerminalPaneState extends State<_FakeTerminalPane> {
  late final Terminal _terminal;

  @override
  void initState() {
    super.initState();
    _terminal = Terminal(maxLines: 2000);
    _writeTranscript();
  }

  void _writeTranscript() {
    final target = widget.model.target;
    _terminal.write('\x1b[32mCCB Mobile fake terminal\x1b[0m\r\n');
    _terminal.write('project: ${target.projectId}\r\n');
    _terminal.write('agent: ${target.agent ?? ''}\r\n');
    _terminal.write('window: ${target.window ?? ''}\r\n');
    _terminal.write('pane evidence: ${target.paneId ?? ''}\r\n');
    _terminal.write('namespace epoch: ${target.namespaceEpoch}\r\n');
    _terminal.write('\r\n');
    _terminal.write('\$ ${widget.model.attachCommand}\r\n');
    _terminal.write('\r\n');
    _terminal.write('fake transport only; live PTY is not connected yet\r\n');
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Column(
      children: [
        Material(
          color: colorScheme.surfaceContainerHighest,
          child: ListTile(
            dense: true,
            leading: const Icon(Icons.terminal),
            title: Text(widget.model.title),
            subtitle: Text(widget.model.attachCommand),
          ),
        ),
        Expanded(
          child: TerminalView(
            _terminal,
            key: const ValueKey('ccb-terminal-view'),
            autofocus: true,
            readOnly: true,
          ),
        ),
      ],
    );
  }
}

class _LiveTerminalPane extends StatefulWidget {
  const _LiveTerminalPane({
    required this.model,
    required this.transport,
    required this.gatewayTerminal,
  });

  final _FakeTerminalModel model;
  final TerminalTransport transport;
  final bool gatewayTerminal;

  @override
  State<_LiveTerminalPane> createState() => _LiveTerminalPaneState();
}

class _LiveTerminalPaneState extends State<_LiveTerminalPane>
    with WidgetsBindingObserver {
  final _inputController = TextEditingController();
  late final Terminal _terminal;
  late final Future<TerminalSession> _sessionFuture;
  TerminalSession? _session;
  StreamSubscription<String>? _outputSubscription;
  TerminalGeometry _lastGeometry = const TerminalGeometry(
    columns: 100,
    rows: 30,
    pixelWidth: 960,
    pixelHeight: 640,
  );
  String _controlStatus = 'Ready';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _terminal = Terminal(
      maxLines: 4000,
      onOutput: (data) {
        _writeTerminalBytes(utf8.encode(data));
      },
      onResize: (width, height, pixelWidth, pixelHeight) {
        final geometry = TerminalGeometry(
          columns: width,
          rows: height,
          pixelWidth: pixelWidth,
          pixelHeight: pixelHeight,
        );
        _lastGeometry = geometry;
        _session?.resize(geometry);
      },
    );
    _sessionFuture = _openSession();
  }

  Future<TerminalSession> _openSession() async {
    final request =
        widget.gatewayTerminal || widget.transport is GatewayTerminalTransport
            ? TerminalOpenRequest.gateway(target: widget.model.target)
            : TerminalOpenRequest(target: widget.model.target);
    final session = await widget.transport.open(request);
    _session = session;
    _outputSubscription = session.output
        .map<List<int>>((bytes) => bytes)
        .transform(utf8.decoder)
        .listen(
          _terminal.write,
          onError: (Object error) {
            _terminal.write('\r\n\x1b[31m$error\x1b[0m\r\n');
          },
        );
    return session;
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _session?.reconnect().catchError((Object error) {
        _terminal.write('\r\n\x1b[33m$error\x1b[0m\r\n');
      });
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _inputController.dispose();
    _outputSubscription?.cancel();
    _session?.close().catchError((_) {
      // Best-effort route teardown; the gateway may already have closed.
    });
    super.dispose();
  }

  void _writeTerminalBytes(List<int> bytes) {
    final session = _session;
    if (session == null) {
      return;
    }
    session.writeBytes(bytes).catchError((Object error) {
      // TerminalView may emit device-status responses while a WebSocket is
      // reconnecting. Keep those best-effort writes from overwriting explicit
      // user command statuses such as Sent, Pasted, and Reconnected.
    });
  }

  Future<void> _sendInput() async {
    final text = _inputController.text;
    if (text.isEmpty) {
      return;
    }
    final session = _session;
    if (session == null) {
      _setControlStatus('Connecting');
      return;
    }
    try {
      await session.writeBytes(utf8.encode(text));
      _inputController.clear();
      _setControlStatus('Sent');
    } catch (error) {
      _setControlStatus('Send failed');
      _terminal.write('\r\n\x1b[31m$error\x1b[0m\r\n');
    }
  }

  Future<void> _pasteInput() async {
    final text = _inputController.text;
    if (text.isEmpty) {
      return;
    }
    final session = _session;
    if (session == null) {
      _setControlStatus('Connecting');
      return;
    }
    try {
      await session.paste(text);
      _inputController.clear();
      _setControlStatus('Pasted');
    } catch (error) {
      _setControlStatus('Paste failed');
      _terminal.write('\r\n\x1b[31m$error\x1b[0m\r\n');
    }
  }

  Future<void> _syncSize() async {
    final session = _session;
    if (session == null) {
      _setControlStatus('Connecting');
      return;
    }
    try {
      await session.resize(_lastGeometry);
      _setControlStatus('Size synced');
    } catch (error) {
      _setControlStatus('Resize failed');
      _terminal.write('\r\n\x1b[31m$error\x1b[0m\r\n');
    }
  }

  Future<void> _reconnect() async {
    final session = _session;
    if (session == null) {
      _setControlStatus('Connecting');
      return;
    }
    try {
      _setControlStatus('Reconnecting');
      await session.reconnect();
      _setControlStatus('Reconnected');
    } catch (error) {
      _setControlStatus('Reconnect failed');
      _terminal.write('\r\n\x1b[33m$error\x1b[0m\r\n');
    }
  }

  void _setControlStatus(String status) {
    if (!mounted) {
      return;
    }
    setState(() {
      _controlStatus = status;
    });
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return FutureBuilder<TerminalSession>(
      future: _sessionFuture,
      builder: (context, snapshot) {
        final connected =
            snapshot.connectionState == ConnectionState.done &&
            snapshot.hasData;
        final status = connected ? 'Gateway WebSocket' : 'Connecting';
        return Column(
          children: [
            Material(
              color: colorScheme.surfaceContainerHighest,
              child: ListTile(
                dense: true,
                leading: const Icon(Icons.terminal),
                title: Text(widget.model.title),
                subtitle: Text(widget.model.attachCommand),
                trailing: Text(status),
              ),
            ),
            Material(
              color: colorScheme.surface,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
                      key: const ValueKey('terminal-command-input'),
                      controller: _inputController,
                      minLines: 1,
                      maxLines: 2,
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) {
                        _sendInput();
                      },
                      decoration: const InputDecoration(
                        isDense: true,
                        labelText: 'Terminal input',
                      ),
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            _controlStatus,
                            key: const ValueKey('terminal-control-status'),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context).textTheme.labelMedium
                                ?.copyWith(color: colorScheme.onSurfaceVariant),
                          ),
                        ),
                        IconButton(
                          key: const ValueKey('terminal-send-button'),
                          tooltip: 'Send input',
                          onPressed: connected ? _sendInput : null,
                          icon: const Icon(Icons.send),
                        ),
                        IconButton(
                          key: const ValueKey('terminal-paste-button'),
                          tooltip: 'Paste input',
                          onPressed: connected ? _pasteInput : null,
                          icon: const Icon(Icons.content_paste_go),
                        ),
                        IconButton(
                          key: const ValueKey('terminal-resize-button'),
                          tooltip: 'Sync terminal size',
                          onPressed: connected ? _syncSize : null,
                          icon: const Icon(Icons.fit_screen),
                        ),
                        IconButton(
                          key: const ValueKey('terminal-reconnect-button'),
                          tooltip: 'Reconnect terminal',
                          onPressed: connected ? _reconnect : null,
                          icon: const Icon(Icons.refresh),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            Expanded(
              child: TerminalView(
                _terminal,
                key: const ValueKey('ccb-live-terminal-view'),
                autofocus: true,
              ),
            ),
          ],
        );
      },
    );
  }
}

class _FakeTerminalModel {
  const _FakeTerminalModel({
    required this.view,
    required this.target,
    required this.attachCommand,
  });

  final CcbProjectView view;
  final CcbTerminalTarget target;
  final String attachCommand;

  String get title {
    return '${view.project.displayName} / ${target.agent ?? target.window ?? 'terminal'}';
  }
}
