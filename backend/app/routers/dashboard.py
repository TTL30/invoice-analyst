"""Dashboard analytics routes."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException

from ..config import get_supabase
from ..schemas.dashboard import (
    GlobalDashboardRequest,
    GlobalDashboardResponse,
    ProductEvolutionRequest,
    ProductEvolutionResponse,
    ProductTimeSeries,
    TimeDataPoint,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.post(
    "/global", response_model=GlobalDashboardResponse, summary="Get global dashboard analytics"
)
async def get_global_dashboard(
    payload: GlobalDashboardRequest,
    supabase=Depends(get_supabase),
):
    """Fetch aggregated analytics for the global dashboard view."""
    user_id = payload.userId
    start_date = payload.startDate
    end_date = payload.endDate

    # Calculate previous period (same duration)
    period_duration = (end_date - start_date).days
    prev_end_date = start_date - timedelta(days=1)
    prev_start_date = prev_end_date - timedelta(days=period_duration)

    # Fetch invoices for the current period
    invoices_query = (
        supabase.table("factures")
        .select("id, date, total_ttc, fournisseur_id")
        .eq("user_id", user_id)
        .gte("date", str(start_date))
        .lte("date", str(end_date))
    )
    invoices_result = invoices_query.execute()
    invoices = invoices_result.data or []

    # Fetch invoices for the previous period
    prev_invoices_query = (
        supabase.table("factures")
        .select("id, date, total_ttc, fournisseur_id")
        .eq("user_id", user_id)
        .gte("date", str(prev_start_date))
        .lte("date", str(prev_end_date))
    )
    prev_invoices_result = prev_invoices_query.execute()
    prev_invoices = prev_invoices_result.data or []

    # Calculate current period KPIs
    total_ttc = sum(inv.get("total_ttc", 0) or 0 for inv in invoices)
    invoice_count = len(invoices)
    avg_invoice_amount = total_ttc / invoice_count if invoice_count > 0 else 0
    active_suppliers = len(
        set(inv.get("fournisseur_id") for inv in invoices if inv.get("fournisseur_id"))
    )

    # Calculate previous period KPIs
    prev_total_ttc = sum(inv.get("total_ttc", 0) or 0 for inv in prev_invoices)
    prev_invoice_count = len(prev_invoices)
    prev_avg_invoice_amount = prev_total_ttc / prev_invoice_count if prev_invoice_count > 0 else 0
    prev_active_suppliers = len(
        set(inv.get("fournisseur_id") for inv in prev_invoices if inv.get("fournisseur_id"))
    )

    # Calculate percentage changes
    def calc_change(current: float, previous: float) -> float:
        if previous == 0:
            return 0.0 if current == 0 else 100.0
        return ((current - previous) / previous) * 100

    total_ttc_change = calc_change(total_ttc, prev_total_ttc)
    invoice_count_change = calc_change(invoice_count, prev_invoice_count)
    avg_invoice_amount_change = calc_change(avg_invoice_amount, prev_avg_invoice_amount)
    active_suppliers_change = calc_change(active_suppliers, prev_active_suppliers)

    # Monthly totals
    from collections import defaultdict

    monthly_totals = defaultdict(float)
    for inv in invoices:
        inv_date = inv.get("date")
        if inv_date:
            month_key = inv_date[:7]  # YYYY-MM format
            monthly_totals[month_key] += inv.get("total_ttc", 0) or 0

    monthly_data = [
        {"month": month, "total": total} for month, total in sorted(monthly_totals.items())
    ]

    # Invoice volume over time
    monthly_counts = defaultdict(int)
    for inv in invoices:
        inv_date = inv.get("date")
        if inv_date:
            month_key = inv_date[:7]
            monthly_counts[month_key] += 1

    invoice_volume = [
        {"month": month, "count": count} for month, count in sorted(monthly_counts.items())
    ]

    # Supplier totals (views have RLS enabled, no need for user_id filter)
    supplier_query = (
        supabase.table("ttc_by_fournisseur_view")
        .select("fournisseur, total_ttc, date")
        .gte("date", str(start_date))
        .lte("date", str(end_date))
    )
    supplier_result = supplier_query.execute()
    supplier_data = supplier_result.data or []

    supplier_agg = defaultdict(float)
    for entry in supplier_data:
        supplier_name = entry.get("fournisseur", "Unknown")
        supplier_agg[supplier_name] += float(entry.get("total_ttc", 0) or 0)

    supplier_totals = [
        {"fournisseur": name, "total": total}
        for name, total in sorted(supplier_agg.items(), key=lambda x: x[1], reverse=True)
    ][:8]

    # Supplier concentration (all suppliers for pie chart)
    supplier_concentration = [
        {"fournisseur": name, "total": total}
        for name, total in sorted(supplier_agg.items(), key=lambda x: x[1], reverse=True)
    ]

    # Top products (views have RLS enabled, no need for user_id filter)
    products_query = (
        supabase.table("top_products_raw_view")
        .select("designation, quantite, date")
        .gte("date", str(start_date))
        .lte("date", str(end_date))
        .limit(50)
    )
    products_result = products_query.execute()
    products_data = products_result.data or []

    product_agg = defaultdict(float)
    for entry in products_data:
        designation = entry.get("designation", "Unknown")
        product_agg[designation] += float(entry.get("quantite", 0) or 0)

    top_products = [
        {"designation": name, "quantite": qty}
        for name, qty in sorted(product_agg.items(), key=lambda x: x[1], reverse=True)
    ][:5]

    # Brand & Category spending (join lignes_facture -> produits -> marques/categories)
    lines_query = (
        supabase.table("lignes_facture")
        .select("montant, produit_id, facture_id")
        .eq("user_id", user_id)
    )
    lines_result = lines_query.execute()
    lines_data = lines_result.data or []

    # Filter lines by facture_id in our date range
    invoice_ids = {inv["id"] for inv in invoices}
    filtered_lines = [line for line in lines_data if line.get("facture_id") in invoice_ids]

    # Get product -> brand/category mapping
    product_ids = {line.get("produit_id") for line in filtered_lines if line.get("produit_id")}
    if product_ids:
        products_query = (
            supabase.table("produits")
            .select("id, marque_id, categorie_id")
            .in_("id", list(product_ids))
        )
        products_result = products_query.execute()
        product_brand_map = {p["id"]: p.get("marque_id") for p in products_result.data or []}
        product_category_map = {p["id"]: p.get("categorie_id") for p in products_result.data or []}

        # Get brand names
        brand_ids = {bid for bid in product_brand_map.values() if bid}
        if brand_ids:
            brands_query = supabase.table("marques").select("id, nom").in_("id", list(brand_ids))
            brands_result = brands_query.execute()
            brand_name_map = {b["id"]: b.get("nom", "Unknown") for b in brands_result.data or []}
        else:
            brand_name_map = {}

        # Get category names
        category_ids = {cid for cid in product_category_map.values() if cid}
        if category_ids:
            categories_query = (
                supabase.table("categories").select("id, nom").in_("id", list(category_ids))
            )
            categories_result = categories_query.execute()
            category_name_map = {
                c["id"]: c.get("nom", "Unknown") for c in categories_result.data or []
            }
        else:
            category_name_map = {}
    else:
        product_brand_map = {}
        brand_name_map = {}
        product_category_map = {}
        category_name_map = {}

    # Aggregate by brand
    brand_spending = defaultdict(float)
    category_spending_dict = defaultdict(float)

    for line in filtered_lines:
        product_id = line.get("produit_id")
        montant = float(line.get("montant", 0) or 0)

        # Brand aggregation
        brand_id = product_brand_map.get(product_id)
        if brand_id:
            brand_name = brand_name_map.get(brand_id, "Unknown")
            brand_spending[brand_name] += montant

        # Category aggregation
        category_id = product_category_map.get(product_id)
        if category_id:
            category_name = category_name_map.get(category_id, "Sans catégorie")
            category_spending_dict[category_name] += montant
        else:
            category_spending_dict["Sans catégorie"] += montant

    top_brands = [
        {"marque": name, "total": total}
        for name, total in sorted(brand_spending.items(), key=lambda x: x[1], reverse=True)
    ][:8]

    category_spending = [
        {"categorie": name, "total": total}
        for name, total in sorted(category_spending_dict.items(), key=lambda x: x[1], reverse=True)
    ]

    # Month-over-month change
    if len(monthly_data) >= 2:
        current_month_total = monthly_data[-1]["total"]
        previous_month_total = monthly_data[-2]["total"]
        if previous_month_total > 0:
            mom_change = ((current_month_total - previous_month_total) / previous_month_total) * 100
        else:
            mom_change = 0.0
    else:
        mom_change = 0.0

    return GlobalDashboardResponse(
        totalTtc=total_ttc,
        invoiceCount=invoice_count,
        avgInvoiceAmount=avg_invoice_amount,
        activeSuppliers=active_suppliers,
        totalTtcChange=total_ttc_change,
        invoiceCountChange=invoice_count_change,
        avgInvoiceAmountChange=avg_invoice_amount_change,
        activeSuppliersChange=active_suppliers_change,
        monthlyTotals=monthly_data,
        invoiceVolume=invoice_volume,
        supplierTotals=supplier_totals,
        supplierConcentration=supplier_concentration,
        topProducts=top_products,
        categorySpending=category_spending,
        topBrands=top_brands,
        momChange=mom_change,
    )


@router.post(
    "/product-evolution",
    response_model=ProductEvolutionResponse,
    summary="Get product evolution analytics",
)
async def get_product_evolution(
    payload: ProductEvolutionRequest,
    supabase=Depends(get_supabase),
):
    """Fetch time series data for selected products and metric."""
    user_id = payload.userId
    product_ids = payload.productIds
    metric = payload.metric
    start_date = payload.startDate
    end_date = payload.endDate

    if not product_ids:
        return ProductEvolutionResponse(series=[])

    # Validate metric
    if metric not in ["unit_price", "quantity", "amount"]:
        raise HTTPException(status_code=400, detail="Invalid metric")

    # Get product details
    products_query = (
        supabase.table("produits")
        .select("id, reference, designation")
        .in_("id", product_ids)
        .eq("user_id", user_id)
    )
    products_result = products_query.execute()
    products_map = {
        p["id"]: f"{p.get('reference', '')} - {p.get('designation', '')}".strip(" -")
        for p in (products_result.data or [])
    }

    # Get invoice lines with facture date
    lines_query = (
        supabase.table("lignes_facture")
        .select("produit_id, prix_unitaire, quantite, montant, facture_id, unite, poids_volume")
        .in_("produit_id", product_ids)
        .eq("user_id", user_id)
    )
    lines_result = lines_query.execute()
    lines_data = lines_result.data or []

    # Get facture dates
    facture_ids = list({line.get("facture_id") for line in lines_data if line.get("facture_id")})
    if not facture_ids:
        return ProductEvolutionResponse(series=[])

    factures_query = (
        supabase.table("factures")
        .select("id, date")
        .in_("id", facture_ids)
        .gte("date", str(start_date))
        .lte("date", str(end_date))
    )
    factures_result = factures_query.execute()
    facture_date_map = {f["id"]: f.get("date") for f in (factures_result.data or [])}

    # Filter lines by date range
    filtered_lines = [line for line in lines_data if line.get("facture_id") in facture_date_map]

    # Aggregate by product and month - collect ALL metrics
    from collections import defaultdict

    # Store all three metrics separately
    product_monthly_data = defaultdict(
        lambda: defaultdict(lambda: {"unit_prices": [], "quantities": [], "amounts": []})
    )

    for line in filtered_lines:
        product_id = line.get("produit_id")
        facture_id = line.get("facture_id")
        invoice_date = facture_date_map.get(facture_id)

        if not invoice_date or not product_id:
            continue

        month_key = invoice_date[:7]  # YYYY-MM format

        # Collect all metrics regardless of selected metric
        unit_price = line.get("prix_unitaire")
        quantity = line.get("quantite")
        amount = line.get("montant")

        if unit_price is not None:
            product_monthly_data[product_id][month_key]["unit_prices"].append(float(unit_price))
        if quantity is not None:
            product_monthly_data[product_id][month_key]["quantities"].append(float(quantity))
        if amount is not None:
            product_monthly_data[product_id][month_key]["amounts"].append(float(amount))

    # Build series
    series = []
    for product_id in product_ids:
        if product_id not in products_map:
            continue

        monthly_data = product_monthly_data.get(product_id, {})
        data_points = []

        for month, metrics in sorted(monthly_data.items()):
            # Calculate aggregated values for all metrics
            avg_unit_price = (
                sum(metrics["unit_prices"]) / len(metrics["unit_prices"])
                if metrics["unit_prices"]
                else None
            )
            total_quantity = sum(metrics["quantities"]) if metrics["quantities"] else None
            total_amount = sum(metrics["amounts"]) if metrics["amounts"] else None

            # Determine the main value based on selected metric
            if metric == "unit_price":
                main_value = avg_unit_price or 0
            elif metric == "quantity":
                main_value = total_quantity or 0
            else:  # amount
                main_value = total_amount or 0

            data_points.append(
                TimeDataPoint(
                    date=month,
                    value=main_value,
                    unitPrice=avg_unit_price,
                    quantity=total_quantity,
                    amount=total_amount,
                )
            )

        series.append(
            ProductTimeSeries(
                productId=product_id,
                productName=products_map[product_id],
                dataPoints=data_points,
            )
        )

    return ProductEvolutionResponse(series=series)
