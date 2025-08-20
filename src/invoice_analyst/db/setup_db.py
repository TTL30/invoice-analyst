import os
import sqlite3

DATABASE_FILE = os.path.join(os.path.dirname(__file__), "invoices.db")


def setup_database():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    # Table fournisseurs
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS fournisseurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL UNIQUE,
            adresse TEXT,
            contact_email TEXT
        )
    """
    )

    # Table marques
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS marques (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL UNIQUE
        )
    """
    )

    # Table categories
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL UNIQUE
        )
    """
    )

    # Table produits
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS produits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        designation TEXT NOT NULL,
        reference TEXT NOT NULL,
        fournisseur_id INTEGER,
        categorie_id INTEGER,
        marque_id INTEGER,
        FOREIGN KEY (categorie_id) REFERENCES categories(id),
        FOREIGN KEY (marque_id) REFERENCES marques(id),
        FOREIGN KEY (fournisseur_id) REFERENCES fournisseurs(id),
        UNIQUE(reference, fournisseur_id)
    )
"""
    )

    # Table factures
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS factures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fournisseur_id INTEGER NOT NULL,
            numero TEXT NOT NULL,
            date TEXT NOT NULL, -- Stored as TEXT in YYYY-MM-DD format
            nom_fichier TEXT NOT NULL,
            total_ht REAL NOT NULL,
            tva_amount REAL NOT NULL,
            total_ttc REAL NOT NULL,
            FOREIGN KEY (fournisseur_id) REFERENCES fournisseurs(id),
            UNIQUE(fournisseur_id, numero)
        )
    """
    )

    # Table lignes_facture
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS lignes_facture (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            facture_id INTEGER NOT NULL,
            produit_id INTEGER NOT NULL,
            prix_unitaire REAL NOT NULL,
            collisage INTEGER NOT NULL,
            quantite REAL NOT NULL,
            montant REAL NOT NULL,
            FOREIGN KEY (facture_id) REFERENCES factures(id),
            FOREIGN KEY (produit_id) REFERENCES produits(id),
            UNIQUE(facture_id, produit_id)
        )
    """
    )

    conn.commit()
    conn.close()
    print(f"Database '{DATABASE_FILE}' and tables created/verified successfully.")


if __name__ == "__main__":
    setup_database()
