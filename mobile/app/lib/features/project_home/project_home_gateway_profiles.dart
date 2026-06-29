import '../../pairing/gateway_pairing.dart';

String projectHomeGatewayProfileKey(GatewayPairedHost profile) {
  return '${profile.profile.hostId}/${profile.profile.deviceId}';
}

String projectHomeGatewayProfileLabel(GatewayPairedHost profile) {
  final route = profile.profile.routeProvider.kind.wireName;
  return '${profile.profile.hostId} / ${profile.profile.deviceId} / $route';
}

List<GatewayPairedHost> sortProjectHomeGatewayProfiles(
  Iterable<GatewayPairedHost> profiles,
) {
  return [...profiles]..sort(
    (a, b) => projectHomeGatewayProfileLabel(
      a,
    ).compareTo(projectHomeGatewayProfileLabel(b)),
  );
}

List<GatewayPairedHost> mergeProjectHomeGatewayProfiles(
  Iterable<GatewayPairedHost> profiles,
  GatewayPairedHost paired,
) {
  final key = projectHomeGatewayProfileKey(paired);
  return sortProjectHomeGatewayProfiles([
    for (final profile in profiles)
      if (projectHomeGatewayProfileKey(profile) != key) profile,
    paired,
  ]);
}
