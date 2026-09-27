import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/legacy.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:go_router/go_router.dart';
import 'package:share_handler/share_handler.dart';

const apiBaseUrl = String.fromEnvironment('SAFE_ARCHIVE_API_URL', defaultValue: 'http://10.0.2.2:8000/api/v1');
final apiProvider = Provider((ref) => ApiClient());
final sessionProvider = ChangeNotifierProvider((ref) => Session(ref.read(apiProvider)));
final shareProvider = ChangeNotifierProvider((ref) => SharedReport());

class ApiClient {
  final Dio dio = Dio(BaseOptions(baseUrl: apiBaseUrl, connectTimeout: const Duration(seconds: 10)));
  final FlutterSecureStorage storage = const FlutterSecureStorage();
  Future<String?> token() => storage.read(key: 'access_token');
  Future<Options> auth() async {
    final value = await token();
    if (value == null) throw StateError('Sign in required');
    return Options(headers: {'Authorization': 'Bearer $value'});
  }
  Future<Map<String, dynamic>> login(String email, String password) async {
    final response = await dio.post<Map<String, dynamic>>('/auth/token', data: {'username': email, 'password': password}, options: Options(contentType: Headers.formUrlEncodedContentType));
    await storage.write(key: 'access_token', value: response.data!['access_token'] as String);
    return me();
  }
  Future<Map<String, dynamic>> me() async => (await dio.get<Map<String, dynamic>>('/auth/me', options: await auth())).data!;
  Future<Map<String, dynamic>> submit(String url, String statement, String sharedText) async =>
    (await dio.post<Map<String, dynamic>>('/reports', data: {'url': url, 'victim_statement': statement.isEmpty ? null : statement, 'shared_text': sharedText.isEmpty ? null : sharedText}, options: await auth())).data!;
  Future<Map<String, dynamic>> evidence(String id) async => (await dio.get<Map<String, dynamic>>('/evidence/$id', options: await auth())).data!;
  Future<void> changePassword(String currentPassword, String newPassword) async {
    await dio.post<void>('/auth/change-password', data: {'current_password': currentPassword, 'new_password': newPassword}, options: await auth());
  }
  Future<void> logout() async {
    try { await dio.post<void>('/auth/logout', options: await auth()); } finally { await storage.delete(key: 'access_token'); }
  }
}

class Session extends ChangeNotifier {
  Session(this.api) { restore(); }
  final ApiClient api;
  Map<String, dynamic>? account;
  bool loading = true;
  Future<void> restore() async {
    try { if (await api.token() != null) account = await api.me(); }
    on DioException catch (error) {
      account = null;
      if (error.response?.statusCode == 401) await api.storage.delete(key: 'access_token');
    } catch (_) { account = null; }
    if (account != null && account!['role'] != 'victim') { await api.storage.delete(key: 'access_token'); account = null; }
    loading = false; notifyListeners();
  }
  Future<void> login(String email, String password) async {
    account = await api.login(email, password);
    if (account!['role'] != 'victim') {
      await api.storage.delete(key: 'access_token'); account = null;
      throw StateError('Use a victim account for mobile reporting.');
    }
    notifyListeners();
  }
  Future<void> expire() async { await api.storage.delete(key: 'access_token'); account = null; notifyListeners(); }
  Future<void> changePassword(String currentPassword, String newPassword) async {
    await api.changePassword(currentPassword, newPassword);
    await expire();
  }
  Future<void> logout() async {
    try { await api.logout(); } finally { account = null; notifyListeners(); }
  }
}

class SharedReport extends ChangeNotifier {
  String url = '';
  String sharedText = '';
  void receive(String? value) {
    if (value == null || value.trim().isEmpty) return;
    final text = value.trim();
    final match = RegExp(r"https?://[^\s<>]+", caseSensitive: false).firstMatch(text);
    if (match != null) {
      final candidate = match.group(0)!.replaceAll(RegExp(r'''[.,;!?)\]\}"']+$'''), '');
      final parsed = Uri.tryParse(candidate);
      if (parsed != null && parsed.host.isNotEmpty) url = candidate;
    }
    sharedText = text.length > 4000 ? text.substring(0, 4000) : text;
    notifyListeners();
  }
  void clear() { url = ''; sharedText = ''; notifyListeners(); }
}

void main() {
  if (kReleaseMode && !apiBaseUrl.startsWith('https://')) {
    throw StateError('A HTTPS SAFE_ARCHIVE_API_URL is required for release builds');
  }
  runApp(const ProviderScope(child: SafeArchiveApp()));
}

class SafeArchiveApp extends ConsumerStatefulWidget {
  const SafeArchiveApp({super.key});
  @override ConsumerState<SafeArchiveApp> createState() => _SafeArchiveAppState();
}

