import json
import streamlit as st
import pandas as pd
from invoice_analyst.constants import ARTICLES_COLUMNS_CONFIG, structure_prompt, MANDATORY_COLUMNS
from invoice_analyst.utils import (
    extract_articles_ocr_from_pdf,
    postprocess_markdown_remove_redundant,
    structure_data_chat,
    highlight_pdf_with_rules
)

def reset_session_state():
    st.session_state["uploaded_file"] = None
    st.session_state["pdf_name"] = None
    st.session_state["structured_data"] = None
    st.session_state["data_articles"] = None
    st.session_state["annotated_pdf"] = None
    st.session_state["extraction_done"] = False


def sidebar(current_page):
    # Sidebar styling
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"][aria-expanded="true"] {
            width: 50px;
            min-width: 20%;
            max-width: 70%;
        }
        </style>
        """,
        unsafe_allow_html=True,
    ) 

    with st.sidebar:
        # Navigation buttons
        top_col1, top_col2 = st.columns([1, 1], gap="small")
        with top_col1:
            if st.button("🏠", key="home_btn", use_container_width=True):
                st.session_state["page"] = "analyst"
                reset_session_state()
                st.rerun()
        with top_col2:
            if st.button("Dashboard", key="dashboard_btn", use_container_width=True, type='primary'):
                st.session_state["page"] = "dashboard"
                reset_session_state()
                st.rerun()
        st.markdown("---")

        # Analyst page
        if current_page == "analyst":
            uploaded_file = st.file_uploader(
                label="📥",
                accept_multiple_files=False,
                type=["pdf"],
                label_visibility="hidden"
            )

            # Step 1: File uploaded but no extraction yet
            if uploaded_file and not st.session_state.get("extraction_done", False):
                st.session_state["uploaded_file"] = uploaded_file
                st.session_state["pdf_name"] = uploaded_file.name

                st.markdown("---")
                st.text("Veuillez entrer le premier article")

                df = pd.DataFrame(columns=ARTICLES_COLUMNS_CONFIG.keys())
                confirmation_df = st.data_editor(
                    df,
                    num_rows="dynamic",
                    use_container_width=True,
                    column_config=ARTICLES_COLUMNS_CONFIG,
                    key="article_editor"
                )
                
                row_filled = False
                if not confirmation_df.empty:
                    row_filled = all(
                        (confirmation_df.iloc[0][col] is not None) and (str(confirmation_df.iloc[0][col]).strip() != "")
                        for col in confirmation_df.columns
                    )

                validate_btn = st.button(
                    "Lancement de l'extraction",
                    key="validate_btn",
                    help="Confirmation du premier article",
                    disabled=not row_filled,
                    use_container_width=True,
                    type='primary'
                )

                if validate_btn:
                    st.markdown("---")
                    with st.spinner("Extraction des données en cours...", show_time=True):
                        raw_markdown_ocr_results = extract_articles_ocr_from_pdf(
                            uploaded_file, st.session_state["client"]
                        )
                        cleaned_markdown_ocr_results = postprocess_markdown_remove_redundant(raw_markdown_ocr_results)
                        
                        structured_data = json.loads(
                            structure_data_chat(
                                st.session_state["client"],
                                structure_prompt(cleaned_markdown_ocr_results, confirmation_df.iloc[0].to_dict()),
                                response_format={"type": "json_object"}
                            )
                        )
                        
                        data_articles = pd.DataFrame(
                            structured_data["articles"],
                            columns=ARTICLES_COLUMNS_CONFIG.keys()
                        )

                        # Annotate PDF
                        annotations = []
                        if "Reference" in data_articles.columns:
                            for _, row in data_articles.iterrows():
                                ref = str(row["Reference"]).strip()
                                if ref:
                                    filtered_data = {
                                        k: v for k, v in row.to_dict().items() if k in MANDATORY_COLUMNS
                                    }
                                    annotations.append({
                                        "text": ref,
                                        "data": filtered_data,
                                        "color": (0, 0.5, 0)
                                    })
                        
                        st.session_state["structured_data"] = structured_data
                        st.session_state["data_articles"] = data_articles
                        st.session_state["annotated_pdf"] = highlight_pdf_with_rules(uploaded_file, annotations)
                        st.session_state["extraction_done"] = True
                        st.rerun()

            # Step 2: Show results after extraction
            elif st.session_state.get("extraction_done", False):
                st.markdown("---")

                st.session_state["uploaded_file"] = st.session_state["annotated_pdf"]

                left_col, right_col = st.columns([1, 1])
                with left_col:
                    invoice_name = st.text_input("Nom de la facture", value=st.session_state["pdf_name"])
                    fournisseur_nom = st.text_input(
                        "Fournisseur",
                        value=st.session_state["structured_data"].get("Information fournisseur", {}).get("nom", "")
                    )
                with right_col:
                    invoice_numero = st.text_input(
                        "Numéro de facture",
                        value=st.session_state["structured_data"].get("Numéro de facture", "")
                    )

                    # Safely handle missing/invalid date
                    raw_date = st.session_state["structured_data"].get("Date facture", "")
                    try:
                        invoice_date = pd.to_datetime(raw_date, dayfirst=True).date()
                    except Exception:
                        invoice_date = pd.to_datetime("today").date()
                    invoice_date = st.date_input("Date de la facture", value=invoice_date)

                fournisseur_adresse = st.text_area(
                    "Adresse",
                    value=st.session_state["structured_data"].get("Information fournisseur", {}).get("adresse", "")
                )

                # Articles table
                articles_df = st.data_editor(
                    st.session_state["data_articles"],
                    num_rows="dynamic",
                    use_container_width=True,
                    key="save_data_editor",
                    column_config=ARTICLES_COLUMNS_CONFIG,
                    height=250,
                )

                # Totals
                nb_colis, invoice_ht_col, invoice_tva_col, invoice_ttc_col = st.columns([1, 1, 1, 1])
                with nb_colis:
                    nombre_colis = st.number_input(
                        "Nombre de colis",
                        value=int(st.session_state["structured_data"].get("Nombre de colis", 1)),
                        min_value=1
                    )
                with invoice_ht_col:
                    total_ht = st.number_input(
                        "Total HT",
                        value=float(st.session_state["structured_data"].get("Total", {}).get("total_ht", 0.0)),
                        format="%.2f"
                    )
                with invoice_tva_col:
                    total_tva = st.number_input(
                        "TVA",
                        value=float(st.session_state["structured_data"].get("Total", {}).get("tva", 0.0)),
                        format="%.2f"
                    )
                with invoice_ttc_col:
                    total_ttc = st.number_input(
                        "Total TTC",
                        value=float(st.session_state["structured_data"].get("Total", {}).get("total_ttc", 0.0)),
                        format="%.2f"
                    )

                # Consistency check
                if "Quantité" in articles_df.columns:
                    quantite_sum = articles_df["Quantité"].sum()
                    if nombre_colis != quantite_sum:
                        st.warning(
                            f"⚠️ Attention : Le nombre de colis ({nombre_colis}) est différent de la somme des quantités ({quantite_sum})."
                        )

                if st.button("Enregistrer les données", key="save_data_btn", use_container_width=True, type='primary'):
                    st.success("Données enregistrées !")
                    # TODO: Implement the save functionality

        # Dashboard page
        elif current_page == "dashboard":
            st.subheader("Dashboard Filters")
            st.write("Add dashboard-specific sidebar content here.")
