import 'package:hive/hive.dart';
import 'package:equatable/equatable.dart';

part 'analysis_model.g.dart';

@HiveType(typeId: 0)
class AnalysisModel extends Equatable {
  @HiveField(0)
  final String ticker;

  @HiveField(1)
  final String companyName;

  @HiveField(2)
  final String sector;

  @HiveField(3)
  final double technicalScore;

  @HiveField(4)
  final double fundamentalScore;

  @HiveField(5)
  final double combinedScore;

  @HiveField(6)
  final ConvictionBreakdown conviction;

  @HiveField(7)
  final String regime;

  @HiveField(8)
  final int alignment;

  @HiveField(9)
  final double breadth;

  @HiveField(10)
  final String breadthState;

  @HiveField(11)
  final String trend;

  @HiveField(12)
  final String extension;

  @HiveField(13)
  final double extensionPercent;

  @HiveField(14)
  final String volume;

  @HiveField(15)
  final double rsVsSpy;

  @HiveField(16)
  final double rsVsSector;

  @HiveField(17)
  final int rsScore;

  @HiveField(18)
  final double sharpeRatio;

  @HiveField(19)
  final double volatility;

  @HiveField(20)
  final String recommendation;

  @HiveField(21)
  final String action;

  @HiveField(22)
  final List<String> warnings;

  @HiveField(23)
  final List<String> vetoes;

  @HiveField(24)
  final DateTime analyzedAt;

  @HiveField(25)
  final double currentPrice;

  @HiveField(26)
  final double stopLoss;

  @HiveField(27)
  final double atr;

  const AnalysisModel({
    required this.ticker,
    required this.companyName,
    required this.sector,
    required this.technicalScore,
    required this.fundamentalScore,
    required this.combinedScore,
    required this.conviction,
    required this.regime,
    required this.alignment,
    required this.breadth,
    required this.breadthState,
    required this.trend,
    required this.extension,
    required this.extensionPercent,
    required this.volume,
    required this.rsVsSpy,
    required this.rsVsSector,
    required this.rsScore,
    required this.sharpeRatio,
    required this.volatility,
    required this.recommendation,
    required this.action,
    required this.warnings,
    required this.vetoes,
    required this.analyzedAt,
    required this.currentPrice,
    required this.stopLoss,
    required this.atr,
  });

  factory AnalysisModel.fromJson(Map<String, dynamic> json) {
    return AnalysisModel(
      ticker: json['ticker'] ?? '',
      companyName: json['company_name'] ?? json['ticker'] ?? '',
      sector: json['sector'] ?? 'Unknown',
      technicalScore: (json['technical_score'] ?? 0).toDouble(),
      fundamentalScore: (json['fundamental_score'] ?? 0).toDouble(),
      combinedScore: (json['combined_score'] ?? 0).toDouble(),
      conviction: ConvictionBreakdown.fromJson(json['conviction'] ?? {}),
      regime: json['regime'] ?? 'UNKNOWN',
      alignment: json['alignment'] ?? 0,
      breadth: (json['breadth'] ?? 0).toDouble(),
      breadthState: json['breadth_state'] ?? 'NEUTRAL',
      trend: json['trend'] ?? 'UNKNOWN',
      extension: json['extension'] ?? 'NORMAL',
      extensionPercent: (json['extension_percent'] ?? 0).toDouble(),
      volume: json['volume'] ?? 'NEUTRAL',
      rsVsSpy: (json['rs_vs_spy'] ?? 0).toDouble(),
      rsVsSector: (json['rs_vs_sector'] ?? 0).toDouble(),
      rsScore: json['rs_score'] ?? 0,
      sharpeRatio: (json['sharpe_ratio'] ?? 0).toDouble(),
      volatility: (json['volatility'] ?? 0).toDouble(),
      recommendation: json['recommendation'] ?? '',
      action: json['action'] ?? 'HOLD',
      warnings: List<String>.from(json['warnings'] ?? []),
      vetoes: List<String>.from(json['vetoes'] ?? []),
      analyzedAt: json['analyzed_at'] != null
          ? DateTime.parse(json['analyzed_at'])
          : DateTime.now(),
      currentPrice: (json['current_price'] ?? 0).toDouble(),
      stopLoss: (json['stop_loss'] ?? 0).toDouble(),
      atr: (json['atr'] ?? 0).toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
        'ticker': ticker,
        'company_name': companyName,
        'sector': sector,
        'technical_score': technicalScore,
        'fundamental_score': fundamentalScore,
        'combined_score': combinedScore,
        'conviction': conviction.toJson(),
        'regime': regime,
        'alignment': alignment,
        'breadth': breadth,
        'breadth_state': breadthState,
        'trend': trend,
        'extension': extension,
        'extension_percent': extensionPercent,
        'volume': volume,
        'rs_vs_spy': rsVsSpy,
        'rs_vs_sector': rsVsSector,
        'rs_score': rsScore,
        'sharpe_ratio': sharpeRatio,
        'volatility': volatility,
        'recommendation': recommendation,
        'action': action,
        'warnings': warnings,
        'vetoes': vetoes,
        'analyzed_at': analyzedAt.toIso8601String(),
        'current_price': currentPrice,
        'stop_loss': stopLoss,
        'atr': atr,
      };

  // Helper getters
  String get convictionLevel {
    if (conviction.final_ >= 0.7) return 'HIGH';
    if (conviction.final_ >= 0.3) return 'MEDIUM';
    return 'LOW';
  }

  bool get isBullish => regime.toUpperCase().contains('BULL');
  bool get isBearish => regime.toUpperCase().contains('BEAR');
  bool get isAmbiguous => regime.toUpperCase().contains('AMBIGUOUS');

  bool get hasWarnings => warnings.isNotEmpty;
  bool get hasVetoes => vetoes.isNotEmpty;

  @override
  List<Object?> get props => [ticker, analyzedAt];
}

@HiveType(typeId: 1)
class ConvictionBreakdown extends Equatable {
  @HiveField(0)
  final double setup;

