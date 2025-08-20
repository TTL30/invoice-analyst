import streamlit as st
from invoice_analyst.components.analytics import analyst
from invoice_analyst.components.gestion import gestion
from invoice_analyst.utils import img_to_bytes, displayPDF


def viewer(db_manager):
    if st.session_state["page"] == "extract" and st.session_state.get("uploaded_file"):
        st.markdown(
            displayPDF(st.session_state["uploaded_file"]), unsafe_allow_html=True
        )
    elif st.session_state["page"] == "analyst":
        analyst(db_manager)
    elif st.session_state["page"] == "gestion":
        gestion(db_manager)
    else:
        st.markdown(
            """
            <div style="display: flex; justify-content: center; align-items: center; height: 70vh;">
                <img src="data:image/png;base64,{}" width="400" style="display: block;"/>
            </div>
            """.format(
                img_to_bytes(
                    "/Users/tiagoteixeira/code/invoice-analyst/assets/logo1.png"
                )
            ),
            unsafe_allow_html=True,
        )
