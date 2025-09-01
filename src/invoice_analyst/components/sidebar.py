"""
Main Sidebar Component

Handles application navigation and user interface controls.
"""

import streamlit as st
from invoice_analyst.page.extraction import sidebar as extraction_sidebar


def reset_session_state() -> None:
    """
    Reset Streamlit session state variables related to file upload and extraction.

    This clears all temporary data when navigating between pages.
    """
    st.session_state["uploaded_file"] = None
    st.session_state["pdf_name"] = None
    st.session_state["structured_data"] = None
    st.session_state["data_articles"] = None
    st.session_state["annotated_pdf"] = None
    st.session_state["extraction_done"] = False


def sidebar() -> None:
    """
    Render the main application sidebar with navigation and page-specific controls.

    Handles:
    - Navigation buttons between different application sections
    - User logout functionality
    - Page-specific sidebar content (extraction tools, dashboard filters)
    """
    with st.sidebar:
        # --- Navigation Buttons ---
        top_col1, top_col2, top_col3 = st.columns([5, 5, 2], gap="small")
        with top_col1:
            if st.button(
                "💾",
                key="home_btn",
                help="élécharger une nouvelle facture",
                use_container_width=True,
                type=(
                    "primary" if st.session_state["page"] == "extract" else "secondary"
                ),
            ):
                st.session_state["page"] = "extract"
                reset_session_state()
                st.rerun()
        with top_col2:
            if st.button(
                "📊 Dashboard",
                key="dashboard_btn",
                use_container_width=True,
                type=(
                    "primary"
                    if st.session_state["page"] in ["gestion", "analyst"]
                    else "secondary"
                ),
            ):
                st.session_state["page"] = "analyst"
                reset_session_state()
                st.rerun()
        with top_col3:
            if st.button("➜", key="logout_btn", use_container_width=True):
                # Remove user/session from session_state and cookies if used
                st.session_state["user"] = None
                st.session_state["session"] = None
                reset_session_state()
                del st.session_state["cookies"]["user_id"]
                st.session_state["cookies"].save()
                st.success("Déconnexion réussie.")
                st.rerun()
        st.markdown("---")

        # --- Extract Page ---
        if st.session_state["page"] == "extract":
            extraction_sidebar()
        # --- Dashboard & Navigation ---
        else:
            # --- Sidebar Styling ---
            st.markdown(
                """
                <style>
                [data-testid="stSidebar"][aria-expanded="true"] {
                    min-width: 25%;
                    max-width: 30%;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )
            if st.button(
                "🔎 Analyse",
                key="analyse_btn",
                use_container_width=True,
                type=(
                    "primary" if st.session_state["page"] == "analyst" else "secondary"
                ),
            ):
                st.session_state["page"] = "analyst"
                st.rerun()
            elif st.button(
                "🗂️ Gestion",
                key="gestion_btn",
                use_container_width=True,
                type=(
                    "primary" if st.session_state["page"] == "gestion" else "secondary"
                ),
            ):
                st.session_state["page"] = "gestion"
                st.rerun()
