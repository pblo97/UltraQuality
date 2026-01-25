# 📖 Cómo Usar la Funcionalidad Multi-País Existente

## 🎯 Lo Que Ya Existe

El sistema **YA TIENE** soporte completo para analizar múltiples países:

### ✅ Funcionalidades Implementadas

1. **Selector de 54 Países** en `run_screener.py` (líneas 2141-2224)
   - Américas: US, CA, MX, BR, CL, AR, CO, PE, etc.
   - Europa: UK, DE, FR, ES, IT, CH, NL, etc.
   - Asia: JP, CN, HK, IN, KR, SG, TW, etc.
   - Medio Oriente & África: SA, AE, ZA, EG, etc.
   - Oceanía: AU, NZ

2. **Filtros Dinámicos por País** (líneas 2271-2356)
   - Cada país tiene umbrales predefinidos de Market Cap y Volumen
   - Ajustados a la realidad de cada mercado

3. **Conversión de Divisas** (líneas 3062-3114)
   - Convierte precios locales a USD
   - Soporta 20+ monedas (KRW, JPY, HKD, CNY, EUR, GBP, etc.)

4. **Análisis Técnico Multi-País**
   - `analyzer.py` acepta parámetro `country` (línea 93)
   - Funciona con acciones internacionales

5. **Configuración por País**
   - `settings.yaml` permite especificar:
     ```yaml
     universe:
       countries: ["US"]  # ISO country codes
       exchanges: ["NYSE", "NASDAQ"]
       min_market_cap: 2_000_000_000
       min_avg_dollar_vol_3m: 5_000_000
     ```

---

## 🔧 Cómo Analizar un País Específico

### Opción 1: Usando Streamlit UI

```bash
# 1. Iniciar la app
streamlit run run_screener.py

# 2. En el sidebar:
#    - Market Selection & Filters
#    - Seleccionar país del dropdown (ej: "India")
#    - Ajustar Min Market Cap y Min Volume
#    - Click "Run Screener"

# 3. Resultados se mostrarán en la UI
# 4. Descargar CSV o Excel con los resultados
```

### Opción 2: Usando CLI (Modificando settings.yaml)

```bash
# 1. Editar settings.yaml
nano settings.yaml

# 2. Cambiar la sección universe:
universe:
  countries: ["IN"]  # India
  exchanges: []      # Dejar vacío para usar country
  min_market_cap: 500_000_000  # $500M (menor que US)
  min_avg_dollar_vol_3m: 2_000_000  # $2M
  top_k: 200  # Menos que US

# 3. Cambiar output path para no sobreescribir
output:
  csv_path: "./data/india_screener_results.csv"

# 4. Ejecutar
python src/screener/orchestrator.py
```

### Opción 3: Programáticamente

```python
from src.screener.orchestrator import ScreenerPipeline
import yaml

# Cargar config base
with open('settings.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Modificar para país específico
config['universe']['countries'] = ['JP']  # Japón
config['universe']['min_market_cap'] = 1_000_000_000
config['output']['csv_path'] = './data/japan_results.csv'

# Guardar config temporal
with open('temp_japan_config.yaml', 'w') as f:
    yaml.dump(config, f)

# Ejecutar screener
pipeline = ScreenerPipeline('temp_japan_config.yaml')
output_csv = pipeline.run()

print(f"Resultados guardados en: {output_csv}")
```

---

## 📊 Análisis de Resultados por País

Una vez ejecutado el screener para un país, el CSV contiene:

```
ticker, name, country, exchange, sector, industry,
marketCap, avgDollarVol_3m, freeFloat,

# Scores
value_score_0_100, quality_score_0_100, composite_0_100,

# Decisión
decision, guardrail_status, guardrail_reasons,

# Technical (si está habilitado)
technical_signal, technical_score, momentum_consistency,
trend, volume_profile, market_state

# + todas las métricas fundamentales
```

### Análisis Manual con Pandas

```python
import pandas as pd

# Cargar resultados
df = pd.read_csv('./data/india_results.csv')

# ¿Cuántas oportunidades BUY?
buy_count = len(df[df['decision'] == 'BUY'])
print(f"Oportunidades BUY: {buy_count}")

# Calidad promedio
avg_quality = df['quality_score_0_100'].mean()
print(f"Calidad promedio: {avg_quality:.1f}")

# Top 10 por composite score
top10 = df.nlargest(10, 'composite_0_100')[['ticker', 'name', 'composite_0_100', 'decision']]
print(top10)

# Distribución de sectores
sector_dist = df['sector'].value_counts()
print(sector_dist)

# Señales técnicas (si disponible)
if 'technical_signal' in df.columns:
    tech_dist = df['technical_signal'].value_counts()
    print(f"\nSeñales técnicas:")
    print(tech_dist)
```

---

## 🔄 Comparar Múltiples Países

### Flujo Manual (Lo Que Existe Ahora)

```bash
# 1. Ejecutar screener para País A
# - Modificar settings.yaml: countries: ["US"]
# - Cambiar output: csv_path: "./data/us_results.csv"
# - Ejecutar: python src/screener/orchestrator.py

# 2. Ejecutar screener para País B
# - Modificar settings.yaml: countries: ["IN"]
# - Cambiar output: csv_path: "./data/india_results.csv"
# - Ejecutar: python src/screener/orchestrator.py

# 3. Ejecutar screener para País C
# - Repetir...

# 4. Comparar resultados manualmente
python
>>> import pandas as pd
>>> us = pd.read_csv('./data/us_results.csv')
>>> india = pd.read_csv('./data/india_results.csv')
>>>
>>> print(f"US BUY: {len(us[us['decision']=='BUY'])}")
>>> print(f"India BUY: {len(india[india['decision']=='BUY'])}")
>>>
>>> print(f"US Avg Quality: {us['quality_score_0_100'].mean():.1f}")
>>> print(f"India Avg Quality: {india['quality_score_0_100'].mean():.1f}")
```

