export type ArticleRow = {
  Reference?: string | null;
  "Désignation"?: string | null;
  "Prix Unitaire"?: number | null;
  Packaging?: number | null;
  "Quantité"?: number | null;
  "Unité"?: string | null;
  "Poids/Volume"?: number | null;
  Total?: number | null;
  Marque?: string | null;
  "Catégorie"?: string | null;
  // Track if user has edited this row (optional, undefined by default)
  userEdited?: boolean;
  // Highlight color from PDF annotation (optional, undefined by default)
  highlightColor?: string;
};

export interface StructuredInvoice {
  "Numéro de facture": string;
  "Date facture": string;
  "Information fournisseur": {
    nom: string;
    adresse?: string | null;
  };
  "Nombre de colis"?: number | null;
  Total: {
    total_ht?: number | null;
    tva?: number | null;
    total_ttc?: number | null;
  };
  articles?: ArticleRow[] | string;
}

export interface ColorMapping {
  metadata_colors: {
    [key: string]: string; // Field name -> hex color
  };
  article_colors: string[]; // Array of hex colors, one per article
}

export interface ExtractionResponse {
  structured: StructuredInvoice;
  articles: ArticleRow[];
  annotatedPdfBase64?: string | null;
  fileName?: string | null;
  colorMapping?: ColorMapping;
}

export interface SaveInvoicePayload {
  userId: string;
  invoiceNumber: string;
  invoiceDate: string;
  supplierName: string;
  supplierAddress?: string | null;
  filename: string;
  totals: {
    total_ht: number;
    tva: number;
    total_ttc: number;
  };
  packageCount?: number | null;
  articles: ArticleRow[];
}
