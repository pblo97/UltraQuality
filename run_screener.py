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
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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


def generate_positions_excel(df_filtered, portfolio_size=420000):
    """
    Generate Excel file with position sizing, staged entry, stop loss, and take profit details.

    Args:
        df_filtered: DataFrame with filtered technical results
        portfolio_size: Total portfolio size in USD (default $420,000)

    Returns:
        BytesIO buffer with Excel file
    """
    from io import BytesIO

    # Prepare data for Excel
    excel_data = []

    for _, row in df_filtered.iterrows():
        try:
            ticker = row['ticker']
            full_analysis = row.get('full_analysis')

            if not full_analysis:
                continue

            # Extract data from analysis
            current_price = full_analysis.get('current_price', 0)
            risk_mgmt = full_analysis.get('risk_management', {})

            # Position sizing
            pos_sizing = risk_mgmt.get('position_sizing', {})
            recommended_pct = pos_sizing.get('final_pct', 0)
            position_dollars = portfolio_size * (recommended_pct / 100)

            # Convert currency if needed (same logic as UI)
            current_price_usd = current_price
            currency = 'USD'

            # Extract exchange suffix for currency conversion
            exchange_fx_rates = {
                '.KQ': ('KRW', 0.000751), '.KS': ('KRW', 0.000751),
                '.T': ('JPY', 0.00665), '.HK': ('HKD', 0.128),
                '.SS': ('CNY', 0.137), '.SZ': ('CNY', 0.137),
                '.SI': ('SGD', 0.742), '.BK': ('THB', 0.0275),
                '.L': ('GBP', 1.27), '.PA': ('EUR', 1.08),
                '.TO': ('CAD', 0.724), '.AX': ('AUD', 0.664),
            }

            for suffix, (curr, fx_rate) in exchange_fx_rates.items():
                if ticker.endswith(suffix):
                    current_price_usd = current_price * fx_rate
                    currency = curr
                    break

            # Calculate shares
            total_shares = int(position_dollars / current_price_usd) if current_price_usd > 0 else 0

            # Staged entry (60% first, 40% second)
            shares_first_entry = int(total_shares * 0.6)
            shares_second_entry = total_shares - shares_first_entry

            # Entry prices
            price_first_entry = current_price  # Current price for first entry

            # Second entry at support (use MA50 or swing low if available)
            entry_strategy = risk_mgmt.get('entry_strategy', {})
            price_second_entry = current_price * 0.96  # Default 4% lower

            # Try to get actual support level from entry strategy
            support_level = entry_strategy.get('support_level', 0)
            if support_level and support_level > 0:
                price_second_entry = support_level

            # Average purchase price (weighted by shares)
            if total_shares > 0:
                total_cost = (shares_first_entry * price_first_entry) + (shares_second_entry * price_second_entry)
                avg_purchase_price = total_cost / total_shares
            else:
                avg_purchase_price = current_price

            # Stop loss
            stop_loss_data = risk_mgmt.get('stop_loss', {})
            stop_loss_price = stop_loss_data.get('stop_price', 0)
            stop_loss_pct = stop_loss_data.get('stop_loss_pct', 0)

            # If stop_loss_pct is relative to current price, recalculate relative to avg price
            if avg_purchase_price > 0 and stop_loss_price > 0:
                stop_loss_pct_avg = ((stop_loss_price - avg_purchase_price) / avg_purchase_price) * 100
            else:
                stop_loss_pct_avg = stop_loss_pct

            # Take profit
            profit_taking = risk_mgmt.get('profit_taking', {})
            take_profit_price = 0

            # Try to extract first target price
            targets = profit_taking.get('targets', [])
            if targets and len(targets) > 0:
                first_target = targets[0]
                if isinstance(first_target, dict):
                    tp_price_str = first_target.get('price', '0')
                    # Remove $ and , from price string
                    tp_price_str = str(tp_price_str).replace('$', '').replace(',', '')
                    try:
                        take_profit_price = float(tp_price_str)
                    except:
                        take_profit_price = 0

            # Potential loss
            if stop_loss_price > 0 and total_shares > 0:
                potential_loss = (avg_purchase_price - stop_loss_price) * total_shares
            else:
                potential_loss = 0

            # Portfolio loss percentage
            portfolio_loss_pct = (potential_loss / portfolio_size) * 100 if portfolio_size > 0 else 0

            # Earnings date (if available)
            earnings_date = full_analysis.get('next_earnings_date', 'N/A')

            # Append row
            excel_data.append({
                'Stock': ticker,
                'Industria': row.get('sector', 'N/A'),
                'Precio Actual': current_price,
                'Precio Actual USD': current_price_usd if currency != 'USD' else '',
                'Moneda': currency if currency != 'USD' else '',

                'Posición 1ª Entrada (60%)': shares_first_entry,
                'Precio 1ª Entrada': price_first_entry,
                'Costo 1ª Entrada': shares_first_entry * price_first_entry,

                'Posición 2ª Entrada (40%)': shares_second_entry,
                'Precio 2ª Entrada (Soporte)': price_second_entry,
                'Costo 2ª Entrada': shares_second_entry * price_second_entry,

                'Total Shares': total_shares,
                'Precio Medio Compra': avg_purchase_price,
                'Inversión Total': position_dollars,
                '% Portfolio': recommended_pct,

                'Stop Loss': stop_loss_price,
                '% Stop Loss vs Precio Medio': stop_loss_pct_avg,

                'Take Profit': take_profit_price if take_profit_price > 0 else 'N/A',

                'Pérdida Potencial ($)': potential_loss,
                '% Pérdida Cartera': portfolio_loss_pct,

                'Fecha Earnings': earnings_date,

                'Tech Score': row.get('technical_score', 0),
                'Conviction': row.get('conviction', 0),
                'Extension': row.get('extension_state', 'N/A'),
                'Fund Score': row.get('fundamental_score', 0),
                'Fund Decision': row.get('fundamental_decision', 'N/A'),
                'Trend State': row.get('trend_state', 'N/A'),
            })

        except Exception as e:
            # Skip stocks with errors
            continue

    # Create DataFrame
    df_excel = pd.DataFrame(excel_data)

    # Create Excel file in memory
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_excel.to_excel(writer, sheet_name='Posiciones', index=False)

        # Get worksheet to apply formatting
        worksheet = writer.sheets['Posiciones']

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

    output.seek(0)
    return output


