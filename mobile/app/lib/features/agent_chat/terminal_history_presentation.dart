import 'package:flutter/material.dart';

import '../../models/readable_terminal_history.dart';

String terminalBlockText(ReadableTerminalBlock block) {
  return block.type == 'command' ? r'$ ' + block.text : block.text;
}

String historyScopeLabel(String scope) {
  return switch (scope) {
    'tmux_scrollback' => 'tmux scrollback',
    'terminal_journal' => 'terminal journal',
    'current_screen' => 'current screen',
    _ => scope,
  };
}

String terminalBlockLabel(String type) {
  return switch (type) {
    'command' => 'Command',
    'code' => 'Code',
    'diff' => 'Diff',
    'error' => 'Error',
    _ => 'Log',
  };
}

IconData terminalBlockIcon(String type) {
  return switch (type) {
    'command' => Icons.terminal,
    'code' => Icons.code,
    'diff' => Icons.difference,
    'error' => Icons.error_outline,
    _ => Icons.notes,
  };
}

Color terminalBlockColor(ColorScheme colorScheme, String type) {
  return switch (type) {
    'command' => colorScheme.primary,
    'code' => colorScheme.tertiary,
    'diff' => colorScheme.secondary,
    'error' => colorScheme.error,
    _ => colorScheme.outline,
  };
}
