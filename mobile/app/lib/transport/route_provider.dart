enum RouteProviderKind {
  lan('lan'),
  tailnet('tailnet'),
  cloudflareTunnel('cloudflare_tunnel'),
  relay('relay');

  const RouteProviderKind(this.wireName);

  final String wireName;

  static RouteProviderKind fromWireName(String value) {
    final normalized = value.trim();
    for (final kind in values) {
      if (kind.wireName == normalized) {
        return kind;
      }
    }
    throw ArgumentError.value(value, 'value', 'unknown route provider');
  }
}

class RouteProvider {
  const RouteProvider({
    required this.kind,
    required this.gatewayUrl,
    this.websocketUrl,
    this.hostFingerprint,
    this.capabilities = const {},
    this.diagnostics = const {},
  });

  final RouteProviderKind kind;
  final Uri gatewayUrl;
  final Uri? websocketUrl;
  final String? hostFingerprint;
  final Set<String> capabilities;
  final Map<String, String> diagnostics;

  Map<String, Object?> toPairingJson() {
    return {
      'route_provider': kind.wireName,
      'gateway_url': gatewayUrl.toString(),
      if (websocketUrl != null) 'websocket_url': websocketUrl.toString(),
      if (_hasText(hostFingerprint)) 'server_fingerprint': hostFingerprint,
      'capabilities': capabilities.toList()..sort(),
      if (diagnostics.isNotEmpty) 'diagnostics': Map.of(diagnostics),
    };
  }
}

class GatewayHostProfile {
  const GatewayHostProfile({
    required this.hostId,
    required this.deviceId,
    required this.routeProvider,
    required this.scopes,
  });

  final String hostId;
  final String deviceId;
  final RouteProvider routeProvider;
  final Set<String> scopes;

  Map<String, Object?> toJson() {
    return {
      'host_id': hostId,
      'device_id': deviceId,
      'scopes': scopes.toList()..sort(),
      ...routeProvider.toPairingJson(),
    };
  }
}

bool _hasText(String? value) => value != null && value.trim().isNotEmpty;
