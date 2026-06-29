# Mobile UX Flows

Date: 2026-06-17
Status: Draft

## Design Bias

The mobile UI should feel like a CCB-aware remote control for server-side CCB
projects, not a marketing app, not a generic SSH launcher, not a tmux-first
terminal clone, and not an independent mobile agent runtime.

The primary job is to answer:

- Can I open a server-side CCB project from phone/iPad?
- Can I switch CCB projects, windows, and agents quickly?
- Can I see exactly one selected agent clearly?
- Can I read and continue the selected agent conversation like a mobile chat?
- Can I keep a short list of common projects and wake/close them remotely?
- Which CCB projects are alive?
- Which agents need attention?
- What is each agent doing?
- Did my agent finish, fail, block, or ask for a callback?
- Can I read Comms/Markdown context without parsing a terminal stream?
- Can I enter raw terminal mode when I explicitly need pane-level control?

## Home

Default home: project-centric list grouped by host.

Each project row should show:

- favorite/pinned state;
- project display name;
- root path or short path;
- host name;
- health: online, starting, degraded, offline, stale;
- lifecycle: stopped, starting, running, stopping, failed, unknown;
- active agent count;
- waiting callback count;
- unread or unresolved Comms count;
- last completion/attention event;
- last activity time;
- quick action to wake/open or close/stop project.

Host health should be visible but not dominate the main workflow unless the
user has many hosts.

## Project Lifecycle Flow

Frequent projects should be one tap away:

1. User pins a project from the project list or current project view.
2. Home shows the pinned project with lifecycle and health.
3. If stopped, the primary action is wake/open.
4. If running, the primary action is open the project workspace.
5. Stop/close actions are available but separated:
   close mobile view is lightweight; stop project uses CCB shutdown behavior.
6. Lifecycle changes produce notifications and update the row state.

## Project Remote View

Opening a project should land in an agent-first workspace, not a terminal
stream or a status dashboard. The first viewport should prioritize an agent
switcher, one selected agent, a conversation timeline, and a persistent
composer:

- top window/agent switcher: a compact window row scopes the agent row below
  it, so CCB windows behave as task/workspace groups rather than connection
  details;
- agent switcher: configured agents for the selected window with compact
  state, callback, and attention indicators;
- main body: exactly one selected agent chat timeline with user messages,
  agent replies, callbacks, Comms, Markdown/content, status events, and
  readable terminal-history evidence where useful;
- bottom composer: multiline input, send action, pending/sent/failed state,
  retry, and per-agent draft preservation;
- project and route details: project path, runtime id, gateway URL, pairing,
  namespace/epoch diagnostics, and route health behind a details affordance;
- explicit terminal action: Open Terminal enters raw terminal control mode for
  the selected agent/window;
- diagnostics/details: pairing, route health, lifecycle, runtime id, and other
  technical state stay behind the Diagnostics affordance; windows should not
  be listed there as connection configuration;
- actions: ask, focus, refresh, restart agent, reload config, admin menu.

Agent taps should switch the selected agent first. Focus requests and terminal
entry should be visible explicit actions, followed by ProjectView refresh to
confirm the active CCB state.

## Agent Detail

Agent detail is the main conversation and control surface for one selected
agent:

- agent name and provider;
- current state and last activity;
- completion state and last finished/failed/blocked event;
- current queue or task summary when available;
- chat timeline with user asks, agent replies, callback prompts, Comms,
  status events, and artifact cards;
- persistent composer;
- Markdown-rendered request/reply content inside timeline cards;
- focus action and explicit open-terminal action for that agent pane.

The agent workspace is the default compact pane-backed chat surface. Composer
and Markdown views should cover normal mobile usage. Raw terminal mode remains
available for full pane-level control, debugging, special keys, mouse/viewport
operations, and operations that are not comfortable in the compact chat shell.

## Ask And Callback Flow

Suggested flow:

1. User opens project.
2. User taps an agent in the top switcher.
3. The selected-agent timeline and composer are already visible.
4. User types a multiline message and sends it.
5. Mobile shows pending, queued/sent, and failed/retry states in the timeline.
6. Gateway writes the text to the selected agent's CCB-validated tmux pane
   through terminal paste/input frames.
7. If callback is required, notification and Comms detail deep-link back to the
   same thread.

This keeps the user's mobile input aligned with the real provider CLI pane
while letting the app render the pane interaction as a readable chat surface.

## Markdown Reading Flow

Markdown should be the default display mode for CCB-authored and
agent-authored content:

