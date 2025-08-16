import streamlit as st


CATEGORIES = [
    "Matières premières",
    "Fruits, légumes, graines et fruits secs",
    "Boissons",
    "Emballages et consommables",
    "Entretien et hygiène",
    "Droguerie et divers",
    "Produits surgelés",
    "Papeterie et caisse",
    "Transport / livraison",
    "Décoration / présentation"
]

ARTICLES_COLUMNS_CONFIG = {
                "Reference": st.column_config.TextColumn("Reference"),
                "Désignation": st.column_config.TextColumn("Désignation"),
                "Prix Unitaire": st.column_config.NumberColumn("Prix Unitaire", format="%.3f"),
                "Packaging": st.column_config.NumberColumn("Packaging", format="%d"),
                "Quantité": st.column_config.NumberColumn("Quantité", format="%d"),
                "Total": st.column_config.NumberColumn("Total", format="%.3f"),
                "Marque": st.column_config.TextColumn("Marque"),
                "Catégorie": st.column_config.SelectboxColumn("Catégorie", options=CATEGORIES),
            }

def structure_prompt(aggregated_ocr, example_row_cleaned):
    return (
        f"This is the OCR result in markdown format:\n\n{aggregated_ocr}\n\n"
        "Your tasks are:\n"
        "1. Extract and clean only the following invoice information:\n"
        "- Invoice number (Numéro de facture)\n"
        "- Invoice date (Date facture)\n"
        "- Supplier information (Information fournisseur: name and address, usually located at the top of the first page)\n"
        "- Number of packages (Nombre de colis)\n"
        "- Total price (Total: total_ht, tva, total_ttc, usually located at the end or on the last page)\n\n"
        "2. Extract, clean, and reorder only the articles table information.\n"
        " For each article, map the columns as follows:\n"
        "- reference (should be a string or number)\n"
        "- designation (should be a string)\n"
        "- packaging (should be an integer)\n"
        "- quantite (should be an integer)\n"
        "- prix unitaire (should be a float, price in euros)\n"
        "- total (should be a float, price in euros)\n"
        "- brand (check in the designation if you find an existing brand, otherwise use null)\n"
        f"- category (attribute a category based on the designation, using only one of the following: {CATEGORIES})\n"
        "For example, the first article row is mapped as:\n"
        f"{example_row_cleaned}\n\n"
        "Return a single valid JSON object with this structure:\n"
        "{\n"
        "  \"Numéro de facture\": ...,\n"
        "  \"Date facture\": ...,\n"
        "  \"Information fournisseur\": {\"nom\": ..., \"adresse\": ...},\n"
        "  \"Nombre de colis\": ...,\n"
        "  \"Total\": {\"total_ht\": ..., \"tva\": ..., \"total_ttc\": ...},\n"
        "  \"articles\": \"<cleaned markdown table of articles, without header>\"\n"
        "}\n"
        "Do not include any extra commentary or explanation."
    )