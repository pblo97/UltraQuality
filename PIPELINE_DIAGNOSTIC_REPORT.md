# 🔍 UltraQuality Pipeline Diagnostic Report

**Generated:** 2025-12-25
**Purpose:** Analyze if quality/value thresholds and technical components are working correctly

---

## 📊 EXECUTIVE SUMMARY

### ✅ What IS Working:
1. **Thresholds ARE being used** - They filter before technical analysis
2. **Quality weight (70/30) IS working** - Composite score uses it correctly
3. **Technical components are NOT redundant** - Each serves different purpose

### ⚠️ Potential Issues Found:
1. **Hidden filter**: Stocks with `composite < 45` NEVER reach technical analysis
2. **Quality weight is FIXED** - Not adjustable in UI (only in settings.yaml)
3. **Technical_score may confuse users** - Looks like duplicate of momentum/volume but it's the SUM

---

## 🔄 COMPLETE PIPELINE FLOW

```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: FUNDAMENTAL SCORING (src/screener/scoring.py)         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐      ┌──────────────┐                        │
│  │ Value Score  │      │Quality Score │                        │
│  │   0-100      │      │   0-100      │                        │
│  └──────┬───────┘      └──────┬───────┘                        │
│         │                     │                                 │
│         │  30% weight         │  70% weight                     │
│         └─────────┬───────────┘                                 │
│                   ▼                                              │
│         ┌──────────────────┐                                    │
│         │ Composite Score  │                                    │
│         │     0-100        │                                    │
│         └─────────┬────────┘                                    │
│                   │                                              │
│                   ▼                                              │
│         ┌──────────────────────────────────┐                   │
│         │ DECISION LOGIC (Thresholds)      │                   │
│         ├──────────────────────────────────┤                   │
│         │ • Composite >= 80  → BUY (AMBAR OK)                  │
│         │ • Quality >= 85 AND Comp >= 60 → BUY (exceptional)   │
│         │ • Composite >= 75 AND AMBAR → BUY                    │
│         │ • Composite >= 70 AND VERDE → BUY                    │
│         │ • Composite >= 45 → MONITOR                          │
│         │ • Composite < 45  → AVOID ❌                         │
│         └─────────┬────────────────────────┘                   │
│                   │                                              │
└───────────────────┼──────────────────────────────────────────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │ CRITICAL FILTER:     │
         │ Only BUY + MONITOR   │
         │ pass to Technical    │
         └──────────┬───────────┘
                    │
                    │ AVOID stocks STOP HERE ❌
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: TECHNICAL ANALYSIS (src/screener/technical/analyzer.py)│
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Components (each contributes to total_score):                  │
│                                                                  │
│  ┌────────────────┬─────────────────────────┐                  │
│  │ momentum_scores│ Multi-timeframe (12m/6m/3m/1m)             │
│  │     ~30-40 pts │ + consistency bonus                        │
│  ├────────────────┼─────────────────────────┤                  │
│  │ risk_score     │ Sharpe ratio (risk-adjusted returns)       │
│  │     ~10-15 pts │                                            │
│  ├────────────────┼─────────────────────────┤                  │
│  │ sector_score   │ Outperformance vs sector ETF               │
│  │     ~5-10 pts  │                                            │
│  ├────────────────┼─────────────────────────┤                  │
│  │ market_score   │ Outperformance vs SPY                      │
│  │     ~5-10 pts  │                                            │
│  ├────────────────┼─────────────────────────┤                  │
│  │ trend_score    │ Price vs MA50/MA200 + Golden Cross         │
│  │     ~10-15 pts │                                            │
│  ├────────────────┼─────────────────────────┤                  │
│  │ volume_score   │ Accumulation/Distribution pattern          │
│  │     ~5 pts     │                                            │
│  ├────────────────┼─────────────────────────┤                  │
│  │regime_adjustment│ BULL market bonus / BEAR penalty          │
│  │     ±10 pts    │                                            │
│  └────────────────┴─────────────────────────┘                  │
│                   │                                              │
│                   ▼                                              │
│         ┌──────────────────┐                                    │
│         │ Technical Score  │  SUM of all components             │
│         │     0-100        │  (clamped to 0-100)                │
│         └─────────┬────────┘                                    │
│                   │                                              │
│                   ▼                                              │
│         ┌──────────────────────────────────┐                   │
│         │ SIGNAL GENERATION                │                   │
│         ├──────────────────────────────────┤                   │
│         │ • Score >= 75 AND UPTREND → BUY  │                   │
│         │ • Score >= 50 → HOLD              │                   │
│         │ • Score < 50  → SELL              │                   │
│         └───────────────────────────────────┘                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔢 CURRENT THRESHOLD CONFIGURATION

**File:** `settings.yaml`

### Fundamental Scoring:
```yaml
scoring:
  weight_value: 0.30        # 30% Value (reasonable price)
  weight_quality: 0.70      # 70% Quality (exceptional companies with moats)
  exclude_reds: true        # Block ROJO guardrails

  # Decision Thresholds:
  threshold_monitor: 45     # Composite >= 45 → MONITOR
  threshold_buy: 65         # Not actually used (hardcoded to 70 for VERDE)
  threshold_buy_amber: 80   # Composite >= 80 → BUY (allows AMBAR)
  threshold_buy_quality_exceptional: 85  # Quality >= 85 → BUY (even if composite lower)
