import base64
import streamlit as st


def displayPDF(uploaded_file):
    bytes_data = uploaded_file.getvalue()
    base64_pdf = base64.b64encode(bytes_data).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

def viewer():
    if st.session_state.get("uploaded_file"):
        displayPDF(st.session_state["uploaded_file"])
    else:
        st.image("/Users/tiagoteixeira/code/invoice-analyst/assets/logo1.png", use_container_width=True)
