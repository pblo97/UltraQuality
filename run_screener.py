"""
UltraQuality - Streamlit Web Interface

This is the MAIN FILE for the Streamlit web app.
- Streamlit Cloud is configured to run this file
- The UI loads instantly with lazy imports
- The screener only runs when user clicks the button

For CLI usage, use: python cli_run_screener.py
"""
import streamlit as st
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
import os
import traceback
import yaml

# Load environment variables from .env file (if exists)
from dotenv import load_dotenv
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Helper function to expand environment variables in config values
def expand_env_vars(value):
    """Expand ${VAR} or $VAR in strings with environment variables."""
    if isinstance(value, str):
        import re
        # Match ${VAR} or $VAR pattern
        pattern = r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)'
        def replace(match):
            var_name = match.group(1) or match.group(2)
            return os.environ.get(var_name, match.group(0))
        return re.sub(pattern, replace, value)
    return value

# NOTE: We import ScreenerPipeline lazily inside the button click
# to avoid blocking the UI load with heavy imports

# ===================================
# Excel Export Helper Functions
# ===================================

def create_screener_excel(df: pd.DataFrame, timestamp: datetime) -> bytes:
    """
    Create Excel file with screener results.

    Args:
        df: Screener results dataframe
        timestamp: Timestamp for metadata

    Returns:
        Excel file as bytes
    """
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Main results sheet
        df.to_excel(writer, sheet_name='Screener Results', index=False)

        # Get the workbook and worksheet
        workbook = writer.book
        worksheet = writer.sheets['Screener Results']

        # Auto-adjust column widths
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width

        # Add summary sheet
        summary_data = {
            'Metric': [
                'Total Stocks Screened',
                'BUY Recommendations',
                'MONITOR Recommendations',
                'AVOID Recommendations',
                'VERDE Guardrails',
                'AMBAR Guardrails',
                'ROJO Guardrails',
                'Average Quality Score',
                'Average Value Score',
                'Average Composite Score',
                'Report Generated'
            ],
            'Value': [
                len(df),
                len(df[df['decision'] == 'BUY']) if 'decision' in df.columns else 0,
                len(df[df['decision'] == 'MONITOR']) if 'decision' in df.columns else 0,
                len(df[df['decision'] == 'AVOID']) if 'decision' in df.columns else 0,
                len(df[df['guardrail_status'] == 'VERDE']) if 'guardrail_status' in df.columns else 0,
                len(df[df['guardrail_status'] == 'AMBAR']) if 'guardrail_status' in df.columns else 0,
                len(df[df['guardrail_status'] == 'ROJO']) if 'guardrail_status' in df.columns else 0,
                f"{df['quality_score_0_100'].mean():.1f}" if 'quality_score_0_100' in df.columns else 'N/A',
                f"{df['value_score_0_100'].mean():.1f}" if 'value_score_0_100' in df.columns else 'N/A',
                f"{df['composite_0_100'].mean():.1f}" if 'composite_0_100' in df.columns else 'N/A',
                timestamp.strftime('%Y-%m-%d %H:%M:%S')
            ]
        }

        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)

        # Auto-adjust summary sheet
        summary_sheet = writer.sheets['Summary']
        summary_sheet.column_dimensions['A'].width = 30
        summary_sheet.column_dimensions['B'].width = 20

    output.seek(0)
    return output.getvalue()


def create_qualitative_excel(analysis: dict, ticker: str, timestamp: datetime) -> bytes:
    """
    Create Excel file with detailed qualitative analysis.

    Args:
        analysis: Qualitative analysis dictionary
        ticker: Stock ticker
        timestamp: Timestamp for metadata

    Returns:
        Excel file as bytes
    """
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Overview
        intrinsic = analysis.get('intrinsic_value', {})
        overview_data = {
            'Metric': ['Ticker', 'Analysis Date', 'Current Price', 'DCF Value', 'Forward Multiple', 'Fair Value',
                      'Upside/Downside %', 'Assessment', 'Confidence', 'Industry Profile', 'Primary Metric'],
            'Value': [
                ticker,
                timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                f"${intrinsic.get('current_price', 0):.2f}",
                f"${intrinsic.get('dcf_value', 0):.2f}" if intrinsic.get('dcf_value') else 'N/A',
                f"${intrinsic.get('forward_multiple_value', 0):.2f}" if intrinsic.get('forward_multiple_value') else 'N/A',
                f"${intrinsic.get('weighted_value', 0):.2f}" if intrinsic.get('weighted_value') else 'N/A',
                f"{intrinsic.get('upside_downside_%', 0):+.1f}%" if intrinsic.get('upside_downside_%') is not None else 'N/A',
                intrinsic.get('valuation_assessment', 'Unknown'),
                intrinsic.get('confidence', 'Low'),
                intrinsic.get('industry_profile', 'unknown').replace('_', ' ').title(),
                intrinsic.get('primary_metric', 'N/A')
            ]
        }
        pd.DataFrame(overview_data).to_excel(writer, sheet_name='Overview', index=False)

        # Sheet 2: Capital Efficiency (ROIC for non-financials, ROE for financials)
        capital_eff = intrinsic.get('capital_efficiency', {})
        if capital_eff:
            metric_name = capital_eff.get('metric_name', 'ROIC')
            current = capital_eff.get('current', 0)
            history_5y = capital_eff.get('history_5y', [])

            cap_data = {
                'Metric': [metric_name, 'WACC', f'Spread ({metric_name} - WACC)',
                          f'3Y Average {metric_name}', f'5Y Average {metric_name}', 'Trend', 'Assessment'],
                'Value': [
                    f"{current:.1f}%",
                    f"{capital_eff.get('wacc', 0):.1f}%",
                    f"{capital_eff.get('spread', 0):+.1f}%",
                    f"{capital_eff.get('avg_3y', 0):.1f}%",
                    f"{capital_eff.get('avg_5y', 0):.1f}%",
                    capital_eff.get('trend', 'N/A'),
                    capital_eff.get('assessment', 'N/A')
                ]
            }
            pd.DataFrame(cap_data).to_excel(writer, sheet_name='Capital Efficiency', index=False)

            # Add 5-year history as separate sheet if available
            if history_5y:
                history_df = pd.DataFrame({
                    'Year': [f'Year {i+1}' for i in range(len(history_5y))],
                    f'{metric_name} (%)': [f"{h:.1f}%" for h in history_5y]
                })
                history_df.to_excel(writer, sheet_name=f'{metric_name} History', index=False)

        # Sheet 3: Quality of Earnings
        earnings_qual = intrinsic.get('earnings_quality', {})
        if earnings_qual:
            eq_data = {
                'Metric': ['OCF / Net Income', 'Accruals Ratio', 'Working Capital Trend', 'Grade', 'Assessment'],
                'Value': [
                    f"{earnings_qual.get('cash_flow_to_net_income', 0):.2f}",
                    f"{earnings_qual.get('accruals_ratio', 0):.2f}%",
                    earnings_qual.get('working_capital_trend', 'N/A'),
                    earnings_qual.get('grade', 'N/A'),
                    earnings_qual.get('assessment', 'N/A')
                ]
            }
            eq_df = pd.DataFrame(eq_data)
            eq_df.to_excel(writer, sheet_name='Earnings Quality', index=False)

            # Add issues if any
            issues = earnings_qual.get('issues', [])
            if issues:
                issues_df = pd.DataFrame({'Issues Detected': issues})
                issues_df.to_excel(writer, sheet_name='Quality Issues', index=False)

        # Sheet 4: Profitability Margins
        profitability = intrinsic.get('profitability_analysis', {})
        if profitability:
            margins_data = []
            for margin_type in ['gross_margin', 'operating_margin', 'fcf_margin']:
                margin = profitability.get(margin_type, {})
                if margin:
                    margins_data.append({
                        'Margin Type': margin_type.replace('_', ' ').title(),
                        'Current': f"{margin.get('current', 0):.1f}%",
                        '3Y Average': f"{margin.get('avg_3y', 0):.1f}%",
                        'Trend': margin.get('trend', 'N/A')
                    })
            if margins_data:
                pd.DataFrame(margins_data).to_excel(writer, sheet_name='Profitability Margins', index=False)

        # Sheet 5: Red Flags
        red_flags = intrinsic.get('red_flags', [])
        if red_flags:
            flags_df = pd.DataFrame({'Red Flags': red_flags})
            flags_df.to_excel(writer, sheet_name='Red Flags', index=False)
        else:
            # Show that no red flags were detected
            flags_df = pd.DataFrame({'Red Flags': [' No red flags detected']})
            flags_df.to_excel(writer, sheet_name='Red Flags', index=False)

        # Sheet 6: Reverse DCF
        reverse_dcf = intrinsic.get('reverse_dcf', {})
        if reverse_dcf:
            rdcf_data = {
                'Metric': ['Implied Growth Rate', 'Current Growth Rate', 'Implied EV/EBIT', 'Interpretation'],
                'Value': [
                    f"{reverse_dcf.get('implied_growth_rate', 0):.1f}%",
                    f"{reverse_dcf.get('current_growth_rate', 0):.1f}%",
                    f"{reverse_dcf.get('implied_ev_ebit', 0):.1f}x" if reverse_dcf.get('implied_ev_ebit') else 'N/A',
                    reverse_dcf.get('interpretation', 'N/A')
                ]
            }
            pd.DataFrame(rdcf_data).to_excel(writer, sheet_name='Reverse DCF', index=False)

        # Sheet 7: Price Projections
        projections = intrinsic.get('price_projections', {})
        scenarios = projections.get('scenarios', {})
        if scenarios:
            proj_data = []
            for scenario_name, data in scenarios.items():
                proj_data.append({
                    'Scenario': scenario_name,
                    'Growth Assumption': data.get('growth_assumption', 'N/A'),
                    'Description': data.get('description', 'N/A'),
                    '1Y Target': f"${data.get('1Y_target', 0):.2f}",
                    '1Y Return': data.get('1Y_return', 'N/A'),
                    '3Y Target': f"${data.get('3Y_target', 0):.2f}",
                    '3Y CAGR': data.get('3Y_cagr', 'N/A'),
                    '5Y Target': f"${data.get('5Y_target', 0):.2f}",
                    '5Y CAGR': data.get('5Y_cagr', 'N/A')
                })
            pd.DataFrame(proj_data).to_excel(writer, sheet_name='Price Projections', index=False)

        # Sheet 8: DCF Sensitivity
        dcf_sens = intrinsic.get('dcf_sensitivity', {})
        if dcf_sens:
            # WACC Sensitivity
            wacc_sens = dcf_sens.get('wacc_sensitivity', {})
            if wacc_sens:
                wacc_data = []
                for scenario, data in wacc_sens.items():
                    wacc_data.append({
                        'Scenario': scenario.title(),
                        'WACC': f"{data.get('wacc', 0):.1f}%",
                        'DCF Value': f"${data.get('dcf_value', 0):.2f}"
                    })
                wacc_df = pd.DataFrame(wacc_data)
                wacc_df.to_excel(writer, sheet_name='WACC Sensitivity', index=False)

            # Terminal Growth Sensitivity
            tg_sens = dcf_sens.get('terminal_growth_sensitivity', {})
            if tg_sens:
                tg_data = []
                for label, data in tg_sens.items():
                    tg_data.append({
                        'Terminal Growth': label,
                        'DCF Value': f"${data.get('dcf_value', 0):.2f}"
                    })
                tg_df = pd.DataFrame(tg_data)
                tg_df.to_excel(writer, sheet_name='Terminal Growth Sensitivity', index=False)

        # Sheet 9: Balance Sheet Strength
        balance_sheet = intrinsic.get('balance_sheet_strength', {})
        if balance_sheet:
            bs_data = {
                'Metric': ['Overall Assessment', 'Debt/Equity', 'Current Ratio', 'Quick Ratio',
                          'Interest Coverage', 'Debt/EBITDA', 'Cash & Equivalents', 'Net Debt', 'Debt Trend YoY'],
                'Value': [
                    balance_sheet.get('overall_assessment', 'N/A'),
                    f"{balance_sheet.get('debt_to_equity', {}).get('value', 0):.2f}x",
                    f"{balance_sheet.get('current_ratio', {}).get('value', 0):.2f}x",
                    f"{balance_sheet.get('quick_ratio', {}).get('value', 0):.2f}x",
                    f"{balance_sheet.get('interest_coverage', {}).get('value', 0):.1f}x" if balance_sheet.get('interest_coverage', {}).get('value') else 'N/A',
                    f"{balance_sheet.get('debt_to_ebitda', {}).get('value', 0):.1f}x",
                    balance_sheet.get('cash', {}).get('formatted', 'N/A'),
                    balance_sheet.get('net_debt', {}).get('formatted', 'N/A'),
                    f"{balance_sheet.get('debt_trend', {}).get('yoy_change_%', 0):+.1f}%" if balance_sheet.get('debt_trend') else 'N/A'
                ],
                'Assessment': [
                    ', '.join(balance_sheet.get('warnings', [])) if balance_sheet.get('warnings') else 'No warnings',
                    balance_sheet.get('debt_to_equity', {}).get('assessment', ''),
                    balance_sheet.get('current_ratio', {}).get('assessment', ''),
                    balance_sheet.get('quick_ratio', {}).get('assessment', ''),
                    balance_sheet.get('interest_coverage', {}).get('assessment', ''),
                    balance_sheet.get('debt_to_ebitda', {}).get('assessment', ''),
                    '',
                    balance_sheet.get('net_debt', {}).get('assessment', ''),
                    balance_sheet.get('debt_trend', {}).get('direction', '')
                ]
            }
            pd.DataFrame(bs_data).to_excel(writer, sheet_name='Balance Sheet', index=False)

        # Sheet 10: Valuation Multiples
        valuation_multiples = intrinsic.get('valuation_multiples', {})
        if valuation_multiples:
            company_vals = valuation_multiples.get('company', {})
            peers_avg = valuation_multiples.get('peers_avg', {})
            vs_peers = valuation_multiples.get('vs_peers', {})

            mult_data = []
            for metric in ['pe', 'pb', 'ps', 'ev_ebitda', 'peg']:
                company_val = company_vals.get(metric)
                peer_val = peers_avg.get(metric)
                vs_peer = vs_peers.get(metric, {})

                if company_val or peer_val:
                    mult_data.append({
                        'Multiple': metric.upper().replace('_', '/'),
                        'Company': f"{company_val:.2f}x" if company_val else 'N/A',
                        'Peers Avg': f"{peer_val:.2f}x" if peer_val else 'N/A',
                        'Premium/Discount %': f"{vs_peer.get('premium_discount_%', 0):+.1f}%" if vs_peer.get('premium_discount_%') is not None else 'N/A',
                        'Assessment': vs_peer.get('assessment', 'N/A')
                    })

            if mult_data:
                pd.DataFrame(mult_data).to_excel(writer, sheet_name='Valuation Multiples', index=False)

        # Sheet 11: Growth Consistency
        growth_consistency = intrinsic.get('growth_consistency', {})
        if growth_consistency:
            gc_data = []
            for category in ['revenue', 'earnings', 'fcf']:
                cat_data = growth_consistency.get(category, {})
                if cat_data:
                    gc_data.append({
                        'Metric': category.upper(),
                        'Years': cat_data.get('years', 0),
                        'Avg Growth %/yr': f"{cat_data.get('avg_growth_%', 0):.1f}%",
                        'Std Dev': f"{cat_data.get('std_dev', 0):.1f}%",
                        'Consistency': cat_data.get('consistency', 'N/A'),
                        'Trend': cat_data.get('trend', 'N/A'),
                        'Last 5Y History ($B)': ', '.join([f"{h:.1f}" for h in cat_data.get('history', [])[:5]])
                    })

            if gc_data:
                pd.DataFrame(gc_data).to_excel(writer, sheet_name='Growth Consistency', index=False)

            # Add overall assessment
            overall_assess = growth_consistency.get('overall_assessment', '')
            if overall_assess:
                assess_df = pd.DataFrame({'Overall Assessment': [overall_assess]})
                assess_df.to_excel(writer, sheet_name='Growth Assessment', index=False)

        # Sheet 12: Cash Conversion Cycle (FASE 1)
        cash_cycle = intrinsic.get('cash_conversion_cycle', {})
        if cash_cycle:
            ccc_data = [{
                'DSO (Days)': f"{cash_cycle.get('dso', 0):.0f}",
                'DIO (Days)': f"{cash_cycle.get('dio', 0):.0f}",
                'DPO (Days)': f"{cash_cycle.get('dpo', 0):.0f}",
                'Cash Conversion Cycle (Days)': f"{cash_cycle.get('ccc', 0):.0f}",
                'YoY Change (Days)': f"{cash_cycle.get('yoy_change', 0):+.0f}",
                'Trend': cash_cycle.get('trend', 'N/A'),
                'Assessment': cash_cycle.get('assessment', 'N/A')
            }]
            pd.DataFrame(ccc_data).to_excel(writer, sheet_name='Cash Conversion Cycle', index=False)

        # Sheet 13: Operating Leverage (FASE 1)
        operating_lev = intrinsic.get('operating_leverage', {})
        if operating_lev:
            ol_data = [{
                'Operating Leverage': f"{operating_lev.get('operating_leverage', 0):.2f}x",
                '2Y Avg OL': f"{operating_lev.get('ol_avg_2y', 0):.2f}x",
                'Revenue Change %': f"{operating_lev.get('revenue_change_%', 0):+.1f}%",
                'EBIT Change %': f"{operating_lev.get('ebit_change_%', 0):+.1f}%",
                'Risk Level': operating_lev.get('risk_level', 'N/A'),
                'Assessment': operating_lev.get('assessment', 'N/A')
            }]
            pd.DataFrame(ol_data).to_excel(writer, sheet_name='Operating Leverage', index=False)

        # Sheet 14: Reinvestment Quality (FASE 1)
        reinvestment = intrinsic.get('reinvestment_quality', {})
        if reinvestment:
            reinv_data = [{
                'Reinvestment Rate %': f"{reinvestment.get('reinvestment_rate_%', 0):.1f}%",
                'Revenue Growth %': f"{reinvestment.get('revenue_growth_%', 0):.1f}%",
                'Growth ROIC': f"{reinvestment.get('growth_roic', 0):.2f}x",
                'Net Capex ($B)': f"${reinvestment.get('net_capex', 0)/1e9:.2f}",
                'Delta Working Capital ($B)': f"${reinvestment.get('delta_wc', 0)/1e9:.2f}",
                'Quality': reinvestment.get('quality', 'N/A'),
                'Assessment': reinvestment.get('assessment', 'N/A')
            }]
            pd.DataFrame(reinv_data).to_excel(writer, sheet_name='Reinvestment Quality', index=False)

        # Sheet 15: Economic Profit / EVA (FASE 2)
        eva = intrinsic.get('economic_profit', {})
        if eva:
            eva_data = [{
                'Economic Value Added': eva.get('eva_formatted', 'N/A'),
                'EVA Margin %': f"{eva.get('eva_margin_%', 0):.1f}%",
                'NOPAT': eva.get('nopat_formatted', 'N/A'),
                'Invested Capital': eva.get('ic_formatted', 'N/A'),
                'WACC %': f"{eva.get('wacc', 0):.1f}%",
                'Capital Charge': eva.get('capital_charge_formatted', 'N/A'),
                'Trend': eva.get('trend', 'N/A'),
                '5Y Avg EVA': eva.get('avg_eva_formatted', 'N/A'),
                'Grade': eva.get('grade', 'N/A'),
                'Assessment': eva.get('assessment', 'N/A')
            }]
            pd.DataFrame(eva_data).to_excel(writer, sheet_name='Economic Profit (EVA)', index=False)

        # Sheet 16: Capital Allocation Score (FASE 2)
        cap_alloc = intrinsic.get('capital_allocation', {})
        if cap_alloc:
            cap_alloc_data = [{
                'Score': f"{cap_alloc.get('score', 0):.0f}/100",
                'Grade': cap_alloc.get('grade', 'N/A'),
                'Free Cash Flow': cap_alloc.get('fcf_formatted', 'N/A'),
                'Dividend % of FCF': f"{cap_alloc.get('dividend_%_fcf', 0):.1f}%",
                'Buyback % of FCF': f"{cap_alloc.get('buyback_%_fcf', 0):.1f}%",
                'Debt Paydown % of FCF': f"{cap_alloc.get('debt_paydown_%_fcf', 0):.1f}%",
                'Retained % of FCF': f"{cap_alloc.get('retained_%_fcf', 0):.1f}%",
                'Shareholder Return %': f"{cap_alloc.get('shareholder_return_%', 0):.1f}%",
                'Payout Ratio %': f"{cap_alloc.get('payout_ratio_%', 0):.1f}%",
                'Dividend Years': cap_alloc.get('dividend_years', 0),
                'Dividend Consistency': cap_alloc.get('dividend_consistency', 'N/A'),
                'Share Count Trend': cap_alloc.get('share_count_trend', 'N/A'),
                'Assessment': cap_alloc.get('assessment', 'N/A')
            }]
            pd.DataFrame(cap_alloc_data).to_excel(writer, sheet_name='Capital Allocation', index=False)

            # Add factors to a separate row
            factors = cap_alloc.get('factors', [])
            if factors:
                factors_data = [{'Key Factors': factor} for factor in factors]
                pd.DataFrame(factors_data).to_excel(writer, sheet_name='Capital Alloc Factors', index=False)

        # Sheet 17: Interest Rate Sensitivity (FASE 2)
        rate_sens = intrinsic.get('interest_rate_sensitivity', {})
        if rate_sens and rate_sens.get('applicable', False):
            rate_data = [{
                'Net Interest Margin %': f"{rate_sens.get('nim_%', 0):.2f}%",
                'NIM Trend': rate_sens.get('nim_trend', 'N/A'),
                'NIM YoY Change': f"{rate_sens.get('nim_yoy_change', 0):+.2f}%",
                '5Y Avg NIM %': f"{rate_sens.get('nim_5y_avg', 0):.2f}%",
                'Net Interest Income': rate_sens.get('nii_formatted', 'N/A'),
                'Loan/Deposit Ratio %': f"{rate_sens.get('loan_to_deposit_%', 0):.1f}%" if rate_sens.get('loan_to_deposit_%') else 'N/A',
                'Assessment': rate_sens.get('assessment', 'N/A'),
                'Rate Sensitivity': rate_sens.get('rate_sensitivity', 'N/A')
            }]
            pd.DataFrame(rate_data).to_excel(writer, sheet_name='Interest Rate Sensitivity', index=False)

            # Add NIM history
            nim_hist = rate_sens.get('nim_history', [])
            if nim_hist:
                hist_data = [{'Year': f"Y-{i}", 'NIM %': f"{nim:.2f}%"} for i, nim in enumerate(nim_hist)]
                pd.DataFrame(hist_data).to_excel(writer, sheet_name='NIM History', index=False)

        # Sheet 18: Insider Trading (Premium Feature)
        insider = intrinsic.get('insider_trading', {})
        if insider and insider.get('available', False):
            insider_data = [{
                'Signal': insider.get('signal', 'N/A'),
                'Score': f"{insider.get('score', 0):.0f}/100",
                'Assessment': insider.get('assessment', 'N/A'),
                'Buys (12M)': insider.get('buy_count_12m', 0),
                'Sells (12M)': insider.get('sell_count_12m', 0),
                'Recent Buys (3M)': insider.get('recent_buys_3m', 0),
                'Unique Buyers (3M)': insider.get('unique_buyers_3m', 0),
                'Executive Buys': insider.get('executive_buys', 0),
                'Buy Value': insider.get('buy_value_formatted', 'N/A'),
                'Sell Value': insider.get('sell_value_formatted', 'N/A'),
                'Net Position': insider.get('net_position', 'N/A')
            }]
            pd.DataFrame(insider_data).to_excel(writer, sheet_name='Insider Trading', index=False)

            # Add recent trades detail
            recent_trades = insider.get('recent_trades', [])
            if recent_trades:
                trades_data = []
                for trade in recent_trades[:10]:  # Top 10 recent buys
                    trades_data.append({
                        'Date': trade.get('date', 'N/A'),
                        'Insider': trade.get('name', 'N/A'),
                        'Type': trade.get('type', 'N/A'),
                        'Shares': trade.get('shares', 0),
                        'Value': f"${trade.get('value', 0)/1e3:.0f}K",
                        'Executive': 'Yes' if trade.get('is_executive', False) else 'No'
                    })
                pd.DataFrame(trades_data).to_excel(writer, sheet_name='Recent Insider Buys', index=False)

        # Sheet 19: Earnings Sentiment (Premium Feature)
        sentiment = intrinsic.get('earnings_sentiment', {})
        if sentiment and sentiment.get('available', False):
            sentiment_data = [{
                'Tone': sentiment.get('tone', 'N/A'),
                'Grade': sentiment.get('grade', 'N/A'),
                'Assessment': sentiment.get('assessment', 'N/A'),
                'Net Sentiment': f"{sentiment.get('net_sentiment', 0):.1f}",
                'Confidence %': f"{sentiment.get('confidence_%', 0):.0f}%",
                'Positive %': f"{sentiment.get('positive_%', 0):.1f}%",
                'Negative %': f"{sentiment.get('negative_%', 0):.1f}%",
                'Caution %': f"{sentiment.get('caution_%', 0):.1f}%",
                'Positive Mentions': sentiment.get('positive_mentions', 0),
                'Negative Mentions': sentiment.get('negative_mentions', 0),
                'Caution Mentions': sentiment.get('caution_mentions', 0),
                'Has Guidance': 'Yes' if sentiment.get('has_guidance', False) else 'No',
                'Quarter': sentiment.get('quarter', 'N/A'),
                'Transcript Date': sentiment.get('transcript_date', 'N/A')
            }]
            pd.DataFrame(sentiment_data).to_excel(writer, sheet_name='Earnings Sentiment', index=False)

        # Auto-adjust all sheets
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width

    output.seek(0)
    return output.getvalue()

def recalculate_scores(df, weight_quality, weight_value, threshold_buy, threshold_monitor,
                       threshold_quality_exceptional, exclude_reds):
    """
    Recalculate composite scores and decisions with new parameters.
    This allows interactive adjustment without re-running the entire pipeline.
    """
    df = df.copy()

    # Recalculate composite score with new weights
    df['composite_0_100'] = (
        weight_quality * df['quality_score_0_100'] +
        weight_value * df['value_score_0_100']
    )

    # Recalculate decision logic
    def decide(row):
        composite = row.get('composite_0_100', 0)
        quality = row.get('quality_score_0_100', 0)
        value = row.get('value_score_0_100', 0)
        status = row.get('guardrail_status', 'AMBAR')

        # Get revenue & quality metrics for decision logic
        revenue_growth = row.get('revenue_growth_3y')
        degradation_delta = row.get('quality_degradation_delta')
        degradation_type = row.get('quality_degradation_type')

        # ROJO = Auto AVOID UNLESS exceptional fundamentals override
        # Allow ROJO to pass if:
        # 1. Quality score exceptional (≥80) - proves underlying business quality
        # 2. Composite score high (≥75) - proves valuation + quality
        # 3. Revenue growing (not declining) - proves business momentum
        # This catches cases like LLY where CCC deterioration is temporary/strategic
        if exclude_reds and status == 'ROJO':
            # Check for override conditions
            can_override = (
                quality >= 80 and  # Exceptional quality (top quartile)
                composite >= 75 and  # High composite score
                (revenue_growth is None or revenue_growth >= 0)  # Revenue not declining
            )

            if can_override:
                # Allow to proceed with standard decision logic
                # But flag it in the reason for transparency
                pass  # Continue to normal decision logic below
            else:
                return 'AVOID', 'RED guardrails (accounting concerns)'

        # Exceptional composite score = BUY even with AMBAR/ROJO (if passed override)
        # BUT: Block if revenue declining OR quality deteriorating (Piotroski for VALUE, Mohanram for GROWTH)

        if composite >= 85:  # Raised from 80 to 85 (more selective)
            # Check 1: Revenue decline (universal check)
            if revenue_growth is not None and revenue_growth < 0:
                return 'MONITOR', f'High score ({composite:.0f}) but revenue declining ({revenue_growth:.1f}% 3Y)'

            # Check 2: Quality degradation (Piotroski F-Score for VALUE, Mohanram G-Score for GROWTH)
            if degradation_delta is not None and degradation_delta < 0:
                score_name = 'F-Score' if degradation_type == 'VALUE' else 'G-Score'
                return 'MONITOR', f'High score ({composite:.0f}) but {degradation_type} quality degrading ({score_name} Δ{degradation_delta})'

            # Add RED override flag if applicable
            suffix = ' (RED override - quality Q:{:.0f} justifies)'.format(quality) if status == 'ROJO' else ''
            return 'BUY', f'Exceptional score ({composite:.0f} ≥ 85){suffix}'

        # Exceptional Quality companies = BUY even with moderate composite
        # Relaxed for AMBAR/ROJO: if very high quality, accept lower composite
        # BUT: Block if revenue declining OR quality deteriorating (Piotroski/Mohanram)
        if quality >= threshold_quality_exceptional:
            # Check 1: Revenue decline
            if revenue_growth is not None and revenue_growth < 0:
                return 'MONITOR', f'High quality (Q:{quality:.0f}) but revenue declining ({revenue_growth:.1f}% 3Y)'

            # Check 2: Quality degradation (F-Score for VALUE, G-Score for GROWTH)
            if degradation_delta is not None and degradation_delta < 0:
                score_name = 'F-Score' if degradation_type == 'VALUE' else 'G-Score'
                return 'MONITOR', f'High quality (Q:{quality:.0f}) but {degradation_type} quality degrading ({score_name} Δ{degradation_delta})'

            # Add RED override flag if applicable
            suffix = ' (RED override)' if status == 'ROJO' else ''

            if composite >= 60:
                return 'BUY', f'Exceptional quality (Q:{quality:.0f} ≥ {threshold_quality_exceptional}, C:{composite:.0f} ≥ 60){suffix}'
            elif composite >= 55 and status != 'ROJO':  # Keep ROJO block for very low composite
                return 'BUY', f'High quality override (Q:{quality:.0f} ≥ {threshold_quality_exceptional}, C:{composite:.0f} ≥ 55)'

        # High Quality with AMBAR can still be BUY if composite is decent
        # This prevents great companies (GOOGL, META) from being blocked by AMBAR
        if quality >= 70 and composite >= threshold_buy and status == 'AMBAR':
            return 'BUY', f'High quality + AMBAR (Q:{quality:.0f} ≥ 70, C:{composite:.0f} ≥ {threshold_buy})'

        # Good score + Clean guardrails = BUY
        if composite >= threshold_buy and status == 'VERDE':
            return 'BUY', f'Score {composite:.0f} ≥ {threshold_buy} + Clean'

        # Middle tier = MONITOR
        if composite >= threshold_monitor:
            return 'MONITOR', f'Score {composite:.0f} in range [{threshold_monitor}, {threshold_buy})'

        # Low score = AVOID
        return 'AVOID', f'Score {composite:.0f} < {threshold_monitor}'

    # Apply decision logic and capture reason
    df[['decision', 'decision_reason']] = df.apply(lambda row: pd.Series(decide(row)), axis=1)

    return df

def get_results_with_current_params():
    """
    Get results from session_state and recalculate with current sidebar parameters.
    Returns None if no results available.
    """
    if 'results' not in st.session_state:
        return None

    df = st.session_state['results']

    # Get current sidebar parameters (these are defined later but accessible)
    w_quality = st.session_state.get('weight_quality_slider', 0.65)
    w_value = 1.0 - w_quality
    t_buy = st.session_state.get('threshold_buy_slider', 65)
    t_monitor = st.session_state.get('threshold_monitor_slider', 45)
    t_quality_exc = st.session_state.get('threshold_quality_exceptional_slider', 80)
    excl_reds = st.session_state.get('exclude_reds_checkbox', True)

    # Recalculate with current parameters
    return recalculate_scores(df, w_quality, w_value, t_buy, t_monitor, t_quality_exc, excl_reds)


def display_smart_stop_loss(stop_loss_data, current_price):
    """
    Display SmartDynamicStopLoss data in Streamlit.

    Args:
        stop_loss_data: Stop loss dict from risk_management
        current_price: Current stock price
    """
    # Check if it's the new SmartDynamicStopLoss format
    if 'tier' in stop_loss_data:
        # === NEW FORMAT: Smart Dynamic StopLoss ===
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 1.5rem; border-radius: 12px; margin-bottom: 1.5rem;'>
            <h3 style='margin: 0; color: white;'><i class="bi bi-shield-check"></i> Smart Dynamic StopLoss</h3>
            <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem;'>
                Sistema Adaptativo por Quality Tiers
            </p>
        </div>
        """, unsafe_allow_html=True)
        st.caption("Basado en ATR (14d) + Clasificación de Riesgo + Lifecycle Management")
        st.markdown("---")

        # === TIER CLASSIFICATION ===
        tier = stop_loss_data.get('tier', 0)
        tier_name = stop_loss_data.get('tier_name', 'N/A')
        tier_description = stop_loss_data.get('tier_description', '')

        # Tier configuration with colors and icons
        tier_config = {
            1: {
                'icon': '<i class="bi bi-shield-fill"></i>',
                'color': '#3498db',
                'label': 'TIER 1: Defensivo'
            },
            2: {
                'icon': '<i class="bi bi-shield-fill-check"></i>',
                'color': '#9b59b6',
                'label': 'TIER 2: Core Growth'
            },
            3: {
                'icon': '<i class="bi bi-lightning-fill"></i>',
                'color': '#e74c3c',
                'label': 'TIER 3: Especulativo'
            }
        }

        tier_info = tier_config.get(tier, {
            'icon': '<i class="bi bi-shield"></i>',
            'color': '#95a5a6',
            'label': 'UNKNOWN TIER'
        })

        # === TIER & STATE IN 2-COLUMN CARDS ===
        col_tier, col_state = st.columns([1, 1])

        with col_tier:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, {tier_info['color']} 0%, {tier_info['color']}dd 100%);
                        padding: 1.5rem; border-radius: 12px; color: white;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.15); min-height: 180px;'>
                <div style='text-align: center;'>
                    <div style='font-size: 3rem; margin-bottom: 0.75rem;'>{tier_info['icon']}</div>
                    <div style='font-size: 1.2rem; font-weight: 700; margin-bottom: 0.5rem;'>{tier_info['label']}</div>
                    <div style='font-size: 0.9rem; opacity: 0.95; margin-bottom: 0.75rem;'>{tier_description}</div>
                    <div style='background: rgba(255,255,255,0.2); padding: 0.5rem; border-radius: 6px; font-size: 0.8rem;'>
                        Risk-based classification (volatility + beta)
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # === MARKET STATE BOX (Professional Cards) ===
        with col_state:
            market_state = stop_loss_data.get('market_state', 'N/A')
            state_emoji = stop_loss_data.get('state_emoji', '')

            # State configuration
            state_cards = {
                'DOWNTREND': {
                    'color': '#dc3545',
                    'action': 'EVITAR o SALIR',
                    'icon_size': '3rem'
                },
                'PARABOLIC_CLIMAX': {
                    'color': '#ff6b35',
                    'action': 'ADVERTENCIA CRÍTICA',
                    'icon_size': '3rem',
                    'details': [
                        'Si NO tienes: NO COMPRAR',
                        'Si YA tienes: ASEGURAR GANANCIAS',
                        'Movimiento vertical insostenible',
                        'Alta probabilidad corrección -15% a -30%'
                    ]
                },
                'POWER_TREND': {
                    'color': '#28a745',
                    'action': 'Dejar Correr',
                    'icon_size': '3rem'
                },
                'BLUE_SKY_ATH': {
                    'color': '#667eea',
                    'action': 'Dejar Correr',
                    'icon_size': '3rem'
                },
                'PULLBACK_FLAG': {
                    'color': '#17a2b8',
                    'action': 'Dar Aire / Monitor',
                    'icon_size': '3rem'
                },
                'CHOPPY_SIDEWAYS': {
                    'color': '#ffc107',
                    'action': 'Usar Stop Conservador',
                    'icon_size': '3rem'
                },
                'ENTRY_BREAKOUT': {
                    'color': '#6c757d',
                    'action': 'Usar Stop Conservador',
                    'icon_size': '3rem'
                }
            }

            state_info = state_cards.get(market_state, {
                'color': '#6c757d',
                'action': 'Monitor',
                'icon_size': '3rem'
            })

            # Build card HTML
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, {state_info['color']} 0%, {state_info['color']}dd 100%);
                        padding: 1.5rem; border-radius: 12px; color: white;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.15); min-height: 180px;'>
                <div style='text-align: center;'>
                    <div style='font-size: {state_info['icon_size']}; margin-bottom: 0.75rem;'>{state_emoji}</div>
                    <div style='font-size: 1.1rem; font-weight: 700; margin-bottom: 0.5rem;'>{market_state.replace('_', ' ')}</div>
                    <div style='background: rgba(255,255,255,0.2); padding: 0.75rem; border-radius: 6px; margin-top: 0.75rem;'>
                        <div style='font-size: 0.9rem; font-weight: 600;'>ACCIÓN:</div>
                        <div style='font-size: 1rem; margin-top: 0.25rem;'>{state_info['action']}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Show additional details for PARABOLIC_CLIMAX
            if market_state == 'PARABOLIC_CLIMAX' and 'details' in state_info:
                with st.expander("⚠️ Ver Detalles Críticos"):
                    for detail in state_info['details']:
                        st.markdown(f"• {detail}")
                    st.caption('Regla: "No compres cohetes en el aire"')

        # === ACTIVE STOP (Main recommendation with professional card) ===
        st.markdown("---")
        st.markdown("""
        <div style='background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
                    padding: 1rem; border-radius: 10px; margin-bottom: 1rem;'>
            <div style='color: white; font-size: 1.2rem; font-weight: 700; text-align: center;'>
                <i class="bi bi-shield-fill-check"></i> Stop Loss Activo
            </div>
        </div>
        """, unsafe_allow_html=True)

        active_stop = stop_loss_data.get('active_stop', {})

        # Better formatting for status
        if market_state == 'NO_POSITION':
            status_display = "Sin Posición"
            status_icon = ""
        elif market_state == 'DOWNTREND':
            status_display = "Tendencia Bajista"
            status_icon = "▼"
        elif market_state == 'PARABOLIC_CLIMAX':
            status_display = "Clímax Parabólico"
            status_icon = "⚠"
        elif market_state == 'POWER_TREND':
            status_display = "Tendencia Fuerte"
            status_icon = "↑"
        elif market_state == 'BLUE_SKY_ATH':
            status_display = "All-Time High"
            status_icon = "★"
        elif market_state == 'PULLBACK_FLAG':
            status_display = "Pullback"
            status_icon = "◐"
        elif market_state == 'CHOPPY_SIDEWAYS':
            status_display = "Lateral"
            status_icon = "↔"
        elif market_state == 'ENTRY_BREAKOUT':
            status_display = "Breakout"
            status_icon = "⊚"
        else:
            status_display = market_state.replace('_', ' ').title()
            status_icon = ""

        # Calculate distance value for display
        distance_str = active_stop.get('distance', 'N/A')
        try:
            distance_val = float(distance_str.replace('%', ''))
            distance_display = f"{distance_str}"
            risk_display = f"{abs(distance_val):.1f}% riesgo"
        except:
            distance_display = distance_str
            risk_display = ""

        # Professional metrics card
        stop_price_val = active_stop.get('price', 'N/A')
        st.markdown(f"""
        <div style='background: linear-gradient(to right, #f8f9fa, #e9ecef);
                    padding: 1.5rem; border-radius: 10px; border: 2px solid #28a745;'>
            <div style='display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem;'>
                <div style='text-align: center;'>
                    <div style='font-size: 0.85rem; color: #6c757d; font-weight: 600; margin-bottom: 0.5rem;'>
                        STOP PRICE
                    </div>
                    <div style='font-size: 2rem; font-weight: 700; color: #dc3545;'>
                        {stop_price_val}
                    </div>
                    <div style='font-size: 0.75rem; color: #6c757d; margin-top: 0.25rem;'>
                        Precio objetivo
                    </div>
                </div>
                <div style='text-align: center;'>
                    <div style='font-size: 0.85rem; color: #6c757d; font-weight: 600; margin-bottom: 0.5rem;'>
                        DISTANCE
                    </div>
                    <div style='font-size: 2rem; font-weight: 700; color: #495057;'>
                        {distance_display}
                    </div>
                    <div style='font-size: 0.75rem; color: #dc3545; margin-top: 0.25rem; font-weight: 600;'>
                        {risk_display}
                    </div>
                </div>
                <div style='text-align: center;'>
                    <div style='font-size: 0.85rem; color: #6c757d; font-weight: 600; margin-bottom: 0.5rem;'>
                        ESTADO
                    </div>
                    <div style='font-size: 1.5rem; font-weight: 700; color: #495057; margin-bottom: 0.25rem;'>
                        {status_icon}
                    </div>
                    <div style='font-size: 0.9rem; color: #495057; font-weight: 600;'>
                        {status_display}
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # === SMART RATIONALE (Bullet Points) ===
        # === ANALYSIS DETAILS ===
        st.markdown("---")
        st.markdown("#### Análisis de Mercado")

        state_rationale = stop_loss_data.get('state_rationale', '')
        if state_rationale:
            # Split rationale by " | " if present
            rationale_parts = state_rationale.split(' | ')

            # Determine alert level
            if market_state == 'DOWNTREND':
                alert_color = '#dc3545'
                alert_bg = '#fff5f5'
                alert_title = '<i class="bi bi-exclamation-octagon-fill"></i> RISK ALERT'
            elif market_state == 'PARABOLIC_CLIMAX':
                alert_color = '#ffc107'
                alert_bg = '#fffbf0'
                alert_title = '<i class="bi bi-exclamation-triangle-fill"></i> CLIMAX ZONE'
            elif market_state == 'POWER_TREND':
                alert_color = '#28a745'
                alert_bg = '#d4edda'
                alert_title = '<i class="bi bi-arrow-up-circle-fill"></i> STRONG TREND'
            else:
                alert_color = '#17a2b8'
                alert_bg = '#d1ecf1'
                alert_title = '<i class="bi bi-info-circle-fill"></i> ANALYSIS'

            # Display as styled card
            st.markdown(f"""
            <div style='background: {alert_bg}; padding: 1.25rem; border-radius: 10px;
                        border-left: 5px solid {alert_color}; margin-bottom: 1rem;'>
                <div style='font-weight: 700; font-size: 1.05rem; color: {alert_color}; margin-bottom: 0.75rem;'>
                    {alert_title}
                </div>
            """, unsafe_allow_html=True)

            # Display rationale parts as styled bullets
            for part in rationale_parts[:3]:  # Show up to 3 parts
                if part.strip():
                    st.markdown(f"""
                    <div style='color: #495057; font-size: 0.95rem; line-height: 1.6; margin-bottom: 0.5rem;'>
                        <i class="bi bi-chevron-right" style='color: {alert_color};'></i> {part.strip()}
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)


        # === BASE PARAMETERS ===
        with st.expander("Technical Indicators"):
            params = stop_loss_data.get('parameters', {})
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("ATR (14d)", f"${params.get('atr_14', 'N/A')}",
                         help="Average True Range - Volatilidad diaria")
                st.write(f"**Swing Low 20d:** ${params.get('swing_low_20', 'N/A')}")

            with col2:
                adx_val = params.get('adx', 'N/A')
                if adx_val != 'N/A':
                    adx_strength = "Fuerte" if float(adx_val) > 25 else "Débil"
                    st.metric("ADX", adx_val,
                             delta=adx_strength,
                             help="Fuerza de tendencia (>25 = fuerte)")
                else:
                    st.metric("ADX", "N/A")
                st.write(f"**EMA 10:** ${params.get('ema_10', 'N/A')}")

            with col3:
                slope_val = params.get('sma_slope', 'N/A')
                if slope_val != 'N/A':
                    slope_dir = "↗️ Alcista" if float(slope_val) > 0.05 else "↘️ Bajista" if float(slope_val) < -0.05 else "➡️ Lateral"
                    st.metric("SMA Slope", f"{slope_val}%",
                             delta=slope_dir,
                             help="Dirección de MA50")
                else:
                    st.metric("SMA Slope", "N/A")
                st.write(f"**EMA 20:** ${params.get('ema_20', 'N/A')}")

            if params.get('is_ath_breakout'):
                st.warning(f"{params.get('ath_note', 'ATH Breakout detected')}")

        # === CONFIGURATION ===
        with st.expander("Tier Configuration"):
            config = stop_loss_data.get('config', {})
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Multiplicador Inicial:** {config.get('initial_multiplier', 'N/A')}x ATR")
                st.write(f"**Multiplicador Trailing:** {config.get('trailing_multiplier', 'N/A')}x ATR")
            with col2:
                st.write(f"**Hard Cap:** {config.get('hard_cap_pct', 'N/A')}%")
                st.write(f"**Ancla Técnica:** {config.get('anchor', 'N/A')}")

        # === TIER COMPARISON ===
        with st.expander("Stop Comparison by Quality Tier (Reference)"):
            tier_stops = stop_loss_data.get('tier_stops', {})

            for tier_key, tier_data in tier_stops.items():
                tier_label = tier_key.replace('_', ' ').title()
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.write(f"**{tier_label}**")
                with col2:
                    st.write(tier_data.get('price', 'N/A'))
                with col3:
                    st.write(tier_data.get('distance', 'N/A'))
                st.caption(f"Formula: {tier_data.get('formula', 'N/A')}")

        # === NOTES ===
        notes = stop_loss_data.get('notes', [])
        if notes:
            with st.expander("System Notes (Advanced)"):
                for note in notes:
                    if note:
                        st.caption(f"• {note}")

    else:
        # === LEGACY FORMAT ===
        st.markdown("###  Stop Loss Recommendations")
        st.caption("Legacy format")

        recommended = stop_loss_data.get('recommended', 'N/A')
        stops = stop_loss_data.get('stops', {})

        st.write(f"**Recomendado:** {recommended.upper()}")

        for stop_type in ['aggressive', 'moderate', 'conservative']:
            if stop_type in stops:
                s = stops[stop_type]
                with st.expander(f"{stop_type.upper()} Stop"):
                    st.metric("Level", s.get('level', 'N/A'), delta=s.get('distance', 'N/A'))
                    st.caption(s.get('rationale', 'N/A'))

        note = stop_loss_data.get('note', '')
        if note:
            st.info(note)


def display_entry_strategy(entry_strategy):
    """
    Display STATE-BASED Entry Strategy with institutional-grade execution plan.

    Shows:
    - Strategy type (SNIPER, BREAKOUT, PYRAMID)
    - Order table with specific prices and order types
    - Invalidation levels
    - Structural support/resistance levels
    """
    # Modern section header
    st.markdown("""
    <div style='background: linear-gradient(to right, #11998e, #38ef7d); padding: 1rem;
                border-radius: 8px; margin-bottom: 1rem;'>
        <h3 style='margin: 0; color: white;'><i class="bi bi-crosshair"></i> Entry Strategy & Execution</h3>
        <p style='margin: 0.25rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem;'>
            State-based entry plan with specific price levels
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Check for VETO
    if entry_strategy.get('veto_active'):
        st.markdown("""
        <div style='background: #f8d7da; padding: 1.5rem; border-radius: 10px;
                    border-left: 6px solid #dc3545; margin: 1rem 0;'>
            <h3 style='color: #721c24; margin-top: 0;'><i class="bi bi-shield-x"></i> VETO ACTIVE - NO ENTRY</h3>
            <div style='color: #721c24;'>
                <strong>Strategy:</strong> {}</div>
        </div>
        """.format(entry_strategy.get('strategy', 'NO ENTRY')), unsafe_allow_html=True)
        st.write(f"**Rationale:** {entry_strategy.get('rationale', 'N/A')}")
        market_state = entry_strategy.get('market_state', 'Unknown')
        if market_state == 'PARABOLIC_CLIMAX':
            st.caption("📚 Academic Evidence: Daniel & Moskowitz (2016) - Momentum Crashes")
        return

    # Get strategy details
    strategy_name = entry_strategy.get('strategy', 'N/A')
    strategy_type = entry_strategy.get('strategy_type', 'UNKNOWN')
    state = entry_strategy.get('state', 'UNKNOWN')
    rationale = entry_strategy.get('rationale', 'N/A')
    tranches = entry_strategy.get('tranches', [])
    invalidation = entry_strategy.get('invalidation', {})
    structural_levels = entry_strategy.get('structural_levels', {})

    # Strategy header with visual card
    strategy_config = {
        'SNIPER': {'icon': '<i class="bi bi-crosshair"></i>', 'color': '#dc3545', 'bg': '#f8d7da'},
        'BREAKOUT': {'icon': '<i class="bi bi-rocket-takeoff"></i>', 'color': '#28a745', 'bg': '#d4edda'},
        'PYRAMID': {'icon': '<i class="bi bi-bar-chart-steps"></i>', 'color': '#007bff', 'bg': '#d1ecf1'},
        'CONSERVATIVE': {'icon': '<i class="bi bi-shield"></i>', 'color': '#6c757d', 'bg': '#e2e3e5'},
        'NONE': {'icon': '<i class="bi bi-pause"></i>', 'color': '#ffc107', 'bg': '#fff3cd'}
    }

    config = strategy_config.get(strategy_type, {'icon': '<i class="bi bi-question-circle" style="font-size: 3rem;"></i>', 'color': '#6c757d', 'bg': '#e2e3e5'})

    st.markdown(f"""
    <div style='background: {config['bg']}; padding: 1.5rem; border-radius: 10px;
                border-left: 6px solid {config['color']}; margin: 1rem 0;'>
        <h3 style='color: {config['color']}; margin-top: 0;'>
            {config['icon']} {strategy_name}
        </h3>
        <div style='font-size: 0.9rem; color: #495057; margin-top: 0.5rem;'>
            <strong>Market State:</strong> {state}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Rationale box with professional styling
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 1.5rem; border-radius: 12px; margin: 1.5rem 0;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);'>
        <div style='color: white;'>
            <div style='font-size: 1.2rem; font-weight: 700; margin-bottom: 0.75rem;'>
                <i class="bi bi-clipboard-check-fill"></i> Execution Plan
            </div>
            <div style='font-size: 0.95rem; line-height: 1.6; opacity: 0.95;'>
                {rationale}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ========== TRANCHES TABLE ==========
    if tranches:
        st.markdown("""
        <div style='background: linear-gradient(to right, #f8f9fa, #e9ecef);
                    padding: 1rem; border-radius: 10px; margin: 1rem 0;
                    border-left: 4px solid #28a745;'>
            <div style='font-size: 1.1rem; font-weight: 700; color: #495057;'>
                <i class="bi bi-list-check"></i> Order Execution Plan
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Create DataFrame for table display
        table_data = []
        for t in tranches:
            table_data.append({
                'Tranche': f"#{t['number']}",
                'Size': t['size'],
                'Order Type': t['order_type'],
                'Price': f"${t['price']:.2f}",
                'Trigger / Condition': t['trigger']
            })

        # Display as table
        import pandas as pd
        df_orders = pd.DataFrame(table_data)
        st.dataframe(
            df_orders,
            use_container_width=True,
            hide_index=True,
            column_config={
                'Tranche': st.column_config.TextColumn('Lote', width='small'),
                'Size': st.column_config.TextColumn('Tamaño', width='small'),
                'Order Type': st.column_config.TextColumn('Tipo Orden', width='medium'),
                'Price': st.column_config.TextColumn('Precio Objetivo', width='medium'),
                'Trigger / Condition': st.column_config.TextColumn('Condición / Gatillo', width='large')
            }
        )

        # Individual tranche details (expandable)
        with st.expander("📊 Details by Tranche"):
            for t in tranches:
                tranche_icon = '<i class="bi bi-1-circle-fill"></i>' if t['number'] == 1 else \
                              '<i class="bi bi-2-circle-fill"></i>' if t['number'] == 2 else \
                              '<i class="bi bi-3-circle-fill"></i>'

                primary_badge = "" if not t['is_primary'] else \
                    '<span style="background: #28a745; color: white; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.7rem; margin-left: 0.5rem;">PRIMARY</span>'

                st.markdown(f"""
                <div style='background: #f8f9fa; padding: 1rem; border-radius: 8px;
                            border-left: 3px solid #667eea; margin-bottom: 1rem;'>
                    <div style='font-size: 1rem; font-weight: 700; color: #495057; margin-bottom: 0.5rem;'>
                        {tranche_icon} Tranche #{t['number']} {primary_badge}
                    </div>
                    <div style='font-size: 0.9rem; color: #6c757d;'>
                        <strong>Tamaño:</strong> {t['size']}<br>
                        <strong>Tipo:</strong> {t['order_type']}<br>
                        <strong>Precio:</strong> ${t['price']:.2f}<br>
                        <strong>Gatillo:</strong> {t['trigger']}
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # ========== INVALIDATION ==========
    if invalidation:
        inv_price = invalidation.get('price', 0)
        inv_action = invalidation.get('action', 'N/A')

        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
                    padding: 1.5rem; border-radius: 12px; margin: 1.5rem 0;
                    box-shadow: 0 4px 12px rgba(220, 53, 69, 0.3);'>
            <div style='color: white; text-align: center;'>
                <div style='font-size: 2rem; margin-bottom: 0.5rem;'>
                    <i class="bi bi-x-octagon-fill"></i>
                </div>
                <div style='font-size: 1.3rem; font-weight: 700; margin-bottom: 0.75rem;'>
                    Invalidación del Setup
                </div>
                <div style='background: rgba(255,255,255,0.2); padding: 1rem; border-radius: 8px; margin-bottom: 0.75rem;'>
                    <div style='font-size: 0.9rem; opacity: 0.9; margin-bottom: 0.25rem;'>
                        PRECIO INVALIDACIÓN
                    </div>
                    <div style='font-size: 2rem; font-weight: 700;'>
                        ${inv_price:.2f}
                    </div>
                </div>
                <div style='font-size: 0.95rem; opacity: 0.95; line-height: 1.5;'>
                    {inv_action}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ========== STRUCTURAL LEVELS (expandable) ==========
    if structural_levels:
        with st.expander("Structural Technical Levels"):
            st.caption("Niveles clave calculados por el sistema")
            for key, value in structural_levels.items():
                if isinstance(value, (int, float)) and value > 0:
                    label = key.replace('_', ' ').title()
                    st.write(f"**{label}:** ${value:.2f}")


def display_take_profit(profit_taking):
    """
    Display professional Take Profit strategies with modern, interactive UI.

    Three strategies:
    - Compounder (Tier 1): Hold forever, only trailing stop
    - Swing (Tier 2): 3R rule, scale at targets
    - Sniper (Tier 3): Aggressive 2R/4R scaling
    """
    import pandas as pd

    # Get core data
    strategy = profit_taking.get('strategy', 'N/A')
    tier = profit_taking.get('tier', 'N/A')
    tier_name = profit_taking.get('tier_name', 'Unknown')
    philosophy = profit_taking.get('philosophy', '')
    action = profit_taking.get('action', '')
    targets = profit_taking.get('targets', [])
    keep_pct = profit_taking.get('keep_pct', 0)
    keep_stop = profit_taking.get('keep_stop', '')
    rationale = profit_taking.get('rationale', '')
    override = profit_taking.get('override', False)

    # Tier-specific styling with improved names
    tier_config = {
        1: {
            'icon': '<i class="bi bi-gem"></i>',
            'name': 'Elite Quality',
            'color': '#1E88E5',  # Blue
            'bg_color': '#E3F2FD',
            'strategy_icon': '<i class="bi bi-building"></i>',
            'recommendation': 'Estrategia conservadora: mantener posición, vender solo si fundamentales deterioran'
        },
        2: {
            'icon': '<i class="bi bi-star-fill"></i>',
            'name': 'Premium',
            'color': '#43A047',  # Green
            'bg_color': '#E8F5E9',
            'strategy_icon': '<i class="bi bi-graph-up"></i>',
            'recommendation': 'Estrategia balanceada: asegurar ganancias (3R) y dejar correr el resto con trailing stop'
        },
        3: {
            'icon': '<i class="bi bi-lightning-fill"></i>',
            'name': 'Especulativa',
            'color': '#FB8C00',  # Orange
            'bg_color': '#FFF3E0',
            'strategy_icon': '<i class="bi bi-bullseye"></i>',
            'recommendation': 'Estrategia agresiva: tomar ganancias frecuentemente, reducir exposición rápido'
        }
    }

    config = tier_config.get(tier, tier_config[2])

    # ========== HEADER: Emergency Override or Normal Strategy ==========
    if override or 'EMERGENCY' in strategy or 'PARABOLIC' in strategy:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #FF6B6B 0%, #C92A2A 100%);
                    padding: 20px; border-radius: 15px; margin-bottom: 20px;
                    box-shadow: 0 4px 15px rgba(255,107,107,0.4);">
            <h2 style="color: white; margin: 0; text-align: center;"> {strategy}</h2>
            <p style="color: white; margin: 10px 0 0 0; text-align: center; font-size: 18px;">
                 <b>URGENT ACTION REQUIRED</b>
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Normal header with tier-specific gradient (improved design)
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, {config['color']} 0%, {config['color']}dd 100%);
                    padding: 1.5rem; border-radius: 12px; margin-bottom: 1.5rem;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div style="flex: 1;">
                    <div style="color: white; font-size: 1.8rem; font-weight: 700; margin-bottom: 0.5rem;">
                        {config['icon']} {strategy}
                    </div>
                    <div style="color: white; font-size: 1rem; opacity: 0.95;">
                        {config['name']}
                    </div>
                </div>
                <div style="font-size: 4rem; opacity: 0.25; color: white;">
                    {config['strategy_icon']}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ========== KEY METRICS ROW ==========
    col1, col2, col3 = st.columns(3)

    with col1:
        if action:
            st.metric(
                label="Acción Recomendada",
                value=action.split()[0] if action else "N/A",
                help=action
            )
        else:
            tier_display = f"{config['icon']} {config['name']}"
            st.metric(label="Clasificación", value=tier_display)

    with col2:
        if keep_pct:
            st.metric(
                label="Keep % (Runner)",
                value=f"{keep_pct}%",
                help="Percentage to keep after taking profits"
            )

    with col3:
        if 'take_profit_rule' in profit_taking:
            rule = profit_taking['take_profit_rule']
            st.metric(
                label="Rule",
                value=rule.split()[0] if rule else "N/A",
                help=rule
            )

    # ========== PHILOSOPHY & RECOMMENDATION ==========
    if philosophy or config['recommendation']:
        st.markdown(f"""
        <div style="background: linear-gradient(to right, {config['bg_color']}, white);
                    padding: 1.25rem; border-radius: 10px; margin: 1.5rem 0;
                    border-left: 5px solid {config['color']};
                    box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
            <div style="margin-bottom: 0.5rem; font-size: 0.9rem; font-weight: 600; color: {config['color']};">
                ESTRATEGIA DE SALIDA
            </div>
            <div style="margin: 0; font-size: 1rem; color: #495057; line-height: 1.6;">
                {philosophy if philosophy else config['recommendation']}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ========== TAKE PROFIT TARGETS - VISUAL CARDS ==========
    if targets and len(targets) > 0:
        st.markdown("###  Take Profit Targets")

        # Display targets as visual cards
        for i, target in enumerate(targets):
            level = target.get('level', 'N/A')
            percent = target.get('percent', 0)
            price = target.get('price', 0)
            rationale_target = target.get('rationale', '')
            r_multiple = target.get('r_multiple', '')

            # Format values - handle different types safely
            import math
            if percent is None or percent == '' or (isinstance(percent, (int, float)) and math.isnan(percent)):
                percent_val = 0
                percent_str = "N/A"
            elif isinstance(percent, str):
                try:
                    percent_val = int(percent.replace('%', '')) if '%' in percent else int(float(percent))
                    percent_str = percent if '%' in percent else f"{percent}%"
                except (ValueError, TypeError):
                    percent_val = 0
                    percent_str = "N/A"
            elif isinstance(percent, (int, float)):
                percent_val = int(percent)
                percent_str = f"{percent}%"
            else:
                percent_val = 0
                percent_str = "N/A"

            if isinstance(price, (int, float)) and price > 0:
                price_str = f"${price:.2f}"
            else:
                price_str = str(price)

            # Color gradient based on target number
            card_colors = ['#4CAF50', '#2196F3', '#FF9800']
            card_color = card_colors[min(i, len(card_colors)-1)]

            # Create visual card for each target
            col_card1, col_card2 = st.columns([3, 1])

            with col_card1:
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, {card_color}15 0%, {card_color}05 100%);
                            padding: 15px; border-radius: 10px; margin: 10px 0;
                            border-left: 5px solid {card_color};
                            box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h4 style="margin: 0; color: {card_color};">
                                {level} {f'({r_multiple}R)' if r_multiple else ''}
                            </h4>
                            <p style="margin: 5px 0; color: #666; font-size: 14px;">
                                {rationale_target if rationale_target else 'Take profit target'}
                            </p>
                        </div>
                        <div style="text-align: right;">
                            <p style="margin: 0; font-size: 24px; font-weight: bold; color: {card_color};">
                                {price_str}
                            </p>
                            <p style="margin: 0; font-size: 14px; color: #999;">
                                Sell {percent_str}
                            </p>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with col_card2:
                # Visual percentage indicator
                st.markdown(f"""
                <div style="text-align: center; padding: 15px;">
                    <div style="font-size: 32px; font-weight: bold; color: {card_color};">
                        {percent_str}
                    </div>
                    <div style="font-size: 12px; color: #999;">SELL</div>
                </div>
                """, unsafe_allow_html=True)

    # ========== TRAILING STOP INFO ==========
    if keep_stop:
        st.markdown(f"""
        <div style="background-color: #FFF9C4;
                    padding: 15px; border-radius: 10px; margin: 20px 0;
                    border-left: 4px solid #FBC02D;">
            <p style="margin: 0;">
                <b> Trailing Stop for Runner:</b> {keep_stop}
            </p>
        </div>
        """, unsafe_allow_html=True)

    # ========== ADDITIONAL INFO IN EXPANDERS ==========
    with st.expander("See Full Strategy Details", expanded=False):

        # Quality Tier explanation
        st.markdown(f"""
        **Quality Tier Classification:**
        - Sistema de clasificación basado en calidad fundamental (Quality Tier) vs riesgo técnico (Risk Tier)
        - **Risk Tier**: Basado en volatilidad de precio y beta (análisis técnico)
        - **Quality Tier**: Basado en score fundamental y guardrails (calidad del negocio)
        """)

        st.markdown("---")

        # Rationale
        if rationale:
            st.markdown(f"** Strategic Rationale:**")
            st.markdown(rationale)

        # Exit conditions forQuality Tier 1
        if 'exit_only_if' in profit_taking and profit_taking['exit_only_if']:
            st.markdown("**🚪 Exit Only If:**")
            for condition in profit_taking['exit_only_if']:
                st.markdown(f"- {condition}")

        # Free ride info
        if 'free_ride' in profit_taking:
            st.success(f"**Free Ride:** {profit_taking['free_ride']}")

        # Examples
        if 'examples' in profit_taking:
            st.info(f"**Historical Examples:** {profit_taking['examples']}")

        # R-multiple info
        if 'risk_r' in profit_taking:
            st.markdown(f"** Risk (R):** {profit_taking['risk_r']} per share")

        # Warning
        if 'warning' in profit_taking and profit_taking['warning']:
            st.warning(f"**Warning:** {profit_taking['warning']}")


st.set_page_config(
    page_title="UltraQuality",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Bootstrap Icons + Modern CSS styling
st.markdown("""
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
<style>
    /* Main container improvements */
    .main {
        background-color: #f8f9fa;
    }

    /* Bootstrap Icons base styling */
    .bi {
        vertical-align: middle;
    }

    /* Professional badges */
    .badge {
        display: inline-block;
        padding: 0.35rem 0.75rem;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .badge-buy {
        background-color: #28a745;
        color: white;
    }

    .badge-sell {
        background-color: #dc3545;
        color: white;
    }

    .badge-hold {
        background-color: #6c757d;
        color: white;
    }

    .badge-monitor {
        background-color: #ffc107;
        color: #000;
    }

    .badge-info {
        background-color: #17a2b8;
        color: white;
    }

    /* Custom progress bar */
    .custom-progress {
        width: 100%;
        height: 8px;
        background: #e9ecef;
        border-radius: 10px;
        overflow: hidden;
        margin: 0.5rem 0;
    }

    .custom-progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #28a745, #20c997);
        transition: width 0.3s ease;
    }

    /* Card-like containers */
    .css-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        margin-bottom: 1rem;
        border: 1px solid #e9ecef;
    }

    /* Metric cards enhancement */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 600;
        color: #1a1a1a;
    }

    [data-testid="stMetricLabel"] {
        font-size: 0.9rem;
        color: #6c757d;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Button improvements */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;
        border: none;
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }

    /* Progress bars */
    .stProgress > div > div {
        background-color: #4CAF50;
        border-radius: 10px;
    }

    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 12px 24px;
        font-weight: 500;
    }

    /* Info boxes */
    .stAlert {
        border-radius: 10px;
        border-left: 4px solid;
    }

    /* Sidebar improvements */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e9ecef;
    }

    /* Headers */
    h1 {
        color: #1a1a1a;
        font-weight: 700;
        letter-spacing: -0.5px;
    }

    h2, h3 {
        color: #2c3e50;
        font-weight: 600;
    }

    /* Expander styling */
    .streamlit-expanderHeader {
        background-color: #f8f9fa;
        border-radius: 8px;
        font-weight: 500;
    }

    /* Score indicators */
    .score-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
    }

    .score-high {
        background-color: #d4edda;
        color: #155724;
    }

    .score-medium {
        background-color: #fff3cd;
        color: #856404;
    }

    .score-low {
        background-color: #f8d7da;
        color: #721c24;
    }
</style>
""", unsafe_allow_html=True)

# Title - Professional header with gradient
st.markdown("""
<div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 2.5rem 2rem; border-radius: 12px; margin-bottom: 2rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
    <h1 style='margin: 0; color: white; font-size: 2.5rem; font-weight: 700; letter-spacing: 1px;'>
        UltraQuality
    </h1>
    <p style='margin: 0.75rem 0 0 0; color: white; opacity: 0.95; font-size: 1.1rem;'>
        Professional stock screening using fundamental quality and value metrics
    </p>
</div>
""", unsafe_allow_html=True)

# ========== SIDEBAR CONFIGURATION ==========
# Professional sidebar styling
st.sidebar.markdown("""
<style>
    /* Sidebar header styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
    }

    /* Section headers */
    .sidebar-section-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.9rem;
        margin: 1rem 0 0.5rem 0;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    /* Divider styling */
    .sidebar-divider {
        height: 2px;
        background: linear-gradient(90deg, transparent, #e2e8f0, transparent);
        margin: 1.5rem 0;
        border: none;
    }

    /* Info badges */
    .info-badge {
        background: #dbeafe;
        color: #1e40af;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
        margin: 0.25rem 0;
    }

    .success-badge {
        background: #d1fae5;
        color: #065f46;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
        margin: 0.25rem 0;
    }

    .warning-badge {
        background: #fef3c7;
        color: #92400e;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
        margin: 0.25rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar Header
st.sidebar.markdown("""
<div style='text-align: center; padding: 1.5rem 0.5rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 12px; margin-bottom: 1.5rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
    <div style='font-size: 1.75rem; font-weight: 700; color: white; margin-bottom: 0.25rem;'>
        UltraQuality
    </div>
    <div style='font-size: 0.85rem; color: #e0e7ff; font-weight: 500;'>
        Configuration Panel
    </div>
</div>
""", unsafe_allow_html=True)

# ========== QUICK PRESET ==========
st.sidebar.markdown("<div class='sidebar-section-header'>QUICK PRESET</div>", unsafe_allow_html=True)

if st.sidebar.button("GLOBAL ELITE",
                     type="primary",
                     use_container_width=True,
                     help="Auto-configure all settings: All Regions, $500M+ mcap, $1M+ volume, 10K stocks, 90% quality weight"):
    # Set session state flags for auto-configuration
    st.session_state['global_elite_active'] = True
    st.session_state['global_elite_region'] = " All Regions"
    st.session_state['global_elite_mcap'] = 500.0  # $500M for broader mid/large cap coverage
    st.session_state['global_elite_vol'] = 1.0     # $1M for good liquidity
    st.session_state['global_elite_topk'] = 10000
    st.session_state['global_elite_quality_weight'] = 0.90
    st.rerun()

# Show active preset indicator
if st.session_state.get('global_elite_active', False):
    st.sidebar.markdown("""
    <div style='background: #d1fae5; border-left: 4px solid #10b981; padding: 0.75rem;
                border-radius: 6px; margin: 0.5rem 0;'>
        <div style='color: #065f46; font-weight: 600; font-size: 0.85rem;'>
            <span style='margin-right: 0.5rem;'>✓</span>Global Elite Active
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.sidebar.button("Clear Preset", help="Return to manual configuration"):
        st.session_state['global_elite_active'] = False
        st.rerun()

st.sidebar.markdown("<hr class='sidebar-divider'>", unsafe_allow_html=True)

# ========== UNIVERSE FILTERS ==========
st.sidebar.markdown("<div class='sidebar-section-header'>UNIVERSE FILTERS</div>", unsafe_allow_html=True)

with st.sidebar.expander("Market Selection & Filters", expanded=True):
    # Region/Country selector
    # Uses exchange codes (country parameter doesn't work in FMP API)
    # Note: Only exchanges verified as available in FMP API are included
    # Complete list of all countries available in FMP API
    # Organized by region and market size for better UX
    region_options = {
        #  AMERICAS
        "United States": "US",
        "Canada": "CA",
        "Mexico": "MX",
        "Brazil": "BR",
        "Argentina": "AR",
        "Chile": "CL",
        "Dominican Rep.": "DO",
        "Bahamas": "BS",
        "Barbados": "BB",
        "Suriname": "SR",

        #  EUROPE - WESTERN
        "United Kingdom": "UK",
        "Germany": "DE",
        "France": "FR",  # via exchanges (not in original list but may work)
        "Spain": "ES",
        "Ireland": "IE",
        "Netherlands": "NL",  # via exchanges
        "Belgium": "BE",  # via exchanges
        "Switzerland": "CH",  # via exchanges
        "Austria": "AT",
        "Norway": "NO",
        "Denmark": "DK",
        "Finland": "FI",

        #  EUROPE - EASTERN
        "Poland": "PL",
        "Czechia": "CZ",
        "Hungary": "HU",
        "Slovakia": "SK",
        "Lithuania": "LT",
        "Estonia": "EE",
        "Slovenia": "SI",
        "Russia": "RU",
        "Ukraine": "UA",
        "Georgia": "GE",

        #  EUROPE - SMALL / TAX HAVENS
        "Liechtenstein": "LI",
        "Monaco": "MC",
        "Malta": "MT",
        "Gibraltar": "GI",
        "Jersey": "JE",
        "Bermuda": "BM",
        "Cyprus": "CY",

        #  ASIA - DEVELOPED
        "Japan": "JP",
        "South Korea": "KR",
        "Singapore": "SG",  # via exchanges
        "Hong Kong": "HK",  # Note: Often used for Chinese companies

        #  ASIA - EMERGING
        "China": "CN",
        "India": "IN",
        "Indonesia": "ID",
        "Thailand": "TH",
        "Vietnam": "VN",
        "Bangladesh": "BD",

        #  MIDDLE EAST & AFRICA
        "Saudi Arabia": "SA",
        "UAE": "AE",  # via exchanges
        "Qatar": "QA",
        "Kuwait": "KW",
        "Egypt": "EG",
        "South Africa": "ZA",  # via exchanges
        "Namibia": "NA",
        "Mauritius": "MU",
        "Mozambique": "MZ",
        "Senegal": "SN",
        "Ivory Coast": "CI",
        "Kyrgyzstan": "KG",
        "Réunion": "RE",

        #  OCEANIA
        "Australia": "AU",
        "New Zealand": "NZ",  # via exchanges

        #  SPECIAL / ALL
        "Falkland Islands": "FK",
        " All Regions": "ALL"
    }

    # Use preset value if Global Elite is active
    if st.session_state.get('global_elite_active', False):
        preset_region = st.session_state.get('global_elite_region', "United States")
        default_index = list(region_options.keys()).index(preset_region) if preset_region in region_options else 0
    else:
        default_index = 0  # Default to US

    selected_region = st.selectbox(
        "Market/Region",
        options=list(region_options.keys()),
        index=default_index,
        help="Select which stock market/region to screen. Filters by country code in FMP API."
    )

    exchange_filter = region_options[selected_region]

    # Show info about selected region (optional, for major markets)
    region_info = {
        # Major Markets
        "US": "NYSE, NASDAQ, AMEX (5000+ stocks)",
        "CA": "Toronto Stock Exchange (TSX)",
        "MX": "Bolsa Mexicana de Valores (BMV)",
        "UK": "London Stock Exchange (LSE)",
        "DE": "Frankfurt/XETRA (DAX, MDAX)",
        "FR": "Euronext Paris (CAC 40)",
        "JP": "Tokyo Stock Exchange (TSE)",
        "CN": "Shanghai & Shenzhen Stock Exchanges",
        "IN": "National Stock Exchange (NSE)",
        "ID": "Indonesia Stock Exchange (IDX)",
        "HK": "Hong Kong Exchange (Alibaba, Tencent)",
        "BR": "B3 São Paulo (Petrobras, Vale)",
        "AU": "Australian Securities Exchange (ASX)",
        "CH": "SIX Swiss Exchange (Nestlé, Roche)",
        "KR": "Korea Exchange (Samsung, Hyundai)",
        "ES": "Bolsa de Madrid (Santander, Inditex)",
        "NL": "Euronext Amsterdam (Shell, ASML)",
        "SG": "Singapore Exchange (DBS, Sea)",
        "ALL": " All regions (54 global markets) - Comprehensive worldwide coverage"
    }

    if exchange_filter in region_info:
        st.caption(region_info[exchange_filter])

    # Dynamic default thresholds based on market size
    # Categorized by market capitalization depth
    # Note: All values must be float for Streamlit compatibility
    default_thresholds = {
        #  MEGA MARKET (US only)
        "US": {"mcap": 2000.0, "vol": 5.0},

        #  LARGE DEVELOPED MARKETS ($300-500M mcap)
        "JP": {"mcap": 500.0, "vol": 2.0},       # Japan - Tokyo
        "UK": {"mcap": 300.0, "vol": 1.0},       # United Kingdom - London
        "DE": {"mcap": 300.0, "vol": 1.0},       # Germany - Frankfurt/XETRA
        "FR": {"mcap": 300.0, "vol": 1.0},       # France - Euronext Paris
        "CA": {"mcap": 300.0, "vol": 1.0},       # Canada - Toronto
        "AU": {"mcap": 300.0, "vol": 1.0},       # Australia - ASX
        "CH": {"mcap": 300.0, "vol": 1.0},       # Switzerland - SIX

        #  MEDIUM DEVELOPED MARKETS ($100-200M mcap)
        "ES": {"mcap": 200.0, "vol": 0.5},       # Spain
        "NL": {"mcap": 200.0, "vol": 0.5},       # Netherlands - Euronext Amsterdam
        "IT": {"mcap": 200.0, "vol": 0.5},       # Italy (if available)
        "NO": {"mcap": 150.0, "vol": 0.5},       # Norway - Oslo Børs
        "DK": {"mcap": 150.0, "vol": 0.5},       # Denmark - Copenhagen
        "FI": {"mcap": 150.0, "vol": 0.5},       # Finland - Helsinki
        "IE": {"mcap": 150.0, "vol": 0.5},       # Ireland - Irish Stock Exchange
        "BE": {"mcap": 150.0, "vol": 0.5},       # Belgium - Euronext Brussels
        "AT": {"mcap": 150.0, "vol": 0.5},       # Austria - Vienna
        "SG": {"mcap": 200.0, "vol": 0.5},       # Singapore
        "NZ": {"mcap": 100.0, "vol": 0.3},       # New Zealand

        #  LARGE EMERGING MARKETS ($100-200M mcap)
        "CN": {"mcap": 200.0, "vol": 1.0},       # China - Shanghai/Shenzhen
        "IN": {"mcap": 200.0, "vol": 1.0},       # India - NSE
        "ID": {"mcap": 150.0, "vol": 0.5},       # Indonesia - IDX
        "BR": {"mcap": 150.0, "vol": 0.5},       # Brazil - B3
        "HK": {"mcap": 200.0, "vol": 1.0},       # Hong Kong
        "KR": {"mcap": 200.0, "vol": 1.0},       # South Korea - KRX
        "MX": {"mcap": 150.0, "vol": 0.5},       # Mexico - BMV (if available)
        "ZA": {"mcap": 100.0, "vol": 0.3},       # South Africa - JSE
        "SA": {"mcap": 200.0, "vol": 0.5},       # Saudi Arabia - Tadawul

        #  SMALL EMERGING MARKETS ($50-100M mcap)
        "TH": {"mcap": 100.0, "vol": 0.3},       # Thailand - SET
        "PL": {"mcap": 100.0, "vol": 0.3},       # Poland - Warsaw
        "CZ": {"mcap": 75.0, "vol": 0.2},        # Czechia - Prague
        "AR": {"mcap": 75.0, "vol": 0.2},        # Argentina - BCBA
        "CL": {"mcap": 75.0, "vol": 0.2},        # Chile - Santiago
        "EG": {"mcap": 75.0, "vol": 0.2},        # Egypt - EGX
        "QA": {"mcap": 100.0, "vol": 0.3},       # Qatar
        "KW": {"mcap": 100.0, "vol": 0.3},       # Kuwait
        "HU": {"mcap": 75.0, "vol": 0.2},        # Hungary - Budapest
        "SK": {"mcap": 50.0, "vol": 0.1},        # Slovakia - Bratislava
        "VN": {"mcap": 75.0, "vol": 0.2},        # Vietnam

        #  FRONTIER / SMALL MARKETS ($20-50M mcap)
        "LT": {"mcap": 50.0, "vol": 0.1},        # Lithuania
        "EE": {"mcap": 50.0, "vol": 0.1},        # Estonia
        "SI": {"mcap": 50.0, "vol": 0.1},        # Slovenia
        "RU": {"mcap": 50.0, "vol": 0.1},        # Russia (sanctions may affect)
        "UA": {"mcap": 30.0, "vol": 0.05},       # Ukraine
        "GE": {"mcap": 30.0, "vol": 0.05},       # Georgia
        "BD": {"mcap": 50.0, "vol": 0.1},        # Bangladesh
        "DO": {"mcap": 30.0, "vol": 0.05},       # Dominican Republic
        "BS": {"mcap": 30.0, "vol": 0.05},       # Bahamas
        "BB": {"mcap": 30.0, "vol": 0.05},       # Barbados
        "SR": {"mcap": 20.0, "vol": 0.05},       # Suriname
        "NA": {"mcap": 30.0, "vol": 0.05},       # Namibia
        "MU": {"mcap": 30.0, "vol": 0.05},       # Mauritius
        "MZ": {"mcap": 20.0, "vol": 0.05},       # Mozambique
        "SN": {"mcap": 20.0, "vol": 0.05},       # Senegal
        "CI": {"mcap": 20.0, "vol": 0.05},       # Ivory Coast
        "KG": {"mcap": 20.0, "vol": 0.05},       # Kyrgyzstan
        "RE": {"mcap": 20.0, "vol": 0.05},       # Réunion

        # 💼 TAX HAVENS / OFFSHORE (company domiciles, not exchanges)
        "LI": {"mcap": 50.0, "vol": 0.1},        # Liechtenstein
        "MC": {"mcap": 50.0, "vol": 0.1},        # Monaco
        "MT": {"mcap": 50.0, "vol": 0.1},        # Malta
        "GI": {"mcap": 50.0, "vol": 0.1},        # Gibraltar
        "JE": {"mcap": 50.0, "vol": 0.1},        # Jersey
        "BM": {"mcap": 75.0, "vol": 0.2},        # Bermuda (many large companies domiciled)
        "CY": {"mcap": 50.0, "vol": 0.1},        # Cyprus
        "FK": {"mcap": 20.0, "vol": 0.05},       # Falkland Islands
        "AE": {"mcap": 150.0, "vol": 0.5},       # UAE - Abu Dhabi/Dubai

        # Default for ALL or unknown markets
        "ALL": {"mcap": 500.0, "vol": 2.0}
    }

    # Get defaults for selected country
    defaults = default_thresholds.get(exchange_filter, {"mcap": 200.0, "vol": 1.0})

    # Use preset values if Global Elite is active
    if st.session_state.get('global_elite_active', False):
        default_mcap = st.session_state.get('global_elite_mcap', defaults["mcap"])
        default_vol = st.session_state.get('global_elite_vol', defaults["vol"])
    else:
        default_mcap = defaults["mcap"]
        default_vol = defaults["vol"]

    min_mcap = st.number_input(
        "Min Market Cap ($M)",
        min_value=10.0,
        max_value=100000.0,
        value=default_mcap,
        step=10.0,
        help=f"Minimum market capitalization in millions. Recommended for {selected_region}: ${defaults['mcap']:.0f}M"
    )

    min_vol = st.number_input(
        "Min Daily Volume ($M)",
        min_value=0.1,
        max_value=100.0,
        value=default_vol,
        step=0.1,
        help=f"Minimum average daily dollar volume in millions. Recommended for {selected_region}: ${defaults['vol']:.1f}M"
    )

    # Use preset value if Global Elite is active
    if st.session_state.get('global_elite_active', False):
        default_topk = st.session_state.get('global_elite_topk', 10000)
    else:
        default_topk = 500

    top_k = st.slider(
        "Top-K Stocks to Analyze",
        min_value=50,
        max_value=10000,
        value=default_topk,
        step=50,
        help="Number of stocks to deep-dive after preliminary ranking. 500 stocks = ~4 min, 3000 stocks = ~25 min, 10,000 stocks = ~80-90 min (first run). Re-runs with incremental cache: < 10 min"
    )

st.sidebar.markdown("<hr class='sidebar-divider'>", unsafe_allow_html=True)

# ========== SCORING & THRESHOLDS ==========
st.sidebar.markdown("<div class='sidebar-section-header'>SCORING & THRESHOLDS</div>", unsafe_allow_html=True)

with st.sidebar.expander("Quality vs Value Balance", expanded=True):
    # Use preset value if Global Elite is active
    if st.session_state.get('global_elite_active', False):
        default_quality_weight = st.session_state.get('global_elite_quality_weight', 0.90)
    else:
        default_quality_weight = 0.70

    weight_quality = st.slider("Quality Weight", 0.0, 1.0, default_quality_weight, 0.05,
                                key='weight_quality_slider',
                                help="QARP default: 0.70 (prioritize exceptional companies with moats)")
    weight_value = 1.0 - weight_quality

    # Show weights as badges
    st.markdown(f"""
    <div style='display: flex; justify-content: space-between; margin: 0.5rem 0;'>
        <span class='info-badge'>Quality: {weight_quality:.0%}</span>
        <span class='warning-badge'>Value: {weight_value:.0%}</span>
    </div>
    """, unsafe_allow_html=True)

    st.caption("Note: Moving sliders will instantly recalculate results")

    # Guidance
    if weight_quality >= 0.75:
        st.success("**Optimal:** 75%+ Quality captures exceptional companies (Buffett-style)")
    elif weight_quality >= 0.70:
        st.success("**Recommended:** 70% Quality = QARP balance")
    elif weight_quality >= 0.60:
        st.info("**Tip:** May miss some high-moat companies")
    else:
        st.warning("**Warning:** Commodities may rank higher than tech giants")

with st.sidebar.expander("Decision Thresholds", expanded=True):
    threshold_buy = st.slider("BUY Threshold", 50, 90, 65, 5,
                               key='threshold_buy_slider',
                               help="Minimum composite score for BUY (QARP default: 65)")
    threshold_monitor = st.slider("MONITOR Threshold", 30, 70, 45, 5,
                                   key='threshold_monitor_slider',
                                   help="Minimum composite score for MONITOR (QARP default: 45)")
    threshold_quality_exceptional = st.slider("Quality Exceptional", 70, 95, 85, 5,
                                               key='threshold_quality_exceptional_slider',
                                               help="If Quality ≥ this, force BUY even with lower composite (only truly exceptional companies). Default: 85")

    exclude_reds = st.checkbox("Auto-Exclude RED Guardrails", value=True,
                               key='exclude_reds_checkbox',
                               help="Auto-AVOID stocks with accounting red flags (exceptions for Q≥80, C≥75)")

    st.markdown("""
    <div style='background: #f8fafc; padding: 0.75rem; border-radius: 6px; margin-top: 0.75rem;'>
        <div style='font-size: 0.75rem; color: #64748b; font-weight: 600; margin-bottom: 0.5rem;'>
            GUARDRAIL SYSTEM
        </div>
        <div style='display: flex; flex-direction: column; gap: 0.5rem;'>
            <div style='display: flex; align-items: center; gap: 0.5rem;'>
                <span class='success-badge'>VERDE</span>
                <span style='font-size: 0.7rem; color: #475569;'>Clean accounting</span>
            </div>
            <div style='display: flex; align-items: center; gap: 0.5rem;'>
                <span class='warning-badge'>AMBAR</span>
                <span style='font-size: 0.7rem; color: #475569;'>Minor concerns</span>
            </div>
            <div style='display: flex; align-items: center; gap: 0.5rem;'>
                <span style='background: #fee2e2; color: #991b1b; padding: 0.2rem 0.5rem; border-radius: 8px; font-size: 0.7rem; font-weight: 600;'>ROJO</span>
                <span style='font-size: 0.7rem; color: #475569;'>Red flags (blocked unless Q≥80 + C≥75)</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.sidebar.markdown("<hr class='sidebar-divider'>", unsafe_allow_html=True)

# ========== RISK MANAGEMENT ==========
st.sidebar.markdown("<div class='sidebar-section-header'>RISK MANAGEMENT</div>", unsafe_allow_html=True)

# Initialize variables at sidebar level (outside expander)
portfolio_capital = st.sidebar.number_input(
    "Portfolio Capital ($)",
    min_value=1000,
    max_value=10000000,
    value=100000,
    step=10000,
    help="Total portfolio size for position sizing calculations",
    key='portfolio_capital_input'
)

max_risk_per_trade_pct = st.sidebar.slider(
    "Max Risk per Trade (%)",
    min_value=0.25,
    max_value=5.0,
    value=1.0,
    step=0.25,
    help="Maximum % of portfolio to risk on any single trade (if stop loss hit)",
    key='max_risk_pct_slider'
)

max_risk_per_trade_dollars = portfolio_capital * (max_risk_per_trade_pct / 100)

# Show compact summary
st.sidebar.markdown(f"""
<div style='background: #f0f9ff; border-left: 4px solid #3b82f6; padding: 0.5rem;
            border-radius: 6px; margin: 0.5rem 0; font-size: 0.75rem;'>
    Portfolio: <strong>${portfolio_capital:,}</strong> |
    Risk: <strong>{max_risk_per_trade_pct}%</strong> = <strong>${max_risk_per_trade_dollars:,.0f}</strong>
</div>
""", unsafe_allow_html=True)

with st.sidebar.expander("Dual Constraint System", expanded=False):
    st.info("""
    **Dual Constraint System:**
    Position Size = MIN(Quality-Based, Risk-Based)

    Ensures you never exceed EITHER:
    - Diversification limit (by quality tier)
    - Risk limit (1% max loss per trade)
    """)

st.sidebar.markdown("<hr class='sidebar-divider'>", unsafe_allow_html=True)

# ========== SYSTEM ==========
st.sidebar.markdown("<div class='sidebar-section-header'>SYSTEM</div>", unsafe_allow_html=True)

# API Status
with st.sidebar.expander("API Status", expanded=False):
    try:
        api_key = st.secrets.get('FMP_API_KEY', '')
        if api_key and not api_key.startswith('your_'):
            st.markdown(f"""
            <div style='background: #d1fae5; border-left: 4px solid #10b981; padding: 0.75rem;
                        border-radius: 6px;'>
                <div style='color: #065f46; font-weight: 600; font-size: 0.85rem;'>
                    ✓ API Key Active
                </div>
                <div style='color: #047857; font-size: 0.75rem; margin-top: 0.25rem;'>
                    {api_key[:10]}...
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.error("API Key not configured")
            st.info("Add FMP_API_KEY to Streamlit secrets")
    except:
        st.warning("Secrets not accessible")

# Cache Management
with st.sidebar.expander("Cache Management", expanded=False):
    if st.button("Clear All Caches",
                 use_container_width=True,
                 help="Clear FMP API cache and incremental processing cache. Use this if you're seeing stale data or analysis errors."):
        import shutil
        from pathlib import Path

        # Clear caches
        caches_cleared = []
        cache_base = Path('./cache')
        if cache_base.exists():
            try:
                shutil.rmtree(cache_base)
                caches_cleared.append("FMP API cache")
            except Exception as e:
                st.error(f"Failed to clear cache: {e}")

        # Clear Streamlit cache
        st.cache_data.clear()
        st.cache_resource.clear()
        caches_cleared.append("Streamlit cache")

        if caches_cleared:
            st.success(f"Cleared: {', '.join(caches_cleared)}")
            st.info("Please run the screener again to refresh data")


# ========== HELPER FUNCTIONS ==========

def display_position_sizing(pos_sizing, stop_loss_data=None, portfolio_size=100000, max_risk_dollars=1000):
    """
    Display enhanced position sizing with DUAL CONSTRAINT system.

    Método A (Quality-Based): Ya calculado con penalties
    Método B (Risk-Based): max_risk_dollars / stop_loss_distance

    DECISIÓN FINAL = MIN(A, B)

    Args:
        pos_sizing: Position sizing dict from risk_management
        stop_loss_data: Stop loss dict with 'stop_loss_pct' key
        portfolio_size: Total portfolio size in dollars (default: $100k)
        max_risk_dollars: Maximum $ to risk per trade (default: $1k = 1% of $100k)
    """
    # Modern section header
    st.markdown("""
    <div style='background: linear-gradient(to right, #667eea, #764ba2); padding: 1rem;
                border-radius: 8px; margin-bottom: 1rem;'>
        <h3 style='margin: 0; color: white;'><i class="bi bi-calculator"></i> Position Sizing Calculator</h3>
        <p style='margin: 0.25rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem;'>
            Dual Constraint System: MIN(Quality-Based, Risk-Based)
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Check for VETO
    if pos_sizing.get('veto_active'):
        st.error(f"🛑 **VETO ACTIVE**")
        st.write(f"**Rationale:** {pos_sizing.get('rationale', 'N/A')}")
        st.caption(pos_sizing.get('calculation_breakdown', ''))
        return

    # Get data
    base_pct = pos_sizing.get('base_pct', 0)
    final_pct = pos_sizing.get('final_pct', 0)
    quality_tier = pos_sizing.get('quality_tier', 'UNKNOWN')
    penalties = pos_sizing.get('penalties', [])
    bonuses = pos_sizing.get('bonuses', [])
    bear_market = pos_sizing.get('bear_market_adjustment', False)

    # ========== MÉTODO A: QUALITY-BASED (ya calculado) ==========
    quality_based_dollars = portfolio_size * (final_pct / 100)

    # ========== MÉTODO B: RISK-BASED (calculamos ahora) ==========
    risk_based_dollars = None
    stop_loss_pct = None

    if stop_loss_data:
        # Get stop loss distance as % (positive value, e.g., 5.0 means 5% below current price)
        stop_loss_pct = stop_loss_data.get('stop_loss_pct')

        if stop_loss_pct and stop_loss_pct != 0:
            # Convert to positive distance (e.g., -5.0 → 5.0)
            stop_distance = abs(stop_loss_pct)

            # Risk-Based Position Size = Max Risk $ / (Stop Distance / 100)
            # Example: $1,000 / (4% / 100) = $1,000 / 0.04 = $25,000
            risk_based_dollars = max_risk_dollars / (stop_distance / 100)

    # ========== DECISIÓN FINAL: MIN(A, B) ==========
    if risk_based_dollars is not None:
        final_dollars = min(quality_based_dollars, risk_based_dollars)
        constraint = "Quality" if quality_based_dollars < risk_based_dollars else "Risk"
    else:
        final_dollars = quality_based_dollars
        constraint = "Quality (no stop loss data)"

    final_pct_adjusted = (final_dollars / portfolio_size) * 100

    # ========== DISPLAY ==========

    # Big visual result card first
    st.markdown(f"""
    <div style='background: white; padding: 2rem; border-radius: 12px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1); margin-bottom: 1.5rem;
                border-left: 6px solid #28a745; text-align: center;'>
        <div style='font-size: 0.9rem; color: #6c757d; margin-bottom: 0.5rem;'>RECOMMENDED POSITION SIZE</div>
        <div style='font-size: 3rem; font-weight: 700; color: #28a745; margin: 0.5rem 0;'>
            ${final_dollars:,.0f}
        </div>
        <div style='font-size: 1.3rem; color: #495057; margin-bottom: 1rem;'>
            {final_pct_adjusted:.1f}% of portfolio
        </div>
        <div style='font-size: 0.85rem; color: #6c757d;'>
            Limited by: <strong>{constraint}</strong> constraint
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Show dual calculation with visual cards
    st.markdown("#### Calculation Breakdown")
    col_a, col_b, col_final = st.columns(3)

    with col_a:
        st.markdown("""
        <div style='background: #e3f2fd; padding: 1rem; border-radius: 8px;
                    border: 2px solid #2196f3; margin-bottom: 0.5rem;'>
            <div style='font-size: 0.85rem; color: #1976d2; font-weight: 600;'>METHOD A: Quality-Based</div>
        </div>
        """, unsafe_allow_html=True)
        st.metric("Allocation", f"{final_pct:.1f}%", delta=f"${quality_based_dollars:,.0f}")
        st.caption(f"Quality Tier: **{quality_tier}**")

        # Visual progress bar for quality allocation
        quality_progress = min(final_pct / 10, 1.0)  # Normalize to 0-1 (assuming max 10%)
        st.progress(quality_progress)

    with col_b:
        st.markdown("""
        <div style='background: #fff3e0; padding: 1rem; border-radius: 8px;
                    border: 2px solid #ff9800; margin-bottom: 0.5rem;'>
            <div style='font-size: 0.85rem; color: #f57c00; font-weight: 600;'>METHOD B: Risk-Based</div>
        </div>
        """, unsafe_allow_html=True)
        if risk_based_dollars is not None and stop_loss_pct is not None:
            risk_pct = (risk_based_dollars / portfolio_size) * 100
            st.metric("Allocation", f"{risk_pct:.1f}%", delta=f"${risk_based_dollars:,.0f}")
            st.caption(f"Stop Loss: **{abs(stop_loss_pct):.1f}%**")

            # Visual progress bar for risk allocation
            risk_progress = min(risk_pct / 10, 1.0)
            st.progress(risk_progress)
        else:
            st.warning("⚠️ N/A")
            st.caption("No stop loss data available")

    with col_final:
        st.markdown("""
        <div style='background: #e8f5e9; padding: 1rem; border-radius: 8px;
                    border: 2px solid #4caf50; margin-bottom: 0.5rem;'>
            <div style='font-size: 0.85rem; color: #388e3c; font-weight: 600;'>✓ FINAL (MIN)</div>
        </div>
        """, unsafe_allow_html=True)
        st.metric("Position Size", f"{final_pct_adjusted:.1f}%", delta=f"${final_dollars:,.0f}")

        # Visual progress bar for final allocation
        final_progress = min(final_pct_adjusted / 10, 1.0)
        st.progress(final_progress)

        if constraint == "Risk":
            st.markdown("""
            <div style='background: linear-gradient(to right, #e3f2fd, #bbdefb);
                        padding: 1rem; border-radius: 8px; border-left: 4px solid #2196f3;'>
                <div style='color: #1565c0; font-weight: 600;'>
                    <i class="bi bi-shield-check"></i> Risk limit is more conservative
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style='background: linear-gradient(to right, #fff8e1, #ffecb3);
                        padding: 1rem; border-radius: 8px; border-left: 4px solid #ffc107;'>
                <div style='color: #f57c00; font-weight: 600;'>
                    <i class="bi bi-star-fill"></i> Quality limit is more conservative
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Display quality tier and base allocation with enhanced design
    st.markdown("---")

    # Quality Tier Header Card
    tier_colors = {
        'ELITE': '#9b59b6',
        'PREMIUM': '#3498db',
        'SOLID': '#2ecc71',
        'SPECULATIVE': '#f39c12',
        'AVOID': '#e74c3c'
    }
    tier_icons = {
        'ELITE': '<i class="bi bi-gem"></i>',
        'PREMIUM': '<i class="bi bi-star-fill"></i>',
        'SOLID': '<i class="bi bi-check-circle-fill"></i>',
        'SPECULATIVE': '<i class="bi bi-exclamation-triangle-fill"></i>',
        'AVOID': '<i class="bi bi-x-circle-fill"></i>'
    }

    tier_color = tier_colors.get(quality_tier, '#3498db')
    tier_icon_ps = tier_icons.get(quality_tier, '<i class="bi bi-graph-up"></i>')

    st.markdown(f"""
    <div style='background: linear-gradient(135deg, {tier_color} 0%, {tier_color}cc 100%);
                padding: 1.5rem; border-radius: 12px; margin-bottom: 1.5rem; color: white;'>
        <div style='font-size: 2rem; margin-bottom: 0.5rem;'>{tier_icon_ps}</div>
        <div style='font-size: 1.5rem; font-weight: 700; margin-bottom: 0.5rem;'>{quality_tier}</div>
        <div style='font-size: 1.2rem; opacity: 0.95;'>Base Allocation: {base_pct}%</div>
    </div>
    """, unsafe_allow_html=True)

    # Penalties and Bonuses in 2 columns
    if penalties or bonuses:
        col_pen, col_bon = st.columns(2)

        with col_pen:
            if penalties:
                st.markdown("""
                <div style='background: #fff5f5; padding: 1rem; border-radius: 10px;
                            border-left: 4px solid #dc3545; margin-bottom: 1rem;'>
                    <div style='font-size: 1rem; font-weight: 600; color: #dc3545; margin-bottom: 0.75rem;'><i class="bi bi-x-circle-fill"></i> Penalties:</div>
                </div>
                """, unsafe_allow_html=True)
                for penalty in penalties:
                    st.markdown(f"""
                    <div style='background: white; padding: 0.75rem; border-radius: 6px;
                                margin-bottom: 0.5rem; border-left: 3px solid #dc3545;'>
                        <div style='font-size: 0.9rem; color: #495057;'>• {penalty}</div>
                    </div>
                    """, unsafe_allow_html=True)

        with col_bon:
            if bonuses:
                st.markdown("""
                <div style='background: #f0f9ff; padding: 1rem; border-radius: 10px;
                            border-left: 4px solid #28a745; margin-bottom: 1rem;'>
                    <div style='font-size: 1rem; font-weight: 600; color: #28a745; margin-bottom: 0.75rem;'><i class="bi bi-check-circle-fill"></i> Bonuses:</div>
                </div>
                """, unsafe_allow_html=True)
                for bonus in bonuses:
                    st.markdown(f"""
                    <div style='background: white; padding: 0.75rem; border-radius: 6px;
                                margin-bottom: 0.5rem; border-left: 3px solid #28a745;'>
                        <div style='font-size: 0.9rem; color: #495057;'>• {bonus}</div>
                    </div>
                    """, unsafe_allow_html=True)

    # Bear market adjustment
    if bear_market:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
                    padding: 1rem; border-radius: 10px; margin-top: 1rem; color: white;'>
            <div style='font-size: 1.1rem; font-weight: 600;'><i class="bi bi-exclamation-triangle-fill"></i> Bear Market Override</div>
            <div style='font-size: 0.9rem; opacity: 0.95; margin-top: 0.5rem;'>All positions halved to reduce exposure</div>
        </div>
        """, unsafe_allow_html=True)

    # Execution details card
    st.markdown("---")
    st.markdown("#### <i class='bi bi-card-checklist'></i> Execution Plan", unsafe_allow_html=True)

    # Calculate shares (assuming we have current price in stop_loss_data)
    if stop_loss_data and stop_loss_data.get('current_price'):
        current_price = stop_loss_data.get('current_price', 0)
        if current_price > 0:
            shares = int(final_dollars / current_price)
            actual_cost = shares * current_price

            # Visual execution card
            st.markdown(f"""
            <div style='background: linear-gradient(to right, #f8f9fa, #e9ecef); padding: 1.5rem;
                        border-radius: 10px; border: 2px solid #667eea; margin-bottom: 1rem;'>
                <div style='display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem;'>
                    <div>
                        <div style='font-size: 0.8rem; color: #6c757d;'>SHARES TO BUY</div>
                        <div style='font-size: 1.8rem; font-weight: 600; color: #495057;'>{shares:,}</div>
                    </div>
                    <div>
                        <div style='font-size: 0.8rem; color: #6c757d;'>PRICE PER SHARE</div>
                        <div style='font-size: 1.8rem; font-weight: 600; color: #495057;'>${current_price:.2f}</div>
                    </div>
                    <div>
                        <div style='font-size: 0.8rem; color: #6c757d;'>TOTAL INVESTMENT</div>
                        <div style='font-size: 1.8rem; font-weight: 600; color: #667eea;'>${actual_cost:,.0f}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Trading fee estimate
            estimated_fee = actual_cost * 0.001  # 0.1% typical commission
            st.caption(f"Estimated trading fees: ${estimated_fee:.2f} (0.1% assumption)")
    else:
        st.info("Current price not available. Use recommended dollar amount: **${:,.0f}**".format(final_dollars))

    # Rationale box
    st.markdown("""
    <div style='margin-top: 1.5rem;'>
        <div style='font-size: 1.1rem; font-weight: 600; margin-bottom: 0.75rem;'>
            <i class="bi bi-lightbulb"></i> Sizing Rationale
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.info(pos_sizing.get('rationale', 'N/A'))

    # Detailed breakdown (expandable)
    with st.expander("Detailed Quality-Based Calculation", expanded=False):
        st.caption(pos_sizing.get('calculation_breakdown', 'N/A'))

    # Risk management reminder
    st.markdown("---")
    st.markdown("""
    <div style='background: #fff3cd; padding: 1rem; border-radius: 8px;
                border-left: 4px solid #ffc107;'>
        <strong><i class="bi bi-exclamation-triangle-fill"></i> Risk Management Reminders:</strong>
        <ul style='margin: 0.5rem 0 0 0; padding-left: 1.5rem;'>
            <li>Never invest more than recommended position size</li>
            <li>Always set a stop loss order after buying</li>
            <li>Consider scaling in with 2-3 entries if position is large</li>
            <li>Review total portfolio exposure before executing</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)


def get_market_regime_display(regime: str) -> str:
    """
    Get emoji and formatted display for market regime.

    Args:
        regime: Market regime ('BULL', 'BEAR', 'SIDEWAYS', etc.)

    Returns:
        Formatted string with emoji and regime name
    """
    regime_emojis = {
        'BULL': '',
        'BEAR': '',
        'SIDEWAYS': '',
        'UNKNOWN': ''
    }
    emoji = regime_emojis.get(regime, '')
    return f"{emoji} {regime}"


# ========== MAIN CONTENT ==========

# Main content
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(["Home", "Results", "Analytics", "Calibration", "Qualitative", "Complete Analysis", "Technical", "About"])

with tab1:
    # Welcome section with modern card design
    st.markdown("""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 2rem; border-radius: 12px; color: white; margin-bottom: 2rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
        <h2 style='margin: 0; color: white; font-weight: 700;'>Home</h2>
        <p style='margin: 0.5rem 0 0 0; opacity: 0.95;'>
            AI-powered fundamental analysis combining Quality (70%) + Value (30%) metrics with
            advanced guardrails and technical validation
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Show existing results summary if available
    if 'results' in st.session_state:
        # Get recalculated results with current slider values
        df_existing = get_results_with_current_params()
        buys_existing = (df_existing['decision'] == 'BUY').sum()
        monitors_existing = (df_existing['decision'] == 'MONITOR').sum()
        avoids_existing = (df_existing['decision'] == 'AVOID').sum()
        timestamp_existing = st.session_state.get('timestamp', datetime.now())
        config_version = st.session_state.get('config_version', 'unknown')

        # Check if results are from old config
        CURRENT_VERSION = "QARP-v3-Moat"
        is_stale = config_version != CURRENT_VERSION

        # Results status card
        if is_stale:
            st.warning(f"**Results from older version** ({config_version}). Re-run to use latest methodology with Moat Score.")
        else:
            st.success(f"**Latest results available** - Generated: {timestamp_existing.strftime('%Y-%m-%d %H:%M:%S')}")

        # Key metrics with enhanced visual design
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 1.5rem;'>
            <h3 style='margin: 0; color: white; font-weight: 600;'>
                📊 Screening Results Overview
            </h3>
            <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem;'>
                Summary metrics from latest screening run
            </p>
        </div>
        """, unsafe_allow_html=True)
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.metric(
                "Total Analyzed",
                f"{len(df_existing):,}",
                help="Total stocks analyzed in latest screening"
            )

        with col2:
            buy_pct = (buys_existing / len(df_existing) * 100) if len(df_existing) > 0 else 0
            st.metric(
                "BUY Signals",
                buys_existing,
                delta=f"{buy_pct:.1f}%",
                delta_color="normal",
                help="High-quality companies at reasonable prices"
            )

        with col3:
            monitor_pct = (monitors_existing / len(df_existing) * 100) if len(df_existing) > 0 else 0
            st.metric(
                "MONITOR",
                monitors_existing,
                delta=f"{monitor_pct:.1f}%",
                delta_color="off",
                help="Companies with potential but need more analysis"
            )

        with col4:
            avoid_pct = (avoids_existing / len(df_existing) * 100) if len(df_existing) > 0 else 0
            st.metric(
                "AVOID",
                avoids_existing,
                delta=f"{avoid_pct:.1f}%",
                delta_color="inverse",
                help="Low quality or overvalued companies"
            )

        with col5:
            avg_score = df_existing['composite_0_100'].mean()
            st.metric(
                "Avg Quality Score",
                f"{avg_score:.1f}",
                help="Average composite quality score (0-100)"
            )

        # Score distribution visualization
        if 'composite_0_100' in df_existing.columns:
            st.markdown("### Quality Score Distribution")

            # Create score ranges
            score_ranges = {
                'Exceptional (80-100)': len(df_existing[df_existing['composite_0_100'] >= 80]),
                'Strong (60-79)': len(df_existing[(df_existing['composite_0_100'] >= 60) & (df_existing['composite_0_100'] < 80)]),
                'Moderate (40-59)': len(df_existing[(df_existing['composite_0_100'] >= 40) & (df_existing['composite_0_100'] < 60)]),
                'Weak (<40)': len(df_existing[df_existing['composite_0_100'] < 40])
            }

            col1, col2, col3, col4 = st.columns(4)
            colors = ['#28a745', '#17a2b8', '#ffc107', '#dc3545']

            for (label, count), col, color in zip(score_ranges.items(), [col1, col2, col3, col4], colors):
                with col:
                    percentage = (count / len(df_existing) * 100) if len(df_existing) > 0 else 0
                    st.markdown(f"""
                    <div style='background: white; padding: 1rem; border-radius: 8px;
                                border-left: 4px solid {color}; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>
                        <div style='font-size: 0.85rem; color: #6c757d; margin-bottom: 0.5rem;'>{label}</div>
                        <div style='font-size: 1.5rem; font-weight: 600;'>{count}</div>
                        <div style='font-size: 0.85rem; color: {color}; font-weight: 500;'>{percentage:.1f}% of universe</div>
                    </div>
                    """, unsafe_allow_html=True)

        # Action buttons
        col_btn1, col_btn2 = st.columns([3, 1])
        with col_btn1:
            st.info("**Next steps:** Explore the Results, Analytics, and Qualitative tabs for detailed analysis")
        with col_btn2:
            if st.button("Clear Results", use_container_width=True):
                for key in ['results', 'timestamp', 'config_version']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

        st.markdown("---")

    # Screening configuration preview
    st.markdown("### Current Configuration")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div style='background: white; padding: 1.2rem; border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center;'>
            <div style='font-size: 0.85rem; color: #6c757d; margin-bottom: 0.5rem;'>UNIVERSE SIZE</div>
            <div style='font-size: 2rem; font-weight: 600; color: #667eea;'>2000+</div>
            <div style='font-size: 0.85rem; color: #6c757d;'>stocks globally</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style='background: white; padding: 1.2rem; border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center;'>
            <div style='font-size: 0.85rem; color: #6c757d; margin-bottom: 0.5rem;'>DEEP ANALYSIS</div>
            <div style='font-size: 2rem; font-weight: 600; color: #764ba2;'>{top_k}</div>
            <div style='font-size: 0.85rem; color: #6c757d;'>top quality stocks</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div style='background: white; padding: 1.2rem; border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center;'>
            <div style='font-size: 0.85rem; color: #6c757d; margin-bottom: 0.5rem;'>PROCESSING TIME</div>
            <div style='font-size: 2rem; font-weight: 600; color: #28a745;'>3-5</div>
            <div style='font-size: 0.85rem; color: #6c757d;'>minutes average</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Methodology explanation with interactive cards
    with st.expander("📊 Screening Methodology - How It Works", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("""
            **Quality Metrics (70% weight)**
            - **Profitability:** ROIC, ROE, Operating Margins
            - **Financial Health:** Altman Z-Score, Debt Ratios
            - **Cash Quality:** Cash Conversion, FCF/NI Ratio
            - **Moat Score:** Competitive Advantages
            - **Earnings Quality:** Beneish M-Score (fraud detection)

            **Value Metrics (30% weight)**
            - **Valuation Multiples:** P/E, P/B, EV/EBITDA
            - **Growth-Adjusted:** PEG Ratio
            - **Intrinsic Value:** DCF-based fair value estimates
            """)

        with col2:
            st.markdown("""
            **Technical Validation**
            - **Multi-timeframe Momentum:** 12M, 6M, 3M, 1M trends
            - **Overextension Risk:** Distance from MA200
            - **Trend Quality:** ADX, slope analysis
            - **Technical Veto:** Filters out poor setups

            **Guardrails System**
            -  **VERDE:** All quality checks passed
            -  **AMBAR:** Minor concerns, needs review
            -  **ROJO:** Critical red flags, avoid
            """)

    st.markdown("---")

    # Big run button with better design
    if st.button("▶️ Run Screener Analysis", type="primary", use_container_width=True, help="Start comprehensive screening process"):

        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            status_text.text("Loading modules...")
            progress_bar.progress(3)

            # Lazy import to avoid blocking UI load
            from screener.orchestrator import ScreenerPipeline

            status_text.text("Initializing pipeline...")
            progress_bar.progress(5)

            # Initialize pipeline
            pipeline = ScreenerPipeline('settings.yaml')

            # Override config with UI values
            pipeline.config['universe']['min_market_cap'] = min_mcap * 1_000_000
            pipeline.config['universe']['min_avg_dollar_vol_3m'] = min_vol * 1_000_000
            pipeline.config['universe']['top_k'] = top_k

            # Set country filter for API
            # Uses ISO 2-letter country codes (US, CA, UK, IN, BR, JP, etc.)
            # The orchestrator will pass this to the FMP API's 'country' parameter

            if exchange_filter == "ALL":
                # All regions - clear filters (will fetch from all countries)
                pipeline.config['universe']['countries'] = []
                pipeline.config['universe']['exchanges'] = []
            else:
                # Specific country selected - use country code directly
                # exchange_filter contains 2-letter ISO codes: US, CA, UK, IN, etc.
                pipeline.config['universe']['countries'] = [exchange_filter]
                pipeline.config['universe']['exchanges'] = []

            pipeline.config['scoring']['weight_value'] = weight_value
            pipeline.config['scoring']['weight_quality'] = weight_quality
            pipeline.config['scoring']['exclude_reds'] = exclude_reds

            status_text.text("Stage 1/6: Building universe...")
            progress_bar.progress(15)

            # Run pipeline
            with st.spinner("Running screening pipeline... This may take 3-5 minutes"):
                output_csv = pipeline.run()

            progress_bar.progress(100)
            status_text.text(" Complete!")

            # Success message
            st.success(f" Screening complete! Results saved to {output_csv}")

            # Load and display results
            # Use error_bad_lines=False and on_bad_lines='warn' to handle any malformed rows gracefully
            try:
                df = pd.read_csv(output_csv, encoding='utf-8', quoting=1)  # quoting=1 is QUOTE_NONNUMERIC
            except Exception as e:
                st.error(f"Error reading results CSV: {e}")
                st.info("Attempting to read with more lenient settings...")
                # Fallback: try with on_bad_lines='skip' if available (pandas >= 1.3)
                try:
                    df = pd.read_csv(output_csv, encoding='utf-8', on_bad_lines='skip')
                except:
                    # For older pandas versions
                    df = pd.read_csv(output_csv, encoding='utf-8', error_bad_lines=False, warn_bad_lines=True)

            # Validate results before saving
            if len(df) == 0:
                st.warning(" Screening completed but no stocks met the criteria.")
                st.info(" Try lowering the minimum Market Cap or Volume thresholds.")
                progress_bar.empty()
                status_text.empty()
            else:
                # Save to session state
                st.session_state['results'] = df
                st.session_state['timestamp'] = datetime.now()
                st.session_state['config_version'] = "QARP-v3-Moat"  # Track methodology version (v3 = Moat Score added)
                st.session_state['output_csv'] = output_csv

                # Show quick summary
                buys = (df['decision'] == 'BUY').sum()
                monitors = (df['decision'] == 'MONITOR').sum()

                st.success(f" Found {buys} BUY signals and {monitors} MONITOR from {len(df)} stocks!")

                # Clear progress indicators
                progress_bar.empty()
                status_text.empty()

                # Force Streamlit to rerun so other tabs show the data
                st.rerun()

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.exception(e)
            progress_bar.empty()
            status_text.empty()

with tab2:
    st.markdown("""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 1.5rem;'>
        <h3 style='margin: 0; color: white; font-weight: 600;'>
            📊 Screening Results
        </h3>
        <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem;'>
            Detailed analysis and filtering of all screened stocks
        </p>
    </div>
    """, unsafe_allow_html=True)

    if 'results' in st.session_state:
        # Get recalculated results with current slider values
        df = get_results_with_current_params()
        timestamp = st.session_state['timestamp']

        # Session info card
        st.markdown(f"""
        <div style='background: linear-gradient(to right, #f8f9fa, #e9ecef); padding: 1rem;
                    border-radius: 8px; margin-bottom: 1.5rem; border-left: 4px solid #667eea;'>
            <div style='font-size: 0.9rem;'>
                <strong>Last Analysis:</strong> {timestamp.strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp;
                <strong>Current Weights:</strong> Quality {weight_quality:.0%}, Value {weight_value:.0%}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Advanced filters with better layout
        st.markdown("#### Filter Results")
        col1, col2, col3 = st.columns(3)
        with col1:
            decision_filter = st.multiselect(
                "Decision Signal",
                options=['BUY', 'MONITOR', 'AVOID'],
                default=['BUY', 'MONITOR'],
                help="Filter by investment recommendation"
            )
        with col2:
            guardrail_filter = st.multiselect(
                "Quality Guardrails",
                options=['VERDE', 'AMBAR', 'ROJO'],
                default=['VERDE', 'AMBAR'],
                help="Filter by accounting quality status"
            )
        with col3:
            min_score = st.slider(
                "Min Quality Score",
                0, 100, 50,
                help="Minimum composite quality score (0-100)"
            )

        # Apply filters
        filtered = df[
            (df['decision'].isin(decision_filter)) &
            (df['guardrail_status'].isin(guardrail_filter)) &
            (df['composite_0_100'] >= min_score)
        ]

        # Results count with visual indicator
        st.markdown(f"""
        <div style='background: white; padding: 1rem; border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin: 1rem 0;'>
            <span style='font-size: 1.1rem; font-weight: 600; color: #667eea;'>
                {len(filtered)} stocks match your filters
            </span>
            <span style='color: #6c757d; margin-left: 1rem;'>
                ({len(filtered)/len(df)*100:.1f}% of total universe)
            </span>
        </div>
        """, unsafe_allow_html=True)

        # Debug panel - show if ROIC-adjusted yields are present
        config_version = st.session_state.get('config_version', 'unknown')
        if config_version in ['QARP-v2', 'QARP-v3-Moat'] and 'earnings_yield_adj' in df.columns:
            with st.expander("🔧 Debug: ROIC-Adjusted Yields Verification"):
                st.caption("Verify that ROIC adjustments are working correctly")

                # Show examples of adjustments
                debug_cols = ['ticker', 'roic_%', 'moat_score', 'earnings_yield', 'earnings_yield_adj',
                             'value_score_0_100', 'quality_score_0_100', 'decision']
                available_debug_cols = [col for col in debug_cols if col in df.columns]

                if available_debug_cols:
                    st.write("**Sample: Top 10 by Quality Score**")
                    debug_df = df[available_debug_cols].sort_values('quality_score_0_100', ascending=False).head(10)
                    st.dataframe(debug_df, use_container_width=True)

                    st.caption("Expected: High ROIC companies should have earnings_yield_adj > earnings_yield")

        # Display table
        display_cols = [
            'ticker', 'name', 'sector',
            'roic_%',  # NEW: Show ROIC for transparency
            'moat_score',  # NEW: Competitive advantages score
            'composite_0_100',
            'value_score_0_100', 'quality_score_0_100',
            'guardrail_status', 'decision', 'decision_reason'  # NEW: shows WHY
        ]

        available_cols = [col for col in display_cols if col in filtered.columns]

        st.dataframe(
            filtered[available_cols].sort_values('composite_0_100', ascending=False),
            use_container_width=True,
            height=600
        )

        # Show special cases
        with st.expander("Investigate Specific Companies - Deep Dive Analysis", expanded=False):
            search_ticker = st.text_input(
                "Enter a single ticker for deep analysis (e.g., LLY, GOOGL, MSFT)",
                key="search_ticker",
                help="Enter ONE ticker to see detailed breakdown of scores, guardrails, and metrics"
            )

            if search_ticker:
                ticker = search_ticker.strip().upper()
                search_df = df[df['ticker'].str.upper() == ticker]

                if not search_df.empty:
                    # Get stock data as dictionary
                    stock_row = search_df.iloc[0]
                    stock_data = stock_row.to_dict()

                    # Header with company info
                    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

                    with col1:
                        company_name = stock_data.get('companyName', ticker)
                        industry = stock_data.get('industry', 'Unknown')
                        sector = stock_data.get('sector', 'Unknown')
                        st.markdown(f"### {ticker} - {company_name}")
                        st.caption(f"{sector} / {industry}")

                    with col2:
                        composite = stock_data.get('composite_0_100', 0)
                        comp_color = "" if composite >= 70 else "" if composite >= 50 else ""
                        st.metric("Composite Score", f"{composite:.0f}", delta=None)
                        st.caption(f"{comp_color} {stock_data.get('decision', 'N/A')}")

                    with col3:
                        value = stock_data.get('value_score_0_100', 0)
                        st.metric("Value Score", f"{value:.0f}")

                    with col4:
                        quality = stock_data.get('quality_score_0_100', 0)
                        st.metric("Quality Score", f"{quality:.0f}")

                    st.markdown("---")

                    # Create analysis tabs
                    analysis_tabs = st.tabs([
                        "Summary",
                        "Guardrails (Accounting Quality)",
                        "Quality Score Breakdown",
                        "Value Score Breakdown"
                    ])

                    # ========== TAB 1: Summary ==========
                    with analysis_tabs[0]:
                        st.markdown("### Quick Overview")

                        # Decision box
                        decision = stock_data.get('decision', 'N/A')
                        decision_reason = stock_data.get('decision_reason', '')
                        guardrail_status = stock_data.get('guardrail_status', 'N/A')
                        guardrail_reasons = stock_data.get('guardrail_reasons', '')

                        decision_color = {
                            'BUY': '#10b981',
                            'MONITOR': '#f59e0b',
                            'AVOID': '#ef4444'
                        }.get(decision, '#6b7280')

                        st.markdown(f"""
                        <div style='background: linear-gradient(135deg, {decision_color} 0%, {decision_color}dd 100%);
                                    padding: 2rem; border-radius: 12px; margin-bottom: 1.5rem; text-align: center;'>
                            <div style='color: white; font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem;'>
                                {decision}
                            </div>
                            <div style='color: white; font-size: 1.1rem; opacity: 0.95;'>
                                {decision_reason}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        # Key metrics grid
                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.markdown("#### Profitability: Profitability")
                            roic = stock_data.get('roic_%')
                            if roic is not None:
                                st.metric("ROIC", f"{roic:.1f}%")

                            fcf_margin = stock_data.get('fcf_margin_%')
                            if fcf_margin is not None:
                                st.metric("FCF Margin", f"{fcf_margin:.1f}%")

                            moat = stock_data.get('moat_score')
                            if moat is not None:
                                st.metric("Moat Score", f"{moat:.0f}/100")

                        with col2:
                            st.markdown("#### Valuation: Valuation")
                            ey_adj = stock_data.get('earnings_yield_adj')
                            if ey_adj is not None:
                                st.metric("Earnings Yield (Adj)", f"{ey_adj:.1f}%")

                            fcf_yield_adj = stock_data.get('fcf_yield_adj')
                            if fcf_yield_adj is not None:
                                st.metric("FCF Yield (Adj)", f"{fcf_yield_adj:.1f}%")

                            sh_yield = stock_data.get('shareholder_yield_%')
                            if sh_yield is not None:
                                st.metric("Shareholder Yield", f"{sh_yield:+.1f}%")

                        with col3:
                            st.markdown("#### Financial Health: Financial Health")

                            guardrail_color = {
                                'VERDE': '',
                                'AMBAR': '',
                                'ROJO': ''
                            }.get(guardrail_status, '')

                            st.markdown(f"**Guardrail Status:** {guardrail_color} {guardrail_status}")
                            if guardrail_reasons:
                                st.caption(guardrail_reasons)

                            int_cov = stock_data.get('interestCoverage')
                            if int_cov is not None:
                                st.metric("Interest Coverage", f"{min(int_cov, 50):.1f}x")

                            net_debt_ebitda = stock_data.get('netDebt_ebitda')
                            if net_debt_ebitda is not None:
                                st.metric("Net Debt/EBITDA", f"{net_debt_ebitda:.1f}x")

                        # Full data table (expandable)
                        with st.expander("📊 View All Metrics"):
                            detail_cols = ['ticker', 'roic_%', 'moat_score', 'earnings_yield', 'earnings_yield_adj',
                                          'value_score_0_100', 'quality_score_0_100', 'composite_0_100',
                                          'guardrail_status', 'decision', 'decision_reason',
                                          'pricing_power_score', 'operating_leverage_score', 'roic_persistence_score',
                                          'fcf_margin_%', 'cfo_to_ni', 'interestCoverage', 'netDebt_ebitda',
                                          'revenue_growth_3y', 'shareholder_yield_%']
                            available_detail_cols = [col for col in detail_cols if col in search_df.columns]

                            st.dataframe(search_df[available_detail_cols], use_container_width=True)

                    # ========== TAB 2: Guardrails ==========
                    with analysis_tabs[1]:
                        try:
                            from screener.advanced_ui import render_guardrails_breakdown
                            from screener.ingest import FMPClient
                            import yaml
                            import os

                            # Load config
                            config_file = 'settings_premium.yaml' if os.path.exists('settings_premium.yaml') else 'settings.yaml'
                            with open(config_file, 'r') as f:
                                config = yaml.safe_load(f)

                            # Get API key
                            api_key = None
                            if 'FMP_API_KEY' in st.secrets:
                                api_key = st.secrets['FMP_API_KEY']
                            elif 'FMP' in st.secrets:
                                api_key = st.secrets['FMP']

                            if not api_key:
                                api_key = os.getenv('FMP_API_KEY')

                            if not api_key:
                                api_key = config['fmp'].get('api_key')

                            if api_key and not api_key.startswith('${'):
                                fmp_client = FMPClient(api_key, config)

                                # Get guardrails data from the row
                                guardrails_data = {}

                                # Extract all guardrail-related columns
                                guardrail_keys = [
                                    'guardrail_status', 'guardrail_reasons', 'altmanZ', 'beneishM',
                                    'accruals_noa_%', 'netShareIssuance_12m_%', 'mna_flag',
                                    'revenue_growth_3y', 'debt_maturity_<24m_%', 'rate_mix_variable_%'
                                ]

                                for key in guardrail_keys:
                                    if key in stock_data:
                                        guardrails_data[key] = stock_data[key]

                                # Parse guardrail_reasons to extract detailed metrics
                                import re
                                reasons = guardrails_data.get('guardrail_reasons', '')

                                # Extract FCF/NI from reasons (e.g., "FCF/NI 154%")
                                fcf_ni_match = re.search(r'FCF/NI\s+([\d.]+)%', reasons)
                                fcf_ni_value = float(fcf_ni_match.group(1)) if fcf_ni_match else stock_data.get('cfo_to_ni')

                                # Extract CCC from reasons (e.g., "CCC +68 days")
                                ccc_match = re.search(r'CCC\s+([+-]?\d+)\s+days', reasons)
                                ccc_value = float(ccc_match.group(1)) if ccc_match else None

                                # Determine CCC trend from reasons
                                ccc_trend = 'Unknown'
                                if 'severe deterioration' in reasons.lower():
                                    ccc_trend = 'Severe Deterioration'
                                elif 'deterioration' in reasons.lower():
                                    ccc_trend = 'Deteriorating'
                                elif 'improvement' in reasons.lower():
                                    ccc_trend = 'Improving'

                                # Build cash_conversion dict with parsed data
                                # Safely build FCF/NI flag
                                fcf_flag = ["FCF/NI data not available"]
                                if fcf_ni_value is not None:
                                    fcf_flag = [f"FCF/NI {fcf_ni_value:.0f}%"]

                                guardrails_data['cash_conversion'] = {
                                    'fcf_to_ni_current': fcf_ni_value,
                                    'fcf_to_ni_avg_8q': fcf_ni_value,  # Approximation
                                    'fcf_to_revenue_current': stock_data.get('fcf_margin_%'),
                                    'capex_intensity_current': None,
                                    'status': 'VERDE' if fcf_ni_value and fcf_ni_value >= 80 else 'AMBAR' if fcf_ni_value and fcf_ni_value >= 60 else 'ROJO',
                                    'flags': fcf_flag
                                }

                                # Build working_capital dict with parsed data
                                # Safely build CCC flag
                                ccc_flags = []
                                if ccc_value is not None:
                                    ccc_flags = [f"CCC {ccc_value:.0f} days ({ccc_trend})"]

                                guardrails_data['working_capital'] = {
                                    'ccc_current': ccc_value,
                                    'dso_current': None,
                                    'dio_current': None,
                                    'ccc_trend': ccc_trend,
                                    'dso_trend': 'Unknown',
                                    'dio_trend': 'Unknown',
                                    'status': 'ROJO' if 'severe deterioration' in reasons.lower() else 'AMBAR' if 'deterioration' in reasons.lower() else 'VERDE',
                                    'flags': ccc_flags
                                }

                                # Build margin_trajectory dict
                                guardrails_data['margin_trajectory'] = {
                                    'gross_margin_current': None,
                                    'operating_margin_current': None,
                                    'gross_margin_trajectory': 'Unknown',
                                    'operating_margin_trajectory': 'Unknown',
                                    'status': 'VERDE'
                                }

                                # Build debt_maturity_wall dict
                                debt_pct = stock_data.get('debt_maturity_<24m_%')
                                int_cov = stock_data.get('interestCoverage')

                                guardrails_data['debt_maturity_wall'] = {
                                    'debt_due_12m': None,
                                    'short_term_debt_pct': debt_pct,
                                    'liquidity_ratio': None,
                                    'interest_coverage': int_cov,
                                    'status': 'VERDE' if int_cov and int_cov >= 5 else 'AMBAR' if int_cov and int_cov >= 3 else 'ROJO',
                                    'flags': []
                                }

                                # Render the breakdown
                                render_guardrails_breakdown(
                                    symbol=ticker,
                                    guardrails_data=guardrails_data,
                                    fmp_client=fmp_client,
                                    industry=industry
                                )
                            else:
                                st.error("FMP API key not configured. Cannot load detailed guardrails analysis.")

                        except Exception as e:
                            st.error(f"Error loading guardrails breakdown: {e}")
                            if st.checkbox("Show error details", key="guardrails_error"):
                                st.exception(e)

                    # ========== TAB 3: Quality Score ==========
                    with analysis_tabs[2]:
                        try:
                            from screener.advanced_ui import render_quality_score_breakdown

                            is_financial = stock_data.get('is_financial', False)

                            render_quality_score_breakdown(
                                symbol=ticker,
                                stock_data=stock_data,
                                is_financial=is_financial
                            )

                        except Exception as e:
                            st.error(f"Error loading quality score breakdown: {e}")
                            if st.checkbox("Show error details", key="quality_error"):
                                st.exception(e)

                    # ========== TAB 4: Value Score ==========
                    with analysis_tabs[3]:
                        try:
                            from screener.advanced_ui import render_value_score_breakdown

                            is_financial = stock_data.get('is_financial', False)

                            render_value_score_breakdown(
                                symbol=ticker,
                                stock_data=stock_data,
                                is_financial=is_financial
                            )

                        except Exception as e:
                            st.error(f"Error loading value score breakdown: {e}")
                            if st.checkbox("Show error details", key="value_error"):
                                st.exception(e)

                else:
                    st.warning(f"❌ No results found for: {ticker}")
                    st.info("💡 Tip: Make sure the ticker exists in the screener results above.")

        # Download buttons
        st.markdown("### 📥 Download Results")
        col1, col2 = st.columns(2)

        with col1:
            import csv as csv_module
            csv = df.to_csv(index=False, quoting=csv_module.QUOTE_NONNUMERIC).encode('utf-8')
            st.download_button(
                label="📄 Download CSV",
                data=csv,
                file_name=f"screener_results_{timestamp.strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )

        with col2:
            try:
                excel_data = create_screener_excel(df, timestamp)
                st.download_button(
                    label=" Download Excel (with Summary)",
                    data=excel_data,
                    file_name=f"screener_results_{timestamp.strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Excel export failed: {e}")
                st.caption("Try CSV download instead")

    else:
        st.info("👈 Run the screener first to see results here")

with tab3:
    st.markdown("""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 2rem; border-radius: 12px; color: white; margin-bottom: 2rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
        <h2 style='margin: 0; color: white; font-weight: 700;'>Analytics & Sector Breakdown</h2>
        <p style='margin: 0.5rem 0 0 0; opacity: 0.95;'>
            Distribution analysis, sector performance, and portfolio insights
        </p>
    </div>
    """, unsafe_allow_html=True)

    if 'results' in st.session_state:
        # Get recalculated results with current slider values
        df = get_results_with_current_params()

        # Validate sufficient data
        if len(df) < 5:
            st.warning(" Not enough data for analytics (minimum 5 stocks required)")
            st.info(" Try lowering the Min Market Cap or Volume thresholds.")
        else:
            try:
                # Sector breakdown
                st.subheader("Sector Distribution")

                col1, col2 = st.columns([2, 1])
                
                with col1:
                    # Sector counts by decision
                    sector_decision = df.groupby(['sector', 'decision']).size().unstack(fill_value=0)
                
                    # Create stacked bar chart
                    import plotly.graph_objects as go
                
                    fig = go.Figure()
                    for decision in ['BUY', 'MONITOR', 'AVOID']:
                        if decision in sector_decision.columns:
                            fig.add_trace(go.Bar(
                                name=decision,
                                x=sector_decision.index,
                                y=sector_decision[decision],
                                marker_color='green' if decision == 'BUY' else 'orange' if decision == 'MONITOR' else 'red'
                            ))
                
                    fig.update_layout(
                        barmode='stack',
                        title="Stocks by Sector and Decision",
                        xaxis_title="Sector",
                        yaxis_title="Count",
                        height=400,
                        xaxis_tickangle=-45
                    )
                
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    # Sector summary table
                    sector_summary = df.groupby('sector').agg({
                        'composite_0_100': 'mean',
                        'ticker': 'count'
                    }).round(1)
                    sector_summary.columns = ['Avg Score', 'Count']
                    sector_summary = sector_summary.sort_values('Avg Score', ascending=False)
                
                    st.dataframe(
                        sector_summary,
                        use_container_width=True,
                        height=400
                    )
                
                st.markdown("---")
                
                # Rejection reasons analysis
                st.subheader("Rejection Analysis")
                
                avoided = df[df['decision'] == 'AVOID']
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("Total AVOID", len(avoided), f"{len(avoided)/len(df)*100:.1f}%")
                
                    # Guardrail breakdown
                    guardrail_breakdown = avoided['guardrail_status'].value_counts()
                
                    fig = go.Figure(data=[go.Pie(
                        labels=guardrail_breakdown.index,
                        values=guardrail_breakdown.values,
                        marker=dict(colors=['red', 'orange', 'green']),
                        hole=0.3
                    )])
                    fig.update_layout(title="Rejection by Guardrail Status", height=300)
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    # Top rejection reasons
                    st.write("**Top Rejection Reasons:**")
                
                    if 'guardrail_reasons' in avoided.columns:
                        all_reasons = []
                        for reasons in avoided['guardrail_reasons'].dropna():
                            all_reasons.extend([r.strip() for r in str(reasons).split(';')])
                
                        if all_reasons:
                            from collections import Counter
                            reason_counts = Counter(all_reasons).most_common(10)
                
                            reason_df = pd.DataFrame(reason_counts, columns=['Reason', 'Count'])
                            st.dataframe(reason_df, use_container_width=True, height=300)
                        else:
                            st.info("No specific reasons recorded")
                    else:
                        st.info("Guardrail reasons not available")
                
                st.markdown("---")
                
                # Score distribution
                st.subheader("Score Distribution")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    fig = go.Figure(data=[go.Histogram(
                        x=df['composite_0_100'],
                        nbinsx=20,
                        marker_color='lightblue'
                    )])
                    fig.update_layout(
                        title="Composite Score Distribution",
                        xaxis_title="Score (0-100)",
                        yaxis_title="Count",
                        height=300
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    fig = go.Figure(data=[go.Histogram(
                        x=df['value_score_0_100'],
                        nbinsx=20,
                        marker_color='lightgreen'
                    )])
                    fig.update_layout(
                        title="Value Score Distribution",
                        xaxis_title="Score (0-100)",
                        yaxis_title="Count",
                        height=300
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                with col3:
                    fig = go.Figure(data=[go.Histogram(
                        x=df['quality_score_0_100'],
                        nbinsx=20,
                        marker_color='lightcoral'
                    )])
                    fig.update_layout(
                        title="Quality Score Distribution",
                        xaxis_title="Score (0-100)",
                        yaxis_title="Count",
                        height=300
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                st.markdown("---")
                
                # Value vs Quality scatter
                st.subheader("Value vs Quality Matrix")
                
                fig = go.Figure()
                
                for decision in ['BUY', 'MONITOR', 'AVOID']:
                    mask = df['decision'] == decision
                    fig.add_trace(go.Scatter(
                        x=df[mask]['value_score_0_100'],
                        y=df[mask]['quality_score_0_100'],
                        mode='markers',
                        name=decision,
                        text=df[mask]['ticker'],
                        marker=dict(
                            size=8,
                            color='green' if decision == 'BUY' else 'orange' if decision == 'MONITOR' else 'red',
                            opacity=0.6
                        )
                    ))
                
                fig.add_hline(y=60, line_dash="dash", line_color="gray", annotation_text="Quality Threshold")
                fig.add_vline(x=60, line_dash="dash", line_color="gray", annotation_text="Value Threshold")
                
                fig.update_layout(
                    title="Value vs Quality Positioning",
                    xaxis_title="Value Score (0-100)",
                    yaxis_title="Quality Score (0-100)",
                    height=500
                )
                
                st.plotly_chart(fig, use_container_width=True)

            except Exception as e:
                st.error(f"❌ Error generating analytics: {str(e)}")
                st.info(" Try running the screener again with different parameters.")

    else:
        st.info("👈 Run the screener first to see analytics")

with tab4:
    st.markdown("""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 2rem; border-radius: 12px; color: white; margin-bottom: 2rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
        <h2 style='margin: 0; color: white; font-weight: 700;'>Guardrail Calibration Analysis</h2>
        <p style='margin: 0.5rem 0 0 0; opacity: 0.95;'>
            Accounting quality detection and guardrail effectiveness metrics
        </p>
    </div>
    """, unsafe_allow_html=True)

    if 'results' in st.session_state:
        df = get_results_with_current_params()

        st.markdown("""
        **Analyze guardrail effectiveness and detect potential false positives.**

        This tool helps you calibrate the screener by showing:
        - Distribution of each guardrail metric
        - Companies affected by each guardrail
        - High-quality companies potentially blocked incorrectly
        - Recommendations for threshold adjustments
        """)

        # Import analyzer
        try:
            from analyze_guardrails import GuardrailAnalyzer

            analyzer = GuardrailAnalyzer(df)

            # Analysis type selector
            analysis_type = st.selectbox(
                "Select Analysis Type",
                options=[
                    'Full Report',
                    ' High-Quality ROJO Deep Dive',
                    'Beneish M-Score',
                    'Altman Z-Score',
                    'Revenue Growth',
                    'M&A / Goodwill',
                    'Share Dilution',
                    'Accruals / NOA'
                ]
            )

            if st.button("Generate Analysis", type="primary"):
                with st.spinner("Analyzing guardrails..."):
                    if analysis_type == 'Full Report':
                        report = analyzer.generate_full_report()
                    elif analysis_type == ' High-Quality ROJO Deep Dive':
                        report = analyzer.analyze_high_quality_rojo_deep_dive()
                    elif analysis_type == 'Beneish M-Score':
                        report = analyzer._analyze_beneish()
                    elif analysis_type == 'Altman Z-Score':
                        report = analyzer._analyze_altman_z()
                    elif analysis_type == 'Revenue Growth':
                        report = analyzer._analyze_revenue_decline()
                    elif analysis_type == 'M&A / Goodwill':
                        report = analyzer._analyze_mna_flag()
                    elif analysis_type == 'Share Dilution':
                        report = analyzer._analyze_dilution()
                    elif analysis_type == 'Accruals / NOA':
                        report = analyzer._analyze_accruals()

                    # Display in code block for better formatting
                    st.code(report, language="text")

                    # Download button
                    st.download_button(
                        label="📥 Download Report",
                        data=report,
                        file_name=f"guardrail_analysis_{analysis_type.lower().replace(' ', '_').replace('/', '_')}.txt",
                        mime="text/plain"
                    )

            # Quick stats
            st.subheader("Quick Stats")
            col1, col2, col3 = st.columns(3)

            with col1:
                verde_count = (df['guardrail_status'] == 'VERDE').sum()
                verde_pct = (verde_count / len(df)) * 100
                st.metric("VERDE (Clean)", f"{verde_count}", f"{verde_pct:.1f}%")

            with col2:
                ambar_count = (df['guardrail_status'] == 'AMBAR').sum()
                ambar_pct = (ambar_count / len(df)) * 100
                st.metric("AMBAR (Warning)", f"{ambar_count}", f"{ambar_pct:.1f}%")

            with col3:
                rojo_count = (df['guardrail_status'] == 'ROJO').sum()
                rojo_pct = (rojo_count / len(df)) * 100
                st.metric("ROJO (Blocked)", f"{rojo_count}", f"{rojo_pct:.1f}%")

            # Top guardrail reasons
            if 'guardrail_reasons' in df.columns:
                st.subheader("Top 10 Guardrail Reasons")
                reasons = df['guardrail_reasons'].value_counts().head(10)
                reasons_df = pd.DataFrame({
                    'Reason': reasons.index,
                    'Count': reasons.values,
                    'Percentage': (reasons.values / len(df) * 100).round(1)
                })
                st.dataframe(reasons_df, use_container_width=True)

        except ImportError as e:
            st.error(f"❌ Error loading analysis tool: {str(e)}")
            st.info("Make sure analyze_guardrails.py is in the project directory")
        except Exception as e:
            st.error(f"❌ Error during analysis: {str(e)}")

    else:
        st.info("👈 Run the screener first to analyze guardrails")

with tab5:
    st.markdown("""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 2rem; border-radius: 12px; color: white; margin-bottom: 2rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
        <h2 style='margin: 0; color: white; font-weight: 700;'>Qualitative Analysis</h2>
        <p style='margin: 0.5rem 0 0 0; opacity: 0.95;'>
            Deep-dive narratives, transcripts, and management insights
        </p>
    </div>
    """, unsafe_allow_html=True)

    if 'results' in st.session_state:
        # Get recalculated results with current slider values
        df = get_results_with_current_params()

        st.markdown("""
        Deep-dive qualitative analysis for individual stocks.
        Select a ticker to get detailed fundamental analysis, moats, risks, and insider activity.
        """)

        # Ticker selection
        col1, col2 = st.columns([1, 3])

        with col1:
            # Filter by decision first
            decision_qual = st.selectbox(
                "Filter by Decision",
                options=['All', 'BUY', 'MONITOR', 'AVOID'],
                index=0
            )

            if decision_qual == 'All':
                tickers = df['ticker'].sort_values().tolist()
            else:
                tickers = df[df['decision'] == decision_qual]['ticker'].sort_values().tolist()

            selected_ticker = st.selectbox(
                "Select Ticker",
                options=tickers,
                index=0 if tickers else None
            )

        with col2:
            if selected_ticker:
                # Get stock info
                stock_data = df[df['ticker'] == selected_ticker].iloc[0]

                # Display summary card
                st.markdown(f"### {stock_data['name']} ({selected_ticker})")

                col_a, col_b, col_c, col_d = st.columns(4)
                with col_a:
                    st.metric("Decision", stock_data['decision'])
                with col_b:
                    st.metric("Composite Score", f"{stock_data['composite_0_100']:.1f}")
                with col_c:
                    st.metric("Value Score", f"{stock_data['value_score_0_100']:.1f}")
                with col_d:
                    st.metric("Quality Score", f"{stock_data['quality_score_0_100']:.1f}")

        st.markdown("---")

        if selected_ticker:
            # Add a button to clear module cache
            col_btn1, col_btn2 = st.columns(2)

            with col_btn1:
                # Run qualitative analysis button
                if st.button(f"Run Deep Analysis for {selected_ticker}", type="primary", use_container_width=True):
                    # Force reload modules to get latest code
                    modules_to_reload = [
                        'screener.ingest',
                        'screener.qualitative'
                    ]
                    for module_name in modules_to_reload:
                        if module_name in sys.modules:
                            del sys.modules[module_name]

                    with st.spinner(f"Analyzing {selected_ticker}... This may take 30-60 seconds"):
                        try:
                            from screener.qualitative import QualitativeAnalyzer
                            from screener.ingest import FMPClient

                            # Load config - USE PREMIUM CONFIG FOR PREMIUM FEATURES!
                            config_file = 'settings_premium.yaml' if os.path.exists('settings_premium.yaml') else 'settings.yaml'
                            with open(config_file, 'r') as f:
                                config = yaml.safe_load(f)

                            st.info(f" Using config: **{config_file}**")

                            # Get API key (same logic as orchestrator)
                            api_key = None
                            if 'FMP_API_KEY' in st.secrets:
                                api_key = st.secrets['FMP_API_KEY']
                            elif 'FMP' in st.secrets:
                                api_key = st.secrets['FMP']

                            if not api_key:
                                api_key = os.getenv('FMP_API_KEY')

                            if not api_key:
                                api_key = config['fmp'].get('api_key')

                            if not api_key or api_key.startswith('${'):
                                st.error("FMP_API_KEY not found. Please configure it in Streamlit secrets.")
                                st.stop()

                            # Initialize FMP client and analyzer
                            fmp_client = FMPClient(api_key, config)  # Pass full config for cache & premium settings
                            analyzer = QualitativeAnalyzer(fmp_client, config)

                            # Get company data from results for context
                            df = st.session_state['results']
                            stock_data = df[df['ticker'] == selected_ticker].iloc[0]
                            company_type = stock_data.get('company_type', 'unknown')

                            # Run analysis
                            analysis = analyzer.analyze_symbol(
                                selected_ticker,
                                company_type=company_type,
                                peers_df=df
                            )

                            if analysis and 'error' not in analysis:
                                st.session_state[f'qual_{selected_ticker}'] = analysis
                                st.success(" Analysis complete!")
                                st.rerun()  # Rerun to show the new results
                            else:
                                st.error(f"❌ Analysis failed: {analysis.get('error', 'Unknown error')}")

                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
                            st.code(traceback.format_exc())

            with col_btn2:
                if st.button("Clear Cache & Reload Modules", use_container_width=True):
                    # Clear this ticker's cache
                    if f'qual_{selected_ticker}' in st.session_state:
                        del st.session_state[f'qual_{selected_ticker}']

                    # Force reload Python modules
                    modules_to_reload = [
                        'screener.ingest',
                        'screener.qualitative',
                        'screener.features',
                        'screener.guardrails',
                        'screener.scoring'
                    ]
                    for module_name in modules_to_reload:
                        if module_name in sys.modules:
                            del sys.modules[module_name]

                    st.success(" Cache cleared and modules reloaded. Click 'Run Deep Analysis' again.")

            # Display cached analysis if available
            if f'qual_{selected_ticker}' in st.session_state:
                analysis = st.session_state[f'qual_{selected_ticker}']

                # Check if analysis is from old version (has DEBUG messages)
                intrinsic = analysis.get('intrinsic_value', {})
                notes = intrinsic.get('notes', [])
                has_old_debug = any('DEBUG:' in str(note) for note in notes)

                if has_old_debug:
                    st.warning(f" Cached analysis for {selected_ticker} is from an older version with outdated diagnostics.")
                    # Clear the cache
                    del st.session_state[f'qual_{selected_ticker}']
                    st.info(" Cache cleared. Please click the ' Run Deep Analysis' button above again to get fresh results with improved diagnostics.")
                    st.markdown("""
                    **New features you'll get:**
                    -  Auto-detection of company type (non_financial, financial, reit, utility)
                    -  Detailed error messages showing exact failure points and data values
                    -  Color-coded diagnostic messages (green=success, red=error, yellow=warning)
                    -  Specific troubleshooting info (e.g., "OCF=X, capex=Y, base_cf=Z")
                    """)
                    # Don't show anything else - wait for user to click button again
                elif f'qual_{selected_ticker}' in st.session_state:
                    # Only show analysis if it's valid (no DEBUG messages)
                    # Business Summary
                    st.subheader("Business Summary")
                    st.write(analysis.get('business_summary', 'Not available'))

                    st.markdown("---")

                    # Moats
                    col1, col2 = st.columns(2)

                    with col1:
                        st.subheader("Competitive Moats")
                        moats = analysis.get('moats', [])
                        if moats:
                            for moat in moats:
                                st.markdown(f"- {moat}")
                        else:
                            st.info("No clear moats identified")

                    with col2:
                        st.subheader("Key Risks")
                        risks = analysis.get('risks', [])
                        if risks:
                            for risk in risks:
                                st.markdown(f"- {risk}")
                        else:
                            st.info("No major risks identified")

                    st.markdown("---")

                    # Insider Activity & Ownership
                    st.subheader("Insider Activity & Ownership")
                    insider = analysis.get('insider_trading', {})

                    if insider:
                        # Ownership metrics
                        col1, col2, col3, col4 = st.columns(4)

                        with col1:
                            insider_own = insider.get('insider_ownership_pct')
                            if insider_own is not None:
                                st.metric("Insider Ownership", f"{insider_own:.2f}%")
                            else:
                                st.metric("Insider Ownership", "N/A")

                        with col2:
                            inst_own = insider.get('institutional_ownership_pct')
                            if inst_own is not None:
                                st.metric("Institutional Own.", f"{inst_own:.1f}%")
                            else:
                                st.metric("Institutional Own.", "N/A")

                        with col3:
                            dilution = insider.get('net_share_issuance_12m_%')
                            if dilution is not None:
                                delta_color = "inverse" if dilution > 0 else "normal"
                                st.metric("Share Change (12M)", f"{dilution:+.1f}%",
                                         delta="Dilution" if dilution > 0 else "Buyback" if dilution < 0 else "Flat",
                                         delta_color=delta_color)
                            else:
                                st.metric("Share Change (12M)", "N/A")

                        with col4:
                            assessment = insider.get('assessment', 'neutral')
                            emoji_map = {'positive': '', 'neutral': '', 'negative': ''}
                            emoji = emoji_map.get(assessment, '')
                            st.metric("Assessment", f"{emoji} {assessment.title()}")

                        # Additional context
                        if insider_own is not None:
                            if insider_own >= 15:
                                st.success("✓ Strong insider ownership (≥15%) indicates good alignment with shareholders")
                            elif insider_own >= 5:
                                st.info("✓ Moderate insider ownership (5-15%)")
                            elif insider_own < 1:
                                st.warning(" Low insider ownership (<1%) - weak alignment signal")

                    else:
                        st.info("Ownership data not available")

                    st.markdown("---")

                    # Recent News
                    st.subheader("Recent News & Events")
                    news = analysis.get('recent_news', [])

                    if news:
                        for item in news[:5]:
                            st.markdown(f"**{item.get('date', 'N/A')}**: {item.get('headline', 'No headline')}")
                            st.caption(item.get('summary', '')[:200])
                    else:
                        st.info("No recent news available")

                    st.markdown("---")

                    # Intrinsic Value Estimation
                    st.subheader("Intrinsic Value Estimation")
                    intrinsic = analysis.get('intrinsic_value', {})

                    # Show section if we have intrinsic_value dict (even if current_price is missing)
                    if intrinsic and 'current_price' in intrinsic:
                        # First row: 4 main valuation metrics
                        col1, col2, col3, col4 = st.columns(4)

                        current_price = intrinsic.get('current_price', 0)

                        with col1:
                            if current_price and current_price > 0:
                                st.metric("Current Price", f"${current_price:.2f}")
                            else:
                                st.metric("Current Price", "N/A")
                                st.caption(" Price data unavailable")

                        with col2:
                            dcf_val = intrinsic.get('dcf_value')
                            if dcf_val and dcf_val > 0:
                                st.metric("DCF Value", f"${dcf_val:.2f}")
                            else:
                                st.metric("DCF Value", "N/A")

                        with col3:
                            fwd_val = intrinsic.get('forward_multiple_value')
                            if fwd_val and fwd_val > 0:
                                st.metric("Forward Multiple", f"${fwd_val:.2f}")
                            else:
                                st.metric("Forward Multiple", "N/A")

                        with col4:
                            fair_val = intrinsic.get('weighted_value')
                            if fair_val and fair_val > 0:
                                st.metric("Fair Value", f"${fair_val:.2f}")
                            else:
                                st.metric("Fair Value", "N/A")

                        # Second row: PEG Ratio + Intrinsic Value PEG-Forward
                        st.markdown("")  # Spacing

                        # Get PEG and related data from correct location
                        peg_ratio = None
                        pe_ratio = None
                        eps_growth = None
                        if 'valuation_multiples' in intrinsic:
                            company_vals = intrinsic['valuation_multiples'].get('company', {})
                            peg_ratio = company_vals.get('peg', None)
                            pe_ratio = company_vals.get('pe', None)
                            eps_growth = company_vals.get('eps_growth_%', None)

                        if peg_ratio and peg_ratio > 0:
                            # Calculate PEG-based Intrinsic Value
                            # Formula: Fair Value = Current Price × (Fair PEG / Current PEG)
                            # Fair PEG = 1.0 (conservative) or 1.5 (growth premium)
                            fair_peg_conservative = 1.0
                            fair_peg_growth = 1.5

                            peg_intrinsic_conservative = current_price * (fair_peg_conservative / peg_ratio) if current_price > 0 else None
                            peg_intrinsic_growth = current_price * (fair_peg_growth / peg_ratio) if current_price > 0 else None

                            # Color-coded PEG display
                            if peg_ratio < 1.0:
                                peg_color = ""
                                peg_label = "Excelente"
                            elif peg_ratio < 1.5:
                                peg_color = ""
                                peg_label = "Bueno (GARP)"
                            elif peg_ratio < 2.0:
                                peg_color = ""
                                peg_label = "Aceptable"
                            else:
                                peg_color = ""
                                peg_label = "Caro para Growth"

                            col_peg1, col_peg2, col_peg3 = st.columns([1, 2, 2])
                            with col_peg1:
                                # Show Intrinsic Value as main metric, PEG in caption
                                if peg_intrinsic_conservative:
                                    upside_conservative = ((peg_intrinsic_conservative - current_price) / current_price) * 100
                                    st.metric("Valor PEG", f"${peg_intrinsic_conservative:.2f}", delta=f"{upside_conservative:+.1f}%")
                                    st.caption(f"PEG: {peg_ratio:.2f} | EPS Growth: {eps_growth:.1f}%" if eps_growth else f"PEG: {peg_ratio:.2f}")
                            with col_peg2:
                                st.markdown(f"### {peg_color} **{peg_label}**")
                                st.caption(f"*Fair PEG = 1.0 (conservador)*")
                            with col_peg3:
                                if peg_intrinsic_growth:
                                    upside_growth = ((peg_intrinsic_growth - current_price) / current_price) * 100
                                    st.caption(f"**Growth PEG 1.5:** ${peg_intrinsic_growth:.2f} ({upside_growth:+.1f}%)")
                                st.caption("*Premium para empresas de alto crecimiento*")
                        else:
                            st.info(" **PEG Ratio:** N/A (Data not available)")

                        # === Valuation Method Recommendation ===
                        # Determine which valuation method is most appropriate
                        peg_ratio = None
                        if 'valuation_multiples' in intrinsic:
                            company_vals = intrinsic['valuation_multiples'].get('company', {})
                            peg_ratio = company_vals.get('peg', None)

                        revenue_growth = None
                        if 'growth_consistency' in intrinsic:
                            revenue_growth = intrinsic['growth_consistency'].get('revenue_growth_5y_cagr', None)

                        # Fallback: Infer growth from PEG if available
                        if not revenue_growth and peg_ratio:
                            company_vals = intrinsic.get('valuation_multiples', {}).get('company', {})
                            eps_growth = company_vals.get('eps_growth_%', None)
                            if eps_growth:
                                revenue_growth = eps_growth  # Use EPS growth as proxy

                        # Determine predominant method
                        # Priority 1: If PEG < 1.5, it's a growth company (even without explicit revenue growth data)
                        if peg_ratio and peg_ratio < 1.5:
                            # Growth company - PEG is king
                            method_icon = ""
                            method_name = "PEG Ratio (Growth Valuation)"
                            growth_text = f"{revenue_growth:.1f}%" if revenue_growth else "Datos limitados (inferido de PEG < 1.5)"
                            method_reason = f"""
**Por qué PEG es mejor para esta empresa:**
- PEG Ratio: {peg_ratio:.2f} (< 1.5 = Growth at reasonable price)
- Growth: {growth_text}
- DCF subestima empresas de crecimiento porque:
  - No captura AI/platform optionality
  - Assumptions conservadoras (3% terminal growth típico)
  - No valora network effects ni moats digitales
- **PEG captura el valor del crecimiento futuro** (P/E ajustado por growth)
- Empresas similares: Amazon, Google, Meta en fase de crecimiento alto
"""
                        elif peg_ratio and peg_ratio > 2.5 and revenue_growth and revenue_growth < 5:
                            # Mature company - DCF is king
                            method_icon = "<i class='bi bi-building-fill'></i>"
                            method_name = "DCF (Mature Company Valuation)"
                            method_reason = f"""
**Por qué DCF es mejor para esta empresa:**
- PEG Ratio: {peg_ratio:.2f} (> 2.5 = Expensive for growth)
- Revenue Growth: {revenue_growth:.1f}% (Mature/stable)
- DCF es ideal para empresas maduras porque:
  - Cash flows predecibles y estables
  - Growth limitado → PEG pierde relevancia
  - Mejor para dividendos y buybacks
- **DCF captura el valor intrínseco de FCF estable**
- Empresas similares: Johnson & Johnson, Procter & Gamble, Coca-Cola
"""
                        elif peg_ratio and revenue_growth and 1.5 <= peg_ratio <= 2.5 and 5 <= revenue_growth <= 10:
                            # Balanced - use both methods
                            method_icon = "<i class='bi bi-diagram-3-fill'></i>"
                            method_name = "Hybrid (DCF + PEG)"
                            method_reason = f"""
**Por qué usar ambos métodos:**
- PEG Ratio: {peg_ratio:.2f} (1.5-2.5 = GARP territory)
- Revenue Growth: {revenue_growth:.1f}% (Moderate growth)
- Empresa en transición: ni puro growth ni pura mature
- **DCF valora cash flows actuales** | **PEG valora potencial de crecimiento**
- Fair Value (weighted average) combina ambas perspectivas
- Empresas similares: Microsoft, Apple (madurez con crecimiento sostenible)
"""
                        else:
                            # Insufficient data or unknown profile
                            method_icon = ""
                            method_name = "Multiple Methods (Insuficiente data)"
                            method_reason = f"""
**Recomendación:**
- Se usan múltiples métodos (DCF, Forward Multiple, Fair Value)
- PEG: {f'{peg_ratio:.2f}' if peg_ratio else 'N/A'}
- Revenue Growth: {f'{revenue_growth:.1f}%' if revenue_growth else 'N/A'}
- Se recomienda usar Fair Value (weighted average) como estimación conservadora
"""

                        st.info(f"{method_icon} **Método de Valoración Predominante:** {method_name}\n\n{method_reason}")

                        # Show debug notes if present (for troubleshooting)
                        notes = intrinsic.get('notes', [])
                        if notes:
                            with st.expander(" Calculation Details & Debug Info"):
                                for note in notes:
                                    if note.startswith('✓'):
                                        st.success(note)
                                    elif note.startswith('✗') or 'ERROR' in note or 'failed' in note.lower():
                                        st.error(note)
                                    elif note.startswith('') or 'WARNING' in note:
                                        st.warning(note)
                                    else:
                                        st.info(note)

                        # Upside/Downside
                        if intrinsic.get('upside_downside_%') is not None:
                            upside = intrinsic.get('upside_downside_%', 0)
                            assessment = intrinsic.get('valuation_assessment', 'Unknown')
                            confidence = intrinsic.get('confidence', 'Low')

                            # === EL MARTILLO DEL PEG: Veto power sobre DCF en Growth Stocks ===
                            # Para empresas de crecimiento, PEG > DCF porque captura optionality
                            # Si PEG < 1.5 y Growth > 10% → VERDE, sin importar DCF

                            growth_override_applied = False
                            growth_override_reason = None

                            # Get PEG Ratio from CORRECT location (valuation_multiples)
                            peg_ratio = None
                            if 'valuation_multiples' in intrinsic:
                                company_vals = intrinsic['valuation_multiples'].get('company', {})
                                peg_ratio = company_vals.get('peg', None)

                            # Fallback: try stock_data (might be in features)
                            if not peg_ratio:
                                peg_ratio = stock_data.get('peg_ratio', None)

                            # Get revenue growth from intrinsic data or stock_data
                            revenue_growth = None
                            if 'growth_consistency' in intrinsic:
                                revenue_growth = intrinsic['growth_consistency'].get('revenue_growth_5y_cagr', None)

                            # Fallback: try to get from features
                            if not revenue_growth:
                                # Check if we have earnings growth used for PEG
                                # If PEG exists and P/E exists, we can infer growth
                                pe_ttm = stock_data.get('pe_ttm', None)
                                if peg_ratio and pe_ttm and peg_ratio > 0:
                                    # PEG = P/E / Growth → Growth = P/E / PEG
                                    revenue_growth = (pe_ttm / peg_ratio) if peg_ratio > 0 else None

                            # Determine if it's a growth stock
                            is_growth_stock = False
                            if revenue_growth and revenue_growth > 10:  # >10% growth
                                is_growth_stock = True
                            elif peg_ratio and peg_ratio < 2.0:  # PEG suggests growth
                                is_growth_stock = True

                            # Get Reverse DCF signal (optional, not required)
                            reverse_dcf_signal = None
                            if 'reverse_dcf' in intrinsic:
                                interpretation = intrinsic['reverse_dcf'].get('interpretation', '')
                                if 'UNDERVALUED' in interpretation.upper():
                                    reverse_dcf_signal = 'UNDERVALUED'

                            # === MARTILLO DEL PEG: Override Logic ===
                            #Quality Tier 1: PEG excelente (< 1.2) + Growth Stock → VERDE inmediato
                            #Quality Tier 2: PEG bueno (< 1.5) + Reverse DCF UNDERVALUED → VERDE
                            #Quality Tier 3: PEG razonable (< 2.0) + High Growth (>15%) → VERDE

                            peg_hammer_triggered = False

                            if peg_ratio:
                                #Quality Tier 1: PEG excelente (< 1.2) en growth stock
                                if peg_ratio < 1.2 and is_growth_stock:
                                    peg_hammer_triggered = True
                                    growth_override_reason = f"""
                                    **🔨 EL MARTILLO DEL PEG -Quality Tier 1: Ganga Absoluta**
                                    - PEG Ratio: {peg_ratio:.2f} (< 1.2 = Excelente)
                                    - Growth Stock: Sí (crecimiento sostenible)
                                    - DCF Fair Value: ${intrinsic.get('weighted_value', 0):.0f} vs Price: ${intrinsic.get('current_price', 0):.0f}

                                    **Veredicto: COMPRA CLARA (PEG tiene veto sobre DCF)**

                                    DCF undervalues growth porque:
                                    • No captura AI/platform optionality
                                    • Assumptions conservadoras (3% terminal growth)
                                    • PEG < 1.2 = "Pagando menos de lo que el crecimiento vale"

                                    **Empresas similares con PEG < 1.2:** Amazon 2015 (PEG 0.8), Google 2018 (PEG 1.0), Meta 2023 (PEG 0.9)
                                    """

                                #Quality Tier 2: PEG bueno (< 1.5) + Reverse DCF confirma
                                elif peg_ratio < 1.5 and reverse_dcf_signal == 'UNDERVALUED':
                                    peg_hammer_triggered = True
                                    growth_override_reason = f"""
                                    **🔨 EL MARTILLO DEL PEG -Quality Tier 2: Growth at Reasonable Price**
                                    - PEG Ratio: {peg_ratio:.2f} (< 1.5 = GARP territory)
                                    - Reverse DCF: UNDERVALUED (mercado pesimista sobre futuro)
                                    - DCF Fair Value: ${intrinsic.get('weighted_value', 0):.0f} vs Price: ${intrinsic.get('current_price', 0):.0f}

                                    **Veredicto: COMPRA (Doble confirmación PEG + Reverse DCF)**

                                    2 señales independientes confirman undervaluation:
                                    1. PEG < 1.5 → Crecimiento a precio razonable
                                    2. Reverse DCF → Mercado espera menos crecimiento del real
                                    """

                                #Quality Tier 3: PEG razonable (< 2.0) en high growth (>15%)
                                elif peg_ratio < 2.0 and revenue_growth and revenue_growth > 15:
                                    peg_hammer_triggered = True
                                    growth_override_reason = f"""
                                    **🔨 EL MARTILLO DEL PEG -Quality Tier 3: High Growth Premium**
                                    - PEG Ratio: {peg_ratio:.2f} (< 2.0 aceptable para growth >15%)
                                    - Revenue Growth: {revenue_growth:.1f}% (High growth justifica premium)
                                    - DCF Fair Value: ${intrinsic.get('weighted_value', 0):.0f} vs Price: ${intrinsic.get('current_price', 0):.0f}

                                    **Veredicto: COMPRA (High growth justifica valuación)**

                                    Para empresas con crecimiento >15%, PEG < 2.0 es razonable.
                                    Regla: "Never short a dull market" → Never sell high growth at PEG < 2.0
                                    """

                            # Apply override if PEG Hammer triggered
                            if peg_hammer_triggered and assessment != 'Undervalued':
                                growth_override_applied = True
                                original_assessment = assessment
                                assessment = 'Growth Undervalued'  # Force GREEN

                                # Recalculate upside based on PEG intrinsic value (use Growth PEG 1.5)
                                current_price = intrinsic.get('current_price', 0)
                                if peg_ratio and current_price > 0:
                                    fair_peg_growth = 1.5  # Growth premium
                                    peg_intrinsic_growth = current_price * (fair_peg_growth / peg_ratio)
                                    upside = ((peg_intrinsic_growth - current_price) / current_price) * 100
                                    # Store for display
                                    growth_override_applied = True

                            # Color based on assessment (with PEG hammer override)
                            if assessment in ['Undervalued', 'Growth Undervalued']:
                                color = 'green'
                                emoji = ''
                            elif assessment == 'Overvalued':
                                color = 'red'
                                emoji = ''
                            else:
                                color = 'orange'
                                emoji = ''

                            # Display industry profile
                            industry_profile = intrinsic.get('industry_profile', 'unknown').replace('_', ' ').title()
                            primary_metric = intrinsic.get('primary_metric', 'EV/EBIT')

                            # Display main status (with PEG-driven upside if applicable)
                            display_assessment = assessment.replace('Growth Undervalued', 'Undervalued (PEG Driver)')

                            # Show upside/downside text based on whether PEG Hammer is active
                            if growth_override_applied and upside > 0:
                                upside_text = "Upside Potential"
                            else:
                                upside_text = 'upside' if upside > 0 else 'downside'

                            st.markdown(f"### {emoji} {display_assessment}: {upside:+.1f}% {upside_text}")
                            st.caption(f"**Industry Profile:** {industry_profile} | **Primary Metric:** {primary_metric}")
                            st.caption(f"**Confidence:** {confidence}")

                            # Show PEG Hammer explanation if applied
                            if growth_override_applied and growth_override_reason:
                                st.success(growth_override_reason)  # Use success (green box) instead of info

                            # Explanation
                            with st.expander("📖 Research-Based Valuation Methodology"):
                                st.markdown(f"""
                                ### Industry-Specific Approach

                                **Industry Profile:** {industry_profile}
                                **Primary Metric:** {primary_metric}

                                This valuation uses academic research (Damodaran, NYU Stern; Harbula 2009) to select
                                optimal metrics by industry characteristics:

                                **Valuation Framework:**

                                1. **Capital-Intensive** (Oil/Gas, Utilities, Manufacturing):
                                   - Primary: **EV/EBIT** (D&A reflects actual capex needs)
                                   - Research: More stable than EBITDA for capex-heavy businesses
                                   - Typical multiples: 8-12x EV/EBIT

                                2. **Asset-Light / High-Growth** (Software, Biotech):
                                   - Primary: **EV/Revenue** or **EV/EBITDA**
                                   - Research: Damodaran 2025 - Software ~98x, Biotech ~62x
                                   - Higher multiples reflect growth potential

                                3. **Asset-Based** (Banks, REITs):
                                   - Primary: **P/B** or **P/FFO**
                                   - Research: Book value best for tangible assets
                                   - Conservative multiples: 1.0-1.5x for banks

                                4. **Mature/Stable** (Consumer Staples, Healthcare):
                                   - Primary: **FCF Yield**
                                   - Research: Predictable cash flows enable accurate DCF
                                   - Higher DCF weighting (50%)

                                5. **Cyclical** (Retail, Consumer Discretionary):
                                   - Primary: **EV/EBITDA**
                                   - Research: Use normalized earnings to avoid peak/trough
                                   - Lower DCF weight (harder to project cycles)

                                ---

                                ### DCF Method
                                - **Growth Capex Adjustment**: Only maintenance capex subtracted
                                - High growth (>10% revenue): 50% capex = maintenance
                                - Moderate (5-10%): 70% maintenance
                                - Mature (<5%): 90% maintenance
                                - **WACC**: Industry-adjusted based on risk profile
                                - **Terminal Growth**: 3% perpetual

                                ### Weighting
                                - **Varies by industry** (not fixed 40/40/20)
                                - High-growth: 30% DCF, 70% Multiples
                                - Stable: 50% DCF, 50% Multiples
                                - Default: 40% DCF, 60% Multiples

                                **No P/E ratios used** - Focus on cash flow and operating metrics per best practices.
                                """)

                        # === PRICE PROJECTIONS ===
                        projections = intrinsic.get('price_projections', {})
                        if projections and 'scenarios' in projections:
                            st.markdown("---")
                            st.markdown("###  Price Projections by Scenario")

                            scenarios = projections.get('scenarios', {})

                            if scenarios:
                                # Display as table
                                scenario_names = list(scenarios.keys())

                                # Create columns for each scenario
                                cols = st.columns(len(scenario_names))

                                for i, (scenario_name, data) in enumerate(scenarios.items()):
                                    with cols[i]:
                                        # Emoji based on scenario
                                        if 'Bear' in scenario_name:
                                            emoji = '🐻'
                                            color = '#ff6b6b'
                                        elif 'Bull' in scenario_name:
                                            emoji = '🐂'
                                            color = '#51cf66'
                                        else:
                                            emoji = ''
                                            color = '#ffd43b'

                                        st.markdown(f"**{emoji} {scenario_name}**")
                                        st.caption(data.get('description', ''))
                                        st.caption(f"Growth: {data.get('growth_assumption', 'N/A')}")

                                        st.markdown("**Price Targets:**")
                                        st.metric("1 Year", f"${data.get('1Y_target', 0):.2f}",
                                                 delta=data.get('1Y_return', 'N/A'))
                                        st.metric("3 Year", f"${data.get('3Y_target', 0):.2f}",
                                                 delta=data.get('3Y_cagr', 'N/A') + " CAGR")
                                        st.metric("5 Year", f"${data.get('5Y_target', 0):.2f}",
                                                 delta=data.get('5Y_cagr', 'N/A') + " CAGR")

                                st.caption("**Note:** Projections based on fundamental growth. Not investment advice.")

                        # ==========================
                        # NEW ADVANCED METRICS
                        # ==========================

                        st.markdown("---")

                        # 1. ROIC vs WACC (Capital Efficiency) - or ROE for financials
                        capital_efficiency = intrinsic.get('capital_efficiency', {})
                        if capital_efficiency:
                            metric_name = capital_efficiency.get('metric_name', 'ROIC')
                            st.markdown(f"###  Capital Efficiency ({metric_name} vs WACC)")

                            col1, col2, col3 = st.columns(3)

                            with col1:
                                current = capital_efficiency.get('current', 0)
                                st.metric(metric_name, f"{current:.1f}%")
                                st.caption(f"3Y Avg: {capital_efficiency.get('avg_3y', 0):.1f}%")

                            with col2:
                                wacc = capital_efficiency.get('wacc', 0)
                                st.metric("WACC", f"{wacc:.1f}%")
                                st.caption(f"5Y Avg {metric_name}: {capital_efficiency.get('avg_5y', 0):.1f}%")

                            with col3:
                                spread = capital_efficiency.get('spread', 0)
                                trend = capital_efficiency.get('trend', 'stable')

                                # Color based on spread
                                if spread > 0:
                                    delta_color = "normal"
                                    emoji = ""
                                else:
                                    delta_color = "inverse"
                                    emoji = ""

                                st.metric(f"Spread ({metric_name} - WACC)", f"{spread:+.1f}%", delta=trend)

                            # Show 5-year history
                            history_5y = capital_efficiency.get('history_5y', [])
                            if history_5y:
                                st.caption(f"**{metric_name} History (last {len(history_5y)} years):** " +
                                         ", ".join([f"{h:.1f}%" for h in history_5y]))

                            assessment = capital_efficiency.get('assessment', '')
                            value_creation = capital_efficiency.get('value_creation', False)

                            if value_creation:
                                st.success(f" {assessment} - {metric_name} exceeds WACC, indicating value creation")
                            else:
                                st.error(f" {assessment} - {metric_name} below WACC, may be destroying value")

                        # 2. Quality of Earnings
                        earnings_quality = intrinsic.get('earnings_quality', {})
                        if earnings_quality:
                            st.markdown("###  Quality of Earnings")

                            col1, col2, col3, col4 = st.columns(4)

                            with col1:
                                cf_to_ni = earnings_quality.get('cash_flow_to_net_income', 0)
                                st.metric("OCF / Net Income", f"{cf_to_ni:.2f}")
                                st.caption(">1.0 is excellent")

                            with col2:
                                accruals = earnings_quality.get('accruals_ratio', 0)
                                st.metric("Accruals Ratio", f"{accruals:.2f}%")
                                st.caption("<5% is good")

                            with col3:
                                wc_trend = earnings_quality.get('working_capital_trend', 'unknown')
                                st.metric("Working Capital", wc_trend.title())

                            with col4:
                                grade = earnings_quality.get('grade', 'C')
                                assessment_eq = earnings_quality.get('assessment', '')

                                # Color grade
                                if grade in ['A', 'B']:
                                    st.success(f"**Grade: {grade}**")
                                elif grade == 'C':
                                    st.warning(f"**Grade: {grade}**")
                                else:
                                    st.error(f"**Grade: {grade}**")

                                st.caption(assessment_eq)

                            # Show issues if any
                            issues = earnings_quality.get('issues', [])
                            if issues:
                                with st.expander(" Quality Issues Detected"):
                                    for issue in issues:
                                        st.warning(f"• {issue}")

                        # 3. Profitability Analysis (Margins and Trends)
                        profitability = intrinsic.get('profitability_analysis', {})
                        if profitability:
                            st.markdown("###  Profitability Margins & Trends")

                            col1, col2, col3 = st.columns(3)

                            with col1:
                                gross = profitability.get('gross_margin', {})
                                if gross:
                                    st.metric("Gross Margin",
                                             f"{gross.get('current', 0):.1f}%",
                                             delta=f"{gross.get('current', 0) - gross.get('avg_3y', 0):.1f}% vs 3Y avg")
                                    st.caption(gross.get('trend', '→ stable'))

                            with col2:
                                operating = profitability.get('operating_margin', {})
                                if operating:
                                    st.metric("Operating Margin",
                                             f"{operating.get('current', 0):.1f}%",
                                             delta=f"{operating.get('current', 0) - operating.get('avg_3y', 0):.1f}% vs 3Y avg")
                                    st.caption(operating.get('trend', '→ stable'))

                            with col3:
                                fcf = profitability.get('fcf_margin', {})
                                if fcf:
                                    st.metric("FCF Margin",
                                             f"{fcf.get('current', 0):.1f}%",
                                             delta=f"{fcf.get('current', 0) - fcf.get('avg_3y', 0):.1f}% vs 3Y avg")
                                    st.caption(fcf.get('trend', '→ stable'))

                        # 4. Balance Sheet Strength
                        balance_sheet = intrinsic.get('balance_sheet_strength', {})
                        if balance_sheet:
                            st.markdown("---")
                            st.markdown("### 🏦 Balance Sheet Health")

                            # Overall assessment banner
                            overall = balance_sheet.get('overall_assessment', 'Unknown')
                            warnings_list = balance_sheet.get('warnings', [])

                            if overall == 'Strong':
                                st.success(f"**Overall: {overall}** - Solid financial position")
                            elif overall == 'Concerning':
                                st.error(f"**Overall: {overall}** - {', '.join(warnings_list)}")
                            else:
                                st.warning(f"**Overall: {overall}**")

                            col1, col2, col3, col4 = st.columns(4)

                            with col1:
                                de_ratio = balance_sheet.get('debt_to_equity', {})
                                if de_ratio:
                                    st.metric("Debt/Equity",
                                            f"{de_ratio.get('value', 0):.2f}x",
                                            help="Total Debt / Shareholders Equity")
                                    st.caption(de_ratio.get('assessment', ''))

                            with col2:
                                current_r = balance_sheet.get('current_ratio', {})
                                if current_r:
                                    st.metric("Current Ratio",
                                            f"{current_r.get('value', 0):.2f}x",
                                            help="Current Assets / Current Liabilities")
                                    st.caption(current_r.get('assessment', ''))

                            with col3:
                                interest_cov = balance_sheet.get('interest_coverage', {})
                                if interest_cov:
                                    val = interest_cov.get('value')
                                    if val is not None:
                                        st.metric("Interest Coverage",
                                                f"{val:.1f}x",
                                                help="EBIT / Interest Expense")
                                    else:
                                        st.metric("Interest Coverage", "N/A")
                                    st.caption(interest_cov.get('assessment', ''))

                            with col4:
                                debt_ebitda = balance_sheet.get('debt_to_ebitda', {})
                                if debt_ebitda:
                                    st.metric("Debt/EBITDA",
                                            f"{debt_ebitda.get('value', 0):.1f}x",
                                            help="Total Debt / EBITDA")
                                    st.caption(debt_ebitda.get('assessment', ''))

                            # Second row: Cash, Net Debt, Debt Trend
                            st.markdown("")
                            col1, col2, col3, col4 = st.columns(4)

                            with col1:
                                cash_info = balance_sheet.get('cash', {})
                                if cash_info:
                                    st.metric("Cash & Equivalents",
                                            cash_info.get('formatted', 'N/A'),
                                            help="Cash + Short-term Investments")

                            with col2:
                                net_debt_info = balance_sheet.get('net_debt', {})
                                if net_debt_info:
                                    st.metric("Net Debt",
                                            net_debt_info.get('formatted', 'N/A'),
                                            help="Total Debt - Cash")
                                    st.caption(net_debt_info.get('assessment', ''))

                            with col3:
                                debt_trend = balance_sheet.get('debt_trend', {})
                                if debt_trend:
                                    st.metric("Debt Trend (YoY)",
                                            f"{debt_trend.get('yoy_change_%', 0):+.1f}%")
                                    st.caption(debt_trend.get('direction', ''))

                            with col4:
                                quick_r = balance_sheet.get('quick_ratio', {})
                                if quick_r:
                                    st.metric("Quick Ratio",
                                            f"{quick_r.get('value', 0):.2f}x",
                                            help="(Current Assets - Inventory) / Current Liabilities")
                                    st.caption(quick_r.get('assessment', ''))

                        # 5. Valuation Multiples vs Peers
                        valuation_multiples = intrinsic.get('valuation_multiples', {})
                        if valuation_multiples:
                            st.markdown("---")
                            st.markdown("###  Valuation Multiples vs Peers")

                            company_vals = valuation_multiples.get('company', {})
                            peers_avg = valuation_multiples.get('peers_avg', {})
                            vs_peers = valuation_multiples.get('vs_peers', {})

                            if company_vals:
                                col1, col2, col3, col4, col5 = st.columns(5)

                                with col1:
                                    pe = company_vals.get('pe')
                                    if pe:
                                        peer_pe = peers_avg.get('pe')
                                        if peer_pe:
                                            delta_info = vs_peers.get('pe', {})
                                            delta_val = delta_info.get('premium_discount_%', 0)
                                            st.metric("P/E Ratio",
                                                    f"{pe:.1f}x",
                                                    delta=f"{delta_val:+.1f}% vs peers")
                                            st.caption(f"Peers: {peer_pe:.1f}x")
                                        else:
                                            st.metric("P/E Ratio", f"{pe:.1f}x")

                                with col2:
                                    pb = company_vals.get('pb')
                                    if pb:
                                        peer_pb = peers_avg.get('pb')
                                        if peer_pb:
                                            delta_info = vs_peers.get('pb', {})
                                            delta_val = delta_info.get('premium_discount_%', 0)
                                            st.metric("P/B Ratio",
                                                    f"{pb:.2f}x",
                                                    delta=f"{delta_val:+.1f}% vs peers")
                                            st.caption(f"Peers: {peer_pb:.2f}x")
                                        else:
                                            st.metric("P/B Ratio", f"{pb:.2f}x")

                                with col3:
                                    ps = company_vals.get('ps')
                                    if ps:
                                        peer_ps = peers_avg.get('ps')
                                        if peer_ps:
                                            delta_info = vs_peers.get('ps', {})
                                            delta_val = delta_info.get('premium_discount_%', 0)
                                            st.metric("P/S Ratio",
                                                    f"{ps:.2f}x",
                                                    delta=f"{delta_val:+.1f}% vs peers")
                                            st.caption(f"Peers: {peer_ps:.2f}x")
                                        else:
                                            st.metric("P/S Ratio", f"{ps:.2f}x")

                                with col4:
                                    ev_ebitda = company_vals.get('ev_ebitda')
                                    if ev_ebitda:
                                        peer_ev = peers_avg.get('ev_ebitda')
                                        if peer_ev:
                                            delta_info = vs_peers.get('ev_ebitda', {})
                                            delta_val = delta_info.get('premium_discount_%', 0)
                                            st.metric("EV/EBITDA",
                                                    f"{ev_ebitda:.1f}x",
                                                    delta=f"{delta_val:+.1f}% vs peers")
                                            st.caption(f"Peers: {peer_ev:.1f}x")
                                        else:
                                            st.metric("EV/EBITDA", f"{ev_ebitda:.1f}x")

                                with col5:
                                    peg = company_vals.get('peg')
                                    if peg:
                                        peer_peg = peers_avg.get('peg')
                                        eps_growth = company_vals.get('eps_growth_%', 0)
                                        if peer_peg:
                                            delta_info = vs_peers.get('peg', {})
                                            delta_val = delta_info.get('premium_discount_%', 0)
                                            st.metric("PEG Ratio",
                                                    f"{peg:.2f}",
                                                    delta=f"{delta_val:+.1f}% vs peers")
                                            st.caption(f"Growth: {eps_growth:.1f}%")
                                        else:
                                            st.metric("PEG Ratio", f"{peg:.2f}")
                                            st.caption(f"Growth: {eps_growth:.1f}%")

                                # Summary assessment
                                premium_count = sum(1 for m in vs_peers.values() if m.get('assessment') == 'Premium')
                                discount_count = sum(1 for m in vs_peers.values() if m.get('assessment') == 'Discount')

                                st.markdown("")
                                if premium_count > discount_count:
                                    st.warning(f" Trading at a **premium** to peers on {premium_count}/{len(vs_peers)} metrics")
                                elif discount_count > premium_count:
                                    st.success(f" Trading at a **discount** to peers on {discount_count}/{len(vs_peers)} metrics")
                                else:
                                    st.info(f" **In-line** with peer valuations")

                        # 6. Growth Consistency (Historical Trends)
                        growth_consistency = intrinsic.get('growth_consistency', {})
                        if growth_consistency:
                            st.markdown("---")
                            st.markdown("###  Growth Consistency & Historical Trends")

                            overall_assess = growth_consistency.get('overall_assessment', '')
                            if 'Highly Consistent' in overall_assess:
                                st.success(f"**{overall_assess}**")
                            elif 'Volatile' in overall_assess:
                                st.error(f"**{overall_assess}**")
                            else:
                                st.info(f"**{overall_assess}**")

                            # Revenue
                            revenue_data = growth_consistency.get('revenue', {})
                            if revenue_data:
                                st.markdown("#### Valuation: Revenue Growth")
                                col1, col2, col3, col4 = st.columns(4)

                                with col1:
                                    st.metric("Avg Growth",
                                            f"{revenue_data.get('avg_growth_%', 0):.1f}%/yr",
                                            help=f"Over {revenue_data.get('years', 0)} years")

                                with col2:
                                    st.metric("Consistency",
                                            revenue_data.get('consistency', 'Unknown'),
                                            help="Based on standard deviation")
                                    st.caption(f"σ = {revenue_data.get('std_dev', 0):.1f}%")

                                with col3:
                                    trend = revenue_data.get('trend', 'Unknown')
                                    if trend == 'Growing':
                                        st.success(f"**{trend}**")
                                    elif trend == 'Declining':
                                        st.error(f"**{trend}**")
                                    else:
                                        st.info(f"**{trend}**")

                                with col4:
                                    history = revenue_data.get('history', [])
                                    if history:
                                        st.caption("Last 5Y Revenue ($B):")
                                        st.caption(", ".join([f"{h:.1f}" for h in history[:5]]))

                            # Earnings
                            earnings_data = growth_consistency.get('earnings', {})
                            if earnings_data:
                                st.markdown("####  Earnings Growth")
                                col1, col2, col3, col4 = st.columns(4)

                                with col1:
                                    st.metric("Avg Growth",
                                            f"{earnings_data.get('avg_growth_%', 0):.1f}%/yr",
                                            help=f"Over {earnings_data.get('years', 0)} years")

                                with col2:
                                    st.metric("Consistency",
                                            earnings_data.get('consistency', 'Unknown'),
                                            help="Based on standard deviation")
                                    st.caption(f"σ = {earnings_data.get('std_dev', 0):.1f}%")

                                with col3:
                                    trend = earnings_data.get('trend', 'Unknown')
                                    if trend == 'Growing':
                                        st.success(f"**{trend}**")
                                    elif trend == 'Declining':
                                        st.error(f"**{trend}**")
                                    else:
                                        st.info(f"**{trend}**")

                                with col4:
                                    history = earnings_data.get('history', [])
                                    if history:
                                        st.caption("Last 5Y Earnings ($B):")
                                        st.caption(", ".join([f"{h:.1f}" for h in history[:5]]))

                            # FCF
                            fcf_data = growth_consistency.get('fcf', {})
                            if fcf_data:
                                st.markdown("#### 💸 Free Cash Flow Growth")
                                col1, col2, col3, col4 = st.columns(4)

                                with col1:
                                    st.metric("Avg Growth",
                                            f"{fcf_data.get('avg_growth_%', 0):.1f}%/yr",
                                            help=f"Over {fcf_data.get('years', 0)} years")

                                with col2:
                                    st.metric("Consistency",
                                            fcf_data.get('consistency', 'Unknown'),
                                            help="Based on standard deviation")
                                    st.caption(f"σ = {fcf_data.get('std_dev', 0):.1f}%")

                                with col3:
                                    trend = fcf_data.get('trend', 'Unknown')
                                    if trend == 'Growing':
                                        st.success(f"**{trend}**")
                                    elif trend == 'Declining':
                                        st.error(f"**{trend}**")
                                    else:
                                        st.info(f"**{trend}**")

                                with col4:
                                    history = fcf_data.get('history', [])
                                    if history:
                                        st.caption("Last 5Y FCF ($B):")
                                        st.caption(", ".join([f"{h:.1f}" for h in history[:5]]))

                        # 7. Cash Conversion Cycle (FASE 1)
                        cash_cycle = intrinsic.get('cash_conversion_cycle', {})
                        if cash_cycle:
                            st.markdown("---")
                            st.markdown("###  Cash Conversion Cycle (Working Capital Efficiency)")

                            # Overall assessment
                            assessment = cash_cycle.get('assessment', 'Unknown')
                            ccc_val = cash_cycle.get('ccc', 0)

                            if 'Excellent' in assessment:
                                st.success(f"**{assessment}** - CCC: {ccc_val:.0f} days")
                            elif 'Very Good' in assessment or 'Good' in assessment:
                                st.info(f"**{assessment}** - CCC: {ccc_val:.0f} days")
                            elif 'Poor' in assessment or 'Concerning' in assessment:
                                st.error(f"**{assessment}** - CCC: {ccc_val:.0f} days")
                            else:
                                st.warning(f"**{assessment}** - CCC: {ccc_val:.0f} days")

                            col1, col2, col3, col4 = st.columns(4)

                            with col1:
                                dso = cash_cycle.get('dso', 0)
                                st.metric("DSO (Days Sales Outstanding)",
                                        f"{dso:.0f} days",
                                        help="How long to collect receivables")

                            with col2:
                                dio = cash_cycle.get('dio', 0)
                                st.metric("DIO (Days Inventory Outstanding)",
                                        f"{dio:.0f} days",
                                        help="How long inventory sits")

                            with col3:
                                dpo = cash_cycle.get('dpo', 0)
                                st.metric("DPO (Days Payables Outstanding)",
                                        f"{dpo:.0f} days",
                                        help="How long to pay suppliers")

                            with col4:
                                trend = cash_cycle.get('trend', 'stable')
                                yoy_change = cash_cycle.get('yoy_change', 0)
                                if trend == 'improving':
                                    st.metric("YoY Trend", " Improving", delta=f"{yoy_change:.0f} days")
                                elif trend == 'deteriorating':
                                    st.metric("YoY Trend", "📉 Worsening", delta=f"{yoy_change:+.0f} days")
                                else:
                                    st.metric("YoY Trend", "→ Stable", delta=f"{yoy_change:+.0f} days")

                            st.caption(" Lower CCC = Better working capital efficiency. Negative CCC means suppliers finance operations.")

                        # 8. Operating Leverage (FASE 1)
                        operating_lev = intrinsic.get('operating_leverage', {})
                        if operating_lev:
                            st.markdown("---")
                            st.markdown("###  Operating Leverage (Cost Structure)")

                            ol_val = operating_lev.get('operating_leverage', 0)
                            risk_level = operating_lev.get('risk_level', 'Unknown')
                            assessment = operating_lev.get('assessment', '')

                            # Color-code by risk
                            if risk_level == 'Low':
                                st.success(f"**Operating Leverage: {ol_val:.2f}x** - {risk_level} Risk")
                            elif risk_level == 'Moderate':
                                st.info(f"**Operating Leverage: {ol_val:.2f}x** - {risk_level} Risk")
                            elif risk_level in ['Moderate-High', 'High', 'Very High']:
                                st.warning(f"**Operating Leverage: {ol_val:.2f}x** - {risk_level} Risk")
                            else:
                                st.info(f"**Operating Leverage: {ol_val:.2f}x** - {risk_level} Risk")

                            st.caption(assessment)

                            col1, col2, col3 = st.columns(3)

                            with col1:
                                rev_change = operating_lev.get('revenue_change_%', 0)
                                st.metric("Revenue Change (YoY)", f"{rev_change:+.1f}%")

                            with col2:
                                ebit_change = operating_lev.get('ebit_change_%', 0)
                                st.metric("EBIT Change (YoY)", f"{ebit_change:+.1f}%")

                            with col3:
                                ol_avg = operating_lev.get('ol_avg_2y', 0)
                                st.metric("2Y Avg OL", f"{ol_avg:.2f}x")

                            st.caption(" High OL = High fixed costs. Profits amplify with revenue growth but also with declines.")

                        # 9. Reinvestment Quality (FASE 1)
                        reinvestment = intrinsic.get('reinvestment_quality', {})
                        if reinvestment:
                            st.markdown("---")
                            st.markdown("###  Reinvestment Quality (Capital Efficiency of Growth)")

                            quality = reinvestment.get('quality', 'Unknown')
                            assessment = reinvestment.get('assessment', '')

                            # Color-code by quality
                            if quality == 'High Quality':
                                st.success(f"**{quality} Growth**")
                            elif quality == 'Good Quality':
                                st.info(f"**{quality} Growth**")
                            elif quality == 'Moderate Quality':
                                st.warning(f"**{quality} Growth**")
                            else:
                                st.error(f"**{quality} Growth**")

                            st.caption(assessment)

                            col1, col2, col3, col4 = st.columns(4)

                            with col1:
                                reinv_rate = reinvestment.get('reinvestment_rate_%', 0)
                                st.metric("Reinvestment Rate",
                                        f"{reinv_rate:.1f}%",
                                        help="(Net Capex + ΔWC) / NOPAT")

                            with col2:
                                rev_growth = reinvestment.get('revenue_growth_%', 0)
                                st.metric("Revenue Growth",
                                        f"{rev_growth:.1f}%",
                                        help="YoY revenue growth")

                            with col3:
                                growth_roic = reinvestment.get('growth_roic', 0)
                                st.metric("Growth ROIC",
                                        f"{growth_roic:.2f}x",
                                        help="Revenue Growth / Reinvestment Rate")
                                if growth_roic > 2:
                                    st.caption(" Excellent")
                                elif growth_roic > 1:
                                    st.caption(" Good")
                                elif growth_roic > 0.5:
                                    st.caption(" Moderate")
                                else:
                                    st.caption("❌ Poor")

                            with col4:
                                net_capex = reinvestment.get('net_capex', 0)
                                delta_wc = reinvestment.get('delta_wc', 0)
                                st.metric("Net Capex",
                                        f"${net_capex/1e9:.1f}B",
                                        delta=f"ΔWC: ${delta_wc/1e9:.1f}B")

                            st.caption(" Growth ROIC > 1 = Efficient growth. > 2 = Exceptional capital efficiency.")

                        # 10. Economic Profit / EVA (FASE 2)
                        eva = intrinsic.get('economic_profit', {})
                        if eva:
                            st.markdown("---")
                            st.markdown("###  Economic Profit (EVA - Economic Value Added)")

                            grade = eva.get('grade', 'C')
                            assessment = eva.get('assessment', '')

                            # Color-code by grade
                            if grade in ['A', 'B', 'B-']:
                                st.success(f"**Grade: {grade}** - {assessment}")
                            elif grade == 'C':
                                st.warning(f"**Grade: {grade}** - {assessment}")
                            else:
                                st.error(f"**Grade: {grade}** - {assessment}")

                            col1, col2, col3, col4 = st.columns(4)

                            with col1:
                                eva_val = eva.get('eva_formatted', 'N/A')
                                eva_margin = eva.get('eva_margin_%', 0)
                                st.metric("Economic Value Added",
                                        eva_val,
                                        delta=f"{eva_margin:.1f}% margin")

                            with col2:
                                nopat = eva.get('nopat_formatted', 'N/A')
                                st.metric("NOPAT",
                                        nopat,
                                        help="Net Operating Profit After Tax")

                            with col3:
                                ic = eva.get('ic_formatted', 'N/A')
                                wacc = eva.get('wacc', 0)
                                st.metric("Invested Capital",
                                        ic,
                                        delta=f"WACC: {wacc:.1f}%")

                            with col4:
                                trend = eva.get('trend', 'stable')
                                avg_eva = eva.get('avg_eva_formatted', 'N/A')
                                if trend == 'improving':
                                    st.metric("5Y Avg EVA", avg_eva, delta=" Improving")
                                elif trend == 'deteriorating':
                                    st.metric("5Y Avg EVA", avg_eva, delta="📉 Declining")
                                else:
                                    st.metric("5Y Avg EVA", avg_eva, delta="→ Stable")

                            st.caption(" EVA = NOPAT - (WACC × Invested Capital). Positive EVA = Value creation above cost of capital.")

                        # 11. Capital Allocation Score (FASE 2)
                        cap_alloc = intrinsic.get('capital_allocation', {})
                        if cap_alloc:
                            st.markdown("---")
                            st.markdown("###  Capital Allocation Scorecard")

                            score = cap_alloc.get('score', 0)
                            grade = cap_alloc.get('grade', 'C')
                            assessment = cap_alloc.get('assessment', '')

                            # Color-code by grade
                            if grade in ['A', 'B']:
                                st.success(f"**Score: {score}/100 (Grade {grade})** - {assessment}")
                            elif grade == 'C':
                                st.info(f"**Score: {score}/100 (Grade {grade})** - {assessment}")
                            else:
                                st.warning(f"**Score: {score}/100 (Grade {grade})** - {assessment}")

                            # FCF Breakdown
                            st.markdown("**Free Cash Flow Deployment:**")
                            col1, col2, col3, col4 = st.columns(4)

                            with col1:
                                fcf = cap_alloc.get('fcf_formatted', 'N/A')
                                shareholder_ret = cap_alloc.get('shareholder_return_%', 0)
                                st.metric("Free Cash Flow", fcf, delta=f"{shareholder_ret:.1f}% to shareholders")

                            with col2:
                                div_pct = cap_alloc.get('dividend_%_fcf', 0)
                                payout = cap_alloc.get('payout_ratio_%', 0)
                                st.metric("Dividends", f"{div_pct:.1f}% of FCF", delta=f"{payout:.0f}% payout ratio")

                            with col3:
                                buyback_pct = cap_alloc.get('buyback_%_fcf', 0)
                                share_trend = cap_alloc.get('share_count_trend', 'stable')
                                emoji = "↓" if share_trend == 'decreasing' else "↑" if share_trend == 'increasing' else "→"
                                st.metric("Buybacks", f"{buyback_pct:.1f}% of FCF", delta=f"Shares {emoji}")

                            with col4:
                                debt_pct = cap_alloc.get('debt_paydown_%_fcf', 0)
                                retained = cap_alloc.get('retained_%_fcf', 0)
                                st.metric("Debt Paydown", f"{debt_pct:.1f}% of FCF", delta=f"{retained:.1f}% retained")

                            # Key factors
                            factors = cap_alloc.get('factors', [])
                            if factors:
                                st.markdown("**Key Factors:**")
                                for factor in factors[:4]:  # Show top 4
                                    st.caption(f"• {factor}")

                            st.caption(" Best allocators: Return capital when opportunities are scarce, reinvest when ROIC > WACC.")

                        # 12. Interest Rate Sensitivity (FASE 2)
                        rate_sens = intrinsic.get('interest_rate_sensitivity', {})
                        if rate_sens and rate_sens.get('applicable', False):
                            st.markdown("---")
                            st.markdown("###  Interest Rate Sensitivity (Financial Companies)")

                            assessment = rate_sens.get('assessment', '')
                            sensitivity = rate_sens.get('rate_sensitivity', '')

                            st.info(f"**{assessment}**")
                            st.caption(sensitivity)

                            col1, col2, col3, col4 = st.columns(4)

                            with col1:
                                nim = rate_sens.get('nim_%', 0)
                                avg_nim = rate_sens.get('nim_5y_avg', 0)
                                st.metric("Net Interest Margin",
                                        f"{nim:.2f}%",
                                        delta=f"5Y Avg: {avg_nim:.2f}%")

                            with col2:
                                trend = rate_sens.get('nim_trend', 'stable')
                                yoy = rate_sens.get('nim_yoy_change', 0)
                                if trend == 'expanding':
                                    st.metric("NIM Trend", " Expanding", delta=f"+{yoy:.2f}% YoY")
                                elif trend == 'compressing':
                                    st.metric("NIM Trend", "📉 Compressing", delta=f"{yoy:.2f}% YoY")
                                else:
                                    st.metric("NIM Trend", "→ Stable", delta=f"{yoy:+.2f}% YoY")

                            with col3:
                                nii = rate_sens.get('nii_formatted', 'N/A')
                                st.metric("Net Interest Income", nii)

                            with col4:
                                ltd = rate_sens.get('loan_to_deposit_%')
                                if ltd:
                                    st.metric("Loan/Deposit Ratio", f"{ltd:.1f}%")

                            # NIM history
                            nim_hist = rate_sens.get('nim_history', [])
                            if nim_hist:
                                st.caption(f"**NIM History (last {len(nim_hist)} years):** " +
                                         ", ".join([f"{h:.2f}%" for h in nim_hist]))

                            st.caption(" Higher NIM = More profitable. Expanding NIM = Benefiting from rate increases.")

                        # 13. Insider Trading Analysis (Premium Feature)
                        insider = intrinsic.get('insider_trading', {})
                        if insider and insider.get('available', False):
                            st.markdown("---")
                            st.markdown("###  Insider Trading Activity (Last 12 Months)")

                            signal = insider.get('signal', 'Neutral')
                            score = insider.get('score', 0)
                            assessment = insider.get('assessment', '')

                            # Color-code by signal
                            if signal == 'Strong Buy':
                                st.success(f"**Signal: {signal}** (Score: {score}/100)")
                            elif signal == 'Buy':
                                st.info(f"**Signal: {signal}** (Score: {score}/100)")
                            elif signal == 'Weak Buy':
                                st.info(f"**Signal: {signal}** (Score: {score}/100)")
                            elif signal == 'Neutral':
                                st.warning(f"**Signal: {signal}** (Score: {score}/100)")
                            else:
                                st.error(f"**Signal: {signal}** (Score: {score}/100)")

                            st.caption(assessment)

                            col1, col2, col3, col4 = st.columns(4)

                            with col1:
                                buy_count = insider.get('buy_count_12m', 0)
                                sell_count = insider.get('sell_count_12m', 0)
                                st.metric("Buys vs Sells (12M)", f"{buy_count} / {sell_count}")

                            with col2:
                                recent_buys = insider.get('recent_buys_3m', 0)
                                unique_buyers = insider.get('unique_buyers_3m', 0)
                                st.metric("Recent Activity (3M)", f"{recent_buys} buys", delta=f"{unique_buyers} insiders")

                            with col3:
                                exec_buys = insider.get('executive_buys', 0)
                                st.metric("Executive Buys", f"{exec_buys}", help="CEO/CFO purchases")

                            with col4:
                                net_pos = insider.get('net_position', 'Neutral')
                                buy_val = insider.get('buy_value_formatted', 'N/A')
                                sell_val = insider.get('sell_value_formatted', 'N/A')
                                if net_pos == 'Buying':
                                    st.metric("Net Position", " Buying")
                                else:
                                    st.metric("Net Position", " Selling")
                                st.caption(f"Buy: {buy_val} | Sell: {sell_val}")

                            # Show recent trades
                            recent_trades = insider.get('recent_trades', [])
                            if recent_trades:
                                st.markdown("**Most Recent Buys:**")
                                for trade in recent_trades[:3]:
                                    st.caption(f"• {trade.get('date')}: {trade.get('name')} - ${trade.get('value')/1e3:.0f}K")

                            st.caption(" Multiple insider buys (especially executives) often precede stock price increases.")

                        # 14. Earnings Call Sentiment (Premium Feature)
                        sentiment = intrinsic.get('earnings_sentiment', {})
                        if sentiment and sentiment.get('available', False):
                            st.markdown("---")
                            st.markdown("### 🎤 Earnings Call Sentiment Analysis")

                            tone = sentiment.get('tone', 'Neutral')
                            grade = sentiment.get('grade', 'C')
                            assessment = sentiment.get('assessment', '')

                            # Color-code by grade
                            if grade == 'A':
                                st.success(f"**Tone: {tone}** (Grade: {grade})")
                            elif grade == 'B':
                                st.info(f"**Tone: {tone}** (Grade: {grade})")
                            elif grade == 'C':
                                st.warning(f"**Tone: {tone}** (Grade: {grade})")
                            else:
                                st.error(f"**Tone: {tone}** (Grade: {grade})")

                            st.caption(assessment)

                            col1, col2, col3, col4 = st.columns(4)

                            with col1:
                                net_sent = sentiment.get('net_sentiment', 0)
                                if net_sent > 0:
                                    st.metric("Net Sentiment", f"+{net_sent:.1f}", delta="Positive")
                                else:
                                    st.metric("Net Sentiment", f"{net_sent:.1f}", delta="Negative")

                            with col2:
                                confidence = sentiment.get('confidence_%', 0)
                                st.metric("Confidence", f"{confidence}%", help="Analysis reliability")

                            with col3:
                                pos_pct = sentiment.get('positive_%', 0)
                                neg_pct = sentiment.get('negative_%', 0)
                                st.metric("Positive Keywords", f"{pos_pct:.1f}%")
                                st.caption(f"Negative: {neg_pct:.1f}%")

                            with col4:
                                quarter = sentiment.get('quarter', 'N/A')
                                has_guidance = sentiment.get('has_guidance', False)
                                st.metric("Quarter", quarter)
                                if has_guidance:
                                    st.caption(" Guidance provided")
                                else:
                                    st.caption(" No guidance")

                            # Keyword breakdown
                            st.markdown("**Keyword Mentions:**")
                            pos_count = sentiment.get('positive_mentions', 0)
                            neg_count = sentiment.get('negative_mentions', 0)
                            cau_count = sentiment.get('caution_mentions', 0)
                            st.caption(f"Growth/Positive: {pos_count} | Challenges/Negative: {neg_count} | Caution: {cau_count}")

                            st.caption(" Positive sentiment from management often signals confidence in future performance.")

                        # 15. Red Flags
                        red_flags = intrinsic.get('red_flags', [])
                        if red_flags:
                            st.markdown("### 🚩 Red Flags Detected")
                            for flag in red_flags:
                                st.error(flag)
                        else:
                            # Only show "no red flags" if we actually ran the analysis
                            if 'red_flags' in intrinsic:
                                st.markdown("###  No Red Flags Detected")
                                st.success("All financial health checks passed")

                        # 5. Reverse DCF (What the market is pricing in)
                        reverse_dcf = intrinsic.get('reverse_dcf', {})
                        if reverse_dcf:
                            st.markdown("###  Reverse DCF: What Does the Price Imply?")

                            col1, col2, col3 = st.columns(3)

                            with col1:
                                implied_growth = reverse_dcf.get('implied_growth_rate', 0)
                                st.metric("Implied Growth Rate", f"{implied_growth:.1f}%")
                                st.caption("What growth the current price implies")

                            with col2:
                                current_growth = reverse_dcf.get('current_growth_rate', 0)
                                st.metric("Current Growth Rate", f"{current_growth:.1f}%")
                                st.caption("Actual revenue growth")

                            with col3:
                                implied_multiple = reverse_dcf.get('implied_ev_ebit')
                                if implied_multiple:
                                    st.metric("Implied EV/EBIT", f"{implied_multiple:.1f}x")

                            interpretation = reverse_dcf.get('interpretation', '')
                            if "acceleration" in interpretation.lower():
                                st.info(f"💭 {interpretation}")
                            elif "above" in interpretation.lower():
                                st.warning(f" {interpretation}")
                            elif "continuation" in interpretation.lower():
                                st.success(f" {interpretation}")
                            else:
                                st.error(f"📉 {interpretation}")

                        # 6. DCF Sensitivity Analysis
                        dcf_sensitivity = intrinsic.get('dcf_sensitivity', {})
                        if dcf_sensitivity:
                            st.markdown("### 📐 DCF Sensitivity Analysis")

                            # Base assumptions
                            base_assumptions = dcf_sensitivity.get('base_assumptions', {})
                            st.caption(f"**Base Assumptions:** WACC={base_assumptions.get('wacc', 0):.1f}%, Terminal Growth={base_assumptions.get('terminal_growth', 0):.1f}%")

                            col1, col2 = st.columns(2)

                            with col1:
                                st.markdown("**WACC Sensitivity**")
                                wacc_sens = dcf_sensitivity.get('wacc_sensitivity', {})
                                if wacc_sens:
                                    for scenario, data in wacc_sens.items():
                                        wacc_val = data.get('wacc', 0)
                                        dcf_val = data.get('dcf_value', 0)
                                        st.write(f"• **{scenario.title()}** ({wacc_val:.1f}%): ${dcf_val:.2f}")

                            with col2:
                                st.markdown("**Terminal Growth Sensitivity**")
                                tg_sens = dcf_sensitivity.get('terminal_growth_sensitivity', {})
                                if tg_sens:
                                    for label, data in tg_sens.items():
                                        tg_val = data.get('terminal_growth', 0)
                                        dcf_val = data.get('dcf_value', 0)
                                        st.write(f"• **{label}** Terminal Growth: ${dcf_val:.2f}")

                            # Valuation range
                            val_range = dcf_sensitivity.get('valuation_range', {})
                            if val_range:
                                min_val = val_range.get('min', 0)
                                max_val = val_range.get('max', 0)
                                spread = val_range.get('spread', 0)

                                st.info(f" **Valuation Range:** ${min_val:.2f} - ${max_val:.2f} (spread: ${spread:.2f})")
                                st.caption("This range shows how sensitive the DCF value is to different assumptions")

                    else:
                        st.info("Valuation analysis not available. Run the analysis to see intrinsic value estimates.")
                        # Show debug notes if available
                        if intrinsic.get('notes'):
                            with st.expander(" Debug Information"):
                                for note in intrinsic.get('notes', []):
                                    st.caption(f"• {note}")

                    st.markdown("---")

                    # Fundamental Metrics Deep Dive
                    st.subheader("Fundamental Metrics")

                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.write("**Valuation**")
                        if not stock_data.get('is_financial', False):
                            st.metric("EV/EBIT", f"{stock_data.get('ev_ebit_ttm', 0):.2f}")
                            st.metric("P/E", f"{stock_data.get('pe_ttm', 0):.2f}")
                            st.metric("P/B", f"{stock_data.get('pb_ttm', 0):.2f}")
                        else:
                            st.metric("P/E", f"{stock_data.get('pe_ttm', 0):.2f}")
                            st.metric("P/B", f"{stock_data.get('pb_ttm', 0):.2f}")

                    with col2:
                        st.write("**Quality**")
                        if not stock_data.get('is_financial', False):
                            st.metric("ROIC", f"{stock_data.get('roic_%', 0):.1f}%")
                            st.metric("FCF Margin", f"{stock_data.get('fcf_margin_%', 0):.1f}%")
                            st.metric("Gross Profits/Assets", f"{stock_data.get('grossProfits_to_assets', 0):.2f}")
                        else:
                            st.metric("ROE", f"{stock_data.get('roe_%', 0):.1f}%")
                            st.metric("ROA", f"{stock_data.get('roa_%', 0):.1f}%")

                    with col3:
                        st.write("**Guardrails**")
                        # Override status to VERDE if PEG Hammer triggered
                        if 'growth_override_applied' in locals() and growth_override_applied:
                            st.metric("Status", "VERDE")
                        else:
                            st.metric("Status", stock_data.get('guardrail_status', 'N/A'))
                        if 'altman_z' in stock_data:
                            st.metric("Altman Z-Score", f"{stock_data.get('altman_z', 0):.2f}")
                        if 'beneish_m' in stock_data:
                            st.metric("Beneish M-Score", f"{stock_data.get('beneish_m', 0):.2f}")

                    # ======================
                    #  DEBUG: PREMIUM FEATURES
                    # ======================
                    st.markdown("---")
                    with st.expander(" DEBUG: Premium Features Status", expanded=False):
                        st.markdown("### Premium Features Configuration & Output")

                        # Show config being used
                        st.markdown("#### 1️⃣ Configuration Loaded")
                        st.code(f"Config file: {config_file if 'config_file' in locals() else 'settings.yaml'}")

                        # Show premium config
                        import os as os_module
                        try:
                            config_to_check = 'settings_premium.yaml' if os_module.path.exists('settings_premium.yaml') else 'settings.yaml'
                            with open(config_to_check, 'r') as f:
                                config = yaml.safe_load(f)
                            premium_config = config.get('premium', {})

                            st.markdown("**Premium Config:**")
                            col1, col2 = st.columns(2)
                            with col1:
                                insider_enabled = premium_config.get('enable_insider_trading', False)
                                if insider_enabled:
                                    st.success(f" Insider Trading: **ENABLED**")
                                else:
                                    st.error(f"❌ Insider Trading: **DISABLED**")

                            with col2:
                                transcripts_enabled = premium_config.get('enable_earnings_transcripts', False)
                                if transcripts_enabled:
                                    st.success(f" Earnings Transcripts: **ENABLED**")
                                else:
                                    st.error(f"❌ Earnings Transcripts: **DISABLED**")
                        except Exception as e:
                            st.error(f"Could not load config: {e}")

                        # Check where features are in the analysis result
                        st.markdown("#### 2️⃣ Features in Analysis Result")

                        # Check root level (WRONG location)
                        has_insider_root = 'insider_trading' in analysis
                        has_sentiment_root = 'earnings_sentiment' in analysis

                        st.markdown("**Root Level (DEPRECATED):**")
                        col1, col2 = st.columns(2)
                        with col1:
                            if has_insider_root:
                                st.warning(" insider_trading found at ROOT (deprecated)")
                            else:
                                st.info("❌ insider_trading NOT at root")
                        with col2:
                            if has_sentiment_root:
                                st.warning(" earnings_sentiment found at ROOT")
                            else:
                                st.info("❌ earnings_sentiment NOT at root")

                        # Check intrinsic_value level (CORRECT location)
                        intrinsic = analysis.get('intrinsic_value', {})
                        has_insider_iv = 'insider_trading' in intrinsic
                        has_sentiment_iv = 'earnings_sentiment' in intrinsic

                        st.markdown("**Inside intrinsic_value Dict ( CORRECT):**")
                        col1, col2 = st.columns(2)
                        with col1:
                            if has_insider_iv:
                                st.success(" insider_trading FOUND in intrinsic_value!")
                            else:
                                st.error("❌ insider_trading NOT in intrinsic_value")
                        with col2:
                            if has_sentiment_iv:
                                st.success(" earnings_sentiment FOUND in intrinsic_value!")
                            else:
                                st.error("❌ earnings_sentiment NOT in intrinsic_value")

                        # Show actual data if present
                        st.markdown("#### 3️⃣ Actual Premium Features Data")

                        if has_insider_iv:
                            st.markdown("** Insider Trading Data:**")
                            insider_data = intrinsic['insider_trading']
                            st.json(insider_data)
                        else:
                            st.warning("No insider trading data in intrinsic_value")

                        if has_sentiment_iv:
                            st.markdown("** Earnings Sentiment Data:**")
                            sentiment_data = intrinsic['earnings_sentiment']
                            st.json(sentiment_data)
                        else:
                            st.warning("No earnings sentiment data in intrinsic_value")

                        # Show what keys ARE in intrinsic_value
                        st.markdown("#### 4️⃣ All Keys in intrinsic_value Dict")
                        st.code(f"Keys: {list(intrinsic.keys())}")

                        st.markdown("""
                        ---
                        ** How to Access Premium Features:**
                        ```python
                        #  CORRECT
                        analysis['intrinsic_value']['insider_trading']
                        analysis['intrinsic_value']['earnings_sentiment']

                        # ❌ WRONG
                        analysis['insider_trading']  # Not here!
                        analysis['earnings_sentiment']  # Not here!
                        ```
                        """)

                    # Export to Excel button
                    st.markdown("---")
                    st.markdown("### 📥 Export Analysis")

                    try:
                        excel_data = create_qualitative_excel(analysis, selected_ticker, datetime.now())
                        st.download_button(
                            label=" Download Full Analysis (Excel)",
                            data=excel_data,
                            file_name=f"{selected_ticker}_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                            help="Download comprehensive analysis with all metrics in multiple Excel sheets"
                        )
                        st.caption(" Includes: Overview, Capital Efficiency, Earnings Quality, Margins, Red Flags, Reverse DCF, Price Projections, and DCF Sensitivity")
                    except Exception as e:
                        st.error(f"Excel export failed: {e}")
                        st.caption("Please report this issue if it persists")

                else:
                    st.info(f"👆 Click the button above to run qualitative analysis for {selected_ticker}")

        else:
            st.info("👈 Run the screener first to access qualitative analysis")

with tab6:
    st.markdown("""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 2rem; border-radius: 12px; color: white; margin-bottom: 2rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
        <h2 style='margin: 0; color: white; font-weight: 700;'>Complete Analysis</h2>
        <p style='margin: 0.5rem 0 0 0; opacity: 0.95;'>
            Standalone qualitative + technical analysis - No screener required
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    **Análisis integral standalone** - No requiere correr el screener

    ###  Este análisis incluye TODO:

    ** Qualitative Analysis:**
    - Intrinsic Value (DCF, Forward Multiple, Weighted Fair Value)
    - Capital Efficiency (ROIC vs WACC, ROE trends)
    - Earnings Quality (Accruals, Beneish M-Score)
    - Profitability Margins (Gross, Operating, Net, FCF)
    - Red Flags (Altman Z-Score, Debt, Liquidity)
    - Competitive Moats (Pricing Power, Network Effects, Switching Costs)
    - Management Quality (Insider Trading, Institutional Ownership)
    - Growth Analysis (Revenue, Earnings, Historical trends)

    ** Technical Analysis:**
    - Multi-timeframe Momentum (12M, 6M, 3M, 1M)
    - Risk-Adjusted Returns (Sharpe Ratio 12M)
    - Relative Strength (vs Sector, vs Market)
    - Market Regime Detection (Bull/Bear/Sideways)
    - SmartDynamicStopLoss with State Machine (7 states)
    - Volume Profile & Confirmation

    ** Risk Management & Trading:**
    - Position Sizing (con veto awareness)
    - Entry Strategy (FULL ENTRY / SCALE-IN / NO ENTRY)
    - Stop Loss Recommendations (context-aware)
    - Profit Taking Targets (Conservative/Moderate/Aggressive)
    - Options Strategies (7 evidence-based strategies)

    ** Ventajas:**
    - Análisis de **cualquier ticker** de 21+ mercados globales
    - Sin necesidad de correr screener completo
    - Veto system integrado (PARABOLIC_CLIMAX, DOWNTREND)
    - Basado en investigación académica (2020-2024)
    """)

    st.info("""
     **Multi-Market Support:** This tool works with stocks from all major global markets!

    **Note:** Some data (insider trading, press releases, transcripts) may have limited availability outside USA markets.
    The analysis will show "N/A" for unavailable data and focus on available metrics.
    """)

    # Ticker input
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        custom_ticker = st.text_input(
            "Enter Ticker Symbol",
            placeholder="e.g., MSFT, CSU (no need for .TO), ASML",
            help="Enter ticker without market suffix - we'll add it automatically based on your market selection"
        ).upper().strip()

    with col2:
        # Market selector (same as Quick Technical)
        custom_market_options = {
            "USA": "US",
            "Canada": "CA",
            "Mexico": "MX",
            "Brazil": "BR",
            "UK": "UK",
            "Germany": "DE",
            "France": "FR",
            "Spain": "ES",
            "China": "CN",
            "Japan": "JP",
            "India": "IN",
            "Indonesia": "ID",
            "Hong Kong": "HK",
            "South Korea": "KR",
            "Singapore": "SG",
            "Australia": "AU",
            "Switzerland": "CH",
            "Netherlands": "NL",
            "🇸🇪 Sweden": "SE",
            "Norway": "NO",
            "Denmark": "DK"
        }

        custom_market = st.selectbox(
            "Market",
            options=list(custom_market_options.keys()),
            index=0,
            key="custom_market_select",
            help="Select the stock's primary market/exchange"
        )
        custom_country_code = custom_market_options.get(custom_market, "US")

    # Helper function to add market suffix to ticker if needed
    def format_ticker_for_market_custom(ticker: str, country_code: str) -> str:
        """Add market suffix to ticker based on country code."""
        if not ticker:
            return ticker

        # Market suffix mapping
        suffix_map = {
            "CA": ".TO",      # Canada - Toronto Stock Exchange
            "UK": ".L",       # UK - London Stock Exchange
            "DE": ".DE",      # Germany - Frankfurt
            "FR": ".PA",      # France - Paris
            "ES": ".MC",      # Spain - Madrid
            "MX": ".MX",      # Mexico - BMV
            "BR": ".SA",      # Brazil - Sao Paulo
            "AU": ".AX",      # Australia - ASX
            "JP": ".T",       # Japan - Tokyo
            "IN": ".NS",      # India - NSE (or .BO for BSE)
            "HK": ".HK",      # Hong Kong
            "CN": ".SS",      # China - Shanghai (or .SZ for Shenzhen)
            "KR": ".KS",      # South Korea - KOSPI
            "SG": ".SI",      # Singapore
            "CH": ".SW",      # Switzerland - SIX
            "NL": ".AS",      # Netherlands - Amsterdam
            "SE": ".ST",      # Sweden - Stockholm
            "NO": ".OL",      # Norway - Oslo
            "DK": ".CO",      # Denmark - Copenhagen
        }

        suffix = suffix_map.get(country_code)

        # If no suffix needed (US) or already has a suffix, return as-is
        if not suffix or "." in ticker:
            return ticker

        return f"{ticker}{suffix}"

    with col3:
        st.markdown("")  # Spacing
        st.markdown("")  # Spacing
        analyze_button = st.button(
            f" Analyze {custom_ticker if custom_ticker else 'Company'}",
            disabled=not custom_ticker,
            use_container_width=True,
            type="primary"
        )

    # Format ticker with market suffix (needed for both analysis and display)
    formatted_custom_ticker = format_ticker_for_market_custom(custom_ticker, custom_country_code) if custom_ticker else ""

    if analyze_button and custom_ticker:

        with st.spinner(f" Analyzing {formatted_custom_ticker}... This may take 30-60 seconds"):
            try:
                # Show formatted ticker if different from input
                if formatted_custom_ticker != custom_ticker:
                    st.info(f" Using ticker: **{formatted_custom_ticker}** (added {custom_market} market suffix)")

                # Import dependencies
                from screener.orchestrator import ScreenerPipeline
                from screener.qualitative import QualitativeAnalyzer
                from screener.technical.analyzer import EnhancedTechnicalAnalyzer

                # Initialize pipeline (this loads settings.yaml and sets up FMP client)
                pipeline = ScreenerPipeline('settings.yaml')

                # Initialize analyzers
                qual_analyzer = QualitativeAnalyzer(pipeline.fmp, pipeline.config)
                tech_analyzer = EnhancedTechnicalAnalyzer(pipeline.fmp)

                # Get company info first for sector
                profile = pipeline.fmp.get_quote(formatted_custom_ticker)
                sector = profile[0].get('sector', 'Unknown') if profile and len(profile) > 0 else 'Unknown'

                # Run QUALITATIVE analysis
                qual_analysis = qual_analyzer.analyze_symbol(
                    formatted_custom_ticker,
                    company_type='unknown',  # Auto-detect
                    peers_df=None  # No peer comparison in custom analysis
                )

                # Extract fundamental data for position sizing
                fundamental_score = None
                guardrails_status = None
                fundamental_decision = None
                if qual_analysis and 'error' not in qual_analysis:
                    fundamental_score = qual_analysis.get('composite_score', None)
                    guardrails_status = qual_analysis.get('guardrails_summary', {}).get('overall_status', None)
                    fundamental_decision = qual_analysis.get('decision', None)

                # Run TECHNICAL analysis with fundamental data for position sizing
                tech_analysis = tech_analyzer.analyze(
                    formatted_custom_ticker,
                    sector=sector,
                    country=custom_country_code,
                    fundamental_score=fundamental_score,
                    guardrails_status=guardrails_status,
                    fundamental_decision=fundamental_decision
                )

                if qual_analysis and 'error' not in qual_analysis:
                    st.session_state[f'custom_{formatted_custom_ticker}'] = qual_analysis
                    st.session_state[f'custom_{formatted_custom_ticker}_tech'] = tech_analysis
                    st.session_state[f'custom_{formatted_custom_ticker}_market'] = custom_country_code
                    st.session_state[f'custom_{formatted_custom_ticker}_sector'] = sector
                    st.success(f" Qualitative + Technical analysis for {formatted_custom_ticker} complete! (Market: {custom_market})")

                    # Show market-specific data availability note
                    if custom_country_code != "US":
                        st.warning("""
                         **Non-US Market Detected**: Some sections may show limited data:
                        - Insider Trading (USA-focused)
                        - Press Releases (limited international coverage)
                        - Earnings Transcripts (availability varies)

                        Core financial metrics (valuation, profitability, balance sheet) should be fully available.
                        """)

                    st.rerun()
                else:
                    error_msg = qual_analysis.get('error', 'Unknown error') if qual_analysis else 'Failed to retrieve data'
                    st.error(f"❌ Analysis failed: {error_msg}")
                    st.info(f" Troubleshooting tips:\n- Ticker: {formatted_custom_ticker}\n- Market suffix has been added automatically\n- Some tickers may have limited data availability\n- Try selecting a different market if the ticker is listed on multiple exchanges")

            except Exception as e:
                st.error(f"❌ Analysis failed: {str(e)}")
                st.info(f" Please check:\n- Ticker symbol is correct for {custom_market}\n- Stock is publicly traded and has financial data\n- API connection is working properly")

    # Display cached analysis if available
    if formatted_custom_ticker and f'custom_{formatted_custom_ticker}' in st.session_state:
        analysis = st.session_state[f'custom_{formatted_custom_ticker}']

        st.markdown("---")

        # Company Info
        st.subheader(f"{formatted_custom_ticker} - Company Overview")

        # Business Summary
        with st.expander(" Business Summary", expanded=False):
            st.write(analysis.get('business_summary', 'Not available'))

        st.markdown("---")

        # === INTRINSIC VALUE SECTION (Same as Qualitative tab) ===
        st.subheader("Intrinsic Value Estimation")
        intrinsic = analysis.get('intrinsic_value', {})

        if intrinsic and 'current_price' in intrinsic:
            col1, col2, col3, col4 = st.columns(4)

            current_price = intrinsic.get('current_price', 0)

            with col1:
                if current_price and current_price > 0:
                    st.metric("Current Price", f"${current_price:.2f}")
                else:
                    st.metric("Current Price", "N/A")

            with col2:
                dcf_val = intrinsic.get('dcf_value')
                if dcf_val and dcf_val > 0:
                    st.metric("DCF Value", f"${dcf_val:.2f}")
                else:
                    st.metric("DCF Value", "N/A")

            with col3:
                fwd_val = intrinsic.get('forward_multiple_value')
                if fwd_val and fwd_val > 0:
                    st.metric("Forward Multiple", f"${fwd_val:.2f}")
                else:
                    st.metric("Forward Multiple", "N/A")

            with col4:
                fair_val = intrinsic.get('weighted_value')
                if fair_val and fair_val > 0:
                    st.metric("Fair Value", f"${fair_val:.2f}")
                else:
                    st.metric("Fair Value", "N/A")

            # Upside/Downside
            if intrinsic.get('upside_downside_%') is not None:
                upside = intrinsic.get('upside_downside_%', 0)
                assessment = intrinsic.get('valuation_assessment', 'Unknown')
                confidence = intrinsic.get('confidence', 'Low')

                if assessment == 'Undervalued':
                    color = 'green'
                    emoji = ''
                elif assessment == 'Overvalued':
                    color = 'red'
                    emoji = ''
                else:
                    color = 'orange'
                    emoji = ''

                st.markdown(f"### {emoji} {assessment}: {upside:+.1f}% {'upside' if upside > 0 else 'downside'}")
                st.caption(f"**Confidence:** {confidence}")
            # Second row: PEG Ratio + Intrinsic Value PEG-Forward
            st.markdown("")  # Spacing

            # Get PEG and related data from correct location
            peg_ratio = None
            pe_ratio = None
            eps_growth = None
            if 'valuation_multiples' in intrinsic:
                company_vals = intrinsic['valuation_multiples'].get('company', {})
                peg_ratio = company_vals.get('peg', None)
                pe_ratio = company_vals.get('pe', None)
                eps_growth = company_vals.get('eps_growth_%', None)

            if peg_ratio and peg_ratio > 0:
                # Calculate PEG-based Intrinsic Value
                # Formula: Fair Value = Current Price × (Fair PEG / Current PEG)
                # Fair PEG = 1.0 (conservative) or 1.5 (growth premium)
                fair_peg_conservative = 1.0
                fair_peg_growth = 1.5

                peg_intrinsic_conservative = current_price * (fair_peg_conservative / peg_ratio) if current_price > 0 else None
                peg_intrinsic_growth = current_price * (fair_peg_growth / peg_ratio) if current_price > 0 else None

                # Color-coded PEG display
                if peg_ratio < 1.0:
                    peg_color = ""
                    peg_label = "Excelente"
                elif peg_ratio < 1.5:
                    peg_color = ""
                    peg_label = "Bueno (GARP)"
                elif peg_ratio < 2.0:
                    peg_color = ""
                    peg_label = "Aceptable"
                else:
                    peg_color = ""
                    peg_label = "Caro para Growth"

                col_peg1, col_peg2, col_peg3 = st.columns([1, 2, 2])
                with col_peg1:
                    # Show Intrinsic Value as main metric, PEG in caption
                    if peg_intrinsic_conservative:
                        upside_conservative = ((peg_intrinsic_conservative - current_price) / current_price) * 100
                        st.metric("Valor PEG", f"${peg_intrinsic_conservative:.2f}", delta=f"{upside_conservative:+.1f}%")
                        st.caption(f"PEG: {peg_ratio:.2f} | EPS Growth: {eps_growth:.1f}%" if eps_growth else f"PEG: {peg_ratio:.2f}")
                with col_peg2:
                    st.markdown(f"### {peg_color} **{peg_label}**")
                    st.caption(f"*Fair PEG = 1.0 (conservador)*")
                with col_peg3:
                    if peg_intrinsic_growth:
                        upside_growth = ((peg_intrinsic_growth - current_price) / current_price) * 100
                        st.caption(f"**Growth PEG 1.5:** ${peg_intrinsic_growth:.2f} ({upside_growth:+.1f}%)")
                    st.caption("*Premium para empresas de alto crecimiento*")
            else:
                st.info(" **PEG Ratio:** N/A (Data not available)")

            # === Valuation Method Recommendation ===
            # Determine which valuation method is most appropriate
            peg_ratio = None
            if 'valuation_multiples' in intrinsic:
                company_vals = intrinsic['valuation_multiples'].get('company', {})
                peg_ratio = company_vals.get('peg', None)

            revenue_growth = None
            if 'growth_consistency' in intrinsic:
                revenue_growth = intrinsic['growth_consistency'].get('revenue_growth_5y_cagr', None)

            # Fallback: Infer growth from PEG if available
            if not revenue_growth and peg_ratio:
                company_vals = intrinsic.get('valuation_multiples', {}).get('company', {})
                eps_growth = company_vals.get('eps_growth_%', None)
                if eps_growth:
                    revenue_growth = eps_growth  # Use EPS growth as proxy

            # Determine predominant method
            # Priority 1: If PEG < 1.5, it's a growth company (even without explicit revenue growth data)
            if peg_ratio and peg_ratio < 1.5:
                # Growth company - PEG is king
                method_icon = ""
                method_name = "PEG Ratio (Growth Valuation)"
                growth_text = f"{revenue_growth:.1f}%" if revenue_growth else "Datos limitados (inferido de PEG < 1.5)"
                method_reason = f"""
**Por qué PEG es mejor para esta empresa:**
- PEG Ratio: {peg_ratio:.2f} (< 1.5 = Growth at reasonable price)
- Growth: {growth_text}
- DCF subestima empresas de crecimiento porque:
  - No captura AI/platform optionality
  - Assumptions conservadoras (3% terminal growth típico)
  - No valora network effects ni moats digitales
- **PEG captura el valor del crecimiento futuro** (P/E ajustado por growth)
- Empresas similares: Amazon, Google, Meta en fase de crecimiento alto
"""
            elif peg_ratio and peg_ratio > 2.5 and revenue_growth and revenue_growth < 5:
                # Mature company - DCF is king
                method_icon = "<i class='bi bi-building-fill'></i>"
                method_name = "DCF (Mature Company Valuation)"
                method_reason = f"""
**Por qué DCF es mejor para esta empresa:**
- PEG Ratio: {peg_ratio:.2f} (> 2.5 = Expensive for growth)
- Revenue Growth: {revenue_growth:.1f}% (Mature/stable)
- DCF es ideal para empresas maduras porque:
  - Cash flows predecibles y estables
  - Growth limitado → PEG pierde relevancia
  - Mejor para dividendos y buybacks
- **DCF captura el valor intrínseco de FCF estable**
- Empresas similares: Johnson & Johnson, Procter & Gamble, Coca-Cola
"""
            elif peg_ratio and revenue_growth and 1.5 <= peg_ratio <= 2.5 and 5 <= revenue_growth <= 10:
                # Balanced - use both methods
                method_icon = "<i class='bi bi-diagram-3-fill'></i>"
                method_name = "Hybrid (DCF + PEG)"
                method_reason = f"""
**Por qué usar ambos métodos:**
- PEG Ratio: {peg_ratio:.2f} (1.5-2.5 = GARP territory)
- Revenue Growth: {revenue_growth:.1f}% (Moderate growth)
- Empresa en transición: ni puro growth ni pura mature
- **DCF valora cash flows actuales** | **PEG valora potencial de crecimiento**
- Fair Value (weighted average) combina ambas perspectivas
- Empresas similares: Microsoft, Apple (madurez con crecimiento sostenible)
"""
            else:
                # Insufficient data or unknown profile
                method_icon = ""
                method_name = "Multiple Methods (Insuficiente data)"
                method_reason = f"""
**Recomendación:**
- Se usan múltiples métodos (DCF, Forward Multiple, Fair Value)
- PEG: {f'{peg_ratio:.2f}' if peg_ratio else 'N/A'}
- Revenue Growth: {f'{revenue_growth:.1f}%' if revenue_growth else 'N/A'}
- Se recomienda usar Fair Value (weighted average) como estimación conservadora
"""

            st.info(f"{method_icon} **Método de Valoración Predominante:** {method_name}\n\n{method_reason}")

            # Show debug notes if present (for troubleshooting)
            notes = intrinsic.get('notes', [])
            if notes:
                with st.expander(" Calculation Details & Debug Info"):
                    for note in notes:
                        if note.startswith('✓'):
                            st.success(note)
                        elif note.startswith('✗') or 'ERROR' in note or 'failed' in note.lower():
                            st.error(note)
                        elif note.startswith('') or 'WARNING' in note:
                            st.warning(note)
                        else:
                            st.info(note)

            # Upside/Downside
            if intrinsic.get('upside_downside_%') is not None:
                upside = intrinsic.get('upside_downside_%', 0)
                assessment = intrinsic.get('valuation_assessment', 'Unknown')
                confidence = intrinsic.get('confidence', 'Low')

                # === EL MARTILLO DEL PEG: Veto power sobre DCF en Growth Stocks ===
                # Para empresas de crecimiento, PEG > DCF porque captura optionality
                # Si PEG < 1.5 y Growth > 10% → VERDE, sin importar DCF

                growth_override_applied = False
                growth_override_reason = None

                # Get PEG Ratio from CORRECT location (valuation_multiples)
                peg_ratio = None
                if 'valuation_multiples' in intrinsic:
                    company_vals = intrinsic['valuation_multiples'].get('company', {})
                    peg_ratio = company_vals.get('peg', None)

                # Fallback: try stock_data (might be in features)
                if not peg_ratio:
                    peg_ratio = analysis.get('peg_ratio', None)

                # Get revenue growth from intrinsic data or stock_data
                revenue_growth = None
                if 'growth_consistency' in intrinsic:
                    revenue_growth = intrinsic['growth_consistency'].get('revenue_growth_5y_cagr', None)

                # Fallback: try to get from features
                if not revenue_growth:
                    # Check if we have earnings growth used for PEG
                    # If PEG exists and P/E exists, we can infer growth
                    pe_ttm = analysis.get('pe_ttm', None)
                    if peg_ratio and pe_ttm and peg_ratio > 0:
                        # PEG = P/E / Growth → Growth = P/E / PEG
                        revenue_growth = (pe_ttm / peg_ratio) if peg_ratio > 0 else None

                # Determine if it's a growth stock
                is_growth_stock = False
                if revenue_growth and revenue_growth > 10:  # >10% growth
                    is_growth_stock = True
                elif peg_ratio and peg_ratio < 2.0:  # PEG suggests growth
                    is_growth_stock = True

                # Get Reverse DCF signal (optional, not required)
                reverse_dcf_signal = None
                if 'reverse_dcf' in intrinsic:
                    interpretation = intrinsic['reverse_dcf'].get('interpretation', '')
                    if 'UNDERVALUED' in interpretation.upper():
                        reverse_dcf_signal = 'UNDERVALUED'

                # === MARTILLO DEL PEG: Override Logic ===
                #Quality Tier 1: PEG excelente (< 1.2) + Growth Stock → VERDE inmediato
                #Quality Tier 2: PEG bueno (< 1.5) + Reverse DCF UNDERVALUED → VERDE
                #Quality Tier 3: PEG razonable (< 2.0) + High Growth (>15%) → VERDE

                peg_hammer_triggered = False

                if peg_ratio:
                    #Quality Tier 1: PEG excelente (< 1.2) en growth stock
                    if peg_ratio < 1.2 and is_growth_stock:
                        peg_hammer_triggered = True
                        growth_override_reason = f"""
                        **🔨 EL MARTILLO DEL PEG -Quality Tier 1: Ganga Absoluta**
                        - PEG Ratio: {peg_ratio:.2f} (< 1.2 = Excelente)
                        - Growth Stock: Sí (crecimiento sostenible)
                        - DCF Fair Value: ${intrinsic.get('weighted_value', 0):.0f} vs Price: ${intrinsic.get('current_price', 0):.0f}

                        **Veredicto: COMPRA CLARA (PEG tiene veto sobre DCF)**

                        DCF undervalues growth porque:
                        • No captura AI/platform optionality
                        • Assumptions conservadoras (3% terminal growth)
                        • PEG < 1.2 = "Pagando menos de lo que el crecimiento vale"

                        **Empresas similares con PEG < 1.2:** Amazon 2015 (PEG 0.8), Google 2018 (PEG 1.0), Meta 2023 (PEG 0.9)
                        """

                    #Quality Tier 2: PEG bueno (< 1.5) + Reverse DCF confirma
                    elif peg_ratio < 1.5 and reverse_dcf_signal == 'UNDERVALUED':
                        peg_hammer_triggered = True
                        growth_override_reason = f"""
                        **🔨 EL MARTILLO DEL PEG -Quality Tier 2: Growth at Reasonable Price**
                        - PEG Ratio: {peg_ratio:.2f} (< 1.5 = GARP territory)
                        - Reverse DCF: UNDERVALUED (mercado pesimista sobre futuro)
                        - DCF Fair Value: ${intrinsic.get('weighted_value', 0):.0f} vs Price: ${intrinsic.get('current_price', 0):.0f}

                        **Veredicto: COMPRA (Doble confirmación PEG + Reverse DCF)**

                        2 señales independientes confirman undervaluation:
                        1. PEG < 1.5 → Crecimiento a precio razonable
                        2. Reverse DCF → Mercado espera menos crecimiento del real
                        """

                    #Quality Tier 3: PEG razonable (< 2.0) en high growth (>15%)
                    elif peg_ratio < 2.0 and revenue_growth and revenue_growth > 15:
                        peg_hammer_triggered = True
                        growth_override_reason = f"""
                        **🔨 EL MARTILLO DEL PEG -Quality Tier 3: High Growth Premium**
                        - PEG Ratio: {peg_ratio:.2f} (< 2.0 aceptable para growth >15%)
                        - Revenue Growth: {revenue_growth:.1f}% (High growth justifica premium)
                        - DCF Fair Value: ${intrinsic.get('weighted_value', 0):.0f} vs Price: ${intrinsic.get('current_price', 0):.0f}

                        **Veredicto: COMPRA (High growth justifica valuación)**

                        Para empresas con crecimiento >15%, PEG < 2.0 es razonable.
                        Regla: "Never short a dull market" → Never sell high growth at PEG < 2.0
                        """

                # Apply override if PEG Hammer triggered
                if peg_hammer_triggered and assessment != 'Undervalued':
                    growth_override_applied = True
                    original_assessment = assessment
                    assessment = 'Growth Undervalued'  # Force GREEN

                    # Recalculate upside based on PEG intrinsic value (use Growth PEG 1.5)
                    current_price = intrinsic.get('current_price', 0)
                    if peg_ratio and current_price > 0:
                        fair_peg_growth = 1.5  # Growth premium
                        peg_intrinsic_growth = current_price * (fair_peg_growth / peg_ratio)
                        upside = ((peg_intrinsic_growth - current_price) / current_price) * 100
                        # Store for display
                        growth_override_applied = True

                # Color based on assessment (with PEG hammer override)
                if assessment in ['Undervalued', 'Growth Undervalued']:
                    color = 'green'
                    emoji = ''
                elif assessment == 'Overvalued':
                    color = 'red'
                    emoji = ''
                else:
                    color = 'orange'
                    emoji = ''

                # Display industry profile
                industry_profile = intrinsic.get('industry_profile', 'unknown').replace('_', ' ').title()
                primary_metric = intrinsic.get('primary_metric', 'EV/EBIT')

                # Display main status (with PEG-driven upside if applicable)
                display_assessment = assessment.replace('Growth Undervalued', 'Undervalued (PEG Driver)')


            # Advanced Metrics (same as Qualitative tab)
            st.markdown("---")

            # 1. ROIC vs WACC (or ROE for financials)
            capital_efficiency = intrinsic.get('capital_efficiency', {})
            if capital_efficiency:
                metric_name = capital_efficiency.get('metric_name', 'ROIC')
                st.markdown(f"###  Capital Efficiency ({metric_name} vs WACC)")
                col1, col2, col3 = st.columns(3)

                with col1:
                    current = capital_efficiency.get('current', 0)
                    st.metric(metric_name, f"{current:.1f}%")
                    st.caption(f"3Y Avg: {capital_efficiency.get('avg_3y', 0):.1f}%")

                with col2:
                    wacc = capital_efficiency.get('wacc', 0)
                    st.metric("WACC", f"{wacc:.1f}%")
                    st.caption(f"5Y Avg {metric_name}: {capital_efficiency.get('avg_5y', 0):.1f}%")

                with col3:
                    spread = capital_efficiency.get('spread', 0)
                    trend = capital_efficiency.get('trend', 'stable')
                    st.metric(f"Spread ({metric_name} - WACC)", f"{spread:+.1f}%", delta=trend)

                # Show 5-year history
                history_5y = capital_efficiency.get('history_5y', [])
                if history_5y:
                    st.caption(f"**{metric_name} History (last {len(history_5y)} years):** " +
                             ", ".join([f"{h:.1f}%" for h in history_5y]))

                value_creation = capital_efficiency.get('value_creation', False)
                assessment_text = capital_efficiency.get('assessment', '')

                if value_creation:
                    st.success(f" {assessment_text} - {metric_name} exceeds WACC")
                else:
                    st.error(f" {assessment_text} - {metric_name} below WACC")

            # 2. Quality of Earnings
            earnings_quality = intrinsic.get('earnings_quality', {})
            if earnings_quality:
                st.markdown("###  Quality of Earnings")
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    cf_to_ni = earnings_quality.get('cash_flow_to_net_income', 0)
                    st.metric("OCF / Net Income", f"{cf_to_ni:.2f}")
                    st.caption(">1.0 is excellent")

                with col2:
                    accruals = earnings_quality.get('accruals_ratio', 0)
                    st.metric("Accruals Ratio", f"{accruals:.2f}%")
                    st.caption("<5% is good")

                with col3:
                    wc_trend = earnings_quality.get('working_capital_trend', 'unknown')
                    st.metric("Working Capital", wc_trend.title())

                with col4:
                    grade = earnings_quality.get('grade', 'C')
                    if grade in ['A', 'B']:
                        st.success(f"**Grade: {grade}**")
                    elif grade == 'C':
                        st.warning(f"**Grade: {grade}**")
                    else:
                        st.error(f"**Grade: {grade}**")

            # 3. Profitability Margins
            profitability = intrinsic.get('profitability_analysis', {})
            if profitability:
                st.markdown("###  Profitability Margins & Trends")
                col1, col2, col3 = st.columns(3)

                with col1:
                    gross = profitability.get('gross_margin', {})
                    if gross:
                        st.metric("Gross Margin", f"{gross.get('current', 0):.1f}%",
                                 delta=f"{gross.get('current', 0) - gross.get('avg_3y', 0):.1f}% vs 3Y avg")
                        st.caption(gross.get('trend', '→ stable'))

                with col2:
                    operating = profitability.get('operating_margin', {})
                    if operating:
                        st.metric("Operating Margin", f"{operating.get('current', 0):.1f}%",
                                 delta=f"{operating.get('current', 0) - operating.get('avg_3y', 0):.1f}% vs 3Y avg")
                        st.caption(operating.get('trend', '→ stable'))

                with col3:
                    fcf = profitability.get('fcf_margin', {})
                    if fcf:
                        st.metric("FCF Margin", f"{fcf.get('current', 0):.1f}%",
                                 delta=f"{fcf.get('current', 0) - fcf.get('avg_3y', 0):.1f}% vs 3Y avg")
                        st.caption(fcf.get('trend', '→ stable'))

            # 4. Balance Sheet Strength
            balance_sheet = intrinsic.get('balance_sheet_strength', {})
            if balance_sheet:
                st.markdown("---")
                st.markdown("### 🏦 Balance Sheet Health")

                # Overall assessment banner
                overall = balance_sheet.get('overall_assessment', 'Unknown')
                warnings_list = balance_sheet.get('warnings', [])

                if overall == 'Strong':
                    st.success(f"**Overall: {overall}** - Solid financial position")
                elif overall == 'Concerning':
                    st.error(f"**Overall: {overall}** - {', '.join(warnings_list)}")
                else:
                    st.warning(f"**Overall: {overall}**")

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    de_ratio = balance_sheet.get('debt_to_equity', {})
                    if de_ratio:
                        st.metric("Debt/Equity",
                                f"{de_ratio.get('value', 0):.2f}x",
                                help="Total Debt / Shareholders Equity")
                        st.caption(de_ratio.get('assessment', ''))

                with col2:
                    current_r = balance_sheet.get('current_ratio', {})
                    if current_r:
                        st.metric("Current Ratio",
                                f"{current_r.get('value', 0):.2f}x",
                                help="Current Assets / Current Liabilities")
                        st.caption(current_r.get('assessment', ''))

                with col3:
                    interest_cov = balance_sheet.get('interest_coverage', {})
                    if interest_cov:
                        val = interest_cov.get('value')
                        if val is not None:
                            st.metric("Interest Coverage",
                                    f"{val:.1f}x",
                                    help="EBIT / Interest Expense")
                        else:
                            st.metric("Interest Coverage", "N/A")
                        st.caption(interest_cov.get('assessment', ''))

                with col4:
                    debt_ebitda = balance_sheet.get('debt_to_ebitda', {})
                    if debt_ebitda:
                        st.metric("Debt/EBITDA",
                                f"{debt_ebitda.get('value', 0):.1f}x",
                                help="Total Debt / EBITDA")
                        st.caption(debt_ebitda.get('assessment', ''))

                # Second row: Cash, Net Debt, Debt Trend
                st.markdown("")
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    cash_info = balance_sheet.get('cash', {})
                    if cash_info:
                        st.metric("Cash & Equivalents",
                                cash_info.get('formatted', 'N/A'),
                                help="Cash + Short-term Investments")

                with col2:
                    net_debt_info = balance_sheet.get('net_debt', {})
                    if net_debt_info:
                        st.metric("Net Debt",
                                net_debt_info.get('formatted', 'N/A'),
                                help="Total Debt - Cash")
                        st.caption(net_debt_info.get('assessment', ''))

                with col3:
                    debt_trend = balance_sheet.get('debt_trend', {})
                    if debt_trend:
                        st.metric("Debt Trend (YoY)",
                                f"{debt_trend.get('yoy_change_%', 0):+.1f}%")
                        st.caption(debt_trend.get('direction', ''))

                with col4:
                    quick_r = balance_sheet.get('quick_ratio', {})
                    if quick_r:
                        st.metric("Quick Ratio",
                                f"{quick_r.get('value', 0):.2f}x",
                                help="(Current Assets - Inventory) / Current Liabilities")
                        st.caption(quick_r.get('assessment', ''))

            # 5. Valuation Multiples vs Peers
            valuation_multiples = intrinsic.get('valuation_multiples', {})
            if valuation_multiples:
                st.markdown("---")
                st.markdown("###  Valuation Multiples vs Peers")

                company_vals = valuation_multiples.get('company', {})
                peers_avg = valuation_multiples.get('peers_avg', {})
                vs_peers = valuation_multiples.get('vs_peers', {})

                if company_vals:
                    col1, col2, col3, col4, col5 = st.columns(5)

                    with col1:
                        pe = company_vals.get('pe')
                        if pe:
                            peer_pe = peers_avg.get('pe')
                            if peer_pe:
                                delta_info = vs_peers.get('pe', {})
                                delta_val = delta_info.get('premium_discount_%', 0)
                                st.metric("P/E Ratio",
                                        f"{pe:.1f}x",
                                        delta=f"{delta_val:+.1f}% vs peers")
                                st.caption(f"Peers: {peer_pe:.1f}x")
                            else:
                                st.metric("P/E Ratio", f"{pe:.1f}x")

                    with col2:
                        pb = company_vals.get('pb')
                        if pb:
                            peer_pb = peers_avg.get('pb')
                            if peer_pb:
                                delta_info = vs_peers.get('pb', {})
                                delta_val = delta_info.get('premium_discount_%', 0)
                                st.metric("P/B Ratio",
                                        f"{pb:.2f}x",
                                        delta=f"{delta_val:+.1f}% vs peers")
                                st.caption(f"Peers: {peer_pb:.2f}x")
                            else:
                                st.metric("P/B Ratio", f"{pb:.2f}x")

                    with col3:
                        ps = company_vals.get('ps')
                        if ps:
                            peer_ps = peers_avg.get('ps')
                            if peer_ps:
                                delta_info = vs_peers.get('ps', {})
                                delta_val = delta_info.get('premium_discount_%', 0)
                                st.metric("P/S Ratio",
                                        f"{ps:.2f}x",
                                        delta=f"{delta_val:+.1f}% vs peers")
                                st.caption(f"Peers: {peer_ps:.2f}x")
                            else:
                                st.metric("P/S Ratio", f"{ps:.2f}x")

                    with col4:
                        ev_ebitda = company_vals.get('ev_ebitda')
                        if ev_ebitda:
                            peer_ev = peers_avg.get('ev_ebitda')
                            if peer_ev:
                                delta_info = vs_peers.get('ev_ebitda', {})
                                delta_val = delta_info.get('premium_discount_%', 0)
                                st.metric("EV/EBITDA",
                                        f"{ev_ebitda:.1f}x",
                                        delta=f"{delta_val:+.1f}% vs peers")
                                st.caption(f"Peers: {peer_ev:.1f}x")
                            else:
                                st.metric("EV/EBITDA", f"{ev_ebitda:.1f}x")

                    with col5:
                        peg = company_vals.get('peg')
                        if peg:
                            peer_peg = peers_avg.get('peg')
                            eps_growth = company_vals.get('eps_growth_%', 0)
                            if peer_peg:
                                delta_info = vs_peers.get('peg', {})
                                delta_val = delta_info.get('premium_discount_%', 0)
                                st.metric("PEG Ratio",
                                        f"{peg:.2f}",
                                        delta=f"{delta_val:+.1f}% vs peers")
                                st.caption(f"Growth: {eps_growth:.1f}%")
                            else:
                                st.metric("PEG Ratio", f"{peg:.2f}")
                                st.caption(f"Growth: {eps_growth:.1f}%")

                    # Summary assessment
                    premium_count = sum(1 for m in vs_peers.values() if m.get('assessment') == 'Premium')
                    discount_count = sum(1 for m in vs_peers.values() if m.get('assessment') == 'Discount')

                    st.markdown("")
                    if premium_count > discount_count:
                        st.warning(f" Trading at a **premium** to peers on {premium_count}/{len(vs_peers)} metrics")
                    elif discount_count > premium_count:
                        st.success(f" Trading at a **discount** to peers on {discount_count}/{len(vs_peers)} metrics")
                    else:
                        st.info(f" **In-line** with peer valuations")

            # 6. Growth Consistency (Historical Trends)
            growth_consistency = intrinsic.get('growth_consistency', {})
            if growth_consistency:
                st.markdown("---")
                st.markdown("###  Growth Consistency & Historical Trends")

                overall_assess = growth_consistency.get('overall_assessment', '')
                if 'Highly Consistent' in overall_assess:
                    st.success(f"**{overall_assess}**")
                elif 'Volatile' in overall_assess:
                    st.error(f"**{overall_assess}**")
                else:
                    st.info(f"**{overall_assess}**")

                # Revenue
                revenue_data = growth_consistency.get('revenue', {})
                if revenue_data:
                    st.markdown("#### Valuation: Revenue Growth")
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("Avg Growth",
                                f"{revenue_data.get('avg_growth_%', 0):.1f}%/yr",
                                help=f"Over {revenue_data.get('years', 0)} years")

                    with col2:
                        st.metric("Consistency",
                                revenue_data.get('consistency', 'Unknown'),
                                help="Based on standard deviation")
                        st.caption(f"σ = {revenue_data.get('std_dev', 0):.1f}%")

                    with col3:
                        trend = revenue_data.get('trend', 'Unknown')
                        if trend == 'Growing':
                            st.success(f"**{trend}**")
                        elif trend == 'Declining':
                            st.error(f"**{trend}**")
                        else:
                            st.info(f"**{trend}**")

                    with col4:
                        history = revenue_data.get('history', [])
                        if history:
                            st.caption("Last 5Y Revenue ($B):")
                            st.caption(", ".join([f"{h:.1f}" for h in history[:5]]))

                # Earnings
                earnings_data = growth_consistency.get('earnings', {})
                if earnings_data:
                    st.markdown("####  Earnings Growth")
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("Avg Growth",
                                f"{earnings_data.get('avg_growth_%', 0):.1f}%/yr",
                                help=f"Over {earnings_data.get('years', 0)} years")

                    with col2:
                        st.metric("Consistency",
                                earnings_data.get('consistency', 'Unknown'),
                                help="Based on standard deviation")
                        st.caption(f"σ = {earnings_data.get('std_dev', 0):.1f}%")

                    with col3:
                        trend = earnings_data.get('trend', 'Unknown')
                        if trend == 'Growing':
                            st.success(f"**{trend}**")
                        elif trend == 'Declining':
                            st.error(f"**{trend}**")
                        else:
                            st.info(f"**{trend}**")

                    with col4:
                        history = earnings_data.get('history', [])
                        if history:
                            st.caption("Last 5Y Earnings ($B):")
                            st.caption(", ".join([f"{h:.1f}" for h in history[:5]]))

                # FCF
                fcf_data = growth_consistency.get('fcf', {})
                if fcf_data:
                    st.markdown("#### 💸 Free Cash Flow Growth")
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("Avg Growth",
                                f"{fcf_data.get('avg_growth_%', 0):.1f}%/yr",
                                help=f"Over {fcf_data.get('years', 0)} years")

                    with col2:
                        st.metric("Consistency",
                                fcf_data.get('consistency', 'Unknown'),
                                help="Based on standard deviation")
                        st.caption(f"σ = {fcf_data.get('std_dev', 0):.1f}%")

                    with col3:
                        trend = fcf_data.get('trend', 'Unknown')
                        if trend == 'Growing':
                            st.success(f"**{trend}**")
                        elif trend == 'Declining':
                            st.error(f"**{trend}**")
                        else:
                            st.info(f"**{trend}**")

                    with col4:
                        history = fcf_data.get('history', [])
                        if history:
                            st.caption("Last 5Y FCF ($B):")
                            st.caption(", ".join([f"{h:.1f}" for h in history[:5]]))

            # 7. Cash Conversion Cycle (FASE 1)
            cash_cycle = intrinsic.get('cash_conversion_cycle', {})
            if cash_cycle:
                st.markdown("---")
                st.markdown("###  Cash Conversion Cycle (Working Capital Efficiency)")

                # Overall assessment
                assessment = cash_cycle.get('assessment', 'Unknown')
                ccc_val = cash_cycle.get('ccc', 0)

                if 'Excellent' in assessment:
                    st.success(f"**{assessment}** - CCC: {ccc_val:.0f} days")
                elif 'Very Good' in assessment or 'Good' in assessment:
                    st.info(f"**{assessment}** - CCC: {ccc_val:.0f} days")
                elif 'Poor' in assessment or 'Concerning' in assessment:
                    st.error(f"**{assessment}** - CCC: {ccc_val:.0f} days")
                else:
                    st.warning(f"**{assessment}** - CCC: {ccc_val:.0f} days")

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    dso = cash_cycle.get('dso', 0)
                    st.metric("DSO (Days Sales Outstanding)",
                            f"{dso:.0f} days",
                            help="How long to collect receivables")

                with col2:
                    dio = cash_cycle.get('dio', 0)
                    st.metric("DIO (Days Inventory Outstanding)",
                            f"{dio:.0f} days",
                            help="How long inventory sits")

                with col3:
                    dpo = cash_cycle.get('dpo', 0)
                    st.metric("DPO (Days Payables Outstanding)",
                            f"{dpo:.0f} days",
                            help="How long to pay suppliers")

                with col4:
                    trend = cash_cycle.get('trend', 'stable')
                    yoy_change = cash_cycle.get('yoy_change', 0)
                    if trend == 'improving':
                        st.metric("YoY Trend", " Improving", delta=f"{yoy_change:.0f} days")
                    elif trend == 'deteriorating':
                        st.metric("YoY Trend", "📉 Worsening", delta=f"{yoy_change:+.0f} days")
                    else:
                        st.metric("YoY Trend", "→ Stable", delta=f"{yoy_change:+.0f} days")

                st.caption(" Lower CCC = Better working capital efficiency. Negative CCC means suppliers finance operations.")

            # 8. Operating Leverage (FASE 1)
            operating_lev = intrinsic.get('operating_leverage', {})
            if operating_lev:
                st.markdown("---")
                st.markdown("###  Operating Leverage (Cost Structure)")

                ol_val = operating_lev.get('operating_leverage', 0)
                risk_level = operating_lev.get('risk_level', 'Unknown')
                assessment = operating_lev.get('assessment', '')

                # Color-code by risk
                if risk_level == 'Low':
                    st.success(f"**Operating Leverage: {ol_val:.2f}x** - {risk_level} Risk")
                elif risk_level == 'Moderate':
                    st.info(f"**Operating Leverage: {ol_val:.2f}x** - {risk_level} Risk")
                elif risk_level in ['Moderate-High', 'High', 'Very High']:
                    st.warning(f"**Operating Leverage: {ol_val:.2f}x** - {risk_level} Risk")
                else:
                    st.info(f"**Operating Leverage: {ol_val:.2f}x** - {risk_level} Risk")

                st.caption(assessment)

                col1, col2, col3 = st.columns(3)

                with col1:
                    rev_change = operating_lev.get('revenue_change_%', 0)
                    st.metric("Revenue Change (YoY)", f"{rev_change:+.1f}%")

                with col2:
                    ebit_change = operating_lev.get('ebit_change_%', 0)
                    st.metric("EBIT Change (YoY)", f"{ebit_change:+.1f}%")

                with col3:
                    ol_avg = operating_lev.get('ol_avg_2y', 0)
                    st.metric("2Y Avg OL", f"{ol_avg:.2f}x")

                st.caption(" High OL = High fixed costs. Profits amplify with revenue growth but also with declines.")

            # 9. Reinvestment Quality (FASE 1)
            reinvestment = intrinsic.get('reinvestment_quality', {})
            if reinvestment:
                st.markdown("---")
                st.markdown("###  Reinvestment Quality (Capital Efficiency of Growth)")

                quality = reinvestment.get('quality', 'Unknown')
                assessment = reinvestment.get('assessment', '')

                # Color-code by quality
                if quality == 'High Quality':
                    st.success(f"**{quality} Growth**")
                elif quality == 'Good Quality':
                    st.info(f"**{quality} Growth**")
                elif quality == 'Moderate Quality':
                    st.warning(f"**{quality} Growth**")
                else:
                    st.error(f"**{quality} Growth**")

                st.caption(assessment)

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    reinv_rate = reinvestment.get('reinvestment_rate_%', 0)
                    st.metric("Reinvestment Rate",
                            f"{reinv_rate:.1f}%",
                            help="(Net Capex + ΔWC) / NOPAT")

                with col2:
                    rev_growth = reinvestment.get('revenue_growth_%', 0)
                    st.metric("Revenue Growth",
                            f"{rev_growth:.1f}%",
                            help="YoY revenue growth")

                with col3:
                    growth_roic = reinvestment.get('growth_roic', 0)
                    st.metric("Growth ROIC",
                            f"{growth_roic:.2f}x",
                            help="Revenue Growth / Reinvestment Rate")
                    if growth_roic > 2:
                        st.caption(" Excellent")
                    elif growth_roic > 1:
                        st.caption(" Good")
                    elif growth_roic > 0.5:
                        st.caption(" Moderate")
                    else:
                        st.caption("❌ Poor")

                with col4:
                    net_capex = reinvestment.get('net_capex', 0)
                    delta_wc = reinvestment.get('delta_wc', 0)
                    st.metric("Net Capex",
                            f"${net_capex/1e9:.1f}B",
                            delta=f"ΔWC: ${delta_wc/1e9:.1f}B")

                st.caption(" Growth ROIC > 1 = Efficient growth. > 2 = Exceptional capital efficiency.")

            # 10. Economic Profit / EVA (FASE 2)
            eva = intrinsic.get('economic_profit', {})
            if eva:
                st.markdown("---")
                st.markdown("###  Economic Profit (EVA - Economic Value Added)")

                grade = eva.get('grade', 'C')
                assessment = eva.get('assessment', '')

                # Color-code by grade
                if grade in ['A', 'B', 'B-']:
                    st.success(f"**Grade: {grade}** - {assessment}")
                elif grade == 'C':
                    st.warning(f"**Grade: {grade}** - {assessment}")
                else:
                    st.error(f"**Grade: {grade}** - {assessment}")

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    eva_val = eva.get('eva_formatted', 'N/A')
                    eva_margin = eva.get('eva_margin_%', 0)
                    st.metric("Economic Value Added",
                            eva_val,
                            delta=f"{eva_margin:.1f}% margin")

                with col2:
                    nopat = eva.get('nopat_formatted', 'N/A')
                    st.metric("NOPAT",
                            nopat,
                            help="Net Operating Profit After Tax")

                with col3:
                    ic = eva.get('ic_formatted', 'N/A')
                    wacc = eva.get('wacc', 0)
                    st.metric("Invested Capital",
                            ic,
                            delta=f"WACC: {wacc:.1f}%")

                with col4:
                    trend = eva.get('trend', 'stable')
                    avg_eva = eva.get('avg_eva_formatted', 'N/A')
                    if trend == 'improving':
                        st.metric("5Y Avg EVA", avg_eva, delta=" Improving")
                    elif trend == 'deteriorating':
                        st.metric("5Y Avg EVA", avg_eva, delta="📉 Declining")
                    else:
                        st.metric("5Y Avg EVA", avg_eva, delta="→ Stable")

                st.caption(" EVA = NOPAT - (WACC × Invested Capital). Positive EVA = Value creation above cost of capital.")

            # 11. Capital Allocation Score (FASE 2)
            cap_alloc = intrinsic.get('capital_allocation', {})
            if cap_alloc:
                st.markdown("---")
                st.markdown("###  Capital Allocation Scorecard")

                score = cap_alloc.get('score', 0)
                grade = cap_alloc.get('grade', 'C')
                assessment = cap_alloc.get('assessment', '')

                # Color-code by grade
                if grade in ['A', 'B']:
                    st.success(f"**Score: {score}/100 (Grade {grade})** - {assessment}")
                elif grade == 'C':
                    st.info(f"**Score: {score}/100 (Grade {grade})** - {assessment}")
                else:
                    st.warning(f"**Score: {score}/100 (Grade {grade})** - {assessment}")

                # FCF Breakdown
                st.markdown("**Free Cash Flow Deployment:**")
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    fcf = cap_alloc.get('fcf_formatted', 'N/A')
                    shareholder_ret = cap_alloc.get('shareholder_return_%', 0)
                    st.metric("Free Cash Flow", fcf, delta=f"{shareholder_ret:.1f}% to shareholders")

                with col2:
                    div_pct = cap_alloc.get('dividend_%_fcf', 0)
                    payout = cap_alloc.get('payout_ratio_%', 0)
                    st.metric("Dividends", f"{div_pct:.1f}% of FCF", delta=f"{payout:.0f}% payout ratio")

                with col3:
                    buyback_pct = cap_alloc.get('buyback_%_fcf', 0)
                    share_trend = cap_alloc.get('share_count_trend', 'stable')
                    emoji = "↓" if share_trend == 'decreasing' else "↑" if share_trend == 'increasing' else "→"
                    st.metric("Buybacks", f"{buyback_pct:.1f}% of FCF", delta=f"Shares {emoji}")

                with col4:
                    debt_pct = cap_alloc.get('debt_paydown_%_fcf', 0)
                    retained = cap_alloc.get('retained_%_fcf', 0)
                    st.metric("Debt Paydown", f"{debt_pct:.1f}% of FCF", delta=f"{retained:.1f}% retained")

                # Key factors
                factors = cap_alloc.get('factors', [])
                if factors:
                    st.markdown("**Key Factors:**")
                    for factor in factors[:4]:  # Show top 4
                        st.caption(f"• {factor}")

                st.caption(" Best allocators: Return capital when opportunities are scarce, reinvest when ROIC > WACC.")

            # 12. Interest Rate Sensitivity (FASE 2)
            rate_sens = intrinsic.get('interest_rate_sensitivity', {})
            if rate_sens and rate_sens.get('applicable', False):
                st.markdown("---")
                st.markdown("###  Interest Rate Sensitivity (Financial Companies)")

                assessment = rate_sens.get('assessment', '')
                sensitivity = rate_sens.get('rate_sensitivity', '')

                st.info(f"**{assessment}**")
                st.caption(sensitivity)

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    nim = rate_sens.get('nim_%', 0)
                    avg_nim = rate_sens.get('nim_5y_avg', 0)
                    st.metric("Net Interest Margin",
                            f"{nim:.2f}%",
                            delta=f"5Y Avg: {avg_nim:.2f}%")

                with col2:
                    trend = rate_sens.get('nim_trend', 'stable')
                    yoy = rate_sens.get('nim_yoy_change', 0)
                    if trend == 'expanding':
                        st.metric("NIM Trend", " Expanding", delta=f"+{yoy:.2f}% YoY")
                    elif trend == 'compressing':
                        st.metric("NIM Trend", "📉 Compressing", delta=f"{yoy:.2f}% YoY")
                    else:
                        st.metric("NIM Trend", "→ Stable", delta=f"{yoy:+.2f}% YoY")

                with col3:
                    nii = rate_sens.get('nii_formatted', 'N/A')
                    st.metric("Net Interest Income", nii)

                with col4:
                    ltd = rate_sens.get('loan_to_deposit_%')
                    if ltd:
                        st.metric("Loan/Deposit Ratio", f"{ltd:.1f}%")

                # NIM history
                nim_hist = rate_sens.get('nim_history', [])
                if nim_hist:
                    st.caption(f"**NIM History (last {len(nim_hist)} years):** " +
                             ", ".join([f"{h:.2f}%" for h in nim_hist]))

                st.caption(" Higher NIM = More profitable. Expanding NIM = Benefiting from rate increases.")

            # 13. Insider Trading Analysis (Premium Feature)
            insider = intrinsic.get('insider_trading', {})
            if insider and insider.get('available', False):
                st.markdown("---")
                st.markdown("###  Insider Trading Activity (Last 12 Months)")

                signal = insider.get('signal', 'Neutral')
                score = insider.get('score', 0)
                assessment = insider.get('assessment', '')

                # Color-code by signal
                if signal == 'Strong Buy':
                    st.success(f"**Signal: {signal}** (Score: {score}/100)")
                elif signal == 'Buy':
                    st.info(f"**Signal: {signal}** (Score: {score}/100)")
                elif signal == 'Weak Buy':
                    st.info(f"**Signal: {signal}** (Score: {score}/100)")
                elif signal == 'Neutral':
                    st.warning(f"**Signal: {signal}** (Score: {score}/100)")
                else:
                    st.error(f"**Signal: {signal}** (Score: {score}/100)")

                st.caption(assessment)

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    buy_count = insider.get('buy_count_12m', 0)
                    sell_count = insider.get('sell_count_12m', 0)
                    st.metric("Buys vs Sells (12M)", f"{buy_count} / {sell_count}")

                with col2:
                    recent_buys = insider.get('recent_buys_3m', 0)
                    unique_buyers = insider.get('unique_buyers_3m', 0)
                    st.metric("Recent Activity (3M)", f"{recent_buys} buys", delta=f"{unique_buyers} insiders")

                with col3:
                    exec_buys = insider.get('executive_buys', 0)
                    st.metric("Executive Buys", f"{exec_buys}", help="CEO/CFO purchases")

                with col4:
                    net_pos = insider.get('net_position', 'Neutral')
                    buy_val = insider.get('buy_value_formatted', 'N/A')
                    sell_val = insider.get('sell_value_formatted', 'N/A')
                    if net_pos == 'Buying':
                        st.metric("Net Position", " Buying")
                    else:
                        st.metric("Net Position", " Selling")
                    st.caption(f"Buy: {buy_val} | Sell: {sell_val}")

                # Show recent trades
                recent_trades = insider.get('recent_trades', [])
                if recent_trades:
                    st.markdown("**Most Recent Buys:**")
                    for trade in recent_trades[:3]:
                        st.caption(f"• {trade.get('date')}: {trade.get('name')} - ${trade.get('value')/1e3:.0f}K")

                st.caption(" Multiple insider buys (especially executives) often precede stock price increases.")

            # 14. Earnings Call Sentiment (Premium Feature)
            sentiment = intrinsic.get('earnings_sentiment', {})
            if sentiment and sentiment.get('available', False):
                st.markdown("---")
                st.markdown("### 🎤 Earnings Call Sentiment Analysis")

                tone = sentiment.get('tone', 'Neutral')
                grade = sentiment.get('grade', 'C')
                assessment = sentiment.get('assessment', '')

                # Color-code by grade
                if grade == 'A':
                    st.success(f"**Tone: {tone}** (Grade: {grade})")
                elif grade == 'B':
                    st.info(f"**Tone: {tone}** (Grade: {grade})")
                elif grade == 'C':
                    st.warning(f"**Tone: {tone}** (Grade: {grade})")
                else:
                    st.error(f"**Tone: {tone}** (Grade: {grade})")

                st.caption(assessment)

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    net_sent = sentiment.get('net_sentiment', 0)
                    if net_sent > 0:
                        st.metric("Net Sentiment", f"+{net_sent:.1f}", delta="Positive")
                    else:
                        st.metric("Net Sentiment", f"{net_sent:.1f}", delta="Negative")

                with col2:
                    confidence = sentiment.get('confidence_%', 0)
                    st.metric("Confidence", f"{confidence}%", help="Analysis reliability")

                with col3:
                    pos_pct = sentiment.get('positive_%', 0)
                    neg_pct = sentiment.get('negative_%', 0)
                    st.metric("Positive Keywords", f"{pos_pct:.1f}%")
                    st.caption(f"Negative: {neg_pct:.1f}%")

                with col4:
                    quarter = sentiment.get('quarter', 'N/A')
                    has_guidance = sentiment.get('has_guidance', False)
                    st.metric("Quarter", quarter)
                    if has_guidance:
                        st.caption(" Guidance provided")
                    else:
                        st.caption(" No guidance")

                # Keyword breakdown
                st.markdown("**Keyword Mentions:**")
                pos_count = sentiment.get('positive_mentions', 0)
                neg_count = sentiment.get('negative_mentions', 0)
                cau_count = sentiment.get('caution_mentions', 0)
                st.caption(f"Growth/Positive: {pos_count} | Challenges/Negative: {neg_count} | Caution: {cau_count}")

                st.caption(" Positive sentiment from management often signals confidence in future performance.")

            # 15. Price Projections by Scenario
            projections = intrinsic.get('price_projections', {})
            if projections and 'scenarios' in projections:
                st.markdown("---")
                st.markdown("###  Price Projections by Scenario")

                scenarios = projections.get('scenarios', {})

                if scenarios:
                    # Display as table
                    scenario_names = list(scenarios.keys())

                    # Create columns for each scenario
                    cols = st.columns(len(scenario_names))

                    for i, (scenario_name, data) in enumerate(scenarios.items()):
                        with cols[i]:
                            # Emoji based on scenario
                            if 'Bear' in scenario_name:
                                emoji = '🐻'
                                color = '#ff6b6b'
                            elif 'Bull' in scenario_name:
                                emoji = '🐂'
                                color = '#51cf66'
                            else:
                                emoji = ''
                                color = '#ffd43b'

                            st.markdown(f"**{emoji} {scenario_name}**")
                            st.caption(data.get('description', ''))
                            st.caption(f"Growth: {data.get('growth_assumption', 'N/A')}")

                            st.markdown("**Price Targets:**")
                            st.metric("1 Year", f"${data.get('1Y_target', 0):.2f}",
                                     delta=data.get('1Y_return', 'N/A'))
                            st.metric("3 Year", f"${data.get('3Y_target', 0):.2f}",
                                     delta=data.get('3Y_cagr', 'N/A') + " CAGR")
                            st.metric("5 Year", f"${data.get('5Y_target', 0):.2f}",
                                     delta=data.get('5Y_cagr', 'N/A') + " CAGR")

                    st.caption("**Note:** Projections based on fundamental growth. Not investment advice.")

            # 5. Red Flags
            red_flags = intrinsic.get('red_flags', [])
            if red_flags:
                st.markdown("---")
                st.markdown("### 🚩 Red Flags Detected")
                for flag in red_flags:
                    st.error(flag)
            else:
                if 'red_flags' in intrinsic:
                    st.markdown("---")
                    st.markdown("###  No Red Flags Detected")
                    st.success("All financial health checks passed")

            # 6. Reverse DCF
            reverse_dcf = intrinsic.get('reverse_dcf', {})
            if reverse_dcf:
                st.markdown("---")
                st.markdown("###  Reverse DCF: Market Expectations")
                col1, col2, col3 = st.columns(3)

                with col1:
                    implied_growth = reverse_dcf.get('implied_growth_rate', 0)
                    st.metric("Implied Growth", f"{implied_growth:.1f}%")
                    st.caption("What market expects")

                with col2:
                    current_growth = reverse_dcf.get('current_growth_rate', 0)
                    st.metric("Actual Growth", f"{current_growth:.1f}%")
                    st.caption("Current reality")

                with col3:
                    implied_multiple = reverse_dcf.get('implied_ev_ebit')
                    if implied_multiple:
                        st.metric("Implied EV/EBIT", f"{implied_multiple:.1f}x")

                interpretation = reverse_dcf.get('interpretation', '')
                if interpretation:
                    if "acceleration" in interpretation.lower():
                        st.info(f"💭 {interpretation}")
                    elif "above" in interpretation.lower():
                        st.warning(f" {interpretation}")
                    elif "continuation" in interpretation.lower():
                        st.success(f" {interpretation}")
                    else:
                        st.error(f"📉 {interpretation}")

            # ========== TECHNICAL ANALYSIS SECTION (NEW) ==========
            # Check if technical analysis is available
            tech_key = f'custom_{formatted_custom_ticker}_tech'
            if tech_key in st.session_state:
                tech_analysis = st.session_state[tech_key]

                if tech_analysis and 'error' not in tech_analysis:
                    st.markdown("---")
                    st.markdown("---")
                    st.header("Technical Analysis")
                    st.caption("Full technical setup including SmartDynamicStopLoss with State Machine")

                    # Get price from analysis
                    current_price = tech_analysis.get('current_price', 0)

                    #Header
                    col1, col2, col3 = st.columns([2, 1, 1])

                    with col1:
                        sector_name = st.session_state.get(f'custom_{formatted_custom_ticker}_sector', 'Unknown')
                        st.markdown(f"**Sector:** {sector_name} | **Price:** ${current_price:.2f}")

                    with col2:
                        tech_score = tech_analysis.get('score', 0)
                        signal = tech_analysis.get('signal', 'HOLD')

                        if signal == 'BUY':
                            st.success(f"** {signal}**")
                        elif signal == 'HOLD':
                            st.info(f"** {signal}**")
                        else:
                            st.error(f"** {signal}**")

                        st.metric("Technical Score", f"{tech_score:.0f}/100")

                    with col3:
                        market_regime = tech_analysis.get('market_regime', 'UNKNOWN')
                        st.metric("Market Regime", get_market_regime_display(market_regime))
                        st.caption(f"Confidence: {tech_analysis.get('regime_confidence', 'unknown')}")

                    st.markdown("---")

                    # Component scores
                    st.markdown("####  Technical Components (NEW Scoring)")

                    components = tech_analysis.get('component_scores', {})

                    col1, col2, col3, col4, col5 = st.columns(5)

                    with col1:
                        st.metric("Multi-TF Momentum", f"{components.get('momentum', 0):.0f}/25")
                        st.caption(f"{tech_analysis.get('momentum_consistency', 'N/A')}")

                    with col2:
                        st.metric("Risk-Adjusted", f"{components.get('risk_adjusted', 0):.0f}/15")
                        st.caption(f"Sharpe: {tech_analysis.get('sharpe_12m', 0):.2f}")

                    with col3:
                        st.metric("Sector Relative", f"{components.get('sector_relative', 0):.0f}/15")
                        st.caption(tech_analysis.get('sector_status', 'N/A'))

                    with col4:
                        st.metric("Market Relative", f"{components.get('market_relative', 0):.0f}/10")
                        st.caption(tech_analysis.get('market_status', 'N/A'))

                    with col5:
                        st.metric("Volume Profile", f"{components.get('volume', 0):.0f}/10")
                        st.caption(tech_analysis.get('volume_profile', 'N/A'))

                    # Regime Adjustment
                    regime_adj = components.get('regime_adjustment', 0)
                    if regime_adj != 0:
                        st.info(f"⚖️ Market Regime Adjustment: {regime_adj:+.0f} pts ({market_regime} market)")

                    # Detailed Metrics
                    st.markdown("---")
                    st.markdown("####  Detailed Metrics")

                    tab1, tab2, tab3, tab4 = st.tabs(["Momentum", "Risk & Relative Strength", "Trend & Volume", "Market Context"])

                    with tab1:
                        st.markdown("**Multi-Timeframe Momentum:**")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("12M Return", f"{tech_analysis.get('momentum_12m', 0):+.1f}%")
                        with col2:
                            st.metric("6M Return", f"{tech_analysis.get('momentum_6m', 0):+.1f}%")
                        with col3:
                            st.metric("3M Return", f"{tech_analysis.get('momentum_3m', 0):+.1f}%")
                        with col4:
                            st.metric("1M Return", f"{tech_analysis.get('momentum_1m', 0):+.1f}%")

                        st.write(f"**Consistency:** {tech_analysis.get('momentum_consistency', 'N/A')}")
                        st.write(f"**Status:** {tech_analysis.get('momentum_status', 'N/A')}")

                    with tab2:
                        col1, col2 = st.columns(2)

                        with col1:
                            st.markdown("**Risk Metrics:**")
                            st.write(f"- Sharpe Ratio (12M): {tech_analysis.get('sharpe_12m', 0):.2f}")
                            st.write(f"- Volatility (12M): {tech_analysis.get('volatility_12m', 0):.1f}%")
                            st.write(f"- Risk Status: {tech_analysis.get('risk_adjusted_status', 'N/A')}")

                        with col2:
                            st.markdown("**Relative Strength:**")
                            st.write(f"- vs Sector: {tech_analysis.get('sector_relative', 0):+.1f}%")
                            st.write(f"- vs Market (SPY): {tech_analysis.get('market_relative', 0):+.1f}%")
                            st.write(f"- Sector Status: {tech_analysis.get('sector_status', 'N/A')}")
                            st.write(f"- Market Status: {tech_analysis.get('market_status', 'N/A')}")

                    with tab3:
                        col1, col2 = st.columns(2)

                        with col1:
                            st.markdown("**Trend Analysis:**")
                            st.write(f"- Trend: {tech_analysis.get('trend', 'N/A')}")
                            st.write(f"- Distance from MA200: {tech_analysis.get('distance_from_ma200', 0):+.1f}%")
                            st.write(f"- Golden Cross: {'' if tech_analysis.get('golden_cross') else '❌'}")

                        with col2:
                            st.markdown("**Volume Analysis:**")
                            st.write(f"- Profile: {tech_analysis.get('volume_profile', 'N/A')}")
                            st.write(f"- Trend: {tech_analysis.get('volume_trend', 'N/A')}")
                            st.write(f"- Accumulation Ratio: {tech_analysis.get('accumulation_ratio', 0):.2f}")

                    with tab4:
                        st.markdown("**Market Environment:**")
                        st.write(f"- Regime: **{market_regime}** ({tech_analysis.get('regime_confidence', 'unknown')} confidence)")

                        # Show regime details
                        st.info("""
                        **Market regime affects momentum effectiveness:**
                        -  **BULL**: Momentum +20% more effective
                        -  **BEAR**: Momentum -60% effectiveness (crowding)
                        -  **SIDEWAYS**: Normal momentum behavior
                        """)

                    # SmartDynamicStopLoss section
                    st.markdown("---")
                    # Get stop_loss from risk_management (correct location)
                    risk_mgmt = tech_analysis.get('risk_management', {})
                    stop_loss = risk_mgmt.get('stop_loss', {})
                    if stop_loss:
                        display_smart_stop_loss(stop_loss, current_price)
                    else:
                        st.warning(" SmartDynamicStopLoss data not available. Analysis may be incomplete.")

                    # ========== RISK MANAGEMENT RECOMMENDATIONS SECTION ==========
                    st.markdown("---")
                    st.header("Risk Management & Trading Strategy")
                    st.caption("Evidence-based position sizing, entry strategy, and profit targets")

                    # risk_mgmt already obtained above for SmartDynamicStopLoss

                    if risk_mgmt:
                        # Create tabs for different risk management areas
                        rm_tab1, rm_tab2, rm_tab3, rm_tab4, rm_tab5 = st.tabs([
                            " Position Sizing",
                            " Entry Strategy",
                            " Stop Loss",
                            " Profit Taking",
                            " Options Strategies"
                        ])

                        with rm_tab1:
                            pos_sizing = risk_mgmt.get('position_sizing', {})
                            if pos_sizing:
                                # Use enhanced display function with dual constraint system
                                display_position_sizing(
                                    pos_sizing,
                                    stop_loss_data=risk_mgmt.get('stop_loss'),
                                    portfolio_size=portfolio_capital,
                                    max_risk_dollars=max_risk_per_trade_dollars
                                )

                        with rm_tab2:
                            entry_strategy = risk_mgmt.get('entry_strategy', {})
                            if entry_strategy:
                                # Use new state-based entry strategy display
                                display_entry_strategy(entry_strategy)

                        with rm_tab3:
                            stop_loss_rec = risk_mgmt.get('stop_loss', {})
                            if stop_loss_rec:
                                # Use SmartDynamicStopLoss data (already displayed above)
                                st.info(" See SmartDynamicStopLoss section above for detailed stop loss recommendations with State Machine analysis")

                        with rm_tab4:
                            profit_taking = risk_mgmt.get('profit_taking', {})
                            if profit_taking:
                                # Use professional Take Profit display function
                                display_take_profit(profit_taking)

                        with rm_tab5:
                            options_strategies = risk_mgmt.get('options_strategies', [])
                            if options_strategies:
                                for strategy in options_strategies:
                                    with st.expander(f" {strategy.get('name', 'Strategy')}"):
                                        if 'when' in strategy:
                                            st.write(f"**When to use:** {strategy['when']}")
                                        if 'structure' in strategy:
                                            st.write(f"**Structure:** {strategy['structure']}")
                                        if 'strike' in strategy:
                                            st.write(f"**Strike Selection:** {strategy['strike']}")
                                        if 'example' in strategy:
                                            st.code(strategy['example'])
                                        if 'premium' in strategy:
                                            st.write(f" {strategy['premium']}")
                                        if 'credit' in strategy:
                                            st.write(f"Valuation: {strategy['credit']}")
                                        if 'cost' in strategy:
                                            st.write(f"Valuation: {strategy['cost']}")
                                        if 'leverage' in strategy:
                                            st.write(f" {strategy['leverage']}")
                                        if 'max_profit' in strategy:
                                            st.write(f" {strategy['max_profit']}")
                                        if 'max_loss' in strategy:
                                            st.write(f" {strategy['max_loss']}")

                                        if 'rationale' in strategy:
                                            st.info(f"**Rationale:** {strategy['rationale']}")
                                        if 'benefit' in strategy:
                                            st.success(f" **Benefit:** {strategy['benefit']}")
                                        if 'risk' in strategy:
                                            st.warning(f" **Risk:** {strategy['risk']}")

                                        # Scenarios
                                        if 'outcome_1' in strategy:
                                            st.write(f"**Scenario 1:** {strategy['outcome_1']}")
                                        if 'outcome_2' in strategy:
                                            st.write(f"**Scenario 2:** {strategy['outcome_2']}")

                                        # Evidence
                                        if 'evidence' in strategy:
                                            st.caption(f"📚 {strategy['evidence']}")

                                        # Additional notes
                                        if 'note' in strategy:
                                            st.caption(f" {strategy['note']}")

                                st.caption(" Based on academic research (Black-Scholes, Whaley 2002, Daniel & Moskowitz 2016, etc.)")
                            else:
                                st.info("No options strategies available for current technical setup")
                    else:
                        st.warning(" Risk management recommendations not available. Technical analysis may be incomplete.")

            # Export to Excel
            st.markdown("---")
            st.markdown("### 📥 Export Analysis")

            try:
                excel_data = create_qualitative_excel(analysis, custom_ticker, datetime.now())
                st.download_button(
                    label=" Download Complete Analysis (Excel)",
                    data=excel_data,
                    file_name=f"{custom_ticker}_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    help="Download full analysis with all metrics"
                )
                st.caption(" Includes: Valuation, Capital Efficiency, Earnings Quality, Margins, Red Flags, Reverse DCF, and more")
            except Exception as e:
                st.error(f"Excel export failed: {e}")

        else:
            st.info(f" Enter a ticker above and click 'Analyze' to see detailed quality and valuation analysis")

with tab8:
    st.markdown("""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 2rem; border-radius: 12px; color: white; margin-bottom: 2rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
        <h2 style='margin: 0; color: white; font-weight: 700;'>About UltraQuality</h2>
        <p style='margin: 0.5rem 0 0 0; opacity: 0.95;'>
            Methodology, academic research, and screening framework details
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    ###  What It Does

    UltraQuality es un **screener financiero completo** que combina:

    1. ** Fundamental Analysis** (Quality + Value investing)
    2. ** Technical Analysis** (Evidence-based timing)
    3. ** Risk Guardrails** (Fraud detection, accounting quality)
    4. ** Qualitative Insights** (Earnings analysis, management assessment)

    ---

    ##  FUNDAMENTAL ANALYSIS

    ### Value Metrics
    - **EV/EBIT, P/E, P/B**: Valuation multiples
    - **Shareholder Yield**: Dividends + Buybacks + Debt reduction
    - **Earnings Yield (ROIC-adjusted)**: Quality-adjusted valuation
    - **Reverse DCF**: Implied growth expectations

    ### Quality Metrics
    - **ROIC, ROA, ROE**: Capital efficiency
    - **FCF Margin**: Cash generation quality
    - **Moat Score**: Competitive advantages (pricing power, operating leverage, ROIC persistence)
    - **Working Capital Efficiency**: DSO, DIO, Cash Conversion Cycle
    - **Margin Trajectory**: Gross/Operating margin trends (12Q linear regression)

    ### Guardrails (Accounting Quality)

    **Traditional:**
    - **Altman Z-Score**: Bankruptcy prediction (1968)
    - **Beneish M-Score**: Earnings manipulation detection (1999)
    - **Accruals/NOA**: Quality of earnings (Sloan 1996)

    **Advanced Red Flags:**
    - **Cash Conversion Quality**: FCF/NI ratio (manipulation check)
    - **Debt Maturity Wall**: Liquidity ratio, interest coverage (refinancing risk)
    - **Benford's Law**: Fraud detection via digit distribution

    ---

    ##  TECHNICAL ANALYSIS

    **Evidence-based indicators ONLY** (no RSI, MACD, Fibonacci):

    - **Momentum 12M** (35 pts): Jegadeesh & Titman (1993), Moskowitz (2012)
    - **Sector Relative Strength** (25 pts): Bretscher (2023), Arnott (2024)
    - **Trend MA200** (25 pts): Brock et al. (1992)
    - **Volume Confirmation** (15 pts): Basic liquidity check

    **Combined Signals:**
    -  **Strong BUY**: Fundamental BUY + Technical BUY (quality + timing aligned)
    -  **BUY**: Fundamental BUY + Technical HOLD (good company, wait for entry)
    - ⏸️ **WAIT**: Fundamental BUY + Technical SELL (great company, bad timing)

    ---

    ##  QUALITATIVE ANALYSIS

    ### Order-Driven Industrials
    - **Backlog Analysis**: Extract backlog, book-to-bill ratio from earnings transcripts
    - Applicable to: Aerospace, Defense, Heavy Equipment

    ### Contextual Warnings (Non-scoring)
    - **Customer Concentration**: Revenue dependency risk
    - **Management Turnover**: CEO/CFO changes (leadership stability)
    - **Geographic Exposure**: China/Russia geopolitical risk

    ### Additional Metrics
    - **R&D Efficiency**: Revenue per $1 R&D (Tech/Pharma only)
    - **Insider Selling Clusters**: 3+ executives selling same date (red flag)
    - **Skin in the Game**: Insider ownership, recent buys/sells

    ---

    ##  PERFORMANCE OPTIMIZATIONS

    ### 1. Caching System
    - Intelligent TTL-based caching by endpoint type
    - **90% reduction** in API costs
    - **10-50x speedup** on re-analysis
    - Cache stats tracking (hit rate, size)

    ### 2. Historical Tracking
    - SQLite database storing metric snapshots over time
    - **Trend analysis**: Detect improving/deteriorating/acceleration
    - Compare current vs historical average
    - Export to CSV for external analysis

    ### 3. Peer Comparison
    - **Percentile rankings** vs sector peers
    - Context: "DSO 64 days (85th percentile, worse than 85% of peers)"
    - Overall rank: Top Quartile / Above Average / Below Average / Bottom Quartile

    ---

    ##  Asset Types Supported

    - **Non-Financials**: Manufacturing, Tech, Services, Consumer, Industrials
    - **Financials**: Banks, Insurance, Asset Management
    - **REITs**: Real Estate Investment Trusts

    **Geographic Coverage:**
    - USA (full coverage)
    - Canada
    - UK
    -  Europe (limited qualitative analysis)
    - Japan (adjusted thresholds for weaker momentum)
    -  Emerging Markets (with caution, stricter thresholds)

    ---

    ##  Methodology

    ### Phase 1: Universe Building
    1. **Screening**: Filter by market cap, volume, country
    2. **Top-K Selection**: Preliminary ranking (2000+ → 100 deep analysis)

    ### Phase 2: Fundamental Analysis
    3. **Feature Calculation**: Value & Quality metrics (asset-type specific)
    4. **Guardrails**: Accounting quality checks (VERDE/AMBAR/ROJO)
    5. **Qualitative**: Contextual analysis (warnings, insights)
    6. **Scoring**: Industry-normalized z-scores

    ### Phase 3: Technical Analysis (NEW)
    7. **Technical Scoring**: Momentum, Sector, Trend, Volume (0-100)
    8. **Combined Signal**: 70% Fundamental + 30% Technical

    ### Phase 4: Decision
    9. **Final Ranking**: BUY / MONITOR / AVOID
    10. **Export**: CSV/Excel with complete analysis

    ---

    ## ⚖️ Scoring Formula

    ### Fundamental Score (0-100)
    ```
    Composite = (Value Weight × Value Score) + (Quality Weight × Quality Score)

    Decision:
    - Score ≥ 75 + VERDE → BUY
    - Score 60-75 or AMBAR → MONITOR
    - Score < 60 or ROJO → AVOID
    ```

    ### Technical Score (0-100)
    ```
    Score = Momentum(35) + Sector(25) + Trend(25) + Volume(15)

    Signal:
    - Score ≥ 75 → BUY
    - Score 50-75 → HOLD
    - Score < 50 → SELL
    ```

    ### Combined Score
    ```
    Final = (Fundamental × 0.70) + (Technical × 0.30)

    Strong BUY: Fundamental BUY + Technical BUY (both >75)
    ```

    ---

    ## 📚 Academic References

    ### Fundamental (Quality & Value)
    - **Altman (1968)** - Z-Score bankruptcy prediction
    - **Beneish (1999)** - M-Score earnings manipulation
    - **Sloan (1996)** - Accruals anomaly
    - **Novy-Marx (2013)** - Gross profitability premium
    - **Piotroski (2000)** - F-Score fundamental analysis
    - **Greenblatt (2005)** - Magic Formula (ROIC + EY)

    ### Technical (Evidence-based)
    - **Jegadeesh & Titman (1993, 2001)** - Momentum works
    - **Moskowitz, Ooi & Pedersen (2012)** - Time series momentum (58 markets)
    - **Brock, Lakonishok & LeBaron (1992)** - Simple technical rules
    - **Bretscher, Julliard & Rosa (2023)** - Power of passive investing (sector momentum)
    - **Arnott, Harvey & Rattray (2024)** - Sector rotation
    - **Asness, Moskowitz & Pedersen (2013)** - Value and momentum everywhere

    ### Recent Evidence (2020-2024)
    - **Ehsani & Linnainmaa (2022)** - Factor momentum decay
    - **Gupta & Kelly (2023)** - Factor momentum everywhere (updated)
    - **Gu, Kelly & Xiu (2020)** - Machine learning in asset pricing
    - **Jacobs & Müller (2020)** - Anomalies across the globe (47 countries)

    ---

    ## 🛠️ Technical Stack

    - **Data Source**: Financial Modeling Prep (FMP) API
    - **Backend**: Python 3.9+ (pandas, numpy, scipy)
    - **Caching**: Pickle-based local cache + SQLite historical DB
    - **Frontend**: Streamlit (interactive web app)
    - **Analysis**:
      - Guardrails: `src/screener/guardrails.py`
      - Qualitative: `src/screener/qualitative.py`
      - Technical: `src/screener/technical/analyzer.py`
      - Peer Comparison: `src/screener/peer_comparison.py`
      - Historical: `src/screener/historical.py`

    ---

    ##  Features Summary

    | Feature | Status | Evidence |
    |---------|--------|----------|
    | Value Metrics |  | Graham, Greenblatt |
    | Quality Metrics |  | Novy-Marx, Piotroski |
    | Moat Score |  | Proprietary (pricing power, leverage, persistence) |
    | Guardrails (Traditional) |  | Altman, Beneish, Sloan |
    | Working Capital Analysis |  | Cash cycle efficiency |
    | Margin Trajectory |  | 12Q linear regression |
    | Cash Conversion Quality |  | FCF/NI manipulation check |
    | Debt Maturity Analysis |  | Refinancing risk |
    | Benford's Law |  | Fraud detection |
    | Backlog Analysis |  | Order-driven industrials |
    | Contextual Warnings |  | Customer, Management, Geographic |
    | R&D Efficiency |  | Tech/Pharma ROI |
    | Insider Analysis |  | Ownership, clusters, skin in game |
    | Caching System |  | 90% API cost reduction |
    | Historical Tracking |  | Trend analysis, acceleration |
    | Peer Comparison |  | Percentile rankings |
    | **Technical Analysis** |  | **Momentum, Sector, Trend, Volume** |

    **Total Features:** 17 fundamental + 4 technical = **21 features**

    ---

    ##  Disclaimer

    **IMPORTANT:** This tool is for **educational and research purposes only**.

    - ❌ **NOT** investment advice
    - ❌ **NOT** a recommendation to buy or sell securities
    - ❌ **NOT** a substitute for professional financial advice

    **You must:**
    -  Conduct your own due diligence
    -  Consult with a qualified financial advisor
    -  Understand the risks of investing
    -  Only invest money you can afford to lose

    Past performance does not guarantee future results. All investing involves risk.

    ---

    ## 🔗 Links

    - 📖 [Documentation](https://github.com/pblo97/UltraQuality) - Full guide and methodology
    - 🔌 [FMP API](https://financialmodelingprep.com) - Data provider
    -  [Streamlit](https://streamlit.io) - Web framework

    ---

    ##  Version History

    - **v1.0** - Initial release (Quality + Value screening)
    - **v2.0** - Added advanced guardrails (Working Capital, Margins, Debt, Cash Conversion)
    - **v2.5** - Qualitative analysis (Backlog, Contextual warnings, R&D, Insider)
    - **v3.0** - TOP 3 Enhancements (Caching, Historical, Peer Comparison)
    - **v4.0** - **Technical Analysis** (Evidence-based timing) ⬅️ **Current**

    ---

    **UltraQuality** - Combining the best of fundamental and technical analysis, backed by academic research.
    """)

with tab7:
    # Modern header with gradient
    st.markdown("""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 2rem; border-radius: 12px; color: white; margin-bottom: 2rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
        <h2 style='margin: 0; color: white; font-weight: 700;'>Technical Analysis & Investment Strategy</h2>
        <p style='margin: 0.5rem 0 0 0; opacity: 0.95;'>
            Evidence-based technical analysis with position sizing and risk management
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Methodology card
    with st.expander("📚 Methodology - Academic Evidence (2020-2024)", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("""
            **✅ Evidence-Based Indicators:**
            - **12-Month Momentum** (Jegadeesh & Titman 1993, Moskowitz 2021)
              → Strongest predictor of future returns
            - **Sector Relative Strength** (Bretscher 2023, Arnott 2024)
              → Industry leadership indicates structural advantages
            - **Trend Following (MA200)** (Brock et al. 1992, updated 2023)
              → Long-term trend identification
            - **Volume Confirmation** (Lo & Wang 2000)
              → Institutional accumulation/distribution
            """)

        with col2:
            st.markdown("""
            **❌ Excluded (No Post-2010 Evidence):**
            - RSI (Relative Strength Index)
            - MACD (Moving Average Convergence Divergence)
            - Stochastic Oscillator
            - Fibonacci Retracements
            - Chart Patterns (head & shoulders, triangles, etc.)

            **Why excluded?** Academic research post-2010 shows these
            indicators have no predictive power after transaction costs.
            """)

    st.markdown("---")

    if 'results' not in st.session_state:
        st.info("👈 Run the screener first to analyze technical signals")

    else:
        # Get results
        df = get_results_with_current_params()

        # Filter to BUY and MONITOR only
        df_technical = df[df['decision'].isin(['BUY', 'MONITOR'])].copy()

        if len(df_technical) == 0:
            st.warning(" No BUY or MONITOR signals found. Run screener with different parameters.")
        else:
            st.success(f" Analyzing **{len(df_technical)}** stocks (BUY + MONITOR signals)")

            # Analyze technical for all BUY/MONITOR stocks
            with st.spinner("Running technical analysis... This may take 30-60 seconds"):
                # Initialize analyzer (lazy import)
                try:
                    from screener.technical import TechnicalAnalyzer
                    from screener.cache import CachedFMPClient
                    from screener.ingest import FMPClient

                    # Setup FMP client
                    with open('settings.yaml') as f:
                        config = yaml.safe_load(f)

                    # Get API key (priority: secrets > config with env expansion)
                    api_key = st.secrets.get('fmp_api_key')
                    if not api_key:
                        api_key = expand_env_vars(config['fmp'].get('api_key'))

                    # Validate API key
                    if not api_key or api_key.startswith('${') or api_key == 'your_api_key_here':
                        st.error("❌ **FMP API Key not configured!**")
                        st.markdown("""
                        Please configure your Financial Modeling Prep API key:

                        **Option 1: Streamlit Secrets** (recommended for Streamlit Cloud)
                        1. Create `.streamlit/secrets.toml`
                        2. Add: `fmp_api_key = "your_actual_api_key"`

                        **Option 2: Environment Variable** (for local development)
                        1. Create `.env` file in project root
                        2. Add: `FMP_API_KEY=your_actual_api_key`
                        3. Restart the app

                        Get your API key at: https://financialmodelingprep.com
                        """)
                        st.stop()

                    fmp_base = FMPClient(api_key, config['fmp'])
                    fmp = CachedFMPClient(fmp_base, cache_dir='.cache')

                    # Initialize analyzer
                    tech_analyzer = TechnicalAnalyzer(fmp)

                    # Analyze each stock
                    technical_results = []
                    progress_bar = st.progress(0)

                    for i, (idx, row) in enumerate(df_technical.iterrows()):
                        symbol = row['ticker']
                        sector = row.get('sector', 'Unknown')

                        try:
                            # Extract fundamental data for position sizing (if available)
                            fundamental_score = row.get('composite_0_100', None)
                            fundamental_decision = row.get('decision', None)
                            guardrails_status = row.get('guardrails_status', None)  # May not be in screener DF

                            # Analyze with fundamental data
                            tech_result = tech_analyzer.analyze(
                                symbol,
                                sector=sector,
                                fundamental_score=fundamental_score,
                                guardrails_status=guardrails_status,
                                fundamental_decision=fundamental_decision
                            )

                            # Fetch current price from FMP
                            current_price = 0
                            try:
                                quote = fmp.get_quote(symbol)
                                if quote and len(quote) > 0:
                                    current_price = quote[0].get('price', 0)
                            except:
                                pass  # Use 0 if price fetch fails

                            # Add to results (using NEW enhanced analyzer fields)
                            technical_results.append({
                                'ticker': symbol,
                                'name': row.get('name', ''),
                                'sector': sector,
                                'price': current_price,  # Use current price from FMP
                                'fundamental_decision': row['decision'],
                                'fundamental_score': row['composite_0_100'],
                                'technical_score': tech_result['score'],
                                'technical_signal': tech_result['signal'],
                                'market_regime': tech_result.get('market_regime', 'UNKNOWN'),
                                'momentum_12m': tech_result.get('momentum_12m', 0),
                                'momentum_6m': tech_result.get('momentum_6m', 0),
                                'momentum_consistency': tech_result.get('momentum_consistency', 'N/A'),
                                'sharpe_12m': tech_result.get('sharpe_12m', 0),
                                'trend': tech_result.get('trend', 'UNKNOWN'),
                                'sector_status': tech_result.get('sector_status', 'UNKNOWN'),
                                'market_status': tech_result.get('market_status', 'UNKNOWN'),
                                'volume_profile': tech_result.get('volume_profile', 'UNKNOWN'),
                                'warnings_count': len(tech_result.get('warnings', [])),
                                'warnings': tech_result.get('warnings', []),
                                # Extract SmartDynamicStopLoss state
                                'stop_loss_state': tech_result.get('risk_management', {}).get('stop_loss', {}).get('market_state', 'UNKNOWN'),
                                'stop_loss_emoji': tech_result.get('risk_management', {}).get('stop_loss', {}).get('state_emoji', ''),
                                # IMPORTANT: Save error reason for debugging UNKNOWN issues
                                'error_reason': tech_result.get('error', None),  # Captures "No quote data" / "No historical data" etc.
                                'full_analysis': tech_result
                            })
                        except Exception as e:
                            logger.error(f"Error analyzing {symbol}: {e}")

                            # Fetch current price from FMP (even on error)
                            current_price = 0
                            try:
                                quote = fmp.get_quote(symbol)
                                if quote and len(quote) > 0:
                                    current_price = quote[0].get('price', 0)
                            except:
                                pass  # Use 0 if price fetch fails

                            # Add with error
                            technical_results.append({
                                'ticker': symbol,
                                'name': row.get('name', ''),
                                'sector': sector,
                                'price': current_price,  # Use current price from FMP
                                'fundamental_decision': row['decision'],
                                'fundamental_score': row['composite_0_100'],
                                'technical_score': 50,
                                'technical_signal': 'ERROR',
                                'momentum_12m': 0,
                                'trend': 'ERROR',
                                'sector_status': 'ERROR',
                                'warnings_count': 1,
                                'warnings': [{'type': 'ERROR', 'message': str(e)}],
                                'stop_loss_state': 'ERROR',
                                'stop_loss_emoji': '❌',
                                'full_analysis': None
                            })

                        # Update progress
                        progress_bar.progress((i + 1) / len(df_technical))

                    progress_bar.empty()

                    # Create DataFrame
                    df_tech = pd.DataFrame(technical_results)

                    # Sort by technical score
                    df_tech = df_tech.sort_values('technical_score', ascending=False)

                    # Save to session state
                    st.session_state['technical_results'] = df_tech

                    st.success(" Technical analysis complete!")

                    # === DATA QUALITY DIAGNOSTICS ===
                    # Only show if error_reason column exists (new version)
                    if 'error_reason' in df_tech.columns:
                        st.markdown("---")
                        st.subheader("📊 Data Quality Diagnostics")
                        st.caption("Breakdown of stocks with incomplete technical data")

                        # Count stocks with errors
                        stocks_with_errors = df_tech[df_tech['error_reason'].notna()]
                        total_stocks = len(df_tech)
                        error_count = len(stocks_with_errors)
                        error_pct = (error_count / total_stocks * 100) if total_stocks > 0 else 0

                        # Summary metrics
                        col_diag1, col_diag2, col_diag3 = st.columns(3)
                        with col_diag1:
                            st.markdown(f"""
                            <div style='background: {"#fee2e2" if error_pct > 30 else "#dbeafe"}; padding: 1rem; border-radius: 8px; text-align: center;'>
                                <div style='font-size: 2rem; font-weight: 700; color: {"#991b1b" if error_pct > 30 else "#1e40af"};'>{error_count}</div>
                                <div style='font-size: 0.9rem; color: {"#7f1d1d" if error_pct > 30 else "#3b82f6"};'>stocks with errors</div>
                            </div>
                            """, unsafe_allow_html=True)

                        with col_diag2:
                            st.markdown(f"""
                            <div style='background: {"#fef3c7" if error_pct > 30 else "#d1fae5"}; padding: 1rem; border-radius: 8px; text-align: center;'>
                                <div style='font-size: 2rem; font-weight: 700; color: {"#92400e" if error_pct > 30 else "#065f46"};'>{error_pct:.1f}%</div>
                                <div style='font-size: 0.9rem; color: {"#78350f" if error_pct > 30 else "#059669"};'>of universe</div>
                            </div>
                            """, unsafe_allow_html=True)

                        with col_diag3:
                            clean_count = total_stocks - error_count
                            st.markdown(f"""
                            <div style='background: #d1fae5; padding: 1rem; border-radius: 8px; text-align: center;'>
                                <div style='font-size: 2rem; font-weight: 700; color: #065f46;'>{clean_count}</div>
                                <div style='font-size: 0.9rem; color: #059669;'>stocks with complete data</div>
                            </div>
                            """, unsafe_allow_html=True)

                        if error_count > 0:
                            # Group errors by reason
                            error_groups = stocks_with_errors.groupby('error_reason').agg({
                                'ticker': lambda x: list(x),
                                'error_reason': 'count'
                            }).rename(columns={'error_reason': 'count'})
                            error_groups = error_groups.sort_values('count', ascending=False)

                            st.markdown("### 🔍 Error Breakdown")

                            for error_reason, row in error_groups.iterrows():
                                count = row['count']
                                pct = (count / error_count * 100)
                                tickers = row['ticker'][:10]  # Show first 10 examples
                                more_count = count - len(tickers)

                                with st.expander(f"**{error_reason}** ({count} stocks, {pct:.1f}% of errors)", expanded=False):
                                    st.markdown(f"**Examples:** {', '.join(tickers)}" + (f" ...and {more_count} more" if more_count > 0 else ""))

                                    # Add specific recommendations based on error type
                                    if "No quote data" in error_reason:
                                        st.info("💡 **Likely cause:** Delisted stocks, incorrect symbols, or stocks not available in FMP")
                                    elif "No historical data" in error_reason:
                                        st.info("💡 **Likely cause:** New IPOs, low-liquidity stocks, or foreign symbols without data")
                                    elif "historical" in error_reason.lower() and "key" in error_reason.lower():
                                        st.warning("⚠️ **Likely cause:** API response format changed or FMP data structure issue")
                                    else:
                                        st.info("💡 **Recommendation:** Check symbol format and FMP availability")
                        else:
                            st.success("✅ All stocks have complete technical data!")

                    # === SMARTDYNAMICSTOPLOSS STATE SUMMARY ===
                    st.markdown("---")
                    st.markdown("""
                    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 1.5rem;'>
                        <h3 style='margin: 0; color: white; font-weight: 600;'>
                            🎯 Estado del Mercado por Acción
                        </h3>
                        <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem;'>
                            SmartDynamicStopLoss - Clasificación automática del estado técnico actual
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

                    # Group by stop_loss_state
                    state_groups = df_tech.groupby('stop_loss_state')['ticker'].apply(list).to_dict()

                    # Define state order and styling
                    state_config = {
                        'DOWNTREND': {'icon': '📉', 'color': 'error', 'label': '🔴 Tendencia Bajista - Evitar Entrada', 'priority': 1},
                        'PARABOLIC_CLIMAX': {'icon': '🚀', 'color': 'warning', 'label': '🟡 Sobreextendido - Alto Riesgo de Corrección', 'priority': 2},
                        'CHOPPY_SIDEWAYS': {'icon': '↔️', 'color': 'info', 'label': '🔵 Lateral - Esperar Definición', 'priority': 3},
                        'PULLBACK_FLAG': {'icon': '🏴', 'color': 'success', 'label': '🟢 Retroceso Saludable - Zona de Compra', 'priority': 4},
                        'ENTRY_BREAKOUT': {'icon': '🚪', 'color': 'success', 'label': '🟢 Breakout Confirmado - Entrada Activa', 'priority': 5},
                        'POWER_TREND': {'icon': '⚡', 'color': 'success', 'label': '🟢 Tendencia Potente - Mantener Posición', 'priority': 6},
                        'BLUE_SKY_ATH': {'icon': '⭐', 'color': 'success', 'label': '🟢 Máximos Históricos - Sin Resistencia', 'priority': 7},
                        'UNKNOWN': {'icon': '❓', 'color': 'info', 'label': '⚪ Datos Incompletos', 'priority': 99},
                        'ERROR': {'icon': '❌', 'color': 'error', 'label': '🔴 Error en Análisis', 'priority': 100}
                    }

                    # Sort states by priority
                    sorted_states = sorted(
                        state_groups.keys(),
                        key=lambda x: state_config.get(x, {'priority': 999})['priority']
                    )

                    # Display in columns (2 per row for better visibility)
                    for i in range(0, len(sorted_states), 2):
                        cols = st.columns(2)

                        for j, col in enumerate(cols):
                            if i + j < len(sorted_states):
                                state = sorted_states[i + j]
                                tickers = state_groups[state]
                                config = state_config.get(state, {'icon': '<i class="bi bi-question-circle" style="font-size: 3rem;"></i>', 'color': 'info', 'label': state, 'priority': 999})

                                with col:
                                    # Use appropriate streamlit component for color
                                    if config['color'] == 'error':
                                        st.error(f"**{config['icon']} {config['label']}** ({len(tickers)})")
                                    elif config['color'] == 'warning':
                                        st.warning(f"**{config['icon']} {config['label']}** ({len(tickers)})")
                                    elif config['color'] == 'success':
                                        st.success(f"**{config['icon']} {config['label']}** ({len(tickers)})")
                                    else:
                                        st.info(f"**{config['icon']} {config['label']}** ({len(tickers)})")

                                    # Show tickers as comma-separated list (max 10 per line)
                                    ticker_display = ', '.join(tickers[:15])
                                    if len(tickers) > 15:
                                        ticker_display += f" ... (+{len(tickers)-15} más)"
                                    st.caption(ticker_display)

                    st.markdown("---")

                    # Debug info - show signal distribution
                    with st.expander(" Analysis Summary", expanded=False):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.write("**Signal Distribution:**")
                            signal_counts = df_tech['technical_signal'].value_counts()
                            for signal, count in signal_counts.items():
                                st.write(f"- {signal}: {count} ({count/len(df_tech)*100:.1f}%)")

                        with col2:
                            st.write("**Score Stats:**")
                            st.write(f"- Min: {df_tech['technical_score'].min():.1f}")
                            st.write(f"- Avg: {df_tech['technical_score'].mean():.1f}")
                            st.write(f"- Max: {df_tech['technical_score'].max():.1f}")

                        with col3:
                            st.write("**Top 3 Stocks:**")
                            top3 = df_tech.nlargest(3, 'technical_score')
                            for _, row in top3.iterrows():
                                st.write(f"- {row['ticker']}: {row['technical_score']:.0f} ({row['technical_signal']})")

                except Exception as e:
                    st.error(f"❌ Error initializing technical analysis: {str(e)}")
                    st.exception(e)

            # Display results
            if 'technical_results' in st.session_state:
                df_tech = st.session_state['technical_results']

                # Check if results are from old version (before error_reason column was added)
                if 'error_reason' not in df_tech.columns:
                    st.warning("""
                    ⚠️ **Outdated Results Detected**

                    Your technical results were generated with an older version of the code.

                    **Please click "Run Technical Analysis" again** to see the new **Data Quality Diagnostics** report.
                    """)
                    st.info("💡 **New in this version:** Detailed breakdown showing WHY each stock has UNKNOWN data (delisted, no history, API errors, etc.)")

                # Summary metrics
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    tech_buys = len(df_tech[df_tech['technical_signal'] == 'BUY'])
                    st.metric(" Tech BUY", tech_buys, f"{tech_buys/len(df_tech)*100:.0f}%")

                with col2:
                    tech_holds = len(df_tech[df_tech['technical_signal'] == 'HOLD'])
                    st.metric(" Tech HOLD", tech_holds, f"{tech_holds/len(df_tech)*100:.0f}%")

                with col3:
                    avg_tech_score = df_tech['technical_score'].mean()
                    st.metric("Avg Tech Score", f"{avg_tech_score:.1f}")

                with col4:
                    # Strong buys (both fundamental and technical)
                    strong_buys = len(df_tech[
                        (df_tech['fundamental_decision'] == 'BUY') &
                        (df_tech['technical_signal'] == 'BUY')
                    ])
                    st.metric(" Strong BUY", strong_buys, "Fund + Tech")

                st.markdown("---")

                # Quick Preset Buttons
                st.markdown("**Filter Presets (Quick Discovery):**")
                preset_col1, preset_col2, preset_col3, preset_col4, preset_col5 = st.columns(5)

                with preset_col1:
                    if st.button("Bulls Only", help="BULL market + UPTREND"):
                        st.session_state['regime_filter'] = ['BULL']
                        st.session_state['trend_filter'] = ['UPTREND', 'STRONG_UPTREND']

                with preset_col2:
                    if st.button("Leaders Only", help="Sector + Market leaders"):
                        st.session_state['sector_filter'] = ['LEADING', 'OUTPERFORMER']

                with preset_col3:
                    if st.button("Strong Momentum", help="Consistent + Accumulation"):
                        st.session_state['consistency_filter'] = ['VERY_CONSISTENT', 'CONSISTENT']
                        st.session_state['volume_filter'] = ['ACCUMULATION']

                with preset_col4:
                    if st.button("Clear Filters", help="Reset all filters to defaults"):
                        # Clear all filter states
                        for key in ['regime_filter', 'sector_filter', 'trend_filter', 'volume_filter', 'consistency_filter', 'hide_incomplete_data']:
                            if key in st.session_state:
                                del st.session_state[key]

                with preset_col5:
                    if st.button("Top Quality", help="BUY signal + 75+ score"):
                        st.session_state['tech_signal_filter'] = ['BUY']
                        st.session_state['min_tech_score'] = 75

                st.markdown("---")

                # ============================================================
                # HIERARCHICAL FILTER STRUCTURE
                # Level 1: Trading Signals (Outputs)
                # Level 2: Market Context (External Factors)
                # Level 3: Technical Components (Building Blocks)
                # Level 4: Data Quality
                # ============================================================

                # LEVEL 1: TRADING SIGNALS (High-Level Decisions)
                st.markdown("""
                <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            padding: 0.5rem 1rem; border-radius: 8px; margin-bottom: 0.5rem;'>
                    <div style='color: white; font-weight: 600; font-size: 0.85rem;'>
                        🎯 TRADING SIGNALS (Decision Outputs)
                    </div>
                </div>
                """, unsafe_allow_html=True)

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    tech_signal_filter = st.multiselect(
                        "Technical Signal",
                        options=['BUY', 'HOLD', 'SELL'],
                        default=['BUY', 'HOLD', 'SELL'],
                        help="Final technical trading signal (BUY if score ≥75 AND uptrend)",
                        key='tech_signal_filter'
                    )

                with col2:
                    fund_decision_filter = st.multiselect(
                        "Fundamental Decision",
                        options=['BUY', 'MONITOR'],
                        default=['BUY', 'MONITOR'],
                        help="Fundamental quality+value decision",
                        key='fund_decision_filter'
                    )

                with col3:
                    min_tech_score = st.slider(
                        "Min Technical Score",
                        0, 100, 0,
                        help="Composite technical score (0-100)",
                        key='min_tech_score'
                    )

                with col4:
                    # Get unique stop loss states for filter
                    all_sl_states = sorted(df_tech['stop_loss_state'].unique().tolist())
                    sl_state_filter = st.multiselect(
                        "Stop Loss State",
                        options=all_sl_states,
                        default=all_sl_states,
                        help="SmartDynamicStopLoss state (execution layer)",
                        key='sl_state_filter'
                    )

                # LEVEL 2: MARKET CONTEXT (External Factors)
                st.markdown("""
                <div style='background: #f8fafc; padding: 0.5rem 1rem; border-radius: 8px;
                            margin-top: 0.75rem; margin-bottom: 0.5rem; border-left: 4px solid #667eea;'>
                    <div style='color: #475569; font-weight: 600; font-size: 0.85rem;'>
                        🌐 MARKET CONTEXT (External Environment)
                    </div>
                </div>
                """, unsafe_allow_html=True)

                col5, col6 = st.columns(2)

                with col5:
                    all_regimes = sorted(df_tech['market_regime'].unique().tolist())
                    regime_filter = st.multiselect(
                        "Market Regime",
                        options=all_regimes,
                        default=all_regimes,
                        help="Overall market state (BULL/BEAR/SIDEWAYS) - affects regime adjustment in score",
                        key='regime_filter'
                    )

                with col6:
                    all_sector_status = sorted(df_tech['sector_status'].unique().tolist())
                    sector_filter = st.multiselect(
                        "Sector Status",
                        options=all_sector_status,
                        default=all_sector_status,
                        help="Sector relative strength vs market - contributes to sector_score component",
                        key='sector_filter'
                    )

                # LEVEL 3: TECHNICAL COMPONENTS (Building Blocks) - ADVANCED DIAGNOSTIC FILTERS
                # These are the RAW INPUTS that make up the Technical Score
                # Filtering by both Score AND Components is REDUNDANT
                st.markdown("""
                <div style='background: #fff3cd; padding: 0.75rem 1rem; border-radius: 8px;
                            margin-top: 0.75rem; margin-bottom: 0.5rem; border-left: 4px solid #ffc107;'>
                    <div style='color: #856404; font-weight: 600; font-size: 0.85rem;'>
                        ⚙️ ADVANCED: Diagnostic Component Filters
                    </div>
                    <div style='color: #856404; font-size: 0.75rem; margin-top: 0.25rem;'>
                        💡 <strong>TIP:</strong> These components are ALREADY included in Technical Score and Signal.
                        Use these filters only for advanced diagnostic analysis to understand WHY a stock has a certain score.
                        Filtering by both Score ≥75 AND Trend=UPTREND is redundant (Trend already contributes 10-15 pts to Score).
                    </div>
                </div>
                """, unsafe_allow_html=True)

                with st.expander("🔍 Show Component Filters (Advanced - Usually Not Needed)", expanded=False):
                    st.caption("⚠️ WARNING: Filtering by components AND score filters the same data twice. "
                              "These filters are for diagnosing WHY a score is high/low, not for primary filtering.")

                    col7, col8, col9 = st.columns(3)

                    with col7:
                        all_trends = sorted(df_tech['trend'].unique().tolist())
                        trend_filter = st.multiselect(
                            "Trend (Contributes ~15pts)",
                            options=all_trends,
                            default=all_trends,
                            help="⚠️ REDUNDANT with Technical Score. Trend status already contributes +15 pts if UPTREND. "
                                "Use this ONLY to diagnose why stocks have certain scores, not for primary filtering.",
                            key='trend_filter'
                        )

                    with col8:
                        all_volumes = sorted(df_tech['volume_profile'].unique().tolist())
                        volume_filter = st.multiselect(
                            "Volume (Contributes ~5pts)",
                            options=all_volumes,
                            default=all_volumes,
                            help="⚠️ REDUNDANT with Technical Score. Volume pattern already contributes ~5 pts to score. "
                                "Use this ONLY to diagnose why stocks have certain scores.",
                            key='volume_filter'
                        )

                    with col9:
                        all_consistency = sorted(df_tech['momentum_consistency'].unique().tolist())
                        consistency_filter = st.multiselect(
                            "Momentum (Contributes ~35pts)",
                            options=all_consistency,
                            default=all_consistency,
                            help="⚠️ REDUNDANT with Technical Score. Momentum consistency already contributes ~35-40 pts to score. "
                                "Use this ONLY to diagnose why stocks have certain scores.",
                            key='consistency_filter'
                        )

                # LEVEL 4: DATA QUALITY FILTER
                st.markdown("""
                <div style='background: #fef3c7; padding: 0.5rem 1rem; border-radius: 8px;
                            margin-top: 0.75rem; margin-bottom: 0.5rem; border-left: 4px solid #f59e0b;'>
                    <div style='color: #92400e; font-weight: 600; font-size: 0.85rem;'>
                        ⚠️ DATA QUALITY
                    </div>
                </div>
                """, unsafe_allow_html=True)

                col_dq1, col_dq2, col_dq3 = st.columns([2, 2, 2])

                with col_dq1:
                    hide_incomplete_data = st.checkbox(
                        "Hide stocks with incomplete data",
                        value=False,
                        help="Exclude stocks with UNKNOWN market regime, trend, or sector status (usually due to insufficient price history)",
                        key='hide_incomplete_data'
                    )

                with col_dq2:
                    # Count stocks with incomplete data
                    incomplete_mask = (
                        (df_tech['market_regime'] == 'UNKNOWN') |
                        (df_tech['trend'] == 'UNKNOWN') |
                        (df_tech['sector_status'] == 'UNKNOWN')
                    )
                    incomplete_count = incomplete_mask.sum()
                    st.markdown(f"""
                    <div style='background: #fee2e2; padding: 0.5rem; border-radius: 6px; text-align: center;'>
                        <div style='font-size: 1.2rem; font-weight: 700; color: #991b1b;'>{incomplete_count}</div>
                        <div style='font-size: 0.7rem; color: #7f1d1d;'>stocks with incomplete data</div>
                    </div>
                    """, unsafe_allow_html=True)

                with col_dq3:
                    # Show percentage
                    pct_incomplete = (incomplete_count / len(df_tech) * 100) if len(df_tech) > 0 else 0
                    st.markdown(f"""
                    <div style='background: #fef3c7; padding: 0.5rem; border-radius: 6px; text-align: center;'>
                        <div style='font-size: 1.2rem; font-weight: 700; color: #92400e;'>{pct_incomplete:.1f}%</div>
                        <div style='font-size: 0.7rem; color: #78350f;'>of universe</div>
                    </div>
                    """, unsafe_allow_html=True)

                # Apply filters
                df_filtered = df_tech[
                    # Level 1: Trading Signals
                    (df_tech['technical_signal'].isin(tech_signal_filter)) &
                    (df_tech['fundamental_decision'].isin(fund_decision_filter)) &
                    (df_tech['stop_loss_state'].isin(sl_state_filter)) &
                    (df_tech['technical_score'] >= min_tech_score) &
                    # Level 2: Market Context
                    (df_tech['market_regime'].isin(regime_filter)) &
                    (df_tech['sector_status'].isin(sector_filter)) &
                    # Level 3: Technical Components
                    (df_tech['trend'].isin(trend_filter)) &
                    (df_tech['volume_profile'].isin(volume_filter)) &
                    (df_tech['momentum_consistency'].isin(consistency_filter))
                ]

                # Level 4: Data Quality Filter
                if hide_incomplete_data:
                    df_filtered = df_filtered[
                        (df_filtered['market_regime'] != 'UNKNOWN') &
                        (df_filtered['trend'] != 'UNKNOWN') &
                        (df_filtered['sector_status'] != 'UNKNOWN')
                    ]

                st.markdown(f"""
                <div style='background: #dbeafe; padding: 0.75rem; border-radius: 8px; margin-top: 0.75rem;'>
                    <div style='font-size: 1.1rem; font-weight: 600; color: #1e40af;'>
                        📊 {len(df_filtered)} stocks match filters
                        <span style='font-size: 0.85rem; color: #3b82f6; font-weight: 400;'>
                            (filtered from {len(df_tech)} total)
                        </span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Main table
                st.subheader("Technical Ranking (Enhanced)")

                display_cols = [
                    'ticker', 'name', 'sector',
                    'stop_loss_state',  # Added SmartDynamicStopLoss state
                    'market_regime',
                    'technical_score', 'technical_signal',
                    'momentum_6m', 'momentum_consistency',
                    'sharpe_12m', 'trend',
                    'sector_status', 'market_status',
                    'volume_profile',
                    'fundamental_score', 'fundamental_decision',
                    'warnings_count'
                ]

                # Format for display
                df_display = df_filtered[display_cols].copy()
                df_display['momentum_6m'] = df_display['momentum_6m'].apply(lambda x: f"{x:+.1f}%")
                df_display['sharpe_12m'] = df_display['sharpe_12m'].apply(lambda x: f"{x:.2f}")

                st.dataframe(
                    df_display,
                    use_container_width=True,
                    height=400,
                    column_config={
                        'ticker': 'Ticker',
                        'name': 'Company',
                        'sector': 'Sector',
                        'stop_loss_state': st.column_config.Column(
                            ' SL State',
                            help='SmartDynamicStopLoss State Machine'
                        ),
                        'technical_score': st.column_config.NumberColumn(
                            'Tech Score',
                            format='%.0f'
                        ),
                        'technical_signal': st.column_config.Column(
                            'Tech Signal'
                        ),
                        'momentum_12m': '12M Return',
                        'trend': 'Trend',
                        'sector_status': 'Sector',
                        'fundamental_score': st.column_config.NumberColumn(
                            'Fund Score',
                            format='%.0f'
                        ),
                        'fundamental_decision': 'Fund Decision',
                        'warnings_count': ''
                    }
                )

                # Detailed analysis section
                st.markdown("---")
                st.subheader("Detailed Analysis")

                # Stock selector
                selected_ticker = st.selectbox(
                    "Select stock for detailed analysis:",
                    options=df_filtered['ticker'].tolist(),
                    key='selected_ticker_technical'
                )

                if selected_ticker:
                    # Get full analysis
                    stock_data = df_filtered[df_filtered['ticker'] == selected_ticker].iloc[0]
                    full_analysis = stock_data['full_analysis']

                    if full_analysis:
                        # Display company info
                        col1, col2 = st.columns([2, 1])

                        with col1:
                            st.markdown(f"### {selected_ticker} - {stock_data['name']}")
                            st.caption(f"Sector: {stock_data['sector']}")

                        with col2:
                            # Combined signal
                            fund_signal = stock_data['fundamental_decision']
                            tech_signal = stock_data['technical_signal']

                            if fund_signal == 'BUY' and tech_signal == 'BUY':
                                st.markdown("""
                                <div style='background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
                                            padding: 1rem; border-radius: 10px; text-align: center;'>
                                    <span class='badge badge-buy' style='font-size: 1.1rem;'>
                                        <i class="bi bi-check-circle-fill"></i> STRONG BUY
                                    </span>
                                    <div style='color: white; margin-top: 0.5rem; font-size: 0.9rem;'>Fundamental + Technical</div>
                                </div>
                                """, unsafe_allow_html=True)
                            elif fund_signal == 'BUY' and tech_signal == 'HOLD':
                                st.markdown("""
                                <div style='background: #d1ecf1; padding: 1rem; border-radius: 10px; text-align: center;
                                            border-left: 4px solid #17a2b8;'>
                                    <span class='badge badge-buy'>
                                        <i class="bi bi-arrow-up-circle"></i> BUY
                                    </span>
                                    <div style='color: #495057; margin-top: 0.5rem; font-size: 0.9rem;'>Good fundamentals, wait for entry</div>
                                </div>
                                """, unsafe_allow_html=True)
                            elif fund_signal == 'BUY' and tech_signal == 'SELL':
                                st.markdown("""
                                <div style='background: #fff3cd; padding: 1rem; border-radius: 10px; text-align: center;
                                            border-left: 4px solid #ffc107;'>
                                    <span class='badge badge-monitor'>
                                        <i class="bi bi-pause-circle"></i> WAIT
                                    </span>
                                    <div style='color: #495057; margin-top: 0.5rem; font-size: 0.9rem;'>Good company, bad timing</div>
                                </div>
                                """, unsafe_allow_html=True)
                            elif fund_signal == 'MONITOR':
                                st.markdown(f"""
                                <div style='background: #fff3cd; padding: 1rem; border-radius: 10px; text-align: center;
                                            border-left: 4px solid #ffc107;'>
                                    <span class='badge badge-monitor'>
                                        <i class="bi bi-eye"></i> MONITOR
                                    </span>
                                    <div style='color: #495057; margin-top: 0.5rem; font-size: 0.9rem;'>Tech Signal: {tech_signal}</div>
                                </div>
                                """, unsafe_allow_html=True)

                        # Score breakdown
                        st.markdown("#### Score Breakdown")

                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.metric(
                                "Technical Score",
                                f"{full_analysis['score']:.0f}/100",
                                delta=full_analysis['signal']
                            )

                        with col2:
                            st.metric(
                                "Fundamental Score",
                                f"{stock_data['fundamental_score']:.0f}/100",
                                delta=stock_data['fundamental_decision']
                            )

                        with col3:
                            # Combined score (70% fundamental, 30% technical)
                            combined = (
                                stock_data['fundamental_score'] * 0.7 +
                                full_analysis['score'] * 0.3
                            )
                            st.metric(
                                "Combined Score",
                                f"{combined:.0f}/100",
                                "70% Fund + 30% Tech"
                            )

                        # === MÓDULO 1: EL CONTEXTO MACRO (El Clima) ===
                        # Always visible header - 3 KPI cards showing market conditions
                        st.markdown("""
                        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                    padding: 1.5rem; border-radius: 12px; margin-bottom: 2rem;'>
                            <h3 style='margin: 0; color: white;'>
                                <i class="bi bi-globe2"></i> MÓDULO 1: CONTEXTO MACRO
                            </h3>
                            <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem;'>
                                ¿Las condiciones favorecen la operación?
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                        # Get data for the 3 cards
                        market_regime = full_analysis.get('market_regime', 'UNKNOWN')
                        sector_status = full_analysis.get('sector_status', 'UNKNOWN')
                        market_status = full_analysis.get('market_status', 'UNKNOWN')
                        trend = full_analysis.get('trend', 'UNKNOWN')
                        distance_ma200 = full_analysis.get('distance_from_ma200', 0)
                        volume_profile = full_analysis.get('volume_profile', 'UNKNOWN')
                        overextension_level = full_analysis.get('overextension_level', 'LOW')
                        components = full_analysis.get('component_scores', {})
                        regime_adj = components.get('regime_adjustment', 0)

                        # Create 3 horizontal KPI cards
                        col1, col2, col3 = st.columns(3)

                        with col1:
                            # TARJETA 1: MARKET REGIME
                            regime_config = {
                                'BULL': {
                                    'icon': '<i class="bi bi-graph-up-arrow" style="font-size: 3rem;"></i>',
                                    'label': 'BULL MARKET',
                                    'bg': 'linear-gradient(135deg, #28a745 0%, #20c997 100%)',
                                    'effectiveness': '+20%',
                                    'risk': 'LOW',
                                    'risk_color': '#28a745'
                                },
                                'BEAR': {
                                    'icon': '<i class="bi bi-graph-down-arrow" style="font-size: 3rem;"></i>',
                                    'label': 'BEAR MARKET',
                                    'bg': 'linear-gradient(135deg, #dc3545 0%, #c82333 100%)',
                                    'effectiveness': '-60%',
                                    'risk': 'HIGH',
                                    'risk_color': '#dc3545'
                                },
                                'SIDEWAYS': {
                                    'icon': '<i class="bi bi-arrow-left-right" style="font-size: 3rem;"></i>',
                                    'label': 'SIDEWAYS MARKET',
                                    'bg': 'linear-gradient(135deg, #ffc107 0%, #ff9800 100%)',
                                    'effectiveness': '-30%',
                                    'risk': 'MEDIUM',
                                    'risk_color': '#ffc107'
                                }
                            }

                            reg_info = regime_config.get(market_regime, {
                                'icon': '<i class="bi bi-question-circle" style="font-size: 3rem;"></i>',
                                'label': 'UNKNOWN',
                                'bg': 'linear-gradient(135deg, #6c757d 0%, #495057 100%)',
                                'effectiveness': 'N/A',
                                'risk': 'UNKNOWN',
                                'risk_color': '#6c757d'
                            })

                            st.markdown(f"""
                            <div style='background: {reg_info['bg']};
                                        padding: 1.5rem; border-radius: 12px; color: white;
                                        box-shadow: 0 4px 12px rgba(0,0,0,0.15); min-height: 280px;'>
                                <div style='text-align: center;'>
                                    <div style='font-size: 3rem; margin-bottom: 0.5rem;'>{reg_info['icon']}</div>
                                    <div style='font-size: 1.3rem; font-weight: 700; margin-bottom: 1rem;'>{reg_info['label']}</div>
                                </div>
                                <div style='background: rgba(255,255,255,0.15); padding: 1rem; border-radius: 8px; margin-bottom: 0.75rem;'>
                                    <div style='font-size: 0.75rem; opacity: 0.9;'>MOMENTUM EFFECTIVENESS</div>
                                    <div style='font-size: 1.5rem; font-weight: 700;'>{reg_info['effectiveness']}</div>
                                </div>
                                <div style='background: rgba(255,255,255,0.15); padding: 1rem; border-radius: 8px; margin-bottom: 0.75rem;'>
                                    <div style='font-size: 0.75rem; opacity: 0.9;'>MARKET RISK LEVEL</div>
                                    <div style='font-size: 1.5rem; font-weight: 700;'>{reg_info['risk']}</div>
                                </div>
                                <div style='background: rgba(255,255,255,0.15); padding: 1rem; border-radius: 8px;'>
                                    <div style='font-size: 0.75rem; opacity: 0.9;'>SCORE ADJUSTMENT</div>
                                    <div style='font-size: 1.5rem; font-weight: 700;'>{regime_adj:+.0f} pts</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        with col2:
                            # TARJETA 2: SECTOR RELATIVE STRENGTH
                            # Determine sector and market colors
                            sector_perf = full_analysis.get('sector_relative', 0)
                            market_perf = full_analysis.get('market_relative', 0)

                            sector_color = '#28a745' if sector_status in ['LEADING', 'OUTPERFORMER'] else '#dc3545' if sector_status in ['LAGGING', 'UNDERPERFORMER'] else '#ffc107'
                            market_color = '#28a745' if market_status in ['LEADING', 'OUTPERFORMER'] else '#dc3545' if market_status in ['LAGGING', 'UNDERPERFORMER'] else '#ffc107'

                            # Overall verdict
                            if sector_status in ['LEADING', 'OUTPERFORMER'] and market_status in ['LEADING', 'OUTPERFORMER']:
                                verdict = 'DOUBLE LEADER'
                                verdict_icon = '<i class="bi bi-star-fill"></i>'
                                verdict_color = '#28a745'
                            elif sector_status in ['LAGGING', 'UNDERPERFORMER'] or market_status in ['LAGGING', 'UNDERPERFORMER']:
                                verdict = 'WEAK'
                                verdict_icon = '<i class="bi bi-exclamation-triangle"></i>'
                                verdict_color = '#dc3545'
                            else:
                                verdict = 'MIXED'
                                verdict_icon = '<i class="bi bi-dash-circle"></i>'
                                verdict_color = '#ffc107'

                            st.markdown(f"""
                            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                        padding: 1.5rem; border-radius: 12px; color: white;
                                        box-shadow: 0 4px 12px rgba(0,0,0,0.15); min-height: 280px;'>
                                <div style='text-align: center; margin-bottom: 1rem;'>
                                    <div style='font-size: 1rem; font-weight: 700; margin-bottom: 0.5rem;'>SECTOR RELATIVE STRENGTH</div>
                                    <div style='font-size: 2.5rem;'>{verdict_icon}</div>
                                </div>
                                <div style='background: rgba(255,255,255,0.15); padding: 1rem; border-radius: 8px; margin-bottom: 0.75rem;'>
                                    <div style='font-size: 0.75rem; opacity: 0.9;'>SECTOR vs MARKET</div>
                                    <div style='font-size: 1.3rem; font-weight: 700;'>{sector_status}</div>
                                    <div style='font-size: 1rem; opacity: 0.9;'>{sector_perf:+.1f}%</div>
                                </div>
                                <div style='background: rgba(255,255,255,0.15); padding: 1rem; border-radius: 8px; margin-bottom: 0.75rem;'>
                                    <div style='font-size: 0.75rem; opacity: 0.9;'>STOCK vs SECTOR</div>
                                    <div style='font-size: 1.3rem; font-weight: 700;'>{market_status}</div>
                                    <div style='font-size: 1rem; opacity: 0.9;'>{market_perf:+.1f}%</div>
                                </div>
                                <div style='background: rgba(255,255,255,0.25); padding: 1rem; border-radius: 8px; text-align: center;'>
                                    <div style='font-size: 1.5rem; font-weight: 700;'>{verdict}</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        with col3:
                            # TARJETA 3: TECHNICAL HEALTH
                            # Determine trend color and emoji
                            trend_config = {
                                'STRONG_UPTREND': {'icon': '<i class="bi bi-rocket-takeoff"></i>', 'color': '#28a745', 'label': 'STRONG UPTREND'},
                                'UPTREND': {'icon': '<i class="bi bi-graph-up"></i>', 'color': '#28a745', 'label': 'UPTREND'},
                                'DOWNTREND': {'icon': '<i class="bi bi-graph-down"></i>', 'color': '#dc3545', 'label': 'DOWNTREND'},
                                'STRONG_DOWNTREND': {'icon': '<i class="bi bi-arrow-down"></i>', 'color': '#dc3545', 'label': 'STRONG DOWNTREND'},
                                'SIDEWAYS': {'icon': '<i class="bi bi-arrow-left-right" style="font-size: 3rem;"></i>', 'color': '#ffc107', 'label': 'SIDEWAYS'}
                            }

                            trend_info = trend_config.get(trend, {'icon': '<i class="bi bi-question-circle" style="font-size: 3rem;"></i>', 'color': '#6c757d', 'label': 'UNKNOWN'})

                            # Extension level colors (matching technical analyzer output)
                            ext_config = {
                                'LOW': {'color': '#28a745', 'label': 'HEALTHY'},
                                'MEDIUM': {'color': '#ffc107', 'label': 'STRETCHED'},
                                'HIGH': {'color': '#ff6b35', 'label': 'OVEREXTENDED'},
                                'EXTREME': {'color': '#dc3545', 'label': 'EXTREME'}
                            }

                            ext_info = ext_config.get(overextension_level, {'color': '#6c757d', 'label': 'UNKNOWN'})

                            # Volume profile
                            vol_config = {
                                'ACCUMULATION': {'icon': '<i class="bi bi-box-arrow-in-down"></i>', 'color': '#28a745'},
                                'DISTRIBUTION': {'icon': '<i class="bi bi-box-arrow-up"></i>', 'color': '#dc3545'},
                                'NEUTRAL': {'icon': '<i class="bi bi-dash"></i>', 'color': '#6c757d'}
                            }

                            vol_info = vol_config.get(volume_profile, {'icon': '<i class="bi bi-question-circle" style="font-size: 3rem;"></i>', 'color': '#6c757d'})

                            st.markdown(f"""
                            <div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
                                        padding: 1.5rem; border-radius: 12px; color: white;
                                        box-shadow: 0 4px 12px rgba(0,0,0,0.15); min-height: 280px;'>
                                <div style='text-align: center; margin-bottom: 1rem;'>
                                    <div style='font-size: 1rem; font-weight: 700; margin-bottom: 0.5rem;'>TECHNICAL HEALTH</div>
                                    <div style='font-size: 2.5rem;'>{trend_info['icon']}</div>
                                </div>
                                <div style='background: rgba(255,255,255,0.15); padding: 1rem; border-radius: 8px; margin-bottom: 0.75rem;'>
                                    <div style='font-size: 0.75rem; opacity: 0.9;'>TREND</div>
                                    <div style='font-size: 1.3rem; font-weight: 700;'>{trend_info['label']}</div>
                                </div>
                                <div style='background: rgba(255,255,255,0.15); padding: 1rem; border-radius: 8px; margin-bottom: 0.75rem;'>
                                    <div style='font-size: 0.75rem; opacity: 0.9;'>EXTENSION</div>
                                    <div style='font-size: 1.3rem; font-weight: 700;'>{ext_info['label']}</div>
                                    <div style='font-size: 1rem; opacity: 0.9;'>{distance_ma200:+.1f}% from MA200</div>
                                </div>
                                <div style='background: rgba(255,255,255,0.15); padding: 1rem; border-radius: 8px;'>
                                    <div style='font-size: 0.75rem; opacity: 0.9;'>VOLUME</div>
                                    <div style='font-size: 1.3rem; font-weight: 700;'>{vol_info['icon']} {volume_profile}</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        st.markdown("---")

                        # === MÓDULO 2: EL DIAGNÓSTICO (El Diagnóstico) ===
                        st.markdown("""
                        <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                                    padding: 1.5rem; border-radius: 12px; margin-bottom: 2rem; margin-top: 2rem;'>
                            <h3 style='margin: 0; color: white;'><i class="bi bi-clipboard2-pulse"></i> MÓDULO 2: DIAGNÓSTICO</h3>
                            <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem;'>
                                Análisis detallado de fuerza y riesgo del activo
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                        # 2-Column Layout: Momentum & Fuerza | Riesgo & Sobre-Extensión
                        col_left, col_right = st.columns(2)

                        # ===== LEFT COLUMN: MOMENTUM & FUERZA =====
                        with col_left:
                            st.markdown("""
                            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                        padding: 1rem; border-radius: 10px; margin-bottom: 1.5rem;'>
                                <h4 style='margin: 0; color: white; text-align: center;'>MOMENTUM & FUERZA</h4>
                            </div>
                            """, unsafe_allow_html=True)

                            # Multi-Timeframe Momentum Display
                            st.markdown("**Multi-Timeframe Returns:**")

                            # Get momentum data
                            mom_12m = full_analysis.get('momentum_12m', 0)
                            mom_6m = full_analysis.get('momentum_6m', 0)
                            mom_3m = full_analysis.get('momentum_3m', 0)
                            mom_1m = full_analysis.get('momentum_1m', 0)

                            # Display each timeframe with color coding
                            for period, value in [('12M', mom_12m), ('6M', mom_6m), ('3M', mom_3m), ('1M', mom_1m)]:
                                mom_color = '#28a745' if value > 10 else '#ffc107' if value > 0 else '#dc3545'
                                mom_norm = min(max((value + 50) / 100, 0), 1)

                                st.markdown(f"""
                                <div style='background: white; padding: 1rem; border-radius: 8px;
                                            box-shadow: 0 2px 6px rgba(0,0,0,0.08); margin-bottom: 0.75rem;
                                            border-left: 4px solid {mom_color};'>
                                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                                        <div style='font-size: 0.9rem; color: #6c757d; font-weight: 600;'>{period} RETURN</div>
                                        <div style='font-size: 1.5rem; font-weight: 700; color: {mom_color};'>{value:+.1f}%</div>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                                st.progress(mom_norm)

                            # Consistency Badge
                            consistency = full_analysis.get('momentum_consistency', 'N/A')
                            momentum_status = full_analysis.get('momentum_status', 'N/A')

                            consist_config = {
                                'VERY_CONSISTENT': {'color': '#28a745', 'icon': '<i class="bi bi-gem"></i>', 'label': 'VERY CONSISTENT'},
                                'CONSISTENT': {'color': '#28a745', 'icon': '<i class="bi bi-check-circle"></i>', 'label': 'CONSISTENT'},
                                'MODERATE': {'color': '#ffc107', 'icon': '<i class="bi bi-exclamation-triangle"></i>', 'label': 'MODERATE'},
                                'CHOPPY': {'color': '#dc3545', 'icon': '<i class="bi bi-exclamation-triangle"></i>', 'label': 'CHOPPY'},
                                'INCONSISTENT': {'color': '#dc3545', 'icon': '<i class="bi bi-x-circle"></i>', 'label': 'INCONSISTENT'}
                            }

                            consist_info = consist_config.get(consistency, {'color': '#6c757d', 'icon': '<i class="bi bi-question-circle" style="font-size: 3rem;"></i>', 'label': consistency})

                            st.markdown("<br>", unsafe_allow_html=True)
                            st.markdown(f"""
                            <div style='background: {consist_info['color']}; padding: 1.25rem; border-radius: 10px;
                                        text-align: center; color: white; margin-bottom: 1rem;'>
                                <div style='font-size: 2rem; margin-bottom: 0.5rem;'>{consist_info['icon']}</div>
                                <div style='font-size: 1.2rem; font-weight: 700;'>{consist_info['label']}</div>
                                <div style='font-size: 0.9rem; opacity: 0.9; margin-top: 0.5rem;'>Consistency</div>
                            </div>
                            """, unsafe_allow_html=True)

                            # Momentum Status
                            st.markdown(f"""
                            <div style='background: #f8f9fa; padding: 1rem; border-radius: 8px;
                                        border-left: 4px solid {consist_info['color']};'>
                                <div style='font-size: 0.85rem; color: #6c757d; margin-bottom: 0.25rem;'>STATUS</div>
                                <div style='font-size: 1.1rem; font-weight: 600; color: #495057;'>{momentum_status}</div>
                            </div>
                            """, unsafe_allow_html=True)

                        # ===== RIGHT COLUMN: RIESGO & SOBRE-EXTENSIÓN =====
                        with col_right:
                            st.markdown("""
                            <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                                        padding: 1rem; border-radius: 10px; margin-bottom: 1.5rem;'>
                                <h4 style='margin: 0; color: white; text-align: center;'>RIESGO & SOBRE-EXTENSIÓN</h4>
                            </div>
                            """, unsafe_allow_html=True)

                            # Get risk data
                            sharpe = full_analysis.get('sharpe_12m', 0)
                            volatility = full_analysis.get('volatility_12m', 0)
                            risk_status = full_analysis.get('risk_adjusted_status', 'N/A')
                            overext_risk = full_analysis.get('overextension_risk', 0)
                            overext_level = full_analysis.get('overextension_level', 'LOW')

                            # Sharpe Ratio
                            sharpe_color = '#28a745' if sharpe > 1.0 else '#ffc107' if sharpe > 0.5 else '#dc3545'
                            sharpe_normalized = min(max(sharpe / 2.0, 0), 1)

                            st.markdown(f"""
                            <div style='background: white; padding: 1rem; border-radius: 8px;
                                        box-shadow: 0 2px 6px rgba(0,0,0,0.08); margin-bottom: 0.75rem;
                                        border-left: 4px solid {sharpe_color};'>
                                <div style='font-size: 0.85rem; color: #6c757d; margin-bottom: 0.5rem;'>SHARPE RATIO (12M)</div>
                                <div style='font-size: 2rem; font-weight: 700; color: {sharpe_color}; text-align: center;'>{sharpe:.2f}</div>
                                <div style='font-size: 0.8rem; color: #6c757d; text-align: center;'>
                                    {'Excellent' if sharpe > 1.0 else 'Good' if sharpe > 0.5 else 'Poor'}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            st.progress(sharpe_normalized)

                            # Volatility
                            vol_color = '#28a745' if volatility < 20 else '#ffc107' if volatility < 40 else '#dc3545'
                            vol_normalized = min(volatility / 100, 1)

                            st.markdown(f"""
                            <div style='background: white; padding: 1rem; border-radius: 8px;
                                        box-shadow: 0 2px 6px rgba(0,0,0,0.08); margin-bottom: 0.75rem;
                                        border-left: 4px solid {vol_color};'>
                                <div style='font-size: 0.85rem; color: #6c757d; margin-bottom: 0.5rem;'>VOLATILITY (12M)</div>
                                <div style='font-size: 2rem; font-weight: 700; color: {vol_color}; text-align: center;'>{volatility:.1f}%</div>
                                <div style='font-size: 0.8rem; color: #6c757d; text-align: center;'>
                                    {'Low' if volatility < 20 else 'Medium' if volatility < 40 else 'High'}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            st.progress(vol_normalized)

                            # Distance from MA200
                            dist_ma200 = full_analysis.get('distance_from_ma200', 0)
                            dist_color = '#28a745' if -5 <= dist_ma200 <= 20 else '#ffc107' if -15 <= dist_ma200 <= 40 else '#dc3545'

                            st.markdown(f"""
                            <div style='background: white; padding: 1rem; border-radius: 8px;
                                        box-shadow: 0 2px 6px rgba(0,0,0,0.08); margin-bottom: 0.75rem;
                                        border-left: 4px solid {dist_color};'>
                                <div style='font-size: 0.85rem; color: #6c757d; margin-bottom: 0.5rem;'>DISTANCE FROM MA200</div>
                                <div style='font-size: 2rem; font-weight: 700; color: {dist_color}; text-align: center;'>{dist_ma200:+.1f}%</div>
                                <div style='font-size: 0.8rem; color: #6c757d; text-align: center;'>
                                    {'Healthy' if -5 <= dist_ma200 <= 20 else 'Stretched' if -15 <= dist_ma200 <= 40 else 'Overextended'}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                            # Overextension Risk Gauge
                            st.markdown("<br>", unsafe_allow_html=True)
                            st.markdown("**Overextension Risk:**")

                            overext_color = '#28a745' if overext_risk < 2 else '#ffc107' if overext_risk < 4 else '#dc3545'
                            overext_norm = overext_risk / 7  # Normalize 0-7 to 0-1

                            st.markdown(f"""
                            <div style='background: {overext_color}; padding: 1.25rem; border-radius: 10px;
                                        text-align: center; color: white; margin-bottom: 1rem;'>
                                <div style='font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem;'>{overext_risk}/7</div>
                                <div style='font-size: 1.2rem; font-weight: 600;'>{overext_level}</div>
                                <div style='font-size: 0.9rem; opacity: 0.9; margin-top: 0.5rem;'>Overextension Level</div>
                            </div>
                            """, unsafe_allow_html=True)
                            st.progress(overext_norm)

                            # Risk interpretation
                            if overext_risk >= 6:
                                st.error("EXTREME: Alto riesgo de corrección 20-40%")
                            elif overext_risk >= 4:
                                st.warning("HIGH: Posible retroceso 10-20%")
                            elif overext_risk >= 2:
                                st.info("MEDIUM: Monitorear reversiones")
                            else:
                                st.success("LOW: Riesgo controlado")

                        st.markdown("---")

                        # ========== MÓDULO 3: LA CALCULADORA DE TAMAÑO ==========
                        st.markdown("""
                        <div style='background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                                    padding: 1.5rem; border-radius: 12px; margin-bottom: 2rem; margin-top: 2rem;'>
                            <h3 style='margin: 0; color: white;'><i class="bi bi-calculator"></i> MÓDULO 3: CALCULADORA DE TAMAÑO</h3>
                            <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem;'>
                                Dual Constraint System: MIN(Quality-Based, Risk-Based)
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                        # Get risk management recommendations
                        risk_mgmt = full_analysis.get('risk_management', {})

                        if risk_mgmt:
                            pos_sizing = risk_mgmt.get('position_sizing', {})
                            if pos_sizing:
                                # Use enhanced display function with dual constraint system
                                display_position_sizing(
                                    pos_sizing,
                                    stop_loss_data=risk_mgmt.get('stop_loss'),
                                    portfolio_size=portfolio_capital,
                                    max_risk_dollars=max_risk_per_trade_dollars
                                )
                            else:
                                st.warning("No position sizing data available")
                        else:
                            st.warning("No risk management data available")

                        # ========== MÓDULO 4: EJECUCIÓN TÁCTICA ==========
                        st.markdown("""
                        <div style='background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
                                    padding: 1.5rem; border-radius: 12px; margin-bottom: 2rem; margin-top: 2rem;'>
                            <h3 style='margin: 0; color: white;'><i class="bi bi-crosshair"></i> MÓDULO 4: EJECUCIÓN TÁCTICA</h3>
                            <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem;'>
                                Stop Loss + Entry Strategy
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                        if risk_mgmt:
                            # Entry Strategy
                            entry_strategy = risk_mgmt.get('entry_strategy', {})
                            if entry_strategy:
                                # Use new state-based entry strategy display
                                display_entry_strategy(entry_strategy)
                            else:
                                st.warning("No entry strategy data available")

                            st.markdown("---")

                            # Stop Loss
                            stop_loss = risk_mgmt.get('stop_loss', {})
                            if stop_loss:
                                # Get current price from full_analysis or stop_loss data
                                current_price = full_analysis.get('current_price', 0)
                                if current_price == 0:
                                    current_price = stop_loss.get('current_price', stock_data.get('price', 0))
                                display_smart_stop_loss(stop_loss, current_price)
                            else:
                                st.warning("No stop loss data available")

                            # Optional: Profit Taking and Options as expandable sections
                            st.markdown("---")

                            with st.expander("Take Profit Strategy", expanded=False):
                                profit_taking = risk_mgmt.get('profit_taking', {})
                                if profit_taking:
                                    # Use professional Take Profit display function
                                    display_take_profit(profit_taking)
                                else:
                                    st.info("No take profit data available")

                            with st.expander("Options Strategies", expanded=False):
                                options_strategies = risk_mgmt.get('options_strategies', [])
                                if options_strategies:
                                    st.markdown(f"**{len(options_strategies)} Recommended Strategies:**")

                                    for i, strategy in enumerate(options_strategies, 1):
                                        st.markdown(f"### {i}. {strategy.get('name', 'Unknown Strategy')}")
                                        
                                        if 'description' in strategy:
                                            st.write(strategy['description'])
                                        
                                        # Show setup
                                        if 'setup' in strategy:
                                            st.success(f"**Setup:** {strategy['setup']}")
                                        
                                        # Show max profit/loss
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            if 'max_profit' in strategy:
                                                st.metric("Max Profit", strategy['max_profit'])
                                        with col2:
                                            if 'max_loss' in strategy:
                                                st.metric("Max Loss", strategy['max_loss'])
                                        
                                        # Show when to use
                                        if 'when_to_use' in strategy:
                                            st.info(f"**When to Use:** {strategy['when_to_use']}")
                                        
                                        # Show risk warning if any
                                        if 'risk' in strategy:
                                            st.warning(f"**Risk:** {strategy['risk']}")
                                        
                                        # Show outcomes for certain strategies
                                        if 'outcome_1' in strategy:
                                            st.write(f"**Outcome 1:** {strategy['outcome_1']}")
                                        if 'outcome_2' in strategy:
                                            st.write(f"**Outcome 2:** {strategy['outcome_2']}")
                                        
                                        # Show evidence
                                        if 'evidence' in strategy:
                                            st.caption(f"Evidence: {strategy['evidence']}")
                                        
                                        # Show additional notes
                                        if 'note' in strategy:
                                            st.info(f"{strategy['note']}")
                                else:
                                    st.info("No specific options strategies recommended for this setup.")
                        else:
                            st.warning("No risk management data available")

                        # ========== SMART MONEY DETECTOR ==========
                        # Check if qualitative data is available
                        qual_data_for_smart_money = None
                        if 'results' in st.session_state:
                            df_results = st.session_state['results']
                            if selected_ticker in df_results['ticker'].values:
                                qual_key = f'qual_{selected_ticker}'
                                if qual_key in st.session_state:
                                    qual_data_for_smart_money = st.session_state[qual_key]

                        # Only show Smart Money section if data is available
                        if qual_data_for_smart_money and 'intrinsic_value' in qual_data_for_smart_money:
                            intrinsic_sm = qual_data_for_smart_money['intrinsic_value']
                            insider_data = intrinsic_sm.get('insider_trading', {})

                            if insider_data and insider_data.get('available', False):
                                # Show header only when data is available
                                st.markdown("""
                                <div style='background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
                                            padding: 1.5rem; border-radius: 12px; margin-bottom: 2rem; margin-top: 2rem;'>
                                    <h3 style='margin: 0; color: white;'><i class="bi bi-cash-stack"></i> SMART MONEY DETECTOR</h3>
                                    <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem;'>
                                        Insiders, Institucionales y Short Interest
                                    </p>
                                </div>
                                """, unsafe_allow_html=True)
                                # Display Smart Money in 3 columns
                                col1, col2, col3 = st.columns(3)

                                with col1:
                                    # INSIDERS
                                    st.markdown("""
                                    <div style='background: white; padding: 1rem; border-radius: 10px;
                                                box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 1rem;'>
                                        <div style='font-size: 0.9rem; color: #6c757d; font-weight: 600; margin-bottom: 0.75rem;'>INSIDERS</div>
                                    </div>
                                    """, unsafe_allow_html=True)

                                    signal = insider_data.get('signal', 'Neutral')
                                    signal_colors = {
                                        'Strong Buy': '#28a745',
                                        'Buy': '#28a745',
                                        'Neutral': '#ffc107',
                                        'Sell': '#dc3545',
                                        'Strong Sell': '#dc3545'
                                    }
                                    signal_color = signal_colors.get(signal, '#6c757d')

                                    buy_count = insider_data.get('buy_count_12m', 0)
                                    sell_count = insider_data.get('sell_count_12m', 0)
                                    exec_buys = insider_data.get('executive_buys', 0)
                                    recent_buys_3m = insider_data.get('recent_buys_3m', 0)

                                    st.markdown(f"""
                                    <div style='background: {signal_color}; padding: 1rem; border-radius: 8px;
                                                text-align: center; color: white; margin-bottom: 0.75rem;'>
                                        <div style='font-size: 1.8rem; font-weight: 700;'>{signal}</div>
                                        <div style='font-size: 0.85rem; opacity: 0.9;'>Insider Signal</div>
                                    </div>
                                    """, unsafe_allow_html=True)

                                    st.metric("Buys (12M)", buy_count, delta=f"{exec_buys} executive")
                                    st.metric("Sells (12M)", sell_count)
                                    st.metric("Recent (3M)", recent_buys_3m)

                                with col2:
                                    # INSTITUTIONAL
                                    st.markdown("""
                                    <div style='background: white; padding: 1rem; border-radius: 10px;
                                                box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 1rem;'>
                                        <div style='font-size: 0.9rem; color: #6c757d; font-weight: 600; margin-bottom: 0.75rem;'>INSTITUCIONALES</div>
                                    </div>
                                    """, unsafe_allow_html=True)

                                    inst_own = insider_data.get('institutional_ownership_pct', None)

                                    if inst_own is not None:
                                        # Determine color based on ownership level
                                        if inst_own >= 70:
                                            inst_color = '#28a745'
                                            inst_status = 'HIGH'
                                        elif inst_own >= 40:
                                            inst_color = '#17a2b8'
                                            inst_status = 'MODERATE'
                                        else:
                                            inst_color = '#ffc107'
                                            inst_status = 'LOW'

                                        st.markdown(f"""
                                        <div style='background: {inst_color}; padding: 1rem; border-radius: 8px;
                                                    text-align: center; color: white; margin-bottom: 0.75rem;'>
                                            <div style='font-size: 2.5rem; font-weight: 700;'>{inst_own:.1f}%</div>
                                            <div style='font-size: 0.85rem; opacity: 0.9;'>{inst_status}</div>
                                        </div>
                                        """, unsafe_allow_html=True)

                                        if inst_own >= 70:
                                            st.success("Strong institutional support")
                                        elif inst_own >= 40:
                                            st.info("Moderate institutional presence")
                                        else:
                                            st.warning("Low institutional ownership")
                                    else:
                                        st.info("Institutional data not available")

                                with col3:
                                    # SHORT INTEREST (placeholder - data may not be available)
                                    st.markdown("""
                                    <div style='background: white; padding: 1rem; border-radius: 10px;
                                                box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 1rem;'>
                                        <div style='font-size: 0.9rem; color: #6c757d; font-weight: 600; margin-bottom: 0.75rem;'>SHORT INTEREST</div>
                                    </div>
                                    """, unsafe_allow_html=True)

                                    # Check if short interest data exists (may not be in current data structure)
                                    short_interest = intrinsic_sm.get('short_interest_pct', None)

                                    if short_interest is not None:
                                        if short_interest > 10:
                                            short_color = '#dc3545'
                                            short_status = 'HIGH'
                                        elif short_interest > 5:
                                            short_color = '#ffc107'
                                            short_status = 'MODERATE'
                                        else:
                                            short_color = '#28a745'
                                            short_status = 'LOW'

                                        st.markdown(f"""
                                        <div style='background: {short_color}; padding: 1rem; border-radius: 8px;
                                                    text-align: center; color: white; margin-bottom: 0.75rem;'>
                                            <div style='font-size: 2.5rem; font-weight: 700;'>{short_interest:.1f}%</div>
                                            <div style='font-size: 0.85rem; opacity: 0.9;'>{short_status}</div>
                                        </div>
                                        """, unsafe_allow_html=True)
                                    else:
                                        st.markdown("""
                                        <div style='background: #6c757d; padding: 1rem; border-radius: 8px;
                                                    text-align: center; color: white; margin-bottom: 0.75rem;'>
                                            <div style='font-size: 1.5rem; font-weight: 600;'>N/A</div>
                                            <div style='font-size: 0.85rem; opacity: 0.9;'>Data not available</div>
                                        </div>
                                        """, unsafe_allow_html=True)
                                        st.caption("Short interest data requires premium API access")

                                st.caption("Smart Money data from Qualitative Analysis (tab 5)")

                        # ========== INSTITUTIONAL HOLDERS ==========
                        st.markdown("---")
                        try:
                            from screener.advanced_ui import render_institutional_holders
                            render_institutional_holders(selected_ticker, fmp)
                        except Exception as e:
                            st.info("Institutional holder data not available")
                            if st.checkbox("Show error details", key=f"inst_error_{selected_ticker}"):
                                st.error(str(e))

                        # ========== EARNINGS CALENDAR ==========
                        st.markdown("---")
                        try:
                            from screener.advanced_ui import render_earnings_calendar_section
                            render_earnings_calendar_section(selected_ticker, fmp)
                        except Exception as e:
                            st.info("Earnings calendar data not available")
                            if st.checkbox("Show error details", key=f"earnings_error_{selected_ticker}"):
                                st.error(str(e))

                        # ========== RESUMEN EJECUTIVO: WARNINGS & DIAGNOSTICS ==========
                        st.markdown("---")
                        st.markdown("""
                        <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                                    padding: 1.5rem; border-radius: 12px; margin-bottom: 1.5rem; margin-top: 2rem;'>
                            <h3 style='margin: 0; color: white;'><i class="bi bi-exclamation-triangle"></i> DIAGNÓSTICO Y ALERTAS</h3>
                            <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem;'>
                                Warnings técnicas y señales de riesgo
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                        # Check for errors first
                        if 'error' in full_analysis:
                            st.markdown("""
                            <div style='background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
                                        padding: 1.5rem; border-radius: 12px; color: white; margin-bottom: 1rem;'>
                                <div style='font-size: 1.3rem; font-weight: 600; margin-bottom: 0.5rem;'>❌ Analysis Error</div>
                                <div style='font-size: 0.95rem; opacity: 0.95;'>{}</div>
                            </div>
                            """.format(full_analysis['error']), unsafe_allow_html=True)
                            st.caption("Common causes: API issues, insufficient historical data (<250 days), or missing API key")

                        warnings = full_analysis.get('warnings', [])
                        if warnings:
                            # Group warnings by severity
                            high_warnings = [w for w in warnings if w.get('type', w.get('severity', 'LOW')) in ['HIGH', 'ERROR']]
                            med_warnings = [w for w in warnings if w.get('type', w.get('severity', 'LOW')) == 'MEDIUM']
                            low_warnings = [w for w in warnings if w.get('type', w.get('severity', 'LOW')) not in ['HIGH', 'ERROR', 'MEDIUM']]

                            # Display in columns by severity
                            if high_warnings:
                                st.markdown("""
                                <div style='margin-bottom: 0.5rem;'>
                                    <span style='font-weight: 600; font-size: 1.05rem;'>
                                        <i class="bi bi-exclamation-circle-fill" style="color: #dc3545;"></i>
                                        Critical Warnings
                                    </span>
                                </div>
                                """, unsafe_allow_html=True)
                                for warning in high_warnings:
                                    message = warning.get('message', '')
                                    st.markdown(f"""
                                    <div style='background: #fff5f5; padding: 1rem; border-radius: 8px;
                                                border-left: 4px solid #dc3545; margin-bottom: 0.75rem;'>
                                        <div style='font-size: 0.95rem; color: #495057;'>{message}</div>
                                    </div>
                                    """, unsafe_allow_html=True)

                            if med_warnings:
                                st.markdown("""
                                <div style='margin-bottom: 0.5rem; margin-top: 1rem;'>
                                    <span style='font-weight: 600; font-size: 1.05rem;'>
                                        <i class="bi bi-exclamation-triangle-fill" style="color: #ffc107;"></i>
                                        Moderate Warnings
                                    </span>
                                </div>
                                """, unsafe_allow_html=True)
                                for warning in med_warnings:
                                    message = warning.get('message', '')
                                    st.markdown(f"""
                                    <div style='background: #fffbf0; padding: 1rem; border-radius: 8px;
                                                border-left: 4px solid #ffc107; margin-bottom: 0.75rem;'>
                                        <div style='font-size: 0.95rem; color: #495057;'>{message}</div>
                                    </div>
                                    """, unsafe_allow_html=True)

                            if low_warnings:
                                with st.expander("Low Priority Info", expanded=False):
                                    for warning in low_warnings:
                                        message = warning.get('message', '')
                                        st.caption(f"• {message}")

                        elif 'error' not in full_analysis:
                            st.markdown("""
                            <div style='background: #d4edda; padding: 1rem; border-radius: 8px;
                                        border-left: 4px solid #28a745; margin-bottom: 1rem;'>
                                <div style='font-size: 0.95rem; color: #155724; font-weight: 600;'>✅ No technical warnings detected</div>
                            </div>
                            """, unsafe_allow_html=True)

                        # ========== RESUMEN EJECUTIVO: RECOMMENDATION ==========
                        st.markdown("---")
                        st.markdown("""
                        <div style='background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                                    padding: 1.5rem; border-radius: 12px; margin-bottom: 1.5rem; margin-top: 2rem;'>
                            <h3 style='margin: 0; color: white;'><i class="bi bi-check2-circle"></i> RECOMENDACIÓN FINAL</h3>
                            <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem;'>
                                Fundamental + Technical + Risk Assessment
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                        fund_score = stock_data['fundamental_score']
                        tech_score = full_analysis['score']
                        overextension_risk = full_analysis.get('overextension_risk', 0)
                        distance_ma200 = full_analysis.get('distance_from_ma200', 0)

                        # ========== KILL SWITCH: STATE MACHINE VETO ==========
                        # CRITICAL: If State Machine detects DOWNTREND, override all recommendations
                        stop_loss_data = full_analysis.get('smart_stop_loss', {})
                        market_state = stop_loss_data.get('market_state', 'UNKNOWN')

                        if market_state == "DOWNTREND":
                            # VETO: Structure is broken - show critical warning FIRST
                            st.error("""
                            ### 🛑 KILL SWITCH: DOWNTREND DETECTED

                            **⛔ State Machine Alert**: Precio < SMA 50 - Estructura rota

                            **ACCIÓN REQUERIDA**:
                            - Si **NO** tienes la acción: **NO COMPRAR** (espera recuperación)
                            - Si **YA** tienes la acción: **SALIR** en próximo rebote

                            **📉 Por qué esto anula los scores históricos**:
                            - Technical Score ({tech_score}/100) mira 12 meses atrás ← PASADO
                            - State Machine mira estructura actual ← PRESENTE
                            - "Una tortuga corriendo cuesta abajo sigue siendo rápida... hasta que se estrella"

                            ** Para re-considerar compra**:
                            - Precio debe recuperar y cerrar arriba de SMA 50
                            - O esperar nuevo breakout confirmado con volumen
                            """)
                            st.caption(f" SMA 50 está en ${full_analysis.get('ma_50', 0):.2f}")

                        elif market_state == "PARABOLIC_CLIMAX":
                            # VETO: Parabolic move - don't buy at the top
                            stop_price = stop_loss_data.get('active_stop', {}).get('price', 0)
                            stop_distance = stop_loss_data.get('active_stop', {}).get('distance_%', 0)

                            st.warning("""
                            ###  VETO DE CLÍMAX: PARABOLIC_CLIMAX DETECTED

                            ** State Machine Alert**: Movimiento vertical - Sobrecompra extrema

                            **ACCIÓN REQUERIDA**:
                            - Si **NO** tienes la acción: **NO COMPRAR** (espera corrección -15% a -25%)
                            - Si **YA** tienes la acción: **ASEGURAR GANANCIAS** (trailing stop o vender parcial)

                            ** Por qué NO comprar en clímax parabólico**:
                            - Technical Score ({tech_score}/100) dice "excelente momentum" ← VERDAD
                            - State Machine dice "movimiento insostenible" ← TAMBIÉN VERDAD
                            - Score alto = "La fiesta fue genial", NO = "La fiesta seguirá siendo genial"

                            ** Evidencia empírica**:
                            - Movimientos parabólicos tienen alta probabilidad de corrección significativa
                            - Momentum crashes research: Daniel & Moskowitz (2016)
                            - Esperar pullback a soportes técnicos mejora punto de entrada

                            ** Para considerar entrada**:
                            - Espera corrección a soporte (MA50, swing low)
                            - O usa stop muy tight ({stop_distance:.1f}%) y acepta alto riesgo de salida
                            - "No compres cohetes en el aire, espéralos en tierra"
                            """)

                            if stop_price > 0:
                                st.caption(f" Si YA tienes posición: Stop Loss de protección en ${stop_price:.2f} ({stop_distance:.1f}%)")

                        else:
                            # Only show recommendations if NO veto is active
                            # Step 1: Fundamental Quality Assessment
                            st.markdown("""
                            <div style='background: linear-gradient(to right, #667eea 0%, #764ba2 100%);
                                        padding: 0.75rem 1rem; border-radius: 8px; margin: 1rem 0 0.75rem 0;'>
                                <div style='color: white; font-size: 1.1rem; font-weight: 600;'><i class="bi bi-bar-chart-line"></i> Fundamental Quality</div>
                            </div>
                            """, unsafe_allow_html=True)
                            if fund_score >= 75:
                                st.success(f" EXCELLENT ({fund_score}/100) - High-quality company with strong fundamentals")
                            elif fund_score >= 60:
                                st.info(f" GOOD ({fund_score}/100) - Solid fundamentals")
                            elif fund_score >= 50:
                                st.warning(f" MODERATE ({fund_score}/100) - Mixed fundamentals")
                            else:
                                st.error(f"WEAK ({fund_score}/100) - Fundamental concerns")

                            # Step 2: Technical Timing Assessment (includes overextension)
                            st.markdown("""
                            <div style='background: linear-gradient(to right, #11998e 0%, #38ef7d 100%);
                                        padding: 0.75rem 1rem; border-radius: 8px; margin: 1rem 0 0.75rem 0;'>
                                <div style='color: white; font-size: 1.1rem; font-weight: 600;'><i class="bi bi-clock-history"></i> Technical Timing</div>
                            </div>
                            """, unsafe_allow_html=True)
                            abs_distance = abs(distance_ma200)
                            is_momentum_leader = tech_score > 80

                            # CRITICAL FIX: Check if Momentum Leader FIRST (overextension is a FEATURE not a BUG)
                            if is_momentum_leader and overextension_risk < 2:
                                # Quality Momentum Leader with low overextension risk (despite high distance)
                                st.success(f" EXCELLENT TIMING ({tech_score}/100) - Quality Momentum Leader with {distance_ma200:+.1f}% from MA200")
                                st.caption(f" Low overextension risk ({overextension_risk}/7). Strong trend can persist. Use Trailing Stop (EMA 20) to protect gains.")
                            elif abs_distance > 60 and not is_momentum_leader:
                                # Extreme overextension (non-leaders only)
                                st.error(f" POOR TIMING - Extreme overextension ({overextension_risk}/7 risk, {distance_ma200:+.1f}% from MA200)")
                                st.caption(" Expect 20-40% pullback. Wait for correction.")
                            elif abs_distance > 50 and not is_momentum_leader:
                                # Severe overextension (non-leaders only)
                                st.error(f" POOR TIMING - Severe overextension ({overextension_risk}/7 risk, {distance_ma200:+.1f}% from MA200)")
                                st.caption(" Expect 15-30% correction. Scale-in recommended (majority capital on pullback).")
                            elif abs_distance > 40 and overextension_risk >= 2:
                                # Significant overextension with moderate risk
                                st.warning(f" CAUTIOUS TIMING - Significant overextension ({overextension_risk}/7 risk, {distance_ma200:+.1f}% from MA200)")
                                st.caption(" Possible 10-20% pullback. Scale-in recommended.")
                            elif overextension_risk >= 3:
                                # Moderate overextension (from other factors like volatility)
                                st.warning(f" CAUTIOUS TIMING - Moderate overextension ({overextension_risk}/7 risk, {distance_ma200:+.1f}% from MA200)")
                                st.caption(" Possible 8-12% consolidation. Consider small reserve.")
                            elif tech_score >= 75:
                                st.success(f" EXCELLENT ({tech_score}/100) - Favorable technical setup, low overextension ({overextension_risk}/7)")
                            elif tech_score >= 60:
                                st.info(f" GOOD ({tech_score}/100) - Decent technical setup")
                            elif tech_score >= 50:
                                st.warning(f" MODERATE ({tech_score}/100) - Mixed technical signals")
                            else:
                                st.error(f"WEAK ({tech_score}/100) - Unfavorable technicals")

                            # Step 3: Final Combined Recommendation
                            st.markdown("""
                            <div style='background: linear-gradient(to right, #f093fb 0%, #f5576c 100%);
                                        padding: 0.75rem 1rem; border-radius: 8px; margin: 1rem 0 0.75rem 0;'>
                                <div style='color: white; font-size: 1.1rem; font-weight: 600;'><i class="bi bi-flag-fill"></i> Final Recommendation</div>
                            </div>
                            """, unsafe_allow_html=True)

                            # STRONG BUY: Great fundamentals + Great timing + Low overextension
                            if fund_score >= 75 and tech_score >= 75 and overextension_risk < 2:
                                st.success("""
                                ** STRONG BUY**: Excellent fundamentals + favorable technical setup + low overextension.
                                Both quality and timing are aligned. Consider building full position.
                                """)

                            # STRONG fundamentals but HIGH overextension - WAIT or SCALE-IN
                            elif fund_score >= 75 and overextension_risk >= 3:
                                # Determine expected pullback range based on distance
                                if abs_distance > 60:
                                    pullback_range = "20-40%"
                                    strategy_desc = "(minimal position now, majority on deep pullback)"
                                elif abs_distance > 50:
                                    pullback_range = "15-30%"
                                    strategy_desc = "(40% now, 60% on pullback)"
                                elif abs_distance > 40:
                                    pullback_range = "10-20%"
                                    strategy_desc = "(60% now, 40% on pullback)"
                                else:
                                    pullback_range = "8-15%"
                                    strategy_desc = "(70% now, 30% on pullback)"

                                st.warning(f"""
                                **⏸️ STRONG COMPANY, WAIT FOR PULLBACK**: Excellent fundamentals but stock is overextended ({distance_ma200:+.1f}% from MA200).
                                **Expected pullback**: {pullback_range}
                                **Action**: Set alerts or use scale-in strategy {strategy_desc}.
                                Consider cash-secured puts to enter at discount.
                                """)

                            # STRONG fundamentals but poor tech score (not due to overextension)
                            elif fund_score >= 75 and tech_score < 50:
                                st.warning("""
                                **⏸️ WAIT**: Great company but poor technical timing.
                                Consider waiting for pullback or better entry point.
                                Set price alerts around MA200 support levels.
                                """)

                            # Good fundamentals + Strong technicals + Moderate overextension
                            elif fund_score >= 60 and tech_score >= 75 and overextension_risk >= 2:
                                st.info("""
                                ** TACTICAL SCALE-IN**: Good fundamentals with strong momentum, but moderate overextension.
                                Use scale-in strategy (e.g., 50% now, 50% on pullback).
                                """)

                            # Good fundamentals + Strong technicals + Low overextension
                            elif fund_score >= 60 and tech_score >= 75 and overextension_risk < 2:
                                st.info("""
                                ** TACTICAL BUY**: Good fundamentals with strong technical momentum and low overextension.
                                May be suitable for shorter-term trade, but monitor fundamentals closely.
                                """)

                            # Both GOOD (60-75 range) - Solid opportunity but not excellent
                            elif fund_score >= 60 and tech_score >= 60:
                                if overextension_risk >= 2:
                                    st.info("""
                                    ** BUY (Scale-in)**: Solid fundamentals and technical setup, but moderate overextension.
                                    Consider scale-in approach (60-70% now, 30-40% on pullback).
                                    """)
                                else:
                                    st.success("""
                                    ** BUY**: Solid fundamentals and favorable technical timing.
                                    Both quality and timing are good. Consider building position (75-100%).
                                    Quality may not be "excellent" but setup is favorable for entry.
                                    """)

                            # Good fundamentals (60+) but moderate technicals (50-60)
                            elif fund_score >= 60 and tech_score >= 50:
                                st.info("""
                                ** CAUTIOUS BUY**: Good fundamentals but moderate technical timing.
                                Consider smaller position (50-60%) or wait for technical improvement.
                                """)

                            # Moderate fundamentals (50-60) but good technicals (60+)
                            elif fund_score >= 50 and tech_score >= 60:
                                st.info("""
                                ** HOLD/TACTICAL**: Moderate fundamentals but favorable technicals.
                                May be suitable for tactical trade with tight stops. Monitor fundamentals closely.
                                Not a long-term core holding due to fundamental quality.
                                """)

                            # Weak on both or other mixed signals
                            else:
                                st.info("""
                                **MONITOR**: Mixed or weak signals. Continue watching for improvement
                                in either fundamentals or technicals before entry.
                                """)

                    else:
                        st.error("No detailed analysis available for this stock.")

                # ========== ADVANCED TOOLS (NEW) ==========
                if selected_ticker and full_analysis:
                    st.markdown("---")
                    st.markdown("""<div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100'); padding: 1.5rem; border-radius: 12px; margin-bottom: 1.5rem;'><h3 style='margin: 0; color: white;'><i class="bi bi-tools"></i> Advanced Risk Management Tools</h3><p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem;'>Herramientas avanzadas basadas en investigación académica</p></div>""", unsafe_allow_html=True)

                    

                    # Import advanced UI components (lazy import)
                    try:
                        from screener.advanced_ui import (
                            render_price_levels_chart,
                            render_overextension_gauge,
                            render_backtesting_section,
                            render_options_calculator,
                            render_market_timing_dashboard,
                            render_portfolio_tracker
                        )

                        # Create tabs for different tools
                        adv_tab1, adv_tab2, adv_tab3, adv_tab4, adv_tab5 = st.tabs([
                            "Visualizations",
                            "Backtesting",
                            "Options",
                            "Market Timing",
                            "Portfolio"
                        ])

                        with adv_tab1:
                            # Header for Visualizations tab
                            st.markdown("""
                            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                        padding: 1.5rem; border-radius: 12px; margin-bottom: 2rem;'>
                                <div style='color: white; text-align: center;'>
                                    <div style='font-size: 2rem; margin-bottom: 0.5rem;'>
                                        <i class="bi bi-graph-up"></i>
                                    </div>
                                    <div style='font-size: 1.5rem; font-weight: 700; margin-bottom: 0.5rem;'>
                                        Technical Visualizations
                                    </div>
                                    <div style='font-size: 0.9rem; opacity: 0.95;'>
                                        Price levels, stop losses & overextension risk analysis
                                    </div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                            col1, col2 = st.columns([2, 1])

                            with col1:
                                # Price Levels Chart with header
                                st.markdown("""
                                <div style='background: linear-gradient(to right, #f8f9fa, #e9ecef);
                                            padding: 1rem; border-radius: 10px; margin-bottom: 1rem;
                                            border-left: 4px solid #28a745;'>
                                    <div style='font-size: 1.1rem; font-weight: 700; color: #495057;'>
                                        <i class="bi bi-bar-chart-line"></i> Price Levels & Risk Management
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)

                                try:
                                    # Get historical data if available
                                    historical_prices = None
                                    try:
                                        from_date = (datetime.now() - timedelta(days=100)).strftime('%Y-%m-%d')
                                        hist_data = fmp.get_historical_prices(selected_ticker, from_date=from_date)
                                        if hist_data and 'historical' in hist_data:
                                            historical_prices = hist_data['historical'][::-1]  # Chronological
                                    except:
                                        pass

                                    render_price_levels_chart(
                                        symbol=selected_ticker,
                                        fmp_client=fmp,
                                        full_analysis=full_analysis,
                                        historical_prices=historical_prices
                                    )
                                except Exception as e:
                                    st.error(f"Error rendering chart: {e}")

                            with col2:
                                # Overextension Gauge with header
                                st.markdown("""
                                <div style='background: linear-gradient(to right, #f8f9fa, #e9ecef);
                                            padding: 1rem; border-radius: 10px; margin-bottom: 1rem;
                                            border-left: 4px solid #dc3545;'>
                                    <div style='font-size: 1.1rem; font-weight: 700; color: #495057;'>
                                        <i class="bi bi-speedometer2"></i> Overextension Risk
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)

                                try:
                                    render_overextension_gauge(full_analysis)
                                except Exception as e:
                                    st.error(f"Error rendering gauge: {e}")

                        with adv_tab2:
                            st.info("""
                            **¿Qué hace?** Analiza 2 años de historial para encontrar todas las veces que este stock
                            estuvo sobreextendido (>40% sobre MA200) y calcula:
                            - Corrección promedio
                            - Días hasta corrección
                            - Win rate de estrategias scale-in vs full entry
                            """)

                            try:
                                render_backtesting_section(selected_ticker, fmp)
                            except Exception as e:
                                st.error(f"Error in backtesting: {e}")

                        with adv_tab3:
                            st.info("""
                            **¿Qué hace?** Calcula métricas exactas para 5 estrategias de opciones:
                            - Covered Call (income generation)
                            - Protective Put (downside protection)
                            - Collar (zero-cost protection)
                            - Cash-Secured Put (entry at discount)
                            - Bull Put Spread (defined risk/reward)

                            Incluye: Premium, Max P&L, Break-even, Annualized Return, Probability, Greeks
                            """)

                            try:
                                render_options_calculator(selected_ticker, fmp, full_analysis)
                            except Exception as e:
                                st.error(f"Error in options calculator: {e}")
                                st.info(" Make sure scipy is installed: `pip install scipy>=1.11.0`")

                        with adv_tab4:
                            st.info("""
                            **¿Qué hace?** Analiza condiciones macro del mercado:
                            - % de stocks overextended (riesgo de corrección)
                            - Breakdown por sector
                            - VIX (fear/greed indicator)
                            - Market breadth
                            - Recomendación: DEFENSIVE/CAUTIOUS/NEUTRAL/BULLISH
                            """)

                            try:
                                # Get top stocks from screening results if available
                                top_stocks = None
                                if 'df_filtered' in locals() and df_filtered is not None and len(df_filtered) > 0:
                                    top_stocks = df_filtered['ticker'].head(20).tolist()

                                render_market_timing_dashboard(fmp, top_stocks)
                            except Exception as e:
                                st.error(f"Error in market timing: {e}")

                        with adv_tab5:
                            st.info("""
                            **¿Qué hace?** Trackea tus posiciones y genera alertas automáticas:
                            - Track entry price, tranches, P&L
                            - Alertas de scale-in opportunities (near MA50/MA200)
                            - Alertas de stop loss triggered
                            - Alertas de profit targets hit
                            - Portfolio summary con total P&L
                            """)

                            try:
                                render_portfolio_tracker(fmp)
                            except Exception as e:
                                st.error(f"Error in portfolio tracker: {e}")

                        # Help section
                        with st.expander("📚 Guía de Uso de Advanced Tools"):
                            st.markdown("""
                            ### Flujo Recomendado

                            1. **Visualizations** 
                               - Revisa el gráfico de price levels para ver dónde están los niveles clave
                               - El gauge muestra el nivel de overextension risk (0-7)

                            2. **Backtesting** 
                               - Valida con datos históricos si correcciones son comunes
                               - Compara performance de full entry vs scale-in

                            3. **Options** 
                               - Calcula estrategia óptima (covered call si overextended, protective put si high risk)
                               - Revisa Greeks para entender sensibilidad

                            4. **Market Timing** 🌡️
                               - Verifica condiciones macro antes de entrar
                               - Si DEFENSIVE (risk 7+), espera mejor momento

                            5. **Portfolio** 💼
                               - Agrega posición para tracking automático
                               - Recibe alertas cuando price hits key levels

                            ### Casos de Uso

                            **Stock Overextendido (ej: +58% sobre MA200)**
                            1. Visualizations → Confirma zona overextension
                            2. Backtesting → Valida que correcciones históricas fueron -25% avg
                            3. Options → Covered call para income mientras esperas pullback
                            4. Market Timing → Si CAUTIOUS/DEFENSIVE, no entres full position
                            5. Portfolio → Scale-in 3 tranches (25% now, 35% @MA50, 40% @MA200)

                            **Stock con Pullback (ej: -15% en 2 semanas)**
                            1. Visualizations → Confirma que salió de zona overextension
                            2. Backtesting → Valida que rebotes desde MA50 son +18% avg
                            3. Options → Cash-secured put para entry at discount
                            4. Market Timing → Si NEUTRAL/BULLISH, OK para agregar
                            5. Portfolio → Add tranche 2 cuando alerta dice "near MA50"

                            ### Documentación Completa

                            Ver `ADVANCED_FEATURES.md` para:
                            - Explicación detallada de cada tool
                            - Ejemplos con NVDA, AAPL
                            - Mejores prácticas
                            - Referencias académicas
                            - Troubleshooting
                            """)

                    except ImportError as e:
                        st.warning(f"""
                         Advanced Tools no disponibles.

                        Error: {e}

                        Para habilitar las Advanced Tools, asegúrate de tener instaladas las dependencias:
                        ```bash
                        pip install scipy>=1.11.0 toml>=0.10.2
                        ```
                        """)
                    except Exception as e:
                        st.error(f"Error loading Advanced Tools: {e}")
                        st.code(traceback.format_exc())

                # Download
                st.markdown("---")
                st.markdown("### 📥 Download Technical Analysis")

                import csv as csv_module
                csv = df_tech.to_csv(index=False, quoting=csv_module.QUOTE_NONNUMERIC).encode('utf-8')
                st.download_button(
                    label="📄 Download Technical Results (CSV)",
                    data=csv,
                    file_name=f"technical_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("UltraQuality v1.0")
st.sidebar.caption("Powered by FMP API")
