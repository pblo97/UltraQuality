# Advanced Features Guide

## 🎉 Nuevas Funcionalidades Implementadas

Este documento describe las **5 herramientas avanzadas** agregadas al sistema UltraQuality para mejorar el análisis técnico y la gestión de riesgo.

---

## 1. 📊 Visualización Gráfica de Niveles

**Ubicación**: Technical Analysis → Advanced Tools → Price Levels Chart

### ¿Qué hace?

Muestra un gráfico interactivo con:
- **Precio actual** y últimos 90 días de historial
- **MA50 y MA200** (líneas de soporte/resistencia)
- **Niveles de entrada** (scale-in tranches)
- **Stop loss levels** (aggressive/moderate/conservative)
- **Zona de overextension** (sombreada en rojo si >30% sobre MA200)

### Cómo usar

1. Selecciona un stock en Technical Analysis
2. Ve a la tab "Advanced Tools"
3. El gráfico se genera automáticamente
4. **Hover** sobre las líneas para ver valores exactos
5. **Zoom/Pan** para explorar diferentes períodos

### Ejemplo

```
NVDA - Current: $175.00
├─ MA50: $162.00 (entrada tranche 2)
├─ MA200: $110.00 (entrada tranche 3)
├─ Aggressive Stop: $162.00
└─ Zona overextension: >$143.00 (rojo)
```

---

## 2. 🔬 Backtesting de Overextension

**Ubicación**: Technical Analysis → Advanced Tools → Historical Analysis

### ¿Qué hace?

Analiza **2 años de historial** del stock para encontrar todas las veces que estuvo sobreextendido (>40% sobre MA200) y calcula:

- **Cuántas veces** pasó
- **Corrección promedio** (ej: -25%)
- **Corrección máxima** (ej: -45%)
- **Días hasta corrección** (ej: 30 días)
- **Tasa de corrección** (ej: 85% de las veces corrigió)

### Cómo usar

1. Selecciona un stock (ej: NVDA)
2. Click en "Run Backtest for [SYMBOL]"
3. Espera 5-10 segundos (analiza 2 años de datos)
4. Revisa las métricas y tabla de eventos recientes

### Interpretación

```
Instances Found: 8
Avg Correction: -28.5%
Max Correction: -42.1%
Avg Days: 35

Interpretación:
- NVDA ha estado sobreextendido 8 veces en 2 años
- En promedio, corrige -28.5% desde el pico
- La peor corrección fue -42.1%
- Tarda ~35 días en corregir

Acción: Scale-in strategy recomendada para reducir timing risk
```

---

## 3. 💰 Options P&L Calculator

**Ubicación**: Technical Analysis → Advanced Tools → Options Calculator

### ¿Qué hace?

Calcula **métricas exactas** para 5 estrategias de opciones:

1. **Covered Call** - Income generation
2. **Protective Put** - Downside protection
3. **Collar** - Zero-cost protection
4. **Cash-Secured Put** - Entry at discount
5. **Bull Put Spread** - Defined risk/reward

Para cada estrategia calcula:
- **Premium** (credit o debit)
- **Max Profit / Max Loss**
- **Break-even price**
- **Annualized return**
- **Probability of profit**
- **Greeks** (Delta, Theta, Vega, Gamma)

### Cómo usar

1. Selecciona una estrategia del dropdown
2. Ajusta parámetros:
   - **Days to Expiration** (7-180 días)
   - **Implied Volatility** (10-100%)
   - **Strike** (% OTM)
3. Revisa métricas calculadas en tiempo real

### Ejemplo - Covered Call en NVDA

```
Inputs:
- Stock Price: $175.00
- Strike: $187.00 (7% OTM)
- Days to Expiry: 45
- IV: 42%

Results:
✅ Premium Collected: $7.35 (4.2% of stock price)
✅ Max Profit: $19.35 (11.1% return)
✅ Annualized Return: 90%
✅ Probability of Profit: 68%
✅ Break-even: $167.65

Greeks:
- Delta: 0.312
- Theta: -0.045 (daily decay)
- Vega: 0.283
- Gamma: 0.0124

Interpretación:
Si vendes un call $187 (45 DTE):
- Recibes $735 de premium inmediato
- Si NVDA se queda ≤$187 → Profit $735 + dividends
- Si NVDA sube >$187 → Profit $1,935 (capped)
- Break-even downside: stock puede caer hasta $167.65
- Probabilidad 68% de quedar con todo el premium
```