def display_smart_stop_loss(stop_loss_data, current_price):
    """
    Display SmartDynamicStopLoss data in Streamlit.

    Args:
        stop_loss_data: Stop loss dict from risk_management
        current_price: Current stock price
    """
    # Check if it's V2 ATR-based format
    if stop_loss_data.get('method') == 'ATR' and 'extension_adjusted' in stop_loss_data:
        # === V2 FORMAT: ATR-Based Stop Loss ===
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 1.5rem; border-radius: 12px; margin-bottom: 1.5rem;'>
            <h3 style='margin: 0; color: white;'><i class="bi bi-shield-check"></i> ATR-Based Stop Loss</h3>
            <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem;'>
                Extension-Adjusted Volatility Stop
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Get data
        stop_price = stop_loss_data.get('stop_price', 0)
        stop_distance_pct = stop_loss_data.get('stop_distance_pct', 0)
        atr_14d_pct = stop_loss_data.get('atr_14d_pct', 0)
        atr_multiplier = stop_loss_data.get('atr_multiplier', 2.5)

        # Calculate risk in dollars
        risk_dollars = current_price - stop_price if current_price > 0 else 0
        risk_pct = (risk_dollars / current_price * 100) if current_price > 0 else 0

        # Main display card
        st.markdown(f"""
        <div style='background: white; padding: 2rem; border-radius: 12px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.1); margin-bottom: 1.5rem;'>
            <div style='display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 2rem; text-align: center;'>
                <div>
                    <div style='font-size: 0.85rem; color: #6c757d; font-weight: 600; margin-bottom: 0.5rem;'>
                        STOP PRICE
                    </div>
                    <div style='font-size: 2.5rem; font-weight: 700; color: #dc3545;'>
                        ${stop_price:.2f}
                    </div>
                    <div style='font-size: 0.8rem; color: #6c757d; margin-top: 0.25rem;'>
                        Entry: ${current_price:.2f}
                    </div>
                </div>
                <div>
                    <div style='font-size: 0.85rem; color: #6c757d; font-weight: 600; margin-bottom: 0.5rem;'>
                        DISTANCE
                    </div>
                    <div style='font-size: 2.5rem; font-weight: 700; color: #495057;'>
                        {stop_distance_pct:.1f}%
                    </div>
                    <div style='font-size: 0.8rem; color: #dc3545; margin-top: 0.25rem; font-weight: 600;'>
                        Risk: ${risk_dollars:.2f}
                    </div>
                </div>
                <div>
                    <div style='font-size: 0.85rem; color: #6c757d; font-weight: 600; margin-bottom: 0.5rem;'>
                        ATR MULTIPLIER
                    </div>
                    <div style='font-size: 2.5rem; font-weight: 700; color: #495057;'>
                        {atr_multiplier:.1f}x
                    </div>
                    <div style='font-size: 0.8rem; color: #6c757d; margin-top: 0.25rem;'>
                        ATR: {atr_14d_pct:.2f}%
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Technical details
        with st.expander("Technical Details"):
            st.markdown(f"""
            **Formula:** Stop Distance = {atr_multiplier}x × ATR(14)

            **Calculation:**
            - ATR (14-day): {atr_14d_pct:.2f}% of price
            - Multiplier: {atr_multiplier}x (extension-adjusted)
            - Stop Distance: {stop_distance_pct:.1f}%
            - Stop Price: ${stop_price:.2f}

            **Extension Adjustment:**
            The ATR multiplier is automatically adjusted based on price extension state:
            - NORMAL/EXTENDED: 2.5x (tight)
            - STRETCHED: 3.0x (moderate air)
            - OVEREXTENDED: 3.5x (max air)

            This ensures stops aren't too tight during volatile periods while maintaining
            discipline during normal conditions.
            """)

    # Check if it's the legacy SmartDynamicStopLoss format
    elif 'tier' in stop_loss_data:
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
                with st.expander("Ver Detalles Críticos"):
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
            status_icon = ""
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
                    slope_dir = "Alcista" if float(slope_val) > 0.05 else "Bajista" if float(slope_val) < -0.05 else "Lateral"
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
        with st.expander("Details by Tranche"):
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
    page_icon="",
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
            <span style='margin-right: 0.5rem;'></span>Global Elite Active
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
                    API Key Active
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

def display_position_sizing(pos_sizing, stop_loss_data=None, portfolio_size=100000, max_risk_dollars=1000, current_price=None, selected_ticker=None, execution_mode='ENTER_NOW'):
    """
    Display enhanced position sizing with DUAL CONSTRAINT system.

    Método A (Risk Budget from conviction): conviction × 10% max allocation
    Método B (Risk-Based from stop): max_risk_dollars / stop_loss_distance

    DECISIÓN FINAL = MIN(A, B)

    Args:
        pos_sizing: Position sizing dict from risk_management
        stop_loss_data: Stop loss dict with 'stop_loss_pct' key
        portfolio_size: Total portfolio size in dollars (default: $100k)
        max_risk_dollars: Maximum $ to risk per trade (default: $1k = 1% of $100k)
        current_price: Current stock price (for share calculation)
        selected_ticker: Ticker symbol (for FX conversion)
    """
    # Modern section header
    st.markdown("""
    <div style='background: linear-gradient(to right, #667eea, #764ba2); padding: 1rem;
                border-radius: 8px; margin-bottom: 1rem;'>
        <h3 style='margin: 0; color: white;'><i class="bi bi-calculator"></i> Position Sizing Calculator</h3>
        <p style='margin: 0.25rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem;'>
            Dual Constraint System: MIN(Risk Budget, Risk-Based Stop)
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Check for VETO
    if pos_sizing.get('veto_active'):
        st.error(f"🛑 **VETO ACTIVE**")
        st.write(f"**Rationale:** {pos_sizing.get('rationale', 'N/A')}")
        st.caption(pos_sizing.get('calculation_breakdown', ''))
        return

    # Get data (V2: different field names)
    # V2 uses position_pct_of_portfolio instead of final_pct
    final_pct = pos_sizing.get('position_pct_of_portfolio', 0)
    base_pct = pos_sizing.get('base_pct', final_pct)  # Fallback to final if no base
    quality_tier = pos_sizing.get('quality_tier', 'CONVICTION-BASED')
    penalties = pos_sizing.get('penalties', [])
    bonuses = pos_sizing.get('bonuses', [])
    bear_market = pos_sizing.get('bear_market_adjustment', False)

    # ========== MÉTODO A: QUALITY-BASED CAP ==========
    # Simple conviction-based cap: higher conviction = larger max allocation
    # Get conviction from pos_sizing (V2 stores it there)
    conviction_scalar = pos_sizing.get('conviction_scalar', 0.5)

    # Quality cap: Scale 0-10% of portfolio based on conviction (0.0 to 1.0)
    # conviction 1.0 → 10%, conviction 0.5 → 5%, conviction 0.0 → 0%
    max_quality_pct = conviction_scalar * 10.0
    quality_based_dollars = portfolio_size * (max_quality_pct / 100)

    # ========== MÉTODO B: RISK-BASED (using stop loss) ==========
    risk_based_dollars = None
    stop_loss_pct = None

    if stop_loss_data:
        # Get stop loss distance as % (positive value, e.g., 5.0 means 5% below current price)
        # V2 uses 'stop_distance_pct' instead of 'stop_loss_pct'
        stop_loss_pct = stop_loss_data.get('stop_distance_pct', stop_loss_data.get('stop_loss_pct'))

        if stop_loss_pct and stop_loss_pct != 0:
            # Convert to positive distance (e.g., -5.0 → 5.0)
            stop_distance = abs(stop_loss_pct)

            # Risk-Based Position Size = Max Risk $ / (Stop Distance / 100)
            # Example: $1,000 / (4% / 100) = $1,000 / 0.04 = $25,000
            risk_based_dollars = max_risk_dollars / (stop_distance / 100)

    # ========== DECISIÓN FINAL: MIN(A, B) with proper N/A handling ==========
    # User requirement: If one is N/A, use the other (don't return $0)
    if quality_based_dollars > 0 and risk_based_dollars is not None and risk_based_dollars > 0:
        # Both exist → take MIN
        final_dollars = min(quality_based_dollars, risk_based_dollars)
        constraint = "Risk Budget (conviction)" if quality_based_dollars < risk_based_dollars else "Risk-Based (stop)"
    elif quality_based_dollars > 0 and risk_based_dollars is None:
        # Only conviction cap exists
        final_dollars = quality_based_dollars
        constraint = "Risk Budget (stop method N/A)"
    elif risk_based_dollars is not None and risk_based_dollars > 0 and quality_based_dollars <= 0:
        # Only risk exists
        final_dollars = risk_based_dollars
        constraint = "Risk-Based (conviction N/A)"
    else:
        # Neither exists or both are 0
        final_dollars = 0
        constraint = "NO EJECUTABLE (insufficient data)"

    final_pct_adjusted = (final_dollars / portfolio_size) * 100 if portfolio_size > 0 else 0

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

    # Display implicit risk (auditable)
    if stop_loss_pct and stop_loss_pct > 0 and final_dollars > 0:
        implicit_risk_dollars = final_dollars * (abs(stop_loss_pct) / 100)
        risk_pct_of_portfolio = (implicit_risk_dollars / portfolio_size) * 100 if portfolio_size > 0 else 0

        st.markdown(f"""
        <div style='background: linear-gradient(to right, #fff5f5, #ffe5e5); padding: 1.25rem;
                    border-radius: 10px; border-left: 5px solid #dc3545; margin-bottom: 1.5rem;'>
            <div style='display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 1rem; align-items: center;'>
                <div>
                    <div style='font-size: 0.8rem; color: #6c757d; margin-bottom: 0.25rem;'>IMPLICIT RISK (Max Loss)</div>
                    <div style='font-size: 1.1rem; color: #495057;'>
                        Position × Stop Distance = <strong style='color: #dc3545;'>${implicit_risk_dollars:,.0f}</strong>
                    </div>
                    <div style='font-size: 0.75rem; color: #6c757d; margin-top: 0.25rem;'>
                        ${final_dollars:,.0f} × {abs(stop_loss_pct):.1f}% = ${implicit_risk_dollars:,.0f}
                    </div>
                </div>
                <div style='text-align: center;'>
                    <div style='font-size: 0.75rem; color: #6c757d;'>% of Portfolio</div>
                    <div style='font-size: 1.8rem; font-weight: 700; color: #dc3545;'>{risk_pct_of_portfolio:.2f}%</div>
                </div>
                <div style='text-align: center;'>
                    <div style='font-size: 0.75rem; color: #6c757d;'>Risk/Reward</div>
                    <div style='font-size: 1.2rem; font-weight: 600; color: #495057;'>1:{(max_risk_dollars / implicit_risk_dollars):.1f}</div>
                </div>
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
            <div style='font-size: 0.85rem; color: #1976d2; font-weight: 600;'>METHOD A: Risk Budget</div>
        </div>
        """, unsafe_allow_html=True)
        quality_pct = (quality_based_dollars / portfolio_size) * 100 if portfolio_size > 0 else 0
        st.metric("Allocation", f"{quality_pct:.1f}%", delta=f"${quality_based_dollars:,.0f}")
        st.caption(f"Risk Budget (conviction {conviction_scalar:.2f}): max {quality_pct:.1f}%")

        # Visual progress bar for quality allocation
        quality_progress = min(quality_pct / 10, 1.0)  # Normalize to 0-1 (assuming max 10%)
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
            st.warning("N/A")
            st.caption("No stop loss data available")

    with col_final:
        st.markdown("""
        <div style='background: #e8f5e9; padding: 1rem; border-radius: 8px;
                    border: 2px solid #4caf50; margin-bottom: 0.5rem;'>
            <div style='font-size: 0.85rem; color: #388e3c; font-weight: 600;'>FINAL (MIN)</div>
        </div>
        """, unsafe_allow_html=True)
        st.metric("Position Size", f"{final_pct_adjusted:.1f}%", delta=f"${final_dollars:,.0f}")

        # Visual progress bar for final allocation
        final_progress = min(final_pct_adjusted / 10, 1.0)
        st.progress(final_progress)

        if constraint.startswith("Risk-Based"):
            st.markdown("""
            <div style='background: linear-gradient(to right, #e3f2fd, #bbdefb);
                        padding: 1rem; border-radius: 8px; border-left: 4px solid #2196f3;'>
                <div style='color: #1565c0; font-weight: 600;'>
                    <i class="bi bi-shield-check"></i> Risk-Based (stop) limit is more conservative
                </div>
            </div>
            """, unsafe_allow_html=True)
        elif constraint.startswith("Risk Budget"):
            st.markdown("""
            <div style='background: linear-gradient(to right, #fff8e1, #ffecb3);
                        padding: 1rem; border-radius: 8px; border-left: 4px solid #ffc107;'>
                <div style='color: #f57c00; font-weight: 600;'>
                    <i class="bi bi-star-fill"></i> Risk Budget (conviction) is more conservative
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

    # Show execution context based on final_action
    if execution_mode == 'ENTER_NOW':
        st.info("✅ **Execution: ENTER NOW** - Sizing shown is actual shares to buy immediately")
    elif execution_mode == 'WAIT_TRIGGER':
        st.warning("⏸️ **Execution: WAIT FOR TRIGGER** - Sizing shown is PLANNED allocation if entry trigger happens")
    else:
        st.error("🛑 **Execution: NO ENTRY** - Do not execute")

    # FIX #9: Currency conversion helper for international stocks
    def convert_to_usd(price_local: float, ticker: str) -> tuple:
        """
        Convert local currency price to USD based on exchange suffix.

        Returns: (price_usd, currency_code, fx_rate)
        """
        # Exchange suffix to currency mapping (approximate FX rates as of 2024)
        # TODO: Fetch live FX rates from API for production
        exchange_fx_rates = {
            # Asia
            '.KS': ('KRW', 0.000751),  # Korea Stock Exchange (Seoul) - 1 KRW ≈ $0.000751
            '.KQ': ('KRW', 0.000751),  # KOSDAQ (Korea)
            '.T': ('JPY', 0.00665),    # Tokyo Stock Exchange - 1 JPY ≈ $0.00665
            '.HK': ('HKD', 0.128),     # Hong Kong - 1 HKD ≈ $0.128
            '.SS': ('CNY', 0.137),     # Shanghai - 1 CNY ≈ $0.137
            '.SZ': ('CNY', 0.137),     # Shenzhen - 1 CNY ≈ $0.137
            '.SI': ('SGD', 0.742),     # Singapore - 1 SGD ≈ $0.742
            '.BK': ('THB', 0.0275),    # Thailand - 1 THB ≈ $0.0275
            '.JK': ('IDR', 0.0000615), # Jakarta - 1 IDR ≈ $0.0000615

            # Europe
            '.L': ('GBP', 1.27),       # London - 1 GBP ≈ $1.27
            '.PA': ('EUR', 1.08),      # Paris - 1 EUR ≈ $1.08
            '.DE': ('EUR', 1.08),      # Germany - 1 EUR ≈ $1.08
            '.MI': ('EUR', 1.08),      # Milan - 1 EUR ≈ $1.08
            '.MC': ('EUR', 1.08),      # Madrid - 1 EUR ≈ $1.08
            '.AS': ('EUR', 1.08),      # Amsterdam - 1 EUR ≈ $1.08
            '.SW': ('CHF', 1.13),      # Switzerland - 1 CHF ≈ $1.13
            '.ST': ('SEK', 0.0919),    # Stockholm - 1 SEK ≈ $0.0919
            '.OL': ('NOK', 0.0911),    # Oslo - 1 NOK ≈ $0.0911
            '.CO': ('DKK', 0.145),     # Copenhagen - 1 DKK ≈ $0.145

            # Americas (non-USD)
            '.TO': ('CAD', 0.724),     # Toronto - 1 CAD ≈ $0.724
            '.V': ('CAD', 0.724),      # TSX Venture (Canada)
            '.MX': ('MXN', 0.0499),    # Mexico - 1 MXN ≈ $0.0499
            '.SA': ('BRL', 0.168),     # Brazil - 1 BRL ≈ $0.168

            # Oceania
            '.AX': ('AUD', 0.664),     # Australia - 1 AUD ≈ $0.664
            '.NZ': ('NZD', 0.606),     # New Zealand - 1 NZD ≈ $0.606

            # Middle East/Africa
            '.SAU': ('SAR', 0.267),    # Saudi Arabia - 1 SAR ≈ $0.267
            '.TA': ('ILS', 0.271),     # Tel Aviv - 1 ILS ≈ $0.271
        }

        # Extract exchange suffix
        for suffix, (currency, fx_rate) in exchange_fx_rates.items():
            if ticker.endswith(suffix):
                price_usd = price_local * fx_rate
                return (price_usd, currency, fx_rate)

        # Default: assume USD (NYSE, NASDAQ, etc.)
        return (price_local, 'USD', 1.0)

    # Calculate shares using current_price parameter or fallback to stop_loss_data
    # V2: current_price is passed as parameter from metadata
    current_price_local = current_price or (stop_loss_data.get('current_price', 0) if stop_loss_data else 0)

    if current_price_local and current_price_local > 0:
        # FIX #9: Convert to USD if international stock
        current_price_usd, currency, fx_rate = convert_to_usd(current_price_local, selected_ticker or '')

        # Calculate shares using USD price
        shares = int(final_dollars / current_price_usd)
        actual_cost_usd = shares * current_price_usd

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
                    <div style='font-size: 1.8rem; font-weight: 600; color: #495057;'>${current_price_usd:.2f}</div>
                    <div style='font-size: 0.75rem; color: #6c757d; margin-top: 0.25rem;'>{current_price_local:,.2f} {currency}</div>
                </div>
                <div>
                    <div style='font-size: 0.8rem; color: #6c757d;'>TOTAL INVESTMENT</div>
                    <div style='font-size: 1.8rem; font-weight: 600; color: #667eea;'>${actual_cost_usd:,.0f}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Currency conversion notice (if not USD)
        if currency != 'USD':
            st.caption(f"💱 FX Rate: 1 {currency} ≈ ${fx_rate:.6f} USD (approximate)")

        # Note about entry price
        st.caption(f"📊 Latest close (${current_price_usd:.2f}) used as entry reference")

        # Trading fee estimate (use USD cost)
        estimated_fee = actual_cost_usd * 0.001  # 0.1% typical commission
        st.caption(f"Estimated trading fees: ${estimated_fee:.2f} (0.1% assumption)")
    else:
        # Fallback if no price available
        st.info(f"💡 Use recommended dollar amount: **${final_dollars:,.0f}** (price data unavailable for share calculation)")

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
    with st.expander("Detailed Calculation Breakdown", expanded=False):
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
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs(["Home", "Results", "Analytics", "Calibration", "Qualitative", "Valuation Dashboard", "Complete Analysis", "Technical", "About"])

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
                Screening Results Overview
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
    with st.expander("Screening Methodology - How It Works", expanded=False):
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
            st.error(f"Error: {str(e)}")
            st.exception(e)
            progress_bar.empty()
            status_text.empty()

with tab2:
    st.markdown("""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 1.5rem;'>
        <h3 style='margin: 0; color: white; font-weight: 600;'>
            Screening Results
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
                        with st.expander("View All Metrics"):
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
                    st.warning(f"No results found for: {ticker}")
                    st.info("Tip: Make sure the ticker exists in the screener results above.")

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

                st.markdown("---")

                # Composite Score Tiers (Only viable candidates >60)
                st.subheader("Quality Tiers - Viable Candidates (Composite Score > 60)")

                # Filter only viable candidates (score > 60)
                viable = df[df['composite_0_100'] > 60].copy()

                if len(viable) >= 3:  # Need at least 3 stocks to create tiers
                    # Calculate percentiles on the viable subset
                    p33 = viable['composite_0_100'].quantile(0.33)
                    p67 = viable['composite_0_100'].quantile(0.67)

                    # Assign tier based on percentiles
                    def assign_tier(score):
                        if score >= p67:
                            return 'Top Tier (Elite)'
                        elif score >= p33:
                            return 'Mid Tier (Good)'
                        else:
                            return 'Lower Tier (Marginal)'

                    viable['tier'] = viable['composite_0_100'].apply(assign_tier)

                    # Count by tier
                    tier_counts = viable['tier'].value_counts()

                    # Create bar chart with color coding
                    tier_order = ['Top Tier (Elite)', 'Mid Tier (Good)', 'Lower Tier (Marginal)']
                    tier_colors = ['#10b981', '#f59e0b', '#ef4444']  # Green, Yellow, Red

                    # Ensure all tiers are present (fill with 0 if missing)
                    tier_data = []
                    color_data = []
                    for tier, color in zip(tier_order, tier_colors):
                        tier_data.append(tier_counts.get(tier, 0))
                        color_data.append(color)

                    col1, col2 = st.columns([2, 1])

                    with col1:
                        fig = go.Figure(data=[go.Bar(
                            x=tier_order,
                            y=tier_data,
                            marker_color=color_data,
                            text=tier_data,
                            textposition='outside',
                            texttemplate='<b>%{text}</b>'
                        )])

                        fig.update_layout(
                            title=f"Quality Distribution (n={len(viable)} stocks with score >60)",
                            xaxis_title="Tier",
                            yaxis_title="Number of Stocks",
                            height=400,
                            showlegend=False
                        )

                        st.plotly_chart(fig, use_container_width=True)

                    with col2:
                        st.markdown("**Tier Definitions:**")
                        st.markdown(f"""
                        - **Top Tier (Elite):** Score ≥ {p67:.1f} (top 33%)
                        - **Mid Tier (Good):** Score {p33:.1f} - {p67:.1f} (middle 33%)
                        - **Lower Tier (Marginal):** Score 60 - {p33:.1f} (bottom 33%)
                        """)

                        st.markdown("---")

                        st.markdown("**Interpretation:**")
                        st.caption("""
                        This analysis focuses on **viable candidates only** (score >60).
                        Green = Best opportunities within viable set.
                        Yellow = Solid companies worth monitoring.
                        Red = Borderline candidates, need deeper review.
                        """)

                        # Show average scores by tier
                        tier_avg = viable.groupby('tier')['composite_0_100'].mean().round(1)
                        st.markdown("**Average Scores:**")
                        for tier in tier_order:
                            if tier in tier_avg.index:
                                st.caption(f"{tier}: {tier_avg[tier]:.1f}")

                    # Optional: Show top stocks in each tier
                    st.markdown("---")
                    st.markdown("**Top Stocks by Tier:**")

                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.markdown("**Top Tier**")
                        top_tier = viable[viable['tier'] == 'Top Tier (Elite)'].nlargest(5, 'composite_0_100')[['ticker', 'composite_0_100', 'decision']]
                        if len(top_tier) > 0:
                            st.dataframe(top_tier, use_container_width=True, hide_index=True)
                        else:
                            st.caption("No stocks in this tier")

                    with col2:
                        st.markdown("**Mid Tier**")
                        mid_tier = viable[viable['tier'] == 'Mid Tier (Good)'].nlargest(5, 'composite_0_100')[['ticker', 'composite_0_100', 'decision']]
                        if len(mid_tier) > 0:
                            st.dataframe(mid_tier, use_container_width=True, hide_index=True)
                        else:
                            st.caption("No stocks in this tier")

                    with col3:
                        st.markdown("**Lower Tier**")
                        lower_tier = viable[viable['tier'] == 'Lower Tier (Marginal)'].nlargest(5, 'composite_0_100')[['ticker', 'composite_0_100', 'decision']]
                        if len(lower_tier) > 0:
                            st.dataframe(lower_tier, use_container_width=True, hide_index=True)
                        else:
                            st.caption("No stocks in this tier")

                else:
                    st.info(f" Only {len(viable)} stocks with composite score > 60. Need at least 3 for tier analysis.")
                    st.caption("Try lowering filters or expanding the universe to get more viable candidates.")

            except Exception as e:
                st.error(f"Error generating analytics: {str(e)}")
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
            st.error(f"Error loading analysis tool: {str(e)}")
            st.info("Make sure analyze_guardrails.py is in the project directory")
        except Exception as e:
            st.error(f"Error during analysis: {str(e)}")

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
                                st.error(f"Analysis failed: {analysis.get('error', 'Unknown error')}")

                        except Exception as e:
                            st.error(f"Error: {str(e)}")
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

                    # ============================================================
                    # BUSINESS OVERVIEW
                    # ============================================================
                    st.markdown("""
                    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 1rem;'>
                        <div style='display: flex; align-items: center; gap: 0.75rem;'>
                            <span style='background: rgba(255,255,255,0.2); padding: 0.35rem 0.75rem; border-radius: 4px; font-size: 0.7rem; font-weight: 700; color: white; letter-spacing: 0.5px;'>
                                SECTION 1
                            </span>
                            <h3 style='margin: 0; color: white; font-weight: 600;'>
                                Business Overview
                            </h3>
                        </div>
                        <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem; padding-left: 0.5rem;'>
                            Core business model and operations
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

                    st.write(analysis.get('business_summary', 'Not available'))

                    st.markdown("---")

                    # ============================================================
                    # COMPETITIVE ADVANTAGES & RISKS
                    # ============================================================
                    st.markdown("""
                    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 1rem;'>
                        <div style='display: flex; align-items: center; gap: 0.75rem;'>
                            <span style='background: rgba(255,255,255,0.2); padding: 0.35rem 0.75rem; border-radius: 4px; font-size: 0.7rem; font-weight: 700; color: white; letter-spacing: 0.5px;'>
                                SECTION 2
                            </span>
                            <h3 style='margin: 0; color: white; font-weight: 600;'>
                                Competitive Position
                            </h3>
                        </div>
                        <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem; padding-left: 0.5rem;'>
                            Sustainable competitive advantages and key business risks
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

                    # Parse and display moats/risks in a cleaner format
                    col1, col2 = st.columns([1, 1])

                    with col1:
                        st.markdown("""
                        <div style='margin-bottom: 1rem;'>
                            <span style='background: #10b981; color: white; padding: 0.25rem 0.75rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; letter-spacing: 0.5px;'>
                                COMPETITIVE MOATS
                            </span>
                        </div>
                        """, unsafe_allow_html=True)

                        # Initialize counters
                        moat_count = 0
                        risk_count = 0

                        moats = analysis.get('moats', [])
                        if moats:
                            import re

                            for moat in moats:
                                # Clean formatting and emojis
                                moat_clean = moat.strip()
                                # Remove emojis
                                moat_clean = re.sub(r'[💪🔒🏆⭐📱🌐💡🎯]', '', moat_clean)
                                # Remove markdown bold markers
                                moat_clean = re.sub(r'\*\*', '', moat_clean)
                                moat_clean = re.sub(r'^[\s]+', '', moat_clean)

                                # Skip metadata lines (not actual moats)
                                if any(skip_text in moat_clean.lower() for skip_text in [
                                    'analysis confidence',
                                    'moats identified',
                                    'confidence:',
                                ]):
                                    continue

                                # Parse format: "Name: Description (Evidence)"
                                match = re.match(r'([^:]+):\s*([^(]+)(?:\(([^)]+)\))?', moat_clean)

                                if match:
                                    moat_name = match.group(1).strip()
                                    moat_desc = match.group(2).strip()
                                    moat_evidence = match.group(3).strip() if match.group(3) else "Unknown"

                                    # Skip if "Not evident" in description OR evidence
                                    if "not evident" in moat_desc.lower() or "not evident" in moat_evidence.lower():
                                        continue

                                    # Skip if it's actually metadata disguised as moat
                                    if any(metadata in moat_name.lower() for metadata in ['confidence', 'identified']):
                                        continue

                                    moat_count += 1

                                    # Determine badge color based on evidence
                                    if "strong" in moat_evidence.lower():
                                        badge_color = "#10b981"
                                        badge_text = "STRONG"
                                    elif "probable" in moat_evidence.lower() or "moderate" in moat_evidence.lower():
                                        badge_color = "#3b82f6"
                                        badge_text = "MODERATE"
                                    else:
                                        badge_color = "#6b7280"
                                        badge_text = "WEAK"

                                    st.markdown(f"""
                                    <div style='background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%);
                                                padding: 1.25rem; border-radius: 10px; margin-bottom: 0.75rem;
                                                border-left: 4px solid {badge_color}; box-shadow: 0 2px 4px rgba(0,0,0,0.08);'>
                                        <div style='display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.75rem;'>
                                            <div style='font-weight: 600; color: #0f172a; font-size: 1rem;'>{moat_name}</div>
                                            <span style='background: {badge_color}; color: white; padding: 0.25rem 0.65rem;
                                                         border-radius: 4px; font-size: 0.7rem; font-weight: 700;
                                                         letter-spacing: 0.5px; white-space: nowrap;'>{badge_text}</span>
                                        </div>
                                        <div style='color: #475569; font-size: 0.9rem; line-height: 1.6;'>{moat_desc}</div>
                                    </div>
                                    """, unsafe_allow_html=True)
                                else:
                                    # Fallback for unparsed moats
                                    if moat_clean and "not evident" not in moat_clean.lower():
                                        moat_count += 1
                                        st.markdown(f"""
                                        <div style='background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%);
                                                    padding: 1.25rem; border-radius: 10px; margin-bottom: 0.75rem;
                                                    border-left: 4px solid #3b82f6; box-shadow: 0 2px 4px rgba(0,0,0,0.08);'>
                                            <div style='color: #0f172a; font-size: 0.9rem; line-height: 1.6; font-weight: 500;'>{moat_clean}</div>
                                        </div>
                                        """, unsafe_allow_html=True)

                            if moat_count == 0:
                                st.info("No clear moats identified")
                        else:
                            st.info("No clear moats identified")

                    with col2:
                        st.markdown("""
                        <div style='margin-bottom: 1rem;'>
                            <span style='background: #f59e0b; color: white; padding: 0.25rem 0.75rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; letter-spacing: 0.5px;'>
                                KEY RISKS
                            </span>
                        </div>
                        """, unsafe_allow_html=True)

                        risks = analysis.get('risks', [])
                        if risks:
                            import re

                            for risk in risks:
                                # Clean formatting and emojis
                                risk_clean = risk.strip()
                                # Remove emojis
                                risk_clean = re.sub(r'[⚠️🚨❗🔴⛔💀🔥📉❌]', '', risk_clean)
                                # Remove markdown bold markers
                                risk_clean = re.sub(r'\*\*', '', risk_clean)
                                risk_clean = risk_clean.strip()

                                # Filter out invalid risks (conference call transcripts, etc.)
                                if any(skip_word in risk_clean.lower() for skip_word in ['operator:', 'welcome everyone', 'thank you for standing', 'good afternoon', 'good morning']):
                                    continue

                                # Parse severity if present
                                severity_match = re.match(r'(Med|High|Low)\s+Severity:\s*(.+)', risk_clean, re.IGNORECASE)

                                if severity_match:
                                    severity = severity_match.group(1).strip()
                                    risk_desc = severity_match.group(2).strip()

                                    # Determine badge color
                                    if severity.lower() == 'high':
                                        badge_color = "#ef4444"
                                        badge_text = "HIGH"
                                    elif severity.lower() == 'med':
                                        badge_color = "#f59e0b"
                                        badge_text = "MEDIUM"
                                    else:
                                        badge_color = "#3b82f6"
                                        badge_text = "LOW"

                                    risk_count += 1
                                    st.markdown(f"""
                                    <div style='background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%);
                                                padding: 1.25rem; border-radius: 10px; margin-bottom: 0.75rem;
                                                border-left: 4px solid {badge_color}; box-shadow: 0 2px 4px rgba(0,0,0,0.08);'>
                                        <div style='margin-bottom: 0.75rem;'>
                                            <span style='background: {badge_color}; color: white; padding: 0.25rem 0.65rem;
                                                         border-radius: 4px; font-size: 0.7rem; font-weight: 700;
                                                         letter-spacing: 0.5px;'>{badge_text} RISK</span>
                                        </div>
                                        <div style='color: #475569; font-size: 0.9rem; line-height: 1.6;'>{risk_desc}</div>
                                    </div>
                                    """, unsafe_allow_html=True)
                                else:
                                    # Risk without severity
                                    if risk_clean and len(risk_clean) > 10:  # Filter very short/empty
                                        risk_count += 1
                                        st.markdown(f"""
                                        <div style='background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%);
                                                    padding: 1.25rem; border-radius: 10px; margin-bottom: 0.75rem;
                                                    border-left: 4px solid #f59e0b; box-shadow: 0 2px 4px rgba(0,0,0,0.08);'>
                                            <div style='color: #0f172a; font-size: 0.9rem; line-height: 1.6; font-weight: 500;'>{risk_clean}</div>
                                        </div>
                                        """, unsafe_allow_html=True)

                            if risk_count == 0:
                                st.info("No major risks identified")
                        else:
                            st.info("No major risks identified")

                    # Clean summary row - only count valid moats/risks
                    if moats or risks:
                        st.markdown(f"""
                        <div style='background: #f8fafc; padding: 0.75rem 1.25rem; border-radius: 8px; margin-top: 1rem; border: 1px solid #e2e8f0;'>
                            <div style='display: flex; justify-content: center; align-items: center; gap: 2rem;'>
                                <div style='text-align: center;'>
                                    <div style='font-size: 1.5rem; font-weight: 700; color: #10b981;'>{moat_count}</div>
                                    <div style='font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px;'>Moats</div>
                                </div>
                                <div style='height: 30px; width: 1px; background: #cbd5e1;'></div>
                                <div style='text-align: center;'>
                                    <div style='font-size: 1.5rem; font-weight: 700; color: #f59e0b;'>{risk_count}</div>
                                    <div style='font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px;'>Risks</div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    st.markdown("---")

                    # ============================================================
                    # INSIDER ACTIVITY & OWNERSHIP
                    # ============================================================
                    st.markdown("""
                    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 1rem;'>
                        <div style='display: flex; align-items: center; gap: 0.75rem;'>
                            <span style='background: rgba(255,255,255,0.2); padding: 0.35rem 0.75rem; border-radius: 4px; font-size: 0.7rem; font-weight: 700; color: white; letter-spacing: 0.5px;'>
                                SECTION 3
                            </span>
                            <h3 style='margin: 0; color: white; font-weight: 600;'>
                                Ownership & Insider Activity
                            </h3>
                        </div>
                        <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem; padding-left: 0.5rem;'>
                            Smart money signals - insider ownership, institutional holdings, and share buybacks
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

                    insider = analysis.get('insider_trading', {})

                    if insider:
                        # ============================================================
                        # SUBSECTION: Insider Trading Activity (Last 12 Months)
                        # ============================================================
                        st.markdown("""
                        <div style='background: #f8fafc; padding: 1rem; border-left: 4px solid #667eea; margin-bottom: 1rem;'>
                            <h4 style='margin: 0 0 0.5rem 0; color: #1e293b; font-weight: 600;'>
                                Insider Trading Activity (Last 12 Months)
                            </h4>
                            <p style='margin: 0; color: #64748b; font-size: 0.85rem;'>
                                Compras vs ventas de ejecutivos y directores
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                        # Get insider trading data
                        buys = insider.get('insider_transactions', {}).get('buys', 0)
                        sells = insider.get('insider_transactions', {}).get('sells', 0)
                        trend = insider.get('insider_trend_90d', 'none')

                        # Display in columns
                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.markdown(f"""
                            <div style='background: white; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;'>
                                <div style='font-size: 2rem; font-weight: 700; color: #10b981; margin-bottom: 0.25rem;'>
                                    {buys}
                                </div>
                                <div style='font-size: 0.85rem; color: #64748b; font-weight: 600;'>
                                    COMPRAS
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        with col2:
                            st.markdown(f"""
                            <div style='background: white; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;'>
                                <div style='font-size: 2rem; font-weight: 700; color: #ef4444; margin-bottom: 0.25rem;'>
                                    {sells}
                                </div>
                                <div style='font-size: 0.85rem; color: #64748b; font-weight: 600;'>
                                    VENTAS
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        with col3:
                            # Calculate net balance
                            net_balance = buys - sells
                            if net_balance > 0:
                                balance_color = '#10b981'
                                balance_text = 'NET COMPRA'
                                balance_badge = f'+{net_balance}'
                            elif net_balance < 0:
                                balance_color = '#ef4444'
                                balance_text = 'NET VENTA'
                                balance_badge = f'{net_balance}'
                            else:
                                balance_color = '#6b7280'
                                balance_text = 'NEUTRAL'
                                balance_badge = '0'

                            st.markdown(f"""
                            <div style='background: white; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;'>
                                <div style='font-size: 2rem; font-weight: 700; color: {balance_color}; margin-bottom: 0.25rem;'>
                                    {balance_badge}
                                </div>
                                <div style='font-size: 0.85rem; color: #64748b; font-weight: 600;'>
                                    {balance_text}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        # Interpretation
                        if net_balance > 3:
                            st.success(f"Señal positiva: Los insiders están comprando más que vendiendo. Posible confianza en el futuro de la empresa.")
                        elif net_balance < -3:
                            st.warning(f"Señal de precaución: Los insiders están vendiendo más que comprando. Puede indicar preocupaciones o simplemente toma de ganancias.")
                        else:
                            st.info(f"Neutral: Actividad de insider trading balanceada o mínima.")

                        st.markdown("---")

                        # ============================================================
                        # SUBSECTION: Institutional Holdings Balance
                        # ============================================================
                        st.markdown("""
                        <div style='background: #f8fafc; padding: 1rem; border-left: 4px solid #764ba2; margin-bottom: 1rem;'>
                            <h4 style='margin: 0 0 0.5rem 0; color: #1e293b; font-weight: 600;'>
                                Institutional Holdings Balance
                            </h4>
                            <p style='margin: 0; color: #64748b; font-size: 0.85rem;'>
                                Balance de compra/venta de fondos e instituciones
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                        # Try to get institutional ownership from FMP
                        try:
                            # Initialize FMP client to fetch institutional data
                            fmp_client = None
                            if 'fmp_client' in st.session_state:
                                fmp_client = st.session_state['fmp_client']
                            else:
                                # Create FMP client on the fly
                                try:
                                    from screener.ingest import FMPClient
                                    import yaml

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
                                except:
                                    pass  # Will show error message below

                            if fmp_client:
                                institutional_holders = fmp_client.get_institutional_holders(selected_ticker)

                                if institutional_holders and len(institutional_holders) > 0:
                                    # Calculate total institutional ownership
                                    total_inst_shares = sum(h.get('shares', 0) for h in institutional_holders)

                                    # Get shares outstanding from df
                                    shares_out = None
                                    if 'results' in st.session_state:
                                        df_results = st.session_state['results']
                                        ticker_row = df_results[df_results['ticker'] == selected_ticker]
                                        if not ticker_row.empty and 'shares_outstanding' in ticker_row.columns:
                                            shares_out = ticker_row['shares_outstanding'].iloc[0]

                                    # Display institutional ownership percentage
                                    if shares_out and shares_out > 0:
                                        inst_own_pct = (total_inst_shares / shares_out) * 100

                                        st.markdown(f"""
                                        <div style='background: white; padding: 1.5rem; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 1rem;'>
                                            <div style='text-align: center;'>
                                                <div style='font-size: 3rem; font-weight: 700; color: #667eea; margin-bottom: 0.5rem;'>
                                                    {inst_own_pct:.1f}%
                                                </div>
                                                <div style='font-size: 1rem; color: #64748b; font-weight: 600;'>
                                                    INSTITUTIONAL OWNERSHIP
                                                </div>
                                            </div>
                                        </div>
                                        """, unsafe_allow_html=True)

                                    # Show top 15 institutional holders
                                    st.caption(f"**Top 15 Institutional Holders** (Total: {len(institutional_holders)} instituciones)")

                                    # Sort by shares held
                                    top_holders = sorted(institutional_holders, key=lambda x: x.get('shares', 0), reverse=True)[:15]

                                    for i, holder in enumerate(top_holders, 1):
                                        holder_name = holder.get('holder', 'Unknown')
                                        shares = holder.get('shares', 0)
                                        date = holder.get('dateReported', 'N/A')
                                        change = holder.get('change', 0)

                                        # Calculate percentage ownership if we have shares_out
                                        if shares_out and shares_out > 0:
                                            holder_pct = (shares / shares_out) * 100
                                            shares_text = f"{shares:,} ({holder_pct:.2f}%)"
                                        else:
                                            shares_text = f"{shares:,}"

                                        # Determine change badge
                                        if change > 0:
                                            change_badge = f'<span style="background: #10b981; color: white; padding: 0.15rem 0.4rem; border-radius: 3px; font-size: 0.7rem; font-weight: 700;">+{change:,}</span>'
                                        elif change < 0:
                                            change_badge = f'<span style="background: #ef4444; color: white; padding: 0.15rem 0.4rem; border-radius: 3px; font-size: 0.7rem; font-weight: 700;">{change:,}</span>'
                                        else:
                                            change_badge = f'<span style="background: #6b7280; color: white; padding: 0.15rem 0.4rem; border-radius: 3px; font-size: 0.7rem; font-weight: 700;">SIN CAMBIO</span>'

                                        st.markdown(f"""
                                        <div style='background: #f8fafc; padding: 0.75rem 1rem; border-radius: 6px; margin-bottom: 0.5rem; border-left: 3px solid #667eea;'>
                                            <div style='display: flex; justify-content: space-between; align-items: center;'>
                                                <div style='flex: 1;'>
                                                    <div style='font-weight: 600; color: #1e293b; font-size: 0.9rem;'>
                                                        {i}. {holder_name}
                                                    </div>
                                                    <div style='color: #64748b; font-size: 0.8rem; margin-top: 0.25rem;'>
                                                        {shares_text} • Reported: {date}
                                                    </div>
                                                </div>
                                                <div style='margin-left: 1rem;'>
                                                    {change_badge}
                                                </div>
                                            </div>
                                        </div>
                                        """, unsafe_allow_html=True)

                                    # Overall institutional balance interpretation
                                    total_change = sum(h.get('change', 0) for h in institutional_holders)
                                    buying_count = sum(1 for h in institutional_holders if h.get('change', 0) > 0)
                                    selling_count = sum(1 for h in institutional_holders if h.get('change', 0) < 0)

                                    # Debug: Show if we have change data
                                    changes_available = any(h.get('change') is not None for h in institutional_holders)

                                    if changes_available:
                                        st.markdown("---")
                                        st.markdown("**Balance de Compra/Venta Institucional**")

                                        col_buy, col_sell, col_net = st.columns(3)

                                        with col_buy:
                                            st.markdown(f"""
                                            <div style='text-align: center; padding: 0.75rem;'>
                                                <div style='font-size: 1.5rem; font-weight: 700; color: #10b981;'>
                                                    {buying_count}
                                                </div>
                                                <div style='font-size: 0.8rem; color: #64748b;'>
                                                    COMPRANDO
                                                </div>
                                            </div>
                                            """, unsafe_allow_html=True)

                                        with col_sell:
                                            st.markdown(f"""
                                            <div style='text-align: center; padding: 0.75rem;'>
                                                <div style='font-size: 1.5rem; font-weight: 700; color: #ef4444;'>
                                                    {selling_count}
                                                </div>
                                                <div style='font-size: 0.8rem; color: #64748b;'>
                                                    VENDIENDO
                                                </div>
                                            </div>
                                            """, unsafe_allow_html=True)

                                        with col_net:
                                            net_inst_balance = buying_count - selling_count
                                            if net_inst_balance > 0:
                                                net_color = '#10b981'
                                                net_text = 'NET COMPRA'
                                            elif net_inst_balance < 0:
                                                net_color = '#ef4444'
                                                net_text = 'NET VENTA'
                                            else:
                                                net_color = '#6b7280'
                                                net_text = 'NEUTRAL'

                                            st.markdown(f"""
                                            <div style='text-align: center; padding: 0.75rem;'>
                                                <div style='font-size: 1.5rem; font-weight: 700; color: {net_color};'>
                                                    {net_inst_balance:+d}
                                                </div>
                                                <div style='font-size: 0.8rem; color: #64748b;'>
                                                    {net_text}
                                                </div>
                                            </div>
                                            """, unsafe_allow_html=True)

                                        # Interpretation
                                        if net_inst_balance > 5:
                                            st.success(f"Smart money comprando: Más instituciones aumentando posiciones que reduciéndolas. Señal de confianza institucional.")
                                        elif net_inst_balance < -5:
                                            st.warning(f"Smart money vendiendo: Más instituciones reduciendo posiciones. Puede indicar preocupaciones o rotación sectorial.")
                                        else:
                                            st.info(f"Balance neutral: Actividad institucional balanceada.")
                                    else:
                                        st.info("Datos de cambio (compra/venta) no disponibles en la API. Solo se muestran las posiciones actuales.")

                                else:
                                    st.info("No hay datos de institutional holdings disponibles")
                            else:
                                st.warning("No se pudo inicializar el cliente FMP para obtener datos institucionales")

                        except Exception as e:
                            st.warning(f"No se pudo obtener información de institutional holdings: {str(e)}")

                    else:
                        st.info("Ownership data not available")


                    st.markdown("---")

                    # ============================================================
                    # RECENT NEWS & EVENTS
                    # ============================================================
                    st.markdown("""
                    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 1rem;'>
                        <div style='display: flex; align-items: center; gap: 0.75rem;'>
                            <span style='background: rgba(255,255,255,0.2); padding: 0.35rem 0.75rem; border-radius: 4px; font-size: 0.7rem; font-weight: 700; color: white; letter-spacing: 0.5px;'>
                                SECTION 4
                            </span>
                            <h3 style='margin: 0; color: white; font-weight: 600;'>
                                Recent News & Market Catalysts
                            </h3>
                        </div>
                        <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem; padding-left: 0.5rem;'>
                            Latest developments and market-moving events
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

                    news = analysis.get('recent_news', [])

                    if news:
                        for i, item in enumerate(news[:5]):
                            date = item.get('date', 'N/A')
                            headline = item.get('headline', 'No headline')
                            summary = item.get('summary', '')
                            url = item.get('url', '')

                            # Color code based on sentiment if available
                            sentiment = item.get('sentiment', 'neutral')
                            if sentiment == 'positive':
                                card_bg = '#d1fae5'
                                card_border = '#10b981'
                                badge = '<span style="background: #10b981; color: white; padding: 0.15rem 0.5rem; border-radius: 3px; font-size: 0.65rem; font-weight: 700; letter-spacing: 0.3px;">POSITIVE</span>'
                            elif sentiment == 'negative':
                                card_bg = '#fee2e2'
                                card_border = '#ef4444'
                                badge = '<span style="background: #ef4444; color: white; padding: 0.15rem 0.5rem; border-radius: 3px; font-size: 0.65rem; font-weight: 700; letter-spacing: 0.3px;">NEGATIVE</span>'
                            else:
                                card_bg = '#f3f4f6'
                                card_border = '#9ca3af'
                                badge = '<span style="background: #6b7280; color: white; padding: 0.15rem 0.5rem; border-radius: 3px; font-size: 0.65rem; font-weight: 700; letter-spacing: 0.3px;">NEWS</span>'

                            # Create expander title - show date and truncated headline
                            expander_title = f"{date}: {headline[:70]}{'...' if len(headline) > 70 else ''}"

                            with st.expander(expander_title, expanded=(i==0)):
                                # Full headline inside
                                st.markdown(f"""
                                <div style='margin-bottom: 0.75rem; display: flex; justify-content: space-between; align-items: start;'>
                                    <div style='font-weight: 600; font-size: 1rem; color: #1e293b; flex: 1; margin-right: 1rem;'>
                                        {headline}
                                    </div>
                                    {badge}
                                </div>
                                """, unsafe_allow_html=True)

                                # Summary - clean up truncated text
                                if summary and len(summary) > 20:
                                    # Remove trailing ellipsis or incomplete sentences
                                    summary_clean = summary.strip()
                                    if summary_clean.endswith('...'):
                                        summary_clean = summary_clean[:-3].strip()
                                    # If ends mid-sentence (lowercase), add ellipsis
                                    if summary_clean and not summary_clean[-1] in '.!?' and summary_clean[-1].islower():
                                        summary_clean += '...'

                                    st.markdown(f"""
                                    <div style='background: {card_bg}; padding: 1rem; border-radius: 8px; border-left: 3px solid {card_border}; margin-bottom: 1rem;'>
                                        <div style='font-size: 0.9rem; line-height: 1.7; color: #334155;'>
                                            {summary_clean}
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)
                                else:
                                    st.info("Summary not available for this article")

                                # Source and link
                                col_date, col_link = st.columns([1, 1])
                                with col_date:
                                    st.caption(f"Published: {date}")
                                with col_link:
                                    if url:
                                        st.markdown(f"[Read full article]({url})")
                                    else:
                                        st.caption("Link not available")
                    else:
                        st.info("No recent news available")

                    st.markdown("---")

                    # ============================================================
                    # SECTION 5: GOVERNMENT TRACKER (Capitol Hill Trading)
                    # ============================================================
                    # Always show section header
                    st.markdown("""
                    <div style='background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
                                padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 1rem;'>
                        <div style='display: flex; align-items: center; gap: 0.75rem;'>
                            <span style='background: rgba(255,255,255,0.2); padding: 0.35rem 0.75rem; border-radius: 4px; font-size: 0.7rem; font-weight: 700; color: white; letter-spacing: 0.5px;'>
                                SECTION 5
                            </span>
                            <h3 style='margin: 0; color: white; font-weight: 600;'>
                                Capitol Hill Activity
                            </h3>
                        </div>
                        <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.85rem; padding-left: 0.5rem;'>
                            Senate & House trading - Following the smart money político
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

                    government_trading = analysis.get('government_trading')
                    if government_trading:
                        signal = government_trading.get('signal', 'Neutral')
                        signal_color_map = {'Bullish': '#10b981', 'Bearish': '#ef4444', 'Neutral': '#6b7280'}
                        signal_color = signal_color_map.get(signal, '#6b7280')

                        # Summary metrics
                        col1, col2, col3, col4 = st.columns(4)

                        with col1:
                            total_trades = government_trading.get('total_trades', 0)
                            st.markdown(f"""
                            <div style='background: white; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;'>
                                <div style='font-size: 0.75rem; color: #64748b; margin-bottom: 0.5rem; font-weight: 600;'>
                                    TOTAL TRADES (6M)
                                </div>
                                <div style='font-size: 2rem; font-weight: 700; color: #667eea;'>
                                    {total_trades}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        with col2:
                            buys_count = len(government_trading.get('buys', []))
                            st.markdown(f"""
                            <div style='background: white; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;'>
                                <div style='font-size: 0.75rem; color: #64748b; margin-bottom: 0.5rem; font-weight: 600;'>
                                    COMPRAS
                                </div>
                                <div style='font-size: 2rem; font-weight: 700; color: #10b981;'>
                                    {buys_count}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        with col3:
                            sells_count = len(government_trading.get('sells', []))
                            st.markdown(f"""
                            <div style='background: white; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;'>
                                <div style='font-size: 0.75rem; color: #64748b; margin-bottom: 0.5rem; font-weight: 600;'>
                                    VENTAS
                                </div>
                                <div style='font-size: 2rem; font-weight: 700; color: #ef4444;'>
                                    {sells_count}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        with col4:
                            st.markdown(f"""
                            <div style='background: {signal_color}; padding: 1rem; border-radius: 8px; text-align: center;'>
                                <div style='font-size: 0.75rem; color: white; margin-bottom: 0.5rem; font-weight: 600; opacity: 0.9;'>
                                    SEÑAL
                                </div>
                                <div style='font-size: 1.3rem; font-weight: 700; color: white;'>
                                    {signal.upper()}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        # Recent trades details
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.markdown("**Recent Activity:**")

                        buys = government_trading.get('buys', [])
                        sells = government_trading.get('sells', [])

                        # Show top 5 recent trades
                        all_trades = []
                        for buy in buys[:3]:
                            all_trades.append({**buy, 'action': 'BUY'})
                        for sell in sells[:3]:
                            all_trades.append({**sell, 'action': 'SELL'})

                        # Sort by date
                        all_trades.sort(key=lambda x: x.get('date', ''), reverse=True)

                        for trade in all_trades[:5]:
                            action = trade.get('action', 'UNKNOWN')
                            action_color = '#10b981' if action == 'BUY' else '#ef4444'
                            action_bg = '#d1fae5' if action == 'BUY' else '#fee2e2'

                            senator = trade.get('senator', 'Unknown')
                            amount = trade.get('amount', 'Unknown')
                            date = trade.get('date', 'N/A')

                            st.markdown(f"""
                            <div style='background: {action_bg}; padding: 0.75rem 1rem; border-radius: 6px; margin-bottom: 0.5rem; border-left: 3px solid {action_color};'>
                                <div style='display: flex; justify-content: space-between; align-items: center;'>
                                    <div>
                                        <div style='font-weight: 600; color: #1e293b; font-size: 0.9rem;'>
                                            {senator}
                                        </div>
                                        <div style='color: #64748b; font-size: 0.8rem;'>
                                            {amount} • {date}
                                        </div>
                                    </div>
                                    <span style='background: {action_color}; color: white; padding: 0.25rem 0.6rem; border-radius: 4px; font-size: 0.7rem; font-weight: 700;'>
                                        {action}
                                    </span>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        if len(all_trades) == 0:
                            st.info("No recent government trading activity found")
                    else:
                        st.info("No hay datos de trading de senators/congresistas para este símbolo. Puede que no sea ampliamente traded por políticos o los datos no están disponibles en FMP.")

                    st.markdown("---")

                    # ============================================================
                    # SECTION 6: GEOGRAPHIC REVENUE RISK MAP
                    # ============================================================
                    revenue_geo = analysis.get('revenue_geographic')
                    if revenue_geo:
                        st.markdown("""
                        <div style='background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                                    padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 1rem;'>
                            <div style='display: flex; align-items: center; gap: 0.75rem;'>
                                <span style='background: rgba(255,255,255,0.2); padding: 0.35rem 0.75rem; border-radius: 4px; font-size: 0.7rem; font-weight: 700; color: white; letter-spacing: 0.5px;'>
                                    SECTION 6
                                </span>
                                <h3 style='margin: 0; color: white; font-weight: 600;'>
                                    Geographic Revenue Exposure
                                </h3>
                            </div>
                            <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.85rem; padding-left: 0.5rem;'>
                                Geopolitical risk assessment - China, Taiwan, emerging markets
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                        risk_level = revenue_geo.get('risk_level', 'Low')
                        risk_level_colors = {
                            'High': ('#ef4444', '#fee2e2'),
                            'Medium': ('#f59e0b', '#fef3c7'),
                            'Low': ('#10b981', '#d1fae5')
                        }
                        risk_color, risk_bg = risk_level_colors.get(risk_level, ('#6b7280', '#f3f4f6'))

                        # Risk level card
                        st.markdown(f"""
                        <div style='background: {risk_bg}; padding: 1.5rem; border-radius: 8px; border: 2px solid {risk_color}; margin-bottom: 1rem; text-align: center;'>
                            <div style='font-size: 0.85rem; color: #64748b; margin-bottom: 0.5rem; font-weight: 600;'>
                                GEOPOLITICAL RISK LEVEL
                            </div>
                            <div style='font-size: 2.5rem; font-weight: 700; color: {risk_color};'>
                                {risk_level.upper()}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        # Geographic breakdown
                        st.markdown("**Revenue by Region:**")

                        breakdown = revenue_geo.get('breakdown', [])
                        for item in breakdown[:8]:  # Show top 8 regions
                            region = item['region']
                            pct = item['percentage']
                            revenue = item['revenue']

                            # Bar visualization
                            bar_width = pct
                            bar_color = '#667eea'

                            # Check if it's a risk region
                            risk_regions = revenue_geo.get('risk_regions', [])
                            is_risk = any(region in risk_region for risk_region in risk_regions)
                            if is_risk:
                                bar_color = '#ef4444' if risk_level == 'High' else '#f59e0b'

                            st.markdown(f"""
                            <div style='margin-bottom: 1rem;'>
                                <div style='display: flex; justify-content: space-between; margin-bottom: 0.25rem;'>
                                    <span style='font-weight: 600; font-size: 0.9rem; color: #1e293b;'>{region}</span>
                                    <span style='font-weight: 700; color: {bar_color};'>{pct:.1f}%</span>
                                </div>
                                <div style='background: #e2e8f0; height: 8px; border-radius: 4px; overflow: hidden;'>
                                    <div style='background: {bar_color}; height: 100%; width: {bar_width}%; transition: width 0.3s ease;'></div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        # Risk regions warning
                        if risk_regions and len(risk_regions) > 0:
                            st.warning(f"**High-risk exposure detected:** {', '.join(risk_regions)}")

                    else:
                        st.info("No hay datos de revenue geográfico para este símbolo. FMP puede no tener segmentación geográfica disponible para esta empresa.")

                        st.markdown("---")

                    # ============================================================
                    # SECTION 7: EARNINGS SURPRISES TRACK RECORD
                    # ============================================================
                    earnings_surprises = analysis.get('earnings_surprises')
                    if earnings_surprises:
                        st.markdown("""
                        <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                                    padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 1rem;'>
                            <div style='display: flex; align-items: center; gap: 0.75rem;'>
                                <span style='background: rgba(255,255,255,0.2); padding: 0.35rem 0.75rem; border-radius: 4px; font-size: 0.7rem; font-weight: 700; color: white; letter-spacing: 0.5px;'>
                                    SECTION 7
                                </span>
                                <h3 style='margin: 0; color: white; font-weight: 600;'>
                                    Earnings Surprises Track Record
                                </h3>
                            </div>
                            <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.85rem; padding-left: 0.5rem;'>
                                Historical earnings beats vs misses - Management credibility
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                        track_record = earnings_surprises.get('track_record', 'Mixed')
                        track_record_colors = {
                            'Excellent': ('#10b981', '#d1fae5'),
                            'Good': ('#3b82f6', '#dbeafe'),
                            'Mixed': ('#f59e0b', '#fef3c7'),
                            'Poor': ('#ef4444', '#fee2e2')
                        }
                        tr_color, tr_bg = track_record_colors.get(track_record, ('#6b7280', '#f3f4f6'))

                        # Summary metrics
                        col1, col2, col3, col4 = st.columns(4)

                        with col1:
                            beats = earnings_surprises.get('beats', 0)
                            st.markdown(f"""
                            <div style='background: #d1fae5; padding: 1rem; border-radius: 8px; border: 1px solid #10b981; text-align: center;'>
                                <div style='font-size: 0.75rem; color: #064e3b; margin-bottom: 0.5rem; font-weight: 600;'>
                                    BEATS
                                </div>
                                <div style='font-size: 2.5rem; font-weight: 700; color: #10b981;'>
                                    {beats}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        with col2:
                            misses = earnings_surprises.get('misses', 0)
                            st.markdown(f"""
                            <div style='background: #fee2e2; padding: 1rem; border-radius: 8px; border: 1px solid #ef4444; text-align: center;'>
                                <div style='font-size: 0.75rem; color: #7f1d1d; margin-bottom: 0.5rem; font-weight: 600;'>
                                    MISSES
                                </div>
                                <div style='font-size: 2.5rem; font-weight: 700; color: #ef4444;'>
                                    {misses}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        with col3:
                            avg_surprise = earnings_surprises.get('avg_surprise_pct', 0)
                            st.markdown(f"""
                            <div style='background: white; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;'>
                                <div style='font-size: 0.75rem; color: #64748b; margin-bottom: 0.5rem; font-weight: 600;'>
                                    AVG SURPRISE
                                </div>
                                <div style='font-size: 2rem; font-weight: 700; color: {"#10b981" if avg_surprise > 0 else "#ef4444"};'>
                                    {avg_surprise:+.1f}%
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        with col4:
                            st.markdown(f"""
                            <div style='background: {tr_bg}; padding: 1rem; border-radius: 8px; border: 2px solid {tr_color}; text-align: center;'>
                                <div style='font-size: 0.75rem; color: #64748b; margin-bottom: 0.5rem; font-weight: 600;'>
                                    TRACK RECORD
                                </div>
                                <div style='font-size: 1.3rem; font-weight: 700; color: {tr_color};'>
                                    {track_record.upper()}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        # Historical details
                        details = earnings_surprises.get('details', [])
                        if details:
                            st.markdown("<br>", unsafe_allow_html=True)
                            st.markdown("**Last 8 Quarters:**")

                            for detail in details[:8]:
                                result = detail.get('result', 'Meet')
                                date = detail.get('date', 'N/A')
                                surprise_pct = detail.get('surprise_pct', 0)

                                result_colors = {
                                    'Beat': ('#10b981', ''),
                                    'Miss': ('#ef4444', ''),
                                    'Meet': ('#6b7280', '=')
                                }
                                result_color, result_icon = result_colors.get(result, ('#6b7280', '?'))

                                st.markdown(f"""
                                <div style='display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0; border-bottom: 1px solid #e2e8f0;'>
                                    <span style='font-weight: 600; color: {result_color};'>{result_icon} {result}</span>
                                    <span style='color: #64748b; font-size: 0.85rem;'>{date}</span>
                                    <span style='color: {result_color}; font-weight: 700;'>{surprise_pct:+.1f}%</span>
                                </div>
                                """, unsafe_allow_html=True)

                    else:
                        st.info("No hay datos de earnings surprises para este símbolo. Puede ser una empresa sin historial público de earnings o datos no disponibles en FMP.")

                        st.markdown("---")

                    # ============================================================
                    # SECTION 8: WALL STREET CONSENSUS
                    # ============================================================
                    analyst_consensus = analysis.get('analyst_consensus')
                    if analyst_consensus:
                        st.markdown("""
                        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                    padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 1rem;'>
                            <div style='display: flex; align-items: center; gap: 0.75rem;'>
                                <span style='background: rgba(255,255,255,0.2); padding: 0.35rem 0.75rem; border-radius: 4px; font-size: 0.7rem; font-weight: 700; color: white; letter-spacing: 0.5px;'>
                                    SECTION 8
                                </span>
                                <h3 style='margin: 0; color: white; font-weight: 600;'>
                                    Wall Street Consensus
                                </h3>
                            </div>
                            <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.85rem; padding-left: 0.5rem;'>
                                Analyst price targets and recommendations
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                        # Price targets
                        target_consensus = analyst_consensus.get('target_consensus', 0)
                        target_high = analyst_consensus.get('target_high', 0)
                        target_low = analyst_consensus.get('target_low', 0)
                        upside_pct = analyst_consensus.get('upside_pct')

                        if target_consensus and target_consensus > 0:
                            st.markdown("**Price Targets:**")

                            col1, col2, col3, col4 = st.columns(4)

                            with col1:
                                st.markdown(f"""
                                <div style='background: white; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;'>
                                    <div style='font-size: 0.75rem; color: #64748b; margin-bottom: 0.5rem; font-weight: 600;'>
                                        TARGET LOW
                                    </div>
                                    <div style='font-size: 1.5rem; font-weight: 700; color: #ef4444;'>
                                        ${target_low:.2f}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)

                            with col2:
                                st.markdown(f"""
                                <div style='background: white; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;'>
                                    <div style='font-size: 0.75rem; color: #64748b; margin-bottom: 0.5rem; font-weight: 600;'>
                                        CONSENSUS
                                    </div>
                                    <div style='font-size: 1.5rem; font-weight: 700; color: #667eea;'>
                                        ${target_consensus:.2f}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)

                            with col3:
                                st.markdown(f"""
                                <div style='background: white; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;'>
                                    <div style='font-size: 0.75rem; color: #64748b; margin-bottom: 0.5rem; font-weight: 600;'>
                                        TARGET HIGH
                                    </div>
                                    <div style='font-size: 1.5rem; font-weight: 700; color: #10b981;'>
                                        ${target_high:.2f}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)

                            with col4:
                                if upside_pct is not None:
                                    upside_color = '#10b981' if upside_pct > 0 else '#ef4444'
                                    st.markdown(f"""
                                    <div style='background: white; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;'>
                                        <div style='font-size: 0.75rem; color: #64748b; margin-bottom: 0.5rem; font-weight: 600;'>
                                            UPSIDE
                                        </div>
                                        <div style='font-size: 1.5rem; font-weight: 700; color: {upside_color};'>
                                            {upside_pct:+.1f}%
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)

                        # Analyst recommendations
                        total_analysts = analyst_consensus.get('total_analysts', 0)
                        if total_analysts > 0:
                            st.markdown("<br>", unsafe_allow_html=True)
                            st.markdown("**Analyst Recommendations:**")

                            strong_buy = analyst_consensus.get('strong_buy', 0)
                            buy = analyst_consensus.get('buy', 0)
                            hold = analyst_consensus.get('hold', 0)
                            sell = analyst_consensus.get('sell', 0)
                            strong_sell = analyst_consensus.get('strong_sell', 0)

                            consensus = analyst_consensus.get('consensus', 'Hold')
                            consensus_color = analyst_consensus.get('consensus_color', 'yellow')

                            # Consensus card
                            consensus_color_map = {
                                'green': '#10b981',
                                'lightgreen': '#3b82f6',
                                'yellow': '#f59e0b',
                                'orange': '#f97316',
                                'red': '#ef4444'
                            }
                            consensus_hex = consensus_color_map.get(consensus_color, '#6b7280')

                            st.markdown(f"""
                            <div style='background: white; padding: 1.5rem; border-radius: 8px; border: 2px solid {consensus_hex}; margin-bottom: 1rem; text-align: center;'>
                                <div style='font-size: 0.85rem; color: #64748b; margin-bottom: 0.5rem; font-weight: 600;'>
                                    CONSENSUS
                                </div>
                                <div style='font-size: 2rem; font-weight: 700; color: {consensus_hex};'>
                                    {consensus.upper()}
                                </div>
                                <div style='font-size: 0.85rem; color: #64748b; margin-top: 0.5rem;'>
                                    Based on {total_analysts} analysts
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                            # Breakdown
                            col1, col2, col3, col4, col5 = st.columns(5)

                            with col1:
                                st.metric("Strong Buy", strong_buy)
                            with col2:
                                st.metric("Buy", buy)
                            with col3:
                                st.metric("Hold", hold)
                            with col4:
                                st.metric("Sell", sell)
                            with col5:
                                st.metric("Strong Sell", strong_sell)

                    else:
                        st.info("No hay datos de consenso de analistas para este símbolo. Puede tener poca cobertura de Wall Street o datos no disponibles en FMP.")

                    st.markdown("---")

                    # ============================================================
                    # SECTION 9: CYCLICAL ASSET ANALYSIS
                    # ============================================================
                    cyclical_analysis = analysis.get('cyclical_analysis')
                    if cyclical_analysis and cyclical_analysis.get('is_cyclical'):
                        st.markdown("""
                        <div style='background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
                                    padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 1rem;'>
                            <div style='display: flex; align-items: center; gap: 0.75rem;'>
                                <span style='background: rgba(255,255,255,0.2); padding: 0.35rem 0.75rem; border-radius: 4px; font-size: 0.7rem; font-weight: 700; color: white; letter-spacing: 0.5px;'>
                                    SECTION 9
                                </span>
                                <h3 style='margin: 0; color: white; font-weight: 600;'>
                                    Cyclical Asset Analysis
                                </h3>
                            </div>
                            <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.85rem; padding-left: 0.5rem;'>
                                Special timing tools for cyclical stocks
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                        # CYCLICAL ASSET BADGE
                        st.markdown("""
                        <div style='background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
                                    padding: 1.5rem; border-radius: 10px; margin-bottom: 1.5rem;
                                    border-left: 4px solid #f59e0b; box-shadow: 0 2px 4px rgba(0,0,0,0.08);'>
                            <div style='font-weight: 700; color: #92400e; font-size: 1.1rem; margin-bottom: 0.75rem; letter-spacing: 0.5px;'>
                                CYCLICAL ASSET DETECTED
                            </div>
                            <div style='font-size: 0.9rem; color: #78350f; line-height: 1.6;'>
                                This stock exhibits cyclical characteristics. Traditional valuation metrics (P/E, P/B) may be misleading.
                                Use the timing tools below to assess cycle position.
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        # DETECTION CRITERIA
                        st.markdown("**How We Detected This as Cyclical:**")

                        detection_reasons = []
                        if cyclical_analysis.get('sector_match'):
                            sector = cyclical_analysis.get('sector', 'Unknown')
                            detection_reasons.append(f"Sector: **{sector}** (cyclical industry)")

                        if cyclical_analysis.get('high_beta'):
                            beta = cyclical_analysis.get('beta', 0)
                            detection_reasons.append(f"Beta: **{beta:.2f}** (>1.3 threshold)")

                        if cyclical_analysis.get('eps_volatility'):
                            eps_volatility_count = cyclical_analysis.get('eps_volatility_count', 0)
                            detection_reasons.append(f"EPS Volatility: **{eps_volatility_count} years** with >20% decline in last 10 years")

                        for reason in detection_reasons:
                            st.markdown(f"- {reason}")

                        st.markdown("<br>", unsafe_allow_html=True)

                        # TIMING TOOLS
                        st.markdown("**Timing Tools (Cycle Position Indicators):**")

                        timing_tools = cyclical_analysis.get('timing_tools', {})

                        # Create 2x2 grid for the 4 tools
                        col1, col2 = st.columns(2)

                        # TOOL 1: P/E PARADOX
                        with col1:
                            pe_paradox = timing_tools.get('pe_paradox', {})

                            # Check if data exists or if there was an attempt
                            if not pe_paradox:
                                pe_signal = 'NEUTRAL'
                                pe_value = None
                                pe_interpretation = 'No P/E data available from FMP API. Check if company has earnings or if premium endpoint is accessible.'
                            else:
                                pe_signal = pe_paradox.get('signal', 'NEUTRAL')
                                pe_value = pe_paradox.get('pe_ratio')
                                pe_interpretation = pe_paradox.get('interpretation', 'No data')

                            # Color based on signal
                            if pe_signal == 'DANGER':
                                signal_color = '#ef4444'
                                signal_bg = '#fee2e2'
                            elif pe_signal == 'OPPORTUNITY':
                                signal_color = '#10b981'
                                signal_bg = '#d1fae5'
                            else:
                                signal_color = '#6b7280'
                                signal_bg = '#f3f4f6'

                            st.markdown(f"""
                            <div style='background: white; padding: 1.25rem; border-radius: 10px; border: 2px solid {signal_color}; margin-bottom: 1rem;'>
                                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;'>
                                    <div style='font-weight: 700; color: #0f172a; font-size: 0.95rem;'>P/E PARADOX</div>
                                    <span style='background: {signal_bg}; color: {signal_color}; padding: 0.25rem 0.65rem;
                                                 border-radius: 4px; font-size: 0.7rem; font-weight: 700;
                                                 letter-spacing: 0.5px;'>{pe_signal}</span>
                                </div>
                                <div style='font-size: 0.85rem; color: #475569; margin-bottom: 0.5rem;'>
                                    Current P/E: <strong>{pe_value if pe_value else 'N/A'}</strong>
                                </div>
                                <div style='font-size: 0.8rem; color: #64748b; line-height: 1.4;'>
                                    {pe_interpretation}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        # TOOL 2: P/B BANDS
                        with col2:
                            pb_bands = timing_tools.get('pb_bands', {})

                            # Check if data exists
                            if not pb_bands:
                                pb_signal = 'NEUTRAL'
                                pb_current = None
                                pb_avg = None
                                pb_interpretation = 'No P/B data available from FMP API. Check if historical key metrics endpoint is accessible.'
                            else:
                                pb_signal = pb_bands.get('signal', 'NEUTRAL')
                                pb_current = pb_bands.get('pb_current')
                                pb_avg = pb_bands.get('pb_avg')
                                pb_lower = pb_bands.get('pb_lower_band')
                                pb_upper = pb_bands.get('pb_upper_band')
                                pb_interpretation = pb_bands.get('interpretation', 'No data')

                            # Format values for display
                            pb_current_str = f"{pb_current:.2f}" if pb_current else "N/A"
                            pb_avg_str = f"{pb_avg:.2f}" if pb_avg else "N/A"

                            # Color based on signal
                            if pb_signal == 'SELL':
                                signal_color = '#ef4444'
                                signal_bg = '#fee2e2'
                            elif pb_signal == 'BUY':
                                signal_color = '#10b981'
                                signal_bg = '#d1fae5'
                            else:
                                signal_color = '#6b7280'
                                signal_bg = '#f3f4f6'

                            st.markdown(f"""
                            <div style='background: white; padding: 1.25rem; border-radius: 10px; border: 2px solid {signal_color}; margin-bottom: 1rem;'>
                                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;'>
                                    <div style='font-weight: 700; color: #0f172a; font-size: 0.95rem;'>P/B BANDS (Centauro)</div>
                                    <span style='background: {signal_bg}; color: {signal_color}; padding: 0.25rem 0.65rem;
                                                 border-radius: 4px; font-size: 0.7rem; font-weight: 700;
                                                 letter-spacing: 0.5px;'>{pb_signal}</span>
                                </div>
                                <div style='font-size: 0.85rem; color: #475569; margin-bottom: 0.5rem;'>
                                    Current: <strong>{pb_current_str}</strong> | Avg: <strong>{pb_avg_str}</strong>
                                </div>
                                <div style='font-size: 0.8rem; color: #64748b; line-height: 1.4;'>
                                    {pb_interpretation}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        col3, col4 = st.columns(2)

                        # TOOL 3: INVENTORY (DIO)
                        with col3:
                            dio_analysis = timing_tools.get('inventory_dio', {})

                            # Check if data exists
                            if not dio_analysis:
                                dio_signal = 'NEUTRAL'
                                dio_current = None
                                dio_avg = None
                                dio_interpretation = 'No inventory data available. Company may not have inventory, or FMP financial ratios endpoint may be inaccessible.'
                            else:
                                dio_signal = dio_analysis.get('signal', 'NEUTRAL')
                                dio_current = dio_analysis.get('dio_current')
                                dio_avg = dio_analysis.get('dio_avg_3y')
                                dio_interpretation = dio_analysis.get('interpretation', 'No data')

                            # Format values for display
                            dio_current_str = f"{dio_current:.1f}" if dio_current else "N/A"
                            dio_avg_str = f"{dio_avg:.1f}" if dio_avg else "N/A"

                            # Color based on signal
                            if dio_signal == 'DANGER':
                                signal_color = '#ef4444'
                                signal_bg = '#fee2e2'
                            elif dio_signal == 'RECOVERY':
                                signal_color = '#10b981'
                                signal_bg = '#d1fae5'
                            else:
                                signal_color = '#6b7280'
                                signal_bg = '#f3f4f6'

                            st.markdown(f"""
                            <div style='background: white; padding: 1.25rem; border-radius: 10px; border: 2px solid {signal_color}; margin-bottom: 1rem;'>
                                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;'>
                                    <div style='font-weight: 700; color: #0f172a; font-size: 0.95rem;'>INVENTORY (DIO)</div>
                                    <span style='background: {signal_bg}; color: {signal_color}; padding: 0.25rem 0.65rem;
                                                 border-radius: 4px; font-size: 0.7rem; font-weight: 700;
                                                 letter-spacing: 0.5px;'>{dio_signal}</span>
                                </div>
                                <div style='font-size: 0.85rem; color: #475569; margin-bottom: 0.5rem;'>
                                    Current: <strong>{dio_current_str}</strong> days | 3Y Avg: <strong>{dio_avg_str}</strong> days
                                </div>
                                <div style='font-size: 0.8rem; color: #64748b; line-height: 1.4;'>
                                    {dio_interpretation}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        # TOOL 4: OPERATING MARGIN
                        with col4:
                            margin_analysis = timing_tools.get('operating_margin', {})
                            margin_signal = margin_analysis.get('signal', 'NEUTRAL')
                            margin_current = margin_analysis.get('margin_current')
                            margin_avg = margin_analysis.get('margin_avg_5y')
                            margin_interpretation = margin_analysis.get('interpretation', 'No data')

                            # Format values for display
                            margin_current_str = f"{margin_current:.1f}" if margin_current else "N/A"
                            margin_avg_str = f"{margin_avg:.1f}" if margin_avg else "N/A"

                            # Color based on signal
                            if margin_signal == 'DANGER':
                                signal_color = '#ef4444'
                                signal_bg = '#fee2e2'
                            elif margin_signal == 'CAUTION':
                                signal_color = '#f59e0b'
                                signal_bg = '#fef3c7'
                            elif margin_signal == 'OPPORTUNITY':
                                signal_color = '#10b981'
                                signal_bg = '#d1fae5'
                            elif margin_signal == 'WATCH':
                                signal_color = '#3b82f6'
                                signal_bg = '#dbeafe'
                            else:
                                signal_color = '#6b7280'
                                signal_bg = '#f3f4f6'

                            st.markdown(f"""
                            <div style='background: white; padding: 1.25rem; border-radius: 10px; border: 2px solid {signal_color}; margin-bottom: 1rem;'>
                                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;'>
                                    <div style='font-weight: 700; color: #0f172a; font-size: 0.95rem;'>OPERATING MARGIN</div>
                                    <span style='background: {signal_bg}; color: {signal_color}; padding: 0.25rem 0.65rem;
                                                 border-radius: 4px; font-size: 0.7rem; font-weight: 700;
                                                 letter-spacing: 0.5px;'>{margin_signal}</span>
                                </div>
                                <div style='font-size: 0.85rem; color: #475569; margin-bottom: 0.5rem;'>
                                    Current: <strong>{margin_current_str}%</strong> | 5Y Avg: <strong>{margin_avg_str}%</strong>
                                </div>
                                <div style='font-size: 0.8rem; color: #64748b; line-height: 1.4;'>
                                    {margin_interpretation}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        # OVERALL CYCLE ASSESSMENT
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.markdown("**Overall Cycle Assessment:**")

                        # Count signals
                        danger_count = sum(1 for tool in timing_tools.values() if tool.get('signal') in ['DANGER', 'SELL'])
                        caution_count = sum(1 for tool in timing_tools.values() if tool.get('signal') == 'CAUTION')
                        opportunity_count = sum(1 for tool in timing_tools.values() if tool.get('signal') in ['OPPORTUNITY', 'BUY', 'RECOVERY'])
                        watch_count = sum(1 for tool in timing_tools.values() if tool.get('signal') == 'WATCH')

                        # Calculate combined scores for assessment
                        peak_score = danger_count + (caution_count * 0.5)  # CAUTION counts as half DANGER
                        trough_score = opportunity_count + (watch_count * 0.5)  # WATCH counts as half OPPORTUNITY

                        if peak_score >= 2:
                            assessment_color = '#fef3c7'
                            assessment_border = '#f59e0b'
                            assessment_text = f"**CAUTION:** {danger_count} DANGER + {caution_count} CAUTION signals suggest this stock may be at or near peak cycle. Traditional 'low P/E = bargain' logic may not apply. Consider waiting for cycle downturn."
                        elif trough_score >= 2:
                            assessment_color = '#d1fae5'
                            assessment_border = '#10b981'
                            assessment_text = f"**OPPORTUNITY:** {opportunity_count} OPPORTUNITY + {watch_count} WATCH signals suggest this stock may be in trough or recovery phase. High P/E or depressed margins may actually signal future upside potential."
                        else:
                            assessment_color = '#f3f4f6'
                            assessment_border = '#6b7280'
                            assessment_text = "**MID-CYCLE:** Mixed signals. Stock appears to be in transition between cycle phases. Monitor closely for clearer directional signals."

                        st.markdown(f"""
                        <div style='background: {assessment_color}; padding: 1.25rem; border-radius: 10px; border-left: 4px solid {assessment_border}; margin-bottom: 1rem;'>
                            <div style='font-size: 0.9rem; color: #0f172a; line-height: 1.6;'>
                                {assessment_text}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        st.markdown("---")

                    # ============================================================
                    # INTRINSIC VALUE & VALUATION
                    # ============================================================
                    st.markdown("""
                    <div style='background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
                                padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 1rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
                        <div style='display: flex; align-items: center; gap: 0.75rem;'>
                            <span style='background: rgba(255,255,255,0.25); padding: 0.35rem 0.75rem; border-radius: 4px; font-size: 0.7rem; font-weight: 700; color: white; letter-spacing: 0.5px;'>
                                VALUATION
                            </span>
                            <h3 style='margin: 0; color: white; font-weight: 600;'>
                                Robust Fair Value Estimation
                            </h3>
                        </div>
                        <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.85rem; padding-left: 0.5rem;'>
                            Multi-method consensus with family weighting and outlier trimming
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

                    intrinsic = analysis.get('intrinsic_value', {})

                    # Show section if we have intrinsic_value dict
                    if intrinsic and 'current_price' in intrinsic:
                        current_price = intrinsic.get('current_price', 0)
                        robust_val = intrinsic.get('robust_valuation')

                        # === ROBUST VALUATION SYSTEM (NEW) ===
                        robust_val = intrinsic.get('robust_valuation')
                        confidence_data = intrinsic.get('confidence_score')
                        growth_engine = intrinsic.get('growth_engine')

                        # DEBUG SECTION - Collapsed by default
                        with st.expander("🔧 DEBUG: Robust Fair Value Calculation", expanded=False):
                            st.write("**Valuation Methods Available:**")
                            dcf_val = intrinsic.get('dcf_value')
                            fwd_val = intrinsic.get('forward_multiple_value')
                            hist_val = intrinsic.get('historical_multiple_value')
                            pe_val = intrinsic.get('pe_value')
                            peg_val = intrinsic.get('peg_value')
                            ev_ebit_val = intrinsic.get('ev_ebit_value')
                            ev_fcf_val = intrinsic.get('ev_fcf_value')

                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"- DCF: ${dcf_val:.2f}" if dcf_val else "- DCF: ❌ None")
                                st.write(f"- Forward Multiple: ${fwd_val:.2f}" if fwd_val else "- Forward Multiple: ❌ None")
                                st.write(f"- Historical Multiple: ${hist_val:.2f}" if hist_val else "- Historical Multiple: ❌ None")
                                st.write(f"- P/E Value: ${pe_val:.2f}" if pe_val else "- P/E Value: ❌ None")
                            with col2:
                                st.write(f"- PEG Value: ${peg_val:.2f}" if peg_val else "- PEG Value: ❌ None")
                                st.write(f"- EV/EBIT Value: ${ev_ebit_val:.2f}" if ev_ebit_val else "- EV/EBIT Value: ❌ None")
                                st.write(f"- EV/FCF Value: ${ev_fcf_val:.2f}" if ev_fcf_val else "- EV/FCF Value: ❌ None")

                            # Count methods
                            methods_count = sum([1 for v in [dcf_val, fwd_val, hist_val, pe_val, peg_val, ev_ebit_val, ev_fcf_val] if v and v > 0])
                            st.write(f"\n**Methods Count:** {methods_count} (need ≥1)")
                            st.write(f"**Confidence Score Exists:** {'✅ Yes' if confidence_data else '❌ No'}")
                            st.write(f"**Growth Engine Exists:** {'✅ Yes' if growth_engine else '❌ No'}")

                            # Show calculation attempts for missing methods
                            calc_attempts = intrinsic.get('_debug_valuation_calc_attempts', [])
                            if calc_attempts:
                                st.divider()
                                st.write("**🔧 Valuation Method Calculation Attempts:**")
                                for attempt in calc_attempts:
                                    if '✓' in attempt:
                                        st.success(attempt)
                                    elif '⚠️' in attempt or 'returned None' in attempt:
                                        st.warning(attempt)
                                    elif '❌' in attempt:
                                        st.error(attempt)
                                    else:
                                        st.write(f"- {attempt}")

                            st.divider()
                            st.write("**🔍 Execution Trace:**")

                            # Show all debug flags
                            debug_started = intrinsic.get('_debug_robust_started')
                            st.write(f"1. Code block started: {'✅ Yes' if debug_started else '❌ NO - CODE NOT EXECUTING'}")

                            if debug_started:
                                st.write(f"2. Variables at start: {intrinsic.get('_debug_variables', 'N/A')}")
                                st.write(f"3. Methods dict built: {intrinsic.get('_debug_methods_dict', 'N/A')}")
                                st.write(f"4. Methods count: {intrinsic.get('_debug_methods_count', 0)}")
                                st.write(f"5. Has confidence: {intrinsic.get('_debug_has_confidence', False)}")

                                condition_met = intrinsic.get('_debug_condition_met')
                                st.write(f"6. Condition met (>=1 methods + confidence): {'✅ Yes' if condition_met else '❌ No'}")

                                if condition_met:
                                    st.write(f"7. Function returned value: {'✅ Yes' if intrinsic.get('_debug_returned') else '❌ No (None)'}")
                                    st.write(f"8. Has 'fair_value_robust' key: {'✅ Yes' if intrinsic.get('_debug_has_fair_value_key') else '❌ No'}")
                                    fair_val_debug = intrinsic.get('_debug_fair_value')
                                    st.write(f"9. fair_value value: ${fair_val_debug:.2f}" if fair_val_debug else "9. fair_value value: ❌ None or 0")

                                    if intrinsic.get('_debug_added_to_dict'):
                                        st.success("✅ Successfully added to valuation dict!")
                                    else:
                                        st.error(f"❌ NOT ADDED: {intrinsic.get('_debug_why_not_added', 'unknown reason')}")

                                        # Show the full returned dict to see error messages in 'notes'
                                        st.write("**🔍 Full return dict from function:**")
                                        full_return = intrinsic.get('_debug_full_return')
                                        if full_return:
                                            st.json(full_return)
                                            if 'notes' in full_return and full_return['notes']:
                                                st.error("**Error messages in notes:**")
                                                for note in full_return['notes']:
                                                    st.write(f"- {note}")
                                        else:
                                            st.write("_debug_full_return not available")
                                else:
                                    st.error(f"❌ Condition not met: {intrinsic.get('_debug_why_not_calculated', 'unknown')}")

                            st.divider()
                            st.write(f"**Final result - robust_valuation in dict:** {'✅ Yes' if robust_val else '❌ NO'}")
                            if robust_val:
                                st.write(f"**has fair_value_robust:** {'✅ Yes' if robust_val.get('fair_value_robust') else '❌ No'}")
                                st.json(robust_val)

                        if robust_val and robust_val.get('fair_value_robust'):
                            st.markdown("<br>", unsafe_allow_html=True)

                            # Extract metrics
                            fair_value_robust = robust_val.get('fair_value_robust')
                            range_p10 = robust_val.get('range_p10')
                            range_p90 = robust_val.get('range_p90')
                            consensus_tightness = robust_val.get('consensus_tightness', 'Low')
                            percentile_info = intrinsic.get('percentile_info', {})
                            positioning = percentile_info.get('positioning', '')
                            downside_label = percentile_info.get('downside_label', '')
                            multiples_reliability = robust_val.get('multiples_reliability', 'Medium')
                            reliability_reason = robust_val.get('multiples_reliability_reason', '')

                            # Professional panel header
                            st.markdown("""
                            <div style='font-weight: 700; color: #0f172a; font-size: 0.95rem; margin-bottom: 0.75rem;'>
                                Robust Fair Value
                            </div>
                            """, unsafe_allow_html=True)

                            col_fv1, col_fv2, col_fv3 = st.columns(3)

                            with col_fv1:
                                st.metric("Robust FV (p50)", f"${fair_value_robust:.2f}", help="Median fair value from robust multi-method consensus")

                            with col_fv2:
                                st.metric("Price", f"${current_price:.2f}", help=f"{positioning}")

                            with col_fv3:
                                # Extract the downside/upside percentage from downside_label
                                # downside_label format: "Downside to robust p90: -20.5%" or "Upside to p90: +25.0%"
                                import re
                                match = re.search(r'([+-]?\d+\.?\d*)%', downside_label)
                                delta_value = match.group(1) if match else "0"
                                delta_display = f"{delta_value}%"
                                label_prefix = "Downside to p90" if "Downside" in downside_label else "Upside to p90"
                                st.metric(label_prefix, delta_display, help=downside_label)

                            # Visual range indicator - Professional design
                            range_span = range_p90 - range_p10
                            if range_span > 0:
                                # Determine if price or FV fall outside the p10-p90 range
                                # If so, extend the visualization range to accommodate them
                                vis_min = min(range_p10, current_price, fair_value_robust)
                                vis_max = max(range_p90, current_price, fair_value_robust)

                                # Add 5% padding on extended sides for better visualization
                                if vis_min < range_p10:
                                    vis_min = vis_min - (range_p10 - vis_min) * 0.05
                                if vis_max > range_p90:
                                    vis_max = vis_max + (vis_max - range_p90) * 0.05

                                vis_span = vis_max - vis_min

                                # Calculate positions in the extended range
                                price_position = (current_price - vis_min) / vis_span
                                fv_position = (fair_value_robust - vis_min) / vis_span
                                p10_position = (range_p10 - vis_min) / vis_span
                                p90_position = (range_p90 - vis_min) / vis_span
                                p50_position = ((range_p10 + range_p90) / 2 - vis_min) / vis_span

                                # Determine zone based on position relative to p10-p90 range (not visual range)
                                if current_price < range_p10:
                                    zone_label = "Deeply Undervalued"
                                    zone_color = "#059669"
                                elif current_price < range_p10 + range_span * 0.33:
                                    zone_label = "Undervalued Zone"
                                    zone_color = "#10b981"
                                elif current_price < range_p10 + range_span * 0.67:
                                    zone_label = "Fair Value Zone"
                                    zone_color = "#f59e0b"
                                elif current_price <= range_p90:
                                    zone_label = "Overvalued Zone"
                                    zone_color = "#ef4444"
                                else:
                                    zone_label = "Extremely Overvalued"
                                    zone_color = "#dc2626"

                                # Pre-build HTML parts with all values calculated
                                extended_left_html = ''
                                if p10_position > 0.02:
                                    left_right_pct = (1 - p10_position) * 100
                                    extended_left_html = f"<div style='position: absolute; top: 32px; left: 0; right: {left_right_pct}%; height: 16px; background: repeating-linear-gradient(45deg, #d1fae5, #d1fae5 4px, #a7f3d0 4px, #a7f3d0 8px); border-radius: 8px 0 0 8px; border: 2px dashed #10b981; opacity: 0.6;'></div>"

                                extended_right_html = ''
                                if p90_position < 0.98:
                                    right_left_pct = p90_position * 100
                                    extended_right_html = f"<div style='position: absolute; top: 32px; left: {right_left_pct}%; right: 0; height: 16px; background: repeating-linear-gradient(45deg, #fee2e2, #fee2e2 4px, #fecaca 4px, #fecaca 8px); border-radius: 0 8px 8px 0; border: 2px dashed #ef4444; opacity: 0.6;'></div>"

                                # Calculate all percentage positions
                                p10_pct = p10_position * 100
                                p50_pct = p50_position * 100
                                p90_pct = p90_position * 100
                                price_pct = price_position * 100
                                fv_pct = fv_position * 100
                                p10_right_pct = (1 - p90_position) * 100
                                p50_value = (range_p10 + range_p90) / 2

                                # Build HTML using string concatenation to avoid f-string issues
                                html_content = "<div style='margin: 1rem 0; padding: 1rem; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0;'>"
                                html_content += "<div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;'>"
                                html_content += "<div style='font-size: 0.75rem; font-weight: 700; color: #0f172a; letter-spacing: 0.5px;'>VALUE RANGE SPECTRUM</div>"
                                html_content += f"<div style='display: inline-block; padding: 3px 8px; background: {zone_color}; color: white; border-radius: 4px; font-size: 0.65rem; font-weight: 700;'>{zone_label}</div>"
                                html_content += "</div>"
                                html_content += "<div style='position: relative; height: 60px; margin: 0.5rem 0;'>"
                                html_content += f"<div style='position: absolute; top: 32px; left: {p10_pct}%; right: {p10_right_pct}%; height: 16px; background: linear-gradient(90deg, #d1fae5 0%, #a7f3d0 15%, #fef3c7 50%, #fecaca 85%, #fee2e2 100%); border-radius: 8px; border: 2px solid #cbd5e1; box-shadow: inset 0 2px 4px rgba(0,0,0,0.06);'></div>"
                                html_content += extended_left_html
                                html_content += extended_right_html
                                html_content += f"<div style='position: absolute; left: {p10_pct}%; top: 28px;'><div style='width: 2px; height: 24px; background: #10b981;'></div><div style='position: absolute; top: -20px; left: 50%; transform: translateX(-50%); font-size: 0.65rem; font-weight: 600; color: #10b981; white-space: nowrap;'>p10: ${range_p10:.0f}</div></div>"
                                html_content += f"<div style='position: absolute; left: {p50_pct}%; top: 28px;'><div style='width: 2px; height: 24px; background: #64748b;'></div><div style='position: absolute; top: -20px; left: 50%; transform: translateX(-50%); font-size: 0.65rem; font-weight: 600; color: #64748b; white-space: nowrap;'>p50: ${p50_value:.0f}</div></div>"
                                html_content += f"<div style='position: absolute; left: {p90_pct}%; top: 28px;'><div style='width: 2px; height: 24px; background: #ef4444;'></div><div style='position: absolute; top: -20px; left: 50%; transform: translateX(-50%); font-size: 0.65rem; font-weight: 600; color: #ef4444; white-space: nowrap;'>p90: ${range_p90:.0f}</div></div>"
                                html_content += f"<div style='position: absolute; left: {price_pct}%; top: 24px; z-index: 10;'><div style='width: 5px; height: 32px; background: #0f172a; border-radius: 2px; box-shadow: 0 3px 8px rgba(0,0,0,0.4);'></div><div style='position: absolute; bottom: -22px; left: 50%; transform: translateX(-50%); font-size: 0.7rem; font-weight: 800; color: #0f172a; white-space: nowrap; background: white; padding: 3px 6px; border-radius: 4px; border: 2px solid #0f172a; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>${current_price:.0f}</div></div>"
                                html_content += f"<div style='position: absolute; left: {fv_pct}%; top: 32px; z-index: 9;'><div style='width: 14px; height: 14px; background: #3b82f6; border: 3px solid white; border-radius: 50%; box-shadow: 0 2px 8px rgba(59, 130, 246, 0.5);'></div><div style='position: absolute; bottom: -22px; left: 50%; transform: translateX(-50%); font-size: 0.65rem; font-weight: 700; color: #3b82f6; white-space: nowrap; background: white; padding: 2px 5px; border-radius: 3px; border: 1px solid #93c5fd;'>FV: ${fair_value_robust:.0f}</div></div>"
                                html_content += "</div>"
                                html_content += "<div style='margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid #e2e8f0; display: flex; justify-content: center; gap: 1.5rem; flex-wrap: wrap;'>"
                                html_content += "<div style='display: flex; align-items: center; gap: 0.35rem;'><div style='width: 5px; height: 16px; background: #0f172a; border-radius: 2px;'></div><span style='font-size: 0.7rem; color: #475569; font-weight: 500;'>Current Price</span></div>"
                                html_content += "<div style='display: flex; align-items: center; gap: 0.35rem;'><div style='width: 14px; height: 14px; background: #3b82f6; border: 2px solid white; border-radius: 50%; box-shadow: 0 1px 3px rgba(0,0,0,0.2);'></div><span style='font-size: 0.7rem; color: #475569; font-weight: 500;'>Fair Value</span></div>"
                                html_content += "<div style='display: flex; align-items: center; gap: 0.35rem;'><div style='width: 20px; height: 12px; background: linear-gradient(90deg, #d1fae5, #fecaca); border-radius: 2px; border: 1px solid #cbd5e1;'></div><span style='font-size: 0.7rem; color: #475569; font-weight: 500;'>p10–p90 Range</span></div>"
                                html_content += "</div></div>"

                                st.markdown(html_content, unsafe_allow_html=True)

                            # Range and consensus info with badges
                            consensus_color = {'High': '#10b981', 'Medium': '#f59e0b', 'Low': '#ef4444'}.get(consensus_tightness, '#64748b')
                            st.markdown(f"""
                            <div style='margin: 0.5rem 0; font-size: 0.75rem; color: #475569;'>
                                Range (p10–p90): <span style='font-weight: 600;'>${range_p10:.2f}–${range_p90:.2f}</span> |
                                Consensus: <span style='display: inline-block; padding: 2px 6px; background: {consensus_color}; color: white; border-radius: 3px; font-weight: 600; font-size: 0.7rem;'>{consensus_tightness}</span> <span style='color: #94a3b8;'>(post-trim)</span>
                            </div>
                            """, unsafe_allow_html=True)

                            # Get method disagreement early for use in conditional
                            method_disagreement = robust_val.get('method_disagreement', '')

                            # Peer selection info - always show for transparency
                            if reliability_reason:
                                # Color scheme based on reliability level
                                reliability_colors = {
                                    'High': {'bg': '#d1fae5', 'border': '#10b981', 'text': '#065f46', 'dot': '#10b981'},
                                    'Medium': {'bg': '#dbeafe', 'border': '#3b82f6', 'text': '#1e3a8a', 'dot': '#3b82f6'},
                                    'Medium-Low': {'bg': '#fef3c7', 'border': '#f59e0b', 'text': '#78350f', 'dot': '#f59e0b'},
                                    'Low': {'bg': '#fef3c7', 'border': '#f59e0b', 'text': '#92400e', 'dot': '#f59e0b'}
                                }
                                colors = reliability_colors.get(multiples_reliability, reliability_colors['Medium'])

                                st.markdown(f"""
                                <div style='background: {colors['bg']}; border-left: 4px solid {colors['border']}; padding: 0.75rem; border-radius: 4px; margin: 0.5rem 0;'>
                                    <div style='display: flex; align-items: center; margin-bottom: 0.35rem;'>
                                        <div style='width: 6px; height: 6px; background: {colors['dot']}; border-radius: 50%; margin-right: 0.5rem;'></div>
                                        <span style='font-weight: 700; color: {colors['text']}; font-size: 0.75rem;'>PEER SELECTION: {multiples_reliability.upper()}</span>
                                    </div>
                                    <div style='font-size: 0.7rem; color: {colors['text']}; margin-left: 1rem;'>{reliability_reason}</div>
                                """, unsafe_allow_html=True)

                                # Family divergence warning (if present)
                                if method_disagreement:
                                    if 'divergence' in method_disagreement.lower():
                                        # Extract divergence percentage if present
                                        import re
                                        divergence_match = re.search(r'(\d+\.?\d*)%', method_disagreement)
                                        divergence_pct = divergence_match.group(1) if divergence_match else None

                                        # Add separator if showing both peer info and divergence
                                        st.markdown("<div style='margin: 0.5rem 0; border-top: 1px solid rgba(0,0,0,0.1); padding-top: 0.5rem;'></div>", unsafe_allow_html=True)

                                        st.markdown(f"""
                                        <div style='display: flex; align-items: center; margin-bottom: 0.35rem;'>
                                            <div style='width: 6px; height: 6px; background: #f59e0b; border-radius: 50%; margin-right: 0.5rem;'></div>
                                            <span style='font-weight: 700; color: #92400e; font-size: 0.75rem;'>FAMILY DIVERGENCE: {divergence_pct + '%' if divergence_pct else 'DETECTED'}</span>
                                        </div>
                                        <div style='font-size: 0.7rem; color: #78350f; margin-left: 1rem;'>{method_disagreement}</div>
                                        """, unsafe_allow_html=True)

                                st.markdown("</div>", unsafe_allow_html=True)

                            # Family divergence shown separately if no peer info
                            elif method_disagreement:
                                st.markdown("""
                                <div style='background: #fef3c7; border-left: 4px solid #f59e0b; padding: 0.75rem; border-radius: 4px; margin: 0.5rem 0;'>
                                """, unsafe_allow_html=True)

                                if 'divergence' in method_disagreement.lower():
                                    import re
                                    divergence_match = re.search(r'(\d+\.?\d*)%', method_disagreement)
                                    divergence_pct = divergence_match.group(1) if divergence_match else None

                                    st.markdown(f"""
                                    <div style='display: flex; align-items: center; margin-bottom: 0.35rem;'>
                                        <div style='width: 6px; height: 6px; background: #f59e0b; border-radius: 50%; margin-right: 0.5rem;'></div>
                                        <span style='font-weight: 700; color: #92400e; font-size: 0.75rem;'>FAMILY DIVERGENCE: {divergence_pct + '%' if divergence_pct else 'DETECTED'}</span>
                                    </div>
                                    <div style='font-size: 0.7rem; color: #78350f; margin-left: 1rem;'>{method_disagreement}</div>
                                    """, unsafe_allow_html=True)

                                st.markdown("</div>", unsafe_allow_html=True)

                            # Consensus explanation if exists (clarifies consensus vs disagreement)
                            consensus_explanation = robust_val.get('consensus_explanation')
                            if consensus_explanation:
                                st.info(f"{consensus_explanation}")

                            # Outliers display (micro-panels for each outlier)
                            outliers_display = robust_val.get('outliers_display')
                            if outliers_display:
                                st.markdown("""
                                <div style='color: #92400e; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.8px; margin-bottom: 0.5rem;'>
                                    OUTLIERS TRIMMED
                                </div>
                                """, unsafe_allow_html=True)

                                # Parse outliers and create micro-panels
                                outliers_list = [o.strip() for o in outliers_display.split(',')]

                                # Create grid of micro-panels
                                cols_per_row = 3
                                for i in range(0, len(outliers_list), cols_per_row):
                                    cols = st.columns(cols_per_row)
                                    for j, outlier in enumerate(outliers_list[i:i+cols_per_row]):
                                        with cols[j]:
                                            # Parse method name and value
                                            if '=' in outlier:
                                                method, value = outlier.split('=', 1)
                                                st.markdown(f"""
                                                <div style='background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
                                                            border: 2px solid #f59e0b;
                                                            padding: 0.75rem;
                                                            border-radius: 8px;
                                                            text-align: center;
                                                            box-shadow: 0 2px 3px rgba(0,0,0,0.08);
                                                            margin-bottom: 0.5rem;'>
                                                    <div style='color: #92400e; font-size: 0.65rem; font-weight: 700; letter-spacing: 0.5px; margin-bottom: 0.25rem;'>
                                                        {method.strip()}
                                                    </div>
                                                    <div style='color: #78350f; font-size: 1.2rem; font-weight: 900; font-family: "SF Mono", Monaco, monospace;'>
                                                        {value.strip()}
                                                    </div>
                                                </div>
                                                """, unsafe_allow_html=True)

                                st.caption("Outliers (outside robust p10–p90 range)")


                        # Implied Expectations (Reverse DCF) - Show prominently
                        reverse_dcf_data = intrinsic.get('reverse_dcf', {})
                        if reverse_dcf_data:
                            implied_growth = reverse_dcf_data.get('implied_growth_rate', 0)
                            interpretation = reverse_dcf_data.get('interpretation', '')

                            # Color based on reasonableness
                            if implied_growth > 40 or implied_growth < -5:
                                expect_color = '#ef4444'
                                expect_bg = '#fee2e2'
                                expect_label = 'ABSURD'
                            elif implied_growth > 25 or implied_growth < 0:
                                expect_color = '#f59e0b'
                                expect_bg = '#fef3c7'
                                expect_label = 'AGGRESSIVE'
                            elif 5 <= implied_growth <= 15:
                                expect_color = '#10b981'
                                expect_bg = '#d1fae5'
                                expect_label = 'REASONABLE'
                            else:
                                expect_color = '#6b7280'
                                expect_bg = '#f3f4f6'
                                expect_label = 'MODERATE'

                            st.markdown(f"""
                            <div style='background: linear-gradient(135deg, {expect_bg} 0%, {expect_bg} 100%);
                                        border-left: 5px solid {expect_color};
                                        padding: 1.25rem 1.5rem; border-radius: 10px; margin-bottom: 1rem;
                                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>
                                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;'>
                                    <div style='font-size: 0.7rem; color: {expect_color}; font-weight: 700; letter-spacing: 0.8px;'>
                                        IMPLIED MARKET EXPECTATIONS
                                    </div>
                                    <div style='background: {expect_color}; color: white; padding: 0.3rem 0.65rem;
                                                border-radius: 5px; font-size: 0.65rem; font-weight: 700; letter-spacing: 0.3px;'>
                                        {expect_label}
                                    </div>
                                </div>
                                <div style='color: {expect_color}; font-size: 1.75rem; font-weight: 800; margin-bottom: 0.5rem; letter-spacing: -0.3px;'>
                                    {implied_growth:.1f}% Perpetual Growth
                                </div>
                                <div style='color: {expect_color}; font-size: 0.85rem; opacity: 0.85; line-height: 1.4;'>
                                    {interpretation}
                                </div>
                                <div style='color: {expect_color}; font-size: 0.7rem; margin-top: 0.5rem; opacity: 0.7; font-style: italic;'>
                                    Reverse DCF Analysis
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        # Confidence Score Visual
                        if confidence_data:
                            conf_score = confidence_data.get('total_score', 0)
                            conf_level = confidence_data.get('confidence_level', 'Low')
                            components = confidence_data.get('components', {})
                            reverse_dcf_penalty = confidence_data.get('reverse_dcf_penalty', 0)

                            # Color based on level
                            if conf_level == 'High':
                                conf_color = '#10b981'
                                conf_bg = '#d1fae5'
                            elif conf_level == 'Medium':
                                conf_color = '#f59e0b'
                                conf_bg = '#fef3c7'
                            else:
                                conf_color = '#ef4444'
                                conf_bg = '#fee2e2'

                            # Professional confidence display without emojis
                            penalty_text = f"<div style='color: {conf_color}; font-size: 0.7rem; margin-top: 0.5rem; opacity: 0.8;'>Reverse DCF Penalty: -{reverse_dcf_penalty}</div>" if reverse_dcf_penalty > 0 else ""
                            st.markdown(f"""
                            <div style='background: linear-gradient(135deg, {conf_bg} 0%, {conf_bg} 100%);
                                        border-left: 5px solid {conf_color};
                                        padding: 1rem 1.25rem; border-radius: 10px; margin-bottom: 1rem;
                                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>
                                <div style='display: flex; align-items: center; gap: 1rem; margin-bottom: 0.5rem;'>
                                    <div>
                                        <div style='font-size: 0.7rem; color: {conf_color}; font-weight: 700; letter-spacing: 0.8px; margin-bottom: 0.25rem;'>
                                            CONFIDENCE SCORE
                                        </div>
                                        <div style='font-size: 2.5rem; font-weight: 900; color: {conf_color}; line-height: 1;'>
                                            {conf_score:.0f}
                                        </div>
                                    </div>
                                    <div style='background: {conf_color}; color: white; padding: 0.4rem 0.8rem;
                                                border-radius: 6px; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.5px;'>
                                        {conf_level.upper()}
                                    </div>
                                </div>
                                {penalty_text}
                            </div>
                            """, unsafe_allow_html=True)

                            # Component breakdown in expander
                            with st.expander("Score Components (Weighted)", expanded=False):
                                comp_labels = {
                                    'stability': ('Stability', 30),
                                    'fcf_quality': ('FCF Quality', 25),
                                    'data_richness': ('Data Richness', 20),
                                    'balance_strength': ('Balance', 15),
                                    'other': ('Other', 10)
                                }

                                for key, (label, weight) in comp_labels.items():
                                    val = components.get(key, 0)
                                    bar_width = val  # 0-100
                                    st.markdown(f"""
                                    <div style='margin-bottom: 0.5rem;'>
                                        <div style='display: flex; justify-content: space-between; font-size: 0.75rem; color: #475569; margin-bottom: 0.2rem;'>
                                            <span>{label} ({weight}%)</span>
                                            <span style='font-weight: 700;'>{val:.0f}</span>
                                        </div>
                                        <div style='background: #e2e8f0; height: 6px; border-radius: 3px; overflow: hidden;'>
                                            <div style='background: {conf_color}; width: {bar_width}%; height: 100%;'></div>
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)

                        # Growth Engine Breakdown
                        if growth_engine and growth_engine.get('revenue_growth_5y'):
                            rev_growth = growth_engine['revenue_growth_5y']

                            st.markdown("<br>", unsafe_allow_html=True)

                            # Extract growth values
                            bear = rev_growth.get('bear', 0) * 100
                            base = rev_growth.get('base', 0) * 100
                            bull = rev_growth.get('bull', 0) * 100
                            volatility = rev_growth.get('volatility', 0)
                            weights = rev_growth.get('weights', {})

                            # Build complete Growth Engine HTML using string concatenation
                            growth_html = "<div style='margin: 1rem 0; padding: 1.25rem; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0;'>"
                            growth_html += "<div style='font-weight: 700; color: #0f172a; font-size: 0.95rem; margin-bottom: 1rem;'>Growth Engine 5Y (Revenue)</div>"

                            # Three scenario cards in a row
                            growth_html += "<div style='display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem;'>"

                            # Bear Case Card
                            growth_html += "<div style='background: white; padding: 1rem; border-radius: 6px; border: 2px solid #fecaca; text-align: center;'>"
                            growth_html += "<div style='font-size: 0.65rem; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.5rem;'>BEAR CASE</div>"
                            growth_html += f"<div style='font-size: 1.75rem; font-weight: 700; color: #ef4444; margin-bottom: 0.25rem;'>{bear:.1f}%</div>"
                            growth_html += "<div style='font-size: 0.65rem; color: #94a3b8;'>Base - volatility</div>"
                            growth_html += "</div>"

                            # Base Case Card
                            growth_html += "<div style='background: white; padding: 1rem; border-radius: 6px; border: 2px solid #93c5fd; text-align: center;'>"
                            growth_html += "<div style='font-size: 0.65rem; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.5rem;'>BASE CASE</div>"
                            growth_html += f"<div style='font-size: 1.75rem; font-weight: 700; color: #3b82f6; margin-bottom: 0.25rem;'>{base:.1f}%</div>"
                            growth_html += "<div style='font-size: 0.65rem; color: #94a3b8;'>Blended estimate</div>"
                            growth_html += "</div>"

                            # Bull Case Card
                            growth_html += "<div style='background: white; padding: 1rem; border-radius: 6px; border: 2px solid #6ee7b7; text-align: center;'>"
                            growth_html += "<div style='font-size: 0.65rem; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.5rem;'>BULL CASE</div>"
                            growth_html += f"<div style='font-size: 1.75rem; font-weight: 700; color: #10b981; margin-bottom: 0.25rem;'>{bull:.1f}%</div>"
                            growth_html += "<div style='font-size: 0.65rem; color: #94a3b8;'>Base + volatility</div>"
                            growth_html += "</div>"

                            growth_html += "</div>"

                            # Growth Scenario Spectrum - Horizontal bars
                            growth_html += "<div style='margin-top: 1rem;'>"
                            growth_html += "<div style='font-size: 0.7rem; font-weight: 600; color: #64748b; margin-bottom: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px;'>GROWTH SCENARIO SPECTRUM</div>"

                            # Calculate max value for consistent scale
                            max_val = max(abs(bear), abs(base), abs(bull), 25)
                            bear_width_pct = (abs(bear) / max_val * 100) if bear >= 0 else 0
                            base_width_pct = (abs(base) / max_val * 100) if base >= 0 else 0
                            bull_width_pct = (abs(bull) / max_val * 100) if bull >= 0 else 0

                            # Bear bar
                            growth_html += "<div style='margin-bottom: 0.75rem;'>"
                            growth_html += "<div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;'>"
                            growth_html += "<span style='font-size: 0.7rem; font-weight: 600; color: #475569;'>Bear</span>"
                            growth_html += f"<span style='font-size: 0.7rem; font-weight: 700; color: #ef4444;'>{bear:.1f}%</span>"
                            growth_html += "</div>"
                            growth_html += "<div style='height: 10px; background: #fee2e2; border-radius: 5px; overflow: hidden;'>"
                            growth_html += f"<div style='height: 100%; width: {bear_width_pct}%; background: linear-gradient(90deg, #ef4444, #dc2626); border-radius: 5px;'></div>"
                            growth_html += "</div></div>"

                            # Base bar
                            growth_html += "<div style='margin-bottom: 0.75rem;'>"
                            growth_html += "<div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;'>"
                            growth_html += "<span style='font-size: 0.7rem; font-weight: 600; color: #475569;'>Base</span>"
                            growth_html += f"<span style='font-size: 0.7rem; font-weight: 700; color: #3b82f6;'>{base:.1f}%</span>"
                            growth_html += "</div>"
                            growth_html += "<div style='height: 10px; background: #dbeafe; border-radius: 5px; overflow: hidden;'>"
                            growth_html += f"<div style='height: 100%; width: {base_width_pct}%; background: linear-gradient(90deg, #3b82f6, #2563eb); border-radius: 5px;'></div>"
                            growth_html += "</div></div>"

                            # Bull bar
                            growth_html += "<div style='margin-bottom: 0.5rem;'>"
                            growth_html += "<div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;'>"
                            growth_html += "<span style='font-size: 0.7rem; font-weight: 600; color: #475569;'>Bull</span>"
                            growth_html += f"<span style='font-size: 0.7rem; font-weight: 700; color: #10b981;'>{bull:.1f}%</span>"
                            growth_html += "</div>"
                            growth_html += "<div style='height: 10px; background: #d1fae5; border-radius: 5px; overflow: hidden;'>"
                            growth_html += f"<div style='height: 100%; width: {bull_width_pct}%; background: linear-gradient(90deg, #10b981, #059669); border-radius: 5px;'></div>"
                            growth_html += "</div></div>"

                            growth_html += "</div></div>"

                            st.markdown(growth_html, unsafe_allow_html=True)

                            # Estimator weights with visual bars
                            if weights:
                                st.markdown("""
                                <div style='font-size: 0.7rem; font-weight: 600; color: #64748b; margin: 1rem 0 0.5rem 0;'>ESTIMATOR WEIGHTS</div>
                                """, unsafe_allow_html=True)

                                for estimator, weight in weights.items():
                                    weight_pct = weight * 100
                                    bar_color = {'historical': '#8b5cf6', 'fundamental': '#06b6d4', 'consensus': '#f59e0b'}.get(estimator.lower(), '#64748b')
                                    st.markdown(f"""
                                    <div style='margin-bottom: 0.5rem;'>
                                        <div style='display: flex; justify-content: space-between; margin-bottom: 0.15rem;'>
                                            <span style='font-size: 0.7rem; font-weight: 600; color: #475569;'>{estimator.title()}</span>
                                            <span style='font-size: 0.7rem; font-weight: 700; color: {bar_color};'>{weight_pct:.1f}%</span>
                                        </div>
                                        <div style='height: 6px; background: #e2e8f0; border-radius: 3px; overflow: hidden;'>
                                            <div style='height: 100%; width: {weight_pct}%; background: {bar_color}; border-radius: 3px;'></div>
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)

                            # Volatility indicator with gauge
                            if volatility:
                                volatility_pct = volatility * 100
                                # Determine volatility level
                                if volatility_pct < 5:
                                    vol_level = "Low"
                                    vol_color = "#10b981"
                                elif volatility_pct < 10:
                                    vol_level = "Medium"
                                    vol_color = "#f59e0b"
                                else:
                                    vol_level = "High"
                                    vol_color = "#ef4444"

                                vol_bar_width = min(volatility_pct * 4, 100)  # Scale for visual

                                st.markdown(f"""
                                <div style='margin: 1rem 0 0.5rem 0;'>
                                    <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;'>
                                        <span style='font-size: 0.7rem; font-weight: 600; color: #64748b;'>GROWTH VOLATILITY (σ)</span>
                                        <span style='display: inline-block; padding: 2px 6px; background: {vol_color}; color: white; border-radius: 3px; font-weight: 600; font-size: 0.65rem;'>{vol_level}</span>
                                    </div>
                                    <div style='display: flex; align-items: center; gap: 0.5rem;'>
                                        <div style='flex: 1; height: 8px; background: linear-gradient(90deg, #10b981 0%, #f59e0b 50%, #ef4444 100%); border-radius: 4px; position: relative;'>
                                            <div style='position: absolute; left: {vol_bar_width}%; top: 50%; transform: translate(-50%, -50%); width: 4px; height: 14px; background: white; border: 2px solid #0f172a; border-radius: 2px; box-shadow: 0 2px 4px rgba(0,0,0,0.3);'></div>
                                        </div>
                                        <span style='font-size: 0.75rem; font-weight: 700; color: {vol_color}; min-width: 3rem; text-align: right;'>{volatility_pct:.1f}%</span>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)

                        st.markdown("<br>", unsafe_allow_html=True)

                        # Second row: PEG Ratio + Intrinsic Value PEG-Forward
                        # Check if PEG is in outliers - if so, skip this section
                        robust_val_check = intrinsic.get('robust_valuation', {})
                        outlier_methods_list = robust_val_check.get('outlier_methods', [])
                        peg_is_outlier_check = any('PEG' in om or 'peg' in om.lower() for om in outlier_methods_list)

                        # Initialize PEG variables BEFORE conditional to avoid NameError
                        peg_ratio = None
                        pe_ratio = None
                        eps_growth = None

                        if not peg_is_outlier_check:
                            st.markdown("")  # Spacing

                            # Get PEG and related data from correct location
                            if 'valuation_multiples' in intrinsic:
                                company_vals = intrinsic['valuation_multiples'].get('company', {})
                                peg_ratio = company_vals.get('peg', None)
                                pe_ratio = company_vals.get('pe', None)
                                eps_growth = company_vals.get('eps_growth_%', None)

                        if peg_ratio and peg_ratio > 0 and not peg_is_outlier_check:
                            # PEG-based valuation ONLY makes sense for growth companies (5% <= growth <= 100%)
                            # For low/no growth companies, PEG is meaningless
                            # Example: Growth 0.4% → Fair PEG 1.0 would imply PE of 0.4x (absurd)
                            # For extreme growth (>100%), it's usually a one-time turnaround, not sustainable
                            # Example: Growth 1352% → Likely losses-to-profits transition, not real growth rate

                            if eps_growth and eps_growth >= 5 and eps_growth <= 100:
                                # Calculate PEG-based Intrinsic Value for GROWTH companies
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
                                        st.caption(f"PEG: {peg_ratio:.2f} | EPS Growth: {eps_growth:.1f}%")
                                with col_peg2:
                                    st.markdown(f"### {peg_color} **{peg_label}**")
                                    st.caption(f"*Fair PEG = 1.0 (conservador)*")
                                with col_peg3:
                                    if peg_intrinsic_growth:
                                        upside_growth = ((peg_intrinsic_growth - current_price) / current_price) * 100
                                        st.caption(f"**Growth PEG 1.5:** ${peg_intrinsic_growth:.2f} ({upside_growth:+.1f}%)")
                                    st.caption("*Premium para empresas de alto crecimiento*")
                            else:
                                # PEG valuation not applicable for low growth OR extreme growth
                                if eps_growth and eps_growth > 100:
                                    # Extreme growth spike (likely one-time turnaround)
                                    st.warning(f"**PEG Valuation Not Applicable:** EPS Growth {eps_growth:.1f}% (> 100% threshold)")
                                    st.caption("Extreme growth rates usually indicate one-time events (losses-to-profits, restructuring, etc.) rather than sustainable growth.")
                                    st.caption(f"Current PEG: **{peg_ratio:.2f}** — Use DCF or sector comparables for valuation instead.")
                                else:
                                    # Low/No growth company
                                    st.warning(f"**PEG Valuation Not Applicable:** EPS Growth {eps_growth:.1f}% (< 5% threshold)")
                                    st.caption("PEG-based valuation only works for growth companies. For mature/declining companies, use DCF or P/E multiples.")
                                    st.caption(f"Current PEG: **{peg_ratio:.2f}** (High PEG with low growth = overvalued)")
                        else:
                            if not peg_is_outlier_check:
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

                        # Check if robust valuation exists and if price is premium-priced
                        robust_valuation = intrinsic.get('robust_valuation', {})
                        outlier_methods = robust_valuation.get('outlier_methods', [])
                        peg_is_outlier = any('PEG' in om or 'peg' in om.lower() for om in outlier_methods)
                        robust_p90 = robust_valuation.get('range_p90', 0)
                        robust_fv = robust_valuation.get('fair_value_robust', 0)
                        percentile_info = intrinsic.get('percentile_info', {})
                        positioning = percentile_info.get('positioning', '')

                        # Determine predominant method
                        # Priority 0: If robust FV exists AND price is premium-priced, use Robust FV
                        if robust_fv and 'above p90' in positioning.lower():
                            # Price above robust range - Robust FV is base, PEG is bull case
                            method_icon = ""
                            method_name = "Robust FV (Price at premium)"
                            peg_value = intrinsic.get('peg_value', 0)
                            range_p10 = robust_valuation.get('range_p10', 0)
                            method_reason = f"""
**Price is above robust valuation range - premium-priced:**

**Valoración Base (Robust FV):**
- Fair Value Robusto: ${robust_fv:.0f} (consenso de múltiples métodos)
- Rango base (p10–p90): ${range_p10:.0f}–${robust_p90:.0f}
- Precio actual: ${current_price:.0f} → Above p90 (premium-priced)

**PEG Bull Case:**
- PEG Fair Value: ${peg_value:.0f}{"" if not peg_ratio else f" (PEG={peg_ratio:.2f})"} ← Escenario si mercado paga premium por crecimiento
- PEG 1.5 premium: ${intrinsic.get('peg_intrinsic_conservative', peg_value * 1.53):.0f}

**Interpretación:**
- Valoración base: ${robust_fv:.0f} (consenso robusto)
- Precio actual ≈ PEG bull case (mercado ya pricing growth premium)
- Valuation base: premium-priced; requiere ejecución y/o momentum para justificar la prima
"""
                        # Priority 1: If PEG < 1.5 AND within robust range AND price reasonable
                        elif peg_ratio and peg_ratio < 1.5 and not peg_is_outlier and 'above p90' not in positioning.lower():
                            # Growth company - PEG is king AND validated by robust range
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
                        elif peg_ratio and peg_ratio < 1.5 and peg_is_outlier:
                            # PEG is low but outside robust range = Bull/Premium case only
                            method_icon = ""
                            method_name = "Robust FV (PEG = escenario bull, no base)"
                            peg_value = intrinsic.get('peg_value', 0)
                            robust_fv = robust_valuation.get('fair_value_robust', 0)
                            range_p10 = robust_valuation.get('range_p10', 0)
                            method_reason = f"""
**PEG sugiere escenario premium, pero el consenso robusto difiere:**

**Valoración Base (Robust FV):**
- Fair Value Robusto: ${robust_fv:.0f} (basado en cash flows y enterprise multiples)
- Rango base (p10–p90): ${range_p10:.0f}–${robust_p90:.0f}

**Escenario Bull (PEG):**
- PEG Ratio: {peg_ratio:.2f} (< 1.5 = Growth at reasonable price)
- PEG Fair Value: ${peg_value:.0f} ← Escenario premium si ejecutan crecimiento

**Interpretación:**
- Si el mercado paga múltiplos premium por crecimiento → target ~${peg_value:.0f}
- Consenso de métodos conservadores (DCF, EV/EBIT, EV/FCF) → rango ${range_p10:.0f}–${robust_p90:.0f}
- Use robust FV como base, PEG como upside potencial
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
  - Growth limitado PEG pierde relevancia
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
                                    if note.startswith(''):
                                        st.success(note)
                                    elif note.startswith('') or 'ERROR' in note or 'failed' in note.lower():
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
                            # Si PEG < 1.5 y Growth > 10% VERDE, sin importar DCF

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
                                    # PEG = P/E / Growth Growth = P/E / PEG
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

                            # === PEG OVERRIDE DISABLED ===
                            # Removed: PEG override logic contradicts robust FV engine
                            # PEG can inform bull/premium case, but doesn't redefine fair value base
                            # Valuation verdict now comes from robust FV vs price percentiles
                            peg_hammer_triggered = False
                            growth_override_applied = False

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

                            # Adjust conviction if multiples reliability is low
                            robust_valuation_check = intrinsic.get('robust_valuation', {})
                            multiples_reliability_check = robust_valuation_check.get('multiples_reliability', 'Medium')

                            if multiples_reliability_check == 'Low' and confidence.lower() == 'high':
                                conviction_display = "MEDIUM-HIGH"
                            else:
                                conviction_display = confidence.upper()

                            # Get upside/downside label with benchmark from percentile_info (if available)
                            percentile_info = intrinsic.get('percentile_info', {})
                            downside_label_full = percentile_info.get('downside_label', '')

                            # Build display text with explicit benchmark
                            if downside_label_full:
                                # downside_label_full is like "Downside to p90: -19.9%" or "Upside to p90: +25.0%"
                                # Use it as-is (already includes percentage)
                                upside_display = downside_label_full
                            elif growth_override_applied and upside > 0:
                                upside_display = f"{upside:+.1f}% Upside Potential"
                            else:
                                upside_text = 'upside' if upside > 0 else 'downside'
                                upside_display = f"{upside:+.1f}% {upside_text}"

                            # Create professional card for valuation summary
                            if color == 'green':
                                bg_gradient = 'linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%)'
                                text_color = '#065f46'
                                border_color = '#10b981'
                                badge_bg = '#10b981'
                            elif color == 'red':
                                bg_gradient = 'linear-gradient(135deg, #fee2e2 0%, #fecaca 100%)'
                                text_color = '#991b1b'
                                border_color = '#ef4444'
                                badge_bg = '#ef4444'
                            else:
                                bg_gradient = 'linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)'
                                text_color = '#92400e'
                                border_color = '#f59e0b'
                                badge_bg = '#f59e0b'

                            # Professional panel-based display for valuation verdict
                            st.markdown("""
                            <div style='font-weight: 700; color: #0f172a; font-size: 0.95rem; margin-bottom: 0.75rem; margin-top: 1rem;'>
                                Valuation Verdict
                            </div>
                            """, unsafe_allow_html=True)

                            # Extract percentage value for delta display
                            import re
                            delta_match = re.search(r'([+-]?\d+\.?\d*)%', upside_display)
                            delta_value = delta_match.group(1) if delta_match else None

                            # Determine colors based on assessment
                            if 'undervalued' in display_assessment.lower():
                                assessment_color = '#10b981'
                                assessment_bg = '#d1fae5'
                                assessment_icon = '▲'
                            elif 'overvalued' in display_assessment.lower():
                                assessment_color = '#ef4444'
                                assessment_bg = '#fee2e2'
                                assessment_icon = '▼'
                            else:
                                assessment_color = '#f59e0b'
                                assessment_bg = '#fef3c7'
                                assessment_icon = '●'

                            # Conviction badge color
                            conviction_colors = {
                                'HIGH': '#10b981',
                                'MEDIUM-HIGH': '#3b82f6',
                                'MEDIUM': '#f59e0b',
                                'LOW': '#ef4444'
                            }
                            conviction_bg_colors = {
                                'HIGH': '#d1fae5',
                                'MEDIUM-HIGH': '#dbeafe',
                                'MEDIUM': '#fef3c7',
                                'LOW': '#fee2e2'
                            }
                            conviction_color = conviction_colors.get(conviction_display, '#64748b')
                            conviction_bg = conviction_bg_colors.get(conviction_display, '#f1f5f9')

                            col_val1, col_val2, col_val3 = st.columns(3)

                            with col_val1:
                                st.metric("Assessment", display_assessment, help="Valuation assessment based on robust multi-method analysis")

                            with col_val2:
                                st.metric("Conviction", conviction_display, help="Confidence level in the valuation assessment")

                            with col_val3:
                                # Clean display for Target vs Price
                                if delta_value:
                                    delta_float = float(delta_value)
                                    delta_display = f"{delta_float:+.1f}%"
                                    label_text = "Downside to p90" if delta_float < 0 else "Upside to p90"
                                else:
                                    delta_display = upside_display
                                    label_text = "Target vs Price"

                                st.metric(label_text, delta_display,
                                         help=downside_label_full if downside_label_full else "Return potential to robust p90 fair value")

                            # Visual verdict card with assessment indicator
                            if delta_value:
                                delta_float = float(delta_value)
                                delta_arrow = '↑' if delta_float > 0 else '↓'
                                delta_color = '#10b981' if delta_float > 0 else '#ef4444'
                            else:
                                delta_arrow = ''
                                delta_color = '#64748b'

                            st.markdown(f"""
                            <div style='background: {assessment_bg}; border-left: 4px solid {assessment_color}; padding: 0.75rem; border-radius: 4px; margin: 0.75rem 0;'>
                                <div style='display: flex; align-items: center; justify-content: space-between;'>
                                    <div style='display: flex; align-items: center; gap: 0.5rem;'>
                                        <div style='font-size: 1.25rem; color: {assessment_color};'>{assessment_icon}</div>
                                        <div>
                                            <div style='font-weight: 700; color: {assessment_color}; font-size: 0.85rem;'>{display_assessment.upper()}</div>
                                            <div style='font-size: 0.65rem; color: #64748b; margin-top: 0.15rem;'>Industry: {industry_profile}</div>
                                        </div>
                                    </div>
                                    <div style='text-align: right;'>
                                        <div style='display: inline-block; padding: 3px 8px; background: {conviction_color}; color: white; border-radius: 4px; font-weight: 700; font-size: 0.7rem;'>{conviction_display}</div>
                                        <div style='font-size: 0.65rem; color: #64748b; margin-top: 0.15rem;'>Conviction Level</div>
                                    </div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                            # Primary metric indicator
                            st.markdown(f"""
                            <div style='display: inline-block; padding: 4px 10px; background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 0.7rem; margin-bottom: 0.5rem;'>
                                <span style='font-weight: 600; color: #475569;'>Primary Metric:</span>
                                <span style='font-weight: 700; color: #0f172a; margin-left: 0.25rem;'>{primary_metric}</span>
                            </div>
                            """, unsafe_allow_html=True)

                            # Show PEG Hammer explanation if applied
                            if growth_override_applied and growth_override_reason:
                                st.markdown(growth_override_reason, unsafe_allow_html=True)

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

                            # Check if using Growth Engine or fallback
                            projection_source = projections.get('source', 'unknown')
                            estimators_used = projections.get('estimators_used', {})

                            if projection_source == 'growth_engine':
                                source_badge = "<span style='background: #10b981; color: white; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.6rem; font-weight: 700; margin-left: 0.5rem;'>GROWTH ENGINE</span>"
                                source_text = "Robust scenarios using 3 estimators (historical, fundamental, consensus)"
                            else:
                                source_badge = "<span style='background: #6b7280; color: white; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.6rem; font-weight: 700; margin-left: 0.5rem;'>SIMPLE</span>"
                                source_text = "Basic scenarios from recent revenue growth"

                            st.markdown(f"""
                            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 0.7rem 1.1rem; border-radius: 10px; margin-bottom: 1rem;'>
                                <div style='display: flex; align-items: center; gap: 0.5rem;'>
                                    <span style='background: rgba(255,255,255,0.2); padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.6rem; font-weight: 700; color: white; letter-spacing: 0.5px;'>PROJECTIONS</span>
                                    <h4 style='margin: 0; color: white; font-weight: 600; font-size: 0.95rem;'>Price Projections by Scenario</h4>
                                    {source_badge}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                            # Show estimator breakdown if using Growth Engine
                            if projection_source == 'growth_engine' and estimators_used:
                                estimator_text = " | ".join([f"{k.title()}: {v:.1%}" for k, v in estimators_used.items()])
                                st.caption(f"**Estimator Weights:** {estimator_text}")

                                # Enhanced Growth Engine Details in expander
                                growth_engine = intrinsic.get('growth_engine')
                                if growth_engine and growth_engine.get('revenue_growth_5y'):
                                    with st.expander("Growth Engine Breakdown (3-Estimator System)", expanded=False):
                                        rev_growth = growth_engine['revenue_growth_5y']

                                        # Volatility and k factor
                                        sigma = rev_growth.get('volatility', 0)
                                        weights = rev_growth.get('weights', {})

                                        # Determine weighting regime
                                        if sigma > 0.25:
                                            regime = "Event-Driven (σ > 25%)"
                                            regime_color = "#dc2626"
                                        elif sigma > 0.15:
                                            regime = "High Volatility (σ > 15%)"
                                            regime_color = "#f59e0b"
                                        else:
                                            regime = "Base/Stable (σ ≤ 15%)"
                                            regime_color = "#10b981"

                                        st.markdown(f"""
                                        <div style='background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
                                                    padding: 1rem; border-radius: 8px; margin-bottom: 1rem;
                                                    border-left: 4px solid {regime_color};'>
                                            <div style='font-size: 0.75rem; color: #0369a1; font-weight: 700; letter-spacing: 0.5px; margin-bottom: 0.5rem;'>
                                                WEIGHTING REGIME
                                            </div>
                                            <div style='font-size: 1.1rem; color: {regime_color}; font-weight: 700;'>
                                                {regime}
                                            </div>
                                            <div style='font-size: 0.85rem; color: #0c4a6e; margin-top: 0.25rem;'>
                                                Growth Volatility (σ): <strong>{sigma:.1%}</strong>
                                            </div>
                                        </div>
                                        """, unsafe_allow_html=True)

                                        # Individual estimator values
                                        st.markdown("**Individual Growth Estimators:**")

                                        cols_est = st.columns(3)

                                        # Historical
                                        hist_val = rev_growth.get('historical')
                                        if hist_val is not None:
                                            with cols_est[0]:
                                                st.markdown(f"""
                                                <div style='background: #fef3c7; padding: 0.75rem; border-radius: 6px; text-align: center;'>
                                                    <div style='font-size: 0.7rem; color: #92400e; font-weight: 700;'>
                                                        HISTORICAL
                                                    </div>
                                                    <div style='font-size: 1.5rem; color: #78350f; font-weight: 900; font-family: monospace;'>
                                                        {hist_val:.1%}
                                                    </div>
                                                    <div style='font-size: 0.7rem; color: #92400e; margin-top: 0.25rem;'>
                                                        Weight: {weights.get('historical', 0):.0%}
                                                    </div>
                                                </div>
                                                """, unsafe_allow_html=True)
                                                st.caption("Median of 3y/5y/10y log-regression")

                                        # Fundamental
                                        fund_val = rev_growth.get('fundamental')
                                        if fund_val is not None:
                                            with cols_est[1]:
                                                st.markdown(f"""
                                                <div style='background: #ddd6fe; padding: 0.75rem; border-radius: 6px; text-align: center;'>
                                                    <div style='font-size: 0.7rem; color: #5b21b6; font-weight: 700;'>
                                                        FUNDAMENTAL
                                                    </div>
                                                    <div style='font-size: 1.5rem; color: #4c1d95; font-weight: 900; font-family: monospace;'>
                                                        {fund_val:.1%}
                                                    </div>
                                                    <div style='font-size: 0.7rem; color: #5b21b6; margin-top: 0.25rem;'>
                                                        Weight: {weights.get('fundamental', 0):.0%}
                                                    </div>
                                                </div>
                                                """, unsafe_allow_html=True)
                                                st.caption("ROIC × Reinvestment Rate")

                                        # Consensus
                                        cons_val = rev_growth.get('consensus')
                                        if cons_val is not None:
                                            with cols_est[2]:
                                                st.markdown(f"""
                                                <div style='background: #bfdbfe; padding: 0.75rem; border-radius: 6px; text-align: center;'>
                                                    <div style='font-size: 0.7rem; color: #1e40af; font-weight: 700;'>
                                                        CONSENSUS
                                                    </div>
                                                    <div style='font-size: 1.5rem; color: #1e3a8a; font-weight: 900; font-family: monospace;'>
                                                        {cons_val:.1%}
                                                    </div>
                                                    <div style='font-size: 0.7rem; color: #1e40af; margin-top: 0.25rem;'>
                                                        Weight: {weights.get('consensus', 0):.0%}
                                                    </div>
                                                </div>
                                                """, unsafe_allow_html=True)
                                                st.caption("Analyst estimates")

                                        # Blended result and scenarios
                                        st.markdown("---")
                                        st.markdown("**Scenario Construction:**")

                                        blended = rev_growth.get('blended', 0)
                                        bear = rev_growth.get('bear', 0)
                                        bull = rev_growth.get('bull', 0)

                                        # Calculate k factor from scenarios
                                        if sigma and sigma > 0:
                                            k_calc = (bull - blended) / sigma if sigma > 0 else 1.0
                                            k_display = f"{k_calc:.1f}"
                                        else:
                                            k_display = "N/A"

                                        st.markdown(f"""
                                        <div style='background: #f0fdf4; padding: 1rem; border-radius: 8px; border: 2px solid #10b981;'>
                                            <div style='display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem;'>
                                                <div style='text-align: center;'>
                                                    <div style='font-size: 0.7rem; color: #065f46; font-weight: 700;'>BEAR</div>
                                                    <div style='font-size: 1.3rem; color: #047857; font-weight: 900; font-family: monospace;'>{bear:.1%}</div>
                                                    <div style='font-size: 0.65rem; color: #065f46; opacity: 0.8;'>Base - k·σ</div>
                                                </div>
                                                <div style='text-align: center; border-left: 2px solid #6ee7b7; border-right: 2px solid #6ee7b7;'>
                                                    <div style='font-size: 0.7rem; color: #065f46; font-weight: 700;'>BASE</div>
                                                    <div style='font-size: 1.3rem; color: #047857; font-weight: 900; font-family: monospace;'>{blended:.1%}</div>
                                                    <div style='font-size: 0.65rem; color: #065f46; opacity: 0.8;'>Weighted blend</div>
                                                </div>
                                                <div style='text-align: center;'>
                                                    <div style='font-size: 0.7rem; color: #065f46; font-weight: 700;'>BULL</div>
                                                    <div style='font-size: 1.3rem; color: #047857; font-weight: 900; font-family: monospace;'>{bull:.1%}</div>
                                                    <div style='font-size: 0.65rem; color: #065f46; opacity: 0.8;'>Base + k·σ</div>
                                                </div>
                                            </div>
                                            <div style='text-align: center; margin-top: 0.75rem; padding-top: 0.75rem; border-top: 2px solid #6ee7b7;'>
                                                <span style='font-size: 0.75rem; color: #065f46;'>
                                                    Scenario Factor: <strong>k = {k_display}</strong> | Volatility: <strong>σ = {sigma:.1%}</strong>
                                                </span>
                                            </div>
                                        </div>
                                        """, unsafe_allow_html=True)

                                        # Growth engine notes
                                        notes = growth_engine.get('notes', [])
                                        if notes:
                                            st.caption(f"**Notes:** {' • '.join(notes)}")

                                        # Additional explanations for edge cases
                                        explanations = []

                                        # Explain low bear scenario
                                        if bear < 0.02:  # < 2%
                                            k_calc = (bull - blended) / sigma if sigma > 0 else 1.0
                                            explanations.append(
                                                f"**Bear scenario very low ({bear:.1%})**: Base ({blended:.1%}) - k·σ = "
                                                f"{blended:.1%} - ({k_calc:.1f} × {sigma:.1%}) = {bear:.1%}. "
                                                f"With low base growth and volatility, bear compresses near zero."
                                            )

                                        # Explain consensus divergence
                                        if cons_val is not None and (hist_val is not None or fund_val is not None):
                                            avg_hist_fund = []
                                            if hist_val is not None:
                                                avg_hist_fund.append(hist_val)
                                            if fund_val is not None:
                                                avg_hist_fund.append(fund_val)

                                            if avg_hist_fund:
                                                avg = sum(avg_hist_fund) / len(avg_hist_fund)
                                                divergence = abs(cons_val - avg) / avg if avg > 0 else 0

                                                if divergence > 0.5:  # >50% divergence
                                                    explanations.append(
                                                        f"**Consensus unusually {'low' if cons_val < avg else 'high'} "
                                                        f"({cons_val:.1%}) vs hist/fundamental (~{avg:.1%})**: "
                                                        f"Analysts may have different view on near-term execution or market conditions."
                                                    )

                                        if explanations:
                                            st.markdown("<br>".join(explanations), unsafe_allow_html=True)

                            scenarios = projections.get('scenarios', {})

                            if scenarios:
                                # ===========================================================
                                # INTERACTIVE PRICE PROJECTIONS CHART
                                # ===========================================================
                                try:
                                    import plotly.graph_objects as go

                                    # Get current price
                                    current_price = intrinsic.get('current_price', 100)

                                    # Prepare data for chart
                                    timeframes = ['Today', '1 Year', '3 Year', '5 Year']
                                    years_numeric = [0, 1, 3, 5]

                                    fig_proj = go.Figure()

                                    for scenario_name, data in scenarios.items():
                                        # Emoji and color based on scenario
                                        if 'Bear' in scenario_name:
                                            color = '#ef4444'
                                            dash = 'dot'
                                        elif 'Bull' in scenario_name:
                                            color = '#10b981'
                                            dash = 'solid'
                                        else:  # Base
                                            color = '#f59e0b'
                                            dash = 'dash'

                                        # Build price path
                                        prices = [
                                            current_price,
                                            data.get('1Y_target', current_price),
                                            data.get('3Y_target', current_price),
                                            data.get('5Y_target', current_price)
                                        ]

                                        fig_proj.add_trace(go.Scatter(
                                            x=years_numeric,
                                            y=prices,
                                            name=scenario_name,
                                            mode='lines+markers',
                                            line=dict(color=color, width=3, dash=dash),
                                            marker=dict(size=10),
                                            hovertemplate=f'<b>{scenario_name}</b><br>Price: $%{{y:.2f}}<br>Year: %{{x}}<extra></extra>'
                                        ))

                                    # Add current price horizontal line
                                    fig_proj.add_hline(
                                        y=current_price,
                                        line_dash="dash",
                                        line_color="gray",
                                        opacity=0.5,
                                        annotation_text=f"Current: ${current_price:.2f}",
                                        annotation_position="right"
                                    )

                                    fig_proj.update_layout(
                                        height=500,
                                        title=dict(
                                            text='Price Evolution Under Different Growth Scenarios',
                                            font=dict(size=16)
                                        ),
                                        xaxis=dict(
                                            title='Years from Today',
                                            tickmode='array',
                                            tickvals=years_numeric,
                                            ticktext=timeframes
                                        ),
                                        yaxis=dict(
                                            title='Stock Price ($)',
                                            tickformat='$,.0f'
                                        ),
                                        hovermode='x unified',
                                        template='plotly_white',
                                        showlegend=True,
                                        legend=dict(
                                            orientation="h",
                                            yanchor="bottom",
                                            y=1.02,
                                            xanchor="right",
                                            x=1
                                        ),
                                        margin=dict(t=100, b=50, l=50, r=50)
                                    )

                                    st.plotly_chart(fig_proj, use_container_width=True)

                                    # Display scenario details in columns below chart
                                    st.markdown("---")
                                    scenario_names = list(scenarios.keys())
                                    cols = st.columns(len(scenario_names))

                                    for i, (scenario_name, data) in enumerate(scenarios.items()):
                                        with cols[i]:
                                            # Badge based on scenario
                                            if 'Bear' in scenario_name:
                                                badge = '<span style="background: #ef4444; color: white; padding: 0.25rem 0.65rem; border-radius: 4px; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.5px;">BEAR CASE</span>'
                                                bg_color = '#fee2e2'
                                                text_color = '#991b1b'
                                            elif 'Bull' in scenario_name:
                                                badge = '<span style="background: #10b981; color: white; padding: 0.25rem 0.65rem; border-radius: 4px; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.5px;">BULL CASE</span>'
                                                bg_color = '#d1fae5'
                                                text_color = '#065f46'
                                            else:
                                                badge = '<span style="background: #f59e0b; color: white; padding: 0.25rem 0.65rem; border-radius: 4px; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.5px;">BASE CASE</span>'
                                                bg_color = '#fef3c7'
                                                text_color = '#92400e'

                                            st.markdown(f"""
                                            <div style='background: {bg_color}; padding: 1rem; border-radius: 10px; margin-bottom: 0.5rem;'>
                                                <div style='margin-bottom: 0.75rem;'>
                                                    {badge}
                                                </div>
                                                <div style='font-size: 0.85rem; color: {text_color}; opacity: 0.9; font-weight: 500;'>
                                                    {data.get('description', '')}
                                                </div>
                                                <div style='font-size: 0.8rem; color: {text_color}; opacity: 0.8; margin-top: 0.5rem;'>
                                                    Growth: {data.get('growth_assumption', 'N/A')}
                                                </div>
                                            </div>
                                            """, unsafe_allow_html=True)

                                            # Metrics
                                            st.metric("1Y Target", f"${data.get('1Y_target', 0):.2f}",
                                                     delta=data.get('1Y_return', 'N/A'))
                                            st.metric("5Y Target", f"${data.get('5Y_target', 0):.2f}",
                                                     delta=data.get('5Y_cagr', 'N/A') + " CAGR")

                                    st.caption("**Important:** Projections based on fundamental growth assumptions. Not investment advice.")

                                except Exception as e:
                                    st.warning(f"Could not generate price projections chart: {str(e)}")
                                    # Fallback to text display
                                    for scenario_name, data in scenarios.items():
                                        st.markdown(f"**{scenario_name}:** {data.get('description', '')}")

                        # ==========================
                        # NEW ADVANCED METRICS
                        # ==========================

                        st.markdown("---")

                        # ============================================================
                        # ADVANCED FUNDAMENTAL METRICS
                        # ============================================================
                        st.markdown("""
                        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                    padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 1.5rem;'>
                            <div style='display: flex; align-items: center; gap: 0.75rem;'>
                                <span style='background: rgba(255,255,255,0.2); padding: 0.35rem 0.75rem; border-radius: 4px; font-size: 0.7rem; font-weight: 700; color: white; letter-spacing: 0.5px;'>
                                    SECTION 9
                                </span>
                                <h3 style='margin: 0; color: white; font-weight: 600;'>
                                    Advanced Fundamental Analysis
                                </h3>
                            </div>
                            <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem; padding-left: 0.5rem;'>
                                Deep-dive into capital efficiency, earnings quality, profitability, and balance sheet strength
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                        # 1. ROIC vs WACC (Capital Efficiency) - or ROE for financials
                        capital_efficiency = intrinsic.get('capital_efficiency', {})
                        if capital_efficiency:
                            metric_name = capital_efficiency.get('metric_name', 'ROIC')
                            st.markdown(f"#### Capital Efficiency — {metric_name} vs WACC")
                            st.caption("Is the company creating or destroying value? ROIC > WACC = value creation")

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

                            # Show 5-year history with chart
                            history_5y = capital_efficiency.get('history_5y', [])
                            if history_5y and len(history_5y) >= 3:
                                try:
                                    import plotly.graph_objects as go
                                    from datetime import datetime

                                    # Create years array (reversed to show oldest to newest)
                                    current_year = datetime.now().year
                                    years = list(range(current_year - len(history_5y) + 1, current_year + 1))
                                    roic_values = list(reversed(history_5y)) if len(history_5y) > 1 and history_5y[0] > history_5y[-1] else history_5y

                                    fig_roic = go.Figure()

                                    # ROIC line
                                    fig_roic.add_trace(go.Scatter(
                                        x=years,
                                        y=roic_values,
                                        name=metric_name,
                                        mode='lines+markers',
                                        line=dict(color='#667eea', width=3),
                                        marker=dict(size=10, color='#667eea'),
                                        fill='tonexty',
                                        fillcolor='rgba(102, 126, 234, 0.1)'
                                    ))

                                    # WACC reference line
                                    wacc_val = capital_efficiency.get('wacc', 0)
                                    fig_roic.add_trace(go.Scatter(
                                        x=years,
                                        y=[wacc_val] * len(years),
                                        name='WACC (Cost of Capital)',
                                        mode='lines',
                                        line=dict(color='#ef4444', width=2, dash='dash'),
                                        hovertemplate='WACC: %{y:.1f}%<extra></extra>'
                                    ))

                                    fig_roic.update_layout(
                                        height=300,
                                        showlegend=True,
                                        hovermode='x unified',
                                        template='plotly_white',
                                        xaxis_title='Year',
                                        yaxis_title='Percentage (%)',
                                        margin=dict(t=30, b=40, l=50, r=20),
                                        legend=dict(
                                            orientation="h",
                                            yanchor="bottom",
                                            y=1.02,
                                            xanchor="right",
                                            x=1
                                        )
                                    )

                                    st.plotly_chart(fig_roic, use_container_width=True)

                                except Exception as e:
                                    # Fallback to text if chart fails
                                    st.caption(f"**{metric_name} History (last {len(history_5y)} years):** " +
                                             ", ".join([f"{h:.1f}%" for h in history_5y]))
                            elif history_5y:
                                st.caption(f"**{metric_name} History (last {len(history_5y)} years):** " +
                                         ", ".join([f"{h:.1f}%" for h in history_5y]))

                            assessment = capital_efficiency.get('assessment', '')
                            value_creation = capital_efficiency.get('value_creation', False)

                            if value_creation:
                                st.success(f" {assessment} - {metric_name} exceeds WACC, indicating value creation")
                            else:
                                st.error(f" {assessment} - {metric_name} below WACC, may be destroying value")

                        # 2. Quality of Earnings (Enhanced with Historical Charts)
                        earnings_quality = intrinsic.get('earnings_quality', {})
                        if earnings_quality:
                            st.markdown("""
                            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                        padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 1rem; margin-top: 2rem;'>
                                <div style='display: flex; align-items: center; gap: 0.75rem;'>
                                    <span style='background: rgba(255,255,255,0.2); padding: 0.35rem 0.75rem; border-radius: 4px; font-size: 0.7rem; font-weight: 700; color: white; letter-spacing: 0.5px;'>
                                        EARNINGS QUALITY
                                    </span>
                                    <h4 style='margin: 0; color: white; font-weight: 600;'>
                                        Quality of Earnings
                                    </h4>
                                </div>
                                <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.85rem; padding-left: 0.5rem;'>
                                    Are earnings backed by real cash flow or accounting tricks?
                                </p>
                            </div>
                            """, unsafe_allow_html=True)

                            # Current metrics in cards
                            col1, col2, col3, col4 = st.columns(4)

                            with col1:
                                cf_to_ni = earnings_quality.get('cash_flow_to_net_income', 0)

                                # Determine color based on quality
                                if cf_to_ni >= 1.0:
                                    metric_color = '#10b981'
                                    quality_label = 'EXCELLENT'
                                elif cf_to_ni >= 0.8:
                                    metric_color = '#3b82f6'
                                    quality_label = 'GOOD'
                                elif cf_to_ni >= 0.6:
                                    metric_color = '#f59e0b'
                                    quality_label = 'FAIR'
                                else:
                                    metric_color = '#ef4444'
                                    quality_label = 'POOR'

                                st.markdown(f"""
                                <div style='background: white; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;'>
                                    <div style='font-size: 0.75rem; color: #64748b; margin-bottom: 0.5rem; font-weight: 600;'>
                                        OCF / NET INCOME
                                    </div>
                                    <div style='font-size: 2rem; font-weight: 700; color: {metric_color}; margin-bottom: 0.25rem;'>
                                        {cf_to_ni:.2f}
                                    </div>
                                    <div style='font-size: 0.7rem; padding: 0.25rem 0.5rem; background: {metric_color}; color: white; border-radius: 3px; display: inline-block;'>
                                        {quality_label}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                                st.caption(">1.0 is excellent")

                            with col2:
                                accruals = earnings_quality.get('accruals_ratio', 0)

                                # Determine color (lower is better for accruals)
                                if accruals < 5:
                                    acc_color = '#10b981'
                                    acc_label = 'GOOD'
                                elif accruals < 10:
                                    acc_color = '#f59e0b'
                                    acc_label = 'MODERATE'
                                else:
                                    acc_color = '#ef4444'
                                    acc_label = 'HIGH'

                                st.markdown(f"""
                                <div style='background: white; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;'>
                                    <div style='font-size: 0.75rem; color: #64748b; margin-bottom: 0.5rem; font-weight: 600;'>
                                        ACCRUALS RATIO
                                    </div>
                                    <div style='font-size: 2rem; font-weight: 700; color: {acc_color}; margin-bottom: 0.25rem;'>
                                        {accruals:.1f}%
                                    </div>
                                    <div style='font-size: 0.7rem; padding: 0.25rem 0.5rem; background: {acc_color}; color: white; border-radius: 3px; display: inline-block;'>
                                        {acc_label}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                                st.caption("<5% is good")

                            with col3:
                                wc_trend = earnings_quality.get('working_capital_trend', 'unknown')

                                # Determine color based on trend
                                if wc_trend.lower() == 'improving':
                                    wc_color = '#10b981'
                                    wc_icon = '↗'
                                elif wc_trend.lower() == 'stable':
                                    wc_color = '#3b82f6'
                                    wc_icon = ''
                                elif wc_trend.lower() == 'deteriorating':
                                    wc_color = '#ef4444'
                                    wc_icon = '↘'
                                else:
                                    wc_color = '#6b7280'
                                    wc_icon = '?'

                                st.markdown(f"""
                                <div style='background: white; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;'>
                                    <div style='font-size: 0.75rem; color: #64748b; margin-bottom: 0.5rem; font-weight: 600;'>
                                        WORKING CAPITAL
                                    </div>
                                    <div style='font-size: 2rem; font-weight: 700; color: {wc_color}; margin-bottom: 0.25rem;'>
                                        {wc_icon}
                                    </div>
                                    <div style='font-size: 0.8rem; color: {wc_color}; font-weight: 600;'>
                                        {wc_trend.title()}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)

                            with col4:
                                grade = earnings_quality.get('grade', 'C')
                                assessment_eq = earnings_quality.get('assessment', '')

                                # Color grade
                                if grade == 'A':
                                    grade_color = '#10b981'
                                    grade_bg = '#d1fae5'
                                elif grade == 'B':
                                    grade_color = '#3b82f6'
                                    grade_bg = '#dbeafe'
                                elif grade == 'C':
                                    grade_color = '#f59e0b'
                                    grade_bg = '#fef3c7'
                                else:
                                    grade_color = '#ef4444'
                                    grade_bg = '#fee2e2'

                                st.markdown(f"""
                                <div style='background: {grade_bg}; padding: 1rem; border-radius: 8px; border: 2px solid {grade_color}; text-align: center;'>
                                    <div style='font-size: 0.75rem; color: #64748b; margin-bottom: 0.5rem; font-weight: 600;'>
                                        OVERALL GRADE
                                    </div>
                                    <div style='font-size: 3rem; font-weight: 700; color: {grade_color}; line-height: 1;'>
                                        {grade}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                                if assessment_eq:
                                    st.caption(assessment_eq)

                            # Show issues if any
                            issues = earnings_quality.get('issues', [])
                            if issues:
                                st.markdown("<br>", unsafe_allow_html=True)
                                with st.expander("Quality Issues Detected", expanded=True):
                                    for issue in issues:
                                        st.warning(f"• {issue}")

                            # Historical Charts
                            st.markdown("---")
                            st.markdown("**Historical Earnings Quality Trends (5 Years)**")

                            try:
                                # Get historical financial data
                                if 'fmp_client' in st.session_state:
                                    fmp_client_eq = st.session_state['fmp_client']
                                else:
                                    # Create FMP client on the fly
                                    from screener.ingest import FMPClient
                                    import yaml
                                    config_file = 'settings_premium.yaml' if os.path.exists('settings_premium.yaml') else 'settings.yaml'
                                    with open(config_file, 'r') as f:
                                        config = yaml.safe_load(f)
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
                                        fmp_client_eq = FMPClient(api_key, config)
                                    else:
                                        fmp_client_eq = None

                                if fmp_client_eq:
                                    # Fetch income statement and cash flow
                                    income_statements = fmp_client_eq.get_income_statement(selected_ticker, limit=5)
                                    cash_flows = fmp_client_eq.get_cash_flow(selected_ticker, limit=5)
                                    balance_sheets = fmp_client_eq.get_balance_sheet(selected_ticker, limit=5)

                                    if income_statements and cash_flows and len(income_statements) > 0 and len(cash_flows) > 0:
                                        # Reverse to get chronological order
                                        income_statements.reverse()
                                        cash_flows.reverse()
                                        balance_sheets.reverse()

                                        # Extract data
                                        years_eq = [is_item.get('calendarYear', 'N/A') for is_item in income_statements]
                                        net_incomes = [is_item.get('netIncome', 0) for is_item in income_statements]
                                        ocfs = [cf_item.get('operatingCashFlow', 0) for cf_item in cash_flows]

                                        # Calculate OCF/NI ratio
                                        ocf_ni_ratios = []
                                        for ni, ocf in zip(net_incomes, ocfs):
                                            if ni and ni != 0:
                                                ocf_ni_ratios.append(ocf / ni)
                                            else:
                                                ocf_ni_ratios.append(0)

                                        # Calculate accruals (simplified: (NI - OCF) / Total Assets)
                                        accruals_ratios = []
                                        for i, (ni, ocf) in enumerate(zip(net_incomes, ocfs)):
                                            if i < len(balance_sheets):
                                                total_assets = balance_sheets[i].get('totalAssets', 1)
                                                if total_assets and total_assets > 0:
                                                    accrual = ((ni - ocf) / total_assets) * 100
                                                    accruals_ratios.append(abs(accrual))
                                                else:
                                                    accruals_ratios.append(0)
                                            else:
                                                accruals_ratios.append(0)

                                        # Chart 1: OCF/NI Ratio Evolution
                                        import plotly.graph_objects as go

                                        fig_ocf_ni = go.Figure()
                                        fig_ocf_ni.add_trace(go.Scatter(
                                            x=years_eq,
                                            y=ocf_ni_ratios,
                                            mode='lines+markers',
                                            name='OCF/NI Ratio',
                                            line=dict(color='#667eea', width=3),
                                            marker=dict(size=10, color='#667eea'),
                                            fill='tonexty',
                                            fillcolor='rgba(102, 126, 234, 0.1)'
                                        ))

                                        # Add reference line at 1.0
                                        fig_ocf_ni.add_hline(
                                            y=1.0,
                                            line_dash="dash",
                                            line_color="#10b981",
                                            annotation_text="Excellent (1.0)",
                                            annotation_position="right"
                                        )

                                        fig_ocf_ni.update_layout(
                                            title="OCF / Net Income Ratio Evolution",
                                            xaxis_title="Year",
                                            yaxis_title="Ratio",
                                            height=400,
                                            hovermode='x unified',
                                            plot_bgcolor='white',
                                            paper_bgcolor='white',
                                            font=dict(size=12)
                                        )

                                        fig_ocf_ni.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#f0f0f0')
                                        fig_ocf_ni.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#f0f0f0')

                                        st.plotly_chart(fig_ocf_ni, use_container_width=True)

                                        # Chart 2: Accruals Ratio Evolution
                                        fig_accruals = go.Figure()
                                        fig_accruals.add_trace(go.Bar(
                                            x=years_eq,
                                            y=accruals_ratios,
                                            name='Accruals Ratio',
                                            marker=dict(
                                                color=accruals_ratios,
                                                colorscale=[[0, '#10b981'], [0.5, '#f59e0b'], [1, '#ef4444']],
                                                showscale=False
                                            )
                                        ))

                                        # Add reference line at 5%
                                        fig_accruals.add_hline(
                                            y=5,
                                            line_dash="dash",
                                            line_color="#10b981",
                                            annotation_text="Good (<5%)",
                                            annotation_position="right"
                                        )

                                        fig_accruals.update_layout(
                                            title="Accruals Ratio Evolution (Lower is Better)",
                                            xaxis_title="Year",
                                            yaxis_title="Accruals %",
                                            height=400,
                                            hovermode='x unified',
                                            plot_bgcolor='white',
                                            paper_bgcolor='white',
                                            font=dict(size=12)
                                        )

                                        fig_accruals.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#f0f0f0')
                                        fig_accruals.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#f0f0f0')

                                        st.plotly_chart(fig_accruals, use_container_width=True)

                                        # Chart 3: OCF vs Net Income Comparison
                                        fig_comparison = go.Figure()

                                        fig_comparison.add_trace(go.Bar(
                                            x=years_eq,
                                            y=[ocf/1e6 for ocf in ocfs],
                                            name='Operating Cash Flow',
                                            marker_color='#10b981'
                                        ))

                                        fig_comparison.add_trace(go.Bar(
                                            x=years_eq,
                                            y=[ni/1e6 for ni in net_incomes],
                                            name='Net Income',
                                            marker_color='#667eea'
                                        ))

                                        fig_comparison.update_layout(
                                            title="Operating Cash Flow vs Net Income (in millions)",
                                            xaxis_title="Year",
                                            yaxis_title="Amount ($M)",
                                            height=400,
                                            barmode='group',
                                            hovermode='x unified',
                                            plot_bgcolor='white',
                                            paper_bgcolor='white',
                                            font=dict(size=12),
                                            legend=dict(
                                                orientation="h",
                                                yanchor="bottom",
                                                y=1.02,
                                                xanchor="right",
                                                x=1
                                            )
                                        )

                                        fig_comparison.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#f0f0f0')
                                        fig_comparison.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#f0f0f0')

                                        st.plotly_chart(fig_comparison, use_container_width=True)

                                        # Summary interpretation
                                        st.markdown("---")
                                        avg_ocf_ni = sum(ocf_ni_ratios) / len(ocf_ni_ratios) if ocf_ni_ratios else 0
                                        avg_accruals = sum(accruals_ratios) / len(accruals_ratios) if accruals_ratios else 0

                                        st.markdown("**5-Year Earnings Quality Summary:**")

                                        col_sum1, col_sum2 = st.columns(2)
                                        with col_sum1:
                                            if avg_ocf_ni >= 1.0:
                                                st.success(f"**Excellent cash conversion:** Average OCF/NI of {avg_ocf_ni:.2f} shows earnings are consistently backed by strong cash flow.")
                                            elif avg_ocf_ni >= 0.8:
                                                st.info(f"**Good cash conversion:** Average OCF/NI of {avg_ocf_ni:.2f} indicates solid earnings quality.")
                                            else:
                                                st.warning(f"**Weak cash conversion:** Average OCF/NI of {avg_ocf_ni:.2f} suggests earnings may include non-cash items or aggressive accounting.")

                                        with col_sum2:
                                            if avg_accruals < 5:
                                                st.success(f"**Low accruals:** Average of {avg_accruals:.1f}% indicates conservative accounting practices.")
                                            elif avg_accruals < 10:
                                                st.info(f"**Moderate accruals:** Average of {avg_accruals:.1f}% is within acceptable range.")
                                            else:
                                                st.warning(f"**High accruals:** Average of {avg_accruals:.1f}% may indicate aggressive accounting or earnings management.")

                                    else:
                                        st.info("Insufficient historical data for charts (need at least 2 years)")
                                else:
                                    st.info("FMP client not available for historical charts")

                            except Exception as e:
                                st.warning(f"Could not generate historical charts: {str(e)}")
                                if st.checkbox("Show error details", key=f"eq_chart_error_{selected_ticker}"):
                                    st.error(traceback.format_exc())

                        # 3. Profitability Analysis (Margins and Trends)
                        profitability = intrinsic.get('profitability_analysis', {})
                        if profitability:
                            # SECTION: Profitability Margins
                            st.markdown("""
                            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                        padding: 1rem 1.5rem; border-radius: 12px; margin: 1.5rem 0 1rem 0;'>
                                <h3 style='margin: 0; color: white; font-weight: 600; font-size: 1.3rem;'>
                                    Profitability Margins Analysis
                                </h3>
                                <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.85rem;'>
                                    Margin expansion indicates pricing power and operational efficiency
                                </p>
                            </div>
                            """, unsafe_allow_html=True)

                            col1, col2, col3 = st.columns(3)

                            with col1:
                                gross = profitability.get('gross_margin', {})
                                if gross:
                                    st.metric("Gross Margin",
                                             f"{gross.get('current', 0):.1f}%",
                                             delta=f"{gross.get('current', 0) - gross.get('avg_3y', 0):.1f}% vs 3Y avg")
                                    st.caption(gross.get('trend', 'stable'))

                            with col2:
                                operating = profitability.get('operating_margin', {})
                                if operating:
                                    st.metric("Operating Margin",
                                             f"{operating.get('current', 0):.1f}%",
                                             delta=f"{operating.get('current', 0) - operating.get('avg_3y', 0):.1f}% vs 3Y avg")
                                    st.caption(operating.get('trend', 'stable'))

                            with col3:
                                fcf = profitability.get('fcf_margin', {})
                                if fcf:
                                    st.metric("FCF Margin",
                                             f"{fcf.get('current', 0):.1f}%",
                                             delta=f"{fcf.get('current', 0) - fcf.get('avg_3y', 0):.1f}% vs 3Y avg")
                                    st.caption(fcf.get('trend', 'stable'))

                            # Margins evolution chart
                            try:
                                import plotly.graph_objects as go

                                # Try to get historical margin data from income statements
                                income_history = fmp_client.get_income_statement(selected_ticker, period='annual', limit=5)

                                if income_history and len(income_history) >= 3:
                                    years_margins = [item.get('calendarYear', 'N/A') for item in reversed(income_history)]
                                    gross_margins = []
                                    operating_margins = []
                                    fcf_margins_calc = []

                                    cash_flow_history = fmp_client.get_cash_flow(selected_ticker, period='annual', limit=5)
                                    fcf_by_year = {}
                                    if cash_flow_history:
                                        for cf_item in cash_flow_history:
                                            year = cf_item.get('calendarYear')
                                            ocf = cf_item.get('operatingCashFlow', 0)
                                            capex = cf_item.get('capitalExpenditure', 0)
                                            fcf = ocf + capex  # capex is negative
                                            fcf_by_year[year] = fcf

                                    for item in reversed(income_history):
                                        revenue = item.get('revenue', 1)
                                        if revenue and revenue > 0:
                                            gross_profit = item.get('grossProfit', 0)
                                            operating_income = item.get('operatingIncome', 0)
                                            gross_margins.append((gross_profit / revenue) * 100)
                                            operating_margins.append((operating_income / revenue) * 100)

                                            year = item.get('calendarYear')
                                            if year in fcf_by_year:
                                                fcf_margins_calc.append((fcf_by_year[year] / revenue) * 100)
                                            else:
                                                fcf_margins_calc.append(None)

                                    fig_margins = go.Figure()

                                    fig_margins.add_trace(go.Scatter(
                                        x=years_margins,
                                        y=gross_margins,
                                        name='Gross Margin',
                                        mode='lines+markers',
                                        line=dict(color='#10b981', width=2),
                                        marker=dict(size=8)
                                    ))

                                    fig_margins.add_trace(go.Scatter(
                                        x=years_margins,
                                        y=operating_margins,
                                        name='Operating Margin',
                                        mode='lines+markers',
                                        line=dict(color='#667eea', width=2),
                                        marker=dict(size=8)
                                    ))

                                    if any(m is not None for m in fcf_margins_calc):
                                        fig_margins.add_trace(go.Scatter(
                                            x=years_margins,
                                            y=fcf_margins_calc,
                                            name='FCF Margin',
                                            mode='lines+markers',
                                            line=dict(color='#f59e0b', width=2),
                                            marker=dict(size=8)
                                        ))

                                    fig_margins.update_layout(
                                        height=350,
                                        showlegend=True,
                                        hovermode='x unified',
                                        template='plotly_white',
                                        xaxis_title='Year',
                                        yaxis_title='Margin (%)',
                                        margin=dict(t=30, b=40, l=50, r=20),
                                        legend=dict(
                                            orientation="h",
                                            yanchor="bottom",
                                            y=1.02,
                                            xanchor="right",
                                            x=1
                                        )
                                    )

                                    st.plotly_chart(fig_margins, use_container_width=True)

                            except Exception as e:
                                pass  # Silent fail - metrics already shown above

                            # ===========================================================
                            # HISTORICAL CHARTS: Revenue, EBIT, FCF Evolution
                            # ===========================================================
                            st.markdown("""
                            <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                                        padding: 1rem 1.5rem; border-radius: 12px; margin: 1.5rem 0 1rem 0;'>
                                <h3 style='margin: 0; color: white; font-weight: 600; font-size: 1.3rem;'>
                                    Historical Financial Performance
                                </h3>
                                <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.85rem;'>
                                    5-year evolution of revenue, profitability, and cash generation
                                </p>
                            </div>
                            """, unsafe_allow_html=True)

                            # Try to get historical data from FMP client
                            try:
                                import plotly.graph_objects as go
                                from plotly.subplots import make_subplots

                                # Get FMP client from session or create new one
                                if 'fmp_client' not in st.session_state:
                                    # Create FMP client (should exist from qualitative analyzer)
                                    from screener.ingest import FMPClient
                                    import os
                                    import yaml

                                    config_file = 'settings_premium.yaml' if os.path.exists('settings_premium.yaml') else 'settings.yaml'
                                    with open(config_file, 'r') as f:
                                        config = yaml.safe_load(f)

                                    api_key = None
                                    if 'FMP_API_KEY' in st.secrets:
                                        api_key = st.secrets['FMP_API_KEY']
                                    elif 'FMP' in st.secrets:
                                        api_key = st.secrets['FMP']
                                    if not api_key:
                                        api_key = os.getenv('FMP_API_KEY')
                                    if not api_key:
                                        api_key = config['fmp'].get('api_key')

                                    fmp_client = FMPClient(api_key, config)
                                else:
                                    fmp_client = st.session_state['fmp_client']

                                # Fetch income statement history (annual, last 10 years)
                                income_stmt = fmp_client.get_income_statement(selected_ticker, period='annual', limit=10)

                                if income_stmt and len(income_stmt) > 0:
                                    # Extract data
                                    years = [item.get('calendarYear', 'N/A') for item in reversed(income_stmt)]
                                    revenue = [item.get('revenue', 0) / 1e6 for item in reversed(income_stmt)]  # In millions
                                    operating_income = [item.get('operatingIncome', 0) / 1e6 for item in reversed(income_stmt)]
                                    net_income = [item.get('netIncome', 0) / 1e6 for item in reversed(income_stmt)]

                                    # Fetch cash flow statement for FCF
                                    cash_flow = fmp_client.get_cash_flow(selected_ticker, period='annual', limit=10)
                                    fcf_values = []
                                    if cash_flow and len(cash_flow) > 0:
                                        for item in reversed(cash_flow):
                                            ocf = item.get('operatingCashFlow', 0)
                                            capex = item.get('capitalExpenditure', 0)
                                            fcf = (ocf + capex) / 1e6  # capex is negative, so we add
                                            fcf_values.append(fcf)

                                    # Create subplots (2 rows)
                                    fig = make_subplots(
                                        rows=2, cols=1,
                                        subplot_titles=('Revenue & Operating Income Evolution', 'Free Cash Flow Evolution'),
                                        vertical_spacing=0.15,
                                        row_heights=[0.55, 0.45]
                                    )

                                    # Row 1: Revenue & Operating Income
                                    fig.add_trace(
                                        go.Bar(x=years, y=revenue, name='Revenue', marker_color='#667eea', opacity=0.8),
                                        row=1, col=1
                                    )
                                    fig.add_trace(
                                        go.Scatter(x=years, y=operating_income, name='Operating Income', mode='lines+markers',
                                                  line=dict(color='#10b981', width=3), marker=dict(size=8)),
                                        row=1, col=1
                                    )

                                    # Row 2: FCF
                                    if fcf_values and len(fcf_values) == len(years):
                                        fig.add_trace(
                                            go.Bar(x=years, y=fcf_values, name='Free Cash Flow',
                                                  marker_color=['#10b981' if v > 0 else '#ef4444' for v in fcf_values]),
                                            row=2, col=1
                                        )

                                    # Update layout
                                    fig.update_xaxes(title_text="Year", row=2, col=1)
                                    fig.update_yaxes(title_text="$ Millions", row=1, col=1)
                                    fig.update_yaxes(title_text="$ Millions", row=2, col=1)

                                    fig.update_layout(
                                        height=700,
                                        showlegend=True,
                                        hovermode='x unified',
                                        template='plotly_white',
                                        margin=dict(t=80, b=50, l=50, r=50)
                                    )

                                    st.plotly_chart(fig, use_container_width=True)

                                    # Add quick stats
                                    if len(revenue) >= 5:
                                        revenue_cagr_5y = (((revenue[-1] / revenue[-5]) ** (1/5)) - 1) * 100
                                        col_stat1, col_stat2, col_stat3 = st.columns(3)

                                        with col_stat1:
                                            st.metric("Revenue CAGR (5Y)", f"{revenue_cagr_5y:+.1f}%")
                                        with col_stat2:
                                            if fcf_values and len(fcf_values) >= 2:
                                                fcf_change = ((fcf_values[-1] / fcf_values[-2]) - 1) * 100 if fcf_values[-2] != 0 else 0
                                                st.metric("FCF Growth (YoY)", f"{fcf_change:+.1f}%")
                                        with col_stat3:
                                            if operating_income and len(operating_income) >= 2:
                                                oi_margin_current = (operating_income[-1] / revenue[-1]) * 100 if revenue[-1] != 0 else 0
                                                oi_margin_prev = (operating_income[-2] / revenue[-2]) * 100 if revenue[-2] != 0 else 0
                                                margin_expansion = oi_margin_current - oi_margin_prev
                                                st.metric("Operating Margin Change", f"{margin_expansion:+.1f}pp",
                                                         help=f"Current: {oi_margin_current:.1f}% vs Prior: {oi_margin_prev:.1f}%")

                                else:
                                    st.info("Historical financial data not available for this ticker")

                            except Exception as e:
                                st.warning(f"Could not generate historical charts: {str(e)}")
                                with st.expander("Show error details"):
                                    st.code(str(e))

                        # 4. Balance Sheet Strength
                        balance_sheet = intrinsic.get('balance_sheet_strength', {})
                        if balance_sheet:
                            # SECTION: Balance Sheet Health
                            st.markdown("""
                            <div style='background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                                        padding: 1rem 1.5rem; border-radius: 12px; margin: 1.5rem 0 1rem 0;'>
                                <h3 style='margin: 0; color: white; font-weight: 600; font-size: 1.3rem;'>
                                    Balance Sheet Strength
                                </h3>
                                <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.85rem;'>
                                    Financial fortress or house of cards? Debt, liquidity, and solvency analysis
                                </p>
                            </div>
                            """, unsafe_allow_html=True)

                            # Overall assessment banner with professional card
                            overall = balance_sheet.get('overall_assessment', 'Unknown')
                            warnings_list = balance_sheet.get('warnings', [])

                            if overall == 'Strong':
                                banner_color = '#d1fae5'
                                banner_text_color = '#065f46'
                                banner_emoji = ''
                                banner_msg = 'Solid financial fortress - Strong liquidity and manageable debt'
                            elif overall == 'Concerning':
                                banner_color = '#fee2e2'
                                banner_text_color = '#991b1b'
                                banner_emoji = ''
                                banner_msg = ', '.join(warnings_list) if warnings_list else 'Financial stress detected'
                            else:
                                banner_color = '#fef3c7'
                                banner_text_color = '#92400e'
                                banner_emoji = ''
                                banner_msg = 'Moderate financial position'

                            st.markdown(f"""
                            <div style='background: {banner_color};
                                        padding: 1rem 1.5rem;
                                        border-radius: 10px;
                                        margin-bottom: 1.5rem;'>
                                <div style='font-size: 1.2rem; font-weight: 600; color: {banner_text_color};'>
                                    {banner_emoji} Overall Assessment: {overall}
                                </div>
                                <div style='font-size: 0.9rem; color: {banner_text_color}; opacity: 0.85; margin-top: 0.25rem;'>
                                    {banner_msg}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

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

                            # ===========================================================
                            # BALANCE SHEET EVOLUTION CHART
                            # ===========================================================
                            st.markdown("---")
                            st.markdown("#### Balance Sheet Evolution (5-10 Years)")
                            st.caption("How has the company's financial position evolved? Assets, liabilities, equity, and debt trends")

                            try:
                                import plotly.graph_objects as go

                                # Fetch balance sheet history
                                balance_sheet_history = fmp_client.get_balance_sheet(selected_ticker, period='annual', limit=10)

                                if balance_sheet_history and len(balance_sheet_history) > 0:
                                    # Extract data
                                    years_bs = [item.get('calendarYear', 'N/A') for item in reversed(balance_sheet_history)]
                                    total_assets = [item.get('totalAssets', 0) / 1e6 for item in reversed(balance_sheet_history)]
                                    total_liabilities = [item.get('totalLiabilities', 0) / 1e6 for item in reversed(balance_sheet_history)]
                                    total_equity = [item.get('totalStockholdersEquity', 0) / 1e6 for item in reversed(balance_sheet_history)]
                                    total_debt = [item.get('totalDebt', 0) / 1e6 for item in reversed(balance_sheet_history)]
                                    cash = [item.get('cashAndCashEquivalents', 0) / 1e6 for item in reversed(balance_sheet_history)]

                                    # Create figure with stacked area chart
                                    fig_bs = go.Figure()

                                    # Assets, Liabilities, Equity as stacked bars
                                    fig_bs.add_trace(go.Bar(
                                        x=years_bs, y=total_assets, name='Total Assets',
                                        marker_color='#667eea', opacity=0.7
                                    ))
                                    fig_bs.add_trace(go.Bar(
                                        x=years_bs, y=total_liabilities, name='Total Liabilities',
                                        marker_color='#ef4444', opacity=0.7
                                    ))
                                    fig_bs.add_trace(go.Bar(
                                        x=years_bs, y=total_equity, name='Total Equity',
                                        marker_color='#10b981', opacity=0.7
                                    ))

                                    # Add debt and cash as lines
                                    fig_bs.add_trace(go.Scatter(
                                        x=years_bs, y=total_debt, name='Total Debt',
                                        mode='lines+markers', line=dict(color='#f59e0b', width=3),
                                        marker=dict(size=8)
                                    ))
                                    fig_bs.add_trace(go.Scatter(
                                        x=years_bs, y=cash, name='Cash & Equivalents',
                                        mode='lines+markers', line=dict(color='#06b6d4', width=3),
                                        marker=dict(size=8)
                                    ))

                                    fig_bs.update_layout(
                                        height=500,
                                        showlegend=True,
                                        hovermode='x unified',
                                        template='plotly_white',
                                        barmode='group',
                                        xaxis_title='Year',
                                        yaxis_title='$ Millions',
                                        margin=dict(t=50, b=50, l=50, r=50)
                                    )

                                    st.plotly_chart(fig_bs, use_container_width=True)

                                    # Key balance sheet metrics
                                    if len(total_assets) >= 2 and len(total_debt) >= 2:
                                        col_bs1, col_bs2, col_bs3 = st.columns(3)

                                        with col_bs1:
                                            debt_to_equity_current = (total_debt[-1] / total_equity[-1]) if total_equity[-1] != 0 else 0
                                            debt_to_equity_prev = (total_debt[-2] / total_equity[-2]) if total_equity[-2] != 0 else 0
                                            debt_trend = debt_to_equity_current - debt_to_equity_prev
                                            st.metric("Debt/Equity Trend",
                                                     f"{debt_to_equity_current:.2f}x",
                                                     delta=f"{debt_trend:+.2f}x vs prior year",
                                                     delta_color="inverse")

                                        with col_bs2:
                                            asset_growth = ((total_assets[-1] / total_assets[-2]) - 1) * 100 if total_assets[-2] != 0 else 0
                                            st.metric("Total Assets Growth (YoY)", f"{asset_growth:+.1f}%")

                                        with col_bs3:
                                            net_debt_current = total_debt[-1] - cash[-1]
                                            net_debt_prev = total_debt[-2] - cash[-2]
                                            net_debt_change = ((net_debt_current - net_debt_prev) / abs(net_debt_prev)) * 100 if net_debt_prev != 0 else 0
                                            st.metric("Net Debt Change (YoY)",
                                                     f"{net_debt_change:+.1f}%",
                                                     help=f"Net Debt: ${net_debt_current:.0f}M",
                                                     delta_color="inverse")

                                else:
                                    st.info("Balance sheet historical data not available")

                            except Exception as e:
                                st.warning(f"Could not generate balance sheet chart: {str(e)}")

                        # 5. Valuation Multiples vs Peers
                        valuation_multiples = intrinsic.get('valuation_multiples', {})
                        if valuation_multiples:
                            # SECTION: Valuation Multiples
                            st.markdown("""
                            <div style='background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
                                        padding: 1rem 1.5rem; border-radius: 12px; margin: 1.5rem 0 1rem 0;'>
                                <h3 style='margin: 0; color: white; font-weight: 600; font-size: 1.3rem;'>
                                    Valuation Multiples vs Peers
                                </h3>
                                <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.85rem;'>
                                    Trading at a premium or discount compared to industry peers?
                                </p>
                            </div>
                            """, unsafe_allow_html=True)

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

                                # Comparative chart: Company vs Peers
                                try:
                                    import plotly.graph_objects as go
                                    from plotly.subplots import make_subplots

                                    metrics_names = []
                                    company_values = []
                                    peer_values = []

                                    for metric_key, metric_name in [('pe', 'P/E'), ('pb', 'P/B'), ('ps', 'P/S'), ('ev_ebitda', 'EV/EBITDA')]:
                                        comp_val = company_vals.get(metric_key)
                                        peer_val = peers_avg.get(metric_key)
                                        if comp_val and peer_val:
                                            metrics_names.append(metric_name)
                                            company_values.append(comp_val)
                                            peer_values.append(peer_val)

                                    if metrics_names:
                                        fig_val = go.Figure()

                                        fig_val.add_trace(go.Bar(
                                            name='Company',
                                            x=metrics_names,
                                            y=company_values,
                                            marker_color='#667eea',
                                            text=[f"{v:.1f}x" for v in company_values],
                                            textposition='outside'
                                        ))

                                        fig_val.add_trace(go.Bar(
                                            name='Peer Average',
                                            x=metrics_names,
                                            y=peer_values,
                                            marker_color='#10b981',
                                            text=[f"{v:.1f}x" for v in peer_values],
                                            textposition='outside'
                                        ))

                                        fig_val.update_layout(
                                            height=300,
                                            barmode='group',
                                            template='plotly_white',
                                            xaxis_title='Valuation Metric',
                                            yaxis_title='Multiple (x)',
                                            margin=dict(t=30, b=40, l=50, r=20),
                                            showlegend=True,
                                            legend=dict(
                                                orientation="h",
                                                yanchor="bottom",
                                                y=1.02,
                                                xanchor="right",
                                                x=1
                                            )
                                        )

                                        st.plotly_chart(fig_val, use_container_width=True)
                                except:
                                    pass  # Silent fail

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
                            # SECTION: Growth Consistency
                            st.markdown("""
                            <div style='background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
                                        padding: 1rem 1.5rem; border-radius: 12px; margin: 1.5rem 0 1rem 0;'>
                                <h3 style='margin: 0; color: #1f2937; font-weight: 600; font-size: 1.3rem;'>
                                    Growth Consistency Analysis
                                </h3>
                                <p style='margin: 0.5rem 0 0 0; color: #374151; opacity: 0.9; font-size: 0.85rem;'>
                                    Steady compounding or volatile roller coaster? 5-year track record
                                </p>
                            </div>
                            """, unsafe_allow_html=True)

                            # Professional card for overall growth assessment
                            overall_assess = growth_consistency.get('overall_assessment', '')

                            if 'Highly Consistent' in overall_assess:
                                growth_bg = '#d1fae5'
                                growth_text = '#065f46'
                                growth_badge_bg = '#10b981'
                                growth_badge_text = 'STRONG'
                            elif 'Volatile' in overall_assess:
                                growth_bg = '#fee2e2'
                                growth_text = '#991b1b'
                                growth_badge_bg = '#ef4444'
                                growth_badge_text = 'VOLATILE'
                            else:
                                growth_bg = '#fef3c7'
                                growth_text = '#92400e'
                                growth_badge_bg = '#f59e0b'
                                growth_badge_text = 'MODERATE'

                            st.markdown(f"""
                            <div style='background: {growth_bg};
                                        padding: 0.75rem 1.25rem;
                                        border-radius: 10px;
                                        margin-bottom: 1rem;'>
                                <div style='display: flex; align-items: center; gap: 0.75rem;'>
                                    <span style='background: {growth_badge_bg}; color: white; padding: 0.25rem 0.6rem; border-radius: 4px; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.5px;'>
                                        {growth_badge_text}
                                    </span>
                                    <span style='font-size: 1rem; font-weight: 600; color: {growth_text};'>
                                        {overall_assess}
                                    </span>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

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
                                st.markdown("#### Free Cash Flow Growth")
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
                            # SECTION: Cash Conversion Cycle
                            st.markdown("""
                            <div style='background: linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%);
                                        padding: 1rem 1.5rem; border-radius: 12px; margin: 1.5rem 0 1rem 0;'>
                                <h3 style='margin: 0; color: white; font-weight: 600; font-size: 1.3rem;'>
                                    Cash Conversion Cycle
                                </h3>
                                <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.85rem;'>
                                    Working capital efficiency - How quickly cash flows through operations
                                </p>
                            </div>
                            """, unsafe_allow_html=True)

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
                                    st.metric("YoY Trend", "Worsening", delta=f"{yoy_change:+.0f} days")
                                else:
                                    st.metric("YoY Trend", "Stable", delta=f"{yoy_change:+.0f} days")

                            st.caption(" Lower CCC = Better working capital efficiency. Negative CCC means suppliers finance operations.")

                        # 8. Operating Leverage (FASE 1)
                        operating_lev = intrinsic.get('operating_leverage', {})
                        if operating_lev:
                            st.markdown("---")
                            # SECTION: Operating Leverage
                            st.markdown("""
                            <div style='background: linear-gradient(135deg, #ffa751 0%, #ffe259 100%);
                                        padding: 1rem 1.5rem; border-radius: 12px; margin: 1.5rem 0 1rem 0;'>
                                <h3 style='margin: 0; color: white; font-weight: 600; font-size: 1.3rem;'>
                                    Operating Leverage
                                </h3>
                                <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.85rem;'>
                                    Cost structure - How profits amplify with revenue changes
                                </p>
                            </div>
                            """, unsafe_allow_html=True)

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
                            # SECTION: Reinvestment Quality
                            st.markdown("""
                            <div style='background: linear-gradient(135deg, #c471f5 0%, #fa71cd 100%);
                                        padding: 1rem 1.5rem; border-radius: 12px; margin: 1.5rem 0 1rem 0;'>
                                <h3 style='margin: 0; color: white; font-weight: 600; font-size: 1.3rem;'>
                                    Reinvestment Quality
                                </h3>
                                <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.85rem;'>
                                    Capital efficiency - How effectively reinvestments drive growth
                                </p>
                            </div>
                            """, unsafe_allow_html=True)

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
                                    st.caption("Poor")

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
                            # SECTION: Economic Profit (EVA)
                            st.markdown("""
                            <div style='background: linear-gradient(135deg, #13547a 0%, #80d0c7 100%);
                                        padding: 1rem 1.5rem; border-radius: 12px; margin: 1.5rem 0 1rem 0;'>
                                <h3 style='margin: 0; color: white; font-weight: 600; font-size: 1.3rem;'>
                                    Economic Profit (EVA)
                                </h3>
                                <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.85rem;'>
                                    Value creation above cost of capital - True economic profit
                                </p>
                            </div>
                            """, unsafe_allow_html=True)

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
                                    st.metric("5Y Avg EVA", avg_eva, delta="Declining")
                                else:
                                    st.metric("5Y Avg EVA", avg_eva, delta="Stable")

                            st.caption(" EVA = NOPAT - (WACC × Invested Capital). Positive EVA = Value creation above cost of capital.")

                        # 11. Capital Allocation Score (FASE 2)
                        cap_alloc = intrinsic.get('capital_allocation', {})
                        if cap_alloc:
                            st.markdown("---")
                            # SECTION: Capital Allocation
                            st.markdown("""
                            <div style='background: linear-gradient(135deg, #3f5efb 0%, #fc466b 100%);
                                        padding: 1rem 1.5rem; border-radius: 12px; margin: 1.5rem 0 1rem 0;'>
                                <h3 style='margin: 0; color: white; font-weight: 600; font-size: 1.3rem;'>
                                    Capital Allocation Scorecard
                                </h3>
                                <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.85rem;'>
                                    Management effectiveness - How cash is deployed and value returned
                                </p>
                            </div>
                            """, unsafe_allow_html=True)

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
                                emoji = "" if share_trend == 'decreasing' else "" if share_trend == 'increasing' else ""
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
                                    st.metric("NIM Trend", "Compressing", delta=f"{yoy:.2f}% YoY")
                                else:
                                    st.metric("NIM Trend", "Stable", delta=f"{yoy:+.2f}% YoY")

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
                            # SECTION: Earnings Call Sentiment
                            st.markdown("""
                            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                        padding: 1rem 1.5rem; border-radius: 12px; margin: 1.5rem 0 1rem 0;'>
                                <h3 style='margin: 0; color: white; font-weight: 600; font-size: 1.3rem;'>
                                    Earnings Call Sentiment Analysis
                                </h3>
                                <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.85rem;'>
                                    Management tone and confidence - What the language reveals
                                </p>
                            </div>
                            """, unsafe_allow_html=True)

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
                            # SECTION: Red Flags
                            st.markdown("""
                            <div style='background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
                                        padding: 1rem 1.5rem; border-radius: 12px; margin: 1.5rem 0 1rem 0;'>
                                <h3 style='margin: 0; color: white; font-weight: 600; font-size: 1.3rem;'>
                                    Red Flags Detected
                                </h3>
                                <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.85rem;'>
                                    Warning signals - Financial health concerns identified
                                </p>
                            </div>
                            """, unsafe_allow_html=True)
                            for flag in red_flags:
                                st.error(flag)
                        else:
                            # Only show "no red flags" if we actually ran the analysis
                            if 'red_flags' in intrinsic:
                                st.markdown("""
                                <div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
                                            padding: 1rem 1.5rem; border-radius: 12px; margin: 1.5rem 0 1rem 0;'>
                                    <h3 style='margin: 0; color: white; font-weight: 600; font-size: 1.3rem;'>
                                        No Red Flags Detected
                                    </h3>
                                    <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.85rem;'>
                                        All financial health checks passed
                                    </p>
                                </div>
                                """, unsafe_allow_html=True)

                        # 5. Reverse DCF (What the market is pricing in)
                        reverse_dcf = intrinsic.get('reverse_dcf', {})
                        if reverse_dcf:
                            # SECTION: Reverse DCF
                            st.markdown("""
                            <div style='background: linear-gradient(135deg, #0ba360 0%, #3cba92 100%);
                                        padding: 1rem 1.5rem; border-radius: 12px; margin: 1.5rem 0 1rem 0;'>
                                <h3 style='margin: 0; color: white; font-weight: 600; font-size: 1.3rem;'>
                                    Reverse DCF Analysis
                                </h3>
                                <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.85rem;'>
                                    What growth rate does the current price imply?
                                </p>
                            </div>
                            """, unsafe_allow_html=True)

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
                                st.error(f"{interpretation}")

                        # 6. DCF Sensitivity Analysis
                        dcf_sensitivity = intrinsic.get('dcf_sensitivity', {})
                        if dcf_sensitivity:
                            # SECTION: DCF Sensitivity
                            st.markdown("""
                            <div style='background: linear-gradient(135deg, #2193b0 0%, #6dd5ed 100%);
                                        padding: 1rem 1.5rem; border-radius: 12px; margin: 1.5rem 0 1rem 0;'>
                                <h3 style='margin: 0; color: white; font-weight: 600; font-size: 1.3rem;'>
                                    DCF Sensitivity Analysis
                                </h3>
                                <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.85rem;'>
                                    How valuation changes with different assumptions
                                </p>
                            </div>
                            """, unsafe_allow_html=True)

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
                        st.markdown("#### Configuration Loaded")
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
                                    st.error(f"Insider Trading: **DISABLED**")

                            with col2:
                                transcripts_enabled = premium_config.get('enable_earnings_transcripts', False)
                                if transcripts_enabled:
                                    st.success(f" Earnings Transcripts: **ENABLED**")
                                else:
                                    st.error(f"Earnings Transcripts: **DISABLED**")
                        except Exception as e:
                            st.error(f"Could not load config: {e}")

                        # Check where features are in the analysis result
                        st.markdown("#### Features in Analysis Result")

                        # Check root level (WRONG location)
                        has_insider_root = 'insider_trading' in analysis
                        has_sentiment_root = 'earnings_sentiment' in analysis

                        st.markdown("**Root Level (DEPRECATED):**")
                        col1, col2 = st.columns(2)
                        with col1:
                            if has_insider_root:
                                st.warning(" insider_trading found at ROOT (deprecated)")
                            else:
                                st.info("insider_trading NOT at root")
                        with col2:
                            if has_sentiment_root:
                                st.warning(" earnings_sentiment found at ROOT")
                            else:
                                st.info("earnings_sentiment NOT at root")

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
                                st.error("insider_trading NOT in intrinsic_value")
                        with col2:
                            if has_sentiment_iv:
                                st.success(" earnings_sentiment FOUND in intrinsic_value!")
                            else:
                                st.error("earnings_sentiment NOT in intrinsic_value")

                        # Show actual data if present
                        st.markdown("#### Actual Premium Features Data")

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
                        st.markdown("#### All Keys in intrinsic_value Dict")
                        st.code(f"Keys: {list(intrinsic.keys())}")

                        st.markdown("""
                        ---
                        ** How to Access Premium Features:**
                        ```python
                        #  CORRECT
                        analysis['intrinsic_value']['insider_trading']
                        analysis['intrinsic_value']['earnings_sentiment']

                        # WRONG
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
        <h2 style='margin: 0; color: white; font-weight: 700;'>Valuation Dashboard</h2>
        <p style='margin: 0.5rem 0 0 0; opacity: 0.95;'>
            Quick overview of all screened stocks with valuation metrics and growth projections
        </p>
    </div>
    """, unsafe_allow_html=True)

    if 'results' in st.session_state:
        # Get recalculated results with current slider values
        df = get_results_with_current_params()

        # Initialize valuation cache in session state if not exists
        if 'valuation_cache' not in st.session_state:
            st.session_state['valuation_cache'] = {}

        st.markdown("""
        **Dashboard Overview** - View valuation metrics for all screened stocks in one place.
        Use filters to quickly identify stocks of interest, then click on a row to see detailed analysis.
        """)

        # Filters section
        st.markdown("### Filters")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            filter_decision = st.selectbox(
                "Decision",
                options=['All', 'BUY', 'MONITOR', 'AVOID'],
                index=0,
                key='dashboard_decision'
            )

        with col2:
            # Get unique sectors
            sectors = ['All'] + sorted(df['sector'].dropna().unique().tolist()) if 'sector' in df.columns else ['All']
            filter_sector = st.selectbox(
                "Sector",
                options=sectors,
                index=0,
                key='dashboard_sector'
            )

        with col3:
            # Get unique industries
            industries = ['All'] + sorted(df['industry'].dropna().unique().tolist()) if 'industry' in df.columns else ['All']
            filter_industry = st.selectbox(
                "Industry",
                options=industries,
                index=0,
                key='dashboard_industry'
            )

        with col4:
            sort_by = st.selectbox(
                "Sort by",
                options=['Composite Score ↓', 'Value Score ↓', 'Quality Score ↓', 'Ticker ↑', 'Market Cap ↓'],
                index=0,
                key='dashboard_sort'
            )

        # Apply filters
        df_filtered = df.copy()

        if filter_decision != 'All':
            df_filtered = df_filtered[df_filtered['decision'] == filter_decision]

        if filter_sector != 'All':
            df_filtered = df_filtered[df_filtered['sector'] == filter_sector] if 'sector' in df_filtered.columns else df_filtered

        if filter_industry != 'All':
            df_filtered = df_filtered[df_filtered['industry'] == filter_industry] if 'industry' in df_filtered.columns else df_filtered

        # Apply sorting
        if sort_by == 'Composite Score ↓':
            df_filtered = df_filtered.sort_values('composite_0_100', ascending=False)
        elif sort_by == 'Value Score ↓':
            df_filtered = df_filtered.sort_values('value_score_0_100', ascending=False)
        elif sort_by == 'Quality Score ↓':
            df_filtered = df_filtered.sort_values('quality_score_0_100', ascending=False)
        elif sort_by == 'Ticker ↑':
            df_filtered = df_filtered.sort_values('ticker')
        elif sort_by == 'Market Cap ↓':
            if 'market_cap' in df_filtered.columns:
                df_filtered = df_filtered.sort_values('market_cap', ascending=False)

        st.markdown("---")

        # Summary metrics
        col_metric1, col_metric2, col_metric3, col_metric4 = st.columns(4)
        with col_metric1:
            st.metric("Total Stocks", len(df_filtered))
        with col_metric2:
            buy_count = (df_filtered['decision'] == 'BUY').sum()
            st.metric("BUY", buy_count)
        with col_metric3:
            monitor_count = (df_filtered['decision'] == 'MONITOR').sum()
            st.metric("MONITOR", monitor_count)
        with col_metric4:
            avoid_count = (df_filtered['decision'] == 'AVOID').sum()
            st.metric("AVOID", avoid_count)

        st.markdown("---")

        # Main table
        st.markdown("### Valuation Overview")

        # Create display dataframe
        display_cols = ['ticker', 'name', 'sector', 'decision', 'composite_0_100', 'value_score_0_100', 'quality_score_0_100']

        # Add optional columns if they exist
        optional_cols = ['price', 'market_cap', 'guardrail']
        for col in optional_cols:
            if col in df_filtered.columns:
                display_cols.append(col)

        # Filter to available columns
        display_cols = [col for col in display_cols if col in df_filtered.columns]

        df_display = df_filtered[display_cols].copy()

        # Rename columns for better display
        column_mapping = {
            'ticker': 'Ticker',
            'name': 'Company',
            'sector': 'Sector',
            'decision': 'Decision',
            'composite_0_100': 'Composite',
            'value_score_0_100': 'Value',
            'quality_score_0_100': 'Quality',
            'price': 'Price',
            'market_cap': 'Market Cap',
            'guardrail': 'Guardrail'
        }

        df_display = df_display.rename(columns=column_mapping)

        # Format numeric columns
        if 'Composite' in df_display.columns:
            df_display['Composite'] = df_display['Composite'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "N/A")
        if 'Value' in df_display.columns:
            df_display['Value'] = df_display['Value'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "N/A")
        if 'Quality' in df_display.columns:
            df_display['Quality'] = df_display['Quality'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "N/A")
        if 'Price' in df_display.columns:
            df_display['Price'] = df_display['Price'].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "N/A")
        if 'Market Cap' in df_display.columns:
            df_display['Market Cap'] = df_display['Market Cap'].apply(
                lambda x: f"${x/1e9:.1f}B" if pd.notna(x) and x >= 1e9 else (f"${x/1e6:.1f}M" if pd.notna(x) else "N/A")
            )

        # Color coding for decisions
        def color_decision(val):
            if val == 'BUY':
                return 'background-color: #d1fae5; color: #065f46; font-weight: 700;'
            elif val == 'MONITOR':
                return 'background-color: #dbeafe; color: #1e3a8a; font-weight: 700;'
            elif val == 'AVOID':
                return 'background-color: #fee2e2; color: #991b1b; font-weight: 700;'
            return ''

        def color_guardrail(val):
            if val == 'VERDE':
                return 'background-color: #d1fae5; color: #065f46; font-weight: 700;'
            elif val == 'AMBAR':
                return 'background-color: #fef3c7; color: #78350f; font-weight: 700;'
            elif val == 'ROJO':
                return 'background-color: #fee2e2; color: #991b1b; font-weight: 700;'
            return ''

        # Apply styling
        styled_df = df_display.style.applymap(color_decision, subset=['Decision'] if 'Decision' in df_display.columns else [])
        if 'Guardrail' in df_display.columns:
            styled_df = styled_df.applymap(color_guardrail, subset=['Guardrail'])

        # Display table
        st.dataframe(
            styled_df,
            use_container_width=True,
            height=600
        )

        st.markdown("---")

        # Expandable section for detailed analysis
        st.markdown("### Detailed Valuation Analysis")
        st.markdown("""
        Select a ticker below to run comprehensive valuation analysis including:
        - **Robust Fair Value** with multi-method consensus
        - **Growth Engine** with 3-estimator system
        - **Price Projections** by scenario
        - **Peer comparison** and reliability metrics
        """)

        # Ticker selection for detailed analysis
        col_detail1, col_detail2 = st.columns([1, 3])

        with col_detail1:
            selected_detail_ticker = st.selectbox(
                "Select ticker for detailed analysis",
                options=df_filtered['ticker'].tolist(),
                key='dashboard_detail_ticker'
            )

        with col_detail2:
            if selected_detail_ticker:
                stock_info = df_filtered[df_filtered['ticker'] == selected_detail_ticker].iloc[0]
                st.markdown(f"**{stock_info['name']}** ({selected_detail_ticker})")

                col_info1, col_info2, col_info3 = st.columns(3)
                with col_info1:
                    st.metric("Decision", stock_info['decision'])
                with col_info2:
                    st.metric("Composite Score", f"{stock_info['composite_0_100']:.1f}")
                with col_info3:
                    st.metric("Guardrail", stock_info.get('guardrail', 'N/A'))

        if selected_detail_ticker and st.button(f"Run Deep Analysis for {selected_detail_ticker}", type="primary", use_container_width=True, key='dashboard_analyze_btn'):
            # Force reload modules to get latest code
            modules_to_reload = [
                'screener.ingest',
                'screener.qualitative'
            ]
            for module_name in modules_to_reload:
                if module_name in sys.modules:
                    del sys.modules[module_name]

            with st.spinner(f"Analyzing {selected_detail_ticker}... This may take 30-60 seconds"):
                try:
                    from screener.qualitative import QualitativeAnalyzer
                    from screener.ingest import FMPClient

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
                        st.error("FMP API key not found. Please set FMP_API_KEY in Streamlit secrets or environment variables.")
                    else:
                        # Initialize clients
                        fmp_client = FMPClient(api_key, config)
                        analyzer = QualitativeAnalyzer(
                            fmp_client=fmp_client,
                            config=config
                        )

                        # Get company type from filtered results
                        stock_data = df_filtered[df_filtered['ticker'] == selected_detail_ticker].iloc[0]
                        company_type = stock_data.get('company_type', 'non_financial')

                        # Run analysis
                        result = analyzer.analyze_symbol(
                            selected_detail_ticker,
                            company_type=company_type,
                            peers_df=df
                        )

                        if result and 'error' not in result:
                            # Extract intrinsic value section
                            intrinsic = result.get('intrinsic_value', {})

                            # Display Robust Fair Value section
                            st.markdown("#### Robust Fair Value Estimation")

                            robust_val = intrinsic.get('robust_valuation', {})
                            current_price = intrinsic.get('current_price', 0)

                            if robust_val and robust_val.get('fair_value_robust'):
                                p10 = robust_val.get('range_p10', 0)
                                p50 = robust_val.get('fair_value_robust', 0)  # Median
                                p90 = robust_val.get('range_p90', 0)
                                consensus = robust_val.get('consensus_tightness', 'Unknown')
                                reliability = robust_val.get('multiples_reliability', 'Unknown')
                                reliability_reason = robust_val.get('multiples_reliability_reason', '')
                                disagreement = robust_val.get('method_disagreement', '')

                                # Show metrics
                                col_fv1, col_fv2, col_fv3, col_fv4 = st.columns(4)
                                with col_fv1:
                                    st.metric("Fair Value (p10)", f"${p10:.2f}")
                                with col_fv2:
                                    st.metric("Fair Value (p50)", f"${p50:.2f}")
                                with col_fv3:
                                    st.metric("Fair Value (p90)", f"${p90:.2f}")
                                with col_fv4:
                                    st.metric("Current Price", f"${current_price:.2f}")

                                # Calculate and show upside/downside
                                if current_price > 0 and p50 > 0:
                                    upside = ((p50 - current_price) / current_price) * 100

                                    # Valuation verdict
                                    if current_price > p90:
                                        verdict = "Overvalued"
                                        color = "#991b1b"
                                    elif current_price >= p50:
                                        verdict = "Fair Value"
                                        color = "#1e3a8a"
                                    elif current_price >= p10:
                                        verdict = "Fair Value"
                                        color = "#1e3a8a"
                                    else:
                                        verdict = "Undervalued"
                                        color = "#065f46"

                                    st.markdown(f"**Verdict:** <span style='color: {color}; font-weight: 700;'>{verdict}</span> | **Upside/Downside vs p50:** {upside:+.1f}%", unsafe_allow_html=True)

                                # Consensus and reliability
                                st.markdown(f"**Consensus Tightness:** {consensus} | **Peer Reliability:** {reliability}")

                                if reliability_reason:
                                    st.caption(f"Peer Selection: {reliability_reason}")

                                if disagreement:
                                    st.caption(f"Method Disagreement: {disagreement}")

                                # Notes if available
                                notes = robust_val.get('notes', [])
                                if notes and len(notes) > 0:
                                    with st.expander("Details"):
                                        for note in notes:
                                            st.write(f"- {note}")
                            else:
                                st.warning("Robust Fair Value data not available for this ticker.")

                            # Display Growth Engine section
                            st.markdown("---")
                            st.markdown("#### Growth Engine")

                            growth_engine = intrinsic.get('growth_engine', {})
                            if growth_engine and growth_engine.get('revenue_growth_5y'):
                                growth_5y = growth_engine['revenue_growth_5y']

                                # Show growth metrics
                                col_g1, col_g2, col_g3 = st.columns(3)
                                with col_g1:
                                    base = growth_5y.get('base')
                                    if base is not None:
                                        st.metric("Base Scenario (5Y)", f"{base:.1f}%")
                                    else:
                                        st.metric("Base Scenario (5Y)", "N/A")
                                with col_g2:
                                    bull = growth_5y.get('bull')
                                    if bull is not None:
                                        st.metric("Bull Scenario (5Y)", f"{bull:.1f}%")
                                    else:
                                        st.metric("Bull Scenario (5Y)", "N/A")
                                with col_g3:
                                    bear = growth_5y.get('bear')
                                    if bear is not None:
                                        st.metric("Bear Scenario (5Y)", f"{bear:.1f}%")
                                    else:
                                        st.metric("Bear Scenario (5Y)", "N/A")

                                # Show confidence if available
                                confidence = growth_5y.get('confidence', '')
                                sources = growth_5y.get('sources', [])
                                if confidence or sources:
                                    st.markdown(f"**Confidence:** {confidence}")
                                    if sources:
                                        st.caption(f"Sources: {', '.join(sources)}")
                            else:
                                st.warning("Growth Engine data not available for this ticker.")

                            # Display Price Projections section
                            st.markdown("---")
                            st.markdown("#### Price Projections by Scenario")

                            projections = intrinsic.get('price_projections', {})
                            scenarios = projections.get('scenarios', {})

                            if scenarios:
                                # Extract targets from scenarios
                                base_case = scenarios.get('Base Case', {})
                                bull_case = scenarios.get('Bull Case', {})
                                bear_case = scenarios.get('Bear Case', {})

                                # Show 5Y projection metrics
                                col_p1, col_p2, col_p3 = st.columns(3)
                                with col_p1:
                                    bear_target = bear_case.get('5Y_target')
                                    if bear_target:
                                        st.metric("Bear Target (5Y)", f"${bear_target:.2f}")
                                        st.caption(bear_case.get('description', ''))
                                with col_p2:
                                    base_target = base_case.get('5Y_target')
                                    if base_target:
                                        st.metric("Base Target (5Y)", f"${base_target:.2f}")
                                        st.caption(base_case.get('description', ''))
                                with col_p3:
                                    bull_target = bull_case.get('5Y_target')
                                    if bull_target:
                                        st.metric("Bull Target (5Y)", f"${bull_target:.2f}")
                                        st.caption(bull_case.get('description', ''))

                                # Show returns for base case
                                if base_case:
                                    st.markdown(f"**Base Case Returns:** 1Y: {base_case.get('1Y_return', 'N/A')} | 3Y: {base_case.get('3Y_return', 'N/A')} ({base_case.get('3Y_cagr', 'N/A')} CAGR) | 5Y: {base_case.get('5Y_return', 'N/A')} ({base_case.get('5Y_cagr', 'N/A')} CAGR)")

                                # Source and methodology
                                source = projections.get('source', '')
                                if source == 'growth_engine':
                                    st.caption("Projection method: Growth Engine (multi-estimator consensus)")
                                elif source == 'simple_revenue':
                                    st.caption("Projection method: Historical revenue trends")

                                # Show all scenarios in expandable table
                                with st.expander("All Scenarios Details"):
                                    for scenario_name, scenario_data in scenarios.items():
                                        st.markdown(f"**{scenario_name}**")
                                        st.write(f"- Growth: {scenario_data.get('growth_assumption', 'N/A')}")
                                        st.write(f"- Blended Return: {scenario_data.get('blended_return', 'N/A')}")
                                        st.write(f"- 1Y Target: ${scenario_data.get('1Y_target', 0):.2f} ({scenario_data.get('1Y_return', 'N/A')})")
                                        st.write(f"- 3Y Target: ${scenario_data.get('3Y_target', 0):.2f} ({scenario_data.get('3Y_cagr', 'N/A')} CAGR)")
                                        st.write(f"- 5Y Target: ${scenario_data.get('5Y_target', 0):.2f} ({scenario_data.get('5Y_cagr', 'N/A')} CAGR)")
                                        st.write("")
                            else:
                                st.warning("Price Projections data not available for this ticker.")

                            st.success(f"Analysis complete for {selected_detail_ticker}")
                        else:
                            error_msg = result.get('error', 'Unknown error') if result else 'No result returned'
                            st.error(f"Analysis error for {selected_detail_ticker}: {error_msg}")

                except Exception as e:
                    st.error(f"Error running analysis: {str(e)}")
                    st.exception(e)

    else:
        st.info("👈 Run the screener first to access the valuation dashboard")

with tab7:
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
                from screener.technical.analyzer_v2 import TechnicalAnalyzerV2

                # Initialize pipeline (this loads settings.yaml and sets up FMP client)
                pipeline = ScreenerPipeline('settings.yaml')

                # Initialize analyzers
                qual_analyzer = QualitativeAnalyzer(pipeline.fmp, pipeline.config)
                tech_analyzer = TechnicalAnalyzerV2(pipeline.fmp)

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
                    st.error(f"Analysis failed: {error_msg}")
                    st.info(f" Troubleshooting tips:\n- Ticker: {formatted_custom_ticker}\n- Market suffix has been added automatically\n- Some tickers may have limited data availability\n- Try selecting a different market if the ticker is listed on multiple exchanges")

            except Exception as e:
                st.error(f"Analysis failed: {str(e)}")
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

                # Get benchmark-specific label if available
                percentile_info_mobile = intrinsic.get('percentile_info', {})
                downside_label_mobile = percentile_info_mobile.get('downside_label', '')
                if downside_label_mobile:
                    upside_display_mobile = downside_label_mobile
                else:
                    upside_display_mobile = f"{upside:+.1f}% {'upside' if upside > 0 else 'downside'}"

                st.markdown(f"### {emoji} {assessment}: {upside_display_mobile}")
                st.caption(f"**Confidence:** {confidence}")
            # Second row: PEG Ratio + Intrinsic Value PEG-Forward
            # Check if PEG is in outliers - if so, skip this section
            robust_val_check_mobile = intrinsic.get('robust_valuation', {})
            outlier_methods_list_mobile = robust_val_check_mobile.get('outlier_methods', [])
            peg_is_outlier_check_mobile = any('PEG' in om or 'peg' in om.lower() for om in outlier_methods_list_mobile)

            # Initialize PEG variables BEFORE conditional to avoid NameError
            peg_ratio = None
            pe_ratio = None
            eps_growth = None

            if not peg_is_outlier_check_mobile:
                st.markdown("")  # Spacing

                # Get PEG and related data from correct location
                if 'valuation_multiples' in intrinsic:
                    company_vals = intrinsic['valuation_multiples'].get('company', {})
                    peg_ratio = company_vals.get('peg', None)
                    pe_ratio = company_vals.get('pe', None)
                    eps_growth = company_vals.get('eps_growth_%', None)

            if peg_ratio and peg_ratio > 0 and not peg_is_outlier_check_mobile:
                # PEG-based valuation ONLY makes sense for growth companies (5% <= growth <= 100%)
                # For low/no growth companies, PEG is meaningless
                # Example: Growth 0.4% → Fair PEG 1.0 would imply PE of 0.4x (absurd)
                # For extreme growth (>100%), it's usually a one-time turnaround, not sustainable
                # Example: Growth 1352% → Likely losses-to-profits transition, not real growth rate

                if eps_growth and eps_growth >= 5 and eps_growth <= 100:
                    # Calculate PEG-based Intrinsic Value for GROWTH companies
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
                            st.caption(f"PEG: {peg_ratio:.2f} | EPS Growth: {eps_growth:.1f}%")
                    with col_peg2:
                        st.markdown(f"### {peg_color} **{peg_label}**")
                        st.caption(f"*Fair PEG = 1.0 (conservador)*")
                    with col_peg3:
                        if peg_intrinsic_growth:
                            upside_growth = ((peg_intrinsic_growth - current_price) / current_price) * 100
                            st.caption(f"**Growth PEG 1.5:** ${peg_intrinsic_growth:.2f} ({upside_growth:+.1f}%)")
                        st.caption("*Premium para empresas de alto crecimiento*")
                else:
                    # PEG valuation not applicable for low growth OR extreme growth
                    if eps_growth and eps_growth > 100:
                        # Extreme growth spike (likely one-time turnaround)
                        st.warning(f"**PEG Valuation Not Applicable:** EPS Growth {eps_growth:.1f}% (> 100% threshold)")
                        st.caption("Extreme growth rates usually indicate one-time events (losses-to-profits, restructuring, etc.) rather than sustainable growth.")
                        st.caption(f"Current PEG: **{peg_ratio:.2f}** — Use DCF or sector comparables for valuation instead.")
                    else:
                        # Low/No growth company
                        st.warning(f"**PEG Valuation Not Applicable:** EPS Growth {eps_growth:.1f}% (< 5% threshold)")
                        st.caption("PEG-based valuation only works for growth companies. For mature/declining companies, use DCF or P/E multiples.")
                        st.caption(f"Current PEG: **{peg_ratio:.2f}** (High PEG with low growth = overvalued)")
            else:
                if not peg_is_outlier_check_mobile:
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

            # Check if PEG is within robust range or outlier
            robust_valuation = intrinsic.get('robust_valuation', {})
            outlier_methods = robust_valuation.get('outlier_methods', [])
            peg_is_outlier = any('PEG' in om or 'peg' in om.lower() for om in outlier_methods)
            robust_p90 = robust_valuation.get('range_p90', 0)
            robust_fv = robust_valuation.get('fair_value_robust', 0)
            percentile_info = intrinsic.get('percentile_info', {})
            positioning = percentile_info.get('positioning', '')

            # Determine predominant method
            # Priority 0: If robust FV exists AND price is premium-priced, use Robust FV
            if robust_fv and 'above p90' in positioning.lower():
                # Price above robust range - Robust FV is base, PEG is bull case
                method_icon = ""
                method_name = "Robust FV (Price at premium)"
                peg_value = intrinsic.get('peg_value', 0)
                range_p10 = robust_valuation.get('range_p10', 0)
                method_reason = f"""
**Price is above robust valuation range - premium-priced:**

**Valoración Base (Robust FV):**
- Fair Value Robusto: ${robust_fv:.0f} (consenso de múltiples métodos)
- Rango base (p10–p90): ${range_p10:.0f}–${robust_p90:.0f}
- Precio actual: ${current_price:.0f} → Above p90 (premium-priced)

**PEG Bull Case:**
- PEG Fair Value: ${peg_value:.0f}{"" if not peg_ratio else f" (PEG={peg_ratio:.2f})"} ← Escenario si mercado paga premium por crecimiento
- PEG 1.5 premium: ${intrinsic.get('peg_intrinsic_conservative', peg_value * 1.53):.0f}

**Interpretación:**
- Valoración base: ${robust_fv:.0f} (consenso robusto)
- Precio actual ≈ PEG bull case (mercado ya pricing growth premium)
- Valuation base: premium-priced; requiere ejecución y/o momentum para justificar la prima
"""
            # Priority 1: If PEG < 1.5 AND within robust range AND price reasonable
            elif peg_ratio and peg_ratio < 1.5 and not peg_is_outlier and 'above p90' not in positioning.lower():
                # Growth company - PEG is king AND validated by robust range
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
            elif peg_ratio and peg_ratio < 1.5 and peg_is_outlier:
                # PEG is low but outside robust range = Bull/Premium case only
                method_icon = ""
                method_name = "Robust FV (PEG = escenario bull, no base)"
                peg_value = intrinsic.get('peg_value', 0)
                robust_fv = robust_valuation.get('fair_value_robust', 0)
                range_p10 = robust_valuation.get('range_p10', 0)
                method_reason = f"""
**PEG sugiere escenario premium, pero el consenso robusto difiere:**

**Valoración Base (Robust FV):**
- Fair Value Robusto: ${robust_fv:.0f} (basado en cash flows y enterprise multiples)
- Rango base (p10–p90): ${range_p10:.0f}–${robust_p90:.0f}

**Escenario Bull (PEG):**
- PEG Ratio: {peg_ratio:.2f} (< 1.5 = Growth at reasonable price)
- PEG Fair Value: ${peg_value:.0f} ← Escenario premium si ejecutan crecimiento

**Interpretación:**
- Si el mercado paga múltiplos premium por crecimiento → target ~${peg_value:.0f}
- Consenso de métodos conservadores (DCF, EV/EBIT, EV/FCF) → rango ${range_p10:.0f}–${robust_p90:.0f}
- Use robust FV como base, PEG como upside potencial
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
  - Growth limitado PEG pierde relevancia
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
                        if note.startswith(''):
                            st.success(note)
                        elif note.startswith('') or 'ERROR' in note or 'failed' in note.lower():
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
                # Si PEG < 1.5 y Growth > 10% VERDE, sin importar DCF

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
                        # PEG = P/E / Growth Growth = P/E / PEG
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

                # === PEG OVERRIDE DISABLED ===
                # Removed: PEG override logic contradicts robust FV engine
                # PEG can inform bull/premium case, but doesn't redefine fair value base
                # Valuation verdict now comes from robust FV vs price percentiles
                peg_hammer_triggered = False
                growth_override_applied = False

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
                        st.caption(gross.get('trend', 'stable'))

                with col2:
                    operating = profitability.get('operating_margin', {})
                    if operating:
                        st.metric("Operating Margin", f"{operating.get('current', 0):.1f}%",
                                 delta=f"{operating.get('current', 0) - operating.get('avg_3y', 0):.1f}% vs 3Y avg")
                        st.caption(operating.get('trend', 'stable'))

                with col3:
                    fcf = profitability.get('fcf_margin', {})
                    if fcf:
                        st.metric("FCF Margin", f"{fcf.get('current', 0):.1f}%",
                                 delta=f"{fcf.get('current', 0) - fcf.get('avg_3y', 0):.1f}% vs 3Y avg")
                        st.caption(fcf.get('trend', 'stable'))

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
                    st.markdown("#### Free Cash Flow Growth")
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
                        st.metric("YoY Trend", "Worsening", delta=f"{yoy_change:+.0f} days")
                    else:
                        st.metric("YoY Trend", "Stable", delta=f"{yoy_change:+.0f} days")

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
                        st.caption("Poor")

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
                        st.metric("5Y Avg EVA", avg_eva, delta="Declining")
                    else:
                        st.metric("5Y Avg EVA", avg_eva, delta="Stable")

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
                    emoji = "" if share_trend == 'decreasing' else "" if share_trend == 'increasing' else ""
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
                        st.metric("NIM Trend", "Compressing", delta=f"{yoy:.2f}% YoY")
                    else:
                        st.metric("NIM Trend", "Stable", delta=f"{yoy:+.2f}% YoY")

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

                # Show Growth Engine badge if applicable
                projection_source = projections.get('source', 'unknown')
                if projection_source == 'growth_engine':
                    st.success("**GROWTH ENGINE** - Robust 3-estimator system")

                    # Show estimator weights
                    estimators_used = projections.get('estimators_used', {})
                    if estimators_used:
                        estimator_text = " | ".join([f"{k.title()}: {v:.1%}" for k, v in estimators_used.items()])
                        st.caption(f"**Weights:** {estimator_text}")

                    # Enhanced details in expander for mobile too
                    growth_engine = intrinsic.get('growth_engine')
                    if growth_engine and growth_engine.get('revenue_growth_5y'):
                        with st.expander("See Growth Engine Details", expanded=False):
                            rev_growth = growth_engine['revenue_growth_5y']
                            sigma = rev_growth.get('volatility', 0)

                            # Show regime
                            if sigma > 0.25:
                                regime = "Event-Driven (σ > 25%)"
                            elif sigma > 0.15:
                                regime = "High Volatility (σ > 15%)"
                            else:
                                regime = "Base/Stable (σ ≤ 15%)"

                            st.info(f"**Regime:** {regime} | **σ:** {sigma:.1%}")

                            # Show individual estimators
                            hist_val = rev_growth.get('historical')
                            fund_val = rev_growth.get('fundamental')
                            cons_val = rev_growth.get('consensus')
                            weights = rev_growth.get('weights', {})

                            if hist_val is not None:
                                st.caption(f"**Historical:** {hist_val:.1%} (weight: {weights.get('historical', 0):.0%})")
                            if fund_val is not None:
                                st.caption(f"**Fundamental:** {fund_val:.1%} (weight: {weights.get('fundamental', 0):.0%})")
                            if cons_val is not None:
                                st.caption(f"**Consensus:** {cons_val:.1%} (weight: {weights.get('consensus', 0):.0%})")

                            # Show scenarios
                            blended = rev_growth.get('blended', 0)
                            bear = rev_growth.get('bear', 0)
                            bull = rev_growth.get('bull', 0)

                            st.markdown(f"**Scenarios:** Bear {bear:.1%} | Base {blended:.1%} | Bull {bull:.1%}")

                scenarios = projections.get('scenarios', {})

                if scenarios:
                    # Display as table
                    scenario_names = list(scenarios.keys())

                    # Create columns for each scenario
                    cols = st.columns(len(scenario_names))

                    for i, (scenario_name, data) in enumerate(scenarios.items()):
                        with cols[i]:
                            # Color based on scenario
                            if 'Bear' in scenario_name:
                                color = '#ff6b6b'
                            elif 'Bull' in scenario_name:
                                color = '#51cf66'
                            else:
                                color = '#ffd43b'

                            st.markdown(f"**{scenario_name}**")
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
                        st.error(f"{interpretation}")

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
                        st.metric("Relative Strength", f"{components.get('relative_strength', 0):.0f}/40")
                        rs_details = tech_analysis.get('component_details', {}).get('relative_strength', {})
                        st.caption(f"RS 12-1: {rs_details.get('rs_12_1_vs_spy', 0):.1f}%")

                    with col2:
                        st.metric("Trend/Structure", f"{components.get('trend_structure', 0):.0f}/25")
                        trend_details = tech_analysis.get('component_details', {}).get('trend_structure', {})
                        st.caption(f"Slope: {trend_details.get('ma200_slope_deg', 0):.1f}°")

                    with col3:
                        st.metric("Risk Quality", f"{components.get('risk_quality', 0):.0f}/20")
                        risk_details = tech_analysis.get('component_details', {}).get('risk_quality', {})
                        st.caption(f"Sharpe 6M: {risk_details.get('sharpe_6m', 0):.2f}")

                    with col4:
                        st.metric("Volume/Participation", f"{components.get('volume_participation', 0):.0f}/15")
                        st.caption(tech_analysis.get('volume_profile', 'N/A'))

                    with col5:
                        # V2: Show conviction in 5th column
                        conviction = tech_analysis.get('conviction', 0)
                        st.metric("Conviction", f"{conviction:.2f}")
                        states = tech_analysis.get('states', {})
                        st.caption(f"{states.get('extension', 'N/A')}")

                    # V2: States Info
                    st.markdown("**States:** Extension: " + states.get('extension', 'N/A') +
                               " | Regime: " + states.get('regime', 'N/A') +
                               " | Trend: " + states.get('trend', 'N/A'))

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

                        # V2: Show RS details instead
                        rs_details = tech_analysis.get('component_details', {}).get('relative_strength', {})
                        st.write(f"**RS 6-1 vs SPY:** {rs_details.get('rs_6_1_vs_spy', 0):+.1f}%")
                        st.write(f"**RS 6-1 vs Sector:** {rs_details.get('rs_6_1_vs_sector', 0):+.1f}%")

                    with tab2:
                        col1, col2 = st.columns(2)

                        with col1:
                            st.markdown("**Risk Metrics:**")
                            st.write(f"- Sharpe Ratio (12M): {tech_analysis.get('sharpe_12m', 0):.2f}")
                            st.write(f"- Volatility (12M): {tech_analysis.get('volatility_12m', 0):.1f}%")
                            st.write(f"- Risk Status: {tech_analysis.get('risk_adjusted_status', 'N/A')}")

                        with col2:
                            st.markdown("**Relative Strength (V2):**")
                            rs_details = tech_analysis.get('component_details', {}).get('relative_strength', {})
                            st.write(f"- RS 12-1 vs SPY: {rs_details.get('rs_12_1_vs_spy', 0):+.1f}%")
                            st.write(f"- RS 6-1 vs SPY: {rs_details.get('rs_6_1_vs_spy', 0):+.1f}%")
                            st.write(f"- RS 6-1 vs Sector: {rs_details.get('rs_6_1_vs_sector', 0):+.1f}%")
                            st.write(f"- Total RS Score: {tech_analysis.get('components', {}).get('relative_strength', 0):.0f}/40")

                    with tab3:
                        col1, col2 = st.columns(2)

                        with col1:
                            st.markdown("**Trend Analysis:**")
                            states = tech_analysis.get('states', {})
                            st.write(f"- Trend State: {states.get('trend', 'N/A')}")
                            metadata = tech_analysis.get('metadata', {})
                            st.write(f"- Distance from MA200: {metadata.get('distance_ma200_pct', 0):+.1f}%")
                            trend_details = tech_analysis.get('component_details', {}).get('trend_structure', {})
                            st.write(f"- Golden Cross: {'✓' if trend_details.get('golden_cross') else '✗'}")

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

with tab9:
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
    - **WAIT**: Fundamental BUY + Technical SELL (great company, bad timing)

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
    2. **Top-K Selection**: Preliminary ranking (2000+ 100 deep analysis)

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

    ## Scoring Formula

    ### Fundamental Score (0-100)
    ```
    Composite = (Value Weight × Value Score) + (Quality Weight × Quality Score)

    Decision:
    - Score ≥ 75 + VERDE BUY
    - Score 60-75 or AMBAR MONITOR
    - Score < 60 or ROJO AVOID
    ```

    ### Technical Score (0-100)
    ```
    Score = Momentum(35) + Sector(25) + Trend(25) + Volume(15)

    Signal:
    - Score ≥ 75 BUY
    - Score 50-75 HOLD
    - Score < 50 SELL
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

    ## Technical Stack

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

    - **NOT** investment advice
    - **NOT** a recommendation to buy or sell securities
    - **NOT** a substitute for professional financial advice

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
    - **v4.0** - **Technical Analysis** (Evidence-based timing) **Current**

    ---

    **UltraQuality** - Combining the best of fundamental and technical analysis, backed by academic research.
    """)

with tab8:
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
            **Evidence-Based Indicators:**
            - **12-Month Momentum** (Jegadeesh & Titman 1993, Moskowitz 2021)
              Strongest predictor of future returns
            - **Sector Relative Strength** (Bretscher 2023, Arnott 2024)
              Industry leadership indicates structural advantages
            - **Trend Following (MA200)** (Brock et al. 1992, updated 2023)
              Long-term trend identification
            - **Volume Confirmation** (Lo & Wang 2000)
              Institutional accumulation/distribution
            """)

        with col2:
            st.markdown("""
            **Excluded (No Post-2010 Evidence):**
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

        # Filter to BUY, MONITOR, and AVOID
        df_technical = df[df['decision'].isin(['BUY', 'MONITOR', 'AVOID'])].copy()

        if len(df_technical) == 0:
            st.warning("No stocks found. Run screener with different parameters.")
        else:
            st.success(f"Analyzing **{len(df_technical)}** stocks (BUY + MONITOR + AVOID signals)")

            # Analyze technical for all stocks
            with st.spinner("Running technical analysis... This may take 30-60 seconds"):
                # Initialize analyzer (lazy import)
                try:
                    from screener.technical.analyzer_v2 import TechnicalAnalyzerV2
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
                        st.error("**FMP API Key not configured!**")
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
                    tech_analyzer = TechnicalAnalyzerV2(fmp)

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

                            # Analyze with fundamental data (V2 with orthogonal components)
                            tech_result = tech_analyzer.analyze(
                                symbol,
                                sector=sector,
                                fundamental_score=fundamental_score,
                                guardrails_status=guardrails_status,
                                fundamental_decision=fundamental_decision,
                                portfolio_value=100000,  # Default $100k portfolio
                                risk_per_trade=0.005  # Default 0.5% risk per trade
                            )

                            # Check if analysis returned an error
                            if 'error' in tech_result:
                                logger.warning(f"Tech analysis error for {symbol}: {tech_result['error']}")

                                # Try to get current price from FMP
                                current_price = 0
                                try:
                                    quote = fmp.get_quote(symbol)
                                    if quote and len(quote) > 0:
                                        current_price = quote[0].get('price', 0)
                                except:
                                    pass

                                # Add with error defaults
                                technical_results.append({
                                    'ticker': symbol,
                                    'name': row.get('name', ''),
                                    'sector': sector,
                                    'price': current_price,
                                    'fundamental_decision': row['decision'],
                                    'fundamental_score': row['composite_0_100'],
                                    'technical_score': 50,
                                    'rs_score': 0,
                                    'trend_score': 0,
                                    'risk_score': 0,
                                    'volume_score': 0,
                                    'extension_state': 'UNKNOWN',
                                    'regime_state': 'UNKNOWN',
                                    'trend_state': 'UNKNOWN',
                                    'conviction': 0,
                                    'position_size_pct': 0,
                                    'rs_12_1': 0,
                                    'rs_6_1_spy': 0,
                                    'rs_6_1_sector': 0,
                                    'sharpe_6m': 0,
                                    'max_dd_6m': 0,
                                    'volume_profile': 'UNKNOWN',
                                    'distance_ma200': 0,
                                    'stop_price': 0,
                                    'stop_distance_pct': 0,
                                    'warnings_count': 1,
                                    'warnings': [{'type': 'ERROR', 'category': 'DATA', 'message': tech_result['error']}],
                                    'error_reason': tech_result['error'],
                                    'full_analysis': None
                                })
                                continue  # Skip to next stock

                            # Get current price from tech_result metadata
                            current_price = tech_result.get('metadata', {}).get('current_price', 0)

                            # Extract V2 components
                            components = tech_result.get('components', {})
                            states = tech_result.get('states', {})
                            component_details = tech_result.get('component_details', {})

                            # Add to results (using NEW V2 orthogonal fields)
                            technical_results.append({
                                'ticker': symbol,
                                'name': row.get('name', ''),
                                'sector': sector,
                                'price': current_price,
                                'fundamental_decision': row['decision'],
                                'fundamental_score': row['composite_0_100'],
                                # V2 Orthogonal Components
                                'technical_score': tech_result['score'],
                                'rs_score': components.get('relative_strength', 0),
                                'trend_score': components.get('trend_structure', 0),
                                'risk_score': components.get('risk_quality', 0),
                                'volume_score': components.get('volume_participation', 0),
                                # V2 States
                                'extension_state': states.get('extension', 'UNKNOWN'),
                                'regime_state': states.get('regime', 'UNKNOWN'),
                                'trend_state': states.get('trend', 'UNKNOWN'),
                                # V2 Conviction & Sizing
                                'conviction': tech_result.get('conviction', 0),
                                'position_size_pct': tech_result.get('position_sizing', {}).get('position_pct_of_portfolio', 0),
                                # Component details (for drilling down)
                                'rs_12_1': component_details.get('relative_strength', {}).get('rs_12_1_vs_spy', 0),
                                'rs_6_1_spy': component_details.get('relative_strength', {}).get('rs_6_1_vs_spy', 0),
                                'rs_6_1_sector': component_details.get('relative_strength', {}).get('rs_6_1_vs_sector', 0),
                                'sharpe_6m': component_details.get('risk_quality', {}).get('sharpe_6m', 0),
                                'max_dd_6m': component_details.get('risk_quality', {}).get('max_drawdown_6m_pct', 0),
                                'volume_profile': component_details.get('volume_participation', {}).get('volume_profile', 'UNKNOWN'),
                                'distance_ma200': tech_result.get('metadata', {}).get('distance_ma200_pct', 0),
                                'warnings_count': len(tech_result.get('warnings', [])),
                                'warnings': tech_result.get('warnings', []),
                                # V2 Stop Loss (ATR-based)
                                'stop_price': tech_result.get('stop_loss', {}).get('stop_price', 0),
                                'stop_distance_pct': tech_result.get('stop_loss', {}).get('stop_distance_pct', 0),
                                # IMPORTANT: Save error reason for debugging issues
                                'error_reason': tech_result.get('error', None),
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

                            # Add with error (V2 defaults)
                            technical_results.append({
                                'ticker': symbol,
                                'name': row.get('name', ''),
                                'sector': sector,
                                'price': current_price,
                                'fundamental_decision': row['decision'],
                                'fundamental_score': row['composite_0_100'],
                                'technical_score': 50,
                                'rs_score': 0,
                                'trend_score': 0,
                                'risk_score': 0,
                                'volume_score': 0,
                                'extension_state': 'UNKNOWN',
                                'regime_state': 'UNKNOWN',
                                'trend_state': 'UNKNOWN',
                                'conviction': 0,
                                'position_size_pct': 0,
                                'rs_12_1': 0,
                                'rs_6_1_spy': 0,
                                'rs_6_1_sector': 0,
                                'sharpe_6m': 0,
                                'max_dd_6m': 0,
                                'volume_profile': 'UNKNOWN',
                                'distance_ma200': 0,
                                'stop_price': 0,
                                'stop_distance_pct': 0,
                                'warnings_count': 1,
                                'warnings': [{'type': 'ERROR', 'category': 'SYSTEM', 'message': str(e)}],
                                'error_reason': str(e),
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
                        st.subheader("Data Quality Diagnostics")
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

                            st.markdown("### Error Breakdown")

                            for error_reason, row in error_groups.iterrows():
                                count = row['count']
                                pct = (count / error_count * 100)
                                tickers = row['ticker'][:10]  # Show first 10 examples
                                more_count = count - len(tickers)

                                with st.expander(f"**{error_reason}** ({count} stocks, {pct:.1f}% of errors)", expanded=False):
                                    st.markdown(f"**Examples:** {', '.join(tickers)}" + (f" ...and {more_count} more" if more_count > 0 else ""))

                                    # Add specific recommendations based on error type
                                    if "No quote data" in error_reason:
                                        st.info("**Likely cause:** Delisted stocks, incorrect symbols, or stocks not available in FMP")
                                    elif "No historical data" in error_reason:
                                        st.info("**Likely cause:** New IPOs, low-liquidity stocks, or foreign symbols without data")
                                    elif "historical" in error_reason.lower() and "key" in error_reason.lower():
                                        st.warning("**Likely cause:** API response format changed or FMP data structure issue")
                                    else:
                                        st.info("**Recommendation:** Check symbol format and FMP availability")
                        else:
                            st.success("All stocks have complete technical data!")

                    # === SMARTDYNAMICSTOPLOSS STATE SUMMARY ===
                    st.markdown("---")
                    st.markdown("""
                    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 1.5rem;'>
                        <h3 style='margin: 0; color: white; font-weight: 600;'>
                            Estado del Mercado por Acción
                        </h3>
                        <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem;'>
                            SmartDynamicStopLoss - Clasificación automática del estado técnico actual
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

                    # Group by extension_state (V2)
                    extension_groups = df_tech.groupby('extension_state')['ticker'].apply(list).to_dict()

                    # Define state order and styling (V2)
                    extension_config = {
                        'NORMAL': {'icon': '✅', 'color': 'success', 'label': 'Normal (≤25% from MA200) - Full Size', 'priority': 1},
                        'EXTENDED': {'icon': '⚠️', 'color': 'warning', 'label': 'Extended (25-40%) - 70% Size', 'priority': 2},
                        'STRETCHED': {'icon': '🔶', 'color': 'warning', 'label': 'Stretched (40-55%) - 40% Size', 'priority': 3},
                        'OVEREXTENDED': {'icon': '🚨', 'color': 'error', 'label': 'Overextended (>55%) - 20% Size', 'priority': 4},
                        'UNKNOWN': {'icon': '❓', 'color': 'info', 'label': 'Unknown - Insufficient Data', 'priority': 99}
                    }

                    # Sort states by priority
                    sorted_extensions = sorted(
                        extension_groups.keys(),
                        key=lambda x: extension_config.get(x, {'priority': 999})['priority']
                    )

                    # Display in columns (2 per row for better visibility)
                    for i in range(0, len(sorted_extensions), 2):
                        cols = st.columns(2)

                        for j, col in enumerate(cols):
                            if i + j < len(sorted_extensions):
                                extension = sorted_extensions[i + j]
                                tickers = extension_groups[extension]
                                config = extension_config.get(extension, {'icon': '❓', 'color': 'info', 'label': extension, 'priority': 999})

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
                            st.write("**Conviction Distribution:**")
                            st.write(f"- High (≥0.7): {len(df_tech[df_tech['conviction'] >= 0.7])}")
                            st.write(f"- Med (0.3-0.7): {len(df_tech[(df_tech['conviction'] >= 0.3) & (df_tech['conviction'] < 0.7)])}")
                            st.write(f"- Low (<0.3): {len(df_tech[df_tech['conviction'] < 0.3])}")

                        with col2:
                            st.write("**Score Stats:**")
                            st.write(f"- Min: {df_tech['technical_score'].min():.1f}")
                            st.write(f"- Avg: {df_tech['technical_score'].mean():.1f}")
                            st.write(f"- Max: {df_tech['technical_score'].max():.1f}")

                        with col3:
                            st.write("**Top 3 by Conviction:**")
                            top3 = df_tech.nlargest(3, 'conviction')
                            for _, row in top3.iterrows():
                                st.write(f"- {row['ticker']}: Conv {row['conviction']:.2f} (Score {row['technical_score']:.0f})")

                except Exception as e:
                    st.error(f"Error initializing technical analysis: {str(e)}")
                    st.exception(e)

            # Display results
            if 'technical_results' in st.session_state:
                df_tech = st.session_state['technical_results']

                # Check if results are from old version (before error_reason column was added)
                if 'error_reason' not in df_tech.columns:
                    st.warning("""
                    **Outdated Results Detected**

                    Your technical results were generated with an older version of the code.

                    **Please click "Run Technical Analysis" again** to see the new **Data Quality Diagnostics** report.
                    """)
                    st.info("**New in this version:** Detailed breakdown showing WHY each stock has UNKNOWN data (delisted, no history, API errors, etc.)")

                # Summary metrics
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    high_conviction = len(df_tech[df_tech['conviction'] >= 0.7])
                    st.metric("🔥 High Conviction", high_conviction, f"{high_conviction/len(df_tech)*100:.0f}%")

                with col2:
                    med_conviction = len(df_tech[(df_tech['conviction'] >= 0.3) & (df_tech['conviction'] < 0.7)])
                    st.metric("⚖️ Med Conviction", med_conviction, f"{med_conviction/len(df_tech)*100:.0f}%")

                with col3:
                    avg_tech_score = df_tech['technical_score'].mean()
                    st.metric("Avg Tech Score", f"{avg_tech_score:.1f}")

                with col4:
                    # High quality + high conviction
                    strong_setups = len(df_tech[
                        (df_tech['fundamental_decision'] == 'BUY') &
                        (df_tech['conviction'] >= 0.5)
                    ])
                    st.metric("💎 Quality + Conv", strong_setups, "Fund + Tech")

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
                    if st.button("Top Quality", help="High conviction + high score"):
                        st.session_state['min_conviction'] = 0.7
                        st.session_state['min_tech_score'] = 75

                # Second row of presets (V2)
                st.markdown("")
                preset2_col1, preset2_col2, preset2_col3, preset2_col4, preset2_col5 = st.columns(5)

                with preset2_col1:
                    if st.button("Buy Opportunities", help="Optimal setup: Bull market + High conviction + Quality", key='buy_opp_preset'):
                        # V2 Filters
                        st.session_state['extension_filter'] = ['NORMAL', 'EXTENDED']  # Not overextended
                        st.session_state['fund_decision_filter'] = ['BUY', 'MONITOR']
                        st.session_state['min_conviction'] = 0.5  # At least moderate
                        st.session_state['regime_filter'] = ['BULL']
                        st.session_state['trend_filter'] = ['UPTREND']
                        st.session_state['volume_filter'] = ['ACCUMULATION', 'NEUTRAL']
                        st.rerun()

                with preset2_col2:
                    if st.button("Contrarian Setup", help="AVOID fundamentals + good technicals", key='contrarian_preset'):
                        st.session_state['fund_decision_filter'] = ['AVOID']
                        st.session_state['min_conviction'] = 0.5
                        st.session_state['min_tech_score'] = 70
                        st.rerun()

                with preset2_col3:
                    if st.button("Confirm AVOID", help="AVOID + weak technicals", key='confirm_avoid_preset'):
                        # Both fundamental and technical weakness
                        st.session_state['fund_decision_filter'] = ['AVOID']
                        st.session_state['min_conviction'] = 0.0
                        st.session_state['trend_filter'] = ['DOWNTREND', 'CHOP']
                        st.session_state['volume_filter'] = ['DISTRIBUTION']
                        st.rerun()

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
                        TRADING SIGNALS (Decision Outputs)
                    </div>
                </div>
                """, unsafe_allow_html=True)

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    # V2: Extension State filter (replaces technical signal)
                    extension_filter = st.multiselect(
                        "Extension State",
                        options=['NORMAL', 'EXTENDED', 'STRETCHED', 'OVEREXTENDED'],
                        default=['NORMAL', 'EXTENDED', 'STRETCHED', 'OVEREXTENDED'],
                        help="Distance from MA200 - affects position sizing",
                        key='extension_filter'
                    )

                with col2:
                    fund_decision_filter = st.multiselect(
                        "Fundamental Decision",
                        options=['BUY', 'MONITOR', 'AVOID'],
                        default=['BUY', 'MONITOR', 'AVOID'],
                        help="Fundamental quality+value decision - now includes AVOID for contrarian analysis",
                        key='fund_decision_filter'
                    )

                with col3:
                    min_tech_score = st.slider(
                        "Min Technical Score",
                        0, 100, 0,
                        help="Orthogonal score (RS + Trend + Risk + Volume)",
                        key='min_tech_score'
                    )

                with col4:
                    # V2: Conviction filter (replaces stop loss state)
                    min_conviction = st.slider(
                        "Min Conviction",
                        0.0, 1.0, 0.0,
                        step=0.1,
                        help="Conviction = (TechScore - 60) / 30, clamped 0-1",
                        key='min_conviction'
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
                    # V2: Regime State (renamed from market_regime)
                    regime_filter = st.multiselect(
                        "Market Regime",
                        options=['BULL', 'SIDEWAYS', 'BEAR'],
                        default=['BULL', 'SIDEWAYS', 'BEAR'],
                        help="Overall market state - affects position sizing only (not score)",
                        key='regime_filter'
                    )

                with col6:
                    # V2: Trend State (replaces sector status)
                    trend_filter = st.multiselect(
                        "Trend State",
                        options=['UPTREND', 'DOWNTREND', 'CHOP'],
                        default=['UPTREND', 'DOWNTREND', 'CHOP'],
                        help="Structural trend state - DOWNTREND triggers veto warnings",
                        key='trend_filter'
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
                        <strong>TIP:</strong> These components are ALREADY included in Technical Score and Signal.
                        Use these filters only for advanced diagnostic analysis to understand WHY a stock has a certain score.
                        Filtering by both Score ≥75 AND Trend=UPTREND is redundant (Trend already contributes 10-15 pts to Score).
                    </div>
                </div>
                """, unsafe_allow_html=True)

                with st.expander("Show Component Filters (Advanced - Usually Not Needed)", expanded=False):
                    st.caption("WARNING: Filtering by components AND score filters the same data twice. "
                              "These filters are for diagnosing WHY a score is high/low, not for primary filtering.")

                    col7, col8, col9 = st.columns(3)

                    with col7:
                        # V2: No trend field anymore, use volume_profile only
                        st.info("Component filters removed in V2 - use component score sliders instead")

                    with col8:
                        all_volumes = sorted(df_tech['volume_profile'].unique().tolist())
                        volume_filter = st.multiselect(
                            "Volume (Contributes ~5pts)",
                            options=all_volumes,
                            default=all_volumes,
                            help="REDUNDANT with Technical Score. Volume pattern already contributes ~5 pts to score. "
                                "Use this ONLY to diagnose why stocks have certain scores.",
                            key='volume_filter'
                        )

                    with col9:
                        # V2: momentum_consistency doesn't exist, show min score sliders instead
                        min_component_score = st.slider(
                            "Min Any Component",
                            0, 100, 0,
                            help="V2: Filter by minimum score in any single component",
                            key='min_any_component'
                        )

                # LEVEL 4: DATA QUALITY FILTER
                st.markdown("""
                <div style='background: #fef3c7; padding: 0.5rem 1rem; border-radius: 8px;
                            margin-top: 0.75rem; margin-bottom: 0.5rem; border-left: 4px solid #f59e0b;'>
                    <div style='color: #92400e; font-weight: 600; font-size: 0.85rem;'>
                        DATA QUALITY
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
                    # Count stocks with incomplete data (V2 fields)
                    incomplete_mask = (
                        (df_tech['regime_state'] == 'UNKNOWN') |
                        (df_tech['trend_state'] == 'UNKNOWN') |
                        (df_tech['extension_state'] == 'UNKNOWN')
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

                # Apply filters (V2)
                df_filtered = df_tech[
                    # Level 1: States & Scores
                    (df_tech['extension_state'].isin(extension_filter)) &
                    (df_tech['fundamental_decision'].isin(fund_decision_filter)) &
                    (df_tech['technical_score'] >= min_tech_score) &
                    (df_tech['conviction'] >= min_conviction) &
                    # Level 2: Market Context
                    (df_tech['regime_state'].isin(regime_filter)) &
                    (df_tech['trend_state'].isin(trend_filter)) &
                    # Level 3: Volume (keep this one as diagnostic)
                    (df_tech['volume_profile'].isin(volume_filter))
                ]

                # Level 4: Data Quality Filter (V2)
                if hide_incomplete_data:
                    df_filtered = df_filtered[
                        (df_filtered['regime_state'] != 'UNKNOWN') &
                        (df_filtered['trend_state'] != 'UNKNOWN') &
                        (df_filtered['extension_state'] != 'UNKNOWN')
                    ]

                st.markdown(f"""
                <div style='background: #dbeafe; padding: 0.75rem; border-radius: 8px; margin-top: 0.75rem;'>
                    <div style='font-size: 1.1rem; font-weight: 600; color: #1e40af;'>
                        {len(df_filtered)} stocks match filters
                        <span style='font-size: 0.85rem; color: #3b82f6; font-weight: 400;'>
                            (filtered from {len(df_tech)} total)
                        </span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Excel Export Button
                if len(df_filtered) > 0:
                    st.markdown("---")

                    # Portfolio size input
                    col_excel1, col_excel2, col_excel3 = st.columns([2, 2, 2])

                    with col_excel1:
                        portfolio_size = st.number_input(
                            "Tamaño Portfolio ($)",
                            min_value=1000,
                            max_value=10000000,
                            value=420000,
                            step=10000,
                            help="Tamaño total del portfolio para calcular position sizing"
                        )

                    with col_excel2:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("📥 Generar Excel de Posiciones", type="primary", use_container_width=True):
                            with st.spinner("Generando Excel..."):
                                try:
                                    excel_buffer = generate_positions_excel(df_filtered, portfolio_size)

                                    # Generate filename with timestamp
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    filename = f"posiciones_ultraquality_{timestamp}.xlsx"

                                    st.download_button(
                                        label="Descargar Excel",
                                        data=excel_buffer,
                                        file_name=filename,
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                        use_container_width=True
                                    )

                                    st.success(f"Excel generado: {len(df_filtered)} posiciones")

                                except Exception as e:
                                    st.error(f"Error generando Excel: {str(e)}")
                                    st.exception(e)

                    with col_excel3:
                        st.info(f"""
                        **Incluye:**
                        - Entrada escalonada (60%/40%)
                        - Stop Loss & Take Profit
                        - Pérdida potencial
                        - Fecha earnings
                        """)

                    st.markdown("---")

                # Main table
                st.subheader("Technical Ranking (Enhanced)")

                display_cols = [
                    'ticker', 'name', 'sector',
                    'technical_score', 'conviction',  # V2: Score + Conviction
                    'extension_state', 'trend_state', 'regime_state',  # V2: States
                    'rs_score', 'trend_score', 'risk_score', 'volume_score',  # V2: Component breakdown
                    'sharpe_6m', 'volume_profile',  # V2: Key details
                    'fundamental_score', 'fundamental_decision',
                    'warnings_count'
                ]

                # Format for display (V2)
                df_display = df_filtered[display_cols].copy()
                df_display['conviction'] = df_display['conviction'].apply(lambda x: f"{x:.2f}")
                df_display['sharpe_6m'] = df_display['sharpe_6m'].apply(lambda x: f"{x:.2f}")

                st.dataframe(
                    df_display,
                    use_container_width=True,
                    height=400,
                    column_config={
                        'ticker': 'Ticker',
                        'name': 'Company',
                        'sector': 'Sector',
                        'technical_score': st.column_config.NumberColumn(
                            'Tech Score',
                            help='Orthogonal: RS + Trend + Risk + Volume',
                            format='%.0f'
                        ),
                        'conviction': st.column_config.Column(
                            'Conviction',
                            help='(Score - 60) / 30, for sizing'
                        ),
                        'extension_state': st.column_config.Column(
                            'Extension',
                            help='Distance from MA200 - affects position size'
                        ),
                        'trend_state': st.column_config.Column(
                            'Trend',
                            help='Structural trend state'
                        ),
                        'regime_state': st.column_config.Column(
                            'Regime',
                            help='Market regime (affects sizing only)'
                        ),
                        'rs_score': st.column_config.NumberColumn('RS', format='%.0f'),
                        'trend_score': st.column_config.NumberColumn('Trend', format='%.0f'),
                        'risk_score': st.column_config.NumberColumn('Risk', format='%.0f'),
                        'volume_score': st.column_config.NumberColumn('Vol', format='%.0f'),
                        'sharpe_6m': 'Sharpe 6M',
                        'volume_profile': 'Vol Profile',
                        'fundamental_score': st.column_config.NumberColumn(
                            'Fund Score',
                            format='%.0f'
                        ),
                        'fundamental_decision': 'Fund Decision',
                        'warnings_count': '⚠️'
                    }
                )

                # Detailed analysis section
                st.markdown("---")
                st.subheader("Detailed Analysis")

                # Helper function: Unified recommendation logic
                def calculate_final_action(fund_decision: str, conviction: float, extension: str, trend: str, tech_score: float = 0) -> dict:
                    """
                    Single source of truth for recommendation.

                    Returns:
                        {
                            'action': 'STRONG_BUY' | 'BUY' | 'TACTICAL_SCALE_IN' | 'WAIT_PULLBACK' | 'WAIT' | 'MONITOR' | 'AVOID',
                            'label': display text,
                            'color': CSS color,
                            'reason': explanation,
                            'execution': 'ENTER_NOW' | 'WAIT_TRIGGER' | 'NO_ENTRY'
                        }
                    """
                    # Kill switch: DOWNTREND vetos all
                    if trend == 'DOWNTREND':
                        return {
                            'action': 'AVOID',
                            'label': 'AVOID - Downtrend',
                            'color': '#dc3545',
                            'reason': 'Structure broken (price < MA50). Wait for recovery.',
                            'execution': 'NO_ENTRY'
                        }

                    # BUY fundamentals path
                    if fund_decision == 'BUY':
                        if conviction >= 0.5 and extension in ['NORMAL', 'EXTENDED']:
                            return {
                                'action': 'STRONG_BUY',
                                'label': 'STRONG BUY',
                                'color': '#28a745',
                                'reason': f'Quality + Strong Conviction ({conviction:.2f}) + Good Entry',
                                'execution': 'ENTER_NOW'
                            }
                        elif conviction >= 0.3:
                            return {
                                'action': 'BUY',
                                'label': 'BUY',
                                'color': '#17a2b8',
                                'reason': f'Good fundamentals, moderate timing (Conv: {conviction:.2f})',
                                'execution': 'ENTER_NOW'
                            }
                        else:
                            return {
                                'action': 'WAIT',
                                'label': 'WAIT',
                                'color': '#ffc107',
                                'reason': f'Good company, weak timing (Conv: {conviction:.2f})',
                                'execution': 'WAIT_TRIGGER'
                            }

                    # MONITOR fundamentals path
                    elif fund_decision == 'MONITOR':
                        # Policy: If tech strong + uptrend BUT overextended → wait for pullback
                        if tech_score >= 75 and conviction >= 0.25 and trend == 'UPTREND':
                            if extension in ['STRETCHED', 'OVEREXTENDED']:
                                return {
                                    'action': 'WAIT_PULLBACK',
                                    'label': 'WAIT (Scale-in on pullback)',
                                    'color': '#ffc107',
                                    'reason': f'Adequate fundamentals + Strong technicals ({int(tech_score)}/100), but overextended ({extension}). Wait for pullback to EMA20/MA50 or extension drops to EXTENDED/NORMAL.',
                                    'execution': 'WAIT_TRIGGER'
                                }
                            else:
                                # NORMAL or EXTENDED → allow tactical entry
                                return {
                                    'action': 'TACTICAL_SCALE_IN',
                                    'label': 'TACTICAL SCALE-IN (Small Now)',
                                    'color': '#17a2b8',
                                    'reason': f'Adequate fundamentals + Strong technicals ({int(tech_score)}/100) + Uptrend + Good entry. Small position only (Conv: {conviction:.2f})',
                                    'execution': 'ENTER_NOW'
                                }
                        # Otherwise, stay in MONITOR (wait for fundamental improvement)
                        else:
                            conv_label = 'High' if conviction >= 0.5 else 'Med' if conviction >= 0.3 else 'Low'
                            return {
                                'action': 'MONITOR',
                                'label': 'MONITOR',
                                'color': '#ffc107',
                                'reason': f'Fundamentals adequate but not high conviction. Tech Conv: {conv_label} ({conviction:.2f}) | Extension: {extension}',
                                'execution': 'NO_ENTRY'
                            }

                    # AVOID fundamentals
                    else:
                        return {
                            'action': 'AVOID',
                            'label': 'AVOID',
                            'color': '#dc3545',
                            'reason': 'Weak fundamentals',
                            'execution': 'NO_ENTRY'
                        }

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
                            # Get unified recommendation (single source of truth)
                            fund_signal = stock_data['fundamental_decision']
                            conviction = stock_data.get('conviction', 0)
                            extension = stock_data.get('extension_state', 'UNKNOWN')
                            trend = stock_data.get('trend_state', 'UNKNOWN')
                            tech_score = stock_data.get('technical_score', 0)

                            # Calculate final action using unified logic
                            final_action = calculate_final_action(fund_signal, conviction, extension, trend, tech_score)

                            # Display badge based on final_action
                            if final_action['action'] == 'STRONG_BUY':
                                st.markdown(f"""
                                <div style='background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
                                            padding: 1rem; border-radius: 10px; text-align: center;'>
                                    <span class='badge badge-buy' style='font-size: 1.1rem;'>
                                        <i class="bi bi-check-circle-fill"></i> {final_action['label']}
                                    </span>
                                    <div style='color: white; margin-top: 0.5rem; font-size: 0.9rem;'>{final_action['reason']}</div>
                                </div>
                                """, unsafe_allow_html=True)
                            elif final_action['action'] == 'BUY':
                                st.markdown(f"""
                                <div style='background: #d1ecf1; padding: 1rem; border-radius: 10px; text-align: center;
                                            border-left: 4px solid #17a2b8;'>
                                    <span class='badge badge-buy'>
                                        <i class="bi bi-arrow-up-circle"></i> {final_action['label']}
                                    </span>
                                    <div style='color: #495057; margin-top: 0.5rem; font-size: 0.9rem;'>{final_action['reason']}</div>
                                </div>
                                """, unsafe_allow_html=True)
                            elif final_action['action'] == 'WAIT':
                                st.markdown(f"""
                                <div style='background: #fff3cd; padding: 1rem; border-radius: 10px; text-align: center;
                                            border-left: 4px solid #ffc107;'>
                                    <span class='badge badge-monitor'>
                                        <i class="bi bi-pause-circle"></i> {final_action['label']}
                                    </span>
                                    <div style='color: #495057; margin-top: 0.5rem; font-size: 0.9rem;'>{final_action['reason']}</div>
                                </div>
                                """, unsafe_allow_html=True)
                            elif final_action['action'] == 'WAIT_PULLBACK':
                                st.markdown(f"""
                                <div style='background: #fff3cd; padding: 1rem; border-radius: 10px; text-align: center;
                                            border-left: 4px solid #ff9800;'>
                                    <span class='badge badge-monitor'>
                                        <i class="bi bi-arrow-down-up"></i> {final_action['label']}
                                    </span>
                                    <div style='color: #495057; margin-top: 0.5rem; font-size: 0.9rem;'>{final_action['reason']}</div>
                                </div>
                                """, unsafe_allow_html=True)
                            elif final_action['action'] == 'TACTICAL_SCALE_IN':
                                st.markdown(f"""
                                <div style='background: #d1ecf1; padding: 1rem; border-radius: 10px; text-align: center;
                                            border-left: 4px solid #17a2b8;'>
                                    <span class='badge badge-buy'>
                                        <i class="bi bi-graph-up-arrow"></i> {final_action['label']}
                                    </span>
                                    <div style='color: #495057; margin-top: 0.5rem; font-size: 0.9rem;'>{final_action['reason']}</div>
                                </div>
                                """, unsafe_allow_html=True)
                            elif final_action['action'] == 'MONITOR':
                                st.markdown(f"""
                                <div style='background: #fff3cd; padding: 1rem; border-radius: 10px; text-align: center;
                                            border-left: 4px solid #ffc107;'>
                                    <span class='badge badge-monitor'>
                                        <i class="bi bi-eye"></i> {final_action['label']}
                                    </span>
                                    <div style='color: #495057; margin-top: 0.5rem; font-size: 0.9rem;'>{final_action['reason']}</div>
                                </div>
                                """, unsafe_allow_html=True)
                            else:  # AVOID
                                st.markdown(f"""
                                <div style='background: #f8d7da; padding: 1rem; border-radius: 10px; text-align: center;
                                            border-left: 4px solid #dc3545;'>
                                    <span class='badge badge-avoid'>
                                        <i class="bi bi-x-circle"></i> {final_action['label']}
                                    </span>
                                    <div style='color: #721c24; margin-top: 0.5rem; font-size: 0.9rem;'>{final_action['reason']}</div>
                                </div>
                                """, unsafe_allow_html=True)

                        # Score breakdown
                        st.markdown("#### Score Breakdown")

                        col1, col2, col3 = st.columns(3)

                        with col1:
                            # V2: Show conviction as delta instead of signal
                            conviction_val = full_analysis.get('conviction', 0)
                            conv_delta = f"Conv: {conviction_val:.2f}"
                            st.metric(
                                "Technical Score",
                                f"{full_analysis['score']:.0f}/100",
                                delta=conv_delta
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

                        # Get data for the 3 cards (V2)
                        states = full_analysis.get('states', {})
                        market_regime = states.get('regime', 'UNKNOWN')
                        trend = states.get('trend', 'UNKNOWN')
                        extension_state = states.get('extension', 'UNKNOWN')

                        metadata = full_analysis.get('metadata', {})
                        distance_ma200 = metadata.get('distance_ma200_pct', 0)

                        volume_profile = full_analysis.get('volume_profile', 'UNKNOWN')
                        components = full_analysis.get('component_scores', {})
                        conviction = full_analysis.get('conviction', 0)

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
                                    'risk_color': '#28a745',
                                    'size_factor': '1.0x'
                                },
                                'BEAR': {
                                    'icon': '<i class="bi bi-graph-down-arrow" style="font-size: 3rem;"></i>',
                                    'label': 'BEAR MARKET',
                                    'bg': 'linear-gradient(135deg, #dc3545 0%, #c82333 100%)',
                                    'effectiveness': '-60%',
                                    'risk': 'HIGH',
                                    'risk_color': '#dc3545',
                                    'size_factor': '0.4x'
                                },
                                'SIDEWAYS': {
                                    'icon': '<i class="bi bi-arrow-left-right" style="font-size: 3rem;"></i>',
                                    'label': 'SIDEWAYS MARKET',
                                    'bg': 'linear-gradient(135deg, #ffc107 0%, #ff9800 100%)',
                                    'effectiveness': '-30%',
                                    'risk': 'MEDIUM',
                                    'risk_color': '#ffc107',
                                    'size_factor': '0.7x'
                                }
                            }

                            reg_info = regime_config.get(market_regime, {
                                'icon': '<i class="bi bi-question-circle" style="font-size: 3rem;"></i>',
                                'label': 'UNKNOWN',
                                'bg': 'linear-gradient(135deg, #6c757d 0%, #495057 100%)',
                                'effectiveness': 'N/A',
                                'risk': 'UNKNOWN',
                                'risk_color': '#6c757d',
                                'size_factor': 'N/A'
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
                                    <div style='font-size: 0.75rem; opacity: 0.9;'>POSITION SIZE FACTOR</div>
                                    <div style='font-size: 1.5rem; font-weight: 700;'>{reg_info.get('size_factor', '1.0x')}</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        with col2:
                            # TARJETA 2: RELATIVE STRENGTH (V2)
                            # Use numeric RS scores from V2 component details
                            rs_details = full_analysis.get('component_details', {}).get('relative_strength', {})
                            rs_spy = rs_details.get('rs_12_1_vs_spy', 0)  # 12-1 month RS vs SPY
                            rs_sector = rs_details.get('rs_6_1_vs_sector', 0)  # 6-1 month RS vs Sector

                            # Determine colors based on RS values (positive = outperforming)
                            spy_color = '#28a745' if rs_spy > 10 else '#dc3545' if rs_spy < -10 else '#ffc107'
                            sector_color = '#28a745' if rs_sector > 5 else '#dc3545' if rs_sector < -5 else '#ffc107'

                            # Overall verdict based on RS strength
                            if rs_spy > 10 and rs_sector > 5:
                                verdict = 'DOUBLE LEADER'
                                verdict_icon = '<i class="bi bi-star-fill"></i>'
                                verdict_color = '#28a745'
                            elif rs_spy < -10 or rs_sector < -5:
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
                                    <div style='font-size: 0.75rem; opacity: 0.9;'>STOCK vs SPY (12-1M)</div>
                                    <div style='font-size: 1.8rem; font-weight: 700; color: {spy_color};'>{rs_spy:+.1f}%</div>
                                    <div style='font-size: 0.85rem; opacity: 0.9;'>{'Outperforming' if rs_spy > 0 else 'Underperforming'}</div>
                                </div>
                                <div style='background: rgba(255,255,255,0.15); padding: 1rem; border-radius: 8px; margin-bottom: 0.75rem;'>
                                    <div style='font-size: 0.75rem; opacity: 0.9;'>STOCK vs SECTOR (6-1M)</div>
                                    <div style='font-size: 1.8rem; font-weight: 700; color: {sector_color};'>{rs_sector:+.1f}%</div>
                                    <div style='font-size: 0.85rem; opacity: 0.9;'>{'Sector Leader' if rs_sector > 0 else 'Sector Laggard'}</div>
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

                            # Extension level colors (V2 states)
                            ext_config = {
                                'NORMAL': {'color': '#28a745', 'label': 'NORMAL', 'desc': '≤25% from MA200'},
                                'EXTENDED': {'color': '#ffc107', 'label': 'EXTENDED', 'desc': '25-40% from MA200'},
                                'STRETCHED': {'color': '#ff6b35', 'label': 'STRETCHED', 'desc': '40-55% from MA200'},
                                'OVEREXTENDED': {'color': '#dc3545', 'label': 'OVEREXTENDED', 'desc': '>55% from MA200'}
                            }

                            ext_info = ext_config.get(extension_state, {'color': '#6c757d', 'label': 'UNKNOWN', 'desc': 'N/A'})

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

                            # V2: Relative Strength Display (replaces absolute returns)
                            st.markdown("**Relative Strength vs Benchmarks:**")

                            # Get RS data from V2
                            rs_details = full_analysis.get('component_details', {}).get('relative_strength', {})
                            rs_12_1_spy = rs_details.get('rs_12_1_vs_spy', 0)
                            rs_6_1_spy = rs_details.get('rs_6_1_vs_spy', 0)
                            rs_6_1_sector = rs_details.get('rs_6_1_vs_sector', 0)
                            rs_score = full_analysis.get('components', {}).get('relative_strength', 0)

                            # Display each RS metric with color coding
                            for label, value, max_pts in [
                                ('RS 12-1M vs SPY', rs_12_1_spy, 18),
                                ('RS 6-1M vs SPY', rs_6_1_spy, 12),
                                ('RS 6-1M vs Sector', rs_6_1_sector, 10)
                            ]:
                                rs_color = '#28a745' if value > 10 else '#ffc107' if value > 0 else '#dc3545'
                                rs_norm = min(max((value + 30) / 60, 0), 1)  # Normalize -30 to +30

                                st.markdown(f"""
                                <div style='background: white; padding: 1rem; border-radius: 8px;
                                            box-shadow: 0 2px 6px rgba(0,0,0,0.08); margin-bottom: 0.75rem;
                                            border-left: 4px solid {rs_color};'>
                                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                                        <div style='font-size: 0.9rem; color: #6c757d; font-weight: 600;'>{label}</div>
                                        <div style='font-size: 1.5rem; font-weight: 700; color: {rs_color};'>{value:+.1f}%</div>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                                st.progress(rs_norm)

                            # Total RS Score
                            st.markdown(f"""
                            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                        padding: 1rem; border-radius: 8px; text-align: center; color: white;'>
                                <div style='font-size: 0.9rem; opacity: 0.9;'>TOTAL RS SCORE</div>
                                <div style='font-size: 2rem; font-weight: 700;'>{rs_score:.0f}/40</div>
                            </div>
                            """, unsafe_allow_html=True)

                            st.markdown("<br>", unsafe_allow_html=True)

                            # V2: Conviction Breakdown
                            conv_breakdown = full_analysis.get('conviction_breakdown', {})
                            if conv_breakdown:
                                st.markdown("**Conviction Breakdown:**")

                                # Get values from breakdown and full_analysis
                                setup_str = conv_breakdown.get('setup_strength', 0)
                                market_f = conv_breakdown.get('market_factor', 1.0)
                                timing_f = conv_breakdown.get('timing_factor', 1.0)
                                data_f = conv_breakdown.get('data_factor', 1.0)
                                final_conv = conv_breakdown.get('conviction', 0)

                                # Get context variables for display
                                tech_score_val = full_analysis.get('score', 0)
                                states_data = full_analysis.get('states', {})
                                market_regime_val = states_data.get('regime', 'UNKNOWN')
                                extension_state_val = states_data.get('extension', 'UNKNOWN')
                                volume_profile_val = full_analysis.get('volume_profile', 'UNKNOWN')

                                st.markdown(f"""
                                <div style='background: white; padding: 1rem; border-radius: 8px;
                                            box-shadow: 0 2px 6px rgba(0,0,0,0.08);'>
                                    <div style='font-size: 0.85rem; color: #6c757d; margin-bottom: 0.75rem;'>
                                        conviction = setup × market × timing × data
                                    </div>
                                    <div style='font-size: 1rem; color: #495057; margin-bottom: 0.5rem;'>
                                        <strong>{final_conv:.3f}</strong> = {setup_str:.2f} × {market_f:.2f} × {timing_f:.2f} × {data_f:.2f}
                                    </div>
                                    <div style='font-size: 0.8rem; color: #6c757d;'>
                                        Setup: {setup_str:.2f} (from tech score {tech_score_val:.0f}/100)<br>
                                        Market: {market_f:.2f} (regime: {market_regime_val})<br>
                                        Timing: {timing_f:.2f} (extension: {extension_state_val})<br>
                                        Data: {data_f:.2f} (volume: {volume_profile_val})
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)

                            # V2: Conviction Badge (replaces consistency)
                            conviction = full_analysis.get('conviction', 0)
                            # Map conviction to status labels
                            if conviction >= 0.7:
                                conviction_status = 'HIGH'
                            elif conviction >= 0.3:
                                conviction_status = 'MEDIUM'
                            else:
                                conviction_status = 'LOW'

                            # V2: Conviction config
                            conviction_config = {
                                'HIGH': {'color': '#28a745', 'icon': '<i class="bi bi-gem"></i>', 'label': 'HIGH CONVICTION'},
                                'MEDIUM': {'color': '#ffc107', 'icon': '<i class="bi bi-check-circle"></i>', 'label': 'MEDIUM CONVICTION'},
                                'LOW': {'color': '#dc3545', 'icon': '<i class="bi bi-x-circle"></i>', 'label': 'LOW CONVICTION'}
                            }

                            conviction_info = conviction_config.get(conviction_status, {'color': '#6c757d', 'icon': '<i class="bi bi-question-circle"></i>', 'label': conviction_status})

                            st.markdown("<br>", unsafe_allow_html=True)
                            st.markdown(f"""
                            <div style='background: {conviction_info['color']}; padding: 1.25rem; border-radius: 10px;
                                        text-align: center; color: white; margin-bottom: 1rem;'>
                                <div style='font-size: 2rem; margin-bottom: 0.5rem;'>{conviction_info['icon']}</div>
                                <div style='font-size: 1.2rem; font-weight: 700;'>{conviction_info['label']}</div>
                                <div style='font-size: 0.9rem; opacity: 0.9; margin-top: 0.5rem;'>Conviction Score: {conviction:.2f}</div>
                            </div>
                            """, unsafe_allow_html=True)

                            # RS Status (V2)
                            rs_details = full_analysis.get('component_details', {}).get('relative_strength', {})
                            rs_12_1 = rs_details.get('rs_12_1_vs_spy', 0)
                            st.markdown(f"""
                            <div style='background: #f8f9fa; padding: 1rem; border-radius: 8px;
                                        border-left: 4px solid {conviction_info['color']};'>
                                <div style='font-size: 0.85rem; color: #6c757d; margin-bottom: 0.25rem;'>RS 12-1 vs SPY</div>
                                <div style='font-size: 1.1rem; font-weight: 600; color: #495057;'>{rs_12_1:+.1f}%</div>
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
                            # V2: Get risk metrics from component_details
                            risk_details = full_analysis.get('component_details', {}).get('risk_quality', {})
                            sharpe = risk_details.get('sharpe_6m', 0)
                            sortino = risk_details.get('sortino_6m', 0)
                            max_dd = risk_details.get('max_drawdown_6m_pct', 0)
                            volatility = risk_details.get('realized_vol_pct', 0)

                            # Sharpe Ratio
                            sharpe_color = '#28a745' if sharpe > 1.0 else '#ffc107' if sharpe > 0.5 else '#dc3545'
                            sharpe_normalized = min(max(sharpe / 2.0, 0), 1)

                            st.markdown(f"""
                            <div style='background: white; padding: 1rem; border-radius: 8px;
                                        box-shadow: 0 2px 6px rgba(0,0,0,0.08); margin-bottom: 0.75rem;
                                        border-left: 4px solid {sharpe_color};'>
                                <div style='font-size: 0.85rem; color: #6c757d; margin-bottom: 0.5rem;'>SHARPE RATIO (6M)</div>
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

                            # Distance from MA200 (V2: use already-extracted distance_ma200)
                            dist_color = '#28a745' if -5 <= distance_ma200 <= 20 else '#ffc107' if -15 <= distance_ma200 <= 40 else '#dc3545'

                            st.markdown(f"""
                            <div style='background: white; padding: 1rem; border-radius: 8px;
                                        box-shadow: 0 2px 6px rgba(0,0,0,0.08); margin-bottom: 0.75rem;
                                        border-left: 4px solid {dist_color};'>
                                <div style='font-size: 0.85rem; color: #6c757d; margin-bottom: 0.5rem;'>DISTANCE FROM MA200</div>
                                <div style='font-size: 2rem; font-weight: 700; color: {dist_color}; text-align: center;'>{distance_ma200:+.1f}%</div>
                                <div style='font-size: 0.8rem; color: #6c757d; text-align: center;'>
                                    {'Healthy' if -5 <= distance_ma200 <= 20 else 'Stretched' if -15 <= distance_ma200 <= 40 else 'Overextended'}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                            # Extension Risk Gauge (V2)
                            st.markdown("<br>", unsafe_allow_html=True)
                            st.markdown("**Extension Risk:**")

                            # Map extension_state to numeric risk for display
                            ext_risk_map = {
                                'NORMAL': (1, 'LOW', '#28a745'),
                                'EXTENDED': (3, 'MEDIUM', '#ffc107'),
                                'STRETCHED': (5, 'HIGH', '#ff6b35'),
                                'OVEREXTENDED': (7, 'EXTREME', '#dc3545')
                            }
                            ext_risk_val, ext_risk_label, ext_risk_color = ext_risk_map.get(
                                extension_state, (1, 'UNKNOWN', '#6c757d')
                            )
                            ext_risk_norm = ext_risk_val / 7  # Normalize 0-7 to 0-1

                            st.markdown(f"""
                            <div style='background: {ext_risk_color}; padding: 1.25rem; border-radius: 10px;
                                        text-align: center; color: white; margin-bottom: 1rem;'>
                                <div style='font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem;'>{extension_state}</div>
                                <div style='font-size: 1.2rem; font-weight: 600;'>{distance_ma200:+.1f}% from MA200</div>
                                <div style='font-size: 0.9rem; opacity: 0.9; margin-top: 0.5rem;'>Extension Level</div>
                            </div>
                            """, unsafe_allow_html=True)
                            st.progress(ext_risk_norm)

                            # Risk interpretation (V2)
                            if extension_state == 'OVEREXTENDED':
                                st.error("EXTREME: Alto riesgo de corrección 20-40%")
                            elif extension_state == 'STRETCHED':
                                st.warning("HIGH: Posible retroceso 10-20%")
                            elif extension_state == 'EXTENDED':
                                st.info("MEDIUM: Monitorear reversiones")
                            else:
                                st.success("NORMAL: Riesgo controlado")

                        st.markdown("---")

                        # ========== MÓDULO 3: LA CALCULADORA DE TAMAÑO ==========
                        st.markdown("""
                        <div style='background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                                    padding: 1.5rem; border-radius: 12px; margin-bottom: 2rem; margin-top: 2rem;'>
                            <h3 style='margin: 0; color: white;'><i class="bi bi-calculator"></i> MÓDULO 3: CALCULADORA DE TAMAÑO</h3>
                            <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem;'>
                                Dual Constraint System: MIN(Risk Budget, Risk-Based Stop)
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                        # Get risk management recommendations (V2: direct fields)
                        pos_sizing = full_analysis.get('position_sizing', {})
                        stop_loss_data = full_analysis.get('stop_loss', {})

                        if pos_sizing:
                            # Get current price from metadata for V2
                            current_price = full_analysis.get('metadata', {}).get('current_price', stock_data.get('price', 0))

                            # Use enhanced display function with dual constraint system
                            display_position_sizing(
                                pos_sizing,
                                stop_loss_data=stop_loss_data,
                                portfolio_size=portfolio_capital,
                                max_risk_dollars=max_risk_per_trade_dollars,
                                current_price=current_price,
                                selected_ticker=selected_ticker,
                                execution_mode=final_action.get('execution', 'ENTER_NOW')
                            )
                        else:
                            st.warning("No position sizing data available")

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

                        # V2: Stop Loss (direct field, no entry_strategy or options in V2)
                        if stop_loss_data:
                            # Get current price from metadata
                            current_price = full_analysis.get('metadata', {}).get('current_price', stock_data.get('price', 0))
                            display_smart_stop_loss(stop_loss_data, current_price)
                        else:
                            st.warning("No stop loss data available")

                        # V2 Note: Entry strategy and options are not part of V2 orthogonal analysis
                        st.info("V2 uses ATR-based stop loss with automatic position sizing. Entry strategy is based on extension state and conviction level.")

                        # ========== INSIDER TRADING & INSTITUTIONAL HOLDINGS ==========
                        # Check if qualitative data is available
                        qual_data_for_smart_money = None
                        if 'results' in st.session_state:
                            df_results = st.session_state['results']
                            if selected_ticker in df_results['ticker'].values:
                                qual_key = f'qual_{selected_ticker}'
                                if qual_key in st.session_state:
                                    qual_data_for_smart_money = st.session_state[qual_key]

                        # Get insider data from qualitative analysis
                        insider = None
                        if qual_data_for_smart_money:
                            insider = qual_data_for_smart_money.get('insider_trading', {})

                        if insider:
                            # Show header
                            st.markdown("""
                            <div style='background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
                                        padding: 1.5rem; border-radius: 12px; margin-bottom: 2rem; margin-top: 2rem;'>
                                <h3 style='margin: 0; color: white;'>Insider Trading & Institutional Holdings</h3>
                                <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem;'>
                                    Smart money signals and institutional activity
                                </p>
                            </div>
                            """, unsafe_allow_html=True)

                            # ============================================================
                            # SUBSECTION: Insider Trading Activity (Last 12 Months)
                            # ============================================================
                            st.markdown("""
                            <div style='background: #f8fafc; padding: 1rem; border-left: 4px solid #667eea; margin-bottom: 1rem;'>
                                <h4 style='margin: 0 0 0.5rem 0; color: #1e293b; font-weight: 600;'>
                                    Insider Trading Activity (Last 12 Months)
                                </h4>
                                <p style='margin: 0; color: #64748b; font-size: 0.85rem;'>
                                    Compras vs ventas de ejecutivos y directores
                                </p>
                            </div>
                            """, unsafe_allow_html=True)

                            # Get insider trading data
                            buys = insider.get('insider_transactions', {}).get('buys', 0)
                            sells = insider.get('insider_transactions', {}).get('sells', 0)
                            trend = insider.get('insider_trend_90d', 'none')

                            # Display in columns
                            col1, col2, col3 = st.columns(3)

                            with col1:
                                st.markdown(f"""
                                <div style='background: white; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;'>
                                    <div style='font-size: 2rem; font-weight: 700; color: #10b981; margin-bottom: 0.25rem;'>
                                        {buys}
                                    </div>
                                    <div style='font-size: 0.85rem; color: #64748b; font-weight: 600;'>
                                        COMPRAS
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)

                            with col2:
                                st.markdown(f"""
                                <div style='background: white; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;'>
                                    <div style='font-size: 2rem; font-weight: 700; color: #ef4444; margin-bottom: 0.25rem;'>
                                        {sells}
                                    </div>
                                    <div style='font-size: 0.85rem; color: #64748b; font-weight: 600;'>
                                        VENTAS
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)

                            with col3:
                                # Calculate net balance
                                net_balance = buys - sells
                                if net_balance > 0:
                                    balance_color = '#10b981'
                                    balance_text = 'NET COMPRA'
                                    balance_badge = f'+{net_balance}'
                                elif net_balance < 0:
                                    balance_color = '#ef4444'
                                    balance_text = 'NET VENTA'
                                    balance_badge = f'{net_balance}'
                                else:
                                    balance_color = '#6b7280'
                                    balance_text = 'NEUTRAL'
                                    balance_badge = '0'

                                st.markdown(f"""
                                <div style='background: white; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;'>
                                    <div style='font-size: 2rem; font-weight: 700; color: {balance_color}; margin-bottom: 0.25rem;'>
                                        {balance_badge}
                                    </div>
                                    <div style='font-size: 0.85rem; color: #64748b; font-weight: 600;'>
                                        {balance_text}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)

                            # Interpretation
                            if net_balance > 3:
                                st.success(f"Señal positiva: Los insiders están comprando más que vendiendo. Posible confianza en el futuro de la empresa.")
                            elif net_balance < -3:
                                st.warning(f"Señal de precaución: Los insiders están vendiendo más que comprando. Puede indicar preocupaciones o simplemente toma de ganancias.")
                            else:
                                st.info(f"Neutral: Actividad de insider trading balanceada o mínima.")

                            st.markdown("---")

                            # ============================================================
                            # SUBSECTION: Institutional Holdings Balance
                            # ============================================================
                            st.markdown("""
                            <div style='background: #f8fafc; padding: 1rem; border-left: 4px solid #764ba2; margin-bottom: 1rem;'>
                                <h4 style='margin: 0 0 0.5rem 0; color: #1e293b; font-weight: 600;'>
                                    Institutional Holdings Balance
                                </h4>
                                <p style='margin: 0; color: #64748b; font-size: 0.85rem;'>
                                    Balance de compra/venta de fondos e instituciones
                                </p>
                            </div>
                            """, unsafe_allow_html=True)

                            # Try to get institutional ownership from FMP
                            try:
                                institutional_holders = fmp.get_institutional_holders(selected_ticker)

                                if institutional_holders and len(institutional_holders) > 0:
                                    # Calculate total institutional ownership
                                    total_inst_shares = sum(h.get('shares', 0) for h in institutional_holders)

                                    # Get shares outstanding from df
                                    shares_out = None
                                    if 'results' in st.session_state:
                                        df_results = st.session_state['results']
                                        ticker_row = df_results[df_results['ticker'] == selected_ticker]
                                        if not ticker_row.empty and 'shares_outstanding' in ticker_row.columns:
                                            shares_out = ticker_row['shares_outstanding'].iloc[0]

                                    # Display institutional ownership percentage
                                    if shares_out and shares_out > 0:
                                        inst_own_pct = (total_inst_shares / shares_out) * 100

                                        st.markdown(f"""
                                        <div style='background: white; padding: 1.5rem; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 1rem;'>
                                            <div style='text-align: center;'>
                                                <div style='font-size: 3rem; font-weight: 700; color: #667eea; margin-bottom: 0.5rem;'>
                                                    {inst_own_pct:.1f}%
                                                </div>
                                                <div style='font-size: 1rem; color: #64748b; font-weight: 600;'>
                                                    INSTITUTIONAL OWNERSHIP
                                                </div>
                                            </div>
                                        </div>
                                        """, unsafe_allow_html=True)

                                    # Show top 15 institutional holders
                                    st.caption(f"**Top 15 Institutional Holders** (Total: {len(institutional_holders)} instituciones)")

                                    # Sort by shares held
                                    top_holders = sorted(institutional_holders, key=lambda x: x.get('shares', 0), reverse=True)[:15]

                                    for i, holder in enumerate(top_holders, 1):
                                        holder_name = holder.get('holder', 'Unknown')
                                        shares = holder.get('shares', 0)
                                        date = holder.get('dateReported', 'N/A')
                                        change = holder.get('change', 0)

                                        # Calculate percentage ownership if we have shares_out
                                        if shares_out and shares_out > 0:
                                            holder_pct = (shares / shares_out) * 100
                                            shares_text = f"{shares:,} ({holder_pct:.2f}%)"
                                        else:
                                            shares_text = f"{shares:,}"

                                        # Determine change badge
                                        if change > 0:
                                            change_badge = f'<span style="background: #10b981; color: white; padding: 0.15rem 0.4rem; border-radius: 3px; font-size: 0.7rem; font-weight: 700;">+{change:,}</span>'
                                        elif change < 0:
                                            change_badge = f'<span style="background: #ef4444; color: white; padding: 0.15rem 0.4rem; border-radius: 3px; font-size: 0.7rem; font-weight: 700;">{change:,}</span>'
                                        else:
                                            change_badge = f'<span style="background: #6b7280; color: white; padding: 0.15rem 0.4rem; border-radius: 3px; font-size: 0.7rem; font-weight: 700;">SIN CAMBIO</span>'

                                        st.markdown(f"""
                                        <div style='background: #f8fafc; padding: 0.75rem 1rem; border-radius: 6px; margin-bottom: 0.5rem; border-left: 3px solid #667eea;'>
                                            <div style='display: flex; justify-content: space-between; align-items: center;'>
                                                <div style='flex: 1;'>
                                                    <div style='font-weight: 600; color: #1e293b; font-size: 0.9rem;'>
                                                        {i}. {holder_name}
                                                    </div>
                                                    <div style='color: #64748b; font-size: 0.8rem; margin-top: 0.25rem;'>
                                                        {shares_text} • Reported: {date}
                                                    </div>
                                                </div>
                                                <div style='margin-left: 1rem;'>
                                                    {change_badge}
                                                </div>
                                            </div>
                                        </div>
                                        """, unsafe_allow_html=True)

                                    # Overall institutional balance interpretation
                                    total_change = sum(h.get('change', 0) for h in institutional_holders)
                                    buying_count = sum(1 for h in institutional_holders if h.get('change', 0) > 0)
                                    selling_count = sum(1 for h in institutional_holders if h.get('change', 0) < 0)

                                    # Debug: Show if we have change data
                                    changes_available = any(h.get('change') is not None for h in institutional_holders)

                                    if changes_available:
                                        st.markdown("---")
                                        st.markdown("**Balance de Compra/Venta Institucional**")

                                        col_buy, col_sell, col_net = st.columns(3)

                                        with col_buy:
                                            st.markdown(f"""
                                            <div style='text-align: center; padding: 0.75rem;'>
                                                <div style='font-size: 1.5rem; font-weight: 700; color: #10b981;'>
                                                    {buying_count}
                                                </div>
                                                <div style='font-size: 0.8rem; color: #64748b;'>
                                                    COMPRANDO
                                                </div>
                                            </div>
                                            """, unsafe_allow_html=True)

                                        with col_sell:
                                            st.markdown(f"""
                                            <div style='text-align: center; padding: 0.75rem;'>
                                                <div style='font-size: 1.5rem; font-weight: 700; color: #ef4444;'>
                                                    {selling_count}
                                                </div>
                                                <div style='font-size: 0.8rem; color: #64748b;'>
                                                    VENDIENDO
                                                </div>
                                            </div>
                                            """, unsafe_allow_html=True)

                                        with col_net:
                                            net_inst_balance = buying_count - selling_count
                                            if net_inst_balance > 0:
                                                net_color = '#10b981'
                                                net_text = 'NET COMPRA'
                                            elif net_inst_balance < 0:
                                                net_color = '#ef4444'
                                                net_text = 'NET VENTA'
                                            else:
                                                net_color = '#6b7280'
                                                net_text = 'NEUTRAL'

                                            st.markdown(f"""
                                            <div style='text-align: center; padding: 0.75rem;'>
                                                <div style='font-size: 1.5rem; font-weight: 700; color: {net_color};'>
                                                    {net_inst_balance:+d}
                                                </div>
                                                <div style='font-size: 0.8rem; color: #64748b;'>
                                                    {net_text}
                                                </div>
                                            </div>
                                            """, unsafe_allow_html=True)

                                        # Interpretation
                                        if net_inst_balance > 5:
                                            st.success(f"Smart money comprando: Más instituciones aumentando posiciones que reduciéndolas. Señal de confianza institucional.")
                                        elif net_inst_balance < -5:
                                            st.warning(f"Smart money vendiendo: Más instituciones reduciendo posiciones. Puede indicar preocupaciones o rotación sectorial.")
                                        else:
                                            st.info(f"Balance neutral: Actividad institucional balanceada.")
                                    else:
                                        st.info("Datos de cambio (compra/venta) no disponibles en la API. Solo se muestran las posiciones actuales.")

                                else:
                                    st.info("No hay datos de institutional holdings disponibles")

                            except Exception as e:
                                st.warning(f"No se pudo obtener información de institutional holdings: {str(e)}")
                        else:
                            st.info("Para ver Insider Trading e Institutional Holdings, primero ejecuta el análisis cualitativo (tab 5) para este ticker.")

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
                                <div style='font-size: 1.3rem; font-weight: 600; margin-bottom: 0.5rem;'>Analysis Error</div>
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
                                <div style='font-size: 0.95rem; color: #155724; font-weight: 600;'>No technical warnings detected</div>
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

                        # V2: Map extension_state to numeric risk for display
                        ext_risk_values = {'NORMAL': 1, 'EXTENDED': 3, 'STRETCHED': 5, 'OVEREXTENDED': 7}
                        overextension_risk = ext_risk_values.get(extension_state, 1)
                        # distance_ma200 already extracted from metadata earlier

                        # ========== KILL SWITCH: STATE MACHINE VETO ==========
                        # V2: Use trend_state from states (not market_state from smart_stop_loss)
                        market_state = trend  # trend was extracted from states earlier

                        if market_state == "DOWNTREND":
                            # VETO: Structure is broken - show critical warning FIRST
                            st.error("""
                            ### 🛑 KILL SWITCH: DOWNTREND DETECTED

                            **⛔ State Machine Alert**: Precio < SMA 50 - Estructura rota

                            **ACCIÓN REQUERIDA**:
                            - Si **NO** tienes la acción: **NO COMPRAR** (espera recuperación)
                            - Si **YA** tienes la acción: **SALIR** en próximo rebote

                            **Por qué esto anula los scores históricos**:
                            - Technical Score ({tech_score}/100) mira 12 meses atrás PASADO
                            - State Machine mira estructura actual PRESENTE
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
                            - Technical Score ({tech_score}/100) dice "excelente momentum" VERDAD
                            - State Machine dice "movimiento insostenible" TAMBIÉN VERDAD
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
                            elif fund_score >= 70:
                                st.info(f" GOOD ({fund_score}/100) - Solid fundamentals")
                            elif fund_score >= 60:
                                st.info(f" ADEQUATE ({fund_score:.1f}/100) - Acceptable fundamentals but not high conviction")
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

                            # Use unified recommendation (same logic as header badge)
                            # This ensures consistency between header and final recommendation
                            fund_decision = stock_data['fundamental_decision']

                            # Display final action with color coding
                            if final_action['action'] == 'STRONG_BUY':
                                st.success(f"""
                                **{final_action['label']}**: {final_action['reason']}

                                **Action**: Consider building full position.
                                - Fund Score: {fund_score:.0f}/100 ({fund_decision})
                                - Tech Score: {tech_score:.0f}/100
                                - Conviction: {conviction:.2f}
                                - Extension: {extension_state}
                                """)
                            elif final_action['action'] == 'BUY':
                                st.info(f"""
                                **{final_action['label']}**: {final_action['reason']}

                                **Action**: Consider position (50-75% size recommended).
                                - Fund Score: {fund_score:.0f}/100 ({fund_decision})
                                - Tech Score: {tech_score:.0f}/100
                                - Conviction: {conviction:.2f}
                                - Extension: {extension_state}
                                """)
                            elif final_action['action'] == 'WAIT':
                                st.warning(f"""
                                **{final_action['label']}**: {final_action['reason']}

                                **Action**: Wait for better technical setup or entry point.
                                - Fund Score: {fund_score:.0f}/100 ({fund_decision})
                                - Tech Score: {tech_score:.0f}/100
                                - Conviction: {conviction:.2f} (needs ≥0.3 for entry)
                                - Set alerts for conviction improvement
                                """)
                            elif final_action['action'] == 'WAIT_PULLBACK':
                                st.warning(f"""
                                **{final_action['label']}**: {final_action['reason']}

                                **Action**: Wait for pullback/de-extension, THEN scale in.
                                - Entry trigger: Price pulls back to EMA20/MA50 OR extension drops to EXTENDED/NORMAL
                                - Sizing shown above is PLANNED allocation if trigger happens
                                - Fund Score: {fund_score:.0f}/100 ({fund_decision})
                                - Tech Score: {tech_score:.0f}/100 (strong)
                                - Conviction: {conviction:.2f}
                                - Extension: {extension_state} (overextended - wait for de-extension)
                                """)
                            elif final_action['action'] == 'TACTICAL_SCALE_IN':
                                st.info(f"""
                                **{final_action['label']}**: {final_action['reason']}

                                **Action**: Enter small position NOW.
                                - Execute shares shown in Módulo 3 (small position only)
                                - Set stop loss from Módulo 4 immediately
                                - Consider adding more on pullback if opportunity arises
                                - Fund Score: {fund_score:.0f}/100 ({fund_decision} - adequate but not high conviction)
                                - Tech Score: {tech_score:.0f}/100 (strong)
                                - Conviction: {conviction:.2f}
                                - Extension: {extension_state}
                                """)
                            elif final_action['action'] == 'MONITOR':
                                st.info(f"""
                                **{final_action['label']}**: {final_action['reason']}

                                **Action**: Watch for fundamental improvement before considering entry.
                                - Fund Score: {fund_score:.0f}/100 ({fund_decision})
                                - Tech Score: {tech_score:.0f}/100
                                - Conviction: {conviction:.2f}
                                - Extension: {extension_state}
                                """)
                            else:  # AVOID
                                st.error(f"""
                                **{final_action['label']}**: {final_action['reason']}

                                **Action**: Do not enter. Wait for structure recovery.
                                - Fund Score: {fund_score:.0f}/100 ({fund_decision})
                                - Tech Score: {tech_score:.0f}/100
                                - Trend: {trend} (needs UPTREND or CHOP for entry)
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
                                <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                            padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 1.5rem;'>
                                    <h3 style='margin: 0; color: white; font-weight: 600;'>
                                        Niveles de Precio & Gestión de Riesgo
                                    </h3>
                                    <p style='margin: 0.5rem 0 0 0; color: white; opacity: 0.9; font-size: 0.9rem;'>
                                        Análisis técnico con stop loss dinámico y niveles clave
                                    </p>
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

                            4. **Market Timing** - Verifica condiciones macro antes de entrar
                               - Si DEFENSIVE (risk 7+), espera mejor momento

                            5. **Portfolio** 💼
                               - Agrega posición para tracking automático
                               - Recibe alertas cuando price hits key levels

                            ### Casos de Uso

                            **Stock Overextendido (ej: +58% sobre MA200)**
                            1. Visualizations Confirma zona overextension
                            2. Backtesting Valida que correcciones históricas fueron -25% avg
                            3. Options Covered call para income mientras esperas pullback
                            4. Market Timing Si CAUTIOUS/DEFENSIVE, no entres full position
                            5. Portfolio Scale-in 3 tranches (25% now, 35% @MA50, 40% @MA200)

                            **Stock con Pullback (ej: -15% en 2 semanas)**
                            1. Visualizations Confirma que salió de zona overextension
                            2. Backtesting Valida que rebotes desde MA50 son +18% avg
                            3. Options Cash-secured put para entry at discount
                            4. Market Timing Si NEUTRAL/BULLISH, OK para agregar
                            5. Portfolio Add tranche 2 cuando alerta dice "near MA50"

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
