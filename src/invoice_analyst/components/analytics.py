import datetime
import streamlit as st
import pandas as pd
from invoice_analyst.utils import get_id_from_name
import plotly.express as px
from invoice_analyst.components.gestion import display_produits
import plotly.graph_objects as go


def get_total_ttc(db_manager, fournisseur_id, start_date, end_date):
    where = []
    params = []
    if fournisseur_id:
        where.append("fournisseur_id = ?")
        params.append(fournisseur_id)
    if start_date and end_date:
        where.append("date BETWEEN ? AND ?")
        params.extend([start_date, end_date])
    where_clause = " AND ".join(where) if where else None
    factures = db_manager.get_rows("factures", where=where_clause, params=tuple(params))
    df = pd.DataFrame(factures, columns=db_manager.get_column_names("factures"))
    return df["total_ttc"].sum() if not df.empty else 0.0


def get_ttc_by_fournisseur(db_manager, start_date, end_date):
    where = []
    params = []
    if start_date and end_date:
        where.append("date BETWEEN ? AND ?")
        params.extend([start_date, end_date])
    where_clause = " AND ".join(where) if where else None

    query = f"""
        SELECT f.fournisseur_id, fr.nom as fournisseur, SUM(f.total_ttc) as total_ttc
        FROM factures f
        JOIN fournisseurs fr ON fr.id = f.fournisseur_id
        {f"WHERE {where_clause}" if where_clause else ""}
        GROUP BY f.fournisseur_id, fr.nom
        ORDER BY total_ttc DESC
    """
    df = pd.read_sql_query(query, db_manager.conn, params=params)
    return df


def get_ttc_by_category(db_manager, fournisseur_id, start_date, end_date):
    where = []
    params = []
    if fournisseur_id:
        where.append("f.fournisseur_id = ?")
        params.append(fournisseur_id)
    if start_date and end_date:
        where.append("f.date BETWEEN ? AND ?")
        params.extend([start_date, end_date])
    where_clause = " AND ".join(where) if where else None

    query = """
        SELECT c.nom as categorie, SUM(lf.montant) as total_ttc
        FROM factures f
        JOIN lignes_facture lf ON lf.facture_id = f.id
        JOIN produits p ON p.id = lf.produit_id
        JOIN categories c ON c.id = p.categorie_id
        {where}
        GROUP BY c.nom
    """.format(
        where=f"WHERE {where_clause}" if where_clause else ""
    )
    df = pd.read_sql_query(query, db_manager.conn, params=params)
    return df


