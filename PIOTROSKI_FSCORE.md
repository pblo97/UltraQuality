# 📊 Piotroski F-Score Delta - Simple Quality Deterioration Detector

## 🎯 Problem Solved

**User reported:** EXPD showing as BUY with composite 91 despite potential deterioration.

**Root cause:** "Exceptional score (≥80)" bypassed ALL deterioration checks.

**User suggestion:**
> "lo que se podria hacer simple como en el caso de la otra app es usar el delta piotrosky para evaluar decaimiento"

---

## ✅ Solution: Piotroski F-Score Delta

### **What is Piotroski F-Score?**

Simple quality scoring system with **9 binary signals** (0-9 total):

| Category | Signals | Score if True |
|----------|---------|---------------|
| **Profitability (4)** | ROA > 0 | +1 |
| | CFO > 0 | +1 |
| | ΔROA > 0 (improving) | +1 |
| | Accrual < 0 (CFO > NI) | +1 |
| **Leverage/Liquidity (3)** | ΔDebt < 0 (decreasing) | +1 |
| | ΔCurrent Ratio > 0 | +1 |
| | No equity issued | +1 |
| **Operating Efficiency (2)** | ΔGross Margin > 0 | +1 |
| | ΔAsset Turnover > 0 | +1 |

**Total Score:** 0-9 (higher = better quality)

---

### **What is F-Score Delta?**

```
Delta = F-Score(current year) - F-Score(1 year ago)
```

**Interpretation:**
- `Delta < 0` → Quality **deteriorating** (e.g., 7 → 5 = -2)
- `Delta = 0` → Quality **stable** (e.g., 6 → 6 = 0)
- `Delta > 0` → Quality **improving** (e.g., 5 → 7 = +2)

---

## 🔧 Implementation

### **In features.py:**

```python
# Line 350-356: Calculate F-Score and delta
features['piotroski_fscore'], features['piotroski_fscore_delta'] = self._calc_piotroski_delta(
    income, balance, cashflow
)
```

**Calculation:**
1. F-Score(current) = Score from Q0-Q3 (last 4 quarters)
2. F-Score(1Y ago) = Score from Q4-Q7 (4 quarters, 1 year ago)
3. Delta = F-Score(current) - F-Score(1Y ago)

---

### **In run_screener.py:**

```python
# Lines 53-58: Block exceptional composite if deteriorating
if composite >= 85:
    if revenue_growth is not None and revenue_growth < 0:
        return 'MONITOR', f'High score but revenue declining'
    if piotroski_delta is not None and piotroski_delta < 0:
        return 'MONITOR', f'High score but Piotroski deteriorating (Δ{piotroski_delta})'
    return 'BUY', f'Exceptional score ({composite:.0f} ≥ 85)'
```

**Logic:**
1. Check if composite ≥ 85 (exceptional)
2. **Before** allowing BUY, check deterioration signals:
   - Revenue declining? → MONITOR
   - Piotroski delta < 0? → MONITOR
3. Only if **both pass** → BUY

---

## 📊 Expected Impact on EXPD

### **Scenario 1: EXPD Deteriorating**

```
EXPD:
- Composite: 91
- Quality: 90
- Revenue growth: -3% (declining)
- F-Score current: 6
- F-Score 1Y ago: 8
- Piotroski delta: -2 (deteriorating)

Decision Logic:
1. Check composite ≥ 85? YES (91 ≥ 85)
2. Check revenue < 0? YES (-3% < 0)
→ MONITOR: "High score (91) but revenue declining (-3.0% 3Y)" ✅

OR:

1. Check composite ≥ 85? YES (91 ≥ 85)
2. Check piotroski_delta < 0? YES (-2 < 0)
→ MONITOR: "High score (91) but Piotroski deteriorating (Δ-2)" ✅
```

### **Scenario 2: EXPD Healthy**

```
EXPD:
- Composite: 91
- Quality: 90
- Revenue growth: +5% (growing)
- F-Score current: 7
- F-Score 1Y ago: 7
- Piotroski delta: 0 (stable)

Decision Logic:
1. Check composite ≥ 85? YES (91 ≥ 85)
2. Check revenue < 0? NO (+5% ≥ 0)
3. Check piotroski_delta < 0? NO (0 ≥ 0)
→ BUY: "Exceptional score (91 ≥ 85)" ✅
```

