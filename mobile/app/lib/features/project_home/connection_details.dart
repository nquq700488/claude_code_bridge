import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../../app/runtime_mode.dart';
import '../../models/ccb_project_lifecycle.dart';
import '../../models/ccb_project_view.dart';
import '../../pairing/gateway_pairing.dart';
import '../../transport/gateway_route_diagnostics.dart';
import '../../transport/route_provider.dart';
import 'gateway_pairing_panel.dart';
import 'project_lifecycle_panel.dart';
import 'runtime_mode_panel.dart';

class ConnectionDetailsScreen extends StatelessWidget {
  const ConnectionDetailsScreen({required this.panel, super.key});

  final Widget panel;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Diagnostics')),
      body: ListView(
        key: const ValueKey('connection-details-scroll'),
        padding: const EdgeInsets.all(16),
        children: [panel],
      ),
    );
  }
}

class ConnectionDetailsPanel extends StatelessWidget {
  const ConnectionDetailsPanel({
    required this.view,
    required this.mode,
    required this.profiles,
    required this.selectedProfile,
    required this.routeDiagnostics,
    required this.lifecycleResultListenable,
    required this.loadingProfiles,
    required this.checkingRoute,
    required this.runningLifecycleActionListenable,
    required this.gatewayUrlController,
    required this.pairingCodeController,
    required this.deviceNameController,
    required this.routeKind,
    required this.claiming,
    required this.onModeChanged,
    required this.onProfileSelected,
    required this.onCheckRoute,
    required this.onLifecycleAction,
    required this.onRouteKindChanged,
    required this.onScan,
    required this.onClaim,
    this.initiallyExpanded = false,
    super.key,
  });

  final CcbProjectView view;
  final AppRuntimeMode mode;
  final List<GatewayPairedHost> profiles;
  final GatewayPairedHost? selectedProfile;
  final GatewayRouteDiagnosticReport? routeDiagnostics;
  final ValueListenable<CcbProjectLifecycleResult?> lifecycleResultListenable;
  final bool loadingProfiles;
  final bool checkingRoute;
  final ValueListenable<CcbLifecycleAction?> runningLifecycleActionListenable;
  final TextEditingController gatewayUrlController;
  final TextEditingController pairingCodeController;
  final TextEditingController deviceNameController;
  final RouteProviderKind routeKind;
  final bool claiming;
  final ValueChanged<AppRuntimeMode> onModeChanged;
  final ValueChanged<GatewayPairedHost> onProfileSelected;
  final VoidCallback onCheckRoute;
  final ValueChanged<CcbLifecycleAction> onLifecycleAction;
  final ValueChanged<RouteProviderKind> onRouteKindChanged;
  final VoidCallback onScan;
  final VoidCallback onClaim;
  final bool initiallyExpanded;

  @override
  Widget build(BuildContext context) {
    return ExpansionTile(
      key: const ValueKey('connection-details-panel'),
      initiallyExpanded: initiallyExpanded,
      tilePadding: EdgeInsets.zero,
      childrenPadding: const EdgeInsets.only(top: 8, bottom: 8),
      leading: const Icon(Icons.tune),
      title: const Text('Diagnostics'),
      subtitle: Text(
        '${view.project.displayName} / ${view.agents.length} agents',
      ),
      children: [
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.folder_open),
          title: const Text('Project'),
          subtitle: Text(view.project.displayName),
        ),
        RuntimeModePanel(
          mode: mode,
          profiles: profiles,
          selectedProfile: selectedProfile,
          routeDiagnostics: routeDiagnostics,
          loadingProfiles: loadingProfiles,
          checkingRoute: checkingRoute,
          onModeChanged: onModeChanged,
          onProfileSelected: onProfileSelected,
          onCheckRoute: onCheckRoute,
        ),
        const SizedBox(height: 8),
        ProjectLifecyclePanel(
          resultListenable: lifecycleResultListenable,
          runningActionListenable: runningLifecycleActionListenable,
          onAction: onLifecycleAction,
        ),
        const SizedBox(height: 8),
        GatewayPairingPanel(
          gatewayUrlController: gatewayUrlController,
          pairingCodeController: pairingCodeController,
          deviceNameController: deviceNameController,
          routeKind: routeKind,
          claiming: claiming,
          onRouteKindChanged: onRouteKindChanged,
          onScan: onScan,
          onClaim: onClaim,
        ),
      ],
    );
  }
}
