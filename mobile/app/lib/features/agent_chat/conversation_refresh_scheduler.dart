import 'dart:async';

typedef ConversationRefreshCallback = void Function(String agentName);
typedef ConversationRefreshIsActive = bool Function(String agentName);
typedef ConversationRefreshTimerFactory =
    Timer Function(Duration delay, void Function() callback);

Timer _defaultTimerFactory(Duration delay, void Function() callback) {
  return Timer(delay, callback);
}

const defaultConversationRefreshDelays = [
  Duration(seconds: 1),
  Duration(seconds: 2),
  Duration(seconds: 5),
  Duration(seconds: 10),
  Duration(seconds: 20),
  Duration(seconds: 40),
  Duration(seconds: 60),
];

class ConversationRefreshScheduler {
  ConversationRefreshScheduler({
    required ConversationRefreshCallback onRefresh,
    required ConversationRefreshIsActive isActive,
    ConversationRefreshTimerFactory timerFactory = _defaultTimerFactory,
    List<Duration> delays = defaultConversationRefreshDelays,
  }) : _onRefresh = onRefresh,
       _isActive = isActive,
       _timerFactory = timerFactory,
       _delays = List.unmodifiable(delays);

  final ConversationRefreshCallback _onRefresh;
  final ConversationRefreshIsActive _isActive;
  final ConversationRefreshTimerFactory _timerFactory;
  final List<Duration> _delays;
  final List<Timer> _timers = [];

  void schedule(String agentName) {
    cancelAll();
    for (final delay in _delays) {
      _timers.add(
        _timerFactory(delay, () {
          if (!_isActive(agentName)) {
            return;
          }
          _onRefresh(agentName);
        }),
      );
    }
  }

  void cancelAll() {
    for (final timer in _timers) {
      timer.cancel();
    }
    _timers.clear();
  }
}
