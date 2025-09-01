import datetime
import pandas as pd
import streamlit as st
import plotly.express as px
from invoice_analyst.utils import get_id_from_name
from invoice_analyst.components.charts import make_bar_fig, make_line_fig


# -----------------------
# Data Access Functions
# -----------------------
def get_top_products_by_quantity(
    supabase, fournisseur_id, start_date, end_date, top_n=5
):
    query = supabase.table("top_products_raw_view").select("*")
    if fournisseur_id:
        query = query.eq("fournisseur", fournisseur_id)
    if start_date and end_date:
        query = query.gte("date", str(start_date)).lte("date", str(end_date))

    data = query.execute()
    df = pd.DataFrame(data.data)
    if df.empty:
        return df
    df = (
        df.groupby(["reference", "designation", "marque", "fournisseur"])["quantite"]
        .sum()
        .reset_index()
        .sort_values("quantite", ascending=False)
        .head(top_n)
    )
    return df


def get_total_ttc(supabase, fournisseur_id, start_date, end_date):
    query = supabase.table("factures").select("total_ttc")
    if fournisseur_id:
        query = query.eq("fournisseur_id", fournisseur_id)
    if start_date and end_date:
        query = query.gte("date", str(start_date)).lte("date", str(end_date))
    data = query.execute()
    df = pd.DataFrame(data.data)
    return df["total_ttc"].sum() if not df.empty else 0.0


def get_ttc_by_fournisseur(supabase, start_date, end_date):
    query = supabase.table("ttc_by_fournisseur_view").select("*")
    if start_date and end_date:
        query = query.gte("date", str(start_date)).lte("date", str(end_date))
    data = query.execute()
    df = pd.DataFrame(data.data)
    if df.empty:
        return df
    df = df.groupby(["fournisseur_id", "fournisseur"])["total_ttc"].sum().reset_index()
    return df.sort_values("total_ttc", ascending=False)


def get_ttc_by_category(supabase, fournisseur_id, start_date, end_date):
    query = supabase.table("ttc_by_category_view").select("*")
    if fournisseur_id:
        query = query.eq("fournisseur_id", fournisseur_id)
    if start_date and end_date:
        query = query.gte("date", str(start_date)).lte("date", str(end_date))
    data = query.execute()
    df = pd.DataFrame(data.data)
    if df.empty:
        return df
    df = df.groupby("categorie")["total_ttc"].sum().reset_index()
    return df


# -----------------------
# Streamlit Page
# -----------------------


def run():
    supabase = st.session_state["supabase"]

    blank, filter2 = st.columns([5, 1])
    with filter2:
        today = datetime.date.today()
        one_year_ago = today.replace(year=today.year - 1)
        date_range = st.date_input(
            "Date",
            value=(one_year_ago, today),
            key="gestion_filter3",
            label_visibility="collapsed",
        )

    fournisseur_name = st.session_state.get("filter1", "")
    fournisseur_id = get_id_from_name(
        st.session_state.get("fournisseurs", {}), fournisseur_name
    )

    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        today = datetime.date.today()
        start_date = today.replace(day=1)
        end_date = today

    # --- Total ---
    total_ttc = get_total_ttc(supabase, fournisseur_id, start_date, end_date)

    col1, col2 = st.columns([1, 2], gap="medium")
    with col1:
        st.markdown(
            f"""
            <div class="custom-card">
                <div class="custom-metric">{total_ttc:,.0f}&nbsp;€</div>
                <div class="custom-label">Total Dépenses</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        data = (
            supabase.table("factures")
            .select("*")
            .gte("date", str(start_date))
            .lte("date", str(end_date))
            .execute()
        )
        df = pd.DataFrame(data.data)
        if df.empty:
            df = pd.DataFrame(
                columns=["id", "date", "numero", "fournisseur_id", "total_ttc"]
            )

        df["date"] = pd.to_datetime(df["date"])
        df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()
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
        df["invoice_info"] = (
            "N°: "
            + df["numero"].astype(str)
            + "<br>Fournisseur: "
            + df["fournisseur_name"].astype(str)
            + "<br>TTC: "
            + df["total_ttc"].astype(str)
            + " €"
        )

        invoice_lists = (
            df.groupby("month")["invoice_info"]
            .apply(lambda x: "<br><br>".join(x))
            .reindex(df["month"].unique(), fill_value="")
        )

        df_monthly = df.groupby("month")["total_ttc"].sum().reset_index()
        df_monthly["invoice_list"] = df_monthly["month"].map(invoice_lists)

        fig = make_line_fig(
            df_monthly,
            x="month",
            y="total_ttc",
            customdata=df_monthly["invoice_list"],
            title="Évolution des Dépenses TTC",
            color_sequence=px.colors.sequential.Teal[4],
        )
        st.plotly_chart(fig, use_container_width=True)

    col3, col4 = st.columns(2, gap="medium")
    with col3:
        data = get_top_products_by_quantity(
            supabase, fournisseur_id, start_date, end_date, top_n=5
        )
        if data.empty:
            ## empty chart
            st.plotly_chart(
                make_bar_fig(
                    pd.DataFrame({"designation": [], "quantite": []}),
                    x="designation",
                    y="quantite",
                    hover_info=None,
                    title="Top 5 Produits par Quantité achetée",
                    color_sequence=px.colors.sequential.Teal,
                ),
                use_container_width=True,
            )
        else:
            st.plotly_chart(
                make_bar_fig(
                    data,
                    x="designation",
                    y="quantite",
                    hover_info="fournisseur",
                    title="Top 5 Produits par Quantité achetée",
                    color_sequence=px.colors.sequential.Teal,
                ),
                use_container_width=True,
            )

    with col4:
        data = get_ttc_by_fournisseur(supabase, start_date, end_date)
        if data.empty:
            ## empty chart
            st.plotly_chart(
                make_bar_fig(
                    pd.DataFrame({"fournisseur": [], "total_ttc": []}),
                    x="fournisseur",
                    y="total_ttc",
                    hover_info=None,
                    title="Dépenses par Fournisseur",
                    color_sequence=px.colors.sequential.Teal,
                ),
                use_container_width=True,
            )
        else:
            st.plotly_chart(
                make_bar_fig(
                    data,
                    x="fournisseur",
                    y="total_ttc",
                    hover_info=None,
                    title="Dépenses par Fournisseur",
                    color_sequence=px.colors.sequential.Teal,
                ),
                use_container_width=True,
            )
