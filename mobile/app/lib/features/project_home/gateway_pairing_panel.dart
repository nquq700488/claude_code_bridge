import 'package:flutter/material.dart';

import '../../transport/route_provider.dart';

class GatewayPairingPanel extends StatelessWidget {
  const GatewayPairingPanel({
    required this.gatewayUrlController,
    required this.pairingCodeController,
    required this.deviceNameController,
    required this.routeKind,
    required this.claiming,
    required this.onRouteKindChanged,
    required this.onScan,
    required this.onClaim,
    super.key,
  });

  final TextEditingController gatewayUrlController;
  final TextEditingController pairingCodeController;
  final TextEditingController deviceNameController;
  final RouteProviderKind routeKind;
  final bool claiming;
  final ValueChanged<RouteProviderKind> onRouteKindChanged;
  final VoidCallback onScan;
  final VoidCallback onClaim;

  @override
  Widget build(BuildContext context) {
    return ExpansionTile(
      key: const ValueKey('gateway-pairing-panel'),
      tilePadding: EdgeInsets.zero,
      childrenPadding: const EdgeInsets.only(top: 8, bottom: 8),
      leading: const Icon(Icons.qr_code_scanner),
      title: const Text('Pair Gateway'),
      subtitle: Text(
        gatewayUrlController.text,
        key: const ValueKey('gateway-pairing-status'),
      ),
      children: [
        TextField(
          key: const ValueKey('gateway-url-field'),
          controller: gatewayUrlController,
          keyboardType: TextInputType.url,
          textInputAction: TextInputAction.next,
          decoration: const InputDecoration(
            labelText: 'Gateway URL',
            prefixIcon: Icon(Icons.link),
          ),
        ),
        const SizedBox(height: 8),
        TextField(
          key: const ValueKey('pairing-code-field'),
          controller: pairingCodeController,
          textInputAction: TextInputAction.next,
          decoration: const InputDecoration(
            labelText: 'Pairing code',
            prefixIcon: Icon(Icons.pin),
          ),
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: TextField(
                key: const ValueKey('pairing-device-name-field'),
                controller: deviceNameController,
                textInputAction: TextInputAction.done,
                decoration: const InputDecoration(
                  labelText: 'Device name',
                  prefixIcon: Icon(Icons.phone_android),
                ),
              ),
            ),
            const SizedBox(width: 12),
            SizedBox(
              width: 154,
              child: DropdownButtonFormField<RouteProviderKind>(
                key: ValueKey('pairing-route-kind-field-${routeKind.wireName}'),
                initialValue: routeKind,
                items: [
                  for (final item in RouteProviderKind.values)
                    DropdownMenuItem(
                      value: item,
                      child: Text(_routeProviderLabel(item)),
                    ),
                ],
                isExpanded: true,
                onChanged: (value) {
                  if (value != null) {
                    onRouteKindChanged(value);
                  }
                },
                decoration: const InputDecoration(labelText: 'Route'),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            OutlinedButton.icon(
              key: const ValueKey('gateway-pairing-scan-button'),
              onPressed: claiming ? null : onScan,
              icon: const Icon(Icons.qr_code_scanner),
              label: const Text('Scan QR'),
            ),
            const SizedBox(width: 12),
            FilledButton.icon(
              key: const ValueKey('gateway-pairing-claim-button'),
              onPressed: claiming ? null : onClaim,
              icon:
                  claiming
                      ? const SizedBox.square(
                        dimension: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                      : const Icon(Icons.add_link),
              label: const Text('Claim'),
            ),
          ],
        ),
      ],
    );
  }
}

String _routeProviderLabel(RouteProviderKind kind) {
  return switch (kind) {
    RouteProviderKind.lan => 'LAN',
    RouteProviderKind.tailnet => 'Tailnet',
    RouteProviderKind.cloudflareTunnel => 'Cloudflare',
    RouteProviderKind.relay => 'Relay',
  };
}
