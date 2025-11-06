# 🔎 Guardrail Calibration Guide

## 📋 Overview

The **Guardrail Calibration Analysis** tool helps you optimize the screener's filtering thresholds by identifying potential false positives and analyzing the distribution of each guardrail metric.

---

## 🚀 How to Use

### **Step 1: Run the Screener**
1. Go to **"🏠 Home"** tab
2. Configure your universe filters (Market Cap, Volume, etc.)
3. Click **"Run Screener"** button
4. Wait for results (~5 minutes for 500 companies)

### **Step 2: Access Calibration Analysis**
1. Click on **"🔎 Calibration"** tab
2. You'll see:
   - **Quick Stats**: Distribution of VERDE/AMBAR/ROJO
   - **Top 10 Guardrail Reasons**: What's blocking companies most frequently

### **Step 3: Generate Detailed Analysis**
1. Select analysis type from dropdown:
   - **Full Report**: Comprehensive analysis of all guardrails
   - **Beneish M-Score**: Earnings manipulation detection
   - **Altman Z-Score**: Bankruptcy risk
   - **Revenue Growth**: Growth/decline patterns
   - **M&A / Goodwill**: Acquisition activity
   - **Share Dilution**: Equity issuance
   - **Accruals / NOA**: Earnings quality

2. Click **"🔍 Generate Analysis"** button

3. Review the report:
   - Distribution statistics
   - Companies affected by each guardrail
   - High-quality companies potentially blocked (false positives)
   - Calibration recommendations

4. Download report using **"📥 Download Report"** button

---

## 📊 Understanding the Reports

### **Full Report Sections**

#### **1. Overall Guardrail Status**
Shows distribution of companies across VERDE/AMBAR/ROJO and top reasons.

**What to look for:**
- ROJO > 30%: Thresholds may be too strict
- Top reason appears >20%: May need threshold adjustment

#### **2. Beneish M-Score Analysis**

**Distribution Statistics:** Mean, median, percentiles of M-Scores

**Companies by Zone:**
- CRITICAL (M > -1.5): Very high risk
- HIGH RISK (M > -1.78): Above original threshold
- MODERATE (M > -2.0): Borderline
- BORDERLINE (M > -2.22): Gray zone
- CLEAN (M ≤ -2.22): Low risk

**🚨 High Quality Companies Blocked:**
- Companies with Quality ≥70 but ROJO due to Beneish
- **If >10 companies:** Consider industry-specific thresholds may need adjustment
- **If specific industry dominates:** Review if threshold appropriate for that sector

**Example:**
```
🚨 HIGH QUALITY COMPANIES BLOCKED BY BENEISH: 3
(Quality ≥70, Status=ROJO due to Beneish)

Ticker   Industry                            Quality  Beneish M  Status
------------------------------------------------------------------------
EXPE     Travel Services                      98.9    -1.65      ROJO
SHOP     Software - Application               95.2    -1.55      ROJO
```

**Action:** These may be false positives. Check if:
1. Industry has complex accounting (travel, software, retail)
2. Company has legitimate business model despite high M-Score
3. Threshold should be adjusted for this industry

---

#### **3. Altman Z-Score Analysis**

**Companies by Zone:**
- DISTRESS (Z < 1.8): High bankruptcy risk
- GRAY ZONE (1.8 ≤ Z < 3.0): Moderate risk
- SAFE ZONE (Z ≥ 3.0): Low risk

**🚨 Extreme Distress (Z < 1.0):**
- Companies with very high bankruptcy risk
- Usually: High debt, low profitability, negative working capital
- **These are CORRECT blocks** - avoid these companies

**What to look for:**
- **By Industry:** Are certain industries systematically in distress?
  - Airlines post-COVID: High distress is expected
  - Retail struggling: Legitimate concern
  - Tech companies: Z-Score may not apply well (low assets)

**Example:**
```
🚨 EXTREME DISTRESS (Z < 1.0): 4

Ticker   Industry                            Altman Z  Quality  Status
------------------------------------------------------------------------
AAL      Airlines                                0.30    45.2   ROJO
BBBY     Department Stores                       0.58    32.1   ROJO
```

**Action:** These blocks are usually correct. If high-quality company (Q≥70) in distress:
- May be recovery play (turnaround situation)
- Verify with qualitative analysis
- Generally still avoid unless expert in distressed investing

---

#### **4. Revenue Growth Analysis**

**Companies by Growth Tier:**
- DECLINING FAST (< -5%): Severe revenue decline
- DECLINING SLOW (-5% to 0%): Modest decline
- FLAT (0% to 5%): Low growth
- GROWING (5% to 15%): Healthy growth
- HIGH GROWTH (≥ 15%): Strong growth

**🤔 High Quality + Declining Revenue:**
- Companies with Quality ≥70 but revenue declining
- **Could be:**
  1. Temporary headwinds (supply chain, COVID)
  2. Structural decline (moat erosion)
  3. Industry-wide contraction

