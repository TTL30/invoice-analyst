import { API_BASE_URL } from "../env";
import { ArticleRow, ExtractionResponse, SaveInvoicePayload } from "../../types/invoice";

export const runExtraction = async ({
  file,
  confirmationRow,
  userId,
}: {
  file: File;
  confirmationRow: ArticleRow;
  userId: string;
}): Promise<ExtractionResponse> => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("user_id", userId);
  formData.append("confirmation_row", JSON.stringify(confirmationRow));

  const response = await fetch(`${API_BASE_URL}/extract`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(error || "Une erreur est survenue lors de l'extraction");
  }

  const data = (await response.json()) as ExtractionResponse;
  return data;
};

export const saveInvoice = async (payload: SaveInvoicePayload, file: File) => {
  const formData = new FormData();
  formData.append("metadata", JSON.stringify(payload));
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/invoices`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || "Impossible d'enregistrer la facture");
  }

  return response.json() as Promise<{ invoiceUrl: string; invoiceId: number }>;
};

export const deleteInvoices = async (userId: string, invoiceIds: number[]) => {
  const response = await fetch(`${API_BASE_URL}/invoices/delete`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ userId, invoiceIds }),
  });
  if (!response.ok) {
    throw new Error("Suppression impossible");
  }
  return response.json() as Promise<{ deleted: number }>;
};

export const downloadInvoices = async (userId: string, invoiceIds: number[]) => {
  const response = await fetch(`${API_BASE_URL}/invoices/download`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ userId, invoiceIds }),
  });
  if (!response.ok) {
    throw new Error("Téléchargement impossible");
  }
  const blob = await response.blob();
  return blob;
};

export const deleteProduct = async (userId: string, productId: number) => {
  const response = await fetch(`${API_BASE_URL}/products/${productId}`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ userId }),
  });
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || "Suppression impossible");
  }
  return response.json() as Promise<{ deleted: boolean; product_id: number }>;
};

export const updateProduct = async (
  userId: string,
  productId: number,
  updates: {
    reference?: string;
    designation?: string;
    fournisseur_id?: number;
    marque_id?: number;
    categorie_id?: number;
  }
) => {
  const response = await fetch(`${API_BASE_URL}/products/${productId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ userId, ...updates }),
  });
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || "Mise à jour impossible");
  }
  return response.json() as Promise<{ success: boolean; product_id: number }>;
};
