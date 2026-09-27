import 'package:flutter_test/flutter_test.dart';
import 'package:safe_archive/main.dart';

void main() {
  test('extracts a shared public URL without surrounding punctuation', () {
    final report = SharedReport();
    report.receive('See this post (https://example.org/post?id=3).');
    expect(report.url, 'https://example.org/post?id=3');
    expect(report.sharedText, contains('See this post'));
    report.clear();
    expect(report.url, isEmpty);
    expect(report.sharedText, isEmpty);
  });

  test('ignores text without a public URL', () {
    final report = SharedReport();
    report.receive('A message without a link');
    expect(report.url, isEmpty);
  });
}
