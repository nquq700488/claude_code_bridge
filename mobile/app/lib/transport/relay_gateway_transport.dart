import 'dart:async';
import 'dart:collection';
import 'dart:convert';

import '../models/ccb_agent_conversation.dart';
import '../models/ccb_project.dart';
import '../models/ccb_project_lifecycle.dart';
import '../models/ccb_project_view.dart';
import '../models/readable_terminal_history.dart';
import 'gateway_transport.dart';
import 'route_provider.dart';

class RelayGatewayEnvelope {
  const RelayGatewayEnvelope({
    required this.sessionId,
    required this.sequence,
    required this.operation,
    required this.ciphertextB64,
    required this.nonceB64,
    this.schemaVersion = 1,
    this.keyId,
  });

  final int schemaVersion;
  final String sessionId;
  final int sequence;
  final String operation;
  final String ciphertextB64;
  final String nonceB64;
  final String? keyId;

  factory RelayGatewayEnvelope.fromJson(Map<String, Object?> json) {
    return RelayGatewayEnvelope(
      schemaVersion: _int(json['schema_version'], fallback: 1),
      sessionId: _requiredText(json['session_id'], 'session_id'),
      sequence: _requiredPositiveInt(json['seq'], 'seq'),
      operation: _requiredText(json['op'], 'op'),
      ciphertextB64: _requiredBase64Text(
        json['ciphertext_b64'],
        'ciphertext_b64',
      ),
      nonceB64: _requiredBase64Text(json['nonce_b64'], 'nonce_b64'),
      keyId: _optionalText(json['key_id']),
    );
  }

  Map<String, Object?> toJson() {
    return {
      'schema_version': schemaVersion,
      'session_id': sessionId,
      'seq': sequence,
      'op': operation,
      'ciphertext_b64': ciphertextB64,
      'nonce_b64': nonceB64,
      if (_hasText(keyId)) 'key_id': keyId,
    };
  }
}

abstract interface class RelayGatewayEnvelopeCodec {
  RelayGatewayEnvelope seal({
    required String sessionId,
    required int sequence,
    required String operation,
    required Map<String, Object?> payload,
  });
}

class LocalOpaqueRelayEnvelopeCodec implements RelayGatewayEnvelopeCodec {
  const LocalOpaqueRelayEnvelopeCodec({this.keyId = 'local-test-key'});

  final String keyId;

  @override
  RelayGatewayEnvelope seal({
    required String sessionId,
    required int sequence,
    required String operation,
    required Map<String, Object?> payload,
  }) {
    final payloadSize = utf8.encode(jsonEncode(payload)).length;
    final opaque = utf8.encode('opaque-local-relay:$operation:$payloadSize');
    final nonce = utf8.encode('$sessionId:$sequence');
    return RelayGatewayEnvelope(
      sessionId: sessionId,
      sequence: sequence,
      operation: operation,
      ciphertextB64: base64UrlEncode(opaque),
      nonceB64: base64UrlEncode(nonce),
      keyId: keyId,
    );
  }
}

class RelayGatewayTransport implements GatewayTransport {
  RelayGatewayTransport({
    required GatewayTransport inner,
    required this.sessionId,
    RelayGatewayEnvelopeCodec codec = const LocalOpaqueRelayEnvelopeCodec(),
  }) : _inner = inner,
       _codec = codec {
    if (inner.profile.routeProvider.kind != RouteProviderKind.relay) {
      throw ArgumentError.value(
        inner.profile.routeProvider.kind.wireName,
        'inner.profile.routeProvider.kind',
        'RelayGatewayTransport requires a relay profile',
      );
    }
  }

  final GatewayTransport _inner;
  final RelayGatewayEnvelopeCodec _codec;
  final String sessionId;
  final _sealedRequests = <RelayGatewayEnvelope>[];
  int _nextSequence = 1;

  List<RelayGatewayEnvelope> get sealedRequests {
    return UnmodifiableListView(_sealedRequests);
  }

  @override
  GatewayHostProfile get profile => _inner.profile;

  @override
  Future<GatewayHealth> health() {
    return _record('health', const {}, _inner.health);
  }

  @override
  Future<GatewayDevice> device() {
    return _record('device', const {}, _inner.device);
  }

  @override
  Future<List<CcbProject>> listProjects() {
    return _record('list_projects', const {}, _inner.listProjects);
  }

  @override
  Future<CcbProjectView> getProjectView(String projectId) {
    return _record('get_project_view', {'project_id': projectId}, () {
      return _inner.getProjectView(projectId);
    });
  }

  @override
  Future<CcbProjectView> focusAgent({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
  }) {
    return _record(
      'focus_agent',
      {
        'project_id': projectId,
        'agent': agent,
        'namespace_epoch': namespaceEpoch,
      },
      () {
        return _inner.focusAgent(
          projectId: projectId,
          agent: agent,
          namespaceEpoch: namespaceEpoch,
        );
      },
    );
  }

  @override
  Future<CcbProjectView> focusWindow({
    required String projectId,
    required String window,
    required int namespaceEpoch,
  }) {
    return _record(
      'focus_window',
      {
        'project_id': projectId,
        'window': window,
        'namespace_epoch': namespaceEpoch,
      },
      () {
        return _inner.focusWindow(
          projectId: projectId,
          window: window,
          namespaceEpoch: namespaceEpoch,
        );
      },
    );
  }

