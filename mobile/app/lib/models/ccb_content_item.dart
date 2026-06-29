class CcbContentItem {
  const CcbContentItem({
    required this.id,
    required this.kind,
    required this.format,
    required this.text,
    this.agentName,
    this.title,
    this.source,
  });

  final String id;
  final String kind;
  final String format;
  final String text;
  final String? agentName;
  final String? title;
  final String? source;

  factory CcbContentItem.fromJson(Map<String, Object?> json) {
    return CcbContentItem(
      id: _text(json['id'], fallback: 'content'),
      kind: _text(json['kind'], fallback: 'unknown'),
      format: _text(json['format'], fallback: 'plain'),
      text: _text(json['text']),
      agentName:
          _optionalText(json['agent']) ?? _optionalText(json['agent_name']),
      title: _optionalText(json['title']),
      source: _optionalText(json['source']),
    );
  }

  bool belongsToAgent(String name) {
    final agent = agentName;
    return agent == null || agent == name;
  }
}

String _text(Object? value, {String fallback = ''}) {
  final text = (value ?? '').toString().trim();
  return text.isEmpty ? fallback : text;
}

String? _optionalText(Object? value) {
  final text = _text(value);
  return text.isEmpty ? null : text;
}
