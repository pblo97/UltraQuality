import 'package:flutter/material.dart';

import '../../../../core/theme/app_theme.dart';
import '../../data/models/analysis_model.dart';

class RecommendationCard extends StatelessWidget {
  final AnalysisModel analysis;

  const RecommendationCard({required this.analysis, super.key});

  @override
  Widget build(BuildContext context) {
    final config = _getActionConfig(analysis.action);

    return Card(
      clipBehavior: Clip.antiAlias,
      child: Container(
        decoration: BoxDecoration(
          border: Border(
            left: BorderSide(color: config.color, width: 4),
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: config.color.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  config.icon,
                  color: config.color,
                  size: 24,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      config.label,
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: config.color,
                      ),
                    ),
                    if (analysis.recommendation.isNotEmpty)
                      Text(
                        analysis.recommendation,
                        style: TextStyle(
                          fontSize: 13,
                          color: Colors.grey.shade600,
                        ),
                      ),
                  ],
                ),
              ),
              // Combined score
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    analysis.combinedScore.toInt().toString(),
                    style: const TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  Text(
                    'Combined',
                    style: TextStyle(
                      fontSize: 11,
                      color: Colors.grey.shade600,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  _ActionConfig _getActionConfig(String action) {
    switch (action.toUpperCase()) {
      case 'BUY':
      case 'STRONG_BUY':
        return _ActionConfig(
          label: 'BUY',
          icon: Icons.arrow_upward,
          color: AppTheme.bullColor,
        );
      case 'SELL':
      case 'STRONG_SELL':
        return _ActionConfig(
          label: 'SELL',
          icon: Icons.arrow_downward,
          color: AppTheme.bearColor,
        );
      case 'HOLD':
        return _ActionConfig(
          label: 'HOLD',
          icon: Icons.pause,
          color: AppTheme.ambiguousColor,
        );
      case 'AVOID':
        return _ActionConfig(
          label: 'AVOID',
          icon: Icons.block,
          color: AppTheme.bearColor,
        );
      default:
        return _ActionConfig(
          label: action,
          icon: Icons.help_outline,
          color: AppTheme.neutralColor,
        );
    }
  }
}

class _ActionConfig {
  final String label;
  final IconData icon;
  final Color color;

  _ActionConfig({
    required this.label,
    required this.icon,
    required this.color,
  });
}
