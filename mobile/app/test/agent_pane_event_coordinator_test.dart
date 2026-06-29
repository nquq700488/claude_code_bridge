import 'package:ccb_mobile/features/agent_chat/agent_chat_controller.dart';
import 'package:ccb_mobile/features/agent_chat/agent_pane_event_coordinator.dart';
import 'package:ccb_mobile/features/agent_chat/pane_chat_controller.dart';
import 'package:ccb_mobile/models/ccb_conversation_item.dart';
import 'package:test/test.dart';

void main() {
  test('applies live output and scrolls when timeline is near end', () {
    final chatController = AgentChatController();
    final scrolledAgents = <String>[];
    final coordinator = _coordinator(
      chatController: chatController,
      isTimelineNearEnd: (_) => true,
      scrollTimelineToEnd: scrolledAgents.add,
    );

    coordinator.apply(
      const PaneChatEvent(
        agentName: 'lead',
        kind: PaneChatEventKind.output,
        body: 'hello',
      ),
    );

    final messages = chatController.localMessagesFor('lead');
    expect(messages, hasLength(1));
    expect(messages.single.kind, CcbConversationItemKind.agentReply);
    expect(messages.single.body, 'hello');
    expect(chatController.hasNewMessages('lead'), isFalse);
    expect(scrolledAgents, const ['lead']);
  });

  test(
    'marks new messages without scrolling when timeline is not near end',
    () {
      final chatController = AgentChatController();
      final scrolledAgents = <String>[];
      final coordinator = _coordinator(
        chatController: chatController,
        isTimelineNearEnd: (_) => false,
        scrollTimelineToEnd: scrolledAgents.add,
      );

      coordinator.apply(
        const PaneChatEvent(
          agentName: 'lead',
          kind: PaneChatEventKind.notice,
          body: 'stream expired',
        ),
      );

      expect(chatController.localMessagesFor('lead'), hasLength(1));
      expect(chatController.hasNewMessages('lead'), isTrue);
      expect(scrolledAgents, isEmpty);
    },
  );

  test('ignores blank output without mutating state or scrolling', () {
    final chatController = AgentChatController();
    final scrolledAgents = <String>[];
    var mutations = 0;
    final coordinator = AgentPaneEventCoordinator(
      chatController: chatController,
      isMounted: () => true,
      mutateState: (update) {
        mutations += 1;
        update();
      },
      isTimelineNearEnd: (_) => true,
      scrollTimelineToEnd: scrolledAgents.add,
    );

    coordinator.apply(
      const PaneChatEvent(
        agentName: 'lead',
        kind: PaneChatEventKind.output,
        body: '  \n',
      ),
    );

    expect(chatController.localMessagesFor('lead'), isEmpty);
    expect(mutations, 0);
    expect(scrolledAgents, isEmpty);
  });
}

AgentPaneEventCoordinator _coordinator({
  required AgentChatController chatController,
  required bool Function(String agentName) isTimelineNearEnd,
  required void Function(String agentName) scrollTimelineToEnd,
}) {
  return AgentPaneEventCoordinator(
    chatController: chatController,
    isMounted: () => true,
    mutateState: (update) {
      update();
    },
    isTimelineNearEnd: isTimelineNearEnd,
    scrollTimelineToEnd: scrollTimelineToEnd,
  );
}
