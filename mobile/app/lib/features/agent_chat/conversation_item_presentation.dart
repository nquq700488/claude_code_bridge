import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';

import '../../models/ccb_conversation_item.dart';
import 'agent_chat_state_helpers.dart';

class ConversationPreview extends StatelessWidget {
  const ConversationPreview({required this.item, super.key});

  final CcbConversationItem item;

  @override
  Widget build(BuildContext context) {
    return Text(
      conversationPreviewTextFor(item),
      key: ValueKey('conversation-preview-${item.id}'),
      maxLines: conversationPreviewMaxLines(item),
      overflow: TextOverflow.ellipsis,
      style: Theme.of(context).textTheme.bodyMedium,
    );
  }
}

class ConversationBody extends StatelessWidget {
  const ConversationBody({
    required this.item,
    this.onDownloadArtifact,
    super.key,
  });

  final CcbConversationItem item;
  final ValueChanged<String>? onDownloadArtifact;

  @override
  Widget build(BuildContext context) {
    if (shouldRenderConversationMarkdown(item)) {
      return MarkdownBody(
        key: ValueKey('markdown-body-conversation-${item.id}'),
        data: item.body,
        selectable: true,
        onTapLink: (text, href, title) {
          if (href != null && href.startsWith('ccb-artifact://')) {
            final fileId = href.replaceFirst('ccb-artifact://', '');
            if (onDownloadArtifact != null) {
              onDownloadArtifact!(fileId);
            }
          } else {
            showBlockedConversationLink(context, href ?? text);
          }
        },
      );
    }
    return SelectableText(
      item.body,
      key: ValueKey('conversation-body-${item.id}'),
    );
  }
}

class ConversationStateChip extends StatelessWidget {
  const ConversationStateChip({required super.key, required this.state});

  final CcbConversationDeliveryState state;

  @override
  Widget build(BuildContext context) {
    return Chip(
      visualDensity: VisualDensity.compact,
      label: Text(conversationStateLabel(state)),
    );
  }
}

bool conversationShouldCollapse(
  CcbConversationItem item, {
  required bool hasCustomChild,
}) {
  if (hasCustomChild) {
    return true;
  }
  if (isTerminalDerivedConversationItem(item)) {
    return true;
  }
  if (item.kind == CcbConversationItemKind.userMessage) {
    return item.body.length > 360 || '\n'.allMatches(item.body).length > 6;
  }
  return item.body.length > 220 || '\n'.allMatches(item.body).length > 4;
}

int conversationPreviewMaxLines(CcbConversationItem item) {
  if (isTerminalInputConversationItem(item)) {
    return 1;
  }
  if (isTerminalDerivedConversationItem(item)) {
    return 2;
  }
  return 3;
}

String conversationPreviewText(String body) {
  final lines = [
    for (final line in body.split('\n'))
      if (line.trim().isNotEmpty) stripPreviewMarkdown(line.trim()),
  ];
  if (lines.isEmpty) {
    return 'No content';
  }
  return lines.take(3).join('\n');
}

String conversationPreviewTextFor(CcbConversationItem item) {
  if (!isTerminalDerivedConversationItem(item)) {
    return conversationPreviewText(item.body);
  }
  final lines = [
    for (final line in item.body.split('\n'))
      if (line.trim().isNotEmpty) line.trim(),
  ];
  if (lines.isEmpty) {
    return 'No content';
  }
  return lines.take(3).join('\n');
}

String stripPreviewMarkdown(String line) {
  return line
      .replaceFirst(RegExp(r'^(#{1,6})\s+'), '')
      .replaceFirst(RegExp(r'^[-*]\s+'), '')
      .replaceFirst(RegExp(r'^\d+\.\s+'), '')
      .replaceFirst(RegExp(r'^>\s+'), '')
      .replaceAll(RegExp(r'[*_`]+'), '');
}

bool shouldRenderConversationMarkdown(CcbConversationItem item) {
  if (isTerminalDerivedConversationItem(item)) {
    return false;
  }
  if (item.format.toLowerCase() == 'markdown') {
    return true;
  }
  return switch (item.kind) {
    CcbConversationItemKind.agentReply ||
    CcbConversationItemKind.callbackRequest ||
    CcbConversationItemKind.commsItem ||
    CcbConversationItemKind.userMessage => true,
    CcbConversationItemKind.statusEvent ||
    CcbConversationItemKind.toolEvent ||
    CcbConversationItemKind.artifactCard ||
    CcbConversationItemKind.terminalHistoryBlock ||
    CcbConversationItemKind.systemNotice => false,
  };
}

String? visibleConversationSourceLabel(CcbConversationItem item) {
  final source = item.source?.trim();
  if (source == null || source.isEmpty) {
    return null;
  }
  if (isTerminalDerivedConversationItem(item)) {
    return null;
  }
  return switch (item.kind) {
    CcbConversationItemKind.statusEvent ||
    CcbConversationItemKind.toolEvent ||
    CcbConversationItemKind.artifactCard ||
    CcbConversationItemKind.terminalHistoryBlock ||
    CcbConversationItemKind.systemNotice => source,
    CcbConversationItemKind.userMessage ||
    CcbConversationItemKind.agentReply ||
    CcbConversationItemKind.callbackRequest ||
    CcbConversationItemKind.commsItem => null,
  };
}

IconData conversationIcon(CcbConversationItemKind kind) {
  return switch (kind) {
    CcbConversationItemKind.userMessage => Icons.person,
    CcbConversationItemKind.agentReply => Icons.smart_toy,
    CcbConversationItemKind.callbackRequest => Icons.record_voice_over,
    CcbConversationItemKind.commsItem => Icons.forum,
    CcbConversationItemKind.statusEvent => Icons.info_outline,
    CcbConversationItemKind.toolEvent => Icons.construction,
    CcbConversationItemKind.artifactCard => Icons.article,
    CcbConversationItemKind.terminalHistoryBlock => Icons.history,
    CcbConversationItemKind.systemNotice => Icons.tune,
  };
}

String conversationStateLabel(CcbConversationDeliveryState state) {
  return switch (state) {
    CcbConversationDeliveryState.pending => 'Pending',
    CcbConversationDeliveryState.sent => 'Sent',
    CcbConversationDeliveryState.failed => 'Failed',
    CcbConversationDeliveryState.unconfirmed => 'Check pane',
  };
}

void showBlockedConversationLink(BuildContext context, String text) {
  ScaffoldMessenger.of(
    context,
  ).showSnackBar(SnackBar(content: Text('Open links from raw source: $text')));
}
