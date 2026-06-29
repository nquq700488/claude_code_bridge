class CcbProject {
  const CcbProject({
    required this.id,
    required this.displayName,
    required this.root,
    this.favorite = false,
    this.health = 'unknown',
  });

  final String id;
  final String displayName;
  final String root;
  final bool favorite;
  final String health;

  factory CcbProject.fromJson(Map<String, Object?> json) {
    return CcbProject(
      id: _text(json['id']),
      displayName: _text(json['display_name'], fallback: _text(json['id'])),
      root: _text(json['root']),
      favorite: json['favorite'] == true,
      health: _text(json['health'], fallback: 'unknown'),
    );
  }
}

String _text(Object? value, {String fallback = ''}) {
  final text = (value ?? '').toString().trim();
  return text.isEmpty ? fallback : text;
}
