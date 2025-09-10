"""
Invoice Extraction Module

Handles PDF invoice extraction, OCR processing, and data structuring using AI.
"""

import json
from typing import Optional, Tuple, Dict, Any, List
import pandas as pd
import streamlit as st
from invoice_analyst.utils import displayPDF
from invoice_analyst.constants import (
    ARTICLES_COLUMNS_CONFIG,
    structure_prompt,
)
from invoice_analyst.utils import (
    extract_articles_ocr_from_pdf,
    postprocess_markdown_remove_redundant,
    structure_data_chat,
    highlight_pdf_with_rules,
)


def autofill_rows(columns: List[str]) -> None:
    """
    Autofill product information when a reference already exists in the database.

    Args:
        columns: List of column names for the DataFrame
    """
    added_rows = st.session_state.get("article_editor", {}).get("added_rows", [])
    df = pd.DataFrame(added_rows)
    if df.empty or "Reference" not in df.columns:
        return None

    reference = df.at[0, "Reference"]
    if not reference:
        return None

    product = (
        st.session_state["supabase"]
        .table("produits")
        .select("*")
        .eq("reference", reference)
        .execute()
        .data
    )

    if product:
        product = product[0]
        # Find marque name by id in the list of dicts
        marque_name = next(
            (
                m["nom"]
                for m in st.session_state["marques"]
                if m["id"] == product["marque_id"]
            ),
            None,
        )
        # Find categorie name by id in the list of dicts
        categorie_name = next(
            (
                c["nom"]
                for c in st.session_state["categories"]
                if c["id"] == product["categorie_id"]
            ),
            None,
        )
        st.session_state["autofill_df"] = pd.DataFrame(
            columns=columns,
            data={
                "Reference": [product["reference"]],
                "Désignation": [product["designation"]],
                "Marque": [marque_name],
                "Catégorie": [categorie_name],
            },
        )


def extract_invoice(
    uploaded_file: Any, confirmation_df: pd.DataFrame
) -> Tuple[Optional[Dict[str, Any]], Optional[pd.DataFrame], Optional[Any]]:
    """
    Extract structured data from a PDF invoice using OCR and LLM processing.

    Args:
        uploaded_file: Streamlit uploaded PDF file
        confirmation_df: DataFrame with confirmation data for extraction optimization

    Returns:
        tuple: (structured_data, data_articles, annotated_pdf) or (None, None, None) on error
    """
    client = st.session_state["client"]

    # OCR extraction
    raw_ocr = extract_articles_ocr_from_pdf(uploaded_file, client)
    cleaned_ocr = postprocess_markdown_remove_redundant(raw_ocr)

    # Structure data with LLM
    try:
        structured_data = json.loads(
            structure_data_chat(
                client,
                structure_prompt(
                    cleaned_ocr,
                    confirmation_df.iloc[0].to_dict(),
                    [cat["nom"] for cat in st.session_state["categories"]],
                ),
                response_format={"type": "json_object"},
            )
        )
    except Exception as e:
        st.error(f"Erreur lors de la structuration des données : {e}")
        return None, None

    data_articles = pd.DataFrame(
        structured_data.get("articles", []),
        columns=ARTICLES_COLUMNS_CONFIG.keys(),
    )

    # Annotate PDF
    annotations = []
    if "Reference" in data_articles.columns:
        for _, row in data_articles.iterrows():
            ref = str(row["Reference"]).strip()
            if ref:
                annotations.append(
                    {
                        "text": ref,
                        "data": {
                            k: v
                            for k, v in row.to_dict().items()
                            if k
                            in [
                                "Reference",
                                "Prix Unitaire",
                                "Packaging",
                                "Quantité",
                                "Total",
                            ]
                        },
                        "color": (0, 0.5, 0),
                    }
                )

    annotated_pdf = highlight_pdf_with_rules(uploaded_file, annotations)
    return structured_data, data_articles, annotated_pdf


