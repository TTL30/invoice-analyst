"""
Invoice and Product Management Module

Provides functionality for managing invoices and products with filtering,
viewing, editing, and batch operations.
"""

import io
import zipfile
import requests
import datetime
from typing import Optional, Tuple
import streamlit as st
import pandas as pd


@st.dialog("Visualisation de la facture", width="large")
def view_pdf_dialog() -> None:
    """
    Display PDF viewer dialog for invoice visualization.

    Renders the PDF file in an embedded iframe viewer.
    """
    pdf_url = st.session_state.get("pdf_to_view")
    if pdf_url:
        # Display PDF from URL in an iframe
        st.markdown(
            f'<iframe src="{pdf_url}" width="100%" height="800px" style="border:none;"></iframe>',
            unsafe_allow_html=True,
        )
    else:
        st.warning("Fichier PDF introuvable.")


@st.dialog("Confirmation de suppression")
def delete_confirmation_dialog() -> None:
    rows_data = st.session_state.get("rows_to_delete", pd.DataFrame())
    if rows_data.empty:
        st.warning("Aucune facture sélectionnée.")
        return

    invoice_numbers = rows_data.get("Numero", []).tolist()
    invoice_ids = rows_data.get("id", []).tolist()
    invoice_names = rows_data.get("Fichier", []).tolist()
    fournisseur_ids = rows_data.get("fournisseur_id", []).tolist()

    st.warning(
        "Voulez-vous vraiment supprimer les factures suivantes ?\n\n"
        + "\n".join(f"- {num}" for num in invoice_numbers)
    )

    cancel_col, conf_col = st.columns([1, 1])
    with conf_col:
        confirm = st.button(
            "✅ Confirmer", key="confirm_delete_facture", type="primary"
        )
    with cancel_col:
        cancel = st.button("❌ Annuler", key="cancel_delete_facture")

    if confirm:
        ids = rows_data.get("id", []).tolist()

        # Delete associated files
        for invoice_id, nom_fichier in zip(invoice_ids, invoice_names):
            file_path = f"{st.session_state['user']}/{invoice_id}_{nom_fichier}"
            try:
                st.session_state["supabase"].storage.from_("invoices").remove(
                    [file_path]
                )
            except Exception as e:
                st.warning(f"Erreur suppression fichier {file_path}: {e}")

        # Delete from DB
        if ids:
            st.session_state["supabase"].table("lignes_facture").delete().in_(
                "facture_id", ids
            ).execute()
            st.session_state["supabase"].table("factures").delete().in_(
                "id", ids
            ).execute()

        st.success("Factures supprimées.")
        st.session_state.show_delete_modal = False
        st.rerun()

    if cancel:
        st.session_state.show_delete_modal = False
        st.rerun()


def display_factures(
    fournisseur_id: Optional[int],
    date_range: Optional[Tuple[datetime.date, datetime.date]],
) -> None:
    """
    Display and manage invoices with filtering and batch operations.

    Features:
    - Filter by supplier and date range
    - View individual PDF files
    - Download selected invoices as ZIP
    - Delete invoices with confirmation

    Args:
        fournisseur_id (int): Supplier ID filter (None for all)
        date_range (tuple): Date range filter (start_date, end_date)
    """
    factures = st.session_state["supabase"].table("factures").select("*")
    if fournisseur_id:
        factures = factures.eq("fournisseur_id", fournisseur_id)
    if date_range:
        factures = factures.gte("date", str(date_range[0])).lte(
            "date", str(date_range[1])
        )
    factures = factures.execute().data
    df = pd.DataFrame(factures)

    if df.empty:
        st.info("Aucune facture trouvée.")
        return

    df["fournisseur_name"] = df["fournisseur_id"].apply(
        lambda x: next(
            (
                f["nom"]
                for f in st.session_state.get("fournisseurs", [])
                if f["id"] == x
            ),
            "Inconnu",
        )
    )

    df["selected"] = False

    display_df = df.rename(
        columns={
            "nom_fichier": "Fichier",
            "numero": "Numero",
            "fournisseur_name": "Fournisseur",
            "date": "Date",
            "total_ht": "Total HT",
            "tva_amount": "TVA",
            "total_ttc": "Total TTC",
        }
    )

    # Table
    left_col, right_col = st.columns([15, 1.5])
    with left_col:
        selected = st.data_editor(
            display_df,
            use_container_width=True,
            hide_index=True,
            key="facture_editor",
            num_rows="fixed",
            disabled=("Fichier", "Numero", "Fournisseur"),
            column_order=[
                "selected",
                "Fichier",
                "Numero",
                "Fournisseur",
                "Date",
                "Total HT",
                "TVA",
                "Total TTC",
            ],
            column_config={
                "selected": st.column_config.CheckboxColumn("", default=False)
            },
        )

    selected_rows = (
        selected.index[selected["selected"]].tolist() if "selected" in selected else []
    )

    # Actions
    with right_col:
        if not selected_rows:
            return

        row_data = display_df.iloc[selected_rows]
        # View PDF (only one selected)
        if len(selected_rows) == 1 and st.button("👁️"):
            invoice_id = row_data.iloc[0]["id"]
            nom_fichier = row_data.iloc[0]["Fichier"]
            invoice_name = f"{invoice_id}_{nom_fichier}"
            object_name = f"{st.session_state['user']}/{invoice_name}"
            url_data = (
                st.session_state["supabase"]
                .storage.from_("invoices")
                .create_signed_url(f"{object_name}", 60 * 60)
            )
            url = url_data.get("signedURL") or url_data.get("url")
            st.session_state["pdf_to_view"] = url
            view_pdf_dialog()

        # Download ZIP
        if st.download_button(
            "⬇️",
            data=build_zip(row_data),
            file_name="factures_selectionnees.zip",
            mime="application/zip",
        ):
            pass

        # Delete
        if st.button("🗑️"):
            st.session_state.rows_to_delete = row_data
            st.session_state.show_delete_modal = True

        if st.session_state.get("show_delete_modal"):
            delete_confirmation_dialog()


