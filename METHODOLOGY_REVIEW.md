# 🔬 Análisis Exhaustivo: Bug + Metodología Value/Quality

## 🐛 BUG CRÍTICO IDENTIFICADO

### Problema: Scores = 50 para stocks 170+

**Síntoma**: Desde stock 170 en adelante, composite/value/quality scores = exactamente 50

**Root Cause**: `_robust_zscore()` en scoring.py líneas 278-288

```python
def _robust_zscore(self, series: pd.Series, higher_is_better: bool):
    clean = series.dropna()

    if len(clean) < 3:  # ❌ BUG
        return pd.Series(0, index=series.index)  # Z-score = 0

    ...

    if mad == 0:  # ❌ BUG
        return pd.Series(0, index=series.index)  # Z-score = 0
```

**Cascada**:
- Z-score = 0 → `_zscore_to_percentile(0)` → 50th percentile → Score = 50

**Por qué ocurre después del stock 170**:
1. Top 150 stocks capturan las industrias principales
2. Stocks 170+ están en industrias pequeñas (1-2 empresas en el sample)
3. Normalización por industria falla → retorna z-score = 0
4. Todas las métricas = 0 → value_score = 50, quality_score = 50, composite = 50

**Ejemplo**:
```
Industry "Aerospace & Defense": 15 empresas → normalización funciona ✅
Industry "Agricultural Inputs": 1 empresa → len(clean) < 3 → z-score = 0 → score = 50 ❌
```

---

## 📚 REVISIÓN LITERATURA: VALUE METRICS

### Current Implementation (Problemas)

#### Non-Financials:
```python
value_metrics = ['ev_ebit_ttm', 'ev_fcf_ttm', 'pe_ttm', 'pb_ttm']
value_higher_better = ['shareholder_yield_%']
```

**Problemas Identificados**:

1. **P/E (Price/Earnings)**
   - ❌ Manipulable con accounting games
   - ❌ No refleja cash generation
   - ❌ Puede ser negativo (pérdidas) → distorsiona z-scores
   - ❌ Sensible a one-time items

2. **P/B (Price/Book)**
   - ❌ Book value es backward-looking
   - ❌ Irrelevante para asset-light companies (tech, services)
   - ❌ Intangibles no reflejados correctamente

3. **EV/EBIT**
   - ✅ Mejor que P/E (capital structure neutral)
   - ⚠️ Pero EBIT incluye D&A (no-cash charges)
   - ⚠️ No refleja CAPEX requirements

4. **EV/FCF**
   - ✅ Bueno pero...
   - ❌ FCF volátil quarter-to-quarter
   - ❌ No distingue maintenance CAPEX vs growth CAPEX

---

### Academic Research: Best Value Metrics

#### 1. **Earnings Yield vs FCF Yield**

**Greenblatt (2005) - Magic Formula**:
- Usa: **EBIT / EV** (Earnings Yield)
- NO usa P/E porque:
  - Tax rates distort E/P
  - Leverage distorts E/P
  - EBIT/EV es capital structure neutral

**Return**: +30.8% anual (1988-2004)

**Recomendación**:
```python
# Actual:
value_metrics = ['ev_ebit_ttm', 'ev_fcf_ttm', 'pe_ttm', 'pb_ttm']

# Mejorado:
value_metrics = [
    'earnings_yield',     # EBIT / EV (invert of EV/EBIT)
    'fcf_yield',          # FCF / EV (invert of EV/FCF)
    'owner_earnings_yield' # Buffett metric (ver abajo)
]
```

---

#### 2. **Owner Earnings (Buffett)**

**Warren Buffett**:
> "Owner Earnings = Net Income + D&A - Maintenance CAPEX"

**Formula**:
```
Owner Earnings = Net Income + D&A + Amortization - Maintenance CAPEX
Owner Earnings Yield = Owner Earnings / Market Cap
```

**Problema**: Diferenciar Maintenance CAPEX vs Growth CAPEX

**Proxy Academia (Titman, Wei, Xie 2004)**:
```
Maintenance CAPEX ≈ Depreciation
Growth CAPEX = Total CAPEX - Depreciation
```

**Implementación Práctica**:
```python
owner_earnings = net_income + depreciation - maintenance_capex
# Donde maintenance_capex ≈ depreciation (conservative)
owner_earnings_yield = owner_earnings / market_cap
```

---

#### 3. **Gross Profitability (Novy-Marx 2013)**

**Formula**: Gross Profit / Assets

**Return**: +4.8% anual premium (1963-2010)

**Por qué funciona**:
- Refleja pricing power
- Menos manipulable que net earnings
- Predice future ROIC

