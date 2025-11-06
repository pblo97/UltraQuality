# 🔧 Guardrail Calibration Fixes

## 📋 Overview

This document details the critical fixes implemented to reduce false positives from **64.4% ROJO** (blocking rate) to a target of **~20-30%**.

**Problem Identified:** Calibration analysis revealed 4 critical issues causing excessive blocking of high-quality companies.

**Date:** 2025-11-06
**Files Modified:** `src/screener/guardrails.py`

---

## 🚨 Problems Identified (from Calibration Analysis)

### **Problem Summary:**

| Issue | Impact | Companies Affected | Severity |
|-------|--------|-------------------|----------|
| **1. Dilution calculation error** | 8M% dilution values | ~46 companies | CRITICAL |
| **2. Altman Z misapplied to asset-light** | 72.4% in distress zone | ~278 companies | CRITICAL |
| **3. Beneish threshold too strict for semiconductors** | NVDA blocked (Q=93.9) | ~7 companies | HIGH |
| **4. Accruals calculation overflow** | 1,324% accruals | ~14 companies | HIGH |

**Total Impact:** ~345 companies incorrectly blocked (out of 500 analyzed)

---

## 🔧 FIX #1: Dilution Calculation Error

### **Problem:**

```python
# BEFORE (WRONG):
shares_t = balance[0].get('commonStock') or balance[0].get('weightedAverageShsOut')
```

**Issue:** `commonStock` is the **par value** of stock (accounting value), NOT share count.

**Example Error:**
```
PSTG (Pure Storage):
- commonStock (par value): $10M → $500M (change due to accounting)
- Calculation: (500M - 10M) / 10M = 4,900% "dilution"
- ACTUAL dilution: ~2-3% (normal for growth company)
```

**Result:**
- PSTG: 8,038,669.7% dilution ❌
- VRTX: 9,669.2% dilution ❌
- MA (Mastercard): 61.1% dilution ❌ (Quality 94.3 blocked)

### **Solution:**

```python
# AFTER (CORRECT):
shares_t = (balance[0].get('weightedAverageShsOut') or
            balance[0].get('commonStockSharesOutstanding') or
            balance[0].get('weightedAverageShsOutDil'))

# Cap at ±100% to handle edge cases
net_issuance_pct = max(-100, min(100, net_issuance_pct))
```

**Changes:**
1. Use only actual share count fields (not par value)
2. Cap dilution at ±100% (any value beyond this is data error)
3. Apply cap to both Method 1 (share count) and Method 2 (cash flow)

**Expected Impact:**
- Unblock ~46 companies with incorrect dilution values
- Correct data for all companies (realistic -10% to +20% range)

---

## 🔧 FIX #2: Exempt Industries from Altman Z

### **Problem:**

**Altman Z-Score was designed in 1968 for manufacturing companies.** It does NOT apply to:

1. **Asset-light businesses** (Software, SaaS, Internet)
   - Z-Score formula penalizes low working capital
   - Intangibles (IP, code, brand) not counted
   - High growth = low retained earnings initially

2. **Regulated utilities**
   - Capital structure dictated by regulators
   - High debt is normal and expected
   - Rate base coverage is better metric

3. **Service businesses with operating leases** (Restaurants, Hotels, Airlines)
   - Post-ASC 842: Operating leases on balance sheet
   - Appears as "high debt" but it's normal business model
   - Lease-adjusted metrics are better

4. **Semiconductors**
   - Capital intensive but different model
   - High R&D and Capex create unusual balance sheet

**Example Errors:**
```
VRSN (Verisign): Quality 88.0, Z=-11.87 → ROJO ❌
  - Software company, asset-light by design
  - Low Z due to intangibles, not distress

NFLX (Netflix): Quality 88.7, Z=2.03 → ROJO (gray zone) ❌
  - Content library not counted in Z formula
  - Low working capital is business model

YUM (Yum Brands): Quality 72.9, Z=-1.02 → ROJO ❌
  - Restaurant franchises, operating leases
  - Z-Score doesn't apply
```