### Fórmulas Usadas

- **Black-Scholes Model** para pricing
- **Normal Distribution** para probabilidades
- **Greeks** calculados con derivadas parciales

---

## 4. 🌡️ Market Timing Dashboard

**Ubicación**: Technical Analysis → Advanced Tools → Market Timing

### ¿Qué hace?

Analiza **condiciones macro del mercado** para ayudarte a decidir cuándo ser agresivo vs defensivo:

#### Métricas Analizadas

1. **SPY vs MA200**
   - ¿Mercado en bull o bear trend?
   - % de extensión

2. **VIX (Volatility Index)**
   - <15 = Complacency (riesgo de spike)
   - 15-20 = Normal
   - 20-30 = Elevated (caution)
   - >30 = Fear (oportunidad contrarian)

3. **Market Breadth**
   - % de sectores sobre MA200
   - <40% = Weak (defensive)
   - 60-80% = Good (normal)
   - >80% = Excellent (agresivo)

4. **Sector Overextension**
   - Qué sectores están extendidos
   - Dónde buscar oportunidades

5. **% Stocks Overextended**
   - % del mercado >40% sobre MA200
   - >40% = Peligro de corrección
   - <15% = Saludable

#### Recomendación Overall

Genera recomendación con 4 niveles:

| Stance | Risk Score | Cash % | Condiciones |
|--------|-----------|---------|-------------|
| 🟢 BULLISH | 0-2 | 0-10% | VIX bajo, breadth fuerte, pocos overextended |
| 🟢 NEUTRAL | 3-4 | 10-20% | Condiciones normales |
| 🟡 CAUTIOUS | 5-6 | 20-30% | Algunas señales de peligro |
| 🔴 DEFENSIVE | 7+ | 40-60% | Múltiples red flags, corrección inminente |

### Cómo usar

1. Click "Analyze Market Conditions"
2. Espera 10-15 segundos (analiza SPY, VIX, 11 sectores)
3. Revisa métricas y recomendación overall

### Ejemplo - Mercado DEFENSIVE

```
📊 SPY: $475 (+3.2% from MA200) ✅
😱 VIX: 32.5 (HIGH FEAR) ⚠️
📈 Breadth: 35% sectors above MA200 (WEAK) 🔴
🔥 Overextension: 48% of stocks >40% extended 🔴

🎯 Overall: DEFENSIVE (Risk Score: 8/10)

Key Factors:
🔴 48% of stocks overextended
🔴 Weak breadth (35%)
🔴 High VIX (32.5) - Market stress
🟡 SPY still above MA200 but breadth divergence

Action: Raise cash to 40-60%, tighten stops, sell overextended positions
```

---

## 5. 💼 Portfolio Tracker

**Ubicación**: Technical Analysis → Advanced Tools → Portfolio

### ¿Qué hace?

Trackea tus **posiciones actuales** y genera **alertas automáticas** basadas en análisis técnico:

#### Features

1. **Position Tracking**
   - Entry price, quantity, tranches
   - Current P&L en $ y %
   - Cost basis tracking

2. **Alertas Automáticas**
   - 🎯 Scale-in opportunities (near MA50/MA200)
   - 🔴 Stop loss triggered
   - 💰 Profit targets hit
   - ⚠️ Overextension risk aumentó/disminuyó

3. **Portfolio Summary**
   - Total value, cost, P&L
   - Mejor/peor performer
   - # de tranches por posición

### Cómo usar

#### Agregar Posición

```
Tab: Add Position

Symbol: NVDA
Quantity: 100
Entry Price: $175.00
Notes: Initial tranche (scale-in strategy)

→ Click "Add Position"
```

#### Ver Alertas

```
Tab: Alerts

NVDA ($168.50, -3.7%)
🎯 Near MA50 ($162.00) - potential scale-in opportunity!

AAPL ($185.20, +8.5%)
💰 Up +8.5%! Consider taking partial profits

TSLA ($245.80, -12.3%)
🔴 Down -12.3%! Review stop loss
```

