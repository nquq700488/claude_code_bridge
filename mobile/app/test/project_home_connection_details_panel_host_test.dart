import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ccb_mobile/ccb_mobile.dart';
import 'package:ccb_mobile/features/project_home/project_home_connection_details_panel_host.dart';

import 'support/project_home_test_driver.dart';

void main() {
  testWidgets('updates route kind from listenable and forwards callback', (
    tester,
  ) async {
    final routeKind = ValueNotifier<RouteProviderKind>(RouteProviderKind.lan);
    final lifecycleResult = ValueNotifier<CcbProjectLifecycleResult?>(null);
    final runningLifecycleAction = ValueNotifier<CcbLifecycleAction?>(null);
    final gatewayUrlController = TextEditingController(
      text: 'http://127.0.0.1:8787',
    );
    final pairingCodeController = TextEditingController();
    final deviceNameController = TextEditingController(text: 'Phone');
    final changedRouteKinds = <RouteProviderKind>[];

    addTearDown(routeKind.dispose);
    addTearDown(lifecycleResult.dispose);
    addTearDown(runningLifecycleAction.dispose);
    addTearDown(gatewayUrlController.dispose);
    addTearDown(pairingCodeController.dispose);
    addTearDown(deviceNameController.dispose);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ListView(
            children: [
              ProjectHomeConnectionDetailsPanelHost(
                view: CcbProjectView.fromProjectViewPayload(
                  demoProjectViewFixture,
                ),
                mode: AppRuntimeMode.fake,
                profiles: const [],
                selectedProfile: null,
                routeDiagnostics: null,
                lifecycleResultListenable: lifecycleResult,
                loadingProfiles: false,
                checkingRoute: false,
                runningLifecycleActionListenable: runningLifecycleAction,
                gatewayUrlController: gatewayUrlController,
                pairingCodeController: pairingCodeController,
                deviceNameController: deviceNameController,
                routeKindListenable: routeKind,
                claiming: false,
                onModeChanged: (_) {},
                onProfileSelected: (_) {},
                onCheckRoute: () {},
                onLifecycleAction: (_) {},
                onRouteKindChanged: changedRouteKinds.add,
                onScan: () {},
                onClaim: () {},
              ),
            ],
          ),
        ),
      ),
    );

    await expandTile(tester, const ValueKey('gateway-pairing-panel'));
    expect(_routeKindValue(tester), RouteProviderKind.lan);

    routeKind.value = RouteProviderKind.cloudflareTunnel;
    await tester.pump();

    expect(_routeKindValue(tester), RouteProviderKind.cloudflareTunnel);

    _routeKindField(tester).onChanged?.call(RouteProviderKind.relay);

    expect(changedRouteKinds, [RouteProviderKind.relay]);
  });
}

DropdownButtonFormField<RouteProviderKind> _routeKindField(
  WidgetTester tester,
) {
  return tester.widget<DropdownButtonFormField<RouteProviderKind>>(
    find.byType(DropdownButtonFormField<RouteProviderKind>),
  );
}

RouteProviderKind? _routeKindValue(WidgetTester tester) {
  return tester
      .state<FormFieldState<RouteProviderKind>>(
        find.byType(DropdownButtonFormField<RouteProviderKind>),
      )
      .value;
}