def save_invoice_supabase_storage(
    uploaded_file: Any, invoice_info: Dict[str, Any], articles_df: pd.DataFrame
) -> None:
    """
    Save complete invoice data to Supabase database and storage.

    This function handles:
    - Creating/updating supplier information
    - Creating/updating invoice records
    - Uploading PDF to Supabase Storage
    - Creating/updating product records
    - Creating invoice line items

    Args:
        uploaded_file: The PDF file to be stored
        invoice_info (dict): Invoice metadata (supplier, number, date, etc.)
        articles_df (pandas.DataFrame): DataFrame containing invoice line items
    """
    supabase = st.session_state["supabase"]
    user_id = st.session_state["user"]
    st.text(f"Saving invoice for user_id: {user_id}")

    # --- Get or create fournisseur ---
    res = (
        supabase.table("fournisseurs")
        .select("id")
        .eq("user_id", user_id)
        .eq("nom", invoice_info["fournisseur_nom"])
        .execute()
    )
    if res.data:
        fournisseur_id = res.data[0]["id"]
    else:
        fournisseur = (
            supabase.table("fournisseurs")
            .insert(
                {
                    "user_id": user_id,
                    "nom": invoice_info["fournisseur_nom"],
                    "adresse": invoice_info.get("adresse", ""),
                }
            )
            .execute()
        )
        fournisseur_id = fournisseur.data[0]["id"]

    # --- Get or create facture ---
    res = (
        supabase.table("factures")
        .select("id")
        .eq("user_id", user_id)
        .eq("fournisseur_id", fournisseur_id)
        .eq("numero", invoice_info["numero"])
        .execute()
    )
    if res.data:
        invoice_id = res.data[0]["id"]
    else:
        facture = (
            supabase.table("factures")
            .insert(
                {
                    "user_id": user_id,
                    "fournisseur_id": fournisseur_id,
                    "numero": invoice_info["numero"],
                    "date": invoice_info["date"].isoformat(),
                    "nom_fichier": invoice_info["filename"],
                    "total_ht": invoice_info["total_ht"],
                    "tva_amount": invoice_info["tva"],
                    "total_ttc": invoice_info["total_ttc"],
                }
            )
            .execute()
        )
        invoice_id = facture.data[0]["id"]

    # --- Upload PDF to Supabase Storage ---
    bucket_name = "invoices"
    invoice_name = f"{invoice_id}_{invoice_info['filename']}"
    object_name = f"{user_id}/{invoice_name}"

    supabase.storage.from_(bucket_name).upload(
        path=object_name,
        file=uploaded_file.getvalue(),
        file_options={"content-type": "application/pdf"},
    )

    # --- Save articles ---
    for _, row in articles_df.iterrows():
        # Categories
        res = (
            supabase.table("categories")
            .select("id")
            .eq("user_id", user_id)
            .eq("nom", row.get("Catégorie"))
            .execute()
        )
        if res.data:
            categorie_id = res.data[0]["id"]
        else:
            categorie = (
                supabase.table("categories")
                .insert({"user_id": user_id, "nom": row.get("Catégorie")})
                .execute()
            )
            categorie_id = categorie.data[0]["id"]

        # Marques
        res = (
            supabase.table("marques")
            .select("id")
            .eq("user_id", user_id)
            .eq("nom", row.get("Marque"))
            .execute()
        )
        if res.data:
            marque_id = res.data[0]["id"]
        else:
            marque = (
                supabase.table("marques")
                .insert({"user_id": user_id, "nom": row.get("Marque")})
                .execute()
            )
            marque_id = marque.data[0]["id"]

        # Produits
        res = (
            supabase.table("produits")
            .select("id")
            .eq("user_id", user_id)
            .eq("reference", row.get("Reference"))
            .eq("fournisseur_id", fournisseur_id)
            .execute()
        )
        if res.data:
            produit_id = res.data[0]["id"]
        else:
            produit = (
                supabase.table("produits")
                .insert(
                    {
                        "user_id": user_id,
                        "designation": row.get("Désignation"),
                        "reference": row.get("Reference"),
                        "fournisseur_id": fournisseur_id,
                        "categorie_id": categorie_id,
                        "marque_id": marque_id,
                    }
                )
                .execute()
            )
            produit_id = produit.data[0]["id"]

        # Lignes facture
        res = (
            supabase.table("lignes_facture")
            .select("id")
            .eq("user_id", user_id)
            .eq("facture_id", invoice_id)
            .eq("produit_id", produit_id)
            .execute()
        )
        if not res.data:
            supabase.table("lignes_facture").insert(
                {
                    "user_id": user_id,
                    "facture_id": invoice_id,
                    "produit_id": produit_id,
                    "prix_unitaire": row.get("Prix Unitaire"),
                    "collisage": row.get("Packaging"),
                    "quantite": row.get("Quantité"),
                    "montant": row.get("Total"),
                }
            ).execute()