#### Add Tranche (Scale-in)

Cuando una alerta dice "near MA50", puedes agregar tranche:

```python
# En código o manualmente:
tracker.add_tranche(
    symbol='NVDA',
    price=162.00,
    quantity=150,  # Tranche 2: 35% of total
)

# Ahora tu average cost es:
# (100 * $175 + 150 * $162) / 250 = $167.40
```

### Persistencia

Posiciones se guardan en `portfolio.json`:

```json
{
  "NVDA": {
    "entry_price": 167.40,
    "quantity": 250,
    "tranches": [
      {"date": "2024-01-15", "price": 175.00, "quantity": 100, "pct": 40},
      {"date": "2024-02-10", "price": 162.00, "quantity": 150, "pct": 60}
    ]
  }
}
```

---

## 🔧 Integración con Sistema Existente

### Dónde se Integran

Todas las herramientas se integran en la **tab "Technical Analysis"** bajo una nueva sección **"Advanced Tools"**:

```
Technical Analysis
├─ Stock Selection
├─ Detailed Analysis (existing)
│  ├─ Market Context
│  ├─ Technical Components
│  ├─ Detailed Metrics
│  └─ Risk Management ← Ya existente
│
└─ 🆕 Advanced Tools ← NUEVO
   ├─ 📊 Price Levels Chart
   ├─ ⚠️ Overextension Gauge
   ├─ 🔬 Historical Backtest
   ├─ 💰 Options Calculator
   ├─ 🌡️ Market Timing
   └─ 💼 Portfolio Tracker
```

### Flujo de Uso Recomendado

1. **Screener** → Encuentra stocks con buenos fundamentals
2. **Technical Analysis** → Valida timing con score 0-100
3. **Risk Management** (existente) → Ve overextension risk y estrategias
4. **Advanced Tools** 🆕:
   - **Price Levels Chart** → Visualiza niveles de entrada/stop
   - **Backtest** → Valida que correcciones son comunes
   - **Options Calculator** → Calcula estrategia óptima (covered call, protective put, etc.)
   - **Market Timing** → Verifica condiciones macro
   - **Portfolio Tracker** → Trackea posición y recibe alertas

---

## 📊 Casos de Uso

### Caso 1: Stock Overextendido (NVDA +58% sobre MA200)

```
1. Screener → NVDA aparece con score 94/100 (BUY)

2. Technical Analysis → Detalles:
   - Overextension Risk: 4/7 (HIGH)
   - Distance MA200: +58%
   - Recommendation: SCALE-IN (3 tranches)

3. Advanced Tools:

   a) Price Levels Chart:
      → Visualizo: Current $175, MA50 $162, MA200 $110
      → Zona roja empieza en $143 (30% sobre MA200)

   b) Backtest:
      → NVDA ha corregido 7 veces en 2 años
      → Corrección promedio: -31%
      → Conclusión: Scale-in es prudente

   c) Options Calculator:
      → Covered Call $187 (45 DTE):
         Premium: $7.35 (4.2%)
         Annualized: 90%
         P(profit): 68%
      → Decisión: Vender covered call después de comprar

   d) Market Timing:
      → Market: CAUTIOUS (45% stocks overextended)
      → VIX: 24 (elevated)
      → Recommendation: 20-30% cash
      → Conclusión: No es momento de ir all-in

   e) Portfolio Tracker:
      → Add position:
         Tranche 1: 25 shares @ $175 (25%)
         Set alerts para MA50 ($162) y MA200 ($110)

4. Ejecución:
   - Compro 25 shares @ $175
   - Vendo 1 covered call $187 (45 DTE) → +$735
   - Espero alerta para tranche 2
```

### Caso 2: Stock con Corrección (AAPL -15% en 2 semanas)