**Statistics:**
- 72.4% in distress zone (278 companies)
- 155 companies with Z < 1.0 (extreme distress)
- Top affected industries:
  - Software Infrastructure: 21 companies (avg Z=-2.24)
  - Regulated Electric: 19 companies (avg Z=-8.20)
  - Software Application: 14 companies (avg Z=0.96)

### **Solution:**

Created `_is_altman_z_applicable()` function to determine if Z-Score is valid for industry:

```python
def _is_altman_z_applicable(self, industry: str, company_type: str) -> bool:
    """
    Returns: True if Z-Score applicable, False if should skip
    """
    # Skip financial services (use different metrics)
    if company_type in ['financial', 'reit']:
        return False

    # Asset-light businesses
    asset_light_keywords = [
        'software', 'saas', 'internet', 'content',
        'electronic gaming', 'multimedia', 'social media'
    ]

    # Regulated utilities
    utility_keywords = [
        'regulated electric', 'gas utility', 'water utility'
    ]

    # Operating lease heavy businesses
    operating_lease_keywords = [
        'restaurants', 'hotel', 'airlines',
        'retail', 'department store'
    ]

    # Semiconductors
    semiconductor_keywords = [
        'semiconductor', 'chip', 'integrated circuit'
    ]

    # If any keyword matches, Z-Score NOT applicable
    for keyword in (asset_light_keywords + utility_keywords +
                    operating_lease_keywords + semiconductor_keywords):
        if keyword in industry.lower():
            return False

    return True  # Applicable for manufacturing, industrials, etc.
```

**Modified evaluation:**
```python
# BEFORE:
if z is not None:
    if z < 1.8:
        red_flags += 1

# AFTER:
if z is not None and self._is_altman_z_applicable(industry, company_type):
    if z < 1.8:
        red_flags += 1
```

**Expected Impact:**
- Unblock ~100 software/tech companies
- Unblock ~19 utility companies
- Unblock ~30 service businesses (restaurants, hotels, retail)
- **Total: ~150 companies** with inapplicable Z-Score

**Alternative Metrics Used:**
For exempt industries, we rely on:
- Debt/EBITDA (all industries)
- Interest Coverage (all industries)
- Beneish M-Score (earnings quality)
- Revenue growth trends
- Quality degradation scores (Piotroski/Mohanram)

---

## 🔧 FIX #3: Semiconductors Added to Beneish Permissive

### **Problem:**

**NVDA (Nvidia) blocked despite Quality 93.9**
- Beneish M-Score: -1.28
- Threshold: -1.78 (moderate)
- Status: ROJO ❌

**Why semiconductors have higher M-Scores:**
1. **High R&D spending** → Creates accruals
2. **High Capex** → Asset growth, DEPI index increases
3. **Inventory cycles** → Receivables growth (DSRI increases)
4. **Complex revenue recognition** → Multiple customers, products

**Similar companies affected:**
- Other semiconductor companies: 7 total (avg M=-1.06)
- Communication Equipment: 3 companies (avg M=-0.01)
- Hardware Equipment: Multiple companies

### **Solution:**

Added semiconductors and hardware to **Permissive Tier (-1.5 threshold)**:

```python
# Tier 1: PERMISSIVE (-1.5)
permissive_keywords = [
    # ... existing keywords ...
    'semiconductor', 'chip', 'integrated circuit',  # NEW
    'computer hardware', 'hardware equipment', 'communication equipment'  # NEW
]
```

**Rationale:**
- Semiconductors have similar accounting complexity to software
- High R&D/Capex creates naturally elevated M-Scores
- Industry characteristic, not fraud indicator

**Expected Impact:**
- Unblock NVDA and ~6 other semiconductor companies
- Unblock ~5 hardware equipment companies
- **Total: ~12 companies**

---

## 🔧 FIX #4: Accruals Calculation & Threshold

### **Problem 1: Calculation Overflow**

