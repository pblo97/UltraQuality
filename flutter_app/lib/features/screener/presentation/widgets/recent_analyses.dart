import 'package:flutter/material.dart';

import '../../../../core/database/database.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../analysis/data/models/analysis_model.dart';
import '../../../analysis/presentation/screens/analysis_screen.dart';

class RecentAnalysesList extends StatelessWidget {
  const RecentAnalysesList({super.key});

  @override
  Widget build(BuildContext context) {
    final analyses = LocalDatabase.getRecentAnalyses(limit: 20);

    if (analyses.isEmpty) {
      return Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          children: [
            Icon(Icons.analytics_outlined, size: 64, color: Colors.grey.shade300),
            const SizedBox(height: 16),
            Text(
              'No recent analyses',
              style: TextStyle(
                fontSize: 16,
                color: Colors.grey.shade600,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Search for a ticker to get started',
              style: TextStyle(
                fontSize: 14,
                color: Colors.grey.shade500,
              ),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: analyses.length,
      itemBuilder: (context, index) {
        final analysis = analyses[index];
        return _AnalysisTile(analysis: analysis);
      },
    );
  }
}

class _AnalysisTile extends StatelessWidget {
  final AnalysisModel analysis;

  const _AnalysisTile({required this.analysis});

  @override
  Widget build(BuildContext context) {
    final actionColor = _getActionColor(analysis.action);

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: InkWell(
        onTap: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => AnalysisScreen(ticker: analysis.ticker),
            ),
          );
        },
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              // Ticker and company
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          analysis.ticker,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 6,
                            vertical: 2,
                          ),
                          decoration: BoxDecoration(
                            color: actionColor.withOpacity(0.1),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            analysis.action,
                            style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w600,
                              color: actionColor,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 2),
                    Text(
                      analysis.sector,
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey.shade600,
                      ),
                    ),
                  ],
                ),
              ),

              // Scores
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Row(
                    children: [
                      _MiniScore(
                        label: 'T',
                        score: analysis.technicalScore,
                        color: AppTheme.technicalColor,
                      ),
                      const SizedBox(width: 6),
                      _MiniScore(
                        label: 'F',
                        score: analysis.fundamentalScore,
                        color: AppTheme.fundamentalColor,
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Conv: ${analysis.conviction.final_.toStringAsFixed(2)}',
                    style: TextStyle(
                      fontSize: 11,
                      color: Colors.grey.shade600,
                    ),
                  ),
                ],
              ),

              const SizedBox(width: 8),
              Icon(Icons.chevron_right, color: Colors.grey.shade400),
            ],
          ),
        ),
      ),
    );
  }

  Color _getActionColor(String action) {
    switch (action.toUpperCase()) {
      case 'BUY':
      case 'STRONG_BUY':
        return AppTheme.bullColor;
      case 'SELL':
      case 'STRONG_SELL':
      case 'AVOID':
        return AppTheme.bearColor;
      case 'HOLD':
        return AppTheme.ambiguousColor;
      default:
        return AppTheme.neutralColor;
    }
  }
}

class _MiniScore extends StatelessWidget {
  final String label;
  final double score;
  final Color color;

  const _MiniScore({
    required this.label,
    required this.score,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w600,
              color: color,
            ),
          ),
          const SizedBox(width: 3),
          Text(
            score.toInt().toString(),
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}
