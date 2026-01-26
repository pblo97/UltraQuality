import 'package:hive_flutter/hive_flutter.dart';
import 'package:path_provider/path_provider.dart';

import '../../features/analysis/data/models/analysis_model.dart';
import '../../features/portfolio/data/models/position_model.dart';
import '../../features/regime/data/models/regime_model.dart';

class LocalDatabase {
  // Box names
  static const String analysisBox = 'analyses';
  static const String portfolioBox = 'portfolio';
  static const String regimeBox = 'regime_history';
  static const String settingsBox = 'settings';
  static const String watchlistBox = 'watchlist';

  /// Initialize Hive and register adapters
  static Future<void> init() async {
    final appDocDir = await getApplicationDocumentsDirectory();
    await Hive.initFlutter(appDocDir.path);

    // Register adapters
    Hive.registerAdapter(AnalysisModelAdapter());
    Hive.registerAdapter(PositionModelAdapter());
    Hive.registerAdapter(RegimeSnapshotAdapter());
    Hive.registerAdapter(ConvictionBreakdownAdapter());

    // Open boxes
    await Future.wait([
      Hive.openBox<AnalysisModel>(analysisBox),
      Hive.openBox<PositionModel>(portfolioBox),
      Hive.openBox<RegimeSnapshot>(regimeBox),
      Hive.openBox(settingsBox),
      Hive.openBox<List<String>>(watchlistBox),
    ]);
  }

  // ==================== ANALYSIS ====================

  static Box<AnalysisModel> get _analysisBox =>
      Hive.box<AnalysisModel>(analysisBox);

  /// Save analysis result
  static Future<void> saveAnalysis(AnalysisModel analysis) async {
    final key = '${analysis.ticker}_${analysis.analyzedAt.millisecondsSinceEpoch}';
    await _analysisBox.put(key, analysis);
  }

  /// Get latest analysis for a ticker
  static AnalysisModel? getLatestAnalysis(String ticker) {
    final analyses = _analysisBox.values
        .where((a) => a.ticker == ticker)
        .toList()
      ..sort((a, b) => b.analyzedAt.compareTo(a.analyzedAt));
    return analyses.isNotEmpty ? analyses.first : null;
  }

  /// Get analysis history for a ticker
  static List<AnalysisModel> getAnalysisHistory(String ticker, {int limit = 30}) {
    final analyses = _analysisBox.values
        .where((a) => a.ticker == ticker)
        .toList()
      ..sort((a, b) => b.analyzedAt.compareTo(a.analyzedAt));
    return analyses.take(limit).toList();
  }

  /// Get all recent analyses
  static List<AnalysisModel> getRecentAnalyses({int limit = 50}) {
    final analyses = _analysisBox.values.toList()
      ..sort((a, b) => b.analyzedAt.compareTo(a.analyzedAt));
    return analyses.take(limit).toList();
  }

  // ==================== PORTFOLIO ====================

  static Box<PositionModel> get _portfolioBox =>
      Hive.box<PositionModel>(portfolioBox);

  /// Save position
  static Future<void> savePosition(PositionModel position) async {
    await _portfolioBox.put(position.ticker, position);
  }

  /// Get all positions
  static List<PositionModel> getPositions() {
    return _portfolioBox.values.toList();
  }

  /// Remove position
  static Future<void> removePosition(String ticker) async {
    await _portfolioBox.delete(ticker);
  }

  // ==================== REGIME ====================

  static Box<RegimeSnapshot> get _regimeBox =>
      Hive.box<RegimeSnapshot>(regimeBox);

  /// Save regime snapshot
  static Future<void> saveRegimeSnapshot(RegimeSnapshot snapshot) async {
    final key = snapshot.timestamp.millisecondsSinceEpoch.toString();
    await _regimeBox.put(key, snapshot);
  }

  /// Get regime history
  static List<RegimeSnapshot> getRegimeHistory({int days = 30}) {
    final cutoff = DateTime.now().subtract(Duration(days: days));
    return _regimeBox.values
        .where((r) => r.timestamp.isAfter(cutoff))
        .toList()
      ..sort((a, b) => b.timestamp.compareTo(a.timestamp));
  }

  // ==================== SETTINGS ====================

  static Box get _settingsBox => Hive.box(settingsBox);

  static T? getSetting<T>(String key) => _settingsBox.get(key) as T?;

  static Future<void> setSetting<T>(String key, T value) async {
    await _settingsBox.put(key, value);
  }

  // ==================== WATCHLIST ====================

  static Box<List<String>> get _watchlistBox =>
      Hive.box<List<String>>(watchlistBox);

  static List<String> getWatchlist(String name) {
    return _watchlistBox.get(name) ?? [];
  }

  static Future<void> saveWatchlist(String name, List<String> tickers) async {
    await _watchlistBox.put(name, tickers);
  }
}
