"""
Invoice Analyst Package

A comprehensive invoice analysis application that provides:
- PDF invoice processing and OCR extraction
- AI-powered data structuring and categorization
- Invoice management and analytics dashboard
- Multi-supplier and product tracking

Main Components:
- app.py: Main Streamlit application
- components/: Reusable UI components (charts, sidebar)
- page/: Application pages (extraction, analysis, management)
- utils.py: Core utility functions for PDF and data processing
- constants.py: Application configuration and constants

Usage:
    Run the application with: streamlit run src/invoice_analyst/app.py
"""

__version__ = "0.1.0"
__author__ = "Invoice Analyst Team"

# Import main modules for easier access
from . import utils
from . import constants
from . import components
from . import page

__all__ = ["utils", "constants", "components", "page"]
