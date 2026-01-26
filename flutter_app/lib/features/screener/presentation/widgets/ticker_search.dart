import 'package:flutter/material.dart';

class TickerSearch extends StatefulWidget {
  final Function(String) onTickerSelected;

  const TickerSearch({required this.onTickerSelected, super.key});

  @override
  State<TickerSearch> createState() => _TickerSearchState();
}

class _TickerSearchState extends State<TickerSearch> {
  final _controller = TextEditingController();
  final _focusNode = FocusNode();

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _submit() {
    final ticker = _controller.text.trim().toUpperCase();
    if (ticker.isNotEmpty) {
      widget.onTickerSelected(ticker);
      _controller.clear();
      _focusNode.unfocus();
    }
  }

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: _controller,
      focusNode: _focusNode,
      textCapitalization: TextCapitalization.characters,
      decoration: InputDecoration(
        hintText: 'Enter ticker symbol (e.g., AAPL)',
        prefixIcon: const Icon(Icons.search),
        suffixIcon: IconButton(
          icon: const Icon(Icons.arrow_forward),
          onPressed: _submit,
        ),
      ),
      onSubmitted: (_) => _submit(),
    );
  }
}
