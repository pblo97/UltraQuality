import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/api/api_client.dart';
import '../../../../core/database/database.dart';
import '../../../../core/theme/app_theme.dart';
import '../../data/models/analysis_model.dart';
import '../widgets/score_card.dart';
import '../widgets/conviction_breakdown_card.dart';
import '../widgets/regime_info_card.dart';
import '../widgets/position_sizing_card.dart';
import '../widgets/recommendation_card.dart';
import '../widgets/warnings_card.dart';

class AnalysisScreen extends ConsumerStatefulWidget {
  final String ticker;

  const AnalysisScreen({required this.ticker, super.key});

  @override
  ConsumerState<AnalysisScreen> createState() => _AnalysisScreenState();
}

class _AnalysisScreenState extends ConsumerState<AnalysisScreen> {
  late Future<AnalysisModel> _analysisFuture;
  bool _isLoading = true;
  String? _error;
  AnalysisModel? _analysis;

  @override
  void initState() {
    super.initState();
    _loadAnalysis();
  }

  Future<void> _loadAnalysis() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final analysis = await ApiClient().analyzeTicker(widget.ticker);

      // Save to local database
      await LocalDatabase.saveAnalysis(analysis);

      setState(() {
        _analysis = analysis;
        _isLoading = false;
      });
    } catch (e) {
      // Try to load from cache
      final cached = LocalDatabase.getLatestAnalysis(widget.ticker);
      if (cached != null) {
        setState(() {
          _analysis = cached;
          _isLoading = false;
          _error = 'Using cached data (${_formatDate(cached.analyzedAt)})';
        });
      } else {
        setState(() {
          _isLoading = false;
          _error = e.toString();
        });
      }
    }
  }

  String _formatDate(DateTime date) {
    return '${date.month}/${date.day} ${date.hour}:${date.minute.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.ticker),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadAnalysis,
          ),
          IconButton(
            icon: const Icon(Icons.star_outline),
            onPressed: () {
              // Add to watchlist
            },
          ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('Analyzing...'),
          ],
        ),
      );
    }

    if (_analysis == null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 64, color: Colors.grey.shade400),
            const SizedBox(height: 16),
            Text(_error ?? 'Failed to load analysis'),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _loadAnalysis,
              child: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    final data = _analysis!;

    return RefreshIndicator(
      onRefresh: _loadAnalysis,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header with company info
            _buildHeader(data),
            const SizedBox(height: 16),

            // Error banner if using cached data
            if (_error != null) _buildCacheBanner(),

            // Recommendation Card
            RecommendationCard(analysis: data),
            const SizedBox(height: 16),

            // Score Cards Row
            Row(
              children: [
                Expanded(
                  child: ScoreCard(
                    title: 'Technical',
                    score: data.technicalScore,
                    color: AppTheme.technicalColor,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ScoreCard(
                    title: 'Fundamental',
                    score: data.fundamentalScore,
                    color: AppTheme.fundamentalColor,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Regime Info
            RegimeInfoCard(analysis: data),
            const SizedBox(height: 16),

            // Conviction Breakdown
            ConvictionBreakdownCard(
              conviction: data.conviction,
              warnings: data.warnings,
            ),
            const SizedBox(height: 16),

            // Warnings if any
            if (data.hasWarnings || data.hasVetoes)
              WarningsCard(
                warnings: data.warnings,
                vetoes: data.vetoes,
              ),
            if (data.hasWarnings || data.hasVetoes) const SizedBox(height: 16),

            // Position Sizing
            PositionSizingCard(analysis: data),
            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader(AnalysisModel data) {
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                data.companyName,
                style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                data.sector,
                style: TextStyle(
                  fontSize: 14,
                  color: Colors.grey.shade600,
                ),
              ),
            ],
          ),
        ),
        Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(
              '\$${data.currentPrice.toStringAsFixed(2)}',
              style: const TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
              ),
            ),
            Text(
              'ATR: ${data.atr.toStringAsFixed(2)}%',
              style: TextStyle(
                fontSize: 12,
                color: Colors.grey.shade600,
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildCacheBanner() {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.amber.shade50,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.amber.shade200),
      ),
      child: Row(
        children: [
          Icon(Icons.info_outline, size: 20, color: Colors.amber.shade700),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              _error!,
              style: TextStyle(color: Colors.amber.shade900, fontSize: 13),
            ),
          ),
        ],
      ),
    );
  }
}
