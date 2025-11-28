# Technical Analysis Troubleshooting Guide

## ❌ Problema: Valores en 0, N/A o UNKNOWN

Si ves resultados como:
- Momentum 6M, 3M, 1M = 0%
- Sharpe Ratio = 0.00
- Volatility = 0.0%
- Market Regime = UNKNOWN
- Volume Profile = N/A
- Sector/Market Relative = +0.0%

**Esto indica que el análisis técnico está fallando silenciosamente.**

---

## 🔍 Diagnóstico: 3 Pasos

### Paso 1: Verificar API Key Configurada

El problema más común es que la API key no está configurada correctamente.

**Verificar**:
```bash
# Opción 1: Variable de entorno
echo $FMP_API_KEY

# Opción 2: Archivo .env
cat .env | grep FMP_API_KEY

# Opción 3: Streamlit secrets
cat .streamlit/secrets.toml | grep fmp_api_key
```

**Si ves**:
- `FMP_API_KEY=YOUR_FMP_API_KEY_HERE` → ❌ Placeholder, NO es válido
- `FMP_API_KEY=${FMP_API_KEY}` → ❌ Variable sin expandir, NO es válido
- `FMP_API_KEY=abc123def456...` → ✅ API key real

**Solución**:
```bash
# Editar .env
nano .env

# Reemplazar con tu API key real:
FMP_API_KEY=tu_api_key_de_financialmodelingprep

# O usar Streamlit secrets:
nano .streamlit/secrets.toml

# Agregar:
fmp_api_key = "tu_api_key_de_financialmodelingprep"
```

---

### Paso 2: Verificar Logs de Streamlit

Los logs ahora incluyen información detallada sobre qué está fallando.

**Ver logs**:
```bash
# Si ejecutas localmente:
streamlit run run_screener.py

# Buscar mensajes como:
# ERROR - {symbol}: hist_data is None or empty
# ERROR - {symbol}: hist_data dict but no 'historical' key
# WARNING - Insufficient data for momentum: X < 250
```

**En Streamlit Cloud**:
1. Ve a tu app en cloud.streamlit.app
2. Click en "Manage app" (esquina superior derecha)
3. Click en "Logs" para ver el terminal

---

### Paso 3: Revisar UI - Sección "Warnings & Diagnostics"

Después de seleccionar un stock en el tab Technical, ve a la sección **"⚠️ Warnings & Diagnostics"**.

Ahora debería mostrar:

**Si hay error**:
```
🔴 Analysis Error: No historical data available (null response)
💡 Common causes: API issues, insufficient historical data (<250 days),
   or missing API key configuration. Check Streamlit logs for details.
```

**Mensajes posibles**:
- `No quote data available` → API key incorrecta o símbolo inválido
- `No historical data available (null response)` → API no responde (rate limit o key inválida)
- `No historical data available (missing 'historical' key...)` → Formato de respuesta incorrecto
- `Insufficient data (X < 250)` → Stock muy nuevo, menos de 1 año de historia

---

## 🛠️ Soluciones por Tipo de Error

### Error: "401 Unauthorized"

**Causa**: API key inválida

**Solución**:
1. Verifica que tu API key sea correcta en https://financialmodelingprep.com/developer
2. Asegúrate de tener un plan activo (Free, Starter, Professional, etc.)
3. Reemplaza el placeholder en `.env` o `.streamlit/secrets.toml`
4. Reinicia la aplicación Streamlit

---

### Error: "No historical data available"

**Causa 1**: Rate limit excedido

Si tienes plan FREE:
- 250 requests/day
- 5 requests/minute

El análisis técnico mejorado hace **más requests** porque:
- 1 request: quote data
- 1 request: historical prices (símbolo)
- 1 request: historical prices (SPY)
- 1 request: historical prices (sector ETF)
- 1 request: VIX quote

**Total**: ~5 requests por stock analizado

**Solución**:
- Upgrade a plan Starter ($14/month) = 750 calls/min
- Limita cuántos stocks analizas a la vez
- Espera 24h para reset del límite FREE

**Causa 2**: Símbolo no existe o sin historia

**Solución**:
- Verifica que el símbolo sea válido en FMP
- Algunos stocks muy nuevos tienen <250 días de historia

---

### Error: "Insufficient data (X < 250)"

**Causa**: Stock tiene menos de 1 año de historia

**Explicación**: El análisis técnico mejorado necesita:
- 250 días trading (~12 meses) para momentum 12M
- 250 días para calcular Sharpe ratio anualizado
- 132 días (~6 meses) para sector/market relative strength

**Solución**:
- Usa stocks con al menos 1 año de trading history
- Los stocks de la lista BUY/MONITOR del screener fundamental generalmente tienen suficiente historia

---

### Error: "Historical data format error"

