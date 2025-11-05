"""
Entry point for Streamlit Cloud.

This file exists because Streamlit Cloud is configured to use run_screener.py
as the main file. It simply imports and executes the Streamlit UI.

For CLI usage, use: python cli_run_screener.py
"""

# Import everything from streamlit_app to run the UI
import streamlit_app

# Note: This file does NOT run the screener automatically.
# The UI loads, and the screener only runs when user clicks the button.