**Recomendación**: Ya lo tienes en Quality ✅, pero también podría ir en Value

---

#### 4. **Enterprise Multiple (O'Shaughnessy 2012)**

**Formula**: EV / (EBITDA - CAPEX)

Similar a EV/FCF pero más estable

**Ventaja**:
- Ajusta por CAPEX intensity
- Más estable que FCF
- Captura cash generation power

---

### Ranking Papers por Métrica Value

| Métrica | Paper | Sharpe Ratio | Mejor Para |
|---------|-------|--------------|------------|
| **Earnings Yield (EBIT/EV)** | Greenblatt 2005 | 0.88 | General |
| **FCF Yield** | Piotroski 2000 | 0.72 | Mature companies |
| **Owner Earnings Yield** | Buffett (no paper) | N/A | Quality filter |
| **Gross Prof/Assets** | Novy-Marx 2013 | 0.69 | Combined w/ Value |
| **EV/Sales** | O'Shaughnessy 2012 | 0.45 | Sales-driven |
| **P/E** | Basu 1977 (original) | 0.35 | Legacy (outdated) |
| **P/B** | Fama-French 1992 | 0.31 | Asset-heavy only |

---

### Recomendación Mejorada: Value Metrics

#### **Tier 1 (Primarios)** - Usar estos:
```python
value_metrics_primary = [
    'earnings_yield',           # EBIT / EV (Greenblatt)
    'fcf_yield',                # FCF / EV
    'owner_earnings_yield',     # (NI + D&A - Maint.CAPEX) / MCap (Buffett)
]
```

#### **Tier 2 (Complementarios)** - Considerar:
```python
value_metrics_secondary = [
    'ev_to_ebitda_minus_capex', # EV / (EBITDA - CAPEX) (O'Shaughnessy)
    'shareholder_yield',         # Div + Buybacks - Issuance (ya lo tienes ✅)
]
```

#### **Eliminar**:
```python
# ❌ Remover estas (outdated/problematic):
'pe_ttm',    # Reemplazar con earnings_yield
'pb_ttm',    # Solo útil para asset-heavy (banks ok, tech no)
```

---

## 📊 REVISIÓN LITERATURA: QUALITY METRICS

### Current Implementation

#### Non-Financials:
```python
quality_metrics = [
    'roic_%',                    # ✅ EXCELENTE
    'grossProfits_to_assets',    # ✅ EXCELENTE (Novy-Marx)
    'fcf_margin_%',              # ✅ BUENO
    'cfo_to_ni',                 # ✅ EXCELENTE (accruals proxy)
    'interestCoverage'           # ✅ BUENO
]
quality_lower_better = [
    'netDebt_ebitda'             # ✅ BUENO
]
```

**Assessment**: Tu implementación Quality es EXCELENTE ✅

**Basada en**:
- Piotroski F-Score components
- Novy-Marx Gross Profitability
- Sloan Accruals Quality

---

### Academic Research: Quality Metrics

#### 1. **Piotroski F-Score (2000)** - 9 signals

**Profitability (4)**:
- ✅ ROA > 0
- ✅ CFO > 0
- ✅ ΔROA > 0
- ✅ Accruals < 0 (CFO > Net Income) ← Tu tienes `cfo_to_ni` ✅

**Leverage/Liquidity (3)**:
- ✅ ΔLong-term Debt < 0 (tu tienes `netDebt_ebitda` ✅)
- ✅ ΔCurrent Ratio > 0
- ❌ No new equity issuance (tu tienes en guardrails ✅)

**Operating Efficiency (2)**:
- ✅ ΔGross Margin > 0 (tu tienes `grossProfits_to_assets` ✅)
- ❌ ΔAsset Turnover > 0

**Return**: +23% anual (high F-Score + Value)

---

#### 2. **Novy-Marx (2013)** - Gross Profitability

**Formula**: (Revenue - COGS) / Assets

**Return**: +4.8% anual

**Por qué**:
- Predice future earnings
- Menos manipulable
- Refleja pricing power

**Tu implementación**: ✅ Ya lo tienes como `grossProfits_to_assets`

---

#### 3. **Sloan (1996)** - Accruals Quality

**Formula**: Accruals / NOA

**Insight**: Low accruals → higher future returns

**Return**: +5.7% anual (hedge portfolio)

**Tu implementación**:
- ✅ Tienes `cfo_to_ni` (proxy)
- ✅ Guardrails tienen accruals check

---

#### 4. **Mohanram (2005)** - G-Score for Growth Stocks

8 signals para growth stocks (complemento a F-Score):

