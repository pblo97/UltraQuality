import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/api/api_client.dart';
import '../../data/models/regime_model.dart';

class RegimeCard extends ConsumerStatefulWidget {
  const RegimeCard({super.key});

  @override
  ConsumerState<RegimeCard> createState() => _RegimeCardState();
}

class _RegimeCardState extends ConsumerState<RegimeCard> {
  RegimeSnapshot? _regime;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadRegime();
  }

  Future<void> _loadRegime() async {
    try {
      final regime = await ApiClient().getMarketRegime();
      setState(() {
        _regime = regime;
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return _buildLoadingCard();
    }

    if (_regime == null) {
      return _buildErrorCard();
    }

    return _buildRegimeCard(_regime!);
  }

  Widget _buildLoadingCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Row(
          children: [
            const SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
            const SizedBox(width: 16),
            Text(
              'Loading market regime...',
              style: TextStyle(color: Colors.grey.shade600),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Row(
          children: [
            Icon(Icons.cloud_off, color: Colors.grey.shade400),
            const SizedBox(width: 16),
            const Text('Unable to load regime'),
            const Spacer(),
            TextButton(
              onPressed: _loadRegime,
              child: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRegimeCard(RegimeSnapshot regime) {
    final regimeColor = _getRegimeColor(regime.globalRegime);

    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          // Header with regime
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [regimeColor, regimeColor.withOpacity(0.8)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
            ),
            child: Row(
              children: [
                Icon(
                  _getRegimeIcon(regime.globalRegime),
                  color: Colors.white,
                  size: 28,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'MARKET REGIME',
                        style: TextStyle(
                          color: Colors.white70,
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          letterSpacing: 1,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        regime.globalRegime.replaceAll('_', ' '),
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ),
                if (regime.killSwitchActive)
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 4,
                    ),
                    decoration: BoxDecoration(
                      color: Colors.red.shade900,
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: const Text(
                      'KILL SWITCH',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
              ],
            ),
          ),

          // Metrics
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Expanded(
                  child: _MetricTile(
                    label: 'ALIGNMENT',
                    value: regime.alignmentDisplay,
                    subtitle: 'Cross-market',
                  ),
                ),
                Container(
                  width: 1,
                  height: 40,
                  color: Colors.grey.shade200,
                ),
                Expanded(
                  child: _MetricTile(
                    label: 'BREADTH',
                    value: regime.breadthDisplay,
                    subtitle: regime.breadthState,
                  ),
                ),
                Container(
                  width: 1,
                  height: 40,
                  color: Colors.grey.shade200,
                ),
                Expanded(
                  child: _MetricTile(
                    label: 'ENVIRONMENT',
                    value: regime.environmentMultiplier.toStringAsFixed(2),
                    subtitle: 'Multiplier',
                  ),
                ),
              ],
            ),
          ),

          // Warnings if any
          if (regime.activeWarnings.isNotEmpty)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              color: Colors.amber.shade50,
              child: Row(
                children: [
                  Icon(
                    Icons.info_outline,
                    size: 16,
                    color: Colors.amber.shade700,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      regime.activeWarnings.first,
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.amber.shade900,
                      ),
                    ),
                  ),
                ],
              ),
            ),
        ],
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

  IconData _getRegimeIcon(String regime) {
    final upper = regime.toUpperCase();
    if (upper.contains('BULL')) return Icons.trending_up;
    if (upper.contains('BEAR')) return Icons.trending_down;
    return Icons.trending_flat;
  }
}

class _MetricTile extends StatelessWidget {
  final String label;
  final String value;
  final String subtitle;

  const _MetricTile({
    required this.label,
    required this.value,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
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
          style: const TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.bold,
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
    );
  }
}