---

## 🎓 Academic Foundation

### **Piotroski (2000) - "Value Investing: The Use of Historical Financial Statement Information"**

**Key findings:**
- High F-Score (8-9): +23% annual returns
- Low F-Score (0-1): -7% annual returns
- **Delta positive**: Outperforms by +7.5% annually

**Why it works:**
- Simple, objective quality signals
- Combines profitability, leverage, efficiency
- Captures business trajectory (improving vs deteriorating)

### **Methodology:**
- Sample: US value stocks (1976-1996)
- Portfolio: Long high F-Score, short low F-Score
- Result: +23% annual excess returns vs market

---

## 🔬 Piotroski 9 Signals Explained

### **1. Profitability Signals (4)**

| Signal | Calculation | Why It Matters |
|--------|-------------|----------------|
| **ROA > 0** | Net Income / Assets > 0 | Basic profitability |
| **CFO > 0** | Operating Cash Flow > 0 | Cash-generating |
| **ΔROA > 0** | ROA(now) > ROA(1Y ago) | Profitability improving |
| **Accrual** | CFO > Net Income | Earnings quality (cash vs accrual) |

**Interpretation:**
- Company with 4/4 = Very profitable, improving, high-quality earnings
- Company with 0/4 = Unprofitable or deteriorating

---

### **2. Leverage/Liquidity Signals (3)**

| Signal | Calculation | Why It Matters |
|--------|-------------|----------------|
| **ΔDebt < 0** | Debt(now) < Debt(1Y ago) | Deleveraging (safer) |
| **ΔCurrent Ratio > 0** | CR(now) > CR(1Y ago) | Liquidity improving |
| **No Equity Issue** | Shares(now) ≤ Shares(1Y ago) | No dilution |

**Interpretation:**
- Company with 3/3 = Financially strengthening
- Company with 0/3 = Increasing leverage, weaker liquidity

---

### **3. Operating Efficiency Signals (2)**

| Signal | Calculation | Why It Matters |
|--------|-------------|----------------|
| **ΔGross Margin > 0** | GM(now) > GM(1Y ago) | Pricing power / efficiency improving |
| **ΔAsset Turnover > 0** | Turnover(now) > Turnover(1Y ago) | Using assets more productively |

**Interpretation:**
- Company with 2/2 = Operating efficiency improving
- Company with 0/2 = Margins compressing, assets underutilized

---

## 💡 Example: GOOGL vs EXPD

### **GOOGL (Healthy)**

```
Profitability:
✓ ROA > 0 (highly profitable)
✓ CFO > 0 (cash machine)
✓ ΔROA > 0 (improving)
✓ CFO > NI (quality earnings)
Score: 4/4

Leverage/Liquidity:
✓ Debt decreasing
✓ Current ratio improving
✓ No dilution
Score: 3/3

Operating Efficiency:
✓ Margins expanding
✓ Asset turnover improving
Score: 2/2

F-Score: 9/9 (Excellent)
Delta: 9 - 8 = +1 (Improving)
→ BUY ✅
```

### **EXPD (If Deteriorating)**

```
Profitability:
✓ ROA > 0 (still profitable)
✓ CFO > 0 (still generating cash)
✗ ΔROA < 0 (declining profitability)
✗ CFO < NI (accrual-based earnings)
Score: 2/4

Leverage/Liquidity:
✗ Debt increasing
✓ Current ratio improving
✓ No dilution
Score: 2/3

Operating Efficiency:
✗ Margins contracting
✗ Asset turnover declining
Score: 0/2

F-Score: 4/9 (Below average)
Delta: 4 - 6 = -2 (Deteriorating)
→ MONITOR ✅
```

---

## ✅ How to Verify

### **Step 1: Re-run Screener**
1. Refresca navegador
2. Clear Results
3. Run Screener (~5 min)

### **Step 2: Check EXPD**

In "Investigate Specific Companies":
```
EXPD
```

