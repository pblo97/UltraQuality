import 'package:dio/dio.dart';
import 'package:logger/logger.dart';

import '../constants/api_constants.dart';
import '../../features/analysis/data/models/analysis_model.dart';
import '../../features/regime/data/models/regime_model.dart';

class ApiClient {
  static final ApiClient _instance = ApiClient._internal();
  factory ApiClient() => _instance;

  late final Dio _dio;
  final _logger = Logger();

  ApiClient._internal() {
    _dio = Dio(BaseOptions(
      baseUrl: ApiConstants.baseUrl,
      connectTimeout: const Duration(seconds: 30),
      receiveTimeout: const Duration(seconds: 60),
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    ));

    // Add interceptors
    _dio.interceptors.add(LogInterceptor(
      requestBody: true,
      responseBody: true,
      logPrint: (obj) => _logger.d(obj),
    ));

    _dio.interceptors.add(InterceptorsWrapper(
      onError: (error, handler) {
        _logger.e('API Error: ${error.message}');
        handler.next(error);
      },
    ));
  }

  // ==================== ANALYSIS ====================

  /// Analyze a single ticker
  Future<AnalysisModel> analyzeTicker(String ticker) async {
    try {
      final response = await _dio.get('/api/v1/analyze/$ticker');
      return AnalysisModel.fromJson(response.data);
    } on DioException catch (e) {
      throw ApiException(
        message: e.response?.data['detail'] ?? 'Failed to analyze ticker',
        statusCode: e.response?.statusCode,
      );
    }
  }

  /// Analyze multiple tickers
  Future<List<AnalysisModel>> analyzeMultiple(List<String> tickers) async {
    try {
      final response = await _dio.post(
        '/api/v1/analyze/batch',
        data: {'tickers': tickers},
      );
      return (response.data as List)
          .map((json) => AnalysisModel.fromJson(json))
          .toList();
    } on DioException catch (e) {
      throw ApiException(
        message: e.response?.data['detail'] ?? 'Failed to analyze tickers',
        statusCode: e.response?.statusCode,
      );
    }
  }

  // ==================== REGIME ====================

  /// Get current market regime
  Future<RegimeSnapshot> getMarketRegime() async {
    try {
      final response = await _dio.get('/api/v1/regime');
      return RegimeSnapshot.fromJson(response.data);
    } on DioException catch (e) {
      throw ApiException(
        message: e.response?.data['detail'] ?? 'Failed to get market regime',
        statusCode: e.response?.statusCode,
      );
    }
  }

  // ==================== SCREENER ====================

  /// Run screener with filters
  Future<List<AnalysisModel>> runScreener({
    String? sector,
    double? minScore,
    double? minConviction,
    String? regime,
  }) async {
    try {
      final response = await _dio.get(
        '/api/v1/screener',
        queryParameters: {
          if (sector != null) 'sector': sector,
          if (minScore != null) 'min_score': minScore,
          if (minConviction != null) 'min_conviction': minConviction,
          if (regime != null) 'regime': regime,
        },
      );
      return (response.data['results'] as List)
          .map((json) => AnalysisModel.fromJson(json))
          .toList();
    } on DioException catch (e) {
      throw ApiException(
        message: e.response?.data['detail'] ?? 'Failed to run screener',
        statusCode: e.response?.statusCode,
      );
    }
  }

  // ==================== FUNDAMENTAL ====================

  /// Get fundamental data for a ticker
  Future<Map<String, dynamic>> getFundamentals(String ticker) async {
    try {
      final response = await _dio.get('/api/v1/fundamentals/$ticker');
      return response.data;
    } on DioException catch (e) {
      throw ApiException(
        message: e.response?.data['detail'] ?? 'Failed to get fundamentals',
        statusCode: e.response?.statusCode,
      );
    }
  }

  // ==================== POSITION SIZING ====================

  /// Calculate position size
  Future<Map<String, dynamic>> calculatePositionSize({
    required String ticker,
    required double portfolioValue,
    required double riskPerTrade,
  }) async {
    try {
      final response = await _dio.post(
        '/api/v1/position-size',
        data: {
          'ticker': ticker,
          'portfolio_value': portfolioValue,
          'risk_per_trade': riskPerTrade,
        },
      );
      return response.data;
    } on DioException catch (e) {
      throw ApiException(
        message: e.response?.data['detail'] ?? 'Failed to calculate position size',
        statusCode: e.response?.statusCode,
      );
    }
  }
}

class ApiException implements Exception {
  final String message;
  final int? statusCode;

  ApiException({required this.message, this.statusCode});

  @override
  String toString() => 'ApiException: $message (status: $statusCode)';
}
