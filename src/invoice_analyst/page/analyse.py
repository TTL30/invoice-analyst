"""
Analysis Dashboard Module

Provides comprehensive analytics and reporting functionality
for invoice data across different dimensions.
"""

import streamlit as st
from invoice_analyst.components.charts import style
from invoice_analyst.page.globale import run as globale
from invoice_analyst.page.produit import run as produit


def run() -> None:
    """
    Main analytics dashboard with tabbed interface.

    Provides analysis across three main dimensions:
    - Global: Overall spending and trends
    - Products: Product-specific analytics
    - Anomalies: Data quality and anomaly detection (placeholder)
    """
    style()
    tab1, tab3, tab4 = st.tabs(["Global", "Produits", "Anomalies"])
    # --- Global tab ---
    with tab1:
        globale()
    # --- Produits tab ---
    with tab3:
        produit()
    # --- Anomalies tab ---
    with tab4:
        st.info("À venir...")
