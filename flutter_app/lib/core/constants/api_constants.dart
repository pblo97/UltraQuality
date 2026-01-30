class ApiConstants {
  // Base URL - change for production
  static const String baseUrl = 'http://localhost:8000';

  // Endpoints
  static const String analyze = '/api/v1/analyze';
  static const String regime = '/api/v1/regime';
  static const String screener = '/api/v1/screener';
  static const String fundamentals = '/api/v1/fundamentals';
  static const String positionSize = '/api/v1/position-size';

  // Timeouts
  static const Duration connectTimeout = Duration(seconds: 30);
  static const Duration receiveTimeout = Duration(seconds: 60);
}
