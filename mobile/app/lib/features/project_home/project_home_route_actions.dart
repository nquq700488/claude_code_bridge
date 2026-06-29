import 'package:flutter/material.dart';

import '../../models/ccb_notification.dart';
import '../../models/ccb_project_view.dart';
import '../../repository/mobile_ccb_repository.dart';
import '../../transport/terminal_transport.dart';
import '../terminal/fake_terminal_screen.dart';
import 'connection_details.dart';
import 'notification_center_sheet.dart';

Future<void> pushProjectHomeTerminalRoute(
  BuildContext context, {
  required MobileCcbRepository repository,
  required String projectId,
  String? agentName,
  String? windowName,
  TerminalTransport? terminalTransport,
  bool gatewayTerminal = false,
}) {
  return Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder:
          (context) => FakeTerminalScreen(
            repository: repository,
            projectId: projectId,
            agentName: agentName,
            windowName: windowName,
            terminalTransport: terminalTransport,
            gatewayTerminal: gatewayTerminal,
          ),
    ),
  );
}

Future<void> pushProjectHomeConnectionDetailsRoute(
  BuildContext context, {
  required Widget panel,
}) {
  return Navigator.of(context).push(
    MaterialPageRoute<void>(
      fullscreenDialog: true,
      builder: (routeContext) => ConnectionDetailsScreen(panel: panel),
    ),
  );
}

Future<void> showProjectHomeNotificationCenter(
  BuildContext context, {
  required List<CcbNotification> notifications,
  required ValueChanged<CcbNotification> onOpen,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (sheetContext) {
      return NotificationCenterSheet(
        notifications: notifications,
        onOpen: (notification) {
          Navigator.of(sheetContext).pop();
          onOpen(notification);
        },
      );
    },
  );
}

Future<bool?> confirmProjectHomeStop(
  BuildContext context, {
  required CcbProjectView view,
}) {
  return showDialog<bool>(
    context: context,
    builder:
        (context) => AlertDialog(
          title: const Text('Stop project'),
          content: Text('Stop ${view.project.displayName}?'),
          actions: [
            TextButton(
              key: const ValueKey('cancel-lifecycle-stop-button'),
              onPressed: () {
                Navigator.of(context).pop(false);
              },
              child: const Text('Cancel'),
            ),
            FilledButton(
              key: const ValueKey('confirm-lifecycle-stop-button'),
              onPressed: () {
                Navigator.of(context).pop(true);
              },
              child: const Text('Stop'),
            ),
          ],
        ),
  );
}
