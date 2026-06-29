import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';

import '../../pairing/gateway_pairing.dart';
import '../../transport/route_provider.dart';
import 'project_home_pairing_request.dart';

class ProjectHomePairingFormController {
  ProjectHomePairingFormController({
    String gatewayUrlText = 'http://127.0.0.1:8787',
    String deviceNameText = projectHomePairingDefaultDeviceName,
    RouteProviderKind routeKind = RouteProviderKind.lan,
  }) : gatewayUrlController = TextEditingController(text: gatewayUrlText),
       pairingCodeController = TextEditingController(),
       deviceNameController = TextEditingController(text: deviceNameText),
       _routeKind = routeKind,
       _routeKindNotifier = ValueNotifier<RouteProviderKind>(routeKind);

  final TextEditingController gatewayUrlController;
  final TextEditingController pairingCodeController;
  final TextEditingController deviceNameController;
  final ValueNotifier<RouteProviderKind> _routeKindNotifier;
  RouteProviderKind _routeKind;

  RouteProviderKind get routeKind => _routeKind;

  ValueListenable<RouteProviderKind> get routeKindListenable =>
      _routeKindNotifier;

  void setRouteKind(RouteProviderKind value) {
    _routeKind = value;
    _routeKindNotifier.value = value;
  }

  ProjectHomePairingRequest buildRequest({
    GatewayPairingPayload? pairingOverride,
  }) {
    return buildProjectHomePairingRequest(
      gatewayUrlText: gatewayUrlController.text,
      pairingCodeText: pairingCodeController.text,
      deviceNameText: deviceNameController.text,
      routeKind: _routeKind,
      pairingOverride: pairingOverride,
    );
  }

  void applyScannedPairing(GatewayPairingPayload pairing) {
    gatewayUrlController.text = pairing.gatewayUrl.toString();
    pairingCodeController.text = pairing.pairingCode;
    setRouteKind(pairing.routeProvider);
  }

  void applyGatewayActivation({
    required String gatewayUrlText,
    required RouteProviderKind routeKind,
  }) {
    gatewayUrlController.text = gatewayUrlText;
    setRouteKind(routeKind);
  }

  void clearPairingCode() {
    pairingCodeController.clear();
  }

  void dispose() {
    gatewayUrlController.dispose();
    pairingCodeController.dispose();
    deviceNameController.dispose();
    _routeKindNotifier.dispose();
  }
}
