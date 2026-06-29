import 'package:flutter/material.dart';

import '../../models/ccb_agent.dart';
import '../../models/ccb_project_view.dart';
import '../../models/ccb_window.dart';
import 'agent_window_switchers.dart';
import 'project_view_selection.dart';

class MobileAgentSwitcherPanel extends StatelessWidget {
  const MobileAgentSwitcherPanel({
    required this.view,
    required this.selectedAgent,
    required this.collapsed,
    required this.onCollapse,
    required this.onExpand,
    required this.onWindowSelected,
    required this.onAgentSelected,
    super.key,
  });

  final CcbProjectView view;
  final CcbAgent? selectedAgent;
  final bool collapsed;
  final VoidCallback onCollapse;
  final VoidCallback onExpand;
  final ValueChanged<String> onWindowSelected;
  final ValueChanged<String> onAgentSelected;

  @override
  Widget build(BuildContext context) {
    if (view.agents.isEmpty) {
      return const SizedBox.shrink();
    }
    final windows = orderedWindowsForView(view);
    final selectedWindow = selectedWindowForView(view, selectedAgent);
    final currentAgents =
        selectedWindow == null
            ? view.agents
            : agentsForWindow(view, selectedWindow.name);
    final agent = selectedAgent;
    if (collapsed) {
      return GestureDetector(
        key: const ValueKey('mobile-agent-switcher-collapsed'),
        behavior: HitTestBehavior.opaque,
        onVerticalDragUpdate: (details) {
          if (details.delta.dy > 0) {
            onExpand();
          }
        },
        child: Material(
          color: Theme.of(context).colorScheme.surface,
          child: InkWell(
            onTap: onExpand,
            child: SizedBox(
              height: 48,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Row(
                  children: [
                    const Icon(Icons.smart_toy, size: 20),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        _mobileAgentSummary(
                          selectedWindow: selectedWindow,
                          selectedAgent: agent,
                          agentCount: view.agents.length,
                        ),
                        key: const ValueKey('mobile-agent-switcher-summary'),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                    ),
                    const Icon(Icons.keyboard_arrow_down),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
    }
    return GestureDetector(
      key: const ValueKey('mobile-agent-switcher-expanded'),
      behavior: HitTestBehavior.opaque,
      onVerticalDragUpdate: (details) {
        if (details.delta.dy < 0) {
          onCollapse();
        }
      },
      child: Column(
        children: [
          WindowSwitcher(
            windows: windows,
            selectedWindowName: selectedWindow?.name,
            onWindowSelected: onWindowSelected,
          ),
          const SizedBox(height: 4),
          AgentSwitcher(
            agents: currentAgents.isEmpty ? view.agents : currentAgents,
            selectedAgentName: selectedAgent?.name,
            onAgentSelected: (agent) {
              onAgentSelected(agent.name);
            },
          ),
          const SizedBox(height: 2),
          Container(
            key: const ValueKey('mobile-agent-switcher-drag-handle'),
            width: 36,
            height: 3,
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.outlineVariant,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
        ],
      ),
    );
  }

  String _mobileAgentSummary({
    required CcbWindow? selectedWindow,
    required CcbAgent? selectedAgent,
    required int agentCount,
  }) {
    final agent = selectedAgent;
    if (agent == null) {
      return '$agentCount agents';
    }
    final window = selectedWindow;
    if (window == null) {
      return agent.name;
    }
    return '${window.label} / ${agent.name}';
  }
}
