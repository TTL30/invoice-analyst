import os
import io
import zipfile
import datetime
import streamlit as st
import pandas as pd
from invoice_analyst.constants import SAVED_INVOICES_DIR
from invoice_analyst.utils import (
    displayPDF,
    get_unique_id_from_invoice_numero,
    get_id_from_name,
)


@st.dialog("Visualisation de la facture", width="large")
def view_pdf_dialog():
    file_path = st.session_state.get("pdf_to_view")
    if file_path and os.path.exists(file_path):
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        uploaded_file = io.BytesIO(file_bytes)
        st.markdown(displayPDF(uploaded_file), unsafe_allow_html=True)
    else:
        st.warning("Fichier PDF introuvable.")


@st.dialog("Confirmation de suppression")
def delete_confirmation_dialog(db_manager):
    rows_data = st.session_state.get("rows_to_delete", pd.DataFrame())
    if rows_data.empty:
        st.warning("Aucune facture sélectionnée.")
        return

    invoice_numbers = rows_data.get("Numero", []).tolist()
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
        for fournisseur_id, numero in zip(fournisseur_ids, invoice_numbers):
            pdf_id = get_unique_id_from_invoice_numero(numero, fournisseur_id)
            file_path = os.path.join(SAVED_INVOICES_DIR, f"{pdf_id}.pdf")
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    st.warning(f"Erreur suppression fichier {file_path}: {e}")

        # Delete from DB
        if ids:
            placeholders = ",".join("?" for _ in ids)
            db_manager.delete_rows(
                "lignes_facture",
                where=f"facture_id IN ({placeholders})",
                params=tuple(ids),
            )
            db_manager.delete_rows(
                "factures", where=f"id IN ({placeholders})", params=tuple(ids)
            )

        st.success("Factures supprimées.")
        st.session_state.show_delete_modal = False
        st.rerun()

    if cancel:
        st.session_state.show_delete_modal = False
        st.rerun()


