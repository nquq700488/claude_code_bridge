import 'ccb_content_item.dart';

enum CcbConversationItemKind {
  userMessage,
  agentReply,
  callbackRequest,
  commsItem,
  statusEvent,
  toolEvent,
  artifactCard,
  terminalHistoryBlock,
  systemNotice,
}

enum CcbConversationDeliveryState { pending, sent, failed, unconfirmed }

enum CcbMessageAttachmentKind { image, document }

enum CcbMessageAttachmentState {
  queued,
  uploading,
  processing,
  failed,
  available,
  downloaded,
}

extension CcbConversationItemKindWire on CcbConversationItemKind {
  String get wireName {
    return switch (this) {
      CcbConversationItemKind.userMessage => 'user_message',
      CcbConversationItemKind.agentReply => 'agent_reply',
      CcbConversationItemKind.callbackRequest => 'callback_request',
      CcbConversationItemKind.commsItem => 'comms_item',
      CcbConversationItemKind.statusEvent => 'status_event',
      CcbConversationItemKind.toolEvent => 'tool_event',
      CcbConversationItemKind.artifactCard => 'artifact_card',
      CcbConversationItemKind.terminalHistoryBlock => 'terminal_history_block',
      CcbConversationItemKind.systemNotice => 'system_notice',
    };
  }
}

extension CcbConversationDeliveryStateWire on CcbConversationDeliveryState {
  String get wireName {
    return switch (this) {
      CcbConversationDeliveryState.pending => 'pending',
      CcbConversationDeliveryState.sent => 'sent',
      CcbConversationDeliveryState.failed => 'failed',
      CcbConversationDeliveryState.unconfirmed => 'unconfirmed',
    };
  }
}

extension CcbMessageAttachmentKindWire on CcbMessageAttachmentKind {
  String get wireName {
    return switch (this) {
      CcbMessageAttachmentKind.image => 'image',
      CcbMessageAttachmentKind.document => 'document',
    };
  }
}

extension CcbMessageAttachmentStateWire on CcbMessageAttachmentState {
  String get wireName {
    return switch (this) {
      CcbMessageAttachmentState.queued => 'queued',
      CcbMessageAttachmentState.uploading => 'uploading',
      CcbMessageAttachmentState.processing => 'processing',
      CcbMessageAttachmentState.failed => 'failed',
      CcbMessageAttachmentState.available => 'available',
      CcbMessageAttachmentState.downloaded => 'downloaded',
    };
  }
}

CcbConversationItemKind ccbConversationItemKindFromWireName(Object? value) {
  return switch (_text(value)) {
    'user_message' => CcbConversationItemKind.userMessage,
    'agent_reply' => CcbConversationItemKind.agentReply,
    'callback_request' => CcbConversationItemKind.callbackRequest,
    'comms_item' => CcbConversationItemKind.commsItem,
    'status_event' => CcbConversationItemKind.statusEvent,
    'tool_event' => CcbConversationItemKind.toolEvent,
    'artifact_card' => CcbConversationItemKind.artifactCard,
    'terminal_history_block' => CcbConversationItemKind.terminalHistoryBlock,
    'system_notice' => CcbConversationItemKind.systemNotice,
    _ => CcbConversationItemKind.systemNotice,
  };
}

CcbConversationDeliveryState? ccbConversationDeliveryStateFromWireName(
  Object? value,
) {
  return switch (_text(value)) {
    'pending' => CcbConversationDeliveryState.pending,
    'sent' => CcbConversationDeliveryState.sent,
    'failed' => CcbConversationDeliveryState.failed,
    'unconfirmed' => CcbConversationDeliveryState.unconfirmed,
    _ => null,
  };
}

CcbMessageAttachmentKind ccbMessageAttachmentKindFromWireName(Object? value) {
  return switch (_text(value)) {
    'image' => CcbMessageAttachmentKind.image,
    _ => CcbMessageAttachmentKind.document,
  };
}

CcbMessageAttachmentState ccbMessageAttachmentStateFromWireName(
  Object? value, {
  CcbMessageAttachmentState fallback = CcbMessageAttachmentState.available,
}) {
  return switch (_text(value)) {
    'queued' => CcbMessageAttachmentState.queued,
    'uploading' => CcbMessageAttachmentState.uploading,
    'processing' => CcbMessageAttachmentState.processing,
    'failed' => CcbMessageAttachmentState.failed,
    'downloaded' => CcbMessageAttachmentState.downloaded,
    'available' => CcbMessageAttachmentState.available,
    _ => fallback,
  };
}

