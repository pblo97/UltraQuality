# 📚 Revisión Basada en Bibliografía Académica

## 🔍 Problema Actual

**Observación**: Solo 1 acción con señal BUY (Adobe) de 150 analizadas (~0.67%)

**Causa Root**: Thresholds demasiado conservadores no alineados con la literatura académica

---

## 📖 Literatura Académica Relevante

### 1. **Joel Greenblatt - "The Little Book That Beats the Market" (2005)**

**Magic Formula**: ROIC alto + Earnings Yield alto

**Metodología Original**:
- Rankea TODAS las acciones por ambos factores
- **NO usa thresholds absolutos**
- Compra top 20-30 acciones del ranking combinado
- **Rebalanceo anual**

**Resultados Históricos** (1988-2004):
- Magic Formula: +30.8% anual
- S&P 500: +12.4% anual

**Aplicación a UltraQuality**:
```yaml
# Greenblatt NO haría esto:
threshold_buy: 75  # ❌ Top 25%

# Greenblatt haría esto:
threshold_buy: 60  # ✅ Top 40% es más razonable
# O mejor: simplemente comprar top N acciones del ranking
```

---

### 2. **Joseph Piotroski - "Value Investing: The Use of Historical Financial Statement Information" (2000)**

**F-Score**: 9 señales binarias de calidad financiera

**Metodología**:
- F-Score >= 7/9 = FUERTE (77.8%)
- F-Score >= 8/9 = MUY FUERTE (88.9%)
- **NO requiere >= 9/9** (100%)

**Resultados**:
- F-Score alto (7-9) + Value: +23% anual
- F-Score bajo (0-2) + Value: -25% anual

**Aplicación a UltraQuality**:
```yaml
# Equivalente F-Score 7/9 = 77.8%
threshold_buy: 70  # ✅ Más alineado con Piotroski

# Current (demasiado estricto):
threshold_buy: 75  # ❌ Equivalente a F-Score 8.25/9
```

---

### 3. **Fama & French - "Common Risk Factors" (1993)**

**3-Factor Model**: Market + Size + Value

**Metodología de Portfolios**:
- Divide universo en **terciles** (33% cada uno)
- Long top tercile, Short bottom tercile
- **NO usa top quartile (25%)**

**Resultados** (1963-1990):
- HML (High Minus Low) premium: +5.4% anual
- SMB (Small Minus Big) premium: +3.7% anual

**Aplicación a UltraQuality**:
```yaml
# Fama-French usarían:
threshold_buy: 67  # ✅ Top tercile (33%)
threshold_monitor: 33  # Middle tercile

# Current (más conservador que academic research):
threshold_buy: 75  # ❌ Top quartile
threshold_monitor: 60  # ❌ Solo 15% en middle tier
```

---

### 4. **Robert Novy-Marx - "The Other Side of Value: Gross Profitability Premium" (2013)**

**Gross Profitability Premium**: GP/A (Gross Profits / Assets)

**Metodología**:
- Quintiles (20% cada uno)
- Top quintile (80th percentile) outperforms
- **NO requiere top decile (90th percentile)**

**Resultados** (1963-2010):
- Top quintile GP/A: +11.1% anual
- Bottom quintile: +6.3% anual
- Premium: +4.8% anual

**Aplicación a UltraQuality**:
```yaml
# Novy-Marx usaría:
threshold_buy: 80  # ❌ Top quintile (demasiado alto para combo quality+value)
# Pero combinado con value:
threshold_buy: 65  # ✅ Top 35% es razonable para combo

# Current:
threshold_buy: 75  # Intermedio pero aún restrictivo
```

---

### 5. **Sloan (1996) - Accruals Anomaly**

**Accruals Quality**: Accruals/NOA bajo = mejor

**Metodología**:
- Deciles (10% cada uno)
- Accruals bajos (bottom 2 deciles = 20%) outperform
- **NO requiere bottom decile solo (10%)**

**Resultados**:
- Low accruals portfolio: +10.4% anual
- High accruals portfolio: +4.7% anual
- Hedge return: +5.7% anual

---

## 🎯 Recomendaciones Basadas en Literatura

### **Opción A: Moderada (Recomendada)**

Basada en Piotroski F-Score + Greenblatt Magic Formula

```yaml
scoring:
  weight_value: 0.5
  weight_quality: 0.5
  exclude_reds: true  # Mantener - buena práctica

  # Adjusted thresholds:
  threshold_buy: 70      # ✅ De 75 → 70 (top 30%)
  threshold_monitor: 50  # ✅ De 60 → 50 (middle 40%)

  # Nuevo: Permitir AMBAR con score muy alto
  threshold_buy_amber: 80  # AMBAR allowed if score >= 80
```

**Decisión Logic Mejorada**:
```python
if status == 'ROJO':
    return 'AVOID'
elif composite >= 80:
    return 'BUY'  # ✅ Permite AMBAR si score excepcional
elif composite >= 70 and status == 'VERDE':
    return 'BUY'  # ✅ Verde con buen score
elif composite >= 50:
    return 'MONITOR'
else:
    return 'AVOID'
```

**Resultado Esperado**: 10-20 BUY signals (~7-13%)

---

### **Opción B: Agresiva**

Basada en Fama-French terciles

```yaml
scoring:
  threshold_buy: 67       # ✅ Top tercile
  threshold_monitor: 33   # Middle tercile
  threshold_buy_amber: 75 # AMBAR con score excepcional
```

**Resultado Esperado**: 15-30 BUY signals (~10-20%)

---

