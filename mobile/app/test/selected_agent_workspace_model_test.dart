import 'package:ccb_mobile/features/agent_chat/agent_chat_controller.dart';
import 'package:ccb_mobile/features/agent_chat/selected_agent_workspace_model.dart';
import 'package:ccb_mobile/models/ccb_agent.dart';
import 'package:ccb_mobile/models/ccb_agent_conversation.dart';
import 'package:ccb_mobile/models/ccb_conversation_item.dart';
import 'package:ccb_mobile/models/ccb_project.dart';
import 'package:ccb_mobile/models/ccb_project_view.dart';
import 'package:test/test.dart';

void main() {
  test('keeps comms updates out of visible conversation timeline', () {
    final chatController = AgentChatController();
    final view = _view();
    final agent = _agent();
    chatController.applyRemoteConversation(
      agentName: agent.name,
      shouldScroll: true,
      conversation: CcbAgentConversation(
        projectId: view.project.id,
        agentName: agent.name,
        namespaceEpoch: view.namespaceEpoch!,
        items: [
          const CcbConversationItem(
            id: 'reply-1',
            agentName: 'mobile',
            kind: CcbConversationItemKind.agentReply,
            title: 'Agent reply',
            body: 'real answer',
            source: 'completion_snapshot',
          ),
          const CcbConversationItem(
            id: 'comms-1',
            agentName: 'mobile',
            kind: CcbConversationItemKind.commsItem,
            title: 'Comms',
            body: 'project view updated',
            source: 'project_view',
          ),
        ],
        generatedAt: DateTime.utc(2026, 6, 24),
      ),
    );

    final model = selectedAgentWorkspaceModel(
      view: view,
      agent: agent,
      chatController: chatController,
    );

    expect(model.timelineItems.map((item) => item.id), ['reply-1']);
    expect(model.commsItems.map((item) => item.id), ['comms-1']);
    expect(model.hasOlderConversation, isFalse);
  });

  test('reports older conversation availability from next cursor', () {
    final chatController = AgentChatController();
    final view = _view();
    final agent = _agent();
    chatController.applyRemoteConversation(
      agentName: agent.name,
      shouldScroll: true,
      conversation: CcbAgentConversation(
        projectId: view.project.id,
        agentName: agent.name,
        namespaceEpoch: view.namespaceEpoch!,
        items: const [],
        nextCursor: '8',
        generatedAt: DateTime.utc(2026, 6, 24),
      ),
    );

    final model = selectedAgentWorkspaceModel(
      view: view,
      agent: agent,
      chatController: chatController,
    );

    expect(model.hasOlderConversation, isTrue);
  });
}

CcbProjectView _view() {
  return CcbProjectView(
    project: const CcbProject(
      id: 'proj',
      displayName: 'Project',
      root: '/tmp/proj',
    ),
    namespaceEpoch: 7,
    tmuxSocketPath: null,
    tmuxSessionName: null,
    activeWindow: 'main',
    activePaneId: null,
    windows: const [],
    agents: [_agent()],
    contentItems: const [],
    notifications: const [],
    terminalHistories: const {},
  );
}

CcbAgent _agent() {
  return const CcbAgent(
    name: 'mobile',
    provider: 'codex',
    window: 'main',
    order: 0,
    active: true,
    queueDepth: 0,
  );
}
