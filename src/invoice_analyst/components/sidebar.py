import os
import json
import streamlit as st
import pandas as pd
from invoice_analyst.constants import (
    structure_prompt,
    MANDATORY_COLUMNS,
    SAVED_INVOICES_DIR,
)
from invoice_analyst.utils import (
    extract_articles_ocr_from_pdf,
    postprocess_markdown_remove_redundant,
    structure_data_chat,
    highlight_pdf_with_rules,
    generate_invoice_unique_id,
)


def reset_session_state():
    """Reset Streamlit session state for file and extraction."""
    st.session_state["uploaded_file"] = None
    st.session_state["pdf_name"] = None
    st.session_state["structured_data"] = None
    st.session_state["data_articles"] = None
    st.session_state["annotated_pdf"] = None
    st.session_state["extraction_done"] = False


def sidebar(db_manager):
    # --- Prepare column config for articles ---
    categories_name = st.session_state.get("categories", []).values()
    ARTICLES_COLUMNS_CONFIG = {
        "Reference": st.column_config.TextColumn("Reference", required=True),
        "Désignation": st.column_config.TextColumn("Désignation"),
        "Prix Unitaire": st.column_config.NumberColumn("Prix Unitaire", format="%.3f"),
        "Packaging": st.column_config.NumberColumn("Packaging", format="%d"),
        "Quantité": st.column_config.NumberColumn("Quantité", format="%d"),
        "Total": st.column_config.NumberColumn("Total", format="%.3f"),
        "Marque": st.column_config.TextColumn("Marque"),
        "Catégorie": st.column_config.SelectboxColumn(
            "Catégorie", options=categories_name
        ),
    }

    # --- Sidebar Styling ---
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"][aria-expanded="true"] {
            min-width: 15%;
            max-width: 70%;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        # --- Navigation Buttons ---
        top_col1, top_col2 = st.columns([1, 1], gap="small")
        with top_col1:
            if st.button(
                "🏠",
                key="home_btn",
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
                "Dashboard",
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
        st.markdown("---")

        # --- Extract Page ---
        if st.session_state["page"] == "extract":
            # File uploader
            uploaded_file = st.file_uploader(
                label="📥",
                accept_multiple_files=False,
                type=["pdf"],
                label_visibility="hidden",
            )
            # Sidebar width adjustment for extract page
            st.markdown(
                """
                <style>
                [data-testid="stSidebar"][aria-expanded="true"] {
                    min-width: 50% !important;
                    max-width: 50% !important;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

            # --- Step 1: File uploaded, no extraction yet ---
            if uploaded_file and not st.session_state.get("extraction_done", False):
                st.session_state["uploaded_file"] = uploaded_file
                st.session_state["pdf_name"] = uploaded_file.name

                st.markdown("---")
                st.text(
                    "Veuillez entrer le premier article",
                    help="Les informations de l'article seront utilisées pour structurer les données.",
                )

                # Empty DataFrame for first article entry
                def autofill_rows(db_manager):
                    # Only new rows (added by the user)
                    added_rows = st.session_state["article_editor"]["added_rows"]
                    df = pd.DataFrame(added_rows)
                    if df.empty or "Reference" not in df.columns:
                        return  # nothing to do

                    reference = df.at[0, "Reference"]

                    if reference:
                        product = db_manager.get_rows(
                            "produits", "reference = ?", (reference,)
                        )
                        if product:
                            product = product[0]
                            autofill_df = pd.DataFrame(
                                columns=ARTICLES_COLUMNS_CONFIG.keys(),
                                data={
                                    "Reference": [product[2]],
                                    "Désignation": [product[1]],
                                    "Marque": [
                                        st.session_state["marques"].get(
                                            product[5], None
                                        )
                                    ],
                                    "Catégorie": [
                                        st.session_state["categories"].get(
                                            product[4], None
                                        )
                                    ],
                                },
                            )
                            # save back to session so editor rerenders
                            st.session_state["autofill_df"] = autofill_df

                # Initial empty DataFrame
                df = pd.DataFrame(columns=ARTICLES_COLUMNS_CONFIG.keys())
                confirmation_df = st.data_editor(
                    st.session_state.get(
                        "autofill_df", df
                    ),  # use autofilled if available
                    num_rows="dynamic",
                    use_container_width=True,
                    column_config=ARTICLES_COLUMNS_CONFIG,
                    key="article_editor",
                    on_change=autofill_rows,
                    args=(db_manager,),
                    hide_index=True,
                )

                # Check if first row is filled
                row_filled = False
                if not confirmation_df.empty:
                    row_filled = all(
                        (confirmation_df.iloc[0][col] is not None)
                        and (str(confirmation_df.iloc[0][col]).strip() != "")
                        for col in confirmation_df.columns
                    )

                # Extraction button
                validate_btn = st.button(
                    "Lancement de l'extraction",
                    key="validate_btn",
                    help="Confirmation du premier article",
                    disabled=not row_filled,
                    use_container_width=True,
                    type="primary",
                )

                # --- Extraction logic ---
                if validate_btn:
                    st.markdown("---")
                    with st.spinner(
                        "Extraction des données en cours...", show_time=True
                    ):
                        # OCR extraction
                        raw_markdown_ocr_results = extract_articles_ocr_from_pdf(
                            uploaded_file, st.session_state["client"]
                        )
                        cleaned_markdown_ocr_results = (
                            postprocess_markdown_remove_redundant(
                                raw_markdown_ocr_results
                            )
                        )
                        # Structure data using LLM
                        structured_data = json.loads(
                            structure_data_chat(
                                st.session_state["client"],
                                structure_prompt(
                                    cleaned_markdown_ocr_results,
                                    confirmation_df.iloc[0].to_dict(),
                                    st.session_state["categories"],
                                ),
                                response_format={"type": "json_object"},
                            )
                        )
                        # Build articles DataFrame
                        data_articles = pd.DataFrame(
                            structured_data["articles"],
                            columns=ARTICLES_COLUMNS_CONFIG.keys(),
                        )

                        # Annotate PDF with article info
                        annotations = []
                        if "Reference" in data_articles.columns:
                            for _, row in data_articles.iterrows():
                                ref = str(row["Reference"]).strip()
                                if ref:
                                    filtered_data = {
                                        k: v
                                        for k, v in row.to_dict().items()
                                        if k in MANDATORY_COLUMNS
                                    }
                                    annotations.append(
                                        {
                                            "text": ref,
                                            "data": filtered_data,
                                            "color": (0, 0.5, 0),
                                        }
                                    )

                        # Save extraction results to session state
                        st.session_state["structured_data"] = structured_data
                        st.session_state["data_articles"] = data_articles
                        st.session_state["annotated_pdf"] = highlight_pdf_with_rules(
                            uploaded_file, annotations
                        )
                        st.session_state["extraction_done"] = True
                        st.rerun()

            # --- Step 2: Show results after extraction ---
            elif st.session_state.get("extraction_done", False):
                st.markdown("---")
                st.session_state["uploaded_file"] = st.session_state["annotated_pdf"]

                # --- Invoice Info Inputs ---
                left_col, right_col = st.columns([1, 1])
                with left_col:
                    invoice_name = st.text_input(
                        "Nom de la facture", value=st.session_state["pdf_name"]
                    )
                    fournisseur_nom = st.text_input(
                        "Fournisseur",
                        value=st.session_state["structured_data"]
                        .get("Information fournisseur", {})
                        .get("nom", ""),
                    )
                with right_col:
                    invoice_numero = st.text_input(
                        "Numéro de facture",
                        value=st.session_state["structured_data"].get(
                            "Numéro de facture", ""
                        ),
                    )
                    # Handle missing/invalid date
                    raw_date = st.session_state["structured_data"].get(
                        "Date facture", ""
                    )
                    try:
                        invoice_date = pd.to_datetime(raw_date, dayfirst=True).date()
                    except Exception:
                        invoice_date = pd.to_datetime("today").date()
                    invoice_date = st.date_input(
                        "Date de la facture", value=invoice_date
                    )

                fournisseur_adresse = st.text_area(
                    "Adresse",
                    value=st.session_state["structured_data"]
                    .get("Information fournisseur", {})
                    .get("adresse", ""),
                )

                # --- Articles Table ---
                articles_df = st.data_editor(
                    st.session_state["data_articles"],
                    num_rows="dynamic",
                    use_container_width=True,
                    key="save_data_editor",
                    column_config=ARTICLES_COLUMNS_CONFIG,
                    height=250,
                )

                # --- Totals and Consistency Check ---
                nb_colis, invoice_ht_col, invoice_tva_col, invoice_ttc_col = st.columns(
                    [1, 1, 1, 1]
                )
                with nb_colis:
                    nombre_colis = st.number_input(
                        "Nombre de colis",
                        value=int(
                            st.session_state["structured_data"].get(
                                "Nombre de colis", 1
                            )
                        ),
                        min_value=1,
                    )
                with invoice_ht_col:
                    total_ht = st.number_input(
                        "Total HT",
                        value=float(
                            st.session_state["structured_data"]
                            .get("Total", {})
                            .get("total_ht", 0.0)
                        ),
                        format="%.2f",
                    )
                with invoice_tva_col:
                    total_tva = st.number_input(
                        "TVA",
                        value=float(
                            st.session_state["structured_data"]
                            .get("Total", {})
                            .get("tva", 0.0)
                        ),
                        format="%.2f",
                    )
                with invoice_ttc_col:
                    total_ttc = st.number_input(
                        "Total TTC",
                        value=float(
                            st.session_state["structured_data"]
                            .get("Total", {})
                            .get("total_ttc", 0.0)
                        ),
                        format="%.2f",
                    )

                # Consistency check for quantities
                if "Quantité" in articles_df.columns:
                    quantite_sum = articles_df["Quantité"].sum()
                    if nombre_colis != quantite_sum:
                        st.warning(
                            f"⚠️ Attention : Le nombre de colis ({nombre_colis}) est différent de la somme des quantités ({quantite_sum})."
                        )

                # --- Save Data Button ---
                if st.button(
                    "Enregistrer les données",
                    key="save_data_btn",
                    use_container_width=True,
                    type="primary",
                ):
                    with st.spinner("Enregistrement des données..."):
                        # Save fournisseur
                        fournisseur_id = db_manager.get_or_create_row(
                            "fournisseurs",
                            {"nom": fournisseur_nom},
                            {"adresse": fournisseur_adresse},
                        )
                        # Save invoice
                        invoice_id = db_manager.get_or_create_row(
                            "factures",
                            {
                                "fournisseur_id": fournisseur_id,
                                "numero": invoice_numero,
                            },
                            {
                                "date": invoice_date.isoformat(),
                                "nom_fichier": st.session_state["pdf_name"],
                                "total_ht": total_ht,
                                "tva_amount": total_tva,
                                "total_ttc": total_ttc,
                            },
                        )
                        # --- Save PDF file with unique id ---
                        unique_id = generate_invoice_unique_id(
                            invoice_numero, fournisseur_id
                        )
                        os.makedirs(SAVED_INVOICES_DIR, exist_ok=True)
                        file_ext = os.path.splitext(st.session_state["pdf_name"])[-1]
                        save_path = os.path.join(
                            SAVED_INVOICES_DIR, f"{unique_id}{file_ext}"
                        )
                        with open(save_path, "wb") as f:
                            f.write(uploaded_file.getvalue())

                        # --- Save articles and invoice lines ---
                        for _, row in articles_df.iterrows():
                            categorie_id = db_manager.get_or_create_row(
                                "categories",
                                {"nom": row.get("Catégorie")},
                            )
                            marque_id = db_manager.get_or_create_row(
                                "marques",
                                {"nom": row.get("Marque")},
                            )
                            produit_id = db_manager.get_or_create_row(
                                "produits",
                                {
                                    "reference": row.get("Reference"),
                                    "fournisseur_id": fournisseur_id,
                                },
                                {
                                    "designation": row.get("Désignation"),
                                    "categorie_id": categorie_id,
                                    "marque_id": marque_id,
                                },
                            )
                            db_manager.get_or_create_row(
                                "lignes_facture",
                                {"facture_id": invoice_id, "produit_id": produit_id},
                                {
                                    "prix_unitaire": row.get("Prix Unitaire"),
                                    "collisage": row.get("Packaging"),
                                    "quantite": row.get("Quantité"),
                                    "montant": row.get("Total"),
                                },
                            )
                        st.session_state["extraction_done"] = False
                    st.success("Données enregistrées !")

        # --- Dashboard & Navigation ---
        else:
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