class _SafeArchiveAppState extends ConsumerState<SafeArchiveApp> {
  StreamSubscription<SharedMedia>? shares;
  late final GoRouter router = GoRouter(routes: [
    GoRoute(path: '/', builder: (context, state) => const HomeScreen()),
    GoRoute(path: '/login', builder: (context, state) => const LoginScreen()),
    GoRoute(path: '/password', builder: (context, state) => const PasswordScreen()),
    GoRoute(path: '/report', builder: (context, state) => const ReportScreen()),
    GoRoute(path: '/receipt/:id', builder: (context, state) => ReceiptScreen(id: state.pathParameters['id']!)),
  ]);
  @override void initState() {
    super.initState();
    final handler = ShareHandler.instance;
    handler.getInitialSharedMedia().then((media) { if (mounted) receive(media?.content); });
    shares = handler.sharedMediaStream.listen((media) => receive(media.content));
  }
  void receive(String? text) {
    if (text == null) return;
    ref.read(shareProvider).receive(text);
    router.go('/report');
  }
  @override void dispose() { shares?.cancel(); router.dispose(); super.dispose(); }
  @override Widget build(BuildContext context) => MaterialApp.router(
    title: 'SAFE-ARCHIVE', debugShowCheckedModeBanner: false,
    theme: ThemeData(useMaterial3: true, colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF23364D))),
    routerConfig: router,
  );
}

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});
  @override Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionProvider);
    return Scaffold(appBar: AppBar(title: const Text('SAFE-ARCHIVE')), body: Center(child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 480), child: Padding(padding: const EdgeInsets.all(24),
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('Preserve public evidence', style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: 16), const Text('Share a public post to SAFE-ARCHIVE, or paste its link here. A case record will be created for review.'),
        const SizedBox(height: 16), const Card(child: Padding(padding: EdgeInsets.all(16), child: Text('Only public pages can be captured. Do not submit passwords or private messages. If you are in immediate danger, contact local emergency services.'))),
        const SizedBox(height: 20),
        if (session.loading) const CircularProgressIndicator() else if (session.account == null)
          FilledButton(onPressed: () => context.go('/login'), child: const Text('Sign in'))
        else ...[
          Text('Signed in as ${session.account!['email']}'),
          FilledButton(onPressed: () => context.go('/report'), child: const Text('Report a public link')),
          TextButton(onPressed: () => context.go('/password'), child: const Text('Change password')),
          TextButton(onPressed: () => ref.read(sessionProvider).logout(), child: const Text('Sign out')),
        ],
      ]),
    ))));
  }
}

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});
  @override ConsumerState<LoginScreen> createState() => _LoginScreenState();
}
class _LoginScreenState extends ConsumerState<LoginScreen> {
  final email = TextEditingController(), password = TextEditingController();
  bool busy = false; String? message;
  @override void dispose() { email.dispose(); password.dispose(); super.dispose(); }
  @override Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: const Text('Sign in')),
    body: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 480), child: Padding(
      padding: const EdgeInsets.all(24), child: Column(mainAxisSize: MainAxisSize.min, children: [
        TextField(controller: email, keyboardType: TextInputType.emailAddress, decoration: const InputDecoration(labelText: 'Email')),
        TextField(controller: password, obscureText: true, decoration: const InputDecoration(labelText: 'Password')),
        if (message != null) Text(message!, style: const TextStyle(color: Colors.red)),
        const SizedBox(height: 20),
        FilledButton(onPressed: busy ? null : () async {
          setState(() { busy = true; message = null; });
          try { await ref.read(sessionProvider).login(email.text.trim(), password.text); if (context.mounted) context.go('/report'); }
          catch (error) { if (mounted) setState(() => message = error is DioException ? 'Sign in failed. Check your details and connection.' : error.toString()); }
          finally { if (mounted) setState(() => busy = false); }
        }, child: const Text('Sign in')),
      ]),
    ))));
}

class PasswordScreen extends ConsumerStatefulWidget {
  const PasswordScreen({super.key});
  @override ConsumerState<PasswordScreen> createState() => _PasswordScreenState();
}

class _PasswordScreenState extends ConsumerState<PasswordScreen> {
  final current = TextEditingController(), next = TextEditingController(), confirmation = TextEditingController();
  bool busy = false;
  String? message;
  @override void dispose() { current.dispose(); next.dispose(); confirmation.dispose(); super.dispose(); }
  @override Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: const Text('Change password')),
    body: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 480), child: ListView(
      padding: const EdgeInsets.all(24), children: [
        TextField(controller: current, obscureText: true, decoration: const InputDecoration(labelText: 'Current password')),
        TextField(controller: next, obscureText: true, decoration: const InputDecoration(labelText: 'New password')),
        TextField(controller: confirmation, obscureText: true, decoration: const InputDecoration(labelText: 'Confirm new password')),
        if (message != null) Padding(padding: const EdgeInsets.only(top: 12), child: Text(message!, style: const TextStyle(color: Colors.red))),
        const SizedBox(height: 20),
        FilledButton(onPressed: busy ? null : () async {
          if (next.text.length < 12 || next.text != confirmation.text) {
            setState(() => message = 'Use at least 12 characters and confirm the new password.');
            return;
          }
          setState(() { busy = true; message = null; });
          try {
            await ref.read(sessionProvider).changePassword(current.text, next.text);
            if (context.mounted) context.go('/login');
          } on DioException catch (error) {
            if (mounted) setState(() => message = error.response?.statusCode == 400 ? 'Current password is incorrect.' : 'Could not change the password.');
          } finally {
            if (mounted) setState(() => busy = false);
          }
        }, child: const Text('Change password')),
      ],
    ))));
}

