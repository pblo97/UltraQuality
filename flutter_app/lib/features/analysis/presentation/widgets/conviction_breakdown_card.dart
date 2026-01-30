import 'package:flutter/material.dart';

import '../../../../core/theme/app_theme.dart';
import '../../data/models/analysis_model.dart';

class ConvictionBreakdownCard extends StatelessWidget {
  final ConvictionBreakdown conviction;
  final List<String> warnings;

  const ConvictionBreakdownCard({
    required this.conviction,
    required this.warnings,
    super.key,
  });

  @override
  Widget build(BuildContext context) {
    final convictionColor = _getConvictionColor(conviction.final_);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Conviction Breakdown',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: convictionColor.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    conviction.final_.toStringAsFixed(2),
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                      color: convictionColor,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Formula
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.grey.shade50,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    conviction.formula,
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey.shade600,
                      fontFamily: 'monospace',
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    conviction.calculation,
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      fontFamily: 'monospace',
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Factor bars
            _FactorBar(label: 'Setup', value: conviction.setup),
            _FactorBar(label: 'Timing', value: conviction.timing),
            _FactorBar(label: 'Data', value: conviction.data),
            _FactorBar(
              label: 'Environment',
              value: conviction.environment,
              highlight: conviction.environment < 1.0,
            ),
          ],
        ),
      ),
    );
  }

  Color _getConvictionColor(double value) {
    if (value >= 0.7) return AppTheme.highConviction;
    if (value >= 0.3) return AppTheme.mediumConviction;
    return AppTheme.lowConviction;
  }
}

class _FactorBar extends StatelessWidget {
  final String label;
  final double value;
  final bool highlight;

  const _FactorBar({
    required this.label,
    required this.value,
    this.highlight = false,
  });

  @override
  Widget build(BuildContext context) {
    final color = highlight ? Colors.orange : Colors.blue;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          SizedBox(
            width: 90,
            child: Text(
              label,
              style: TextStyle(
                fontSize: 13,
                color: highlight ? Colors.orange.shade700 : Colors.grey.shade700,
                fontWeight: highlight ? FontWeight.w600 : FontWeight.normal,
              ),
            ),
          ),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(3),
              child: LinearProgressIndicator(
                value: value.clamp(0.0, 1.0),
                minHeight: 6,
                backgroundColor: Colors.grey.shade200,
                valueColor: AlwaysStoppedAnimation(color),
              ),
            ),
          ),
          const SizedBox(width: 12),
          SizedBox(
            width: 40,
            child: Text(
              value.toStringAsFixed(2),
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w500,
                color: highlight ? Colors.orange.shade700 : Colors.grey.shade800,
              ),
              textAlign: TextAlign.right,
            ),
          ),
        ],
      ),
    );
  }
}
