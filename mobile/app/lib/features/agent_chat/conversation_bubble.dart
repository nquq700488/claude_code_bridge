import 'package:flutter/material.dart';

import '../../models/ccb_conversation_item.dart';
import 'conversation_item_presentation.dart';

class ConversationBubble extends StatelessWidget {
  const ConversationBubble({
    required this.item,
    required this.expanded,
    required this.onToggleExpanded,
    this.child,
    this.onRetry,
    this.onDownloadAttachment,
    this.downloadingAttachmentIds = const {},
    this.downloadedAttachmentIds = const {},
    super.key,
  });

  final CcbConversationItem item;
  final bool expanded;
  final ValueChanged<String> onToggleExpanded;
  final Widget? child;
  final VoidCallback? onRetry;
  final ValueChanged<CcbMessageAttachment>? onDownloadAttachment;
  final Set<String> downloadingAttachmentIds;
  final Set<String> downloadedAttachmentIds;

  void _toggleExpanded() {
    onToggleExpanded(item.id);
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final isUser = item.kind == CcbConversationItemKind.userMessage;
    final collapsible = conversationShouldCollapse(
      item,
      hasCustomChild: child != null,
    );
    final sourceLabel = visibleConversationSourceLabel(item);
    final body = child ?? ConversationBody(
      item: item,
      onDownloadArtifact: onDownloadAttachment == null ? null : (fileId) {
        final attachment = item.attachments.where((a) => a.fileId == fileId).firstOrNull;
        if (attachment != null) {
          onDownloadAttachment!(attachment);
        }
      },
    );
    final bubbleColor =
        isUser ? colorScheme.primaryContainer : colorScheme.surfaceContainerLow;
    final borderColor = switch (item.state) {
      CcbConversationDeliveryState.failed => colorScheme.error,
      CcbConversationDeliveryState.unconfirmed => colorScheme.tertiary,
      _ => colorScheme.outlineVariant,
    };
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 720),
        child: Material(
          key: ValueKey('conversation-item-${item.id}'),
          color: bubbleColor,
          clipBehavior: Clip.antiAlias,
          shape: RoundedRectangleBorder(
            side: BorderSide(color: borderColor),
            borderRadius: BorderRadius.circular(8),
          ),
          child: InkWell(
            onTap: collapsible ? _toggleExpanded : null,
            child: Padding(
              padding: const EdgeInsets.all(10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(conversationIcon(item.kind), size: 16),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          item.title,
                          style: Theme.of(context).textTheme.titleSmall,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      if (item.state != null)
                        ConversationStateChip(
                          key: ValueKey('conversation-state-${item.id}'),
                          state: item.state!,
                        ),
                      if (collapsible)
                        IconButton(
                          key: ValueKey('conversation-expand-${item.id}'),
                          visualDensity: VisualDensity.compact,
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints.tightFor(
                            width: 32,
                            height: 32,
                          ),
                          tooltip:
                              expanded ? 'Collapse message' : 'Expand message',
                          onPressed: _toggleExpanded,
                          icon: Icon(
                            expanded ? Icons.expand_less : Icons.expand_more,
                          ),
                        ),
                    ],
                  ),
                  if (sourceLabel != null) ...[
                    const SizedBox(height: 1),
                    Text(
                      sourceLabel,
                      style: Theme.of(context).textTheme.bodySmall,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                  const SizedBox(height: 6),
                  if (collapsible && !expanded)
                    ConversationPreview(item: item)
                  else
                    body,
                  if (item.attachments.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    ConversationAttachmentList(
                      item: item,
                      onDownloadAttachment: onDownloadAttachment,
                      downloadingAttachmentIds: downloadingAttachmentIds,
                      downloadedAttachmentIds: downloadedAttachmentIds,
                    ),
                  ],
                  if (onRetry != null) ...[
                    const SizedBox(height: 6),
                    Align(
                      alignment: Alignment.centerRight,
                      child: TextButton.icon(
                        key: ValueKey('retry-message-${item.id}'),
                        onPressed: onRetry,
                        icon: const Icon(Icons.refresh),
                        label: const Text('Retry'),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class ConversationAttachmentList extends StatelessWidget {
  const ConversationAttachmentList({
    required this.item,
    required this.onDownloadAttachment,
    required this.downloadingAttachmentIds,
    required this.downloadedAttachmentIds,
    super.key,
  });

  final CcbConversationItem item;
  final ValueChanged<CcbMessageAttachment>? onDownloadAttachment;
  final Set<String> downloadingAttachmentIds;
  final Set<String> downloadedAttachmentIds;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      key: ValueKey('conversation-attachment-list-${item.id}'),
      spacing: 8,
      runSpacing: 4,
      children: [
        for (final attachment in item.attachments)
          ConversationAttachmentChip(
            attachment: _withDownloadState(attachment),
            onPressed:
                onDownloadAttachment == null
                    ? null
                    : () => onDownloadAttachment!(attachment),
          ),
      ],
    );
  }

  CcbMessageAttachment _withDownloadState(CcbMessageAttachment attachment) {
    if (downloadingAttachmentIds.contains(attachment.fileId)) {
      return attachment.copyWith(state: CcbMessageAttachmentState.uploading);
    }
    if (downloadedAttachmentIds.contains(attachment.fileId)) {
      return attachment.copyWith(state: CcbMessageAttachmentState.downloaded);
    }
    return attachment;
  }
}

class ConversationAttachmentChip extends StatelessWidget {
  const ConversationAttachmentChip({
    required this.attachment,
    required this.onPressed,
    super.key,
  });

  final CcbMessageAttachment attachment;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final failed = attachment.state == CcbMessageAttachmentState.failed;
    final busy =
        attachment.state == CcbMessageAttachmentState.queued ||
        attachment.state == CcbMessageAttachmentState.uploading ||
        attachment.state == CcbMessageAttachmentState.processing;
    final downloaded = attachment.state == CcbMessageAttachmentState.downloaded;
    final label = StringBuffer(attachment.fileName);
    if (attachment.sizeBytes > 0) {
      label.write(' (${_formatBytes(attachment.sizeBytes)})');
    }
    final errorMessage = attachment.errorMessage;
    if (failed && errorMessage != null) {
      label.write(' - $errorMessage');
    }
    return ActionChip(
      key: ValueKey('conversation-attachment-chip-${attachment.fileId}'),
      avatar:
          busy
              ? SizedBox.square(
                key: ValueKey('agent-attachment-progress-${attachment.fileId}'),
                dimension: 16,
                child: const CircularProgressIndicator(strokeWidth: 2),
              )
              : Icon(
                key: ValueKey(
                  downloaded
                      ? 'conversation-attachment-open-${attachment.fileId}'
                      : 'conversation-attachment-download-${attachment.fileId}',
                ),
                failed
                    ? Icons.error_outline
                    : downloaded
                    ? Icons.folder_open
                    : attachment.isImage
                    ? Icons.image_outlined
                    : Icons.description_outlined,
                color: failed ? theme.colorScheme.error : null,
                size: 16,
              ),
      label: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 220),
        child: Text(label.toString(), overflow: TextOverflow.ellipsis),
      ),
      onPressed: busy ? null : onPressed,
      tooltip:
          failed
              ? errorMessage
              : downloaded
              ? 'Open attachment'
              : 'Download attachment',
    );
  }
}

String _formatBytes(int bytes) {
  if (bytes >= 1024 * 1024) {
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }
  if (bytes >= 1024) {
    return '${(bytes / 1024).toStringAsFixed(1)} KB';
  }
  return '$bytes B';
}