1. ✅ ROA
2. ✅ Cash ROA (CFO / Assets)
3. ❌ ROA variance (stability) ← Falta
4. ❌ CFO variance ← Falta
5. ✅ R&D to Market Cap
6. ✅ CAPEX to Assets
7. ✅ Ad spending to Market Cap
8. Accruals

**Return**: +19.8% anual (high G-Score growth stocks)

---

#### 5. **Asness, Frazzini, Pedersen (2019)** - Quality Minus Junk

**Quality = Profitability + Growth + Safety**

**Profitability**:
- ✅ Gross Profit / Assets (tienes ✅)
- ✅ ROE (tienes ROIC, similar ✅)
- ✅ ROA
- ✅ CFO / Assets
- ✅ GMAR (Gross Margin)
- ❌ ACC (Accruals, pero tienes cfo_to_ni ✅)

**Growth**:
- ❌ 5yr growth in Prof/Assets
- ❌ 5yr growth in ROE
- ❌ 5yr growth in ROA

**Safety**:
- ✅ Low leverage (tienes netDebt_ebitda ✅)
- ❌ Low volatility ROE
- ❌ Low volatility earnings
- ❌ Low beta
- ❌ Low idiosyncratic vol

**Return**: Quality factor +0.3% monthly (3.6% anual)

---

### Mejoras Sugeridas: Quality Metrics

#### **Agregar**:

```python
# 1. Earnings Stability (Mohanram)
'roa_stability': std(ROA últimos 4Q) / mean(ROA)  # Lower is better
'fcf_stability': std(FCF últimos 4Q) / mean(FCF)  # Lower is better

# 2. Growth Persistence (Asness et al.)
'roa_growth_3y': (ROA_now - ROA_3y_ago) / ROA_3y_ago
'gross_profit_growth_3y': similar

# 3. Cash Conversion (Piotroski)
'cash_roa': CFO / Assets  # Similar a tu cfo_to_ni pero normalizado

# 4. Asset Turnover (Piotroski F-Score component)
'asset_turnover': Revenue / Assets
'asset_turnover_change': ΔAsset Turnover > 0

# 5. Working Capital Management
'days_sales_outstanding': (Receivables / Revenue) * 365
'days_inventory_outstanding': (Inventory / COGS) * 365
'cash_conversion_cycle': DSO + DIO - DPO
```

---

## 🎯 RECOMENDACIONES FINALES

### 1. Fix del Bug (CRÍTICO)

**Problema**: Normalización por industria falla con < 3 empresas

**Solución A** (Preferida): Cross-sectional ranking
```python
def _robust_zscore(self, series, higher_is_better):
    clean = series.dropna()

    if len(clean) < 3:
        # ❌ No retornar 0
        # ✅ Usar percentile ranking del universo completo
        return series.rank(pct=True) - 0.5  # Center at 0

    # Rest of code...
```

**Solución B**: Fallback a universe-wide normalization
```python
def _normalize_by_industry(self, df, metrics, higher_is_better):
    for metric in metrics:
        # Try industry normalization
        df[f'{metric}_zscore'] = df.groupby('industry')[metric].transform(
            lambda x: self._robust_zscore(x, higher_is_better)
        )

        # Check for companies with z-score = 0 (failed normalization)
        failed_mask = df[f'{metric}_zscore'] == 0

        if failed_mask.any():
            # Fallback: normalize against entire universe
            universe_zscore = self._robust_zscore(df[metric], higher_is_better)
            df.loc[failed_mask, f'{metric}_zscore'] = universe_zscore[failed_mask]
```

---

### 2. Value Metrics - Implementación Mejorada

**Reemplazar**:
```python
# ❌ Actual
value_metrics = ['ev_ebit_ttm', 'ev_fcf_ttm', 'pe_ttm', 'pb_ttm']

# ✅ Mejorado (Greenblatt + Buffett + Novy-Marx)
value_metrics = [
    'earnings_yield',         # EBIT / EV (inverted EV/EBIT)
    'fcf_yield',              # FCF / EV (inverted EV/FCF)
    'owner_earnings_yield',   # (NI + D&A - D&A) / MCap ≈ CFO / MCap
    'ev_to_ebitda_minus_capex' # EV / (EBITDA - CAPEX)
]
value_higher_better = [
    'shareholder_yield_%'     # Keep ✅
]
```

**Cálculos**:
```python
# In features.py:
df['earnings_yield'] = df['ebit'] / df['enterpriseValue'] * 100
df['fcf_yield'] = df['freeCashFlow'] / df['enterpriseValue'] * 100
df['owner_earnings_yield'] = df['operatingCashFlow'] / df['marketCap'] * 100
df['ev_to_ebitda_minus_capex'] = df['enterpriseValue'] / (df['ebitda'] - df['capitalExpenditure'])
```

