"use client";

import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";

import { useSupabase } from "../../hooks/useSupabase";
import { ArticleRow, ExtractionResponse } from "../../types/invoice";
import { runExtraction, saveInvoice } from "../../lib/api/extraction";
import { PdfDropzone } from "../forms/PdfDropzone";
import { EditableArticlesTable } from "../tables/EditableArticlesTable";
import { PdfViewer } from "./PdfViewer";

interface ExtractionWorkspaceProps {
  categories: string[];
  marques: string[];
  fournisseurs: string[];
}

interface InvoiceFormValues {
  filename: string;
  supplierName: string;
  supplierAddress: string;
  invoiceNumber: string;
  invoiceDate: string;
  packageCount: number | null;
  total_ht: number;
  tva: number;
  total_ttc: number;
}

const emptyArticle: ArticleRow = {};

const buildDefaultFormValues = (): InvoiceFormValues => ({
  filename: "",
  supplierName: "",
  supplierAddress: "",
  invoiceNumber: "",
  invoiceDate: new Date().toISOString().slice(0, 10),
  packageCount: null,
  total_ht: 0,
  tva: 0,
  total_ttc: 0,
});

export const ExtractionWorkspace = ({ categories, marques, fournisseurs }: ExtractionWorkspaceProps) => {
  const { session } = useSupabase();
  const userId = session?.user.id;
  const [file, setFile] = useState<File | null>(null);
  const [localPreviewUrl, setLocalPreviewUrl] = useState<string | null>(null);
  const [annotatedPreviewUrl, setAnnotatedPreviewUrl] = useState<string | null>(null);
  const [confirmationRow, setConfirmationRow] = useState<ArticleRow>(emptyArticle);
  const [isExtracting, setIsExtracting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [result, setResult] = useState<ExtractionResponse | null>(null);
  const [articles, setArticles] = useState<ArticleRow[]>([emptyArticle]);
  const [activePdf, setActivePdf] = useState<"annotated" | "original">("original");

  const { register, handleSubmit, reset } = useForm<InvoiceFormValues>({
    defaultValues: buildDefaultFormValues(),
  });

  const convertBase64PdfToUrl = (base64: string) => {
    if (typeof window === "undefined" || typeof atob === "undefined") {
      return null;
    }
    const byteCharacters = atob(base64);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i += 1) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    const blob = new Blob([byteArray], { type: "application/pdf" });
    return URL.createObjectURL(blob);
  };

  useEffect(() => {
    if (!result) {
      setAnnotatedPreviewUrl((prev) => {
        if (prev && prev.startsWith("blob:")) {
          URL.revokeObjectURL(prev);
        }
        return null;
      });
      setActivePdf("original");
      return;
    }

    const structured = result.structured;
    reset({
      filename: result.fileName ?? file?.name ?? "facture.pdf",
      supplierName: structured["Information fournisseur"].nom ?? "",
      supplierAddress: structured["Information fournisseur"].adresse ?? "",
      invoiceNumber: structured["Numéro de facture"] ?? "",
      invoiceDate: structured["Date facture"]
        ? new Date(structured["Date facture"]).toISOString().slice(0, 10)
        : new Date().toISOString().slice(0, 10),
      packageCount: structured["Nombre de colis"] ?? null,
      total_ht: structured.Total.total_ht ? Number(structured.Total.total_ht) : 0,
      tva: structured.Total.tva ? Number(structured.Total.tva) : 0,
      total_ttc: structured.Total.total_ttc ? Number(structured.Total.total_ttc) : 0,
    });
    setArticles(result.articles.length ? result.articles : [emptyArticle]);

    const annotatedUrl = result.annotatedPdfBase64
      ? convertBase64PdfToUrl(result.annotatedPdfBase64)
      : null;

    setAnnotatedPreviewUrl((prev) => {
      if (prev && prev.startsWith("blob:")) {
        URL.revokeObjectURL(prev);
      }
      return annotatedUrl;
    });

    setActivePdf(annotatedUrl ? "annotated" : "original");
  }, [file, reset, result]);

  useEffect(() => () => {
    if (localPreviewUrl && localPreviewUrl.startsWith("blob:")) {
      URL.revokeObjectURL(localPreviewUrl);
    }
  }, [localPreviewUrl]);

  useEffect(() => () => {
    if (annotatedPreviewUrl && annotatedPreviewUrl.startsWith("blob:")) {
      URL.revokeObjectURL(annotatedPreviewUrl);
    }
  }, [annotatedPreviewUrl]);

  const handleFileSelected = (selected: File | null) => {
    setFile(selected);
    setAnnotatedPreviewUrl((prev) => {
      if (prev && prev.startsWith("blob:")) {
        URL.revokeObjectURL(prev);
      }
      return null;
    });

    const nextPreviewUrl = selected ? URL.createObjectURL(selected) : null;
    setLocalPreviewUrl((prev) => {
      if (prev && prev.startsWith("blob:")) {
        URL.revokeObjectURL(prev);
      }
      return nextPreviewUrl;
    });

    reset({ ...buildDefaultFormValues(), filename: selected?.name ?? "" });
    setArticles([emptyArticle]);
    setResult(null);
    setActivePdf("original");
    resetConfirmationRow();
  };

  const confirmationReady = useMemo(() => {
    const {
      Reference,
      "Désignation": designation,
      Packaging,
      "Quantité": quantity,
      "Prix Unitaire": unitPrice,
      Total,
      Marque,
      "Catégorie": category,
    } = confirmationRow;

    const numericValues = [Packaging, quantity, unitPrice, Total];
    const numericFieldsValid = numericValues.every((value) => {
      if (value === null || value === undefined || value === "") {
        return false;
      }
      const parsed = Number(value);
      return !Number.isNaN(parsed) && parsed > 0;
    });

    const textFieldsValid = [Reference, designation, Marque, category].every((value) => {
      if (typeof value === "string") {
        return value.trim().length > 0;
      }
      return Boolean(value);
    });

    return Boolean(textFieldsValid && numericFieldsValid);
  }, [confirmationRow]);

  const canExtract = Boolean(file && confirmationReady);
  const hasExtraction = Boolean(result);
  const resetConfirmationRow = () => setConfirmationRow({ ...emptyArticle });
  const annotatedAvailable = Boolean(annotatedPreviewUrl);

  useEffect(() => {
    if (activePdf === "annotated" && !annotatedAvailable) {
      setActivePdf("original");
    }
  }, [activePdf, annotatedAvailable]);

  const onExtract = async () => {
    if (!file) {
      toast.error("Veuillez sélectionner un PDF");
      return;
    }
    if (!userId) {
      toast.error("Session utilisateur introuvable");
      return;
    }
    try {
      setAnnotatedPreviewUrl((prev) => {
        if (prev && prev.startsWith("blob:")) {
          URL.revokeObjectURL(prev);
        }
        return null;
      });
      setActivePdf("original");
      setIsExtracting(true);
      const extraction = await runExtraction({
        file,
        confirmationRow,
        userId,
      });
      setResult(extraction);
      toast.success("Extraction terminée");
    } catch (error) {
      console.error(error);
      toast.error(error instanceof Error ? error.message : "Extraction impossible");
    } finally {
      setIsExtracting(false);
    }
  };

  const onSave = async (values: InvoiceFormValues) => {
    if (!userId || !result) {
      toast.error("Données incomplètes");
      return;
    }
    if (!file) {
      toast.error("Fichier PDF introuvable");
      return;
    }
    try {
      setIsSaving(true);
      const payload = {
        userId,
        invoiceNumber: values.invoiceNumber,
        invoiceDate: values.invoiceDate,
        supplierName: values.supplierName,
        supplierAddress: values.supplierAddress,
        filename: values.filename || file?.name || "facture.pdf",
        totals: {
          total_ht: Number(values.total_ht) || 0,
          tva: Number(values.tva) || 0,
          total_ttc: Number(values.total_ttc) || 0,
        },
        packageCount: values.packageCount ? Number(values.packageCount) : null,
        articles,
      };
      const response = await saveInvoice(payload, file);
      toast.success("Facture enregistrée");
      setResult(null);
      setArticles([emptyArticle]);
      setFile(null);
      resetConfirmationRow();
      if (localPreviewUrl && localPreviewUrl.startsWith("blob:")) {
        URL.revokeObjectURL(localPreviewUrl);
      }
      setLocalPreviewUrl(null);
      setAnnotatedPreviewUrl((prev) => {
        if (prev && prev.startsWith("blob:")) {
          URL.revokeObjectURL(prev);
        }
        return null;
      });
      reset();
      return response;
    } catch (error) {
      console.error(error);
      toast.error(error instanceof Error ? error.message : "Enregistrement impossible");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,0.6fr)_minmax(0,0.4fr)] lg:items-start">
      <div className="flex flex-col gap-8">
        {hasExtraction && (
          <section className="card space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-slate-800">1. Vérifier les données extraites</h2>
                <p className="text-sm text-slate-500">Revoyez les informations générées automatiquement.</p>
              </div>
              <button
                type="button"
                className="rounded-xl border border-slate-200 px-4 py-2 text-sm text-slate-600 hover:bg-slate-100"
                onClick={() => {
                  setResult(null);
                  setArticles([emptyArticle]);
                  resetConfirmationRow();
                }}
              >
                Recommencer
              </button>
            </div>
            <form className="space-y-6" onSubmit={handleSubmit(onSave)}>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-600">Nom de la facture</label>
                  <input
                    type="text"
                    className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:border-brand focus:outline-none"
                    {...register("filename")}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-600">Fournisseur</label>
                  <input
                    type="text"
                    list="suppliers-list"
                    className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:border-brand focus:outline-none"
                    {...register("supplierName")}
                  />
                  <datalist id="suppliers-list">
                    {fournisseurs.map((name) => (
                      <option key={name} value={name} />
                    ))}
                  </datalist>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-600">Numéro de facture</label>
                  <input
                    type="text"
                    className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:border-brand focus:outline-none"
                    {...register("invoiceNumber")}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-600">Date</label>
                  <input
                    type="date"
                    className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:border-brand focus:outline-none"
                    {...register("invoiceDate")}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-600">Adresse fournisseur</label>
                <textarea
                  rows={3}
                  className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:border-brand focus:outline-none"
                  {...register("supplierAddress")}
                />
              </div>
              <div className="grid gap-4 md:grid-cols-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-600">Nombre de colis</label>
                  <input
                    type="number"
                    className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:border-brand focus:outline-none"
                    {...register("packageCount", { valueAsNumber: true })}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-600">Total HT</label>
                  <input
                    type="number"
                    step="0.01"
                    className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:border-brand focus:outline-none"
                    {...register("total_ht", { valueAsNumber: true })}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-600">TVA</label>
                  <input
                    type="number"
                    step="0.01"
                    className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:border-brand focus:outline-none"
                    {...register("tva", { valueAsNumber: true })}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-600">Total TTC</label>
                  <input
                    type="number"
                    step="0.01"
                    className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:border-brand focus:outline-none"
                    {...register("total_ttc", { valueAsNumber: true })}
                  />
                </div>
              </div>
              <div className="max-h-[360px] overflow-auto rounded-xl border border-slate-200">
                <EditableArticlesTable
                  articles={articles}
                  categories={categories}
                  marques={marques}
                  onChange={setArticles}
                />
              </div>
              <div className="flex items-center justify-between rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-600">
                <div>
                  <p>Total quantité: {articles.reduce((sum, item) => sum + (Number(item["Quantité"]) || 0), 0)}</p>
                  <p>Total montant: {articles.reduce((sum, item) => sum + (Number(item.Total) || 0), 0).toFixed(2)} €</p>
                </div>
                <button
                  type="submit"
                  disabled={isSaving}
                  className="rounded-xl bg-brand px-6 py-3 text-sm font-semibold text-white hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isSaving ? "Enregistrement..." : "Enregistrer"}
                </button>
              </div>
            </form>
          </section>
        )}

        {!hasExtraction && (
          <section className="card space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-slate-800">1. Importer une facture</h2>
                <p className="text-sm text-slate-500">Ajoutez un PDF et renseignez un premier article pour guider l'extraction.</p>
              </div>
            </div>
            <PdfDropzone
              file={file}
              onFileSelected={handleFileSelected}
            />
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-600">Référence *</label>
                <input
                  type="text"
                  value={confirmationRow.Reference ?? ""}
                  onChange={(event) => setConfirmationRow((current) => ({ ...current, Reference: event.target.value }))}
                  className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:border-brand focus:outline-none"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-600">Désignation *</label>
                <input
                  type="text"
                  value={confirmationRow["Désignation"] ?? ""}
                  onChange={(event) => setConfirmationRow((current) => ({ ...current, "Désignation": event.target.value }))}
                  className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:border-brand focus:outline-none"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-600">Packaging *</label>
                <input
                  type="number"
                  min={1}
                  step={1}
                  value={confirmationRow.Packaging ?? ""}
                  onChange={(event) =>
                    setConfirmationRow((current) => ({
                      ...current,
                      Packaging: event.target.value === "" ? null : Number(event.target.value),
                    }))
                  }
                  className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:border-brand focus:outline-none"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-600">Quantité *</label>
                <input
                  type="number"
                  min={1}
                  step={1}
                  value={confirmationRow["Quantité"] ?? ""}
                  onChange={(event) =>
                    setConfirmationRow((current) => ({
                      ...current,
                      "Quantité": event.target.value === "" ? null : Number(event.target.value),
                    }))
                  }
                  className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:border-brand focus:outline-none"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-600">Prix Unitaire (€) *</label>
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={confirmationRow["Prix Unitaire"] ?? ""}
                  onChange={(event) =>
                    setConfirmationRow((current) => ({
                      ...current,
                      "Prix Unitaire": event.target.value === "" ? null : Number(event.target.value),
                    }))
                  }
                  className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:border-brand focus:outline-none"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-600">Total (€) *</label>
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={confirmationRow.Total ?? ""}
                  onChange={(event) =>
                    setConfirmationRow((current) => ({
                      ...current,
                      Total: event.target.value === "" ? null : Number(event.target.value),
                    }))
                  }
                  className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:border-brand focus:outline-none"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-600">Marque *</label>
                <input
                  type="text"
                  value={confirmationRow.Marque ?? ""}
                  onChange={(event) => setConfirmationRow((current) => ({ ...current, Marque: event.target.value }))}
                  list="marques-extraction"
                  className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:border-brand focus:outline-none"
                />
                <datalist id="marques-extraction">
                  {marques.map((marque) => (
                    <option key={marque} value={marque} />
                  ))}
                </datalist>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-600">Catégorie *</label>
                <select
                  value={confirmationRow["Catégorie"] ?? ""}
                  onChange={(event) => setConfirmationRow((current) => ({ ...current, "Catégorie": event.target.value }))}
                  className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:border-brand focus:outline-none"
                >
                  <option value="">-</option>
                  {categories.map((category) => (
                    <option key={category} value={category}>
                      {category}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <p className="text-xs text-slate-500">
              Renseignez toutes les informations marquées d'un * pour optimiser l'extraction des lignes.
            </p>
            <button
              type="button"
              onClick={onExtract}
              disabled={!canExtract || isExtracting}
              className="w-full rounded-xl bg-brand px-6 py-3 text-sm font-semibold text-white transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isExtracting ? "Extraction en cours..." : "Lancer l'extraction"}
            </button>
          </section>
        )}
      </div>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-800">Prévisualisation</h2>
          <div className="flex items-center gap-2 rounded-full bg-white p-1 shadow-card">
            <button
              type="button"
              onClick={() => setActivePdf("original")}
              className={`rounded-full px-4 py-2 text-sm font-medium ${activePdf === "original" ? "bg-brand text-white" : "text-slate-500"}`}
            >
              Originale
            </button>
            <button
              type="button"
              onClick={() => setActivePdf("annotated")}
              disabled={!annotatedAvailable}
              className={`rounded-full px-4 py-2 text-sm font-medium ${activePdf === "annotated" ? "bg-brand text-white" : "text-slate-500"} ${!annotatedAvailable ? "opacity-50" : ""}`}
              title={annotatedAvailable ? undefined : "Disponible après extraction"}
            >
              Annotée
            </button>
          </div>
        </div>
        <PdfViewer
          url={
            activePdf === "annotated"
              ? annotatedPreviewUrl
              : localPreviewUrl
          }
        />
      </div>
    </div>
  );
};
