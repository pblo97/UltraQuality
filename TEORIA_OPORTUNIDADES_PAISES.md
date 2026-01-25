# 🌍 Teoría: Identificación de Países con Oportunidades Técnicas

## 📋 Índice

1. [Objetivo](#objetivo)
2. [Metodología de Análisis](#metodología-de-análisis)
3. [Métricas Clave por Nivel](#métricas-clave-por-nivel)
4. [Framework de Evaluación](#framework-de-evaluación)
5. [Interpretación de Resultados](#interpretación-de-resultados)
6. [Limitaciones y Consideraciones](#limitaciones-y-consideraciones)

---

## 🎯 Objetivo

Identificar **qué mercados/países ofrecen las mejores oportunidades técnicas** para inversión basándose en:

1. **Número de oportunidades disponibles** (cantidad)
2. **Calidad de las empresas** (quality score)
3. **Señales técnicas favorables** (momentum, tendencia)
4. **Liquidez del mercado** (volumen, market cap)

**No buscamos**: Solo países "baratos" o en crisis
**Buscamos**: Países con empresas de calidad + señales técnicas alcistas + liquidez adecuada

---

## 🧠 Metodología de Análisis

### Enfoque Multi-Nivel

```
Nivel 1: SCREENING RÁPIDO (5 min)
├── Métricas de mercado agregadas
├── Disponibilidad de acciones
└── Liquidez general

Nivel 2: ANÁLISIS FUNDAMENTAL (30-60 min por país)
├── Ejecutar screener completo
├── Quality + Value scores
└── Guardrails (accounting quality)

Nivel 3: ANÁLISIS TÉCNICO (profundo)
├── Technical signals (BUY/HOLD/SELL)
├── Market state (POWER_TREND, DOWNTREND, etc.)
└── Momentum multi-timeframe
```

### Principios Fundamentales

**1. Quality First (Calidad Primero)**
- No queremos mercados "baratos" llenos de empresas de baja calidad
- Preferimos 10 oportunidades de calidad vs 100 mediocres
- Score de calidad promedio > 60/100 es requisito mínimo

**2. Technical Confirmation (Confirmación Técnica)**
- Las oportunidades deben tener señales técnicas favorables
- Momentum positivo (al menos 2 de 4 timeframes)
- Tendencia alcista (precio > MA200)
- NO comprar en DOWNTREND aunque score fundamental sea alto

**3. Liquidity Matters (Liquidez Importa)**
- Empresas con volumen diario < $2M = difícil entrar/salir
- Market cap < $500M = alta volatilidad, riesgo
- Preferir mercados con al menos 50 acciones líquidas

**4. Diversification Opportunity (Oportunidad de Diversificación)**
- Países con múltiples sectores representados
- No depender de un solo sector (ej: Brasil = solo commodities)
- Variedad de tamaños (large, mid, small caps)

---

## 📊 Métricas Clave por Nivel

### Nivel 1: Screening Rápido (Métricas de Mercado)

#### A. Tamaño del Mercado
```
Métrica: Total de acciones disponibles con filtros mínimos

Filtros base:
- Market cap > $500M
- Volumen diario > $1M
- Free float > 20%

Interpretación:
- > 500 acciones = Mercado grande (US, UK, India)
- 200-500 = Mercado mediano (Canadá, Alemania, Japón)
- 100-200 = Mercado pequeño (Hong Kong, Brasil)
- < 100 = Mercado muy limitado (considerar solo large caps)
```

#### B. Distribución de Capitalización
```
Métrica: % Large / Mid / Small caps

Definiciones:
- Large cap: > $10B
- Mid cap: $2B - $10B
- Small cap: $500M - $2B

Ideal:
- 20-30% Large caps (estabilidad)
- 40-50% Mid caps (oportunidades)
- 20-30% Small caps (growth)

Red flags:
- > 70% small caps = mercado inmaduro
- > 80% large caps = pocas oportunidades growth
```

#### C. Liquidez Agregada
```
Métrica: % de acciones con volumen > $5M diario

Interpretación:
- > 40% = Muy líquido (US, China)
- 20-40% = Líquido adecuado (UK, Canadá)
- 10-20% = Liquidez limitada (Brasil, India)
- < 10% = Problema de liquidez (cuidado)
```

#### D. Momentum General del Mercado
```
Métrica: % de acciones con precio positivo (YTD o 1M)

Interpretación:
- > 60% = Bull market (favorable para BUY)
- 40-60% = Neutral/Mixed
- < 40% = Bear market (esperar)

IMPORTANTE: NO comprar en bear markets globales
```

---

### Nivel 2: Análisis Fundamental (Quality + Value)

#### A. Oportunidades BUY Identificadas
```
Métrica: Número absoluto de señales BUY

Cálculo:
BUY = (Composite Score ≥ 65 AND Guardrails ≠ ROJO)
     OR (Quality Score ≥ 85 AND Composite ≥ 60)

Interpretación:
- > 50 BUY = Muchas oportunidades (US, China)
- 20-50 BUY = Buenas oportunidades (UK, Canadá)
- 10-20 BUY = Oportunidades limitadas
- < 10 BUY = Considerar otros mercados
```

#### B. Proporción de Oportunidades
```
Métrica: % de acciones con señal BUY

Cálculo:
% BUY = (# BUY / Total screened) × 100

Interpretación:
- > 15% = Mercado muy favorable (raro)
- 10-15% = Buen mercado
- 5-10% = Normal
- < 5% = Mercado difícil (bear market o valuaciones altas)

IMPORTANTE: Preferir calidad sobre cantidad
Mejor: 20 BUY con Quality 80+
vs 50 BUY con Quality 60-70
```

#### C. Calidad Promedio del Mercado
```
Métrica: Quality Score promedio de todas las acciones screened

Interpretación:
- > 70 = Mercado de alta calidad (US, Japón)
- 60-70 = Calidad buena (UK, Canadá, Alemania)
- 50-60 = Calidad media (India, Brasil)
- < 50 = Calidad baja (evitar)

Por qué importa:
- Calidad alta = empresas resilientes en bear markets
- Calidad baja = alto riesgo de quiebras/fraude
```

#### D. Guardrails Rojos (Red Flags)
```
Métrica: % de acciones con guardrails ROJO

Guardrails críticos:
- Altman Z < 1.8 (riesgo quiebra)
- Beneish M > -1.78 (manipulación)
- Net Share Issuance > 10% (dilución)

Interpretación:
- < 10% ROJO = Mercado saludable
- 10-20% ROJO = Normal
- 20-30% ROJO = Mercado con problemas
- > 30% ROJO = EVITAR (crisis contable generalizada)
```

---

### Nivel 3: Análisis Técnico (Señales de Timing)

#### A. Technical Signal Distribution
```
Métrica: Distribución de BUY / HOLD / SELL

Ideal para entrar:
- > 30% BUY signals
- < 20% SELL signals
- Resto HOLD

Red flag:
- > 50% SELL signals = Bear market técnico
- < 10% BUY signals = Falta momentum
```

#### B. Market State Predominante
```
Métrica: % de acciones en cada estado

Estados positivos:
- POWER_TREND ⚡ (mantener, dejar correr)
- BLUE_SKY_ATH ⭐ (breakout, sin resistencia)
- ENTRY_BREAKOUT 🚪 (inicio tendencia)

Estados neutrales:
- PULLBACK_FLAG 🏴 (pullback saludable)
- CHOPPY_SIDEWAYS ↔️ (esperar definición)

Estados negativos:
- DOWNTREND ▼ (evitar)
- PARABOLIC_CLIMAX 🚀 (sobreextendido, esperar)

Interpretación:
- > 40% estados positivos = Buen timing para entrar
- > 40% DOWNTREND = Mercado bajista, ESPERAR
```

#### C. Momentum Multi-Timeframe
```
Métrica: % de acciones con momentum STRONG/MIXED/WEAK

Momentum Consistency:
- STRONG: 4/4 timeframes positivos (12m, 6m, 3m, 1m)
- MIXED: 2-3 timeframes positivos
- WEAK: 0-1 timeframes positivos

Interpretación:
- > 30% STRONG = Tendencia alcista establecida
- > 50% WEAK = Mercado sin dirección
```

#### D. Overextension Risk
```
Métrica: % de acciones con overextension > 6/10

Overextension = Precio muy alejado de MA50

Interpretación:
- < 20% overextended = Saludable
- 20-40% = Normal en bull markets
- > 40% = Mercado sobreextendido (esperar pullback)
```

---

## 🎯 Framework de Evaluación

### Opportunity Score Formula

Combinar las 3 dimensiones en un score único:

```
Opportunity Score (0-100) =
    40% × BUY_Ratio_Score +
    30% × Quality_Score +
    30% × Technical_Score

Donde:
    BUY_Ratio_Score = (% BUY / 15%) × 100  [cap at 100]
    Quality_Score = Avg Quality Score (0-100)
    Technical_Score = (
        40% × % Technical BUY +
        30% × % Positive Momentum +
        30% × % Non-Downtrend States
    )
```

### Interpretación del Opportunity Score

```
90-100: EXCELENTE
- Muchas oportunidades BUY (>15%)
- Alta calidad promedio (>75)
- Señales técnicas muy favorables
- Acción: PRIORIZAR este mercado

75-89: MUY BUENO
- Buenas oportunidades (10-15% BUY)
- Calidad alta (65-75)
- Técnicas favorables
- Acción: Explorar en detalle

60-74: BUENO
- Oportunidades moderadas (5-10% BUY)
- Calidad decente (60-65)
- Técnicas mixtas
- Acción: Considerar selectivamente

45-59: REGULAR
- Pocas oportunidades (<5% BUY)
- Calidad media (50-60)
- Técnicas débiles
- Acción: Solo si hay tesis específica

< 45: EVITAR
- Muy pocas oportunidades
- Calidad baja
- Señales técnicas negativas
- Acción: Esperar mejores condiciones
```

---

## 🔍 Interpretación de Resultados

### Escenarios Típicos

#### Escenario 1: US (Estados Unidos)
```
Características esperadas:
- Total stocks: 3000-5000
- BUY signals: 200-500 (10-15%)
- Quality avg: 70-75
- Large caps: 500-800
- Liquidez: Muy alta (>50% con vol >$5M)
- Opportunity Score: 80-90

Pros:
✅ Muchas oportunidades
✅ Alta calidad
✅ Liquidez excelente
✅ Datos completos (transcripts, insider)

Contras:
⚠️ Valuaciones altas (menor margen de seguridad)
⚠️ Competencia (mercado eficiente)
```

#### Escenario 2: Mercados Emergentes (India, Brasil)
```
Características esperadas:
- Total stocks: 500-1500
- BUY signals: 50-150 (10-15%)
- Quality avg: 50-60 (menor que US)
- Large caps: 50-100
- Liquidez: Media (20-30%)
- Opportunity Score: 60-75

Pros:
✅ Valuaciones atractivas
✅ Growth potential alto
✅ Menor competencia

Contras:
⚠️ Calidad promedio menor
⚠️ Liquidez limitada
⚠️ Riesgo político/regulatorio
⚠️ Datos incompletos
⚠️ Guardrails rojos más frecuentes
```

#### Escenario 3: Europa Desarrollada (UK, Alemania)
```
Características esperadas:
- Total stocks: 500-2000
- BUY signals: 50-200 (8-12%)
- Quality avg: 65-70
- Large caps: 100-300
- Liquidez: Buena (30-40%)
- Opportunity Score: 70-80

Pros:
✅ Balance calidad-valor
✅ Liquidez adecuada
✅ Estabilidad regulatoria
✅ Diversificación sectorial

Contras:
⚠️ Crecimiento económico lento
⚠️ Menor data (transcripts limitados)
```

#### Escenario 4: Asia Desarrollada (Japón, Hong Kong)
```
Características esperadas:
- Total stocks: 1000-2000
- BUY signals: 100-300 (10-15%)
- Quality avg: 60-68
- Large caps: 200-400
- Liquidez: Media-Alta
- Opportunity Score: 70-80

Pros:
✅ Valuaciones atractivas (Japón)
✅ Tech giants (Hong Kong: Alibaba, Tencent)
✅ Acceso a growth Asia

Contras:
⚠️ Barreras de idioma
⚠️ Accounting standards diferentes
⚠️ Riesgo geopolítico (Hong Kong-China)
```

---

## 🧩 Estrategia de Priorización

### Paso 1: Screening Inicial (Rápido)
```
Ejecutar Nivel 1 en TODOS los países (5 min)
↓
Eliminar países con red flags:
- < 100 acciones disponibles
- < 10% liquidez alta
- > 60% mercado en DOWNTREND
↓
Identificar Top 3-5 países por Opportunity Score
```

### Paso 2: Análisis Profundo (30-60 min c/u)
```
Para cada Top 3-5:
↓
Ejecutar screener completo (Nivel 2)
↓
Revisar:
- Lista completa de BUY signals
- Distribución sectorial
- Top 10 oportunidades por score
↓
Validar con análisis técnico (Nivel 3)
```

### Paso 3: Selección Final
```
Criterios de decisión:
1. ¿Hay al menos 10 BUY signals de calidad (Quality > 70)?
2. ¿El mercado está en bull/neutral (no bear)?
3. ¿La liquidez es adecuada para mi tamaño de posición?
4. ¿Tengo ventaja informativa en este mercado?
↓
Seleccionar 2-3 mercados principales
↓
Diversificar portfolio entre ellos
```

---

## ⚠️ Limitaciones y Consideraciones

### Limitaciones del Análisis

**1. Data Quality Varía por País**
```
Datos completos (US):
- Earnings transcripts ✅
- Insider trading ✅
- Segment data ✅
- Real-time prices ✅

Datos limitados (Emergentes):
- Earnings transcripts ❌
- Insider trading ❌
- Segment data ⚠️ Parcial
- Delayed quotes ⚠️
```

**2. Accounting Standards Diferentes**
```
US: GAAP
Europe: IFRS
Japan: J-GAAP
China: Modified IFRS

⚠️ Las métricas no son 100% comparables
⚠️ Altman Z, Beneish calibrados para US GAAP
⚠️ Ajustes necesarios para otros países
```

**3. Factores No Capturados**
```
❌ Riesgo político
❌ Riesgo de divisa (FX)
❌ Barreras regulatorias
❌ Impuestos locales
❌ Costos de transacción (comisiones)
❌ Accesibilidad (algunos mercados requieren cuentas especiales)
```

### Consideraciones Prácticas

**1. Costos de Transacción**
```
US: Comisiones bajas ($0-5 por trade)
International: Comisiones altas ($15-50 por trade)

⚠️ Para portfolios < $50k, concentrarse en 1-2 mercados
⚠️ Para portfolios > $100k, diversificar en 3-4 mercados
```

**2. Riesgo de Divisa**
```
Invertir en mercados extranjeros = exposición FX

Ejemplo:
- Compras acción UK a £100
- Acción sube 10% → £110
- Pero GBP/USD cae 8%
- Return en USD = +2% (no 10%)

Mitigación:
- Hedge FX (costoso)
- Diversificar divisas (natural hedge)
- Aceptar volatilidad FX
```

**3. Accesibilidad**
```
Fácil acceso (ADRs en US):
✅ UK, Canadá
✅ Grandes empresas de HK, JP, BR

Difícil acceso:
❌ India NSE (requiere cuenta local)
❌ Small caps extranjeros
```

---

## 🎓 Conclusiones y Recomendaciones

### Framework de Decisión Final

```
┌─────────────────────────────────────┐
│  PASO 1: Screening Rápido           │
│  → Identificar top 5 países         │
│  → 5 minutos por país               │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│  PASO 2: Análisis Fundamental       │
│  → Screener completo en top 3       │
│  → 30-60 min por país               │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│  PASO 3: Validación Técnica         │
│  → Technical signals                │
│  → Market timing                    │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│  PASO 4: Selección Final            │
│  → 2-3 mercados principales         │
│  → Portfolio diversificado          │
└─────────────────────────────────────┘
```

### Reglas de Oro

1. **Calidad sobre Cantidad**: Preferir 10 oportunidades de Quality 80+ que 50 de Quality 60
2. **No Pelear con la Tendencia**: Evitar países en DOWNTREND técnico
3. **Liquidez es Clave**: No comprar acciones con volumen < $2M diario
4. **Diversificar Inteligentemente**: 2-3 mercados, no 8 (complejidad mata)
5. **Validar con Técnico**: Score fundamental alto NO garantiza buen timing

### Matriz de Decisión Simplificada

```
                    │ Quality  │ Value   │ Technical │ Liquidez │ Acción
                    │ Avg      │ Avg     │ BUY %     │ Alta %   │
────────────────────┼──────────┼─────────┼───────────┼──────────┼────────
EXCELENTE (90+)     │ > 75     │ > 70    │ > 30%     │ > 40%    │ ENTRAR
MUY BUENO (75-89)   │ 65-75    │ 60-70   │ 20-30%    │ 30-40%   │ EXPLORAR
BUENO (60-74)       │ 60-65    │ 50-60   │ 10-20%    │ 20-30%   │ SELECTIVO
REGULAR (45-59)     │ 50-60    │ 40-50   │ 5-10%     │ 10-20%   │ CUIDADO
EVITAR (< 45)       │ < 50     │ < 40    │ < 5%      │ < 10%    │ SKIP
```

---

**Próximos Pasos**:
1. Implementar Nivel 1 (Quick Screening)
2. Validar con datos reales de FMP
3. Refinar thresholds basados en resultados
4. Ejecutar análisis completo en top 3 países
5. Documentar resultados y ajustar estrategia

---

**Documento creado**: 2026-01-25
**Versión**: 1.0 - Marco Teórico
**Siguiente**: Implementación práctica
