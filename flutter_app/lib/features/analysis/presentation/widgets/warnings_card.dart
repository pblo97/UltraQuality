import 'package:flutter/material.dart';

class WarningsCard extends StatelessWidget {
  final List<String> warnings;
  final List<String> vetoes;

  const WarningsCard({
    required this.warnings,
    required this.vetoes,
    super.key,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Alerts',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 12),

            // Vetoes (critical)
            ...vetoes.map((veto) => _AlertTile(
                  type: AlertType.veto,
                  message: veto,
                )),

            // Warnings
            ...warnings.map((warning) => _AlertTile(
                  type: AlertType.warning,
                  message: warning,
                )),
          ],
        ),
      ),
    );
  }
}

enum AlertType { veto, warning }

class _AlertTile extends StatelessWidget {
  final AlertType type;
  final String message;

  const _AlertTile({
    required this.type,
    required this.message,
  });

  @override
  Widget build(BuildContext context) {
    final isVeto = type == AlertType.veto;
    final bgColor = isVeto ? Colors.red.shade50 : Colors.amber.shade50;
    final borderColor = isVeto ? Colors.red.shade400 : Colors.amber.shade400;
    final textColor = isVeto ? Colors.red.shade900 : Colors.amber.shade900;
    final labelColor = isVeto ? Colors.red.shade800 : Colors.amber.shade800;

    // Determine label
    String label = isVeto ? 'VETO' : 'ENVIRONMENT';
    if (message.toLowerCase().contains('sector')) {
      label = 'SECTOR';
    } else if (message.toLowerCase().contains('breadth')) {
      label = 'BREADTH';
    } else if (message.toLowerCase().contains('drawdown')) {
      label = 'RISK';
    } else if (message.toLowerCase().contains('fatigue')) {
      label = 'FATIGUE';
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(6),
        border: Border(
          left: BorderSide(color: borderColor, width: 3),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w600,
              color: labelColor,
              letterSpacing: 0.5,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            message,
            style: TextStyle(
              fontSize: 13,
              color: textColor,
            ),
          ),
        ],
      ),
    );
  }
}
