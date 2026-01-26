import 'package:flutter/material.dart';

import '../../../../core/theme/app_theme.dart';
import '../../data/models/analysis_model.dart';

class RegimeInfoCard extends StatelessWidget {
  final AnalysisModel analysis;

  const RegimeInfoCard({required this.analysis, super.key});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Market Context',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 16),

            // Regime row
            Row(
              children: [
                Expanded(
                  child: _InfoTile(
                    label: 'REGIME',
                    value: analysis.regime.replaceAll('_', ' '),
                    valueColor: _getRegimeColor(analysis.regime),
                  ),
                ),
                Expanded(
                  child: _InfoTile(
                    label: 'ALIGNMENT',
                    value: '${analysis.alignment}/5',
                  ),
                ),
                Expanded(
                  child: _InfoTile(
                    label: 'BREADTH',
                    value: '${(analysis.breadth * 100).toInt()}%',
                    subtitle: analysis.breadthState,
                  ),
                ),
              ],
            ),
            const Divider(height: 24),

            // Technical row
            Row(
              children: [
                Expanded(
                  child: _InfoTile(
                    label: 'TREND',
                    value: analysis.trend,
                    valueColor: analysis.trend == 'UPTREND'
                        ? AppTheme.bullColor
                        : analysis.trend == 'DOWNTREND'
                            ? AppTheme.bearColor
                            : null,
                  ),
                ),
                Expanded(
                  child: _InfoTile(
                    label: 'EXTENSION',
                    value: analysis.extension,
                    subtitle: '${analysis.extensionPercent.toStringAsFixed(1)}% from MA200',
                  ),
                ),
                Expanded(
                  child: _InfoTile(
                    label: 'VOLUME',
                    value: analysis.volume,
                  ),
                ),
              ],
            ),
            const Divider(height: 24),

            // Relative Strength row
            Row(
              children: [
                Expanded(
                  child: _InfoTile(
                    label: 'RS vs SPY',
                    value: '${analysis.rsVsSpy >= 0 ? '+' : ''}${analysis.rsVsSpy.toStringAsFixed(1)}%',
                    valueColor: analysis.rsVsSpy >= 0 ? AppTheme.bullColor : AppTheme.bearColor,
                  ),
                ),
                Expanded(
                  child: _InfoTile(
                    label: 'RS vs SECTOR',
                    value: '${analysis.rsVsSector >= 0 ? '+' : ''}${analysis.rsVsSector.toStringAsFixed(1)}%',
                    valueColor: analysis.rsVsSector >= 0 ? AppTheme.bullColor : AppTheme.bearColor,
                  ),
                ),
                Expanded(
                  child: _InfoTile(
                    label: 'RS SCORE',
                    value: '${analysis.rsScore}/40',
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Color _getRegimeColor(String regime) {
    final upper = regime.toUpperCase();
    if (upper.contains('BULL')) return AppTheme.bullColor;
    if (upper.contains('BEAR')) return AppTheme.bearColor;
    if (upper.contains('AMBIGUOUS')) return AppTheme.ambiguousColor;
    return AppTheme.neutralColor;
  }
}

class _InfoTile extends StatelessWidget {
  final String label;
  final String value;
  final String? subtitle;
  final Color? valueColor;

  const _InfoTile({
    required this.label,
    required this.value,
    this.subtitle,
    this.valueColor,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: TextStyle(
            fontSize: 10,
            fontWeight: FontWeight.w600,
            color: Colors.grey.shade500,
            letterSpacing: 0.5,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          value,
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            color: valueColor ?? Colors.grey.shade800,
          ),
        ),
        if (subtitle != null)
          Text(
            subtitle!,
            style: TextStyle(
              fontSize: 11,
              color: Colors.grey.shade600,
            ),
          ),
      ],
    );
  }
}
