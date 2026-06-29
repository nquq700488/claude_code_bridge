import '../../models/ccb_conversation_item.dart';
import 'live_terminal_output.dart';
import 'pane_chat_controller.dart';

typedef PaneChatEventIdFactory = String Function();

class PaneChatEventMessageUpdate {
  const PaneChatEventMessageUpdate({
    required this.changed,
    required this.messages,
  });

  final bool changed;
  final List<CcbConversationItem> messages;
}

PaneChatEventMessageUpdate localMessagesAfterPaneChatEvent({
  required PaneChatEvent event,
  required List<CcbConversationItem> currentMessages,
  required PaneChatEventIdFactory nextOutputId,
  required PaneChatEventIdFactory nextNoticeId,
}) {
  switch (event.kind) {
    case PaneChatEventKind.output:
      return _localMessagesAfterOutputEvent(
        event: event,
        currentMessages: currentMessages,
        nextOutputId: nextOutputId,
      );
    case PaneChatEventKind.notice:
      return _localMessagesAfterNoticeEvent(
        event: event,
        currentMessages: currentMessages,
        nextNoticeId: nextNoticeId,
      );
  }
}

PaneChatEventMessageUpdate _localMessagesAfterOutputEvent({
  required PaneChatEvent event,
  required List<CcbConversationItem> currentMessages,
  required PaneChatEventIdFactory nextOutputId,
}) {
  if (event.body.isEmpty) {
    return PaneChatEventMessageUpdate(
      changed: false,
      messages: currentMessages,
    );
  }
  final readableBody = compactLiveTerminalOutput(event.body);
  if (readableBody.isEmpty) {
    return PaneChatEventMessageUpdate(
      changed: false,
      messages: currentMessages,
    );
  }
  final item = CcbConversationItem(
    id: nextOutputId(),
    agentName: event.agentName,
    kind: CcbConversationItemKind.agentReply,
    title: 'Terminal output',
    body: readableBody,
    format: 'plain',
    source: 'tmux output / live',
  );
  return PaneChatEventMessageUpdate(
    changed: true,
    messages: appendOrMergeLiveTerminalOutput(currentMessages, item),
  );
}

PaneChatEventMessageUpdate _localMessagesAfterNoticeEvent({
  required PaneChatEvent event,
  required List<CcbConversationItem> currentMessages,
  required PaneChatEventIdFactory nextNoticeId,
}) {
  final item = CcbConversationItem(
    id: nextNoticeId(),
    agentName: event.agentName,
    kind: CcbConversationItemKind.systemNotice,
    title: 'Terminal stream',
    body: event.body,
    source: 'terminal transport',
  );
  return PaneChatEventMessageUpdate(
    changed: true,
    messages: [...currentMessages, item],
  );
}