class ReportScreen extends ConsumerStatefulWidget {
  const ReportScreen({super.key});
  @override ConsumerState<ReportScreen> createState() => _ReportScreenState();
}
class _ReportScreenState extends ConsumerState<ReportScreen> {
  final url = TextEditingController(), statement = TextEditingController();
  bool busy = false; String? seededShareUrl, message;
  @override void dispose() { url.dispose(); statement.dispose(); super.dispose(); }
  @override Widget build(BuildContext context) {
    final session = ref.watch(sessionProvider), shared = ref.watch(shareProvider);
    if (shared.url.isEmpty) {
      seededShareUrl = null;
    } else if (seededShareUrl != shared.url) {
      url.text = shared.url;
      seededShareUrl = shared.url;
    }
    return Scaffold(appBar: AppBar(title: const Text('Report a public link')), body: Center(child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 540), child: ListView(padding: const EdgeInsets.all(24), children: [
        if (session.account == null) ...[
          const Text('Sign in to submit your report.'),
          FilledButton(onPressed: () => context.go('/login'), child: const Text('Sign in')),
        ] else ...[
          Text('What would you like to preserve?', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 16),
          TextField(controller: url, keyboardType: TextInputType.url, decoration: const InputDecoration(labelText: 'Public post URL', border: OutlineInputBorder())),
          const SizedBox(height: 16),
          TextField(controller: statement, maxLines: 4, maxLength: 4000, decoration: const InputDecoration(labelText: 'What happened? (optional)', border: OutlineInputBorder())),
          if (shared.sharedText.isNotEmpty) Card(child: Padding(padding: const EdgeInsets.all(12), child: Text('Shared text: ${shared.sharedText}'))),
          const SizedBox(height: 12), const Text('Submission queues a capture of publicly visible content. Capture may fail if a site blocks automated access.'),
          if (message != null) Text(message!, style: const TextStyle(color: Colors.red)),
          const SizedBox(height: 20),
          FilledButton(onPressed: busy ? null : () async {
            final value = url.text.trim(), uri = Uri.tryParse(url.text.trim());
            if (uri == null || !['http', 'https'].contains(uri.scheme) || uri.host.isEmpty) {
              setState(() => message = 'Enter a public HTTP(S) link.'); return;
            }
            setState(() { busy = true; message = null; });
            try {
              final receipt = await ref.read(apiProvider).submit(value, statement.text.trim(), shared.sharedText);
              ref.read(shareProvider).clear();
              if (context.mounted) context.go('/receipt/${receipt['evidence_id']}');
            } on DioException catch (error) {
              if (error.response?.statusCode == 401) {
                await ref.read(sessionProvider).expire();
                if (context.mounted) context.go('/login');
              } else if (mounted) {
                setState(() => message = 'Could not submit. Check your connection and link.');
              }
            } finally { if (mounted) setState(() => busy = false); }
          }, child: Text(busy ? 'Submitting…' : 'Submit report')),
        ],
      ]),
    )));
  }
}

class ReceiptScreen extends ConsumerStatefulWidget {
  const ReceiptScreen({required this.id, super.key});
  final String id;
  @override ConsumerState<ReceiptScreen> createState() => _ReceiptScreenState();
}
class _ReceiptScreenState extends ConsumerState<ReceiptScreen> {
  Map<String, dynamic>? evidence; String? message; bool busy = false;
  @override void initState() { super.initState(); refresh(); }
  Future<void> refresh() async {
    setState(() { busy = true; message = null; });
    try { final result = await ref.read(apiProvider).evidence(widget.id); if (mounted) setState(() => evidence = result); }
    catch (_) { if (mounted) setState(() => message = 'Could not load capture status.'); }
    finally { if (mounted) setState(() => busy = false); }
  }
  @override Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: const Text('Submission received')),
    body: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 480), child: Padding(
      padding: const EdgeInsets.all(24), child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('Your link was submitted', style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 12), Text('Reference: ${widget.id}'),
        Text('Capture status: ${evidence?['capture_status'] ?? 'queued'}'),
        if (evidence?['capture_error'] != null) Text('Reason: ${evidence!['capture_error']}'),
        if (evidence?['hash_sha256'] != null) SelectableText('SHA-256: ${evidence!['hash_sha256']}'),
        if (message != null) Text(message!, style: const TextStyle(color: Colors.red)),
        const SizedBox(height: 20),
        OutlinedButton(onPressed: busy ? null : refresh, child: const Text('Refresh status')),
        TextButton(onPressed: () => context.go('/'), child: const Text('Done')),
      ]),
    ))));
}