```

### Technical Scoring:
```python
# Hardcoded in analyzer.py (NOT in settings.yaml)
if score >= 75 and is_uptrend:
    return 'BUY'
elif score >= 50:
    return 'HOLD'
else:
    return 'SELL'
```

---

## ⚠️ CRITICAL FINDING: Hidden Filter

### **Stocks with `composite < 45` NEVER reach Technical Analysis**

**Location:** `run_screener.py:7576`
```python
df_technical = df[df['decision'].isin(['BUY', 'MONITOR'])].copy()
```

**Impact:**
- If `composite_score < 45` → `decision = 'AVOID'`
- AVOID stocks are **excluded** from technical analysis
- You lose potential "momentum upgrade" opportunities

**Example Scenario:**
```
Stock: XYZ
├── Composite Score: 42 (below 45 threshold)
├── Decision: AVOID
└── Technical Analysis: ❌ NEVER RUN

Even if XYZ has:
- Momentum: +50% (12m)
- Trend: UPTREND
- Volume: ACCUMULATION
→ Still blocked from technical analysis!
```

### **Is This a Problem?**

**Philosophy Question:**
- **Current approach**: "Only analyze technically what is fundamentally sound"
- **Alternative approach**: "Let momentum upgrade weak fundamentals"

**Recommendation:**
- If you want to catch "momentum plays" with weak fundamentals, change to:
  ```python
  # Option 1: Analyze ALL stocks
  df_technical = df.copy()

  # Option 2: Only block true garbage (< 30)
  df_technical = df[df['composite_0_100'] >= 30].copy()
  ```

---

## 📊 TECHNICAL SCORE vs COMPONENTS

### **Are They Redundant?**

**NO** - This is a common misconception. Here's why:

### Technical_Score (0-100):
```
= momentum_scores + risk_score + sector_score + market_score +
  trend_score + volume_score + regime_adjustment
```

### Individual Components (shown in filters):
- **Trend**: UPTREND/DOWNTREND (categorical) - ONE component of the score
- **Volume Profile**: ACCUMULATION/DISTRIBUTION (categorical) - ONE component
- **Momentum Consistency**: HIGH/LOW (categorical) - Quality metric, not score

### **Why Show Both?**

1. **Technical_Score** = Summary metric for sorting/filtering
2. **Components** = Explain WHY the score is what it is

**Example:**
```
Stock: AAPL
├── Technical Score: 85 (HIGH)
│
└── Why? (Components)
    ├── Trend: UPTREND (+15 pts)
    ├── Volume: ACCUMULATION (+5 pts)
    ├── Momentum 12m: +45% (+35 pts)
    ├── Sector: LEADING (+8 pts)
    ├── Sharpe: 1.8 (+12 pts)
    └── Regime: BULL (+10 pts)
    ────────────────────────
    Total: 85 pts
```

**NOT Redundant** - One is the SUM, the others are the ADDENDS.

---

## 🎛️ QUALITY WEIGHT USAGE

### **Is the 70/30 weight working?**

**YES** ✅ - Here's the proof:

**Location:** `src/screener/scoring.py:211-215`
```python
# Composite calculation
df['composite_0_100'] = (
    self.w_value * df['value_score_0_100'] +      # 0.30
    self.w_quality * df['quality_score_0_100']    # 0.70
)
```

### **Example Calculation:**
```
Stock: GOOGL
├── Quality Score: 85
├── Value Score: 50
│
└── Composite = (0.30 × 50) + (0.70 × 85)
              = 15 + 59.5
              = 74.5
