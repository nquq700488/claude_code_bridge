import 'package:ccb_mobile/ccb_mobile.dart';
import 'package:test/test.dart';

void main() {
  test('fixture maps project view into CCB models', () {
    final view = CcbProjectView.fromProjectViewPayload(demoProjectViewFixture);

    expect(view.project.id, 'proj-demo');
    expect(view.namespaceEpoch, 4);
    expect(view.tmuxSocketPath, '/tmp/ccb-demo/tmux.sock');
    expect(view.tmuxSessionName, 'ccb-demo');
    expect(view.windows.single.agents, containsAll(['lead', 'mobile']));
    expect(view.agentByName('mobile')?.active, isTrue);
    expect(
      view.contentForAgent('mobile').single.title,
      'Emulator landing status',
    );
    expect(view.contentForAgent('lead').single.id, 'content-lead-plan');
    final history = view.terminalHistoryForAgent('mobile');
    expect(history?.historyScope, 'tmux_scrollback');
    expect(history?.sourcePaneId, '%2');
    expect(
      history?.blocks.map((item) => item.id),
      contains('mobile-checkpoint-09'),
    );
    expect(
      view.notifications.map((item) => item.kind),
      containsAll([
        CcbNotificationKind.taskCompleted,
        CcbNotificationKind.callbackWaiting,
        CcbNotificationKind.commsMention,
      ]),
    );
    expect(
      view.notifications
          .singleWhere((item) => item.kind == CcbNotificationKind.taskCompleted)
          .target
          .contentId,
      'content-lead-plan',
    );
    expect(
      view.notifications
          .singleWhere((item) => item.kind == CcbNotificationKind.commsMention)
          .target
          .commsId,
      'comms-mobile-callback',
    );

    final target = view.terminalTargetForAgent('mobile');
    expect(target.projectId, 'proj-demo');
    expect(target.namespaceEpoch, 4);
    expect(target.agent, 'mobile');
    expect(target.window, 'main');
    expect(target.paneId, '%2');
    expect(target.hasDirectTmuxAttachEvidence, isTrue);
    expect(target.canAcceptTerminalInput, isTrue);

    final windowTarget = view.terminalTargetForWindow('main');
    expect(windowTarget.kind, CcbTerminalTargetKind.windowActivePane);
    expect(windowTarget.projectId, 'proj-demo');
    expect(windowTarget.namespaceEpoch, 4);
    expect(windowTarget.agent, isNull);
    expect(windowTarget.window, 'main');
    expect(windowTarget.paneId, '%2');
    expect(windowTarget.hasDirectTmuxAttachEvidence, isTrue);
    expect(windowTarget.canAcceptTerminalInput, isTrue);
  });

  test('fake repository rejects stale namespace epoch', () async {
    final repo = FakeMobileCcbRepository.demo();

    await expectLater(
      repo.focusAgent(
        projectId: 'proj-demo',
        agent: 'mobile',
        namespaceEpoch: 3,
      ),
      throwsStateError,
    );
  });

  test('project view synthesizes failed, blocked, and unhealthy attention', () {
    final view = CcbProjectView.fromProjectViewPayload({
      'view': {
        'project': {
          'id': 'proj-alerts',
          'root': '/tmp/proj-alerts',
          'display_name': 'alerts',
        },
        'namespace': {'epoch': 2},
        'windows': [
          {
            'name': 'main',
            'label': 'main',
            'kind': 'agents',
            'order': 0,
            'active': true,
            'agents': ['failed', 'blocked', 'missing'],
          },
        ],
        'agents': [
          {
            'name': 'failed',
            'provider': 'codex',
            'window': 'main',
            'state': 'failed',
          },
          {
            'name': 'blocked',
            'provider': 'codex',
            'window': 'main',
            'state': 'blocked',
          },
          {
            'name': 'missing',
            'provider': 'codex',
            'window': 'main',
            'runtime_health': 'missing',
          },
        ],
        'comms': {
          'items': [
            {
              'id': 'callback-thread',
              'kind': 'callback',
              'agent': 'blocked',
              'title': 'Callback thread',
              'text': 'waiting for user',
            },
          ],
        },
      },
    });

    expect(
      view.notifications.map((item) => item.kind),
      containsAll([
        CcbNotificationKind.taskFailed,
        CcbNotificationKind.taskBlocked,
        CcbNotificationKind.agentUnhealthy,
        CcbNotificationKind.commsMention,
      ]),
    );
    expect(
      view.notifications
          .singleWhere((item) => item.kind == CcbNotificationKind.taskFailed)
          .severity,
      CcbNotificationSeverity.critical,
    );
  });
}
