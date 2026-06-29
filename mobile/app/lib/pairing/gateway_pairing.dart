import 'dart:convert';
import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../transport/route_provider.dart';

class GatewayPairingException implements Exception {
  GatewayPairingException(this.uri, this.statusCode, this.message);

  final Uri uri;
  final int statusCode;
  final String message;

  @override
  String toString() {
    return 'GatewayPairingException($statusCode $uri: $message)';
  }
}

class GatewayPairingPayload {
  const GatewayPairingPayload({
    required this.pairingCode,
    required this.claimEndpoint,
    required this.routeProvider,
    required this.gatewayUrl,
    required this.scopes,
    this.projectId,
    this.expiresAt,
  });

  final String pairingCode;
  final Uri claimEndpoint;
  final RouteProviderKind routeProvider;
  final Uri gatewayUrl;
  final Set<String> scopes;
  final String? projectId;
  final DateTime? expiresAt;

  factory GatewayPairingPayload.fromJson(Map<String, Object?> json) {
    return GatewayPairingPayload(
      pairingCode: _requiredText(json['pairing_code'], 'pairing_code'),
      claimEndpoint: _requiredUri(json['claim_endpoint'], 'claim_endpoint'),
      routeProvider: RouteProviderKind.fromWireName(
        _requiredText(json['route_provider'], 'route_provider'),
      ),
      gatewayUrl: _requiredUri(json['gateway_url'], 'gateway_url'),
      scopes: _stringSet(json['scopes']),
      projectId: _optionalText(json['project_id']),
      expiresAt: _optionalDateTime(json['expires_at']),
    );
  }

  factory GatewayPairingPayload.fromQrText(String text) {
    final trimmed = text.trim();
    if (trimmed.isEmpty) {
      throw const FormatException('pairing QR payload is empty');
    }
    final decoded = jsonDecode(trimmed);
    if (decoded is Map) {
      return GatewayPairingPayload.fromJson({
        for (final entry in decoded.entries) entry.key.toString(): entry.value,
      });
    }
    throw const FormatException('pairing QR payload must be a JSON object');
  }

  Map<String, Object?> toJson() {
    return {
      'pairing_code': pairingCode,
      'claim_endpoint': claimEndpoint.toString(),
      'route_provider': routeProvider.wireName,
      'gateway_url': gatewayUrl.toString(),
      'scopes': scopes.toList()..sort(),
      if (_hasText(projectId)) 'project_id': projectId,
      if (expiresAt != null) 'expires_at': expiresAt!.toUtc().toIso8601String(),
    };
  }
}

class GatewayPairedHost {
  const GatewayPairedHost({
    required this.profile,
    required this.deviceToken,
    this.projectId,
    this.createdAt,
  });

  final GatewayHostProfile profile;
  final String deviceToken;
  final String? projectId;
  final DateTime? createdAt;

  factory GatewayPairedHost.fromClaimJson(
    Map<String, Object?> json, {
    required GatewayPairingPayload pairing,
  }) {
    final hostProfile = _map(json['host_profile']);
    final device = _map(json['device']);
    final deviceToken = _requiredText(json['device_token'], 'device_token');
    final deviceId =
        _optionalText(hostProfile['device_id']) ??
        _requiredText(device['device_id'], 'device.device_id');
    final projectId =
        _optionalText(hostProfile['project_id']) ?? pairing.projectId;
    final hostId =
        _optionalText(hostProfile['host_id']) ??
        projectId ??
        _requiredText(device['project_id'], 'device.project_id');
    final routeProvider = RouteProvider(
      kind: RouteProviderKind.fromWireName(
        _optionalText(hostProfile['route_provider']) ??
            pairing.routeProvider.wireName,
      ),
      gatewayUrl:
          _optionalUri(hostProfile['gateway_url']) ?? pairing.gatewayUrl,
      websocketUrl: _optionalUri(hostProfile['websocket_url']),
      hostFingerprint: _optionalText(hostProfile['server_fingerprint']),
      capabilities: _stringSet(hostProfile['capabilities']),
      diagnostics: _stringMap(hostProfile['diagnostics']),
    );
    return GatewayPairedHost(
      profile: GatewayHostProfile(
        hostId: hostId,
        deviceId: deviceId,
        routeProvider: routeProvider,
        scopes:
            _stringSet(hostProfile['scopes']).isEmpty
                ? pairing.scopes
                : _stringSet(hostProfile['scopes']),
      ),
      deviceToken: deviceToken,
      projectId: projectId,
      createdAt: _optionalDateTime(device['created_at']),
    );
  }