**Causa**: FMP cambió formato de respuesta

**Diagnóstico**: Revisa logs para ver qué devuelve `get_historical_prices`:
```python
# Esperado:
{
  'symbol': 'AAPL',
  'historical': [
    {'date': '2024-01-01', 'close': 150.0, 'volume': 100000, ...},
    {'date': '2024-01-02', 'close': 151.0, 'volume': 110000, ...},
    ...
  ]
}

# Si devuelve una lista en lugar de dict:
# ERROR - Historical data format error (got list instead of dict)
```

**Solución**: Report issue en GitHub con el output exacto de los logs

---

## ✅ Verificación de Funcionamiento

Una vez configurado correctamente, deberías ver:

**En la tabla principal (tab Technical)**:
- **Market Regime**: 🟢 BULL, 🔴 BEAR, o 🟡 SIDEWAYS (NO "UNKNOWN")
- **Momentum 6M**: Valores reales como +8.2%, -3.5% (NO 0%)
- **Sharpe 12M**: Valores reales como 1.23, 0.85 (NO 0.00)
- **Consistency**: HIGH, MEDIUM, LOW (NO "N/A")
- **Volume Profile**: ACCUMULATION, DISTRIBUTION, NEUTRAL (NO "N/A")

**En análisis detallado**:
- **Multi-Timeframe Momentum**: 4 valores diferentes (12M, 6M, 3M, 1M)
- **Risk Metrics**: Sharpe ratio > 0, Volatility > 0
- **Relative Strength**: Valores vs Sector y vs Market (SPY)
- **Warnings**: Si todo funciona, debería decir "✅ No technical warnings"

---

## 📊 Ejemplo de Análisis Correcto (MSFT)

```
🟢 Market Context: BULL (high confidence)

📊 Technical Components:
- Multi-TF Momentum: 15/25 (MEDIUM)
- Risk-Adjusted: 9/15 (Sharpe: 1.05)
- Sector Relative: 10/15 (GOOD)
- Market Relative: 6/10 (BEATING_MARKET)
- Volume Profile: 7/10 (ACCUMULATION)

Multi-Timeframe Momentum:
- 12M Return: +1.4%
- 6M Return: +8.2%
- 3M Return: +12.1%
- 1M Return: -2.3%
- Consistency: MEDIUM
- Status: POSITIVE

Risk Metrics:
- Sharpe Ratio (12M): 1.05
- Volatility (12M): 22.3%
- Risk Status: MODERATE

Relative Strength:
- vs Sector: +0.8%
- vs Market (SPY): +3.2%
- Sector Status: GOOD
- Market Status: BEATING_MARKET

Volume Analysis:
- Profile: ACCUMULATION
- Trend: INCREASING
- Accumulation Ratio: 0.58
```

**Si ves esto → ✅ Todo funciona correctamente**

---

## 🐛 Si Nada Funciona

1. **Borra el cache**:
```bash
rm -rf .cache .cache_test
```

2. **Prueba con un test simple**:
```bash
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')

from screener.ingest import FMPClient
import yaml

# Load API key
with open('settings.yaml') as f:
    config = yaml.safe_load(f)

import os
api_key = os.environ.get('FMP_API_KEY', '')
if not api_key:
    with open('.env') as f:
        for line in f:
            if 'FMP_API_KEY' in line:
                api_key = line.split('=')[1].strip()
                break

print(f"API Key: {api_key[:10]}...")

# Test
fmp = FMPClient(api_key, config['fmp'])
quote = fmp.get_quote('AAPL')
print(f"Quote test: {quote[0].get('price', 'ERROR')}")

hist = fmp.get_historical_prices('AAPL', from_date='2024-01-01')
print(f"Historical test: {len(hist.get('historical', []))} records")
EOF
```

3. **Verifica plan FMP**: https://financialmodelingprep.com/developer/docs/pricing
   - Free: 250 requests/day → Suficiente para 40-50 stocks
   - Starter: 750 requests/min → Ilimitado prácticamente

4. **Report issue**: https://github.com/yourusername/UltraQuality/issues
   - Incluye logs completos
   - Incluye output del test simple
   - Incluye plan FMP que tienes

---

## 📚 Recursos

- [FMP API Docs](https://site.financialmodelingprep.com/developer/docs)
- [Historical Price Endpoint](https://site.financialmodelingprep.com/developer/docs/stable/index-historical-price-eod-full)
- [FMP Pricing](https://financialmodelingprep.com/developer/docs/pricing)
- [Streamlit Secrets Management](https://docs.streamlit.io/streamlit-community-cloud/get-started/deploy-an-app/connect-to-data-sources/secrets-management)

---

**Última actualización**: 2024-11-28
**Versión**: v4.0 (Enhanced Technical Analysis)