  @HiveField(1)
  final double market;

  @HiveField(2)
  final double timing;

  @HiveField(3)
  final double data;

  @HiveField(4)
  final double environment;

  @HiveField(5)
  final double final_;

  const ConvictionBreakdown({
    required this.setup,
    required this.market,
    required this.timing,
    required this.data,
    required this.environment,
    required this.final_,
  });

  factory ConvictionBreakdown.fromJson(Map<String, dynamic> json) {
    return ConvictionBreakdown(
      setup: (json['setup'] ?? 0).toDouble(),
      market: (json['market'] ?? 1).toDouble(),
      timing: (json['timing'] ?? 1).toDouble(),
      data: (json['data'] ?? 1).toDouble(),
      environment: (json['environment'] ?? 1).toDouble(),
      final_: (json['final'] ?? json['conviction'] ?? 0).toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
        'setup': setup,
        'market': market,
        'timing': timing,
        'data': data,
        'environment': environment,
        'final': final_,
      };

  String get formula => 'conviction = setup × timing × data × environment';

  String get calculation =>
      '${final_.toStringAsFixed(3)} = ${setup.toStringAsFixed(2)} × ${timing.toStringAsFixed(2)} × ${data.toStringAsFixed(2)} × ${environment.toStringAsFixed(2)}';

  @override
  List<Object?> get props => [setup, market, timing, data, environment, final_];
}

// Hive adapters will be generated by build_runner
class AnalysisModelAdapter extends TypeAdapter<AnalysisModel> {
  @override
  final int typeId = 0;

  @override
  AnalysisModel read(BinaryReader reader) {
    final json = Map<String, dynamic>.from(reader.readMap());
    return AnalysisModel.fromJson(json);
  }

  @override
  void write(BinaryWriter writer, AnalysisModel obj) {
    writer.writeMap(obj.toJson());
  }
}

class ConvictionBreakdownAdapter extends TypeAdapter<ConvictionBreakdown> {
  @override
  final int typeId = 1;

  @override
  ConvictionBreakdown read(BinaryReader reader) {
    final json = Map<String, dynamic>.from(reader.readMap());
    return ConvictionBreakdown.fromJson(json);
  }

  @override
  void write(BinaryWriter writer, ConvictionBreakdown obj) {
    writer.writeMap(obj.toJson());
  }
}