  factory GatewayPairedHost.fromSecureJson(Map<String, Object?> json) {
    final profileJson = _map(json['profile']);
    final routeProvider = RouteProvider(
      kind: RouteProviderKind.fromWireName(
        _requiredText(profileJson['route_provider'], 'route_provider'),
      ),
      gatewayUrl: _requiredUri(profileJson['gateway_url'], 'gateway_url'),
      websocketUrl: _optionalUri(profileJson['websocket_url']),
      hostFingerprint: _optionalText(profileJson['server_fingerprint']),
      capabilities: _stringSet(profileJson['capabilities']),
      diagnostics: _stringMap(profileJson['diagnostics']),
    );
    return GatewayPairedHost(
      profile: GatewayHostProfile(
        hostId: _requiredText(profileJson['host_id'], 'host_id'),
        deviceId: _requiredText(profileJson['device_id'], 'device_id'),
        routeProvider: routeProvider,
        scopes: _stringSet(profileJson['scopes']),
      ),
      deviceToken: _requiredText(json['device_token'], 'device_token'),
      projectId: _optionalText(json['project_id']),
      createdAt: _optionalDateTime(json['created_at']),
    );
  }

  Map<String, Object?> toSecureJson() {
    return {
      'schema_version': 1,
      'profile': profile.toJson(),
      'device_token': deviceToken,
      if (_hasText(projectId)) 'project_id': projectId,
      if (createdAt != null) 'created_at': createdAt!.toUtc().toIso8601String(),
    };
  }
}

class GatewayPairingClient {
  GatewayPairingClient({
    HttpClient? httpClient,
    Duration timeout = const Duration(seconds: 5),
  }) : _httpClient = httpClient ?? HttpClient(),
       _timeout = timeout;

  final HttpClient _httpClient;
  final Duration _timeout;

  Future<GatewayPairedHost> claim({
    required GatewayPairingPayload pairing,
    required String deviceName,
    String? deviceId,
  }) async {
    final json = await _postJson(pairing.claimEndpoint, {
      'pairing_code': pairing.pairingCode,
      'device_name': deviceName,
      if (_hasText(deviceId)) 'device_id': deviceId,
    });
    return GatewayPairedHost.fromClaimJson(json, pairing: pairing);
  }

  Future<GatewayPairedHost> claimAndStore({
    required GatewayPairingPayload pairing,
    required String deviceName,
    required GatewayHostProfileStore store,
    String? deviceId,
  }) async {
    final paired = await claim(
      pairing: pairing,
      deviceName: deviceName,
      deviceId: deviceId,
    );
    await store.save(paired);
    return paired;
  }

  void close({bool force = false}) {
    _httpClient.close(force: force);
  }

  Future<Map<String, Object?>> _postJson(
    Uri uri,
    Map<String, Object?> payload,
  ) async {
    final request = await _httpClient.postUrl(uri).timeout(_timeout);
    request.headers.set(HttpHeaders.acceptHeader, 'application/json');
    request.headers.contentType = ContentType.json;
    final bodyBytes = utf8.encode(jsonEncode(payload));
    request.contentLength = bodyBytes.length;
    request.add(bodyBytes);
    final response = await request.close().timeout(_timeout);
    final body = await utf8.decodeStream(response).timeout(_timeout);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw GatewayPairingException(uri, response.statusCode, body);
    }
    final decoded = jsonDecode(body);
    if (decoded is Map) {
      return {
        for (final entry in decoded.entries) entry.key.toString(): entry.value,
      };
    }
    throw FormatException('pairing response is not a JSON object: $uri');
  }
}

abstract interface class GatewaySecureStore {
  Future<String?> read({required String key});

  Future<void> write({required String key, required String value});

  Future<void> delete({required String key});
}

