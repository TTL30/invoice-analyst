export type ArticleRow = {
  Reference?: string | null;
  "Désignation"?: string | null;
  "Prix Unitaire"?: number | null;
  Packaging?: number | null;
  "Quantité"?: number | null;
  Total?: number | null;
  Marque?: string | null;
  "Catégorie"?: string | null;
  // Validation status from PDF annotation
  validationStatus?: "correct" | "error" | null;
  missingFields?: string[] | null;
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

export interface ExtractionResponse {
  structured: StructuredInvoice;
  articles: ArticleRow[];
  annotatedPdfBase64?: string | null;
  fileName?: string | null;
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
