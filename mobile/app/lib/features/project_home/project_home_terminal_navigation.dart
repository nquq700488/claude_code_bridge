import '../../models/ccb_project_view.dart';

const projectHomeTerminalTransportNotReadySnack =
    'Gateway terminal transport is not ready';

ProjectHomeTerminalNavigationOutcome projectHomeFakeTerminalNavigation({
  required CcbProjectView view,
  required String agentName,
}) {
  return ProjectHomeTerminalNavigationOutcome.open(
    ProjectHomeTerminalNavigationSpec(
      projectId: view.project.id,
      agentName: agentName,
      gatewayTerminal: false,
    ),
  );
}

ProjectHomeTerminalNavigationOutcome projectHomeGatewayTerminalNavigation({
  required CcbProjectView? focusedView,
  required String agentName,
  required bool hasTerminalTransport,
}) {
  if (focusedView == null) {
    return const ProjectHomeTerminalNavigationOutcome.none();
  }
  if (!hasTerminalTransport) {
    return const ProjectHomeTerminalNavigationOutcome.noTransport(
      snackMessage: projectHomeTerminalTransportNotReadySnack,
    );
  }
  return ProjectHomeTerminalNavigationOutcome.open(
    ProjectHomeTerminalNavigationSpec(
      projectId: focusedView.project.id,
      agentName: agentName,
      gatewayTerminal: true,
    ),
  );
}

enum ProjectHomeTerminalNavigationKind { none, noTransport, open }

class ProjectHomeTerminalNavigationOutcome {
  const ProjectHomeTerminalNavigationOutcome.none()
    : kind = ProjectHomeTerminalNavigationKind.none,
      spec = null,
      snackMessage = null;

  const ProjectHomeTerminalNavigationOutcome.noTransport({
    required String snackMessage,
  }) : this._(
         kind: ProjectHomeTerminalNavigationKind.noTransport,
         snackMessage: snackMessage,
       );

  const ProjectHomeTerminalNavigationOutcome.open(
    ProjectHomeTerminalNavigationSpec spec,
  ) : this._(kind: ProjectHomeTerminalNavigationKind.open, spec: spec);

  const ProjectHomeTerminalNavigationOutcome._({
    required this.kind,
    this.spec,
    this.snackMessage,
  });

  final ProjectHomeTerminalNavigationKind kind;
  final ProjectHomeTerminalNavigationSpec? spec;
  final String? snackMessage;
}

class ProjectHomeTerminalNavigationSpec {
  const ProjectHomeTerminalNavigationSpec({
    required this.projectId,
    required this.agentName,
    required this.gatewayTerminal,
  });

  final String projectId;
  final String agentName;
  final bool gatewayTerminal;
}
