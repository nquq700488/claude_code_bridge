import 'dart:typed_data';

import '../models/ccb_terminal_target.dart';
import '../tmux/tmux_command_builder.dart';

class TerminalGeometry {
  const TerminalGeometry({
    this.columns = 80,
    this.rows = 24,
    this.pixelWidth = 0,
    this.pixelHeight = 0,
  }) : assert(columns > 0),
       assert(rows > 0),
       assert(pixelWidth >= 0),
       assert(pixelHeight >= 0);

  final int columns;
  final int rows;
  final int pixelWidth;
  final int pixelHeight;
}

class TerminalOpenRequest {
  TerminalOpenRequest({
    required this.target,
    this.geometry = const TerminalGeometry(),
    this.terminalType = 'xterm-256color',
  }) : attachCommand = _buildAttachCommand(target, requireDirectAttach: true) {
    _validateTerminalType(terminalType);
  }

  TerminalOpenRequest.gateway({
    required this.target,
    this.geometry = const TerminalGeometry(),
    this.terminalType = 'xterm-256color',
  }) : attachCommand = _buildAttachCommand(target, requireDirectAttach: false) {
    _validateTerminalType(terminalType);
  }

  static void _validateTerminalType(String terminalType) {
    if (terminalType.trim().isEmpty) {
      throw ArgumentError.value(terminalType, 'terminalType', 'required');
    }
  }

  final CcbTerminalTarget target;
  final TerminalGeometry geometry;
  final String terminalType;
  final String attachCommand;

  static String _buildAttachCommand(
    CcbTerminalTarget target, {
    required bool requireDirectAttach,
  }) {
    if (!target.canAcceptTerminalInput) {
      throw StateError(
        'terminal target requires project identity, namespace epoch, stable '
        'agent/window identity, and terminal_input scope',
      );
    }
    if (!requireDirectAttach) {
      final identity =
          target.agent ?? target.window ?? target.paneId ?? 'terminal';
      return 'gateway terminal stream ${target.projectId}/$identity';
    }
    final builder = TmuxCommandBuilder.forTarget(target);
    return TmuxCommandBuilder.shellCommand(builder.attachSession());
  }
}

abstract interface class TerminalTransport {
  Future<TerminalSession> open(TerminalOpenRequest request);
}

abstract interface class TerminalSession {
  String get launchedCommand;

  Stream<Uint8List> get output;

  Future<void> writeBytes(List<int> bytes);

  Future<void> paste(String text);

  Future<void> resize(TerminalGeometry geometry);

  Future<void> reconnect();

  Future<void> close();
}

class TerminalTransportException implements Exception {
  const TerminalTransportException(this.message, [this.cause]);

  final String message;
  final Object? cause;

  @override
  String toString() {
    final causeText = cause == null ? '' : ': $cause';
    return 'TerminalTransportException($message$causeText)';
  }
}
