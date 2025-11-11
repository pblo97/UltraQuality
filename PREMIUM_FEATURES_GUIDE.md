# Premium Features Troubleshooting Guide

## 🎯 Estado Actual

Las premium features **ESTÁN IMPLEMENTADAS Y CONFIGURADAS CORRECTAMENTE**.

✅ Verificado con `test_premium_features.py`:
- Cache TTL funcionando (4h, 24h, 12h)
- Premium config accesible
- Métodos implementados

## 📍 Dónde Están las Premium Features

### **IMPORTANTE:** Las features están NESTED (anidadas) en el output

```python
summary = analyzer.analyze_symbol('AAPL', 'non_financial', peers_df)

# ❌ NO están aquí:
summary['insider_trading']  # NO EXISTE
summary['earnings_sentiment']  # NO EXISTE

# ✅ Están aquí:
summary['intrinsic_value']['insider_trading']  # ✅ AQUÍ
summary['intrinsic_value']['earnings_sentiment']  # ✅ AQUÍ
```

## 🔍 Cómo Verificar que Funcionan

### Opción 1: Test Rápido (Ya hecho)
```bash
python test_premium_features.py
# Resultado: ✅ ALL TESTS PASSED
```

### Opción 2: Test con API Real
```bash
# Asegúrate de tener FMP_API_KEY configurada
export FMP_API_KEY='tu_clave_aqui'

# Ejecuta el test
python test_premium_real.py
```

Este script:
1. Llama a la API real de FMP
2. Ejecuta `_estimate_intrinsic_value()` sobre AAPL
3. Verifica si `insider_trading` y `earnings_sentiment` están en el resultado
4. Muestra el JSON completo de cada feature

### Opción 3: En Streamlit UI
```bash
python run_screener.py --config settings_premium.yaml
```

Luego:
1. Ve al tab **"Deep Dive"**
2. Selecciona un símbolo
3. Busca las secciones:
   - **Insider Trading Analysis**
   - **Earnings Call Sentiment**

**NOTA:** Las features NO aparecen en el screening inicial, solo en análisis cualitativo.

## 🐛 Troubleshooting

### "No veo nada habilitado"

#### Causa 1: Estás usando el config equivocado
```bash
# ❌ WRONG
python run_screener.py

# ✅ CORRECT
python run_screener.py --config settings_premium.yaml
```

#### Causa 2: Buscas en el lugar equivocado
Las features están en:
- `intrinsic_value.insider_trading` (NO en root)
- `intrinsic_value.earnings_sentiment` (NO en root)

#### Causa 3: Solo ejecutan en análisis cualitativo
- ❌ NO en screening inicial
- ✅ Solo en "Deep Dive" / qualitative analysis

#### Causa 4: Tu plan FMP no incluye premium features
Si el test real muestra:
```json
{
  "available": false,
  "note": "No insider trading data available"
}
```

Significa:
- El código SÍ ejecutó ✅
- La API respondió ✅
- Pero tu plan no tiene acceso a esos datos ⚠️

**Solución:** Actualiza tu plan FMP a Professional+ para:
- Insider Trading
- Earnings Call Transcripts

## 📊 Output Esperado

### Insider Trading (cuando funciona):
```json
{
  "available": true,
  "score": 85,
  "signal": "Strong Buy",
  "buy_count_12m": 12,
  "sell_count_12m": 2,
  "recent_buys_3m": 8,
  "executive_buys": 4,
  "net_position": "Buying"
}
```

### Earnings Sentiment (cuando funciona):
```json
{
  "available": true,
  "tone": "Very Positive",
  "grade": "A",
  "net_sentiment": 32.5,
  "positive_%": 55.2,
  "negative_%": 22.7,
  "has_guidance": true
}
```

## ✅ Siguiente Paso

**Ejecuta este comando para ver si la API real devuelve datos:**

```bash
export FMP_API_KEY='tu_clave'  # Si no está ya configurada
python test_premium_real.py
```

Esto te dirá:
1. ✅ Si las features se ejecutan (código correcto)
2. ✅ Si la API devuelve datos (plan correcto)
3. ✅ Dónde encontrar el output

## 📝 Commits Realizados

1. `fa042e6` - Enable Premium FMP features
2. `9f4fb3f` - Fix FMPClient config passing

Ambos commits ya están en la rama:
`claude/insider-earnings-sentiment-analysis-011CV2hLogkvpaYDpBDSVJJa`
