import 'package:flutter/material.dart';

import '../../models/ccb_agent.dart';
import '../../models/ccb_window.dart';

class AgentSwitcher extends StatelessWidget {
  const AgentSwitcher({
    required this.agents,
    required this.selectedAgentName,
    required this.onAgentSelected,
    super.key,
  });

  final List<CcbAgent> agents;
  final String? selectedAgentName;
  final ValueChanged<CcbAgent> onAgentSelected;

  @override
  Widget build(BuildContext context) {
    if (agents.isEmpty) {
      return const SizedBox.shrink();
    }
    return SizedBox(
      key: const ValueKey('agent-switcher'),
      height: 40,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: agents.length,
        separatorBuilder: (context, index) => const SizedBox(width: 6),
        itemBuilder: (context, index) {
          final agent = agents[index];
          final selected = agent.name == selectedAgentName;
          return ChoiceChip(
            key: ValueKey('agent-${agent.name}'),
            selected: selected,
            visualDensity: VisualDensity.compact,
            labelPadding: const EdgeInsets.symmetric(horizontal: 4),
            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
            avatar: Icon(
              agent.active ? Icons.radio_button_checked : Icons.smart_toy,
              size: 16,
            ),
            label: Text(agent.name),
            onSelected: (_) {
              onAgentSelected(agent);
            },
          );
        },
      ),
    );
  }
}

class WindowSwitcher extends StatelessWidget {
  const WindowSwitcher({
    required this.windows,
    required this.selectedWindowName,
    required this.onWindowSelected,
    super.key,
  });

  final List<CcbWindow> windows;
  final String? selectedWindowName;
  final ValueChanged<String> onWindowSelected;

  @override
  Widget build(BuildContext context) {
    if (windows.isEmpty) {
      return const SizedBox.shrink();
    }
    return SizedBox(
      key: const ValueKey('window-switcher'),
      height: 36,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: windows.length,
        separatorBuilder: (context, index) => const SizedBox(width: 6),
        itemBuilder: (context, index) {
          final window = windows[index];
          final selected = window.name == selectedWindowName;
          return ChoiceChip(
            key: ValueKey('window-tab-${window.name}'),
            selected: selected,
            visualDensity: VisualDensity.compact,
            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
            avatar: Icon(
              selected ? Icons.radio_button_checked : Icons.view_column,
              size: 15,
            ),
            label: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 140),
              child: Text(
                window.label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            onSelected: (_) {
              if (!selected) {
                onWindowSelected(window.name);
              }
            },
          );
        },
      ),
    );
  }
}