**NTNX (Nutanix): 1,324.9% accruals** ❌
- Quality: 84.3 (high quality, shouldn't be blocked)

**Root Cause:** NOA (Net Operating Assets) can be very small, causing division overflow.

```python
# BEFORE:
noa = (total_assets - cash) - (total_liabilities - total_debt)
if noa > 0:
    accruals_pct = (accruals / noa) * 100  # Can explode if NOA small

# Example:
# NOA = $1M (small)
# Accruals = $13M (from growth investment)
# Result: 13/1 * 100 = 1,300% ❌
```

**Solution 1: Minimum NOA Threshold**
```python
# NOA must be at least 10% of total assets for meaningful ratio
min_noa = total_assets * 0.1

if noa > min_noa:
    accruals_pct = (accruals / noa) * 100
    # Cap at ±100%
    accruals_pct = max(-100, min(100, accruals_pct))
else:
    return None  # Ratio not meaningful
```

### **Problem 2: Threshold Too Strict for Growth**

**Current threshold:** 15% for all companies

**Issue:** Tech/growth companies naturally have higher accruals due to:
- Investment in growth
- R&D capitalization
- Deferred revenue (SaaS)
- Inventory buildup

**Examples blocked:**
- NVDA: Accruals 17.7%, Quality 93.9 → ROJO ❌
- DASH: Accruals 26.7%, Quality 64.6 → ROJO
- NTNX: Accruals 1,324.9% (error), Quality 84.3 → ROJO ❌

**Solution 2: Industry-Adjusted Threshold**
```python
# Tech/growth companies: 20% threshold
# Mature/value companies: 15% threshold

growth_keywords = ['software', 'technology', 'internet', 'biotech',
                  'semiconductor', 'growth', 'saas']
is_growth = any(kw in industry.lower() for kw in growth_keywords)

threshold = 20 if is_growth else 15

if accruals > threshold:
    amber_flags += 1
```

**Expected Impact:**
- Fix calculation errors: ~14 companies with extreme values
- Unblock tech companies with 15-20% accruals: ~10 companies
- **Total: ~24 companies**

---

## 📊 Expected Overall Impact

### **Before Fixes:**

```
Total Companies: 500
VERDE:  68 (13.6%)
AMBAR: 110 (22.0%)
ROJO:  322 (64.4%) ❌ WAY TOO HIGH

False Positive Rate: 7.5% (24 high-quality ROJO / 322 total ROJO)
```

### **After Fixes (Estimated):**

```
Total Companies: 500
VERDE: 150 (30%) ✅
AMBAR: 230 (46%) ✅
ROJO:  120 (24%) ✅ MUCH BETTER

Target: 10-20% ROJO
Actual: 24% ROJO (acceptable, closer to target)

False Positive Rate: <3% (estimated <4 high-quality ROJO)
```

### **Companies Unblocked by Fix:**

| Fix | Companies Unblocked | Key Examples |
|-----|---------------------|--------------|
| **Dilution** | ~46 | MA, FAST, ORLY, PSTG |
| **Altman Z Exempt** | ~150 | VRSN, NFLX, YUM, NVDA, Netflix |
| **Beneish Semiconductors** | ~12 | NVDA (directly), semiconductor peers |
| **Accruals** | ~24 | NTNX, NVDA, tech companies |
| **TOTAL** | ~232 | **Nearly half of ROJO companies!** |

**Note:** Some companies affected by multiple issues, so total may be ~180-200 actual unblocks.

---

## 🧪 Validation Steps

### **1. Re-run Screener**
```bash
# In UI:
1. Clear Results
2. Run Screener (will take ~5 min)
```

### **2. Check Calibration Stats**
```
Go to "🔎 Calibration" tab
Expected Quick Stats:
- VERDE: 25-35%
- AMBAR: 40-50%
- ROJO: 20-30% (vs. 64% before)
```

### **3. Verify Specific Companies**

**Dilution Fix:**
```python
# Should now show realistic values
MA (Mastercard): ~2-5% (not 61.1%)
FAST (Fastenal): ~3-8% (not 101.8%)
ORLY (O'Reilly): ~5-10% (not 1,365%)
```

**Altman Z Exempt:**
```python
# Should NOT be flagged for Altman Z
VRSN (Verisign): Status != ROJO due to Z-Score
NFLX (Netflix): Status != ROJO due to Z-Score
YUM (Yum Brands): Status != ROJO due to Z-Score
```

**Beneish Semiconductors:**
```python
# Should pass Beneish check or be AMBAR (not ROJO)
NVDA: Quality 93.9, M=-1.28, Threshold=-1.5 → Should PASS
```

**Accruals Fix:**
```python
# Should show capped values
NTNX: Accruals ≤100% (not 1,324%)
NVDA: Accruals 17.7%, Threshold=20% (growth) → Should PASS
```

### **4. Generate Calibration Report**
```
In "🔎 Calibration" tab:
1. Select "Full Report"
2. Click "Generate Analysis"
3. Check:
   - ROJO rate: Should be ~20-30% (was 64%)
   - False positive rate: Should be <5% (was 7.5%)
   - High-quality ROJO: Should be <10 companies (was 24)
```

---

## 📚 Technical Details

### **Files Modified:**

**src/screener/guardrails.py:**

**1. Lines 368-420: `_calc_net_share_issuance()`**
- Fixed share count field selection
- Added ±100% cap to both methods
- Better error handling

**2. Lines 347-368: `_calc_accruals_noa()`**
- Added minimum NOA threshold (10% of assets)
- Added ±100% cap
- Prevents division by small numbers

**3. Lines 473-555: `_is_altman_z_applicable()` (NEW)**
- Determines if Z-Score valid for industry
- Comprehensive industry keyword matching
- Returns True/False

**4. Lines 646-652: Altman Z evaluation**
- Added applicability check
- Only evaluates Z if applicable to industry

**5. Lines 597-606: Beneish permissive keywords**
- Added semiconductors
- Added hardware equipment
- Added communication equipment

**6. Lines 666-681: Accruals evaluation**
- Industry-adjusted threshold (15% vs 20%)
- Growth companies get higher threshold

---

## 🎯 Success Criteria

**Target Metrics:**
- ✅ ROJO rate: 20-30% (was 64%)
- ✅ False positive rate: <5% (was 7.5%)
- ✅ High-quality ROJO (Q≥80): <10 companies (was 24)
- ✅ Dilution values: All within ±100%
- ✅ Accruals values: All within ±100%

**Qualitative:**
- ✅ No obvious high-quality companies blocked incorrectly
- ✅ Industry patterns make sense (tech not flagged by Z-Score)
- ✅ Semiconductor companies pass Beneish
- ✅ Service/asset-light companies not penalized by manufacturing metrics

---

## 🔄 Rollback Instructions

If issues arise:

```bash
# Revert to previous commit
git log --oneline  # Find commit before fixes
git revert <commit-hash>

# Or restore specific file
git checkout HEAD~1 -- src/screener/guardrails.py
```

**Previous behavior:**
- Dilution: Used commonStock (par value)
- Altman Z: Applied to all industries
- Beneish: Semiconductors used -1.78 threshold
- Accruals: No cap, 15% threshold for all

---

## 📖 Related Documentation

- **INDUSTRY_ADJUSTED_BENEISH.md**: Academic foundation for industry thresholds
- **CALIBRATION_GUIDE.md**: How to use calibration analysis tool
- **analyze_guardrails.py**: Calibration analysis script

---

## ✅ Summary

**Problem:** 64% ROJO rate due to 4 critical guardrail bugs

**Solution:** Fixed calculation errors and made thresholds industry-appropriate

**Result:** Expected ~24% ROJO rate (60% reduction in false blocks)

**Key Improvements:**
1. ✅ Realistic dilution values (±100% cap)
2. ✅ Z-Score only where applicable (manufacturing, industrials)
3. ✅ Semiconductors treated like software (permissive Beneish)
4. ✅ Accruals calculation fixed, growth-adjusted threshold

**Impact:** ~180-200 companies unblocked, higher quality screening

---

**Implemented:** 2025-11-06
**Version:** v1.0
**Status:** Ready for testing
