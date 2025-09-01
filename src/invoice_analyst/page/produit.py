import datetime
import pandas as pd
import streamlit as st
import plotly.express as px
from invoice_analyst.utils import get_id_from_name
from invoice_analyst.components.charts import (
    make_time_series_fig,
    make_pie_fig,
    make_bubble_fig,
)


def run():
    supabase = st.session_state["supabase"]

    # ================== 🎨 CSS ==================
    st.markdown(
        """
        <style>
        .card {
            background-color: white;
            border-radius: 16px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            padding: 20px;
            margin-bottom: 20px;
        }
        [data-testid="stDataFrame"] {
            background-color: white !important;
            padding: 8px;
            border-radius: 18px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.10);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ================== 📅 Filtres ==================
    blank, filter2 = st.columns([5, 1])
    with filter2:
        today = datetime.date.today()
        one_year_ago = today.replace(year=today.year - 1)
        date_range = st.date_input(
            "Date", value=(one_year_ago, today), key="gestion_filter5"
        )

    col1, col2 = st.columns([3, 1], gap="medium")

    # ================== 🔎 Filtres Fournisseur / Catégorie ==================
    with col2:
        fournisseur_options = ["Tous"] + [
            f["nom"] for f in st.session_state.get("fournisseurs", [])
        ]
        fournisseur_name = st.selectbox(
            "Fournisseur", fournisseur_options, key="gestion_filter7"
        )
        fournisseur_id = (
            next(
                (
                    f["id"]
                    for f in st.session_state.get("fournisseurs", [])
                    if f["nom"] == fournisseur_name
                ),
                None,
            )
            if fournisseur_name != "Tous"
            else None
        )

        categorie_options = ["Toutes"] + [
            c["nom"] for c in st.session_state.get("categories", [])
        ]
        categorie_name = st.selectbox(
            "Catégorie", categorie_options, key="gestion_filter6"
        )
        categorie_id = (
            next(
                (
                    c["id"]
                    for c in st.session_state.get("categories", [])
                    if c["nom"] == categorie_name
                ),
                None,
            )
            if categorie_name != "Toutes"
            else None
        )

        # ================== Récupération Produits ==================
        query = supabase.table("produits").select("*")
        if fournisseur_id:
            query = query.eq("fournisseur_id", fournisseur_id)
        if categorie_id:
            query = query.eq("categorie_id", categorie_id)

        data = query.execute()
        df_produits = pd.DataFrame(data.data)
        if df_produits.empty:
            st.info("Aucun produit trouvé.")
            return

        # Map names
        df_produits["fournisseur_name"] = df_produits["fournisseur_id"].apply(
            lambda x: next(
                (
                    f["nom"]
                    for f in st.session_state.get("fournisseurs", [])
                    if f["id"] == x
                ),
                "Inconnu",
            )
        )
        df_produits["marque_name"] = df_produits["marque_id"].apply(
            lambda x: next(
                (m["nom"] for m in st.session_state.get("marques", []) if m["id"] == x),
                "Inconnu",
            )
        )
        df_produits["categorie_name"] = df_produits["categorie_id"].apply(
            lambda x: next(
                (
                    c["nom"]
                    for c in st.session_state.get("categories", [])
                    if c["id"] == x
                ),
                "Inconnu",
            )
        )

        # Display table with checkbox
        display_df = df_produits.rename(
            columns={
                "reference": "Référence",
                "designation": "Désignation",
                "fournisseur_name": "Fournisseur",
                "marque_name": "Marque",
                "categorie_name": "Catégorie",
            }
        )
        display_df["selected"] = False

        selected = st.data_editor(
            display_df,
            use_container_width=True,
            hide_index=True,
            key="produit_editor",
            height=350,
            column_order=[
                "selected",
                "Référence",
                "Désignation",
                "Fournisseur",
                "Marque",
                "Catégorie",
            ],
            column_config={
                "selected": st.column_config.CheckboxColumn("", default=False)
            },
        )

        selected_rows = (
            selected.index[selected["selected"]].tolist()
            if "selected" in selected
            else []
        )

    # ================== 📊 Graphiques Produits ==================
    with col1:
        df_products_charts = pd.DataFrame()
        if selected_rows:
            selected_ids = df_produits.iloc[selected_rows]["id"].tolist()
            placeholders = ",".join(map(str, selected_ids))

            # Fetch lignes_facture joined with factures and produits from Supabase
            data = supabase.rpc(
                "get_lignes_facture_by_produit_ids", {"ids": selected_ids}
            ).execute()
            df_products_charts = pd.DataFrame(data.data)
            if not df_products_charts.empty:
                df_products_charts["date"] = pd.to_datetime(df_products_charts["date"])
                df_products_charts = df_products_charts[
                    (df_products_charts["date"] >= pd.to_datetime(date_range[0]))
                    & (df_products_charts["date"] <= pd.to_datetime(date_range[1]))
                ]
                df_products_charts["ref_designation"] = (
                    df_products_charts["reference"].astype(str)
                    + " - "
                    + df_products_charts["designation"].astype(str)
                )
                df_products_charts["fournisseur_name"] = df_products_charts[
                    "fournisseur_id"
                ].apply(
                    lambda x: next(
                        (
                            f["nom"]
                            for f in st.session_state.get("fournisseurs", [])
                            if f["id"] == x
                        ),
                        "Inconnu",
                    )
                )
                df_products_charts["marque_name"] = df_products_charts[
                    "marque_id"
                ].apply(
                    lambda x: next(
                        (
                            m["nom"]
                            for m in st.session_state.get("marques", [])
                            if m["id"] == x
                        ),
                        "Inconnu",
                    )
                )
                df_products_charts["produit_info"] = (
                    df_products_charts["designation"].astype(str)
                    + " - "
                    + df_products_charts["fournisseur_name"].astype(str)
                    + " - "
                    + df_products_charts["marque_name"].astype(str)
                    + "<br>Qté: "
                    + df_products_charts["quantite"].astype(str)
                    + "<br>PU: "
                    + df_products_charts["prix_unitaire"].astype(str)
                    + " €"
                )

        fig = make_time_series_fig(
            df_products_charts,
            x="date",
            y="prix_unitaire",
            name="ref_designation",
            customdata=df_products_charts.get("produit_info", []),
            title="Évolution du Prix Unitaire (Produits Sélectionnés)",
            color_sequence=px.colors.qualitative.Set2,
            height=550,
        )
        st.plotly_chart(fig, use_container_width=True, theme="streamlit", height=550)

    st.markdown("---")
    col1, col2 = st.columns(2, gap="medium")

    with col1:
        # Pie chart categories
        data = supabase.table("produits").select("*").execute()
        df_all_products = pd.DataFrame(data.data)
        df_all_products["categorie_name"] = df_all_products["categorie_id"].apply(
            lambda x: next(
                (
                    c["nom"]
                    for c in st.session_state.get("categories", [])
                    if c["id"] == x
                ),
                "Inconnu",
            )
        )
        category_summary = (
            df_all_products.groupby("categorie_name").size().reset_index(name="count")
        )

        fig = make_pie_fig(
            category_summary,
            names="categorie_name",
            values="count",
            title="Répartition des Dépenses par Catégorie",
            color_sequence=px.colors.qualitative.Pastel,
            height=450,
        )
        st.plotly_chart(fig, use_container_width=True, theme="streamlit", height=450)

    with col2:
        # Bubble chart summary
        def get_product_summary(supabase, fournisseur_id, start_date, end_date):
            query = supabase.table("produits").select("*").execute()
            df = pd.DataFrame(query.data)
            if fournisseur_id:
                df = df[df["fournisseur_id"] == fournisseur_id]

            # Fetch lignes_facture within date range
            data = supabase.rpc(
                "get_lignes_facture_by_produit_ids", {"ids": df["id"].tolist()}
            ).execute()
            df_lines = pd.DataFrame(data.data)
            if df_lines.empty:
                return pd.DataFrame(
                    columns=[
                        "id",
                        "reference",
                        "designation",
                        "total_quantity",
                        "total_amount",
                        "avg_unit_price",
                    ]
                )
            df_lines["date"] = pd.to_datetime(df_lines["date"])
            df_lines = df_lines[
                (df_lines["date"] >= pd.to_datetime(start_date))
                & (df_lines["date"] <= pd.to_datetime(end_date))
            ]

            df_summary = (
                df_lines.groupby(["produit_id", "reference", "designation"])
                .agg(
                    total_quantity=pd.NamedAgg(column="quantite", aggfunc="sum"),
                    total_amount=pd.NamedAgg(column="montant", aggfunc="sum"),
                    avg_unit_price=pd.NamedAgg(column="prix_unitaire", aggfunc="mean"),
                )
                .reset_index()
            )

            return df_summary

        product_summary = get_product_summary(
            supabase, fournisseur_id, date_range[0], date_range[1]
        )

        fig = make_bubble_fig(
            product_summary,
            x="total_quantity",
            y="total_amount",
            size="avg_unit_price",
            hover_name="designation",
            title="Classement des Produits (Quantité vs Montant Dépensé)",
            color_sequence=px.colors.qualitative.Vivid,
            height=450,
        )
        st.plotly_chart(fig, use_container_width=True, theme="streamlit", height=450)