### Limitaciones del Flujo Manual

❌ Requiere ejecutar screener múltiples veces (lento)
❌ Hay que modificar config manualmente cada vez
❌ Comparación manual de CSVs
❌ No hay reporte consolidado
❌ Propenso a errores (olvidar cambiar output path → sobreescribir)

---

## 💡 Lo Que FALTA (Oportunidades de Mejora)

### 1. Script de Análisis Multi-País Automatizado

**Lo que existe**: Screener puede analizar 1 país a la vez
**Lo que falta**: Script que:
- Ejecute screener para N países automáticamente
- Guarde resultados separados por país
- Genere reporte comparativo

### 2. Dashboard de Comparación de Países

**Lo que existe**: Resultados individuales por país
**Lo que falta**: Vista comparativa que muestre:
- Ranking de países por oportunidades
- Métricas lado a lado
- Identificación de mejores mercados

### 3. Screening Rápido (Quick Mode)

**Lo que existe**: Screener completo (30-60 min por país)
**Lo que falta**: Modo rápido que:
- Use solo métricas de mercado agregadas
- Identifique top 3-5 países en 5 minutos
- Luego ejecute screener completo solo en esos

### 4. Métricas de País Agregadas

**Lo que existe**: Métricas por acción individual
**Lo que falta**: Métricas a nivel país:
- % de acciones con BUY
- Calidad promedio del mercado
- Liquidez agregada
- Momentum general

---

## 🎯 Propuesta: Usar lo Existente de Forma Inteligente

### Enfoque Pragmático (Sin Código Nuevo)

**Paso 1: Quick Test con Streamlit UI**
```bash
# Probar 3 países manualmente en UI:
# 1. US (baseline)
# 2. India (emerging market)
# 3. UK (developed international)

# Anotar para cada uno:
# - # Total stocks
# - # BUY signals
# - Avg Quality Score
# - Top 3 stocks
```

**Paso 2: Análisis Profundo del Top 1**
```bash
# El que muestre mejores métricas, ejecutar screener completo
# Descargar CSV completo
# Analizar distribución sectorial
# Revisar top 20 oportunidades
```

**Paso 3: Validación Técnica**
```bash
# Para top 5-10 stocks del país ganador:
# Usar "Custom Deep Dive Analysis"
# Validar señales técnicas
# Confirmar timing de entrada
```

### Enfoque Automatizado (Con Scripts Nuevos)

**Solo si el enfoque manual es insuficiente:**

1. **`quick_country_scan.py`**: Screening rápido de los 8 mercados principales (5 min)
2. **`analyze_country_opportunities.py`**: Screener completo para top 3 (30-60 min c/u)
3. **`compare_country_results.py`**: Generar reporte comparativo

---

## ❓ Preguntas para Decidir Próximos Pasos

### Para el Usuario

1. **¿Ya probaste el screener con diferentes países en la UI?**
   - ¿Qué países te interesan?
   - ¿Viste diferencias significativas?

2. **¿Cuál es tu objetivo específico?**
   - A) Identificar top 3 países para explorar profundamente
   - B) Comparar países que ya conoces (ej: US vs India)
   - C) Screening global amplio (50+ países)

3. **¿Cuánto tiempo puedes dedicar?**
   - Si tienes 1 hora → Enfoque manual con UI (3 países)
   - Si tienes 3+ horas → Script automatizado (8+ países)

4. **¿Qué métricas te importan más?**
   - Número de oportunidades (cantidad)
   - Calidad promedio (quality score)
   - Señales técnicas favorables (momentum)
   - Liquidez (volume)

---

## 🚀 Recomendación Inmediata

### Opción A: Prueba Rápida (15 minutos)

```bash
# 1. Abrir Streamlit
streamlit run run_screener.py

# 2. Probar 3 países:
#    - US (min_mcap=$2B, min_vol=$5M)
#    - India (min_mcap=$500M, min_vol=$2M)
#    - UK (min_mcap=$1B, min_vol=$3M)

# 3. Para cada uno, anotar:
#    Total Stocks, BUY Signals, Avg Quality

# 4. Identificar cuál se ve más prometedor

# 5. Descargar CSV del ganador y analizarlo en detalle
```

### Opción B: Análisis Completo (2-3 horas)

```bash
# Ejecutar los scripts que creé:
# (Si decides que el enfoque manual no es suficiente)

# 1. Quick scan (5 min)
python quick_country_opportunities.py

# 2. Ver reporte de top 3 países

# 3. Análisis profundo de esos 3 (30-60 min c/u)
# - Modificar analyze_country_opportunities.py
# - Ejecutar solo para top 3 en lugar de todos

# 4. Reporte final con comparación
```

---

## 📋 Próxima Acción

**¿Qué quieres hacer?**

1. **Probar manualmente** 2-3 países en UI primero → Te guío paso a paso
2. **Ejecutar scripts automatizados** → Los que creé están listos
3. **Ajustar la teoría** → Refinar métricas en TEORIA_OPORTUNIDADES_PAISES.md
4. **Otra cosa** → Dime qué necesitas

---

**Documento creado**: 2026-01-25
**Propósito**: Documentar funcionalidad existente antes de crear código nuevo
**Próximo paso**: Decisión del usuario sobre enfoque (manual vs automatizado)
