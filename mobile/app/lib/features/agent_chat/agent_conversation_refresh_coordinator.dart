import '../../models/ccb_agent_conversation.dart';
import '../../models/ccb_project_view.dart';
import '../../repository/mobile_ccb_repository.dart';
import 'agent_chat_controller.dart';
import 'agent_conversation_loader.dart';

typedef AgentChatStateMutation = void Function(void Function() update);
typedef AgentChatIsMounted = bool Function();
typedef AgentTimelineNearEnd = bool Function(String agentName);
typedef AgentTimelineScrollToEnd = void Function(String agentName);

class AgentConversationRefreshCoordinator {
  const AgentConversationRefreshCoordinator({
    required AgentChatController chatController,
    required AgentChatIsMounted isMounted,
    required AgentChatStateMutation mutateState,
    required AgentTimelineNearEnd isTimelineNearEnd,
    required AgentTimelineScrollToEnd scrollTimelineToEnd,
  }) : _chatController = chatController,
       _isMounted = isMounted,
       _mutateState = mutateState,
       _isTimelineNearEnd = isTimelineNearEnd,
       _scrollTimelineToEnd = scrollTimelineToEnd;

  final AgentChatController _chatController;
  final AgentChatIsMounted _isMounted;
  final AgentChatStateMutation _mutateState;
  final AgentTimelineNearEnd _isTimelineNearEnd;
  final AgentTimelineScrollToEnd _scrollTimelineToEnd;

  Future<void> load({
    required MobileCcbRepository repository,
    required CcbProjectView view,
    required String agentName,
    AgentViewRefresh? refreshView,
  }) async {
    if (view.namespaceEpoch == null ||
        _chatController.isLoadingConversation(agentName)) {
      return;
    }
    _mutateState(() {
      _chatController.beginLoadingConversation(agentName);
    });
    try {
      final conversation = await AgentConversationLoader(
        repository: repository,
        refreshView: refreshView,
      ).load(agentName: agentName, view: view);
      if (!_isMounted() || conversation == null) {
        return;
      }
      _applyLoadedConversation(
        agentName: agentName,
        conversation: conversation,
      );
    } catch (error) {
      if (!_isMounted()) {
        return;
      }
      _mutateState(() {
        _chatController.setConversationError(agentName, error);
      });
    } finally {
      if (_isMounted()) {
        _mutateState(() {
          _chatController.finishLoadingConversation(agentName);
        });
      }
    }
  }

  Future<bool> loadOlder({
    required MobileCcbRepository repository,
    required CcbProjectView view,
    required String agentName,
    AgentViewRefresh? refreshView,
  }) async {
    final cursor = _chatController.olderConversationCursor(agentName);
    if (view.namespaceEpoch == null ||
        cursor == null ||
        _chatController.isLoadingConversation(agentName)) {
      return false;
    }
    _mutateState(() {
      _chatController.beginLoadingConversation(agentName);
    });
    var changed = false;
    try {
      final conversation = await AgentConversationLoader(
        repository: repository,
        refreshView: refreshView,
      ).load(agentName: agentName, view: view, cursor: cursor);
      if (!_isMounted() || conversation == null) {
        return false;
      }
      _mutateState(() {
        final update = _chatController.prependRemoteConversationPage(
          agentName: agentName,
          conversation: conversation,
        );
        changed = update.changed;
      });
      return changed;
    } catch (error) {
      if (_isMounted()) {
        _mutateState(() {
          _chatController.setConversationError(agentName, error);
        });
      }
      return false;
    } finally {
      if (_isMounted()) {
        _mutateState(() {
          _chatController.finishLoadingConversation(agentName);
        });
      }
    }
  }

  void _applyLoadedConversation({
    required String agentName,
    required CcbAgentConversation conversation,
  }) {
    final previousConversation = _chatController.remoteConversationFor(
      agentName,
    );
    final shouldScroll =
        previousConversation == null || _isTimelineNearEnd(agentName);
    var changed = false;
    _mutateState(() {
      final update = _chatController.applyRemoteConversation(
        agentName: agentName,
        conversation: conversation,
        shouldScroll: shouldScroll,
      );
      changed = update.changed;
    });
    if (changed && shouldScroll) {
      _scrollTimelineToEnd(agentName);
    }
  }
}