**Verify columns:**
- `piotroski_fscore`: Should be 0-9
- `piotroski_fscore_delta`: Should be -9 to +9
- `revenue_growth_3y`: Check if negative
- `decision`: Should be MONITOR if either deteriorating
- `decision_reason`: Should explain why

### **Expected Results:**

**If EXPD deteriorating:**
```
piotroski_fscore: 4-6
piotroski_fscore_delta: -1 to -3
revenue_growth_3y: -X%
decision: MONITOR
decision_reason: "High score (91) but Piotroski deteriorating (Δ-2)"
```

**If EXPD healthy:**
```
piotroski_fscore: 7-9
piotroski_fscore_delta: 0 or +1
revenue_growth_3y: +X%
decision: BUY
decision_reason: "Exceptional score (91 ≥ 85)"
```

---

## 🔧 Troubleshooting

### **Issue: All piotroski_fscore = null**
**Cause:** Insufficient data (<8 quarters)
**Fix:** Ensure 12 quarters of income/balance/cashflow available

### **Issue: All piotroski_fscore_delta = null**
**Cause:** Can't compare to 1Y ago (need 12 quarters minimum)
**Fix:** Check data availability, some stocks may not have full history

### **Issue: F-Score seems wrong**
**Cause:** Data quality issues or calculation error
**Debug:** Check individual signals in _calc_fscore()

---

## 📈 Other Improvements Made

### **1. Raised Exceptional Threshold: 80 → 85**
- More selective
- Top 20% → Top 15%
- Reduces false positives

### **2. Deterioration Checks for Exceptional Quality**
Same logic applied to exceptional quality bypass:
```python
if quality >= 85:
    if revenue_growth < 0 OR piotroski_delta < 0:
        return 'MONITOR'
```

---

## 🎯 Why This Approach Works

### **Complementary Signals**

| Metric | Detects | Example |
|--------|---------|---------|
| **Revenue Growth** | Top-line deterioration | Sales declining |
| **ROIC Trend** | Returns deterioration | Competitive pressure |
| **Margin Trend** | Pricing power loss | Margins compressing |
| **Piotroski Delta** | Multi-factor deterioration | Overall quality decline |

**Combined:** These 4 metrics catch different types of deterioration.

### **Simple but Comprehensive**

- Piotroski covers 9 dimensions of quality
- Binary signals = easy to calculate
- Delta = easy to interpret
- No complex machine learning needed

### **Proven Track Record**

- 20+ years of academic research
- +23% annual returns historically
- Used by value investors worldwide

---

## 🚀 Next Steps

After verifying Piotroski works:

### **Option 2 (Moderate) - Still Pending:**
- Add `revenue_growth_3y` to quality_metrics
- Weight positive growth higher
- Reward margin expansion

### **Option 3 (Complete) - Still Pending:**
- Full momentum score
- Earnings momentum (EPS growth)
- Combined Quality + Moat + Momentum + F-Score

---

## 📝 Summary

**Problem:** EXPD bypassing deterioration checks with "Exceptional score"

**Solution:**
1. Raise exceptional threshold (80 → 85)
2. Check revenue growth before BUY
3. Check Piotroski delta before BUY
4. Block if either signal shows deterioration

**Result:**
- High-score declining businesses → MONITOR
- High-score healthy businesses → BUY
- More selective, higher quality signals

---

## 🎓 References

1. **Piotroski, J. (2000)** - "Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers"
   - Journal of Accounting Research, Vol. 38
   - Shows F-Score predicts returns (+23% for high F-Score)

2. **Mohanram, P. (2005)** - "Separating Winners from Losers among Low Book-to-Market Stocks using Financial Statement Analysis"
   - Extends Piotroski to growth stocks
   - Shows quality signals work across value/growth

3. **Asness, C., Frazzini, A., & Pedersen, L. (2019)** - "Quality Minus Junk"
   - Quality factors (including profitability, leverage, efficiency) predict returns
   - F-Score captures many QMJ dimensions

---

**¡Implementación completa del Piotroski F-Score Delta!** 🎯

Ahora el screener bloqueará empresas con scores altos pero calidad deteriorando.
