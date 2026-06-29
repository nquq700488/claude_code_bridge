import 'package:ccb_mobile/features/project_home/project_home_gateway_profiles.dart';
import 'package:ccb_mobile/features/project_home/project_home_profile_bootstrapper.dart';
import 'package:ccb_mobile/features/project_home/runtime_mode_panel.dart'
    as runtime_mode_panel;
import 'package:ccb_mobile/pairing/gateway_pairing.dart';
import 'package:ccb_mobile/transport/route_provider.dart';
import 'package:test/test.dart';

import 'support/project_home_test_fakes.dart';

void main() {
  test('runtime mode panel keeps gateway profile helper API path', () {
    final profile = _pairedHost(
      hostId: 'project',
      deviceId: 'phone',
      routeKind: RouteProviderKind.relay,
    );

    expect(
      runtime_mode_panel.projectHomeGatewayProfileKey(profile),
      'project/phone',
    );
    expect(
      runtime_mode_panel.projectHomeGatewayProfileLabel(profile),
      'project / phone / relay',
    );
  });

  test('merge replaces existing profile with same host and device', () {
    final oldProfile = _pairedHost(
      hostId: 'project',
      deviceId: 'phone',
      token: 'old-token',
      routeKind: RouteProviderKind.lan,
    );
    final replacement = _pairedHost(
      hostId: 'project',
      deviceId: 'phone',
      token: 'new-token',
      routeKind: RouteProviderKind.cloudflareTunnel,
    );
    final otherProfile = _pairedHost(hostId: 'other', deviceId: 'tablet');

    final merged = mergeProjectHomeGatewayProfiles([
      oldProfile,
      otherProfile,
    ], replacement);

    expect(merged, hasLength(2));
    expect(merged, contains(same(replacement)));
    expect(merged, contains(same(otherProfile)));
    expect(merged, isNot(contains(same(oldProfile))));
  });

  test('merge result is sorted by project home profile label', () {
    final beta = _pairedHost(hostId: 'beta', deviceId: 'phone');
    final alphaTablet = _pairedHost(hostId: 'alpha', deviceId: 'tablet');
    final alphaPhone = _pairedHost(hostId: 'alpha', deviceId: 'phone');

    final merged = mergeProjectHomeGatewayProfiles([
      beta,
      alphaTablet,
    ], alphaPhone);

    expect(merged.map(projectHomeGatewayProfileLabel), [
      'alpha / phone / lan',
      'alpha / tablet / lan',
      'beta / phone / lan',
    ]);
  });

  test(
    'load without debug profile keeps selected profile or chooses store first',
    () async {
      final beta = _pairedHost(hostId: 'beta', deviceId: 'phone');
      final alpha = _pairedHost(hostId: 'alpha', deviceId: 'phone');
      final store = _OrderedProfileStore([beta, alpha]);
      final bootstrapper = ProjectHomeProfileBootstrapper(store: store);

      final keptSelection = await bootstrapper.bootstrap(
        selectedProfile: beta,
        debugProfile: null,
      );
      final firstSelection = await bootstrapper.bootstrap(
        selectedProfile: null,
        debugProfile: null,
      );

      expect(keptSelection.selectedProfile, same(beta));
      expect(firstSelection.selectedProfile, same(beta));
      expect(firstSelection.profiles.map(projectHomeGatewayProfileLabel), [
        'beta / phone / lan',
        'alpha / phone / lan',
      ]);
    },
  );

  test(
    'debug profile is saved, selected, and marked for auto activation',
    () async {
      final store = GatewayHostProfileStore(secureStore: MemorySecureStore());
      final bootstrapper = ProjectHomeProfileBootstrapper(store: store);
      final stored = _pairedHost(hostId: 'stored', deviceId: 'phone');
      final debug = _pairedHost(hostId: 'debug', deviceId: 'phone');
      await store.save(stored);

      final result = await bootstrapper.bootstrap(
        selectedProfile: stored,
        debugProfile: debug,
        autoActivateDebugProfile: true,
      );
      final savedDebug = await store.read(hostId: 'debug', deviceId: 'phone');

      expect(result.selectedProfile, same(debug));
      expect(result.activateProfile, same(debug));
      expect(savedDebug?.deviceToken, 'debug-token');
      expect(result.profiles.map(projectHomeGatewayProfileLabel), [
        'debug / phone / lan',
        'stored / phone / lan',
      ]);
    },
  );
}

class _OrderedProfileStore extends GatewayHostProfileStore {
  _OrderedProfileStore(this._profiles)
    : super(secureStore: MemorySecureStore());

  final List<GatewayPairedHost> _profiles;

  @override
  Future<List<GatewayPairedHost>> list() async => List.of(_profiles);
}

GatewayPairedHost _pairedHost({
  required String hostId,
  required String deviceId,
  String? token,
  RouteProviderKind routeKind = RouteProviderKind.lan,
}) {
  return GatewayPairedHost(
    profile: GatewayHostProfile(
      hostId: hostId,
      deviceId: deviceId,
      routeProvider: RouteProvider(
        kind: routeKind,
        gatewayUrl: Uri.parse('http://$hostId.example.test'),
      ),
      scopes: const {'view'},
    ),
    deviceToken: token ?? '$hostId-token',
    projectId: hostId,
    createdAt: DateTime.utc(2026, 6, 22),
  );
}
