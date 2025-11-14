"""
UltraQuality Screener - Streamlit Web Interface

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
from datetime import datetime
from io import BytesIO

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

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
            flags_df = pd.DataFrame({'Red Flags': ['✅ No red flags detected']})
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

        # ROJO = Auto AVOID (accounting red flags)
        if exclude_reds and status == 'ROJO':
            return 'AVOID', 'RED guardrails (accounting concerns)'

        # Exceptional composite score = BUY even with AMBAR
        # BUT: Block if revenue declining OR quality deteriorating (Piotroski for VALUE, Mohanram for GROWTH)
        revenue_growth = row.get('revenue_growth_3y')
        degradation_delta = row.get('quality_degradation_delta')
        degradation_type = row.get('quality_degradation_type')

        if composite >= 85:  # Raised from 80 to 85 (more selective)
            # Check 1: Revenue decline (universal check)
            if revenue_growth is not None and revenue_growth < 0:
                return 'MONITOR', f'High score ({composite:.0f}) but revenue declining ({revenue_growth:.1f}% 3Y)'

            # Check 2: Quality degradation (Piotroski F-Score for VALUE, Mohanram G-Score for GROWTH)
            if degradation_delta is not None and degradation_delta < 0:
                score_name = 'F-Score' if degradation_type == 'VALUE' else 'G-Score'
                return 'MONITOR', f'High score ({composite:.0f}) but {degradation_type} quality degrading ({score_name} Δ{degradation_delta})'

            return 'BUY', f'Exceptional score ({composite:.0f} ≥ 85)'

        # Exceptional Quality companies = BUY even with moderate composite
        # Relaxed for AMBAR: if very high quality, accept lower composite
        # BUT: Block if revenue declining OR quality deteriorating (Piotroski/Mohanram)
        if quality >= threshold_quality_exceptional:
            # Check 1: Revenue decline
            if revenue_growth is not None and revenue_growth < 0:
                return 'MONITOR', f'High quality (Q:{quality:.0f}) but revenue declining ({revenue_growth:.1f}% 3Y)'

            # Check 2: Quality degradation (F-Score for VALUE, G-Score for GROWTH)
            if degradation_delta is not None and degradation_delta < 0:
                score_name = 'F-Score' if degradation_type == 'VALUE' else 'G-Score'
                return 'MONITOR', f'High quality (Q:{quality:.0f}) but {degradation_type} quality degrading ({score_name} Δ{degradation_delta})'

            if composite >= 60:
                return 'BUY', f'Exceptional quality (Q:{quality:.0f} ≥ {threshold_quality_exceptional}, C:{composite:.0f} ≥ 60)'
            elif composite >= 55 and status != 'ROJO':
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

st.set_page_config(
    page_title="UltraQuality Screener",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title
st.title("📊 UltraQuality: Quality + Value Screener")
st.markdown("*Screening stocks using fundamental quality and value metrics*")

# Sidebar configuration
st.sidebar.header("⚙️ Configuration")

# Universe filters
with st.sidebar.expander("🌍 Universe Filters", expanded=True):
    # Region/Country selector
    # Uses exchange codes (country parameter doesn't work in FMP API)
    region_options = {
        "🇺🇸 United States": "US",        # Special: no filter (most stocks are US)
        "🇨🇦 Canada": "TSX",              # Toronto Stock Exchange
        "🇬🇧 United Kingdom": "LSE",      # London Stock Exchange
        "🇩🇪 Germany": "XETRA",           # Frankfurt/XETRA
        "🇫🇷 France / Europe": "EURONEXT", # Euronext (multi-country)
        "🇮🇳 India": "NSE",               # National Stock Exchange
        "🇨🇳 China (Hong Kong)": "HKSE",  # Hong Kong Stock Exchange
        "🇨🇳 China (Shanghai)": "SSE",    # Shanghai Stock Exchange
        "🇰🇷 South Korea": "KRX",         # Korea Exchange
        "🇯🇵 Japan": "JPX",               # Japan Exchange Group
        "🇨🇱 Chile": "SNT",               # Santiago Stock Exchange
        "🇲🇽 Mexico": "BMV",              # Bolsa Mexicana de Valores
        "🇧🇷 Brazil": "SAO",              # B3 São Paulo
        "🌎 All Regions": "ALL"
    }

    selected_region = st.selectbox(
        "📍 Market/Region",
        options=list(region_options.keys()),
        index=0,  # Default to US
        help="Select which stock market/region to screen. Filters by country code in FMP API."
    )

    exchange_filter = region_options[selected_region]

    # Show info about selected region
    region_info = {
        "US": "United States - NYSE, NASDAQ, AMEX (5000+ stocks)",
        "TSX": "Canada - Toronto Stock Exchange (1500+ stocks)",
        "LSE": "United Kingdom - London Stock Exchange (2000+ stocks)",
        "XETRA": "Germany - Frankfurt/XETRA (500+ stocks, DAX, MDAX)",
        "EURONEXT": "France/Europe - Euronext (CAC 40, AEX, BEL 20)",
        "NSE": "India - National Stock Exchange (1700+ stocks)",
        "HKSE": "Hong Kong - Hong Kong Stock Exchange (Alibaba, Tencent)",
        "SSE": "China - Shanghai Stock Exchange (A-shares)",
        "KRX": "South Korea - Korea Exchange (Samsung, Hyundai, LG)",
        "JPX": "Japan - Tokyo Stock Exchange (Sony, Toyota, etc.)",
        "SNT": "Chile - Santiago Stock Exchange (Copper, Lithium)",
        "BMV": "Mexico - Bolsa Mexicana de Valores",
        "SAO": "Brazil - B3 São Paulo (Petrobras, Vale, etc.)",
        "ALL": "All regions combined - May be slower"
    }

    if exchange_filter in region_info:
        st.caption(f"ℹ️ {region_info[exchange_filter]}")

    # Dynamic default thresholds based on market size
    # Note: All values must be float for Streamlit compatibility
    default_thresholds = {
        # Large developed markets
        "US": {"mcap": 2000.0, "vol": 5.0},
        "JPX": {"mcap": 500.0, "vol": 2.0},

        # Medium developed markets
        "TSX": {"mcap": 50.0, "vol": 0.1},       # Canada (smaller market than US/UK)
        "LSE": {"mcap": 300.0, "vol": 1.0},      # UK
        "XETRA": {"mcap": 300.0, "vol": 1.0},    # Germany
        "EURONEXT": {"mcap": 300.0, "vol": 1.0}, # Europe

        # Large emerging markets
        "SSE": {"mcap": 200.0, "vol": 1.0},      # Shanghai
        "HKSE": {"mcap": 200.0, "vol": 1.0},     # Hong Kong
        "NSE": {"mcap": 200.0, "vol": 1.0},      # India
        "KRX": {"mcap": 200.0, "vol": 1.0},      # South Korea
        "SAO": {"mcap": 150.0, "vol": 0.5},      # Brazil

        # Smaller markets
        "BMV": {"mcap": 100.0, "vol": 0.5},      # Mexico
        "SNT": {"mcap": 50.0, "vol": 0.3},       # Chile

        # Default for ALL or unknown
        "ALL": {"mcap": 500.0, "vol": 2.0}
    }

    # Get defaults for selected country
    defaults = default_thresholds.get(exchange_filter, {"mcap": 200.0, "vol": 1.0})

    min_mcap = st.number_input(
        "Min Market Cap ($M)",
        min_value=10.0,
        max_value=100000.0,
        value=defaults["mcap"],
        step=10.0,
        help=f"Minimum market capitalization in millions. Recommended for {selected_region}: ${defaults['mcap']:.0f}M"
    )

    min_vol = st.number_input(
        "Min Daily Volume ($M)",
        min_value=0.1,
        max_value=100.0,
        value=defaults["vol"],
        step=0.1,
        help=f"Minimum average daily dollar volume in millions. Recommended for {selected_region}: ${defaults['vol']:.1f}M"
    )

    top_k = st.slider(
        "Top-K Stocks to Analyze",
        min_value=50,
        max_value=700,
        value=500,
        step=50,
        help="Number of stocks to deep-dive after preliminary ranking. 500 stocks = ~4 min with 1300 calls/min API limit"
    )

# Scoring weights
with st.sidebar.expander("⚖️ Scoring Weights", expanded=True):
    weight_quality = st.slider("Quality Weight", 0.0, 1.0, 0.70, 0.05,
                                key='weight_quality_slider',
                                help="QARP default: 0.70 (prioritize exceptional companies with moats)")
    weight_value = 1.0 - weight_quality
    st.write(f"**Value Weight:** {weight_value:.2f}")
    st.caption("✨ Moving sliders will instantly recalculate results")

    # Guidance
    if weight_quality >= 0.75:
        st.success("✅ **Optimal:** 75%+ Quality captures exceptional companies (Buffett-style)")
    elif weight_quality >= 0.70:
        st.success("✅ **Recommended:** 70% Quality = QARP balance (wonderful companies at fair prices)")
    elif weight_quality >= 0.60:
        st.info("💡 **Tip:** 60-70% Quality works but may miss some high-moat companies (GOOGL, META)")
    else:
        st.warning("⚠️ **Warning:** <60% Quality prioritizes value over excellence. Commodities may rank higher than tech giants.")

# Decision thresholds
with st.sidebar.expander("🎯 Decision Thresholds", expanded=True):
    threshold_buy = st.slider("BUY Threshold", 50, 90, 65, 5,
                               key='threshold_buy_slider',
                               help="Minimum composite score for BUY (QARP default: 65)")
    threshold_monitor = st.slider("MONITOR Threshold", 30, 70, 45, 5,
                                   key='threshold_monitor_slider',
                                   help="Minimum composite score for MONITOR (QARP default: 45)")
    threshold_quality_exceptional = st.slider("Quality Exceptional", 70, 95, 85, 5,
                                               key='threshold_quality_exceptional_slider',
                                               help="If Quality ≥ this, force BUY even with lower composite (only truly exceptional companies). Default: 85")

    exclude_reds = st.checkbox("Exclude RED Guardrails", value=True,
                               key='exclude_reds_checkbox',
                               help="Auto-AVOID stocks with accounting red flags")

    st.caption("""
    **Guardrail Colors:**
    - 🟢 VERDE: Clean accounting
    - 🟡 AMBAR: Minor concerns (high-quality companies often have AMBAR)
    - 🔴 ROJO: Red flags (manipulation risk)

    **New:** Quality ≥70 + AMBAR can still be BUY
    """)

# API Key status
st.sidebar.markdown("---")
st.sidebar.subheader("🔑 API Status")
try:
    api_key = st.secrets.get('FMP_API_KEY', '')
    if api_key and not api_key.startswith('your_'):
        st.sidebar.success(f"✓ API Key: {api_key[:10]}...")
    else:
        st.sidebar.error("❌ API Key not configured")
        st.sidebar.info("Add FMP_API_KEY to Streamlit secrets")
except:
    st.sidebar.warning("⚠️ Secrets not accessible")

# Main content
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["🏠 Home", "📊 Results", "📈 Analytics", "🔎 Calibration", "🔍 Qualitative", "🎯 Custom Analysis", "ℹ️ About"])

with tab1:
    st.header("Run Screener")

    # Show existing results summary if available
    if 'results' in st.session_state:
        # Get recalculated results with current slider values
        df_existing = get_results_with_current_params()
        buys_existing = (df_existing['decision'] == 'BUY').sum()
        monitors_existing = (df_existing['decision'] == 'MONITOR').sum()
        timestamp_existing = st.session_state.get('timestamp', datetime.now())
        config_version = st.session_state.get('config_version', 'unknown')

        # Check if results are from old config
        CURRENT_VERSION = "QARP-v3-Moat"  # Updated when major scoring changes (v3 = Moat Score added)
        is_stale = config_version != CURRENT_VERSION

        if is_stale:
            st.warning(f"⚠️ **Results are from older version** ({config_version}). Re-run screener to use latest methodology with **Moat Score** (competitive advantages).")
        else:
            st.success(f"📊 **Latest Results Available** (from {timestamp_existing.strftime('%Y-%m-%d %H:%M:%S')})")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Analyzed", len(df_existing))
        with col2:
            st.metric("🟢 BUY Signals", buys_existing)
        with col3:
            st.metric("🟡 MONITOR", monitors_existing)
        with col4:
            avg = df_existing['composite_0_100'].mean()
            st.metric("Avg Score", f"{avg:.1f}")

        col_btn1, col_btn2 = st.columns([3, 1])
        with col_btn1:
            st.info("👉 Check **Results**, **Analytics**, and **Qualitative** tabs to explore the data")
        with col_btn2:
            if st.button("🗑️ Clear Results", use_container_width=True):
                for key in ['results', 'timestamp', 'config_version']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

        st.markdown("---")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Universe", "2000+", "stocks")
    with col2:
        st.metric("Deep Analysis", f"{top_k}", "top stocks")
    with col3:
        st.metric("Time", "3-5", "minutes")

    st.markdown("---")

    # Big run button
    if st.button("🚀 Run Screener", type="primary", use_container_width=True):

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

            # Set exchange/region filter
            # Note: USA uses no filter since most stocks in FMP are US-based anyway
            if exchange_filter != "ALL" and exchange_filter != "US":
                # International exchanges: Use exchange code (TSX, LSE, NSE, etc.)
                pipeline.config['universe']['exchanges'] = [exchange_filter]
            else:
                # USA or ALL regions - no filter (most stocks in FMP are USA anyway)
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
            status_text.text("✅ Complete!")

            # Success message
            st.success(f"✅ Screening complete! Results saved to {output_csv}")

            # Load and display results
            df = pd.read_csv(output_csv)

            # Validate results before saving
            if len(df) == 0:
                st.warning("⚠️ Screening completed but no stocks met the criteria.")
                st.info("💡 Try lowering the minimum Market Cap or Volume thresholds.")
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

                st.success(f"✅ Found {buys} BUY signals and {monitors} MONITOR from {len(df)} stocks!")

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
    st.header("Screening Results")

    if 'results' in st.session_state:
        # Get recalculated results with current slider values
        df = get_results_with_current_params()
        timestamp = st.session_state['timestamp']

        st.caption(f"Last run: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        st.caption(f"⚖️ Current weights: Quality {weight_quality:.0%}, Value {weight_value:.0%}")

        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            decision_filter = st.multiselect(
                "Decision",
                options=['BUY', 'MONITOR', 'AVOID'],
                default=['BUY', 'MONITOR']
            )
        with col2:
            guardrail_filter = st.multiselect(
                "Guardrails",
                options=['VERDE', 'AMBAR', 'ROJO'],
                default=['VERDE', 'AMBAR']
            )
        with col3:
            min_score = st.slider("Min Composite Score", 0, 100, 50)

        # Apply filters
        filtered = df[
            (df['decision'].isin(decision_filter)) &
            (df['guardrail_status'].isin(guardrail_filter)) &
            (df['composite_0_100'] >= min_score)
        ]

        st.write(f"**{len(filtered)}** stocks match filters")

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
        with st.expander("🔍 Investigate Specific Companies"):
            search_ticker = st.text_input("Enter ticker(s) - comma separated (e.g., MA,V,GOOGL)", key="search_ticker")
            if search_ticker:
                tickers = [t.strip().upper() for t in search_ticker.split(',')]
                search_df = df[df['ticker'].str.upper().isin(tickers)]

                if not search_df.empty:
                    detail_cols = ['ticker', 'roic_%', 'moat_score', 'earnings_yield', 'earnings_yield_adj',
                                  'value_score_0_100', 'quality_score_0_100', 'composite_0_100',
                                  'guardrail_status', 'decision', 'decision_reason',
                                  'pricing_power_score', 'operating_leverage_score', 'roic_persistence_score']
                    available_detail_cols = [col for col in detail_cols if col in search_df.columns]

                    st.dataframe(search_df[available_detail_cols], use_container_width=True)
                else:
                    st.warning(f"No results found for: {', '.join(tickers)}")

        # Download buttons
        st.markdown("### 📥 Download Results")
        col1, col2 = st.columns(2)

        with col1:
            csv = df.to_csv(index=False).encode('utf-8')
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
                    label="📊 Download Excel (with Summary)",
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
    st.header("📈 Analytics & Sector Breakdown")

    if 'results' in st.session_state:
        # Get recalculated results with current slider values
        df = get_results_with_current_params()

        # Validate sufficient data
        if len(df) < 5:
            st.warning("⚠️ Not enough data for analytics (minimum 5 stocks required)")
            st.info("💡 Try lowering the Min Market Cap or Volume thresholds.")
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
                st.subheader("🚫 Rejection Analysis")
                
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
                st.subheader("📊 Score Distribution")
                
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
                st.subheader("💎 Value vs Quality Matrix")
                
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
                st.info("💡 Try running the screener again with different parameters.")

    else:
        st.info("👈 Run the screener first to see analytics")

with tab4:
    st.header("🔎 Guardrail Calibration Analysis")

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
                    '🔍 High-Quality ROJO Deep Dive',
                    'Beneish M-Score',
                    'Altman Z-Score',
                    'Revenue Growth',
                    'M&A / Goodwill',
                    'Share Dilution',
                    'Accruals / NOA'
                ]
            )

            if st.button("🔍 Generate Analysis", type="primary"):
                with st.spinner("Analyzing guardrails..."):
                    if analysis_type == 'Full Report':
                        report = analyzer.generate_full_report()
                    elif analysis_type == '🔍 High-Quality ROJO Deep Dive':
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
            st.subheader("📊 Quick Stats")
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
                st.subheader("🔝 Top 10 Guardrail Reasons")
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
    st.header("🔍 Qualitative Analysis")

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
                if st.button(f"🔍 Run Deep Analysis for {selected_ticker}", type="primary", use_container_width=True):
                    # Force reload modules to get latest code
                    import sys
                    modules_to_reload = [
                        'screener.ingest',
                        'screener.qualitative'
                    ]
                    for module_name in modules_to_reload:
                        if module_name in sys.modules:
                            del sys.modules[module_name]

                    with st.spinner(f"Analyzing {selected_ticker}... This may take 30-60 seconds"):
                        try:
                            import yaml
                            import os
                            from screener.qualitative import QualitativeAnalyzer
                            from screener.ingest import FMPClient

                            # Load config - USE PREMIUM CONFIG FOR PREMIUM FEATURES!
                            config_file = 'settings_premium.yaml' if os.path.exists('settings_premium.yaml') else 'settings.yaml'
                            with open(config_file, 'r') as f:
                                config = yaml.safe_load(f)

                            st.info(f"📋 Using config: **{config_file}**")

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
                                st.success("✅ Analysis complete!")
                                st.rerun()  # Rerun to show the new results
                            else:
                                st.error(f"❌ Analysis failed: {analysis.get('error', 'Unknown error')}")

                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
                            import traceback
                            st.code(traceback.format_exc())

            with col_btn2:
                if st.button("🔄 Clear Cache & Reload Modules", use_container_width=True):
                    # Clear this ticker's cache
                    if f'qual_{selected_ticker}' in st.session_state:
                        del st.session_state[f'qual_{selected_ticker}']

                    # Force reload Python modules
                    import sys
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

                    st.success("✅ Cache cleared and modules reloaded. Click 'Run Deep Analysis' again.")

            # Display cached analysis if available
            if f'qual_{selected_ticker}' in st.session_state:
                analysis = st.session_state[f'qual_{selected_ticker}']

                # Check if analysis is from old version (has DEBUG messages)
                intrinsic = analysis.get('intrinsic_value', {})
                notes = intrinsic.get('notes', [])
                has_old_debug = any('DEBUG:' in str(note) for note in notes)

                if has_old_debug:
                    st.warning(f"⚠️ Cached analysis for {selected_ticker} is from an older version with outdated diagnostics.")
                    # Clear the cache
                    del st.session_state[f'qual_{selected_ticker}']
                    st.info("🔄 Cache cleared. Please click the '🔍 Run Deep Analysis' button above again to get fresh results with improved diagnostics.")
                    st.markdown("""
                    **New features you'll get:**
                    - ✅ Auto-detection of company type (non_financial, financial, reit, utility)
                    - ✅ Detailed error messages showing exact failure points and data values
                    - ✅ Color-coded diagnostic messages (green=success, red=error, yellow=warning)
                    - ✅ Specific troubleshooting info (e.g., "OCF=X, capex=Y, base_cf=Z")
                    """)
                    # Don't show anything else - wait for user to click button again
                elif f'qual_{selected_ticker}' in st.session_state:
                    # Only show analysis if it's valid (no DEBUG messages)
                    # Business Summary
                    st.subheader("📝 Business Summary")
                    st.write(analysis.get('business_summary', 'Not available'))

                    st.markdown("---")

                    # Moats
                    col1, col2 = st.columns(2)

                    with col1:
                        st.subheader("🏰 Competitive Moats")
                        moats = analysis.get('moats', [])
                        if moats:
                            for moat in moats:
                                st.markdown(f"- {moat}")
                        else:
                            st.info("No clear moats identified")

                    with col2:
                        st.subheader("⚠️ Key Risks")
                        risks = analysis.get('risks', [])
                        if risks:
                            for risk in risks:
                                st.markdown(f"- {risk}")
                        else:
                            st.info("No major risks identified")

                    st.markdown("---")

                    # Insider Activity & Ownership
                    st.subheader("👔 Insider Activity & Ownership")
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
                            emoji_map = {'positive': '🟢', 'neutral': '🟡', 'negative': '🔴'}
                            emoji = emoji_map.get(assessment, '🟡')
                            st.metric("Assessment", f"{emoji} {assessment.title()}")

                        # Additional context
                        if insider_own is not None:
                            if insider_own >= 15:
                                st.success("✓ Strong insider ownership (≥15%) indicates good alignment with shareholders")
                            elif insider_own >= 5:
                                st.info("✓ Moderate insider ownership (5-15%)")
                            elif insider_own < 1:
                                st.warning("⚠️ Low insider ownership (<1%) - weak alignment signal")

                    else:
                        st.info("Ownership data not available")

                    st.markdown("---")

                    # Recent News
                    st.subheader("📰 Recent News & Events")
                    news = analysis.get('recent_news', [])

                    if news:
                        for item in news[:5]:
                            st.markdown(f"**{item.get('date', 'N/A')}**: {item.get('headline', 'No headline')}")
                            st.caption(item.get('summary', '')[:200])
                    else:
                        st.info("No recent news available")

                    st.markdown("---")

                    # Intrinsic Value Estimation
                    st.subheader("💰 Intrinsic Value Estimation")
                    intrinsic = analysis.get('intrinsic_value', {})

                    # Show section if we have intrinsic_value dict (even if current_price is missing)
                    if intrinsic and 'current_price' in intrinsic:
                        col1, col2, col3, col4 = st.columns(4)

                        current_price = intrinsic.get('current_price', 0)

                        with col1:
                            if current_price and current_price > 0:
                                st.metric("Current Price", f"${current_price:.2f}")
                            else:
                                st.metric("Current Price", "N/A")
                                st.caption("⚠️ Price data unavailable")

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

                        # Show debug notes if present (for troubleshooting)
                        notes = intrinsic.get('notes', [])
                        if notes:
                            with st.expander("📋 Calculation Details & Debug Info"):
                                for note in notes:
                                    if note.startswith('✓'):
                                        st.success(note)
                                    elif note.startswith('✗') or 'ERROR' in note or 'failed' in note.lower():
                                        st.error(note)
                                    elif note.startswith('⚠️') or 'WARNING' in note:
                                        st.warning(note)
                                    else:
                                        st.info(note)

                        # Upside/Downside
                        if intrinsic.get('upside_downside_%') is not None:
                            upside = intrinsic.get('upside_downside_%', 0)
                            assessment = intrinsic.get('valuation_assessment', 'Unknown')
                            confidence = intrinsic.get('confidence', 'Low')

                            # Color based on assessment
                            if assessment == 'Undervalued':
                                color = 'green'
                                emoji = '🟢'
                            elif assessment == 'Overvalued':
                                color = 'red'
                                emoji = '🔴'
                            else:
                                color = 'orange'
                                emoji = '🟡'

                            # Display industry profile
                            industry_profile = intrinsic.get('industry_profile', 'unknown').replace('_', ' ').title()
                            primary_metric = intrinsic.get('primary_metric', 'EV/EBIT')

                            st.markdown(f"### {emoji} {assessment}: {upside:+.1f}% {'upside' if upside > 0 else 'downside'}")
                            st.caption(f"**Industry Profile:** {industry_profile} | **Primary Metric:** {primary_metric}")
                            st.caption(f"**Confidence:** {confidence}")

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
                            st.markdown("### 📈 Price Projections by Scenario")

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
                                            emoji = '📊'
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
                            st.markdown(f"### ⚙️ Capital Efficiency ({metric_name} vs WACC)")

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
                                    emoji = "✅"
                                else:
                                    delta_color = "inverse"
                                    emoji = "⚠️"

                                st.metric(f"Spread ({metric_name} - WACC)", f"{spread:+.1f}%", delta=trend)

                            # Show 5-year history
                            history_5y = capital_efficiency.get('history_5y', [])
                            if history_5y:
                                st.caption(f"**{metric_name} History (last {len(history_5y)} years):** " +
                                         ", ".join([f"{h:.1f}%" for h in history_5y]))

                            assessment = capital_efficiency.get('assessment', '')
                            value_creation = capital_efficiency.get('value_creation', False)

                            if value_creation:
                                st.success(f"✅ {assessment} - {metric_name} exceeds WACC, indicating value creation")
                            else:
                                st.error(f"⚠️ {assessment} - {metric_name} below WACC, may be destroying value")

                        # 2. Quality of Earnings
                        earnings_quality = intrinsic.get('earnings_quality', {})
                        if earnings_quality:
                            st.markdown("### 🎯 Quality of Earnings")

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
                                with st.expander("⚠️ Quality Issues Detected"):
                                    for issue in issues:
                                        st.warning(f"• {issue}")

                        # 3. Profitability Analysis (Margins and Trends)
                        profitability = intrinsic.get('profitability_analysis', {})
                        if profitability:
                            st.markdown("### 📊 Profitability Margins & Trends")

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
                            st.markdown("### 📊 Valuation Multiples vs Peers")

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
                                    st.warning(f"⚠️ Trading at a **premium** to peers on {premium_count}/{len(vs_peers)} metrics")
                                elif discount_count > premium_count:
                                    st.success(f"✅ Trading at a **discount** to peers on {discount_count}/{len(vs_peers)} metrics")
                                else:
                                    st.info(f"📊 **In-line** with peer valuations")

                        # 6. Growth Consistency (Historical Trends)
                        growth_consistency = intrinsic.get('growth_consistency', {})
                        if growth_consistency:
                            st.markdown("---")
                            st.markdown("### 📈 Growth Consistency & Historical Trends")

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
                                st.markdown("#### 💵 Revenue Growth")
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
                                st.markdown("#### 💰 Earnings Growth")
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
                            st.markdown("### 💰 Cash Conversion Cycle (Working Capital Efficiency)")

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
                                    st.metric("YoY Trend", "📈 Improving", delta=f"{yoy_change:.0f} days")
                                elif trend == 'deteriorating':
                                    st.metric("YoY Trend", "📉 Worsening", delta=f"{yoy_change:+.0f} days")
                                else:
                                    st.metric("YoY Trend", "→ Stable", delta=f"{yoy_change:+.0f} days")

                            st.caption("💡 Lower CCC = Better working capital efficiency. Negative CCC means suppliers finance operations.")

                        # 8. Operating Leverage (FASE 1)
                        operating_lev = intrinsic.get('operating_leverage', {})
                        if operating_lev:
                            st.markdown("---")
                            st.markdown("### ⚙️ Operating Leverage (Cost Structure)")

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

                            st.caption("💡 High OL = High fixed costs. Profits amplify with revenue growth but also with declines.")

                        # 9. Reinvestment Quality (FASE 1)
                        reinvestment = intrinsic.get('reinvestment_quality', {})
                        if reinvestment:
                            st.markdown("---")
                            st.markdown("### 🔄 Reinvestment Quality (Capital Efficiency of Growth)")

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
                                    st.caption("🌟 Excellent")
                                elif growth_roic > 1:
                                    st.caption("✅ Good")
                                elif growth_roic > 0.5:
                                    st.caption("⚠️ Moderate")
                                else:
                                    st.caption("❌ Poor")

                            with col4:
                                net_capex = reinvestment.get('net_capex', 0)
                                delta_wc = reinvestment.get('delta_wc', 0)
                                st.metric("Net Capex",
                                        f"${net_capex/1e9:.1f}B",
                                        delta=f"ΔWC: ${delta_wc/1e9:.1f}B")

                            st.caption("💡 Growth ROIC > 1 = Efficient growth. > 2 = Exceptional capital efficiency.")

                        # 10. Economic Profit / EVA (FASE 2)
                        eva = intrinsic.get('economic_profit', {})
                        if eva:
                            st.markdown("---")
                            st.markdown("### 💎 Economic Profit (EVA - Economic Value Added)")

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
                                    st.metric("5Y Avg EVA", avg_eva, delta="📈 Improving")
                                elif trend == 'deteriorating':
                                    st.metric("5Y Avg EVA", avg_eva, delta="📉 Declining")
                                else:
                                    st.metric("5Y Avg EVA", avg_eva, delta="→ Stable")

                            st.caption("💡 EVA = NOPAT - (WACC × Invested Capital). Positive EVA = Value creation above cost of capital.")

                        # 11. Capital Allocation Score (FASE 2)
                        cap_alloc = intrinsic.get('capital_allocation', {})
                        if cap_alloc:
                            st.markdown("---")
                            st.markdown("### 📊 Capital Allocation Scorecard")

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

                            st.caption("💡 Best allocators: Return capital when opportunities are scarce, reinvest when ROIC > WACC.")

                        # 12. Interest Rate Sensitivity (FASE 2)
                        rate_sens = intrinsic.get('interest_rate_sensitivity', {})
                        if rate_sens and rate_sens.get('applicable', False):
                            st.markdown("---")
                            st.markdown("### 📈 Interest Rate Sensitivity (Financial Companies)")

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
                                    st.metric("NIM Trend", "📈 Expanding", delta=f"+{yoy:.2f}% YoY")
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

                            st.caption("💡 Higher NIM = More profitable. Expanding NIM = Benefiting from rate increases.")

                        # 13. Insider Trading Analysis (Premium Feature)
                        insider = intrinsic.get('insider_trading', {})
                        if insider and insider.get('available', False):
                            st.markdown("---")
                            st.markdown("### 🎯 Insider Trading Activity (Last 12 Months)")

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
                                    st.metric("Net Position", "🟢 Buying")
                                else:
                                    st.metric("Net Position", "🔴 Selling")
                                st.caption(f"Buy: {buy_val} | Sell: {sell_val}")

                            # Show recent trades
                            recent_trades = insider.get('recent_trades', [])
                            if recent_trades:
                                st.markdown("**Most Recent Buys:**")
                                for trade in recent_trades[:3]:
                                    st.caption(f"• {trade.get('date')}: {trade.get('name')} - ${trade.get('value')/1e3:.0f}K")

                            st.caption("💡 Multiple insider buys (especially executives) often precede stock price increases.")

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
                                    st.caption("✅ Guidance provided")
                                else:
                                    st.caption("⚠️ No guidance")

                            # Keyword breakdown
                            st.markdown("**Keyword Mentions:**")
                            pos_count = sentiment.get('positive_mentions', 0)
                            neg_count = sentiment.get('negative_mentions', 0)
                            cau_count = sentiment.get('caution_mentions', 0)
                            st.caption(f"Growth/Positive: {pos_count} | Challenges/Negative: {neg_count} | Caution: {cau_count}")

                            st.caption("💡 Positive sentiment from management often signals confidence in future performance.")

                        # 15. Red Flags
                        red_flags = intrinsic.get('red_flags', [])
                        if red_flags:
                            st.markdown("### 🚩 Red Flags Detected")
                            for flag in red_flags:
                                st.error(flag)
                        else:
                            # Only show "no red flags" if we actually ran the analysis
                            if 'red_flags' in intrinsic:
                                st.markdown("### ✅ No Red Flags Detected")
                                st.success("All financial health checks passed")

                        # 5. Reverse DCF (What the market is pricing in)
                        reverse_dcf = intrinsic.get('reverse_dcf', {})
                        if reverse_dcf:
                            st.markdown("### 🔄 Reverse DCF: What Does the Price Imply?")

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
                                st.warning(f"⚠️ {interpretation}")
                            elif "continuation" in interpretation.lower():
                                st.success(f"✅ {interpretation}")
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

                                st.info(f"📊 **Valuation Range:** ${min_val:.2f} - ${max_val:.2f} (spread: ${spread:.2f})")
                                st.caption("This range shows how sensitive the DCF value is to different assumptions")

                    else:
                        st.info("Valuation analysis not available. Run the analysis to see intrinsic value estimates.")
                        # Show debug notes if available
                        if intrinsic.get('notes'):
                            with st.expander("🔍 Debug Information"):
                                for note in intrinsic.get('notes', []):
                                    st.caption(f"• {note}")

                    st.markdown("---")

                    # Fundamental Metrics Deep Dive
                    st.subheader("📊 Fundamental Metrics")

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
                        st.metric("Status", stock_data.get('guardrail_status', 'N/A'))
                        if 'altman_z' in stock_data:
                            st.metric("Altman Z-Score", f"{stock_data.get('altman_z', 0):.2f}")
                        if 'beneish_m' in stock_data:
                            st.metric("Beneish M-Score", f"{stock_data.get('beneish_m', 0):.2f}")

                    # ======================
                    # 🔍 DEBUG: PREMIUM FEATURES
                    # ======================
                    st.markdown("---")
                    with st.expander("🔍 DEBUG: Premium Features Status", expanded=False):
                        st.markdown("### Premium Features Configuration & Output")

                        # Show config being used
                        st.markdown("#### 1️⃣ Configuration Loaded")
                        st.code(f"Config file: {config_file if 'config_file' in locals() else 'settings.yaml'}")

                        # Show premium config
                        import yaml
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
                                    st.success(f"✅ Insider Trading: **ENABLED**")
                                else:
                                    st.error(f"❌ Insider Trading: **DISABLED**")

                            with col2:
                                transcripts_enabled = premium_config.get('enable_earnings_transcripts', False)
                                if transcripts_enabled:
                                    st.success(f"✅ Earnings Transcripts: **ENABLED**")
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
                                st.warning("⚠️ insider_trading found at ROOT (deprecated)")
                            else:
                                st.info("❌ insider_trading NOT at root")
                        with col2:
                            if has_sentiment_root:
                                st.warning("⚠️ earnings_sentiment found at ROOT")
                            else:
                                st.info("❌ earnings_sentiment NOT at root")

                        # Check intrinsic_value level (CORRECT location)
                        intrinsic = analysis.get('intrinsic_value', {})
                        has_insider_iv = 'insider_trading' in intrinsic
                        has_sentiment_iv = 'earnings_sentiment' in intrinsic

                        st.markdown("**Inside intrinsic_value Dict (✅ CORRECT):**")
                        col1, col2 = st.columns(2)
                        with col1:
                            if has_insider_iv:
                                st.success("✅ insider_trading FOUND in intrinsic_value!")
                            else:
                                st.error("❌ insider_trading NOT in intrinsic_value")
                        with col2:
                            if has_sentiment_iv:
                                st.success("✅ earnings_sentiment FOUND in intrinsic_value!")
                            else:
                                st.error("❌ earnings_sentiment NOT in intrinsic_value")

                        # Show actual data if present
                        st.markdown("#### 3️⃣ Actual Premium Features Data")

                        if has_insider_iv:
                            st.markdown("**🎯 Insider Trading Data:**")
                            insider_data = intrinsic['insider_trading']
                            st.json(insider_data)
                        else:
                            st.warning("No insider trading data in intrinsic_value")

                        if has_sentiment_iv:
                            st.markdown("**🎯 Earnings Sentiment Data:**")
                            sentiment_data = intrinsic['earnings_sentiment']
                            st.json(sentiment_data)
                        else:
                            st.warning("No earnings sentiment data in intrinsic_value")

                        # Show what keys ARE in intrinsic_value
                        st.markdown("#### 4️⃣ All Keys in intrinsic_value Dict")
                        st.code(f"Keys: {list(intrinsic.keys())}")

                        st.markdown("""
                        ---
                        **📍 How to Access Premium Features:**
                        ```python
                        # ✅ CORRECT
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
                            label="📊 Download Full Analysis (Excel)",
                            data=excel_data,
                            file_name=f"{selected_ticker}_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                            help="Download comprehensive analysis with all metrics in multiple Excel sheets"
                        )
                        st.caption("📋 Includes: Overview, Capital Efficiency, Earnings Quality, Margins, Red Flags, Reverse DCF, Price Projections, and DCF Sensitivity")
                    except Exception as e:
                        st.error(f"Excel export failed: {e}")
                        st.caption("Please report this issue if it persists")

                else:
                    st.info(f"👆 Click the button above to run qualitative analysis for {selected_ticker}")

        else:
            st.info("👈 Run the screener first to access qualitative analysis")

with tab6:
    st.header("🎯 Custom Company Analysis")
    st.markdown("""
    Analyze **any company** (quality + valuation) without needing to run the full screener.
    Perfect for researching specific tickers that caught your attention.
    """)

    # Ticker input
    col1, col2 = st.columns([2, 1])

    with col1:
        custom_ticker = st.text_input(
            "Enter Ticker Symbol",
            placeholder="e.g., MSFT, GOOGL, BRK.B",
            help="Enter any valid stock ticker"
        ).upper().strip()

    with col2:
        st.markdown("")  # Spacing
        st.markdown("")  # Spacing
        analyze_button = st.button(
            f"🔍 Analyze {custom_ticker if custom_ticker else 'Company'}",
            disabled=not custom_ticker,
            use_container_width=True,
            type="primary"
        )

    if analyze_button and custom_ticker:
        with st.spinner(f"🔄 Analyzing {custom_ticker}... This may take 30-60 seconds"):
            try:
                # Import dependencies
                from screener.orchestrator import ScreenerPipeline
                from screener.qualitative import QualitativeAnalyzer
                import yaml

                # Initialize pipeline (this loads settings.yaml and sets up FMP client)
                pipeline = ScreenerPipeline('settings.yaml')

                # Initialize qualitative analyzer
                qual_analyzer = QualitativeAnalyzer(pipeline.fmp, pipeline.config)

                # Run full analysis (without needing screener results)
                # company_type will be auto-detected if set to 'unknown'
                analysis = qual_analyzer.analyze_symbol(
                    custom_ticker,
                    company_type='unknown',  # Auto-detect
                    peers_df=None  # No peer comparison in custom analysis
                )

                if analysis and 'error' not in analysis:
                    st.session_state[f'custom_{custom_ticker}'] = analysis
                    st.success(f"✅ Analysis for {custom_ticker} complete!")
                    st.rerun()
                else:
                    error_msg = analysis.get('error', 'Unknown error') if analysis else 'Failed to retrieve data'
                    st.error(f"❌ Analysis failed: {error_msg}")
                    st.info("💡 Make sure the ticker is valid and try again. Some tickers may have limited data.")

            except Exception as e:
                st.error(f"❌ Analysis failed: {str(e)}")
                st.info("💡 Please check that the ticker is valid and try again.")

    # Display cached analysis if available
    if custom_ticker and f'custom_{custom_ticker}' in st.session_state:
        analysis = st.session_state[f'custom_{custom_ticker}']

        st.markdown("---")

        # Company Info
        st.subheader(f"📊 {custom_ticker} - Company Overview")

        # Business Summary
        with st.expander("📝 Business Summary", expanded=False):
            st.write(analysis.get('business_summary', 'Not available'))

        st.markdown("---")

        # === INTRINSIC VALUE SECTION (Same as Qualitative tab) ===
        st.subheader("💰 Intrinsic Value Estimation")
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
                    emoji = '🟢'
                elif assessment == 'Overvalued':
                    color = 'red'
                    emoji = '🔴'
                else:
                    color = 'orange'
                    emoji = '🟡'

                st.markdown(f"### {emoji} {assessment}: {upside:+.1f}% {'upside' if upside > 0 else 'downside'}")
                st.caption(f"**Confidence:** {confidence}")

            # Advanced Metrics (same as Qualitative tab)
            st.markdown("---")

            # 1. ROIC vs WACC (or ROE for financials)
            capital_efficiency = intrinsic.get('capital_efficiency', {})
            if capital_efficiency:
                metric_name = capital_efficiency.get('metric_name', 'ROIC')
                st.markdown(f"### ⚙️ Capital Efficiency ({metric_name} vs WACC)")
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
                    st.success(f"✅ {assessment_text} - {metric_name} exceeds WACC")
                else:
                    st.error(f"⚠️ {assessment_text} - {metric_name} below WACC")

            # 2. Quality of Earnings
            earnings_quality = intrinsic.get('earnings_quality', {})
            if earnings_quality:
                st.markdown("### 🎯 Quality of Earnings")
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
                st.markdown("### 📊 Profitability Margins & Trends")
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
                st.markdown("### 📊 Valuation Multiples vs Peers")

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
                        st.warning(f"⚠️ Trading at a **premium** to peers on {premium_count}/{len(vs_peers)} metrics")
                    elif discount_count > premium_count:
                        st.success(f"✅ Trading at a **discount** to peers on {discount_count}/{len(vs_peers)} metrics")
                    else:
                        st.info(f"📊 **In-line** with peer valuations")

            # 6. Growth Consistency (Historical Trends)
            growth_consistency = intrinsic.get('growth_consistency', {})
            if growth_consistency:
                st.markdown("---")
                st.markdown("### 📈 Growth Consistency & Historical Trends")

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
                    st.markdown("#### 💵 Revenue Growth")
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
                    st.markdown("#### 💰 Earnings Growth")
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
                st.markdown("### 💰 Cash Conversion Cycle (Working Capital Efficiency)")

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
                        st.metric("YoY Trend", "📈 Improving", delta=f"{yoy_change:.0f} days")
                    elif trend == 'deteriorating':
                        st.metric("YoY Trend", "📉 Worsening", delta=f"{yoy_change:+.0f} days")
                    else:
                        st.metric("YoY Trend", "→ Stable", delta=f"{yoy_change:+.0f} days")

                st.caption("💡 Lower CCC = Better working capital efficiency. Negative CCC means suppliers finance operations.")

            # 8. Operating Leverage (FASE 1)
            operating_lev = intrinsic.get('operating_leverage', {})
            if operating_lev:
                st.markdown("---")
                st.markdown("### ⚙️ Operating Leverage (Cost Structure)")

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

                st.caption("💡 High OL = High fixed costs. Profits amplify with revenue growth but also with declines.")

            # 9. Reinvestment Quality (FASE 1)
            reinvestment = intrinsic.get('reinvestment_quality', {})
            if reinvestment:
                st.markdown("---")
                st.markdown("### 🔄 Reinvestment Quality (Capital Efficiency of Growth)")

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
                        st.caption("🌟 Excellent")
                    elif growth_roic > 1:
                        st.caption("✅ Good")
                    elif growth_roic > 0.5:
                        st.caption("⚠️ Moderate")
                    else:
                        st.caption("❌ Poor")

                with col4:
                    net_capex = reinvestment.get('net_capex', 0)
                    delta_wc = reinvestment.get('delta_wc', 0)
                    st.metric("Net Capex",
                            f"${net_capex/1e9:.1f}B",
                            delta=f"ΔWC: ${delta_wc/1e9:.1f}B")

                st.caption("💡 Growth ROIC > 1 = Efficient growth. > 2 = Exceptional capital efficiency.")

            # 10. Economic Profit / EVA (FASE 2)
            eva = intrinsic.get('economic_profit', {})
            if eva:
                st.markdown("---")
                st.markdown("### 💎 Economic Profit (EVA - Economic Value Added)")

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
                        st.metric("5Y Avg EVA", avg_eva, delta="📈 Improving")
                    elif trend == 'deteriorating':
                        st.metric("5Y Avg EVA", avg_eva, delta="📉 Declining")
                    else:
                        st.metric("5Y Avg EVA", avg_eva, delta="→ Stable")

                st.caption("💡 EVA = NOPAT - (WACC × Invested Capital). Positive EVA = Value creation above cost of capital.")

            # 11. Capital Allocation Score (FASE 2)
            cap_alloc = intrinsic.get('capital_allocation', {})
            if cap_alloc:
                st.markdown("---")
                st.markdown("### 📊 Capital Allocation Scorecard")

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

                st.caption("💡 Best allocators: Return capital when opportunities are scarce, reinvest when ROIC > WACC.")

            # 12. Interest Rate Sensitivity (FASE 2)
            rate_sens = intrinsic.get('interest_rate_sensitivity', {})
            if rate_sens and rate_sens.get('applicable', False):
                st.markdown("---")
                st.markdown("### 📈 Interest Rate Sensitivity (Financial Companies)")

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
                        st.metric("NIM Trend", "📈 Expanding", delta=f"+{yoy:.2f}% YoY")
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

                st.caption("💡 Higher NIM = More profitable. Expanding NIM = Benefiting from rate increases.")

            # 13. Insider Trading Analysis (Premium Feature)
            insider = intrinsic.get('insider_trading', {})
            if insider and insider.get('available', False):
                st.markdown("---")
                st.markdown("### 🎯 Insider Trading Activity (Last 12 Months)")

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
                        st.metric("Net Position", "🟢 Buying")
                    else:
                        st.metric("Net Position", "🔴 Selling")
                    st.caption(f"Buy: {buy_val} | Sell: {sell_val}")

                # Show recent trades
                recent_trades = insider.get('recent_trades', [])
                if recent_trades:
                    st.markdown("**Most Recent Buys:**")
                    for trade in recent_trades[:3]:
                        st.caption(f"• {trade.get('date')}: {trade.get('name')} - ${trade.get('value')/1e3:.0f}K")

                st.caption("💡 Multiple insider buys (especially executives) often precede stock price increases.")

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
                        st.caption("✅ Guidance provided")
                    else:
                        st.caption("⚠️ No guidance")

                # Keyword breakdown
                st.markdown("**Keyword Mentions:**")
                pos_count = sentiment.get('positive_mentions', 0)
                neg_count = sentiment.get('negative_mentions', 0)
                cau_count = sentiment.get('caution_mentions', 0)
                st.caption(f"Growth/Positive: {pos_count} | Challenges/Negative: {neg_count} | Caution: {cau_count}")

                st.caption("💡 Positive sentiment from management often signals confidence in future performance.")

            # 15. Price Projections by Scenario
            projections = intrinsic.get('price_projections', {})
            if projections and 'scenarios' in projections:
                st.markdown("---")
                st.markdown("### 📈 Price Projections by Scenario")

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
                                emoji = '📊'
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
                    st.markdown("### ✅ No Red Flags Detected")
                    st.success("All financial health checks passed")

            # 6. Reverse DCF
            reverse_dcf = intrinsic.get('reverse_dcf', {})
            if reverse_dcf:
                st.markdown("---")
                st.markdown("### 🔄 Reverse DCF: Market Expectations")
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
                        st.warning(f"⚠️ {interpretation}")
                    elif "continuation" in interpretation.lower():
                        st.success(f"✅ {interpretation}")
                    else:
                        st.error(f"📉 {interpretation}")

            # Export to Excel
            st.markdown("---")
            st.markdown("### 📥 Export Analysis")

            try:
                excel_data = create_qualitative_excel(analysis, custom_ticker, datetime.now())
                st.download_button(
                    label="📊 Download Complete Analysis (Excel)",
                    data=excel_data,
                    file_name=f"{custom_ticker}_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    help="Download full analysis with all metrics"
                )
                st.caption("📋 Includes: Valuation, Capital Efficiency, Earnings Quality, Margins, Red Flags, Reverse DCF, and more")
            except Exception as e:
                st.error(f"Excel export failed: {e}")

        else:
            st.info(f"💡 Enter a ticker above and click 'Analyze' to see detailed quality and valuation analysis")

with tab7:
    st.header("About UltraQuality Screener")

    st.markdown("""
    ### 🎯 What It Does

    UltraQuality combines **Quality** and **Value** investing principles to screen stocks:

    - **Value Metrics**: EV/EBIT, P/E, P/B, Shareholder Yield
    - **Quality Metrics**: ROIC, ROA/ROE, FCF Margin, Efficiency Ratios
    - **Guardrails**: Altman Z-Score, Beneish M-Score, Accruals Analysis

    ### 📊 Asset Types Supported

    - **Non-Financials**: Manufacturing, Tech, Services, Consumer
    - **Financials**: Banks, Insurance, Asset Management
    - **REITs**: Real Estate Investment Trusts

    ### 🔍 Methodology

    1. **Universe Building**: Filter by market cap and volume
    2. **Top-K Selection**: Preliminary ranking
    3. **Feature Calculation**: Value & Quality metrics
    4. **Guardrails**: Accounting quality checks
    5. **Scoring**: Industry-normalized z-scores
    6. **Decision**: BUY / MONITOR / AVOID

    ### ⚖️ Scoring Formula

    ```
    Composite Score = (Value Weight × Value Score) + (Quality Weight × Quality Score)

    Decision:
    - Score ≥ 75 + VERDE → BUY
    - Score 60-75 or AMBAR → MONITOR
    - Score < 60 or ROJO → AVOID
    ```

    ### 📚 References

    - Altman Z-Score (1968) - Bankruptcy prediction
    - Beneish M-Score (1999) - Earnings manipulation detection
    - Sloan (1996) - Accruals anomaly
    - Novy-Marx (2013) - Gross profitability premium

    ### ⚠️ Disclaimer

    This tool is for **educational and research purposes only**.
    It is NOT investment advice. Always conduct your own due diligence
    and consult with a qualified financial advisor before making
    investment decisions.

    ### 🔗 Links

    - [Documentation](https://github.com/pblo97/UltraQuality)
    - [FMP API](https://financialmodelingprep.com)
    """)

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("UltraQuality v1.0")
st.sidebar.caption("Powered by FMP API")
