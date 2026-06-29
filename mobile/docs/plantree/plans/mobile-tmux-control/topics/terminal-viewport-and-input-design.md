# Terminal Viewport And Input Design

Date: 2026-06-22
Status: Design direction

## Role

Preserve the terminal-mode product design from the `mobile_app_engineer`
terminal audit and turn it into a durable implementation reference for the
explicit Open Terminal route.

This topic does not change the chat-first default. It defines how future raw
tmux controls should behave once the user intentionally enters terminal mode.

Related:

- [chat-first agent workspace](chat-first-agent-workspace.md)
- [terminal transport spike](terminal-transport-spike.md)
- [Decision 012](../decisions/012-agent-first-project-workspace.md)
- [Decision 013](../decisions/013-readable-terminal-history.md)
- [Decision 014](../decisions/014-chat-first-agent-workspace.md)

## Product Boundary

The default project page remains a CCB agent chat workspace:

- project list or project/agent sidebars for navigation;
- one selected-agent conversation timeline;
- a CCB-owned composer for normal user messages;
- static, readable terminal-history snapshots when terminal evidence helps;
- explicit Open Terminal for raw tmux fallback/debug control.

Terminal viewport controls, mouse simulation, wheel handling, pinch zoom,
special keys, and raw input must stay inside the Terminal route. They should
not appear in chat bubbles, the project list, or the default selected-agent
timeline.

## Viewport Modes

### Fit Session

Default terminal route mode.

- Show the full current tmux session layout.
- Scale the terminal grid so the whole session is visible on the device.
- Keep existing resize/sync controls explicit; entering this mode should not
  silently damage the user's desktop tmux layout.
- Prefer readability warnings or quick mode changes over automatic destructive
  resizing when the session has many panes.

### Fit Pane

Phone-first readable control mode for split tmux sessions.

- Render only the active or selected pane.
- Hide sibling panes from the visual viewport without changing CCB's agent
  ownership model.
- Validate namespace epoch, window, pane evidence, and selected agent/window
  before accepting input.
- If the source cannot provide reliable pane geometry, fall back to Fit Session
  with a visible notice instead of guessing from stale pane ids.

### Free Zoom

Inspection mode for large terminal surfaces.

- Pinch zoom and pan transform the Flutter viewport only.
- Do not trigger tmux resize or `SIGWINCH` while the user is only magnifying.
- Keep the terminal grid stable underneath the magnifier.
- Provide a quick reset back to Fit Session or Fit Pane.

## Pointer, Wheel, And Shortcut Model

Pointer behavior should be mode-scoped to the Terminal route:

- Chat timeline: native scroll and selection behavior only.
- Terminal route: pointer events are captured by the terminal surface.
- Touch drag in terminal: scrollback/pan depending on the selected viewport
  mode, not parent-page scrolling.
- External wheel: default to terminal scrollback; allow a terminal-mouse mode
  when tmux mouse support is enabled or explicitly requested.
- Left click/tap: terminal focus or tmux mouse click when terminal-mouse mode
  is active.
- Secondary click/long press: open a compact terminal context menu for copy,
  paste, send right-click, and pointer-mode selection.
- Hardware keyboard: trap terminal shortcuts only while the Terminal route has
  focus, including `Ctrl+C`, `Esc`, paste, arrows, and function keys.

Soft-keyboard users still need visible modifier affordances such as Esc, Ctrl,
Alt, arrows, paste, size sync, and reconnect. Hardware-keyboard users can have
that modifier bar collapsed once a physical keyboard is detected.

## UI Placement

Use terminal-only controls:

- A compact segmented control or menu for `Session`, `Pane`, and `Zoom`.
- Pointer mode under the same terminal toolbar or overflow menu.
- Existing send, paste, resize/sync, and reconnect controls remain in the
  terminal control bar.
- The Terminal route should look visually distinct from the chat workspace so
  users can tell they are in raw server control.

Do not embed an active terminal inside the selected-agent timeline. Chat-side
terminal evidence remains static readable history, not an interactive terminal
surface.

## Implementation Packages

1. UI-only terminal route package:
   add terminal viewport mode state, segmented controls, gesture isolation,
   and focused widget tests in the existing terminal screen surface.
2. Pane evidence package:
   extend the gateway/readable ProjectView evidence enough to identify the
   active pane safely, then implement Fit Pane behind epoch and pane checks.
3. Pointer and wheel package:
   add route-scoped pointer-mode handling and frame/schema tests before sending
   mouse events through the live gateway transport.
4. Emulator validation package:
   run the Android Emulator smoke against a disposable multi-pane project and
   verify chat mode stays unaffected while terminal mode supports zoom, pan,
   scrollback, and explicit input.

## Acceptance Gates

- Phone chat screen keeps the compact selected-agent conversation/composer as
  the default first viewport.
- Opening Terminal exposes the viewport mode control without changing normal
  chat input behavior.
- Pinch and pan work only inside Terminal route.
- Free Zoom does not resize tmux.
- Fit Pane never sends input to stale pane evidence.
- External wheel and mouse actions do not scroll or click the chat timeline
  while Terminal route is focused.
- Widget tests cover mode toggles, gesture isolation, and keyboard focus.
- Local Android Emulator smoke covers at least one multi-pane session.

## Open Edges

- The source of reliable pane bounds still needs measurement against current
  ProjectView/tmux evidence.
- tmux mouse-mode defaults need a product decision after testing external
  mouse users on iPad/desktop widths.
- If PTY attach resize continues to affect the desktop session, Fit Pane may
  need tmux control mode or a CCB-owned grouped mobile view session.