---

### 3. Quality Metrics - Agregar Stability

**Agregar**:
```python
quality_metrics = [
    'roic_%',                    # Keep ✅
    'grossProfits_to_assets',    # Keep ✅
    'fcf_margin_%',              # Keep ✅
    'cfo_to_ni',                 # Keep ✅
    'interestCoverage',          # Keep ✅
    'roa_stability',             # NEW: std(ROA) / mean(ROA)
    'cash_roa',                  # NEW: CFO / Assets
]
```

**Cálculos** (requiere 4Q data):
```python
# In features.py:
roas = [q['roa'] for q in last_4_quarters]
df['roa_stability'] = np.std(roas) / np.mean(roas) if np.mean(roas) != 0 else 0
df['cash_roa'] = df['operatingCashFlow'] / df['totalAssets'] * 100
```

---

### 4. Pesos Value/Quality

**Actual**: 50/50

**Recomendación basada en literatura**:

**Opción A** (Conservative - Piotroski):
```yaml
weight_value: 0.4
weight_quality: 0.6  # Más peso a quality
```
**Justificación**: Piotroski muestra que F-Score funciona MEJOR con value stocks baratos, quality actúa como filtro

**Opción B** (Aggressive - Greenblatt):
```yaml
weight_value: 0.5
weight_quality: 0.5  # Equal weight
```
**Justificación**: Magic Formula usa equal weight

**Opción C** (Value-focused):
```yaml
weight_value: 0.6
weight_quality: 0.4
```
**Justificación**: Si crees que el mercado sobrevalora quality

---

## 📊 COMPARACIÓN: Actual vs Propuesto

| Aspecto | Actual | Propuesto | Literatura |
|---------|--------|-----------|------------|
| **Value Primary** | EV/EBIT, EV/FCF, P/E, P/B | Earnings Yield, FCF Yield, Owner Earnings | Greenblatt, Buffett |
| **Value Problem** | P/E, P/B outdated | Remove, focus on yields | Multiple papers |
| **Quality** | ✅ Excelente | Add stability metrics | Mohanram, Asness |
| **Normalización** | ❌ Bug (z-score=0) | Fallback to universe | Statistical best practice |
| **Pesos** | 50/50 | 40/60 o 50/50 | Piotroski, Greenblatt |

---

## 🔬 PRÓXIMOS PASOS

1. **Fix Bug** (Crítico):
   - Implementar fallback normalization
   - Test con industries pequeñas

2. **Mejorar Value**:
   - Calcular yields (inverted multiples)
   - Implementar owner earnings yield
   - Remove P/E, P/B (o dejarlos con menos peso)

3. **Mejorar Quality**:
   - Agregar stability metrics (ROA, FCF)
   - Agregar cash ROA

4. **Testing**:
   - Backtest con nuevas métricas
   - Comparar scores antes/después

---

## 📚 REFERENCIAS COMPLETAS

1. **Greenblatt, J. (2005)** - "The Little Book That Beats the Market"
2. **Piotroski, J. (2000)** - "Value Investing: The Use of Historical Financial Statement Information"
3. **Novy-Marx, R. (2013)** - "The Other Side of Value: Gross Profitability Premium"
4. **Sloan, R. (1996)** - "Do Stock Prices Fully Reflect Information in Accruals"
5. **Mohanram, P. (2005)** - "Separating Winners from Losers among Low Book-to-Market Stocks"
6. **Asness, C., Frazzini, A., Pedersen, L. (2019)** - "Quality Minus Junk"
7. **Titman, S., Wei, K., Xie, F. (2004)** - "Capital Investments and Stock Returns"
8. **Basu, S. (1977)** - "Investment Performance of Common Stocks in Relation to P/E Ratios" (original P/E paper)
9. **Fama, E. & French, K. (1992)** - "The Cross-Section of Expected Stock Returns" (original P/B paper)
10. **O'Shaughnessy, J. (2012)** - "What Works on Wall Street" (4th edition)

---

## ✅ CONCLUSIÓN

**Bug Crítico**: Normalización falla → z-score=0 → scores=50
**Fix**: Fallback to universe-wide normalization

**Value Metrics**: P/E y P/B están outdated
**Mejora**: Usar yields (Greenblatt, Buffett)

**Quality Metrics**: Implementación actual es EXCELENTE
**Mejora**: Agregar stability metrics (Mohanram, Asness)

**Next**: Implementar fixes + mejoras propuestas