```

**Vs if weights were 50/50:**
```
Composite = (0.50 × 50) + (0.50 × 85) = 67.5  ❌ Different!
```

### **Can You Adjust It in the UI?**

**NO** ❌ - The weight is **only** configurable in `settings.yaml`.

There is **no sidebar slider** to change quality/value weight dynamically.

**Recommendation:**
If you want UI control, I can add:
```python
st.sidebar.slider("Quality Weight", 0.0, 1.0, 0.7, 0.05)
```

---

## 🔍 DIAGNOSTICS: Is Anything Blocking Your Stocks?

### Run This Analysis:

1. **Check how many stocks get AVOID:**
   ```python
   df_all = st.session_state['results']

   avoid_count = len(df_all[df_all['decision'] == 'AVOID'])
   buy_count = len(df_all[df_all['decision'] == 'BUY'])
   monitor_count = len(df_all[df_all['decision'] == 'MONITOR'])

   print(f"BUY: {buy_count}")
   print(f"MONITOR: {monitor_count}")
   print(f"AVOID: {avoid_count} ❌ Never reach technical")
   ```

2. **Check score distribution:**
   ```python
   print(df_all['composite_0_100'].describe())

   # Count stocks below threshold
   below_45 = len(df_all[df_all['composite_0_100'] < 45])
   print(f"{below_45} stocks have composite < 45 (blocked)")
   ```

3. **Check if quality weight matters:**
   ```python
   # Current composite (70/30)
   df_all['composite_current'] = df_all['composite_0_100']

   # Hypothetical 50/50
   df_all['composite_5050'] = (
       0.5 * df_all['value_score_0_100'] +
       0.5 * df_all['quality_score_0_100']
   )

   # Compare decision changes
   df_all['decision_5050'] = df_all['composite_5050'].apply(
       lambda x: 'BUY' if x >= 70 else ('MONITOR' if x >= 45 else 'AVOID')
   )

   changes = df_all[df_all['decision'] != df_all['decision_5050']]
   print(f"{len(changes)} stocks would have DIFFERENT decision with 50/50 weight")
   ```

---

## 📋 SUMMARY OF FINDINGS

### ✅ Working Correctly:
1. **Quality weight (70/30)** - Applied in composite score calculation
2. **Thresholds (45/70/80/85)** - Used in decision logic
3. **Technical components** - Each serves unique purpose, not redundant
4. **Technical score** - Proper aggregation of all components

### ⚠️ Potential Issues:
1. **Hidden filter at composite < 45** - Blocks weak fundamentals from technical
2. **No UI control for weights** - Must edit settings.yaml to change
3. **threshold_buy (65) not used** - Hardcoded to 70 for VERDE in code
4. **Technical threshold (75) hardcoded** - Not in settings.yaml

### 💡 Recommendations:

**IF you want to catch momentum plays with weak fundamentals:**
```python
# Change run_screener.py:7576 from:
df_technical = df[df['decision'].isin(['BUY', 'MONITOR'])].copy()

# To:
df_technical = df[df['composite_0_100'] >= 30].copy()  # Lower threshold
# This allows AVOID stocks (composite 30-44) to reach technical analysis
```

**IF you want UI control over quality/value weight:**
- Add sidebar slider to adjust weight dynamically
- Recalculate composite score on-the-fly

**IF you want consistent thresholds:**
- Move technical thresholds (75/50) to settings.yaml
- Remove hardcoded values from analyzer.py

---

## 🎯 Action Items

**Priority 1 (Critical):**
- [ ] Decide: Should AVOID stocks (< 45 composite) reach technical analysis?
- [ ] If YES: Lower the filter threshold in run_screener.py

**Priority 2 (Enhancement):**
- [ ] Add UI slider for quality/value weight adjustment
- [ ] Move technical thresholds to settings.yaml for consistency

**Priority 3 (Nice to have):**
- [ ] Add diagnostic widget showing filter impact in real-time
- [ ] Show "X stocks blocked by composite < 45" warning

---

**End of Report**
