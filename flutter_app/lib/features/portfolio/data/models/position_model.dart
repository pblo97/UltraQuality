import 'package:hive/hive.dart';
import 'package:equatable/equatable.dart';

@HiveType(typeId: 3)
class PositionModel extends Equatable {
  @HiveField(0)
  final String ticker;

  @HiveField(1)
  final String companyName;

  @HiveField(2)
  final int shares;

  @HiveField(3)
  final double avgCost;

  @HiveField(4)
  final double currentPrice;

  @HiveField(5)
  final double stopLoss;

  @HiveField(6)
  final DateTime entryDate;

  @HiveField(7)
  final double conviction;

  @HiveField(8)
  final String entryRegime;

  @HiveField(9)
  final String notes;

  const PositionModel({
    required this.ticker,
    required this.companyName,
    required this.shares,
    required this.avgCost,
    required this.currentPrice,
    required this.stopLoss,
    required this.entryDate,
    required this.conviction,
    required this.entryRegime,
    this.notes = '',
  });

  // Calculated properties
  double get marketValue => shares * currentPrice;
  double get costBasis => shares * avgCost;
  double get unrealizedPnL => marketValue - costBasis;
  double get unrealizedPnLPercent => costBasis > 0 ? (unrealizedPnL / costBasis) * 100 : 0;
  double get riskToStop => ((currentPrice - stopLoss) / currentPrice) * 100;

  bool get isInProfit => unrealizedPnL > 0;
  bool get isNearStop => riskToStop < 3; // Within 3% of stop

  factory PositionModel.fromJson(Map<String, dynamic> json) {
    return PositionModel(
      ticker: json['ticker'] ?? '',
      companyName: json['company_name'] ?? '',
      shares: json['shares'] ?? 0,
      avgCost: (json['avg_cost'] ?? 0).toDouble(),
      currentPrice: (json['current_price'] ?? 0).toDouble(),
      stopLoss: (json['stop_loss'] ?? 0).toDouble(),
      entryDate: json['entry_date'] != null
          ? DateTime.parse(json['entry_date'])
          : DateTime.now(),
      conviction: (json['conviction'] ?? 0).toDouble(),
      entryRegime: json['entry_regime'] ?? 'UNKNOWN',
      notes: json['notes'] ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'ticker': ticker,
        'company_name': companyName,
        'shares': shares,
        'avg_cost': avgCost,
        'current_price': currentPrice,
        'stop_loss': stopLoss,
        'entry_date': entryDate.toIso8601String(),
        'conviction': conviction,
        'entry_regime': entryRegime,
        'notes': notes,
      };

  PositionModel copyWith({
    String? ticker,
    String? companyName,
    int? shares,
    double? avgCost,
    double? currentPrice,
    double? stopLoss,
    DateTime? entryDate,
    double? conviction,
    String? entryRegime,
    String? notes,
  }) {
    return PositionModel(
      ticker: ticker ?? this.ticker,
      companyName: companyName ?? this.companyName,
      shares: shares ?? this.shares,
      avgCost: avgCost ?? this.avgCost,
      currentPrice: currentPrice ?? this.currentPrice,
      stopLoss: stopLoss ?? this.stopLoss,
      entryDate: entryDate ?? this.entryDate,
      conviction: conviction ?? this.conviction,
      entryRegime: entryRegime ?? this.entryRegime,
      notes: notes ?? this.notes,
    );
  }

  @override
  List<Object?> get props => [ticker, shares, avgCost, entryDate];
}

// Hive adapter
class PositionModelAdapter extends TypeAdapter<PositionModel> {
  @override
  final int typeId = 3;

  @override
  PositionModel read(BinaryReader reader) {
    final json = Map<String, dynamic>.from(reader.readMap());
    return PositionModel.fromJson(json);
  }

  @override
  void write(BinaryWriter writer, PositionModel obj) {
    writer.writeMap(obj.toJson());
  }
}