**Example:**
```
🤔 HIGH QUALITY + DECLINING REVENUE: 2

Ticker   Industry                            Rev 3Y   Quality  Status
------------------------------------------------------------------------
PG       Household Products                   -0.5%    87.3    AMBAR
KHC      Packaged Foods                       -1.2%    72.8    AMBAR
```

**Action:** Investigate qualitatively:
- Is decline temporary or structural?
- Is company losing market share or industry contracting?
- If industry-wide contraction but high quality, may still be good investment

---

#### **5. M&A / Goodwill Analysis**

**M&A Flag Distribution:**
- LOW: Minimal M&A activity
- MODERATE: Some acquisitions
- HIGH: Frequent acquisitions, goodwill growing

**💼 High Quality + High M&A:**
- Companies with Quality ≥70 and HIGH M&A flag
- **Could be:**
  1. Serial acquirers with good track record (Constellation Software, Danaher)
  2. Roll-up strategy (may be dilutive)
  3. Empire building (value destruction)

**Example:**
```
💼 HIGH QUALITY + HIGH M&A: 8

Ticker   Industry                            Quality  M&A    Status
------------------------------------------------------------------------
DHR      Medical Devices                       92.1    HIGH   AMBAR
CSCO     Networking Equipment                  78.5    HIGH   AMBAR
```

**Action:** Review M&A history:
- Are acquisitions accretive or dilutive?
- Track record of integration success?
- If systematic acquirer with good track record, may reduce weight of M&A flag

---

#### **6. Share Dilution Analysis**

**Companies by Dilution Tier:**
- BUYBACK (< -5%): Reducing shares (good)
- NEUTRAL (-5% to 5%): Minimal dilution
- MODERATE DILUTION (5% to 10%): Some dilution (caution)
- HIGH DILUTION (> 10%): Significant dilution (red flag)

**Top Diluters:**
- Companies with >10% dilution in 12 months
- **Could be:**
  1. Growth companies raising capital (biotech, tech)
  2. Distressed companies raising survival cash
  3. Equity compensation heavy (tech)

**What to look for:**
- **Growth companies (biotech, early-stage tech):** Dilution may be acceptable if funding R&D
- **Mature companies:** Dilution >10% is concerning

---

### **Calibration Recommendations Section**

The tool provides specific recommendations based on your results:

**✅ Well Calibrated:**
```
✅ BENEISH: Only 2 high-quality companies blocked - acceptable rate.
✅ ALTMAN Z: 12.5% in distress zone - normal range (10-20%).
```

**⚠️ Needs Attention:**
```
⚠️ BENEISH: 15 high-quality companies (Q≥80) blocked by Beneish.
   Consider reviewing industry thresholds or specific cases.

⚠️ M&A FLAG: 28.5% flagged as HIGH M&A.
   Consider if threshold is too strict (currently triggers on goodwill growth).
```

---

## 🎯 Common Calibration Scenarios

### **Scenario 1: Too Many ROJO (>30%)**

**Problem:** Blocking too many companies, missing good opportunities

**Solution:**
1. Run **Full Report**
2. Identify which guardrail is causing most blocks (check "Top 10 Reasons")
3. Review companies affected:
   - If mostly low quality (Q<50): Guardrail working correctly
   - If many high quality (Q≥70): Threshold may be too strict

**Threshold Adjustments:**
- **Beneish:** Already industry-adjusted; check if specific industries need further tuning
- **Altman Z:** 1.8 is standard; only adjust if many tech companies affected (they have low Z naturally)
- **Revenue decline:** -5% severe, 0% moderate - can adjust in code if needed

---

### **Scenario 2: High-Quality Companies Blocked**

**Problem:** Companies with Quality ≥80 being flagged as ROJO

**Solution:**
1. Run specific guardrail analysis (e.g., "Beneish M-Score")
2. Review **"HIGH QUALITY COMPANIES BLOCKED"** section
3. For each company:
   - Check industry: Is accounting complexity expected?
   - Review guardrail value: Close to threshold or way over?
   - Investigate qualitatively: Is concern legitimate?

**Decision Matrix:**
| Guardrail Value | Quality | Action |
|-----------------|---------|--------|
| Just over threshold | ≥80 | Likely false positive - consider exception |
| Way over threshold | ≥80 | Investigate - may be legitimate concern |
| Any value | <70 | Block is appropriate |

---

### **Scenario 3: Industry-Specific Issues**

**Problem:** Specific industry consistently flagged (e.g., all Airlines ROJO due to Altman Z)

**Solution:**
1. Run **Full Report** or specific guardrail analysis
2. Check **"By Industry"** sections
3. Determine if:
   - Industry characteristic (Airlines have high debt → low Altman Z)
   - Industry in crisis (Retail in 2020)
   - Guardrail doesn't apply (Software/SaaS has low Z-Score naturally)

**Actions:**
- **If industry characteristic:** Consider industry-specific threshold (like we did for Beneish)
- **If industry in crisis:** Keep strict threshold (avoiding crisis-hit industries is correct)
- **If guardrail doesn't apply:** Exclude industry or use alternative metric

**Example:** Tech companies with Altman Z < 1.8 due to asset-light model:
- **Option A:** Use alternative distress metric for tech (leverage ratio, interest coverage)
- **Option B:** Accept lower Z-Score for asset-light industries
- **Current:** System already accounts for this in guardrail evaluation