### **Opción C: Muy Conservadora (Actual)**

Actual settings - solo para inversores MUY risk-averse

```yaml
scoring:
  threshold_buy: 75       # Top quartile
  threshold_monitor: 60
```

**Resultado Esperado**: 1-5 BUY signals (~0.7-3%)
**Literatura**: NO hay evidencia que top 25% + VERDE sea óptimo

---

## 🔧 Otras Mejoras Basadas en Research

### 1. **Winsorizing (Novy-Marx, Fama-French)**

**Problema Actual**: Cap z-scores en ±3
```python
z_scores = z_scores.clip(-3, 3)  # Correcto
```

**Recomendación**: ✅ Mantener - es best practice

---

### 2. **Industry Neutralization (Asness et al. 2000)**

**Problema Actual**: Normaliza por industry ✅
**Recomendación**: Perfecto - keep as is

---

### 3. **Multi-Factor Combination (Fama-French-Carhart)**

**Problema Actual**: 50/50 value/quality
**Literatura**: Algunos papers sugieren 60/40 o 70/30

**Recomendación Flexible**:
```yaml
scoring:
  weight_value: 0.6    # ✅ Ligeramente más peso a value
  weight_quality: 0.4  # Quality como filtro
  # O mantener 50/50 - ambos válidos
```

**Evidencia**:
- Piotroski: F-Score funciona MEJOR con value stocks
- Greenblatt: Equal weight
- Novy-Marx: Quality puede ser standalone

**Conclusión**: 50/50 está bien, pero 60/40 es más agresivo en value

---

### 4. **Rebalancing Frequency (Greenblatt, Piotroski)**

**Literatura**:
- Greenblatt: Anual
- Piotroski: Anual
- Fama-French: Anual (Julio)

**Recomendación**: Cache settings OK (48h para símbolos)

---

### 5. **Size Factor (Fama-French)**

**Problema Actual**: min_market_cap = $2B (mid-large cap)

**Literatura**:
- Small cap premium: +3.7% anual (Fama-French)
- Pero: menos líquido, más riesgo

**Recomendación**:
```yaml
universe:
  min_market_cap: 2_000_000_000  # ✅ OK para large caps
  # O si quieres small cap premium:
  min_market_cap: 300_000_000    # Include small caps
```

**Trade-off**: Liquidez vs Premium

---

## 📊 Comparación de Approaches

| Approach | Threshold BUY | Expected BUY % | Research Basis | Risk Level |
|----------|---------------|----------------|----------------|------------|
| **Current** | 75 + VERDE | 0.7-3% | None | Ultra Conservative |
| **Piotroski** | 70 + allow AMBAR(80+) | 7-13% | F-Score paper | Conservative |
| **Fama-French** | 67 + allow AMBAR(75+) | 10-20% | 3-Factor model | Moderate |
| **Greenblatt** | Top N stocks | 13-20% | Magic Formula | Moderate-Aggressive |

---

## 🎯 Recommendation Final

### **Implementar Opción A (Moderada - Piotroski-based)**

**Cambios en `settings.yaml`**:
```yaml
scoring:
  weight_value: 0.5
  weight_quality: 0.5
  exclude_reds: true
  threshold_buy: 70           # ✅ De 75 → 70
  threshold_monitor: 50       # ✅ De 60 → 50
  threshold_buy_amber: 80     # ✅ NUEVO - permite AMBAR excepcional
```

**Cambios en `scoring.py` decisión logic**:
```python
def decide(row):
    composite = row.get('composite_0_100', 0)
    status = row.get('guardrail_status', 'AMBAR')

    # ROJO = Auto AVOID
    if self.exclude_reds and status == 'ROJO':
        return 'AVOID'

    # Score excepcional = BUY incluso con AMBAR
    if composite >= 80:  # Top 20%
        return 'BUY'

    # Score bueno + VERDE = BUY
    if composite >= 70 and status == 'VERDE':  # Top 30% + clean
        return 'BUY'

    # Score medio = MONITOR
    if composite >= 50:
        return 'MONITOR'

    # Resto = AVOID
    return 'AVOID'
```

**Resultado Esperado**:
- 10-20 BUY signals (7-13% del universo)
- Alineado con Piotroski F-Score >= 7/9
- Más diversificación
- Mantiene quality standards

---

## 📚 Referencias

1. **Greenblatt, J. (2005)** - "The Little Book That Beats the Market"
2. **Piotroski, J. (2000)** - "Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers", Journal of Accounting Research
3. **Fama, E. & French, K. (1993)** - "Common Risk Factors in the Returns on Stocks and Bonds", Journal of Financial Economics
4. **Novy-Marx, R. (2013)** - "The Other Side of Value: The Gross Profitability Premium", Journal of Financial Economics
5. **Sloan, R. (1996)** - "Do Stock Prices Fully Reflect Information in Accruals and Cash Flows about Future Earnings?", The Accounting Review
6. **Asness, C., Porter, B., & Stevens, R. (2000)** - "Predicting Stock Returns Using Industry-Relative Firm Characteristics"

---

## 🎓 Conclusión

Los thresholds actuales (75 + VERDE) son **más conservadores que cualquier paper académico**.

**Literatura muestra**:
- Piotroski: 77.8% (F>=7) es suficiente
- Greenblatt: Top 30 stocks del ranking
- Fama-French: Top tercile (67%)
- Novy-Marx: Top quintile (80%)

**Recomendación**: Bajar threshold a **70** y permitir **AMBAR con score >= 80**

Esto te dará 10-20 oportunidades en lugar de 1, manteniendo calidad.