def build_zip(rows: pd.DataFrame) -> io.BytesIO:
    """Return a BytesIO zip of selected factures (fetching PDFs from Supabase Storage URLs)."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zipf:
        for _, row in rows.iterrows():
            invoice_id = row["id"] if "id" in row else row.get("id")
            nom_fichier = row["Fichier"] if "Fichier" in row else row.get("Fichier")
            if not invoice_id or not nom_fichier:
                continue
            object_name = f"{st.session_state['user']}/{invoice_id}_{nom_fichier}"
            # Get signed URL from Supabase
            url_data = (
                st.session_state["supabase"]
                .storage.from_("invoices")
                .create_signed_url(object_name, 60 * 5)
            )
            url = url_data.get("signedURL") or url_data.get("url")
            if url:
                try:
                    response = requests.get(url)
                    if response.status_code == 200:
                        zipf.writestr(nom_fichier, response.content)
                except Exception as e:
                    st.warning(f"Erreur lors du téléchargement du PDF: {e}")
    zip_buffer.seek(0)
    return zip_buffer


def display_produits(
    fournisseur_id: Optional[int], marque_id: Optional[int], category_id: Optional[int]
) -> Optional[pd.DataFrame]:
    """
    Display and edit products with comprehensive filtering.

    Args:
        fournisseur_id (int): Supplier ID filter
        marque_id (int): Brand ID filter
        category_id (int): Category ID filter

    Returns:
        pandas.DataFrame: Filtered and formatted product data
    """
    produits = st.session_state["supabase"].table("produits").select("*")
    if fournisseur_id:
        produits = produits.eq("fournisseur_id", fournisseur_id)
    if marque_id:
        produits = produits.eq("marque_id", marque_id)
    if category_id:
        produits = produits.eq("categorie_id", category_id)
    produits = produits.execute().data
    df = pd.DataFrame(produits)

    if df.empty:
        st.info("Aucun produit trouvé.")
        return

    # Replace IDs with names for display
    df["fournisseur_name"] = df["fournisseur_id"].apply(
        lambda x: next(
            (
                f["nom"]
                for f in st.session_state.get("fournisseurs", [])
                if f["id"] == x
            ),
            "Inconnu",
        )
    )
    df["marque_name"] = df["marque_id"].apply(
        lambda x: next(
            (m["nom"] for m in st.session_state.get("marques", []) if m["id"] == x),
            "Inconnu",
        )
    )
    df["categorie_name"] = df["categorie_id"].apply(
        lambda x: next(
            (c["nom"] for c in st.session_state.get("categories", []) if c["id"] == x),
            "Inconnu",
        )
    )

    # Prepare display dataframe
    display_df = df.rename(
        columns={
            "reference": "Référence",
            "designation": "Désignation",
            "fournisseur_name": "Fournisseur",
            "marque_name": "Marque",
            "categorie_name": "Catégorie",
        }
    )
    return display_df


def save_products_changes(selected_df: pd.DataFrame, original_ids: set) -> None:
    """Apply edits from produits data_editor into the DB."""
    # IDs remaining after edit
    edited_ids = set(selected_df["id"]) if "id" in selected_df else set()
    # IDs that were deleted
    deleted_ids = original_ids - edited_ids

    # Delete removed products from DB
    if deleted_ids:
        st.session_state["supabase"].table("produits").delete().in_(
            "id", list(deleted_ids)
        ).execute()
        st.session_state["supabase"].table("lignes_facture").delete().in_(
            "produit_id", list(deleted_ids)
        ).execute()

    for _, row in selected_df.iterrows():
        produit_id = row.get("id", None)

        # Resolve foreign keys
        fournisseur_id = next(
            (
                f["id"]
                for f in st.session_state["fournisseurs"]
                if f["nom"] == row["Fournisseur"]
            ),
            None,
        )
        marque_id = next(
            (m["id"] for m in st.session_state["marques"] if m["nom"] == row["Marque"]),
            None,
        )
        categorie_id = next(
            (
                c["id"]
                for c in st.session_state["categories"]
                if c["nom"] == row["Catégorie"]
            ),
            None,
        )

        # If marque doesn't exist → create
        if not marque_id and row["Marque"]:
            marque_id = next(
                (
                    m["id"]
                    for m in st.session_state["marques"]
                    if m["nom"] == row["Marque"]
                ),
                None,
            )

        produit_data = {
            "reference": row["Référence"],
            "designation": row["Désignation"],
            "fournisseur_id": fournisseur_id,
            "marque_id": marque_id,
            "categorie_id": categorie_id,
        }

        if pd.notna(produit_id):  # Update existing
            st.session_state["supabase"].table("produits").update(produit_data).eq(
                "id", produit_id
            ).execute()
        else:  # Insert new
            st.session_state["supabase"].table("produits").insert(
                produit_data
            ).execute()

    st.success("Produits mis à jour avec succès ✅")
    st.rerun()


def run() -> None:
    """
    Main management interface for invoices and products.

    Provides a unified interface for:
    - Switching between invoice and product management
    - Applying filters (supplier, date, brand, category)
    - Performing CRUD operations on data
    """
    # Filters
    filter_type, _, f2, f3, f4 = st.columns([1, 3, 1, 1, 1])
    with filter_type:
        st.selectbox("", ["Factures", "Produits"], key="gestion_filter1")

    fournisseur_id = marque_id = category_id = None
    fournisseur_name = marque_name = category_name = None
    date_range = None

    with f3:
        fournisseur_options = ["Tous"] + [
            f["nom"] for f in st.session_state.get("fournisseurs", [])
        ]
        fournisseur_name = st.selectbox(
            "Fournisseur", fournisseur_options, key="gestion_filter2"
        )
        fournisseur_id = next(
            (
                f["id"]
                for f in st.session_state.get("fournisseurs", [])
                if f["nom"] == fournisseur_name
            ),
            None,
        )

    with f4:
        if st.session_state.get("gestion_filter1") == "Factures":
            today = datetime.date.today()
            one_year_ago = today.replace(year=today.year - 1)
            date_range = st.date_input(
                "Date", value=(one_year_ago, today), key="gestion_filter3"
            )
        else:
            marque_options = ["Toutes"] + [
                m["nom"] for m in st.session_state.get("marques", [])
            ]
            marque_name = st.selectbox("Marque", marque_options, key="gestion_filter4")
            marque_id = next(
                (
                    m["id"]
                    for m in st.session_state.get("marques", [])
                    if m["nom"] == marque_name
                ),
                None,
            )

    with f2:
        if st.session_state.get("gestion_filter1") == "Produits":
            category_options = ["Toutes"] + [
                c["nom"] for c in st.session_state.get("categories", [])
            ]
            category_name = st.selectbox(
                "Catégorie", category_options, key="gestion_filter5"
            )
            category_id = next(
                (
                    c["id"]
                    for c in st.session_state.get("categories", [])
                    if c["nom"] == category_name
                ),
                None,
            )

    st.markdown("---")

    if st.session_state.get("gestion_filter1") == "Factures":
        display_factures(fournisseur_id, date_range)
    else:
        display_df = display_produits(fournisseur_id, marque_id, category_id)
        if display_df is None:
            return
        original_ids = set(display_df["id"]) if "id" in display_df else set()
        selected = st.data_editor(
            display_df,
            height=600,
            use_container_width=True,
            hide_index=True,
            key="produit_editor",
            num_rows="dynamic",
            column_order=[
                "Référence",
                "Désignation",
                "Fournisseur",
                "Marque",
                "Catégorie",
            ],
            column_config={
                "Fournisseur": st.column_config.SelectboxColumn(
                    "Fournisseur",
                    options=[f["nom"] for f in st.session_state["fournisseurs"]],
                ),
                "Marque": st.column_config.TextColumn("Marque"),
                "Catégorie": st.column_config.SelectboxColumn(
                    "Catégorie",
                    options=[c["nom"] for c in st.session_state["categories"]],
                ),
            },
        )

        if st.button("💾 Enregistrer les modifications", key="save_products"):
            save_products_changes(selected, original_ids)