  @override
  Future<ReadableTerminalHistory?> getReadableTerminalHistory({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
    int maxLines = 200,
  }) {
    return _record(
      'terminal_history',
      {
        'project_id': projectId,
        'agent': agent,
        'namespace_epoch': namespaceEpoch,
        'max_lines': maxLines,
      },
      () {
        return _inner.getReadableTerminalHistory(
          projectId: projectId,
          agent: agent,
          namespaceEpoch: namespaceEpoch,
          maxLines: maxLines,
        );
      },
    );
  }

  @override
  Future<CcbAgentConversation> getAgentConversation({
    required String projectId,
    required String agent,
    required int namespaceEpoch,
    int limit = 50,
    String? cursor,
  }) {
    return _record(
      'agent_conversation',
      {
        'project_id': projectId,
        'agent': agent,
        'namespace_epoch': namespaceEpoch,
        'limit': limit,
        if (_hasText(cursor)) 'cursor': cursor,
      },
      () {
        return _inner.getAgentConversation(
          projectId: projectId,
          agent: agent,
          namespaceEpoch: namespaceEpoch,
          limit: limit,
          cursor: cursor,
        );
      },
    );
  }

  @override
  Future<CcbAgentMessageSubmitResult> submitAgentMessage(
    CcbAgentMessageSubmitRequest request,
  ) {
    return _record('submit_agent_message', request.toJson(), () {
      return _inner.submitAgentMessage(request);
    });
  }

  @override
  Future<CcbProjectLifecycleResult> requestLifecycle({
    required String projectId,
    required CcbLifecycleAction action,
  }) {
    return _record(
      'lifecycle',
      {'project_id': projectId, 'action': action.wireName},
      () {
        return _inner.requestLifecycle(projectId: projectId, action: action);
      },
    );
  }

  @override
  Future<GatewayTerminalHandle> openTerminal(
    GatewayTerminalOpenRequest request,
  ) {
    return _record('open_terminal', request.toJson(), () {
      return _inner.openTerminal(request);
    });
  }

  @override
  Stream<GatewayTerminalFrame> terminalFrames(
    GatewayTerminalHandle handle, {
    int? resumeCursor,
  }) {
    _seal('terminal_frames', {
      'terminal_id': handle.terminalId,
      if (resumeCursor != null) 'resume_cursor': resumeCursor,
    });
    return _inner.terminalFrames(handle, resumeCursor: resumeCursor);
  }

  @override
  Future<void> sendTerminalFrame(
    GatewayTerminalHandle handle,
    GatewayTerminalFrame frame,
  ) {
    return _record(
      'send_terminal_frame',
      {'terminal_id': handle.terminalId, 'frame': frame.toJson()},
      () {
        return _inner.sendTerminalFrame(handle, frame);
      },
    );
  }

  @override
  Future<GatewayFileUploadResult> uploadFile({
    required String projectId,
    required String agentName,
    required String fileName,
    required String mimeType,
    required List<int> bytes,
  }) {
    return _record(
      'upload_file',
      {
        'project_id': projectId,
        'agent': agentName,
        'file_name': fileName,
        'mime_type': mimeType,
        'size_bytes': bytes.length,
      },
      () {
        return _inner.uploadFile(
          projectId: projectId,
          agentName: agentName,
          fileName: fileName,
          mimeType: mimeType,
          bytes: bytes,
        );
      },
    );
  }

  @override
  Future<List<int>> downloadFile({
    required String projectId,
    required String agentName,
    required String fileId,
  }) {
    return _record(
      'download_file',
      {'project_id': projectId, 'agent': agentName, 'file_id': fileId},
      () {
        return _inner.downloadFile(
          projectId: projectId,
          agentName: agentName,
          fileId: fileId,
        );
      },
    );
  }

  Future<T> _record<T>(
    String operation,
    Map<String, Object?> payload,
    Future<T> Function() action,
  ) {
    _seal(operation, payload);
    return action();
  }

  void _seal(String operation, Map<String, Object?> payload) {
    final envelope = _codec.seal(
      sessionId: sessionId,
      sequence: _nextSequence,
      operation: operation,
      payload: payload,
    );
    _nextSequence += 1;
    _sealedRequests.add(envelope);
  }
}

String _requiredText(Object? value, String name) {
  final text = _optionalText(value);
  if (!_hasText(text)) {
    throw FormatException('relay envelope missing text field: $name');
  }
  return text!;
}

String _requiredBase64Text(Object? value, String name) {
  final text = _requiredText(value, name);
  try {
    base64Url.decode(text);
  } on FormatException catch (error) {
    throw FormatException('relay envelope invalid base64 field: $name', error);
  }
  return text;
}

String? _optionalText(Object? value) {
  final text = (value ?? '').toString().trim();
  return text.isEmpty ? null : text;
}

int _int(Object? value, {required int fallback}) {
  if (value is int) {
    return value;
  }
  return int.tryParse((value ?? '').toString()) ?? fallback;
}

int _requiredPositiveInt(Object? value, String name) {
  final parsed = value is int ? value : int.tryParse((value ?? '').toString());
  if (parsed == null || parsed < 1) {
    throw FormatException('relay envelope missing positive integer: $name');
  }
  return parsed;
}

bool _hasText(String? value) => value != null && value.trim().isNotEmpty;