def sidebar() -> None:
    """
    Render sidebar interface for invoice extraction workflow.

    This function manages the complete extraction process:
    1. File upload
    2. First article confirmation for extraction optimization
    3. Invoice data extraction and processing
    4. Data review and correction
    5. Database storage
    """
    # Sidebar width
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"][aria-expanded="true"] {
            min-width: 50% !important;
            max-width: 70% !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader("📥", type=["pdf"], label_visibility="hidden")

    # === Step 1: Upload & Confirm first article ===
    if uploaded_file and not st.session_state.get("extraction_done", False):
        st.session_state.update(
            {"uploaded_file": uploaded_file, "pdf_name": uploaded_file.name}
        )

        st.divider()
        st.text(
            "Veuillez entrer le premier article",
            help="Les données seront utilisées pour optimiser l'extraction.",
        )

        df = pd.DataFrame(columns=ARTICLES_COLUMNS_CONFIG.keys())
        confirmation_df = st.data_editor(
            st.session_state.get("autofill_df", df),
            num_rows="dynamic",
            use_container_width=True,
            column_config=ARTICLES_COLUMNS_CONFIG,
            key="article_editor",
            on_change=autofill_rows,
            args=(ARTICLES_COLUMNS_CONFIG.keys(),),
            hide_index=True,
        )

        row_filled = (
            not confirmation_df.empty and not confirmation_df.iloc[0].isnull().any()
        )

        if st.button(
            "Lancement de l'extraction",
            disabled=not row_filled,
            type="primary",
            use_container_width=True,
        ):
            with st.spinner("Extraction des données en cours...", show_time=True):
                structured_data, data_articles, annotated_pdf = extract_invoice(
                    uploaded_file, confirmation_df
                )
                if structured_data:
                    st.session_state.update(
                        {
                            "structured_data": structured_data,
                            "data_articles": data_articles,
                            "annotated_pdf": annotated_pdf,
                            "extraction_done": True,
                        }
                    )
                    st.rerun()

    # === Step 2: Show results & Save ===
    elif st.session_state.get("extraction_done", False):
        st.divider()
        # --- Invoice Info ---
        sd = st.session_state["structured_data"]
        left, right = st.columns(2)
        with left:
            invoice_name = st.text_input(
                "Nom de la facture", value=st.session_state["pdf_name"]
            )
            fournisseur_nom = st.text_input(
                "Fournisseur",
                value=sd.get("Information fournisseur", {}).get("nom", ""),
            )
        with right:
            numero = st.text_input(
                "Numéro de facture", value=sd.get("Numéro de facture", "")
            )
            try:
                invoice_date = pd.to_datetime(
                    sd.get("Date facture", ""), dayfirst=True
                ).date()
            except Exception:
                invoice_date = pd.to_datetime("today").date()
            invoice_date = st.date_input("Date de la facture", value=invoice_date)

        fournisseur_adresse = st.text_area(
            "Adresse", value=sd.get("Information fournisseur", {}).get("adresse", "")
        )

        # --- Articles ---
        articles_df = st.data_editor(
            st.session_state["data_articles"],
            num_rows="dynamic",
            use_container_width=True,
            key="save_data_editor",
            column_config=ARTICLES_COLUMNS_CONFIG,
            height=250,
        )

        # --- Totaux ---
        nb_colis, ht_col, tva_col, ttc_col = st.columns(4)
        with nb_colis:
            nb = st.number_input(
                "Nombre de colis", value=int(sd.get("Nombre de colis", 1)), min_value=1
            )
        with ht_col:
            ht = st.number_input(
                "Total HT",
                value=float(sd.get("Total", {}).get("total_ht", 0.0)),
                format="%.2f",
            )
        with tva_col:
            tva = st.number_input(
                "TVA", value=float(sd.get("Total", {}).get("tva", 0.0)), format="%.2f"
            )
        with ttc_col:
            ttc = st.number_input(
                "Total TTC",
                value=float(sd.get("Total", {}).get("total_ttc", 0.0)),
                format="%.2f",
            )

        if "Quantité" in articles_df.columns and nb != articles_df["Quantité"].sum():
            st.warning(
                f"⚠️ Nombre de colis ({nb}) différent de la somme des quantités ({int(articles_df['Quantité'].sum())})."
            )

        if st.button("Enregistrer les données", type="primary"):
            with st.spinner("Enregistrement en cours..."):
                save_invoice_supabase_storage(
                    st.session_state["uploaded_file"],
                    {
                        "fournisseur_nom": fournisseur_nom,
                        "adresse": fournisseur_adresse,
                        "numero": numero,
                        "date": invoice_date,
                        "filename": invoice_name,
                        "total_ht": ht,
                        "tva": tva,
                        "total_ttc": ttc,
                    },
                    articles_df,
                )
                st.session_state["extraction_done"] = False
            st.success("✅ Données enregistrées !")


def main_content() -> None:
    """
    Render the main content area showing the PDF viewer.

    Displays either the original uploaded PDF or the annotated version
    with extraction highlights if processing is complete.
    """

    st.markdown(
        displayPDF(
            "https://oglvvptgegpwugiuclyx.supabase.co/storage/v1/object/public/test/dummy_invoice.pdf"
        ),
        unsafe_allow_html=True,
    )