class FlutterGatewaySecureStore implements GatewaySecureStore {
  FlutterGatewaySecureStore({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  @override
  Future<String?> read({required String key}) {
    return _storage.read(key: key);
  }

  @override
  Future<void> write({required String key, required String value}) {
    return _storage.write(key: key, value: value);
  }

  @override
  Future<void> delete({required String key}) {
    return _storage.delete(key: key);
  }
}

class GatewayHostProfileStore {
  GatewayHostProfileStore({GatewaySecureStore? secureStore})
    : _secureStore = secureStore ?? FlutterGatewaySecureStore();

  static const _indexKey = 'ccb_mobile.gateway_profiles.index';
  static const _profilePrefix = 'ccb_mobile.gateway_profiles.profile.';

  final GatewaySecureStore _secureStore;

  Future<void> save(GatewayPairedHost host) async {
    final key = _profileKey(host.profile.hostId, host.profile.deviceId);
    await _secureStore.write(key: key, value: jsonEncode(host.toSecureJson()));
    final keys = await _readIndex();
    if (!keys.contains(key)) {
      keys.add(key);
      await _writeIndex(keys);
    }
  }

  Future<GatewayPairedHost?> read({
    required String hostId,
    required String deviceId,
  }) async {
    return _readProfile(_profileKey(hostId, deviceId));
  }

  Future<List<GatewayPairedHost>> list() async {
    final result = <GatewayPairedHost>[];
    for (final key in await _readIndex()) {
      final profile = await _readProfile(key);
      if (profile != null) {
        result.add(profile);
      }
    }
    return result;
  }

  Future<void> delete({
    required String hostId,
    required String deviceId,
  }) async {
    final key = _profileKey(hostId, deviceId);
    await _secureStore.delete(key: key);
    final keys = await _readIndex();
    keys.remove(key);
    await _writeIndex(keys);
  }

  Future<GatewayPairedHost?> _readProfile(String key) async {
    final raw = await _secureStore.read(key: key);
    if (!_hasText(raw)) {
      return null;
    }
    final decoded = jsonDecode(raw!);
    if (decoded is Map) {
      return GatewayPairedHost.fromSecureJson({
        for (final entry in decoded.entries) entry.key.toString(): entry.value,
      });
    }
    throw FormatException('stored gateway profile is not a JSON object');
  }

  Future<List<String>> _readIndex() async {
    final raw = await _secureStore.read(key: _indexKey);
    if (!_hasText(raw)) {
      return [];
    }
    final decoded = jsonDecode(raw!);
    if (decoded is Iterable) {
      return [for (final item in decoded) item.toString()];
    }
    return [];
  }

  Future<void> _writeIndex(List<String> keys) {
    final unique = keys.toSet().toList()..sort();
    return _secureStore.write(key: _indexKey, value: jsonEncode(unique));
  }

  static String _profileKey(String hostId, String deviceId) {
    final encoded = base64Url
        .encode(utf8.encode('$hostId\n$deviceId'))
        .replaceAll('=', '');
    return '$_profilePrefix$encoded';
  }
}

Map<String, Object?> _map(Object? value) {
  if (value is Map) {
    return {
      for (final entry in value.entries) entry.key.toString(): entry.value,
    };
  }
  return const {};
}

Map<String, String> _stringMap(Object? value) {
  if (value is Map) {
    return {
      for (final entry in value.entries)
        entry.key.toString(): entry.value.toString(),
    };
  }
  return const {};
}

Set<String> _stringSet(Object? value) {
  if (value is Iterable) {
    return {for (final item in value) item.toString()};
  }
  return const {};
}

String _requiredText(Object? value, String field) {
  final text = _optionalText(value);
  if (!_hasText(text)) {
    throw FormatException('pairing response missing $field');
  }
  return text!;
}

String? _optionalText(Object? value) {
  final text = (value ?? '').toString().trim();
  return text.isEmpty ? null : text;
}

Uri _requiredUri(Object? value, String field) {
  final uri = _optionalUri(value);
  if (uri == null) {
    throw FormatException('pairing response missing $field');
  }
  return uri;
}

Uri? _optionalUri(Object? value) {
  final text = _optionalText(value);
  if (text == null) {
    return null;
  }
  final uri = Uri.tryParse(text);
  if (uri == null || !uri.hasScheme) {
    throw FormatException('invalid URI: $text');
  }
  return uri;
}

DateTime? _optionalDateTime(Object? value) {
  final parsed = DateTime.tryParse((value ?? '').toString());
  return parsed?.toUtc();
}

bool _hasText(String? value) => value != null && value.trim().isNotEmpty;
