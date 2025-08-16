import tempfile
import base64
import streamlit as st
import io
from pdf_annotate import PdfAnnotator, Location, Appearance

def annotate_pdf_with_rectangles(pdf_bytes, annotations):
    """
    annotations: List of tuples (page, x1, y1, x2, y2, label, color)
    color: (r, g, b) tuple, values between 0 and 1
    """
    output = io.BytesIO()
    # Write PDF bytes to a temporary file
    with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_pdf:
        temp_pdf.write(pdf_bytes)
        temp_pdf.flush()
        annotator = PdfAnnotator(temp_pdf.name)
        for page, x1, y1, x2, y2, label, color in annotations:
            annotator.add_annotation(
                'square',
                Location(x1=x1, y1=y1, x2=x2, y2=y2, page=page),
                Appearance(stroke_color=color, stroke_width=2, fill=None, content=label),
            )
            annotator.add_annotation(
                'text',
                Location(x1=x1, y1=y1, x2=x1+80, y2=y2+20, page=page),
                Appearance(stroke_color=color, fill=(1, 1, 0), content=label),
            )
        annotator.write(output)
    output.seek(0)
    return output.read()

def displayPDF(uploaded_file, annotations=None):
    bytes_data = uploaded_file.getvalue()
    if annotations:
        bytes_data = annotate_pdf_with_rectangles(bytes_data, annotations)
    base64_pdf = base64.b64encode(bytes_data).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

def viewer():
    if st.session_state.get("uploaded_file"):
        displayPDF(st.session_state["uploaded_file"], st.session_state.get("annotations", []))
