import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../../app/runtime_mode.dart';
import '../../models/ccb_project_lifecycle.dart';
import '../../models/ccb_project_view.dart';
import '../../pairing/gateway_pairing.dart';
import '../../transport/gateway_route_diagnostics.dart';
import '../../transport/route_provider.dart';
import 'connection_details.dart';

class ProjectHomeConnectionDetailsPanelHost extends StatelessWidget {
  const ProjectHomeConnectionDetailsPanelHost({
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
    required this.routeKindListenable,
    required this.claiming,
    required this.onModeChanged,
    required this.onProfileSelected,
    required this.onCheckRoute,
    required this.onLifecycleAction,
    required this.onRouteKindChanged,
    required this.onScan,
    required this.onClaim,
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
  final ValueListenable<RouteProviderKind> routeKindListenable;
  final bool claiming;
  final ValueChanged<AppRuntimeMode> onModeChanged;
  final ValueChanged<GatewayPairedHost> onProfileSelected;
  final VoidCallback onCheckRoute;
  final ValueChanged<CcbLifecycleAction> onLifecycleAction;
  final ValueChanged<RouteProviderKind> onRouteKindChanged;
  final VoidCallback onScan;
  final VoidCallback onClaim;

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<RouteProviderKind>(
      valueListenable: routeKindListenable,
      builder:
          (context, routeKind, _) => ConnectionDetailsPanel(
            view: view,
            mode: mode,
            profiles: profiles,
            selectedProfile: selectedProfile,
            routeDiagnostics: routeDiagnostics,
            lifecycleResultListenable: lifecycleResultListenable,
            loadingProfiles: loadingProfiles,
            checkingRoute: checkingRoute,
            runningLifecycleActionListenable: runningLifecycleActionListenable,
            gatewayUrlController: gatewayUrlController,
            pairingCodeController: pairingCodeController,
            deviceNameController: deviceNameController,
            routeKind: routeKind,
            claiming: claiming,
            initiallyExpanded: true,
            onModeChanged: onModeChanged,
            onProfileSelected: onProfileSelected,
            onCheckRoute: onCheckRoute,
            onLifecycleAction: onLifecycleAction,
            onRouteKindChanged: onRouteKindChanged,
            onScan: onScan,
            onClaim: onClaim,
          ),
    );
  }
}