def analyst(db_manager):
    st.markdown(
        """
        <style>
        div[data-testid="stMetric"] {
            background-color: white;
            border-radius: 8px;
            padding: 10px;
            border: 1px solid #eee;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )
    # Top filters (purple)
    blank, filter1, filter2 = st.columns([7, 1, 1])
    with filter1:
        fournisseur_options = [""] + list(
            st.session_state.get("fournisseurs", {}).values()
        )

        st.selectbox(
            "Fournisseur",
            fournisseur_options,
            key="filter1",
            label_visibility="visible",
        )
    with filter2:
        today = datetime.date.today()
        one_year_ago = today.replace(year=today.year - 1)
        date_range = st.date_input(
            "Date", value=(one_year_ago, today), key="gestion_filter3"
        )

    # Get selected fournisseur name and map to id
    fournisseur_name = st.session_state.get("filter1", "")
    fournisseur_id = get_id_from_name(
        st.session_state.get("fournisseurs", {}), fournisseur_name
    )

    # Get date range
    date_range = st.session_state.get("gestion_filter3", None)
    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        today = datetime.date.today()
        start_date = today.replace(day=1)
        end_date = today

    # Compute previous month range
    first_of_this_month = start_date.replace(day=1)
    last_month_end = first_of_this_month - datetime.timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    # Get totals
    total_ttc = get_total_ttc(db_manager, fournisseur_id, start_date, end_date)
    total_ttc_prev = get_total_ttc(
        db_manager, fournisseur_id, last_month_start, last_month_end
    )

    # Compute evolution
    if total_ttc_prev == 0:
        delta = "N/A"
    else:
        delta = f"{((total_ttc - total_ttc_prev) / total_ttc_prev) * 100:.1f}%"

    kpi1, kpi2 = st.columns([1, 1])
    df_fourn = get_ttc_by_fournisseur(db_manager, start_date, end_date)

    with kpi1:
        st.metric(
            "Total dépenses TTC",
            f"{total_ttc:,.2f} €",
            delta=delta,
            delta_color=(
                "normal"
                if delta == "N/A"
                else "inverse" if total_ttc < total_ttc_prev else "off"
            ),
        )
        if not df_fourn.empty:
            fig = px.bar(
                df_fourn,
                x="fournisseur",
                y="total_ttc",
                title="Répartition des dépenses TTC par fournisseur",
                text_auto=".2s",
                color="total_ttc",
                color_continuous_scale=px.colors.sequential.Teal,
            )
            fig.update_layout(
                paper_bgcolor="white",
                plot_bgcolor="white",
                height=210,
                xaxis_title="Fournisseur",
                yaxis_title="Total TTC (€)",
                showlegend=False,
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aucune dépense pour ce filtre.")

    df_cat = get_ttc_by_category(db_manager, fournisseur_id, start_date, end_date)

    with kpi2:
        if not df_cat.empty:
            fig = px.pie(
                df_cat,
                names="categorie",
                values="total_ttc",
                title="Répartition des dépenses TTC par catégorie",
                hole=0.5,
                color_discrete_sequence=px.colors.sequential.Teal,
            )
            fig.update_layout(
                paper_bgcolor="white",
                plot_bgcolor="white",
                height=350,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aucune donnée pour ce filtre.")

    st.markdown("---")
    display_df = display_produits(db_manager, fournisseur_id, None, None)
    display_df["selected"] = False

    # Main data area (red)
    main, side = st.columns([3, 1])
    with main:
        with st.container():
            df_evo = st.session_state.get("df_evo", pd.DataFrame())
            if not df_evo.empty:
                fig = go.Figure()
                for ref in df_evo["reference"].unique():
                    df_ref = df_evo[df_evo["reference"] == ref]
                    designation = (
                        df_ref["designation"].iloc[0] if "designation" in df_ref else ""
                    )
                    legend_label = f"{ref} - {designation}" if designation else ref
                    # Line for unit price
                    fig.add_trace(
                        go.Scatter(
                            x=df_ref["date"],
                            y=df_ref["prix_unitaire"],
                            mode="lines+markers",
                            name=f"Prix unitaire - {legend_label}",
                            yaxis="y1",
                        )
                    )
                    # Bar for quantity
                    fig.add_trace(
                        go.Bar(
                            x=df_ref["date"],
                            y=df_ref["quantite"],
                            name=f"Quantité - {legend_label}",
                            yaxis="y2",
                            opacity=0.3,
                        )
                    )
                # Layout with dual y-axes
                fig.update_layout(
                    title="Évolution du prix unitaire et quantités achetées",
                    xaxis_title="Date",
                    yaxis=dict(title="Prix unitaire", side="left"),
                    yaxis2=dict(
                        title="Quantité",
                        overlaying="y",
                        side="right",
                        showgrid=False,
                    ),
                    legend=dict(orientation="h"),
                    bargap=0.2,
                    paper_bgcolor="white",
                    plot_bgcolor="white",
                    height=500,
                    margin=dict(l=10, r=10, t=40, b=10),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(
                    "Aucune donnée pour les produits sélectionnés dans cette période."
                )
    with side:
        with st.container():
            selected = st.data_editor(
                display_df,
                height=500,
                use_container_width=True,
                hide_index=True,
                key="produit_editor",
                num_rows="fixed",
                column_order=[
                    "selected",
                    "Référence",
                    "Désignation",
                    "Fournisseur",
                    "Marque",
                    "Catégorie",
                ],
                column_config={
                    "selected": st.column_config.CheckboxColumn("", default=False),
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
        selected_rows = (
            selected.index[selected["selected"]].tolist()
            if "selected" in selected
            else []
        )

        if selected_rows:
            selected_refs = selected.loc[selected_rows, "Référence"].tolist()
            # Query only if refs exist
            if selected_refs:
                placeholders = ",".join(["?"] * len(selected_refs))
                query = f"""
                    SELECT f.date, p.reference, p.designation, lf.prix_unitaire, lf.quantite
                    FROM lignes_facture lf
                    JOIN produits p ON p.id = lf.produit_id
                    JOIN factures f ON f.id = lf.facture_id
                    WHERE p.reference IN ({placeholders})
                    AND f.date BETWEEN ? AND ?
                    ORDER BY p.reference, f.date
                """
                params = selected_refs + [start_date, end_date]
                df_evo = pd.read_sql_query(query, db_manager.conn, params=params)
        else:
            # No selection → empty dataframe
            df_evo = pd.DataFrame()

        # Update session state and trigger rerun if changed
        if not st.session_state.get("df_evo", pd.DataFrame()).equals(df_evo):
            st.session_state["df_evo"] = df_evo
            st.rerun()
