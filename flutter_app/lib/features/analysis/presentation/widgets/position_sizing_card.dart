import 'package:flutter/material.dart';

import '../../data/models/analysis_model.dart';

class PositionSizingCard extends StatelessWidget {
  final AnalysisModel analysis;
  final double portfolioValue;
  final double riskPerTrade;

  const PositionSizingCard({
    required this.analysis,
    this.portfolioValue = 100000,
    this.riskPerTrade = 0.005,
    super.key,
  });

  @override
  Widget build(BuildContext context) {
    // Calculate position size based on conviction
    final conviction = analysis.conviction.final_;
    final allocationPercent = conviction * 10; // Max 10% for conviction 1.0
    final positionSize = portfolioValue * (allocationPercent / 100);
    final shares = (positionSize / analysis.currentPrice).floor();
    final actualInvestment = shares * analysis.currentPrice;
    final stopDistance = ((analysis.currentPrice - analysis.stopLoss) / analysis.currentPrice) * 100;
    final maxLoss = actualInvestment * (stopDistance / 100);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Position Sizing',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 16),

            // Main metrics row
            Row(
              children: [
                Expanded(
                  child: _MetricBox(
                    label: 'POSITION SIZE',
                    value: '\$${_formatNumber(actualInvestment)}',
                    subtitle: '${allocationPercent.toStringAsFixed(1)}% of portfolio',
                    highlight: true,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _MetricBox(
                    label: 'SHARES',
                    value: shares.toString(),
                    subtitle: '@ \$${analysis.currentPrice.toStringAsFixed(2)}',
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),

            // Risk metrics row
            Row(
              children: [
                Expanded(
                  child: _MetricBox(
                    label: 'STOP LOSS',
                    value: '\$${analysis.stopLoss.toStringAsFixed(2)}',
                    subtitle: '${stopDistance.toStringAsFixed(1)}% below entry',
                    isRisk: true,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _MetricBox(
                    label: 'MAX LOSS',
                    value: '\$${_formatNumber(maxLoss)}',
                    subtitle: '${(maxLoss / portfolioValue * 100).toStringAsFixed(2)}% of portfolio',
                    isRisk: true,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Conviction constraint note
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.blue.shade50,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Icon(Icons.info_outline, size: 18, color: Colors.blue.shade700),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Limited by conviction cap (${conviction.toStringAsFixed(2)})',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.blue.shade900,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _formatNumber(double value) {
    if (value >= 1000) {
      return '${(value / 1000).toStringAsFixed(1)}K';
    }
    return value.toStringAsFixed(0);
  }
}

class _MetricBox extends StatelessWidget {
  final String label;
  final String value;
  final String subtitle;
  final bool highlight;
  final bool isRisk;

  const _MetricBox({
    required this.label,
    required this.value,
    required this.subtitle,
    this.highlight = false,
    this.isRisk = false,
  });

  @override
  Widget build(BuildContext context) {
    final bgColor = highlight
        ? Colors.blue.shade50
        : isRisk
            ? Colors.red.shade50
            : Colors.grey.shade50;
    final valueColor = highlight
        ? Colors.blue.shade700
        : isRisk
            ? Colors.red.shade700
            : Colors.grey.shade800;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w600,
              color: Colors.grey.shade600,
              letterSpacing: 0.5,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: valueColor,
            ),
          ),
          Text(
            subtitle,
            style: TextStyle(
              fontSize: 11,
              color: Colors.grey.shade600,
            ),
          ),
        ],
      ),
    );
  }
}
