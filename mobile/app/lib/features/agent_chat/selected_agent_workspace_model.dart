import '../../models/ccb_agent.dart';
import '../../models/ccb_content_item.dart';
import '../../models/ccb_conversation_item.dart';
import '../../models/ccb_project_view.dart';
import '../../models/readable_terminal_history.dart';
import 'agent_chat_controller.dart';
import 'agent_chat_timeline_items.dart';

class SelectedAgentWorkspaceModel {
  const SelectedAgentWorkspaceModel({
    required this.agent,
    required this.contentItems,
    required this.initialHistory,
    required this.timelineItems,
    required this.commsItems,
    required this.isLoadingConversation,
    required this.hasOlderConversation,
    required this.expandedItemIds,
    required this.hasNewMessages,
    required this.isSending,
    required this.isComposerCollapsed,
  });

  final CcbAgent agent;
  final List<CcbContentItem> contentItems;
  final ReadableTerminalHistory? initialHistory;
  final List<CcbConversationItem> timelineItems;
  final List<CcbConversationItem> commsItems;
  final bool isLoadingConversation;
  final bool hasOlderConversation;
  final Set<String> expandedItemIds;
  final bool hasNewMessages;
  final bool isSending;
  final bool isComposerCollapsed;
}

SelectedAgentWorkspaceModel selectedAgentWorkspaceModel({
  required CcbProjectView view,
  required CcbAgent agent,
  required AgentChatController chatController,
}) {
  final contentItems = view.contentForAgent(agent.name);
  final terminalHistory =
      chatController.refreshedTerminalHistoryFor(agent.name) ??
      view.terminalHistoryForAgent(agent.name);
  final remoteConversation = chatController.remoteConversationFor(agent.name);
  final conversationError = chatController.conversationErrorFor(agent.name);
  final allTimelineItems = selectedAgentTimelineItems(
    view: view,
    agent: agent,
    contentItems: contentItems,
    terminalHistory: terminalHistory,
    remoteConversation: remoteConversation,
    conversationError: conversationError,
    localMessages: chatController.localMessagesFor(agent.name),
  );
  return SelectedAgentWorkspaceModel(
    agent: agent,
    contentItems: contentItems,
    initialHistory: terminalHistory,
    timelineItems: [
      for (final item in allTimelineItems)
        if (item.kind != CcbConversationItemKind.commsItem) item,
    ],
    commsItems: [
      for (final item in allTimelineItems)
        if (item.kind == CcbConversationItemKind.commsItem) item,
    ],
    isLoadingConversation: chatController.isLoadingConversation(agent.name),
    hasOlderConversation: chatController.hasOlderConversation(agent.name),
    expandedItemIds: chatController.expandedItemIds(agent.name),
    hasNewMessages: chatController.hasNewMessages(agent.name),
    isSending: chatController.isSubmitting(agent.name),
    isComposerCollapsed: chatController.isComposerCollapsed(agent.name),
  );
}
