import streamlit as st
from mistralai import Mistral
from invoice_analyst.components.sidebar import sidebar
from invoice_analyst.components.main import viewer
from invoice_analyst.db.setup_db import setup_database
from invoice_analyst.db.db_manager import DBManager

st.set_page_config(
    page_icon="/Users/tiagoteixeira/code/invoice-analyst/assets/logo.jpg",
    page_title="Invoice Analyst",
    layout="wide",
)


def init_session_state():
    if "uploaded_file" not in st.session_state:
        st.session_state["uploaded_file"] = None
    if "pdf_name" not in st.session_state:
        st.session_state["pdf_name"] = None
    if "page" not in st.session_state:
        st.session_state["page"] = "extract"
    if "client" not in st.session_state:
        st.session_state["client"] = Mistral(api_key="BuL1xwdpsBm4Jdwpdx2ycOCl382xIRBO")


# --- Database Setup ---
setup_database()
db_manager = DBManager(
    "/Users/tiagoteixeira/code/invoice-analyst/src/invoice_analyst/db/invoices.db"
)
categories = db_manager.get_rows("categories")
categories_dict = {k: v for k, v in categories}
marques = db_manager.get_rows("marques")
marques_dict = {k: v for k, v in marques}
fournisseurs = db_manager.get_rows("fournisseurs")
fournisseurs_dict = {k: v for k, v, _, _ in fournisseurs}
st.session_state["categories"] = categories_dict
st.session_state["marques"] = marques_dict
st.session_state["fournisseurs"] = fournisseurs_dict
# --- Streamlit App ---
init_session_state()
sidebar(db_manager)
viewer(db_manager)