class CcbConversationItem {
  const CcbConversationItem({
    required this.id,
    required this.agentName,
    required this.kind,
    required this.title,
    required this.body,
    this.format = 'plain',
    this.state,
    this.contentId,
    this.source,
    this.attachments = const [],
  });

  final String id;
  final String agentName;
  final CcbConversationItemKind kind;
  final String title;
  final String body;
  final String format;
  final CcbConversationDeliveryState? state;
  final String? contentId;
  final String? source;
  final List<CcbMessageAttachment> attachments;

  factory CcbConversationItem.userMessage({
    required String id,
    required String agentName,
    required String body,
    List<CcbMessageAttachment> attachments = const [],
    CcbConversationDeliveryState state = CcbConversationDeliveryState.pending,
  }) {
    return CcbConversationItem(
      id: id,
      agentName: agentName,
      kind: CcbConversationItemKind.userMessage,
      title: 'You',
      body: body,
      format: 'markdown',
      state: state,
      source: 'mobile',
      attachments: attachments,
    );
  }

  factory CcbConversationItem.agentReplyFromContent({
    required String agentName,
    required CcbContentItem content,
  }) {
    return CcbConversationItem(
      id: 'reply-${content.id}',
      agentName: agentName,
      kind: CcbConversationItemKind.agentReply,
      title: content.title ?? 'Agent reply',
      body: content.text,
      format: content.format,
      contentId: content.id,
      source: content.source,
      attachments: const [],
    );
  }

  factory CcbConversationItem.status({
    required String id,
    required String agentName,
    required String title,
    required String body,
  }) {
    return CcbConversationItem(
      id: id,
      agentName: agentName,
      kind: CcbConversationItemKind.statusEvent,
      title: title,
      body: body,
      source: 'project_view',
      attachments: const [],
    );
  }

  factory CcbConversationItem.callback({
    required String id,
    required String agentName,
    required String body,
  }) {
    return CcbConversationItem(
      id: id,
      agentName: agentName,
      kind: CcbConversationItemKind.callbackRequest,
      title: 'Callback',
      body: body,
      source: 'project_view',
      attachments: const [],
    );
  }

  factory CcbConversationItem.terminalHistory({required String agentName}) {
    return CcbConversationItem(
      id: 'terminal-history-$agentName',
      agentName: agentName,
      kind: CcbConversationItemKind.terminalHistoryBlock,
      title: 'Readable terminal history',
      body: 'Best-effort tmux scrollback for this agent.',
      source: 'tmux_scrollback',
      attachments: const [],
    );
  }

  factory CcbConversationItem.fromJson(Map<String, Object?> json) {
    final kind = ccbConversationItemKindFromWireName(json['kind']);
    return CcbConversationItem(
      id: _text(json['id'], fallback: 'conversation-item'),
      agentName:
          _optionalText(json['agent']) ??
          _optionalText(json['agent_name']) ??
          '',
      kind: kind,
      title:
          _optionalText(json['title']) ??
          _defaultTitleForConversationKind(kind),
      body: _optionalText(json['body']) ?? _text(json['text']),
      format: _text(json['format'], fallback: 'plain'),
      state: ccbConversationDeliveryStateFromWireName(json['state']),
      contentId:
          _optionalText(json['content_id']) ?? _optionalText(json['contentId']),
      source: _optionalText(json['source']),
      attachments: [
        if (json['attachments'] is Iterable)
          for (final item in json['attachments'] as Iterable)
            if (item is Map)
              CcbMessageAttachment.fromJson({
                for (final entry in item.entries)
                  entry.key.toString(): entry.value,
              }),
      ],
    );
  }

  Map<String, Object?> toJson() {
    return {
      'id': id,
      'agent': agentName,
      'kind': kind.wireName,
      'title': title,
      'body': body,
      'format': format,
      if (state != null) 'state': state!.wireName,
      if (contentId != null) 'content_id': contentId,
      if (source != null) 'source': source,
      if (attachments.isNotEmpty)
        'attachments': [for (final a in attachments) a.toJson()],
    };
  }

