# 🔍 Cómo Diagnosticar "No Aparece Nada Habilitado"

## El Problema Más Común: Ubicación Incorrecta ⚠️

Las premium features **NO están en el nivel raíz** del resultado. Están **ANIDADAS dentro de `intrinsic_value`**.

### ❌ Ubicación Incorrecta (donde probablemente estás mirando):
```python
summary['insider_trading']      # NO EXISTE (o es deprecated)
summary['earnings_sentiment']   # NO EXISTE
```

### ✅ Ubicación Correcta (donde REALMENTE están):
```python
summary['intrinsic_value']['insider_trading']      # ✅ AQUÍ
summary['intrinsic_value']['earnings_sentiment']   # ✅ AQUÍ
```

---

## 🧪 Pasos de Diagnóstico

### PASO 1: Verifica la estructura del output
```bash
python check_where_to_look.py
```
Este script te muestra EXACTAMENTE dónde buscar.

---

### PASO 2: Ejecuta el test completo con tu API key
```bash
# Configura tu API key
export FMP_API_KEY='tu_clave_aqui'

# Ejecuta el test de flujo completo
python test_premium_flow.py
```

**Qué buscar en el output:**

✅ **Si ves esto = FUNCIONA:**
```
🔍 Premium config for AAPL: {'enable_insider_trading': True, ...}
✓ Insider Trading is ENABLED, calling _analyze_insider_trading(AAPL)...
✓ Insider Trading result: available=True
✓ Insider Trading added to valuation dict
```

❌ **Si ves esto = PROBLEMA DE CONFIG:**
```
❌ Insider Trading is DISABLED in config
```
→ Solución: Verifica que usas `--config settings_premium.yaml`

⚠️ **Si ves esto = PROBLEMA DE PLAN FMP:**
```
✓ Insider Trading result: available=False
```
→ Solución: Tu plan FMP no incluye insider trading (necesitas Professional+)

---

### PASO 3: Si ejecutas el screener, verifica DÓNDE miras

#### En Python/Scripts:
```python
# Ejecuta análisis cualitativo
summary = analyzer.analyze_symbol('AAPL', 'non_financial', peers_df)

# VERIFICA la estructura
print("Keys en raíz:", list(summary.keys()))
print("Keys en intrinsic_value:", list(summary.get('intrinsic_value', {}).keys()))

# Busca las features en el lugar CORRECTO
iv = summary.get('intrinsic_value', {})
print("Tiene insider_trading:", 'insider_trading' in iv)
print("Tiene earnings_sentiment:", 'earnings_sentiment' in iv)

# ACCEDE correctamente
if 'insider_trading' in iv:
    print("Insider Trading:", iv['insider_trading'])
if 'earnings_sentiment' in iv:
    print("Earnings Sentiment:", iv['earnings_sentiment'])
```

#### En Streamlit UI:
1. Ejecuta: `python run_screener.py --config settings_premium.yaml`
2. Ve al tab **"Deep Dive"** (NO "Screening")
3. Selecciona un símbolo
4. Busca las secciones:
   - **"Insider Trading Analysis"**
   - **"Earnings Call Sentiment"**

**NOTA:** Las features **NO** aparecen en el screening inicial, solo en análisis cualitativo.

---

## 🎯 Checklist Completo

Marca cada item:

- [ ] Usas `--config settings_premium.yaml` (no settings.yaml)
- [ ] Ejecutas análisis cualitativo (no solo screening)
- [ ] Buscas en `intrinsic_value` (no en root)
- [ ] Tienes FMP_API_KEY configurada
- [ ] Tu plan FMP incluye premium features (Professional+)

---

## 📊 Cómo Saber Si Funciona

### Test 1: Configuración ✅
```bash
python test_premium_features.py
# Debe mostrar: ✅ ALL TESTS PASSED
```

### Test 2: Ejecución Real ✅
```bash
export FMP_API_KEY='tu_clave'
python test_premium_flow.py
# Debe mostrar logs con 🔍 ✓ y features en resultado
```

### Test 3: Output Correcto ✅
```bash
# Al ejecutar análisis cualitativo:
summary['intrinsic_value']['insider_trading']['available'] == True
summary['intrinsic_value']['earnings_sentiment']['available'] == True
```

---

## 🐛 Debugging Adicional

### Ver logs del screener:
```bash
# Ejecuta con logging detallado
python run_screener.py --config settings_premium.yaml --qualitative AAPL > debug.log 2>&1

# Busca las líneas de debug
grep "🔍\|✓\|❌" debug.log
```

### Dump completo del output:
```python
import json

# Después de ejecutar análisis
with open('debug_output.json', 'w') as f:
    json.dump(summary, f, indent=2, default=str)

# Abre debug_output.json y busca "insider_trading" y "earnings_sentiment"
# Verás DÓNDE están exactamente en la estructura
```

---

## 📝 Si NADA de Esto Funciona

Comparte el output de:
```bash
# 1. Test de config
python test_premium_features.py > test1.log 2>&1

# 2. Test de flujo (con tu API key)
export FMP_API_KEY='tu_clave'
python test_premium_flow.py > test2.log 2>&1

# 3. Config actual
cat settings_premium.yaml | grep -A5 "premium:"
```

Esto mostrará EXACTAMENTE dónde está el problema.

---

## ✅ Resumen

**El problema más común (90% de casos):**
- Estás mirando en `summary['insider_trading']` (root level) ❌
- Debes mirar en `summary['intrinsic_value']['insider_trading']` ✅

**Otros problemas comunes:**
- No usas `--config settings_premium.yaml`
- Solo ves screening, no análisis cualitativo
- Tu plan FMP no incluye premium features

**Para verificar:**
```bash
python test_premium_flow.py
```
Este script te dirá EXACTAMENTE qué está pasando.