1. User opens a Comms item, ask result, callback, or artifact-backed message.
2. Mobile shows a clean Markdown reading view.
3. Code blocks have copy buttons and wrap/scroll controls.
4. Tables can switch between fitted, horizontal scroll, and card/list mode.
5. Long sections can collapse without losing the raw text.
6. A raw source toggle remains available for debugging or copy fidelity.

Pane snapshots stay terminal output, not Markdown. If a provider's latest reply
is available through CCB message/session evidence, mobile should prefer that
structured content over trying to infer Markdown from captured terminal text.

## Pane Snapshot Flow

Pane snapshots evolve into a readable terminal history flow for the selected
agent. This is still a fallback/observability surface, not the authoritative
Markdown reply source.

Suggested flow:

1. User taps an agent.
2. The selected-agent workspace shows a vertically scrollable readable history
   block or timeline section built from the current pane plus retained tmux
   scrollback.
3. Pull-to-refresh or periodic refresh appends/reconciles newer output without
   jumping away from the user's current scroll position.
4. Snapshot header shows agent/window, freshness, alive/dead, and stale-view
   warnings.
5. If stale, the UI asks the user to refresh ProjectView instead of sending
   input to old pane evidence.

Readable history mode should support copy text, copy block, collapse repeated
logs, wrap/scroll code, diff highlighting, and "open raw terminal" as a
deliberate upgrade path.

Readable history may detect Markdown-looking output for convenience, but it
should not become the authoritative reply view. The authoritative Markdown view
should come from CCB message/reply/artifact content when available.

The MVP can only show current tmux scrollback. A later terminal journal should
record output as it happens if the product needs complete project-lifetime
history beyond tmux `history-limit`.

## Interactive Terminal Flow

Interactive terminal is an explicit raw-control flow:

1. User opens a project from the project list.
2. User selects one agent or window in the agent-first workspace.
3. User taps Open Terminal.
4. Gateway resolves project id to current CCB tmux socket/session facts.
5. Terminal opens with special key controls and paste composer.
6. Side/bottom sheet shows target identity: project, window, agent, current
   pane evidence.
7. If stale target evidence is detected, input locks until refresh.
8. Closing terminal returns to the selected agent workspace and does not affect project
   lifecycle.

Phone terminal controls should include:

- Esc, Tab, Ctrl, Alt modifier toggles;
- arrows and function keys;
- paste as block;
- font size;
- reconnect status;
- read-only/input lock indicator;
- explicit close.

## Notifications

Useful notification classes:

- task completed;
- task failed, incomplete, or cancelled;
- callback waiting;
- direct Comms mention;
- agent unhealthy or pane missing;
- project backend offline;
- project wake/stop result;
- raw terminal session disconnected.

Notifications should deep-link by project id plus agent/window/Comms id. They
should not deep-link by pane id alone.

## Multi-Agent Views

For CCB, a phone-specific "agent board" is more useful than a pane grid:

- rows are configured agents;
- columns or chips show provider, window, activity, queue, callback, and health;
- completion markers show done, failed, blocked, or waiting for user;
- one-tap focus changes the desktop tmux view through `ccbd`;
- one-tap ask opens composer;
- terminal snapshot is secondary detail.

This is the main product difference from generic tmux clients.

## Mobile Constraints

Avoid mobile layouts that require reading four panes side by side. Prefer:

- list-first navigation;
- one selected agent/window at a time;
- dense rows with status chips;
- terminal snapshot as scrollable content;
- raw terminal as full-screen mode;
- admin actions behind menus and confirmations.

## MVP Screens

Minimum screens:

1. Pairing screen.
2. Project list.
3. Project agent workspace with top agent switcher, selected-agent timeline,
   and persistent composer.
4. Explicit raw terminal mode for selected agent/window.
5. Project lifecycle confirmation sheet.
6. Markdown content detail for Comms, replies, formulas, and artifacts.
7. Comms/callback detail.
8. Notification center.
9. Settings/devices screen for permissions and revocation.

## Anti-Patterns

Avoid:

- starting from SSH host/session lists;
- showing every tmux pane as equal to a CCB agent;
- making raw terminal the default project page;
- making agent taps open terminal instead of switching selected agent;
- letting project path, gateway URL, pairing code, runtime id, or diagnostics
  consume the first viewport;
- exposing destructive tmux commands in the normal UI;
- depending on pane ids in deep links;
- treating captured terminal text as the only readable answer source;
- making the input composer a hidden secondary action instead of the default
  selected-agent control;
- sending normal user messages by typing into a provider/tmux pane;
- hiding stale namespace warnings.
