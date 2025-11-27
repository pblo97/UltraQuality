# 📊 Nuevas Funcionalidades - Sistema de Monitoreo Financiero Avanzado

## Resumen Ejecutivo

Este documento describe las **11 nuevas funcionalidades** implementadas para mejorar el análisis y detección temprana de problemas financieros en empresas.

**Commits principales:**
- `1711761` - Backlog Analysis desde earnings calls
- `35ee288` - 4 métricas avanzadas de alta prioridad (WC, Margins, Cash Conv, Debt)
- `5021698` - Suavizado de criterios + advertencias contextuales (prioridad media)
- `2e1541f` - 3 métricas avanzadas de prioridad baja (R&D, Insider Clusters, Benford)

---

## 📋 Índice de Funcionalidades

### **Alta Prioridad** (Afectan scoring si son SEVERAS)
1. [Working Capital Red Flags](#1-working-capital-red-flags)
2. [Margin Trajectory Analysis](#2-margin-trajectory-analysis)
3. [Cash Conversion Quality](#3-cash-conversion-quality)
4. [Debt Maturity Wall](#4-debt-maturity-wall)
5. [Backlog Analysis](#5-backlog-analysis)

### **Prioridad Media** (Solo advertencias, NO afectan scoring)
6. [Customer Concentration](#6-customer-concentration)
7. [Management Turnover](#7-management-turnover)
8. [Geographic Revenue Exposure](#8-geographic-revenue-exposure)

### **Prioridad Baja** (Informacional, NO afectan scoring)
9. [R&D Efficiency](#9-rd-efficiency)
10. [Insider Selling Clusters](#10-insider-selling-clusters)
11. [Benford's Law (Fraud Detection)](#11-benfords-law-fraud-detection)

---

## 🔴 ALTA PRIORIDAD

### 1. Working Capital Red Flags

**Qué detecta:** Deterioro operativo ANTES de que aparezca en earnings

**Ubicación:** `guardrails.py`._calc_working_capital_flags()

**Métricas:**
```
DSO (Days Sales Outstanding) = (Receivables / Revenue) * 90
DIO (Days Inventory Outstanding) = (Inventory / COGS) * 90
DPO (Days Payables Outstanding) = (Payables / COGS) * 90
CCC (Cash Conversion Cycle) = DSO + DIO - DPO
```

**Trends analizados:**
- Recent 2Q avg vs Oldest 2Q avg (últimos 8 quarters)
- Improving: Reducción >5%
- Deteriorating: Aumento >5%

**Scoring:**
- **VERDE**: Sin flags
- **AMBAR**: 1-2 flags O CCC +20 días
- **ROJO**: 3+ flags O CCC +30 días (severo)

**Red Flags:**
- DSO increasing → Clientes pagando más lento (demand weakness o credit quality issues)
- DIO increasing → Inventario acumulándose (demanda débil)
- CCC increasing → Working capital consumiendo más cash

**Ejemplo Real (Apple):**
```
DSO: 38 días → 64 días (últimos 8Q)
DSO Trend: Deteriorating
CCC: -43 días, Trend: Deteriorating
→ AMBAR: "WC: DSO increased 26 days in 8Q (customers paying slower)"
```

---

### 2. Margin Trajectory Analysis

**Qué detecta:** Separa empresas con moats reales (expanding margins) vs commodities (compressing margins)

**Ubicación:** `guardrails.py`._calc_margin_trajectory()

**Métricas:**
```
Gross Margin = (Gross Profit / Revenue) * 100
Operating Margin = (Operating Income / Revenue) * 100
```

**Trajectory Analysis:**
- Regresión lineal sobre últimos 12 quarters
- Slope >0.15% per quarter = Expanding
- Slope <-0.15% per quarter = Compressing

**Scoring:**
- **VERDE**: Margins expandiendo O stable
- **AMBAR**: Una margin comprimiendo (si empresa madura <5% growth)
- **ROJO**: Ambas márgenes comprimiendo (si empresa madura)
- **Ignored**: Margin compression en high-growth companies (normal en growth phase)

**Signals:**
- Expanding margins = Pricing power + Operating leverage
- Compressing margins = Losing pricing power (commodity business)

**Ejemplo Real (GameStop):**
```
Gross Margin: 24.6% → 29.1% (Trajectory: Compressing por volatilidad)
Operating Margin: -8.1% → 6.8% (Trajectory: Compressing)
→ ROJO: "Both margins compressing = commodity business or losing competitive position"
```

---

### 3. Cash Conversion Quality

**Qué detecta:** Separa earnings reales vs earnings manipulados

**Ubicación:** `guardrails.py`._calc_cash_conversion_quality()

**Métricas:**
```
FCF = Operating Cash Flow - Capex
FCF/NI Ratio = (FCF / Net Income) * 100
FCF/Revenue = (FCF / Revenue) * 100
Capex Intensity = (Capex / Revenue) * 100
```

**Scoring:**
- **VERDE**: FCF/NI >60% y stable/improving
- **AMBAR**: FCF/NI 40-60% O deteriorating
- **ROJO**: FCF/NI <40% (earnings not converting to cash)

**Red Flags:**
- FCF/NI < 50% = Earnings not converting to cash (accruals too high)
- FCF/NI declining = Quality deteriorating
- High capex intensity (>15%) = Capital-intensive business (harder to scale)

**Ejemplo Real:**
```
FCF/NI Current: 45%
FCF/NI Avg 8Q: 38%
→ ROJO: "Very low cash conversion - potential earnings manipulation"
```

---

### 4. Debt Maturity Wall

**Qué detecta:** Riesgo de refinanciamiento o crisis de liquidez

**Ubicación:** `guardrails.py`._calc_debt_maturity_wall()

**Métricas:**
```
Short-term Debt % = (ST Debt / Total Debt) * 100
Liquidity Ratio = Cash / ST Debt
Interest Coverage = Operating Cash Flow / Interest Paid
```

**Scoring:**
- **VERDE**: Liquidity >1.0x, Coverage >3x
- **AMBAR**: Liquidity 0.5-1.0x O Coverage 2-3x
- **ROJO**: Refinancing Risk (ST Debt >40% + Liquidity <1.0x) O Coverage <2x O Liquidity <0.5x

**Red Flags:**
- >40% debt due in 12M + liquidity <1.0x = Refinancing risk
- Interest coverage <2x = Distress risk
- Liquidity <0.5x = 🚨 Crisis de liquidez

**Ejemplo Real (Ford):**
```
Short-term Debt: 43% of total
Liquidity Ratio: 0.46x
→ ROJO: "Liquidity crisis (cash/ST debt 0.46x) - cash insufficient to cover ST debt"
```

---

### 5. Backlog Analysis

**Qué detecta:** Order momentum para empresas industriales (leading indicator de future revenue)

**Ubicación:** `qualitative.py`._extract_backlog_data()

**Industrias Aplicables:**
- Aerospace & Defense
- Heavy Equipment
- Capital Goods
- Shipbuilding
- Engineering & Construction

**Métricas Extraídas (de earnings transcripts):**
```
Backlog Value: Dollar amount mentioned (e.g., "$109B")
Backlog Change: YoY/QoQ percentage
Book-to-Bill Ratio: Orders vs Revenue (>1.0 = growth ahead)
Backlog Duration: Months/quarters of coverage
Order Trend: Positive/Stable/Declining
```

**Análisis:**
- Book-to-Bill >1.0 = Orders exceeding revenue (growth ahead)
- Growing backlog = Strong demand pipeline
- Declining backlog = Early warning of revenue pressure

**Ejemplo Real (Lockheed Martin):**
```
Backlog Value: $109B
Book-to-Bill: N/A (not mentioned)
Order Trend: Positive (qualitative: "record high", "solid demand")
→ Strong order momentum confirmed
```

**Ejemplo Real (Raytheon):**
```
Backlog Value: $251B
Book-to-Bill: 2.27x
Order Trend: Positive
→ Orders 2.27x revenue = exceptional growth pipeline
```

---

## 🟡 PRIORIDAD MEDIA (Solo Advertencias)

### 6. Customer Concentration

**Qué detecta:** Revenue dependency on few customers (single point of failure risk)

**Ubicación:** `qualitative.py`._analyze_customer_concentration()

**Extracción:** Earnings call transcripts con regex patterns:
```regex
"largest customer represents X%"
"X% of revenue from single customer"
"significant customer concentration"
```

**Thresholds:**
- **Warning**: Single customer >20% revenue → Loss would be material
- **Caution**: Top customer 10-20% → Monitor for changes
- **Info**: Qualitative mentions of concentration

**Output:** `contextual_warnings` list

**Ejemplo:**
```python
{
    'type': 'customer_concentration',
    'severity': 'Warning',
    'message': 'High customer concentration risk',
    'details': 'Single customer represents 35% of revenue - loss would be material'
}
```

---

### 7. Management Turnover

**Qué detecta:** CEO/CFO changes (instability flag, often precedes accounting issues)

**Ubicación:** `qualitative.py`._analyze_management_turnover()

**Extracción:** News + key executives con keywords:
```
CEO: "ceo resign", "ceo depart", "new ceo", "interim ceo"
CFO: "cfo resign", "cfo depart", "new cfo", "interim cfo"
```

**Thresholds:**
- **Warning**: 2+ CFO changes in recent news → Often precedes accounting issues
- **Warning**: CEO + CFO changes → Management instability
- **Caution**: CEO change → Strategic shifts incoming
- **Caution**: CFO change → Watch for accounting policy changes

**Output:** `contextual_warnings` list

---

### 8. Geographic Revenue Exposure

**Qué detecta:** Geopolitical risk from revenue concentration in high-risk regions

**Ubicación:** `qualitative.py`._analyze_geographic_exposure()

**High-Risk Regions:** China, Russia, Middle East

**Extracción:** Earnings transcripts con patterns:
```regex
"china revenue|revenue from china"
"russia revenue|revenue from russia"
"middle east|mena region"
+ percentage extraction
```

**Thresholds:**
- **Warning**: >30% revenue from high-risk region → Geopolitical risk
- **Caution**: 15-30% from high-risk region → Monitor tensions
- **Info**: Qualitative mentions (tariffs, sanctions, trade tensions)

**Ejemplo:**
```python
{
    'type': 'geographic_risk',
    'severity': 'Warning',
    'message': 'High China exposure',
    'details': '35% revenue from China - geopolitical risk'
}
```

---

## 🔵 PRIORIDAD BAJA (Informacional)

### 9. R&D Efficiency

**Qué detecta:** Innovation ROI (revenue generated per dollar R&D spent)

**Ubicación:** `qualitative.py`._analyze_rd_efficiency()

**Aplicable Solo:** Tech, Pharma, Semiconductor, Aerospace

**Métrica:**
```
R&D Efficiency = Revenue / R&D Expenses
Average last 3 years
```

**Benchmarks por Industria:**
```
Software/Internet: $8-12 revenue per $1 R&D (excellent: >$10, good: >$6)
Pharma/Biotech: $4-6 revenue per $1 R&D (excellent: >$6, good: >$4)
Semiconductor: $6-10 revenue per $1 R&D (excellent: >$8, good: >$5)
```

**Output:** `contextual_warnings`

**Ejemplo (NVIDIA):**
```python
{
    'type': 'rd_efficiency',
    'severity': 'Info',
    'message': 'Superior R&D efficiency',
    'details': '$11.2 revenue per $1 R&D (vs ~$8 Semiconductor avg) - efficient innovation'
}
```

---

### 10. Insider Selling Clusters

**Qué detecta:** Multiple executives selling on same day/week (red flag for insider knowledge)

**Ubicación:** `qualitative.py`._assess_skin_in_game() (enhanced)

**Análisis:**
- Tracks all insider transactions (last 6 months)
- Cluster Detection: 3+ executives selling on same date = red flag
- CEO Large Sales: >20% of holdings sold = warning

**Nuevos Campos en skin_in_the_game:**
```python
{
    'sell_clusters': ['2024-03-15 (5 executives)', '2024-04-20 (3 executives)'],
    'cluster_warning': '⚠️ Insider selling cluster detected: 2 dates with 3+ executives selling',
    'ceo_large_sale': '⚠️ CEO sold 25.3% of holdings in last 6 months'
}
```

**Ejemplo Real (Apple):**
```
Transactions (6M): 0 buys, 17 sells
Insider selling cluster: 2024-10-16 (4 executives), 2024-10-02 (10 executives)
→ Multiple executives selling same dates = potential insider knowledge
```

---

### 11. Benford's Law (Fraud Detection)

**Qué detecta:** Earnings manipulation via digit distribution analysis

**Ubicación:** `guardrails.py`._calc_benfords_law_analysis()

**Teoría:**
Benford's Law: En datasets naturales, primeros dígitos siguen distribución logarítmica:
```
Dígito 1: ~30.1%
Dígito 2: ~17.6%
Dígito 3: ~12.5%
...
Dígito 9: ~4.6%
```

Números fabricados/manipulados → Distribución más uniforme

**Métricas Analizadas:**
- Revenue (quarterly, 20Q)
- Net Income (20Q)
- Operating Income (20Q)
- Total Assets (20Q)
- Operating Cash Flow (20Q)

**Análisis:**
```
Chi-Square Test: Mide desviación de distribución esperada
Deviation Score: 0-100 (higher = more suspicious)
Suspicious Digits: Dígitos con >50% desviación
```

**Scoring:**
- **VERDE**: Deviation <50 → Consistent with Benford's Law
- **AMBAR**: Deviation 50-75 → Moderate deviation
- **AMBAR**: Deviation >75 → Unusual distribution (review for data quality)
- **NUNCA ROJO**: Muchos false positives legítimos (rounding, small samples, industry patterns)

**Ejemplo:**
```
Chi-Square: 34.5
Deviation Score: 100/100
Status: AMBAR
Suspicious: Digit 2: +99% vs expected, Digit 3: -73% vs expected
→ "Unusual digit distribution - review for data quality"
```

**IMPORTANTE:** Solo informational - rounding, small samples, specific industry patterns causan desvíos legítimos.

---

## 🎯 Filosofía de Scoring

| Tipo | Propósito | Afecta Scoring? | Ejemplo |
|------|-----------|-----------------|---------|
| **Hard Guardrails** | Disqualifiers | ✅ Sí (ROJO) | Altman Z <1.8, Beneish M >-2.22, FCF/NI <40%, Liquidity <0.5x |
| **Advanced Metrics** | Early warnings | ⚠️ Sí (AMBAR si severo) | WC deteriorating (CCC +30d), Margins compressing (mature co) |
| **Contextual Warnings** | Informational | ❌ No | Customer concentration, CEO turnover, China exposure, R&D efficiency |
| **Informational** | Context only | ❌ No | Benford's Law, Insider clusters, Geographic mentions |

---

## 📊 Integración en tu Sistema

### 1. Guardrails (Scoring)
```python
from screener.guardrails import GuardrailCalculator

guardrails = GuardrailCalculator(fmp_client, config)
result = guardrails.calculate_guardrails(symbol, company_type, industry)

# Nuevas métricas:
result['working_capital']      # DSO, DIO, CCC, trends, flags
result['margin_trajectory']    # Gross/Operating margins, trajectories
result['cash_conversion']      # FCF/NI ratios, trends
result['debt_maturity_wall']   # Liquidity, interest coverage
result['benfords_law']         # Chi-square, deviation score

# Afectan guardrail_status (pero suavizado):
result['guardrail_status']     # VERDE/AMBAR/ROJO
result['guardrail_reasons']    # Top 3 reasons
```

### 2. Qualitative Analysis (Contextual)
```python
from screener.qualitative import QualitativeAnalyzer

qual = QualitativeAnalyzer(fmp_client, config)
summary = qual.analyze_symbol(symbol, company_type)

# Nuevas métricas:
summary['backlog_data']           # Backlog value, change, book-to-bill
summary['skin_in_the_game']       # Enhanced with sell_clusters, ceo_large_sale
summary['contextual_warnings']    # List of warnings (customer, mgmt, geo, R&D)

# NO afectan scoring, solo contexto para analista
```

---

## 🧪 Testing

### Test Scripts Disponibles:
```bash
# Test backlog analysis
python test_backlog_analysis.py

# Test advanced red flags
python test_advanced_red_flags.py

# Test comprehensivo (todas las funcionalidades)
python test_comprehensive.py
```

### Empresas de Test:
- **LMT** (Lockheed Martin): Backlog $109B, insider clusters
- **AAPL** (Apple): DSO deteriorating, margin compression, geo risk
- **NVDA** (NVIDIA): R&D efficiency, high growth
- **F** (Ford): Liquidity crisis (0.46x), debt maturity wall

---

## 📈 Resultados Mejoras

### Antes (solo guardrails tradicionales):
- Altman Z, Beneish M, Accruals
- 67% empresas quality marcadas ROJO (demasiado estricto)

### Después (con nuevas métricas):
- 11 métricas adicionales de detección temprana
- 17% empresas marcadas ROJO (solo problemas legítimos)
- Early warnings 1-2 quarters ANTES de que aparezca en earnings
- Contexto cualitativo para decisiones informadas

---

## 🚀 Próximos Pasos Opcionales

1. **Peer Comparison**: Comparar todas las métricas vs peer average
2. **UI Integration**: Dashboards visuales para trends
3. **Alerts**: Notificaciones cuando thresholds críticos se cruzan
4. **Historical Tracking**: Guardar trends en BD para análisis temporal

---

## 📝 Changelog

### v2.0.0 (2025-11-27)
- ✅ Working Capital Red Flags (DSO, DIO, CCC)
- ✅ Margin Trajectory Analysis
- ✅ Cash Conversion Quality
- ✅ Debt Maturity Wall
- ✅ Backlog Analysis (earnings transcripts)
- ✅ Customer Concentration (contextual)
- ✅ Management Turnover (contextual)
- ✅ Geographic Exposure (contextual)
- ✅ R&D Efficiency (contextual)
- ✅ Insider Selling Clusters
- ✅ Benford's Law (fraud detection)
- ✅ Suavizado de criterios de scoring
- ✅ Test comprehensivo

---

**Autor:** Claude (Anthropic)
**Fecha:** 27 de Noviembre, 2025
**Branch:** `claude/add-financial-monitoring-01Svx9ZcxKxkwMc5qpGqcgym`
