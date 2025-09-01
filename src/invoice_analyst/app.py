"""
Invoice Analyst - Main Application

A Streamlit application for analyzing and managing invoices using OCR and AI.
"""

import streamlit as st
from supabase import create_client
from mistralai import Mistral
from streamlit_cookies_manager import EncryptedCookieManager

from invoice_analyst.utils import img_to_bytes
from invoice_analyst.components.sidebar import sidebar
from invoice_analyst.page.extraction import main_content as extraction_main_content
from invoice_analyst.page.gestion import run as gestion
from invoice_analyst.page.analyse import run as analyst

LOGO = "assets/logo1.png"

def initialize_session():
    """Initialize Supabase client, cookies, and session state."""
    # Connect to Supabase
    url = st.secrets["supabase_url"]
    key = st.secrets["supabase_key"]
    supabase = create_client(url, key)
    st.session_state["supabase"] = supabase
    
    # Cookie manager
    cookies = EncryptedCookieManager(
        prefix="invoice_analyst",
        password=st.secrets["cookie_secret"],
    )
    st.session_state["cookies"] = cookies
    if not cookies.ready():
        st.stop()

    # Initialize session state
    if "user" not in st.session_state:
        st.session_state["user"] = cookies.get("user_id")
    if "session" not in st.session_state:
        st.session_state["session"] = None


def render_login_page():
    """Render the login page UI."""
    st.markdown(
        f"""
        <div style="
            display: flex;
            justify-content: center;
            align-items: center;
            height: 30vh;
            flex-direction: column;
        ">
            <img src="data:image/png;base64,{img_to_bytes(LOGO)}" width="300"/>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return st.text_input("Email"), st.text_input("Password", type="password")


def handle_authentication(email, password):
    """Handle user authentication."""
    if st.button("Connexion"):
        try:
            session = st.session_state["supabase"].auth.sign_in_with_password(
                {"email": email, "password": password}
            )
            user = session.user
            st.session_state["user"] = user.id
            st.session_state["session"] = session

            # Store user_id in cookies for persistence
            st.session_state["cookies"]["user_id"] = user.id
            st.session_state["cookies"].save()

            st.success("Connexion réussie!")
            st.rerun()
        except Exception as e:
            st.error(f"Connexion impossible: {str(e)}")


def initialize_app_data():
    """Load application data from database."""
    supabase = st.session_state["supabase"]
    
    st.session_state["marques"] = (
        supabase.table("marques").select("*").execute().data
    )
    st.session_state["fournisseurs"] = (
        supabase.table("fournisseurs").select("*").execute().data
    )
    st.session_state["categories"] = (
        supabase.table("categories").select("*").execute().data
    )


def initialize_session_variables():
    """Initialize session state variables."""
    if "uploaded_file" not in st.session_state:
        st.session_state["uploaded_file"] = None
    if "pdf_name" not in st.session_state:
        st.session_state["pdf_name"] = None
    if "page" not in st.session_state:
        st.session_state["page"] = "extract"
    if "client" not in st.session_state:
        st.session_state["client"] = Mistral(api_key=st.secrets["mistral_api_key"])


def render_main_app():
    """Render the main application interface."""
    sidebar()
    
    if st.session_state["page"] == "extract" and st.session_state.get("uploaded_file"):
        extraction_main_content()
    elif st.session_state["page"] == "analyst":
        analyst()
    elif st.session_state["page"] == "gestion":
        gestion()
    else:
        st.markdown(
            f"""
            <div style="display: flex; justify-content: center; align-items: center; height: 70vh;">
                <img src="data:image/png;base64,{img_to_bytes(LOGO)}" width="400" style="display: block;"/>
            </div>
            """,
            unsafe_allow_html=True,
        )


def main():
    """Main application entry point."""
    # Initialize session and page config
    initialize_session()
    
    st.set_page_config(
        page_icon=LOGO,
        page_title="Gestionnaire de factures",
    )

    # Check authentication
    if st.session_state["user"] is None:
        email, password = render_login_page()
        handle_authentication(email, password)
        st.stop()

    # Main app
    st.set_page_config(
        page_icon=LOGO,
        page_title="Invoice Analyst",
        layout="wide",
    )
    
    initialize_app_data()
    initialize_session_variables()
    render_main_app()


if __name__ == "__main__":
    main()