  CcbConversationItem copyWith({
    CcbConversationDeliveryState? state,
    List<CcbMessageAttachment>? attachments,
  }) {
    return CcbConversationItem(
      id: id,
      agentName: agentName,
      kind: kind,
      title: title,
      body: body,
      format: format,
      state: state ?? this.state,
      contentId: contentId,
      source: source,
      attachments: attachments ?? this.attachments,
    );
  }
}

String _defaultTitleForConversationKind(CcbConversationItemKind kind) {
  return switch (kind) {
    CcbConversationItemKind.userMessage => 'You',
    CcbConversationItemKind.agentReply => 'Agent reply',
    CcbConversationItemKind.callbackRequest => 'Callback',
    CcbConversationItemKind.commsItem => 'Comms',
    CcbConversationItemKind.statusEvent => 'Status',
    CcbConversationItemKind.toolEvent => 'Tool',
    CcbConversationItemKind.artifactCard => 'Artifact',
    CcbConversationItemKind.terminalHistoryBlock => 'Readable terminal history',
    CcbConversationItemKind.systemNotice => 'System',
  };
}

String _text(Object? value, {String fallback = ''}) {
  final text = (value ?? '').toString().trim();
  return text.isEmpty ? fallback : text;
}

String? _optionalText(Object? value) {
  final text = _text(value);
  return text.isEmpty ? null : text;
}

class CcbMessageAttachment {
  const CcbMessageAttachment({
    required this.fileId,
    required this.fileName,
    required this.mimeType,
    required this.sizeBytes,
    this.kind,
    this.state = CcbMessageAttachmentState.available,
    this.localPath,
    this.errorMessage,
  });

  final String fileId;
  final String fileName;
  final String mimeType;
  final int sizeBytes;
  final CcbMessageAttachmentKind? kind;
  final CcbMessageAttachmentState state;
  final String? localPath;
  final String? errorMessage;

  CcbMessageAttachmentKind get effectiveKind {
    final explicit = kind;
    if (explicit != null) {
      return explicit;
    }
    return mimeType.startsWith('image/')
        ? CcbMessageAttachmentKind.image
        : CcbMessageAttachmentKind.document;
  }

  bool get isImage => effectiveKind == CcbMessageAttachmentKind.image;

  CcbMessageAttachment copyWith({
    String? fileId,
    String? fileName,
    String? mimeType,
    int? sizeBytes,
    CcbMessageAttachmentKind? kind,
    CcbMessageAttachmentState? state,
    String? localPath,
    String? errorMessage,
    bool clearLocalPath = false,
    bool clearErrorMessage = false,
  }) {
    return CcbMessageAttachment(
      fileId: fileId ?? this.fileId,
      fileName: fileName ?? this.fileName,
      mimeType: mimeType ?? this.mimeType,
      sizeBytes: sizeBytes ?? this.sizeBytes,
      kind: kind ?? this.kind,
      state: state ?? this.state,
      localPath: clearLocalPath ? null : localPath ?? this.localPath,
      errorMessage:
          clearErrorMessage ? null : errorMessage ?? this.errorMessage,
    );
  }

  factory CcbMessageAttachment.fromJson(Map<String, Object?> json) {
    final mimeType = _text(json['mime_type']);
    return CcbMessageAttachment(
      fileId:
          _optionalText(json['file_id']) ??
          _optionalText(json['id']) ??
          _optionalText(json['attachment_id']) ??
          '',
      fileName:
          _optionalText(json['file_name']) ??
          _optionalText(json['filename']) ??
          'attachment',
      mimeType: mimeType.isEmpty ? 'application/octet-stream' : mimeType,
      sizeBytes: int.tryParse((json['size_bytes'] ?? '').toString()) ?? 0,
      kind:
          json.containsKey('kind')
              ? ccbMessageAttachmentKindFromWireName(json['kind'])
              : null,
      state: ccbMessageAttachmentStateFromWireName(json['state']),
      localPath: _optionalText(json['local_path']),
      errorMessage: _optionalText(json['error']),
    );
  }

  Map<String, Object?> toJson() {
    return {
      'file_id': fileId,
      'file_name': fileName,
      'mime_type': mimeType,
      'size_bytes': sizeBytes,
      'kind': effectiveKind.wireName,
      'state': state.wireName,
      if (errorMessage != null) 'error': errorMessage,
    };
  }

  Map<String, Object?> toSubmitJson() {
    return {
      'file_id': fileId,
      'file_name': fileName,
      'mime_type': mimeType,
      'size_bytes': sizeBytes,
      'kind': effectiveKind.wireName,
    };
  }
}
