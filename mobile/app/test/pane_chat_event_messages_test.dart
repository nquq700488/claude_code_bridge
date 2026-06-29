import 'package:flutter_test/flutter_test.dart';

import 'package:ccb_mobile/features/agent_chat/pane_chat_controller.dart';
import 'package:ccb_mobile/features/agent_chat/pane_chat_event_messages.dart';
import 'package:ccb_mobile/models/ccb_conversation_item.dart';

void main() {
  test('maps pane output to compact live terminal conversation item', () {
    var outputIds = 0;

    final update = localMessagesAfterPaneChatEvent(
      event: const PaneChatEvent(
        agentName: 'lead',
        kind: PaneChatEventKind.output,
        body: '\x1B[31mline\x1B[0m',
      ),
      currentMessages: const [],
      nextOutputId: () => 'out-${outputIds++}',
      nextNoticeId: () => 'notice',
    );

    expect(update.changed, isTrue);
    expect(update.messages.single.id, 'out-0');
    expect(update.messages.single.kind, CcbConversationItemKind.agentReply);
    expect(update.messages.single.title, 'Terminal output');
    expect(update.messages.single.body, 'line');
    expect(update.messages.single.format, 'plain');
    expect(update.messages.single.source, 'tmux output / live');
    expect(outputIds, 1);
  });

  test('ignores blank output without consuming ids', () {
    var outputIds = 0;
    final current = [
      CcbConversationItem.userMessage(
        id: 'user',
        agentName: 'lead',
        body: 'hello',
      ),
    ];

    final update = localMessagesAfterPaneChatEvent(
      event: const PaneChatEvent(
        agentName: 'lead',
        kind: PaneChatEventKind.output,
        body: '  \n\t',
      ),
      currentMessages: current,
      nextOutputId: () => 'out-${outputIds++}',
      nextNoticeId: () => 'notice',
    );

    expect(update.changed, isFalse);
    expect(update.messages, same(current));
    expect(outputIds, 0);
  });

  test('merges consecutive live terminal output bubbles', () {
    var outputIds = 0;
    final first = CcbConversationItem(
      id: 'live-previous',
      agentName: 'lead',
      kind: CcbConversationItemKind.agentReply,
      title: 'Terminal output',
      body: 'first',
      source: 'tmux output / live',
    );

    final update = localMessagesAfterPaneChatEvent(
      event: const PaneChatEvent(
        agentName: 'lead',
        kind: PaneChatEventKind.output,
        body: 'second',
      ),
      currentMessages: [first],
      nextOutputId: () => 'out-${outputIds++}',
      nextNoticeId: () => 'notice',
    );

    expect(update.changed, isTrue);
    expect(update.messages, hasLength(1));
    expect(update.messages.single.id, 'live-previous');
    expect(update.messages.single.body, contains('first'));
    expect(update.messages.single.body, contains('second'));
    expect(outputIds, 1);
  });

  test('maps pane notices to terminal stream system notices', () {
    var noticeIds = 0;

    final update = localMessagesAfterPaneChatEvent(
      event: const PaneChatEvent(
        agentName: 'lead',
        kind: PaneChatEventKind.notice,
        body: 'TerminalTransportException(expired)',
      ),
      currentMessages: const [],
      nextOutputId: () => 'output',
      nextNoticeId: () => 'notice-${noticeIds++}',
    );

    expect(update.changed, isTrue);
    expect(update.messages.single.id, 'notice-0');
    expect(update.messages.single.kind, CcbConversationItemKind.systemNotice);
    expect(update.messages.single.title, 'Terminal stream');
    expect(update.messages.single.body, contains('expired'));
    expect(update.messages.single.source, 'terminal transport');
    expect(noticeIds, 1);
  });
}
