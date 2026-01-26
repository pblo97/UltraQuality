import 'package:hive/hive.dart';
import 'package:equatable/equatable.dart';

@HiveType(typeId: 2)
class RegimeSnapshot extends Equatable {
  @HiveField(0)
  final String globalRegime;

  @HiveField(1)
  final int alignment;

  @HiveField(2)
  final double breadth;

  @HiveField(3)
  final String breadthState;

  @HiveField(4)
  final String regionalRegime;

  @HiveField(5)
  final Map<String, String> sectorRegimes;

  @HiveField(6)
  final double environmentMultiplier;

  @HiveField(7)
  final bool killSwitchActive;

  @HiveField(8)
  final List<String> activeVetoes;

  @HiveField(9)
  final List<String> activeWarnings;

  @HiveField(10)
  final DateTime timestamp;

  @HiveField(11)
  final Map<String, double> indexReturns;

  const RegimeSnapshot({
    required this.globalRegime,
    required this.alignment,
    required this.breadth,
    required this.breadthState,
    required this.regionalRegime,
    required this.sectorRegimes,
    required this.environmentMultiplier,
    required this.killSwitchActive,
    required this.activeVetoes,
    required this.activeWarnings,
    required this.timestamp,
    required this.indexReturns,
  });

  factory RegimeSnapshot.fromJson(Map<String, dynamic> json) {
    return RegimeSnapshot(
      globalRegime: json['global_regime'] ?? 'UNKNOWN',
      alignment: json['alignment'] ?? 0,
      breadth: (json['breadth'] ?? 0).toDouble(),
      breadthState: json['breadth_state'] ?? 'NEUTRAL',
      regionalRegime: json['regional_regime'] ?? 'UNKNOWN',
      sectorRegimes: Map<String, String>.from(json['sector_regimes'] ?? {}),
      environmentMultiplier: (json['environment_multiplier'] ?? 1).toDouble(),
      killSwitchActive: json['kill_switch_active'] ?? false,
      activeVetoes: List<String>.from(json['vetoes'] ?? []),
      activeWarnings: List<String>.from(json['warnings'] ?? []),
      timestamp: json['timestamp'] != null
          ? DateTime.parse(json['timestamp'])
          : DateTime.now(),
      indexReturns: Map<String, double>.from(
        (json['index_returns'] ?? {}).map(
          (k, v) => MapEntry(k, (v as num).toDouble()),
        ),
      ),
    );
  }

  Map<String, dynamic> toJson() => {
        'global_regime': globalRegime,
        'alignment': alignment,
        'breadth': breadth,
        'breadth_state': breadthState,
        'regional_regime': regionalRegime,
        'sector_regimes': sectorRegimes,
        'environment_multiplier': environmentMultiplier,
        'kill_switch_active': killSwitchActive,
        'vetoes': activeVetoes,
        'warnings': activeWarnings,
        'timestamp': timestamp.toIso8601String(),
        'index_returns': indexReturns,
      };

  // Helper getters
  bool get isBull => globalRegime.toUpperCase().contains('BULL');
  bool get isBear => globalRegime.toUpperCase().contains('BEAR');
  bool get isAmbiguous => globalRegime.toUpperCase().contains('AMBIGUOUS');

  String get alignmentDisplay => '$alignment/5';
  String get breadthDisplay => '${(breadth * 100).toStringAsFixed(0)}%';

  bool get hasIssues => killSwitchActive || activeVetoes.isNotEmpty;

  @override
  List<Object?> get props => [globalRegime, alignment, breadth, timestamp];
}

// Hive adapter
class RegimeSnapshotAdapter extends TypeAdapter<RegimeSnapshot> {
  @override
  final int typeId = 2;

  @override
  RegimeSnapshot read(BinaryReader reader) {
    final json = Map<String, dynamic>.from(reader.readMap());
    return RegimeSnapshot.fromJson(json);
  }

  @override
  void write(BinaryWriter writer, RegimeSnapshot obj) {
    writer.writeMap(obj.toJson());
  }
}