---

## 📈 Recommended Calibration Workflow

### **After Each Screener Run:**

1. **Check Quick Stats** (in Calibration tab):
   - ROJO: Should be 10-20% (if >30%, too strict)
   - AMBAR: Should be 30-50%
   - VERDE: Should be 30-60%

2. **Review Top 10 Reasons**:
   - If one reason dominates (>20%), investigate that guardrail
   - If "All checks OK" is top reason, system may be too permissive

3. **Run Full Report** once per week:
   - Save report for comparison over time
   - Track false positive rate: (High-quality ROJO) / (Total ROJO)
   - Target: <10% false positive rate

4. **Investigate High-Quality Blocks**:
   - Any company with Quality ≥85 and ROJO deserves manual review
   - Check if industry/business model causes guardrail to trigger incorrectly

### **Quarterly Calibration Review:**

1. **Compile 10-15 screener runs** over the quarter

2. **Identify patterns:**
   - Which industries are systematically flagged?
   - Which guardrails have highest false positive rate?
   - Are there legitimate companies consistently blocked?

3. **Adjust thresholds:**
   - Document reasoning for any change
   - Test on historical data
   - Monitor impact for 1-2 months

4. **Validate:**
   - Did false positive rate decrease?
   - Did we start blocking new bad companies (false negatives)?
   - Balance precision vs. recall

---

## 🛠️ Advanced Usage

### **Command-Line Analysis**

For batch processing or automation:

```bash
# Full report
python analyze_guardrails.py --results output/screener_results.csv

# Specific guardrail
python analyze_guardrails.py --results output/screener_results.csv --guardrail beneish

# Save to file
python analyze_guardrails.py --results output/screener_results.csv --output reports/calibration_2024-01-15.txt
```

### **Programmatic Analysis**

```python
import pandas as pd
from analyze_guardrails import GuardrailAnalyzer

# Load results
df = pd.read_csv('output/screener_results.csv')

# Create analyzer
analyzer = GuardrailAnalyzer(df)

# Generate specific analysis
beneish_report = analyzer._analyze_beneish()
altman_report = analyzer._analyze_altman_z()

# Full report
full_report = analyzer.generate_full_report()

# Save
with open('calibration_report.txt', 'w') as f:
    f.write(full_report)
```

---

## ❓ FAQ

### **Q: How often should I run calibration analysis?**
**A:**
- Quick stats: Every screener run (1 minute)
- Full report: Weekly (5 minutes)
- Threshold adjustments: Quarterly (after pattern analysis)

### **Q: What's an acceptable false positive rate?**
**A:**
- Target: <10% of ROJO companies should be high-quality (Q≥70)
- Acceptable: 10-15%
- Concerning: >15% - thresholds likely too strict

### **Q: Should I adjust thresholds based on one screener run?**
**A:**
- NO - wait for pattern across multiple runs
- Exception: Obvious error (e.g., 50% of companies ROJO)
- Best practice: Collect 10-15 runs, then analyze trends

### **Q: What if a high-quality company keeps getting blocked?**
**A:**
1. Run qualitative analysis on that company
2. Review all guardrails: which one(s) trigger?
3. Research if concern is legitimate
4. If false positive:
   - Check if industry-wide (adjust threshold)
   - Check if company-specific (manual exception in your process)

### **Q: Can I disable a guardrail?**
**A:**
- Yes, but not recommended
- Better approach: Adjust threshold to be more permissive
- Example: Beneish threshold -1.78 → -1.5 for travel industry
- Disabling removes important safety net

### **Q: Industry-adjusted Beneish - is it working?**
**A:**
Check Beneish report:
- Look at "By Industry" section under flagged companies
- If travel/software/retail still dominating: May need further adjustment
- If balanced across industries: Working well

### **Q: What if I disagree with a ROJO classification?**
**A:**
- System is conservative by design (safety first)
- Use AMBAR companies for opportunities (can be BUY if composite ≥85)
- If repeatedly disagree: Adjust threshold in code
- Document reasoning for any override

---

## 📚 Related Documentation

- **INDUSTRY_ADJUSTED_BENEISH.md**: Academic foundation for industry-specific thresholds
- **DUAL_QUALITY_DEGRADATION.md**: Piotroski/Mohanram quality degradation system
- **MOMENTUM_FILTERS.md**: Revenue growth, ROIC trend, margin trend filters

---

## 🎯 Summary

**The Calibration tool helps you:**
✅ Identify false positives (good companies blocked)
✅ Understand guardrail distributions
✅ Adjust thresholds based on data
✅ Track calibration quality over time
✅ Make evidence-based decisions

**Target Metrics:**
- ROJO rate: 10-20%
- False positive rate: <10%
- High-quality blocks (Q≥80): <5 companies per run

**Calibration Philosophy:**
- Conservative by default (avoid bad companies)
- Iterate based on evidence (not hunches)
- Document all threshold changes
- Monitor impact over time

---

**Happy Calibrating! 🔎**
