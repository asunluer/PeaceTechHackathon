import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:guardia/main.dart';

void main() {
  testWidgets('post-login dialog explains sharing and shows the contact email', (tester) async {
    await tester.pumpWidget(MaterialApp(home: Builder(builder: (context) => TextButton(
      onPressed: () => showDialog<void>(context: context, builder: (_) => const HowToReportDialog(email: 'survivor@example.org')),
      child: const Text('open'),
    ))));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();

    expect(find.text('How to report'), findsOneWidget);
    expect(find.textContaining('Tap Share'), findsOneWidget);
    expect(find.textContaining('Choose GUARDIA'), findsOneWidget);
    expect(find.textContaining('survivor@example.org'), findsOneWidget);

    await tester.tap(find.text('Got it'));
    await tester.pumpAndSettle();
    expect(find.text('How to report'), findsNothing);
  });
}
