import streamlit as st
from mistralai import Mistral
from components.sidebar import sidebar
from components.viewer import viewer
from components.dashboard import dashboard

st.set_page_config(page_icon="/Users/tiagoteixeira/code/invoice-analyst/assets/logo.jpg", page_title="Invoice Analyst", layout="centered")

def init_session_state():
    if "uploaded_file" not in st.session_state:
        st.session_state["uploaded_file"] = None
    if "pdf_name" not in st.session_state:
        st.session_state["pdf_name"] = None
    if "page" not in st.session_state:
        st.session_state["page"] = "analyst"
    if "client" not in st.session_state:
        st.session_state["client"] = Mistral(api_key="BuL1xwdpsBm4Jdwpdx2ycOCl382xIRBO")


init_session_state()
current_page = st.session_state["page"]
sidebar(current_page)

if current_page == "analyst":
    viewer()
elif current_page == "dashboard":
    dashboard()