def display_factures(db_manager, fournisseur_id, fournisseur_name, date_range):
    where_clause, params = [], []

    if fournisseur_id:
        where_clause.append("fournisseur_id = ?")
        params.append(fournisseur_id)

    if date_range:
        where_clause.append("date BETWEEN ? AND ?")
        params.extend([date_range[0], date_range[1]])

    factures = db_manager.get_rows(
        "factures",
        where=" AND ".join(where_clause) if where_clause else None,
        params=tuple(params),
    )
    df = pd.DataFrame(factures, columns=db_manager.get_column_names("factures"))

    if df.empty:
        st.info("Aucune facture trouvée.")
        return

    df["fournisseur_name"] = df["fournisseur_id"].apply(
        lambda x: st.session_state.get("fournisseurs", {}).get(x, "Inconnu")
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
            fournisseur_id = row_data.iloc[0]["fournisseur_id"]
            numero = row_data.iloc[0]["Numero"]
            pdf_id = get_unique_id_from_invoice_numero(numero, fournisseur_id)
            file_path = os.path.join(SAVED_INVOICES_DIR, f"{pdf_id}.pdf")
            st.session_state["pdf_to_view"] = file_path
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
            delete_confirmation_dialog(db_manager)


def build_zip(rows):
    """Return a BytesIO zip of selected factures."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zipf:
        for _, row in rows.iterrows():
            pdf_id = get_unique_id_from_invoice_numero(
                row["Numero"], row["fournisseur_id"]
            )
            file_path = os.path.join(SAVED_INVOICES_DIR, f"{pdf_id}.pdf")
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    zipf.writestr(f"{pdf_id}.pdf", f.read())
    zip_buffer.seek(0)
    return zip_buffer


def display_produits(db_manager, fournisseur_id, marque_id, category_id):
    """Display and edit products with filters."""

    # Build where clause
    where_clause, params = [], []
    if fournisseur_id:
        where_clause.append("fournisseur_id = ?")
        params.append(fournisseur_id)
    if marque_id:
        where_clause.append("marque_id = ?")
        params.append(marque_id)
    if category_id:
        where_clause.append("categorie_id = ?")
        params.append(category_id)

    produits = db_manager.get_rows(
        "produits",
        where=" AND ".join(where_clause) if where_clause else None,
        params=tuple(params),
    )
    df = pd.DataFrame(produits, columns=db_manager.get_column_names("produits"))

    if df.empty:
        st.info("Aucun produit trouvé.")
        return

    # Replace IDs with names for display
    df["fournisseur_name"] = df["fournisseur_id"].apply(
        lambda x: st.session_state.get("fournisseurs", {}).get(x, "Inconnu")
    )
    df["marque_name"] = df["marque_id"].apply(
        lambda x: st.session_state.get("marques", {}).get(x, "Inconnu")
    )
    df["categorie_name"] = df["categorie_id"].apply(
        lambda x: st.session_state.get("categories", {}).get(x, "Inconnu")
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


def save_products_changes(db_manager, selected_df: pd.DataFrame):
    """Apply edits from produits data_editor into the DB."""
    for _, row in selected_df.iterrows():
        produit_id = row.get("id", None)

        # Resolve foreign keys
        fournisseur_id = get_id_from_name(
            st.session_state.get("fournisseurs", {}), row["Fournisseur"]
        )
        marque_id = get_id_from_name(st.session_state.get("marques", {}), row["Marque"])
        categorie_id = get_id_from_name(
            st.session_state.get("categories", {}), row["Catégorie"]
        )

        # If marque doesn't exist → create
        if not marque_id and row["Marque"]:
            marque_id = db_manager.get_or_create_row("marques", {"nom": row["Marque"]})

        produit_data = {
            "reference": row["Référence"],
            "designation": row["Désignation"],
            "fournisseur_id": fournisseur_id,
            "marque_id": marque_id,
            "categorie_id": categorie_id,
        }

        if pd.notna(produit_id):  # Update existing
            db_manager.update_row("produits", produit_id, produit_data)
        else:  # Insert new
            db_manager.add_row(
                "produits",
                list(produit_data.keys()),
                list(produit_data.values()),
            )

    st.success("Produits mis à jour avec succès ✅")
    st.rerun()


def gestion(db_manager):
    """Main dashboard for managing factures or produits."""
    # Filters
    filter_type, _, f2, f3, f4 = st.columns([1, 3, 1, 1, 1])
    with filter_type:
        st.selectbox("", ["Factures", "Produits"], key="gestion_filter1")

    fournisseur_id = marque_id = category_id = None
    fournisseur_name = marque_name = category_name = None
    date_range = None

    with f3:
        fournisseur_options = [""] + list(
            st.session_state.get("fournisseurs", {}).values()
        )
        fournisseur_name = st.selectbox(
            "Fournisseur", fournisseur_options, key="gestion_filter2"
        )
        fournisseur_id = get_id_from_name(
            st.session_state.get("fournisseurs", {}), fournisseur_name
        )

    with f4:
        if st.session_state.get("gestion_filter1") == "Factures":
            today = datetime.date.today()
            one_year_ago = today.replace(year=today.year - 1)
            date_range = st.date_input(
                "Date", value=(one_year_ago, today), key="gestion_filter3"
            )
        else:
            marque_options = [""] + list(st.session_state.get("marques", {}).values())
            marque_name = st.selectbox("Marque", marque_options, key="gestion_filter4")
            marque_id = get_id_from_name(
                st.session_state.get("marques", {}), marque_name
            )

    with f2:
        if st.session_state.get("gestion_filter1") == "Produits":
            category_options = [""] + list(
                st.session_state.get("categories", {}).values()
            )
            category_name = st.selectbox(
                "Catégorie", category_options, key="gestion_filter5"
            )
            category_id = get_id_from_name(
                st.session_state.get("categories", {}), category_name
            )

    st.markdown("---")

    if st.session_state.get("gestion_filter1") == "Factures":
        display_factures(db_manager, fournisseur_id, fournisseur_name, date_range)
    else:
        display_df = display_produits(
            db_manager, fournisseur_id, marque_id, category_id
        )
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
                    options=st.session_state.get("fournisseurs", {}).values(),
                ),
                "Marque": st.column_config.TextColumn("Marque"),
                "Catégorie": st.column_config.SelectboxColumn(
                    "Catégorie",
                    options=[c[1] for c in db_manager.get_rows("categories")],
                ),
            },
        )

        if st.button("💾 Enregistrer les modifications", key="save_products"):
            save_products_changes(db_manager, selected)