```
1. Portfolio Alert:
   "🎯 AAPL near MA50 ($178) - scale-in opportunity!"

2. Technical Analysis:
   - Overextension Risk: 0/7 → 1/7 (mejoró)
   - Was: +35% over MA200
   - Now: +20% over MA200
   - Recommendation: FULL ENTRY or SCALE-IN 2

3. Advanced Tools:

   a) Price Levels Chart:
      → Ya no está en zona overextension
      → MA50 ahora es soporte

   b) Backtest:
      → Cuando AAPL corrige a MA50, sube +18% en 3M (80% de las veces)

   c) Options Calculator:
      → Cash-Secured Put $175 (30 DTE):
         Premium: $3.20
         Effective entry: $171.80 (mejor que comprar @ $178)
         Annualized: 67%

   d) Market Timing:
      → Market: NEUTRAL (condiciones normales)
      → OK para agregar posición

4. Ejecución:
   - Vendo cash-secured put $175 → +$320
   - Si assigned → Entry efectivo $171.80 (3.5% descuento)
   - Si no assigned → Keep premium, repito next month
```

---

## 🎓 Mejores Prácticas

### 1. Backtesting

- **Siempre** backtestea antes de entrar en stocks overextendidos
- Si avg correction >25%, usa scale-in 3 tranches
- Si correction rate >70%, espera pullback en lugar de FOMO

### 2. Options Calculator

- **Covered Calls**: Usa en stocks overextendidos con high IV
- **Protective Puts**: Usa en holdings con >20% gain y overextension risk ≥4
- **Cash-Secured Puts**: Usa para entrar después de correcciones
- **Collars**: Usa en bear markets o high VIX (>30)

### 3. Market Timing

- **DEFENSIVE** (risk 7+): 40-60% cash, no compres overextendidos
- **CAUTIOUS** (risk 5-6): 20-30% cash, solo quality
- **NEUTRAL** (risk 3-4): 10-20% cash, normal
- **BULLISH** (risk 0-2): 0-10% cash, agresivo en pullbacks

### 4. Portfolio Tracker

- **Agrega TODAS tus posiciones** para tracking automático
- **Revisa alerts diariamente** antes de mercado abre
- **Usa tranches** para scale-in sistemático
- **No ignores stop loss alerts** (disciplina > esperanza)

### 5. Combinación de Herramientas

**Mejor práctica**:
1. Backtest → Valida histórico
2. Market Timing → Contexto macro
3. Options Calculator → Estrategia óptima
4. Portfolio Tracker → Ejecución + alertas

---

## 📚 Referencias Académicas

Todas las herramientas están basadas en investigación académica:

### Backtesting
- George & Hwang (2004) - "52-week high momentum"
- De Bondt & Thaler (1985) - "Mean reversion"

### Options
- Black & Scholes (1973) - "Options pricing"
- Whaley (2002) - "Covered calls"
- Shastri & Tandon (1986) - "Protective puts"

### Market Timing
- Cooper et al. (2004) - "Market regime effects"
- Daniel & Moskowitz (2016) - "Momentum crashes"

---

## 🐛 Troubleshooting

### "No historical data available"
- Stock muy nuevo (<2 años de historial)
- Solución: Usa solo para stocks con >2 años de trading

### "Greeks not displaying"
- Scipy no instalado
- Solución: `pip install scipy>=1.11.0`

### "Portfolio not saving"
- Permisos de escritura
- Solución: Verifica que app tiene write access a `portfolio.json`

### "Market timing stuck"
- API rate limit
- Solución: Espera 1 minuto, analiza menos stocks

---

## 🚀 Próximas Mejoras

Features planeadas pero no implementadas (por ahora):

1. **Peer Comparison Charts** - Comparar overextension vs peers en sector
2. **Correlation Matrix** - Analizar correlación de portfolio
3. **Machine Learning Predictions** - Predecir probabilidad de corrección
4. **Export TradingView Alerts** - Generar alerts automáticas
5. **Real-time Alerts** - Push notifications cuando price hits levels

---

## 📞 Soporte

Para reportar bugs o sugerir mejoras:
1. GitHub Issues: `https://github.com/anthropics/claude-code/issues`
2. Documentación: `RISK_MANAGEMENT_IMPLEMENTATION.md`
3. Guía de troubleshooting: `TECHNICAL_ANALYSIS_TROUBLESHOOTING.md`

---

**Versión**: v6.0 (Advanced Features)
**Última actualización**: 2024-11-29
**Status**: ✅ Completado y listo para uso
