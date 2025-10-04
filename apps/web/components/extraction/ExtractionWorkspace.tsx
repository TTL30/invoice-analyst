"use client";

import { useEffect, useMemo, useState, useCallback, useRef } from "react";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";

import { useSupabase } from "../../hooks/useSupabase";
import { ArticleRow, ExtractionResponse } from "../../types/invoice";
import { runExtraction, saveInvoice } from "../../lib/api/extraction";
import { PdfDropzone } from "../forms/PdfDropzone";
import { EditableArticlesTable } from "../tables/EditableArticlesTable";
import { PdfViewer } from "./PdfViewer";
import {
  loadExtractionState,
  saveExtractionState,
  clearExtractionState,
  base64ToFile,
  base64ToUrl
} from "../../lib/extractionPersistence";

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
  const [isExtracting, setIsExtracting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [result, setResult] = useState<ExtractionResponse | null>(null);
  const [articles, setArticles] = useState<ArticleRow[]>([emptyArticle]);
  const [activePdf, setActivePdf] = useState<"annotated" | "original">("original");
  const [hideDetails, setHideDetails] = useState(false);
  const [isRestoringState, setIsRestoringState] = useState(false);
  const [metadataColors, setMetadataColors] = useState<{ [key: string]: string }>({});

  const { register, handleSubmit, reset, watch, getValues } = useForm<InvoiceFormValues>({
    defaultValues: buildDefaultFormValues(),
  });

  // Watch all form values for auto-save
  const formValues = watch();
  const packageCount = formValues.packageCount;

  // Track if we've loaded persisted state to avoid overwriting
  const hasLoadedPersistedState = useRef(false);
  // Debounce timer for auto-save
  const autoSaveTimer = useRef<NodeJS.Timeout | null>(null);

  // Helper to get background color with opacity for metadata fields
  const getFieldBackgroundColor = (fieldName: string) => {
    const color = metadataColors[fieldName];
    if (!color) return undefined;
    return color + "30"; // Add 30% opacity (hex: ~50)
  };

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

  // Load persisted state on mount
  useEffect(() => {
    if (!userId || hasLoadedPersistedState.current || isRestoringState) {
      return;
    }

    const persistedState = loadExtractionState(userId);
    if (!persistedState) {
      hasLoadedPersistedState.current = true;
      return;
    }

    setIsRestoringState(true);

    try {
      // Restore form values
      reset(persistedState.formValues);

      // Restore articles
      setArticles(persistedState.articles);

      // Restore result
      setResult(persistedState.result);

      // Restore file if available
      if (persistedState.fileData) {
        const restoredFile = base64ToFile(
          persistedState.fileData.base64,
          persistedState.fileData.name,
          persistedState.fileData.type
        );
        setFile(restoredFile);

        const previewUrl = URL.createObjectURL(restoredFile);
        setLocalPreviewUrl(previewUrl);
      }

      // Restore annotated PDF if available
      if (persistedState.annotatedPdfBase64) {
        const annotatedUrl = base64ToUrl(persistedState.annotatedPdfBase64);
        setAnnotatedPreviewUrl(annotatedUrl);
      }

      // Restore UI state
      setActivePdf(persistedState.activePdf);
      setHideDetails(persistedState.hideDetails);

      hasLoadedPersistedState.current = true;
      toast.success("Brouillon restauré");
    } catch (error) {
      console.error("Error restoring persisted state:", error);
      toast.error("Erreur lors de la restauration du brouillon");
    } finally {
      setIsRestoringState(false);
    }
  }, [userId, reset, isRestoringState]);

  // Auto-save to localStorage with debouncing
  useEffect(() => {
    if (!userId || !hasLoadedPersistedState.current || isRestoringState) {
      return;
    }

    // Only auto-save if there's actual data to save
    if (!result && !file && articles.length === 1 && !articles[0].Reference) {
      return;
    }

    // Clear existing timer
    if (autoSaveTimer.current) {
      clearTimeout(autoSaveTimer.current);
    }

    // Debounce the save
    autoSaveTimer.current = setTimeout(async () => {
      try {
        await saveExtractionState(userId, {
          formValues: getValues(),
          articles,
          result,
          file,
          annotatedPdfBase64: result?.annotatedPdfBase64 ?? null,
          activePdf,
          hideDetails,
        });
      } catch (error) {
        console.error("Error auto-saving extraction state:", error);
      }
    }, 2000); // Save 2 seconds after last change

    return () => {
      if (autoSaveTimer.current) {
        clearTimeout(autoSaveTimer.current);
      }
    };
  }, [userId, formValues, articles, result, file, activePdf, hideDetails, isRestoringState, getValues]);

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

    // Add highlight colors to articles from color mapping
    const articlesWithColors = result.articles.map((article, index) => ({
      ...article,
      highlightColor: result.colorMapping?.article_colors?.[index],
    }));

    setArticles(articlesWithColors.length ? articlesWithColors : [emptyArticle]);

    // Store metadata colors for form field highlighting
    if (result.colorMapping?.metadata_colors) {
      setMetadataColors(result.colorMapping.metadata_colors);
    }

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

  const handleFileSelected = async (selected: File | null) => {
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

    // Auto-extract when file is dropped
    if (selected && userId) {
      await onExtract(selected);
    }
  };

  const hasExtraction = Boolean(result);
  const annotatedAvailable = Boolean(annotatedPreviewUrl);

  useEffect(() => {
    if (activePdf === "annotated" && !annotatedAvailable) {
      setActivePdf("original");
    }
  }, [activePdf, annotatedAvailable]);

  const onExtract = async (fileToExtract: File) => {
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
        file: fileToExtract,
        userId,
      });
      setResult(extraction);

      // Auto-save immediately after extraction
      if (extraction && file) {
        await autoSave(extraction, fileToExtract);
      }

      toast.success("Extraction et enregistrement terminés");
    } catch (error) {
      console.error(error);
      const errorMessage = error instanceof Error ? error.message : "Extraction impossible";

      // Check if it's an unsupported invoice type error
      if (errorMessage.includes("Invoice type not supported") || errorMessage.includes("not supported")) {
        toast.error("Type de facture non supporté, contactez l'administrateur");
      } else {
        toast.error(errorMessage);
      }
    } finally {
      setIsExtracting(false);
    }
  };

  const autoSave = async (extraction: ExtractionResponse, fileToSave: File) => {
    if (!userId) return;

    const structured = extraction.structured;
    const payload = {
      userId,
      invoiceNumber: structured["Numéro de facture"] ?? "",
      invoiceDate: structured["Date facture"]
        ? new Date(structured["Date facture"]).toISOString().slice(0, 10)
        : new Date().toISOString().slice(0, 10),
      supplierName: structured["Information fournisseur"].nom ?? "",
      supplierAddress: structured["Information fournisseur"].adresse ?? "",
      filename: extraction.fileName ?? fileToSave.name ?? "facture.pdf",
      totals: {
        total_ht: structured.Total.total_ht ? Number(structured.Total.total_ht) : 0,
        tva: structured.Total.tva ? Number(structured.Total.tva) : 0,
        total_ttc: structured.Total.total_ttc ? Number(structured.Total.total_ttc) : 0,
      },
      packageCount: structured["Nombre de colis"] ?? null,
      articles: extraction.articles.length ? extraction.articles : [emptyArticle],
    };

    await saveInvoice(payload, fileToSave);
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

      // Clear localStorage after successful save
      clearExtractionState(userId);

      toast.success("Facture enregistrée");
      setResult(null);
      setArticles([emptyArticle]);
      setFile(null);
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
    <div className={hasExtraction ? "grid gap-8 lg:grid-cols-[minmax(0,0.65fr)_minmax(0,0.35fr)] lg:items-start" : "flex items-center justify-center min-h-[60vh]"}>
      <div className={`${!hasExtraction ? "w-full max-w-2xl" : "space-y-6"}`}>
        {hasExtraction && (
          <div className="card flex flex-col h-[calc(100vh-8rem)]">
            <div className="mb-4 flex items-start justify-between">
              <div>
                <h3 className="text-base font-semibold text-gray-900">Vérifier les données extraites</h3>
                <p className="text-sm text-gray-600">Revoyez les informations générées automatiquement.</p>
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setHideDetails(!hideDetails)}
                  className="text-sm text-gray-600 hover:text-gray-900 underline"
                >
                  {hideDetails ? "Afficher détails" : "Masquer détails"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (userId) {
                      clearExtractionState(userId);
                    }
                    setResult(null);
                    setArticles([emptyArticle]);
                    setFile(null);
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
                  }}
                  className="text-sm text-gray-600 hover:text-gray-900 underline"
                >
                  Recommencer
                </button>
              </div>
            </div>

            <form onSubmit={handleSubmit(onSave)} className="flex flex-col flex-1 min-h-0 space-y-4">
              {!hideDetails && (
              <>
              <div className="grid grid-cols-3 gap-4">
                <div className="col-span-2">
                  <label className="block text-sm text-gray-700 mb-1">Nom de la facture</label>
                  <input
                    type="text"
                    {...register("filename")}
                    placeholder="Value"
                    className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600 focus:border-transparent"
                  />
                </div>

                <div>
                  <label className="block text-sm text-gray-700 mb-1">Nombre de colis</label>
                  <input
                    type="number"
                    {...register("packageCount", { valueAsNumber: true })}
                    placeholder="Value"
                    className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600 focus:border-transparent"
                  />
                </div>

                <div>
                  <label className="block text-sm text-gray-700 mb-1">Fournisseur</label>
                  <input
                    type="text"
                    {...register("supplierName")}
                    list="suppliers-list"
                    placeholder="Value"
                    className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600 focus:border-transparent"
                    style={{ backgroundColor: getFieldBackgroundColor("supplier_name") }}
                  />
                  <datalist id="suppliers-list">
                    {fournisseurs.map((name) => (
                      <option key={name} value={name} />
                    ))}
                  </datalist>
                </div>

                <div>
                  <label className="block text-sm text-gray-700 mb-1">Numéro de facture</label>
                  <input
                    type="text"
                    {...register("invoiceNumber")}
                    placeholder="Value"
                    className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600 focus:border-transparent"
                    style={{ backgroundColor: getFieldBackgroundColor("invoice_number") }}
                  />
                </div>

                <div>
                  <label className="block text-sm text-gray-700 mb-1">Date</label>
                  <input
                    type="date"
                    {...register("invoiceDate")}
                    placeholder="Value"
                    className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600 focus:border-transparent"
                    style={{ backgroundColor: getFieldBackgroundColor("invoice_date") }}
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm text-gray-700 mb-1">Adresse fournisseur</label>
                <input
                  type="text"
                  {...register("supplierAddress")}
                  placeholder="Value"
                  className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600 focus:border-transparent"
                />
              </div>
              </>
              )}

              <div className="flex-1 min-h-0 overflow-auto">
                <EditableArticlesTable
                  articles={articles}
                  categories={categories}
                  marques={marques}
                  onChange={setArticles}
                />
              </div>

              {/* Package count validation warning */}
              {!hideDetails && (() => {
                const totalQuantity = articles.reduce((sum, article) => sum + (Number(article["Quantité"]) || 0), 0);
                const expectedPackages = packageCount ? Number(packageCount) : null;

                if (expectedPackages !== null && totalQuantity !== expectedPackages) {
                  return (
                    <div className="rounded-lg bg-yellow-50 border border-yellow-200 p-3 flex items-start gap-2">
                      <span className="text-yellow-600 text-lg">⚠️</span>
                      <div className="flex-1 text-sm">
                        <p className="font-semibold text-yellow-800">Attention : Écart détecté</p>
                        <p className="text-yellow-700 mt-1">
                          Le nombre de colis extrait ({expectedPackages}) ne correspond pas à la somme des quantités dans le tableau ({totalQuantity}).
                          Veuillez vérifier les données.
                        </p>
                      </div>
                    </div>
                  );
                }
                return null;
              })()}

              {!hideDetails && (
              <>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm text-gray-700 mb-1">Total HT</label>
                  <input
                    type="number"
                    step="0.01"
                    {...register("total_ht", { valueAsNumber: true })}
                    placeholder="Value"
                    className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600 focus:border-transparent"
                    style={{ backgroundColor: getFieldBackgroundColor("total_without_taxes") }}
                  />
                </div>

                <div>
                  <label className="block text-sm text-gray-700 mb-1">TVA</label>
                  <input
                    type="number"
                    step="0.01"
                    {...register("tva", { valueAsNumber: true })}
                    placeholder="Value"
                    className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600 focus:border-transparent"
                    style={{ backgroundColor: getFieldBackgroundColor("taxes_amount") }}
                  />
                </div>

                <div>
                  <label className="block text-sm text-gray-700 mb-1">Total TTC</label>
                  <input
                    type="number"
                    step="0.01"
                    {...register("total_ttc", { valueAsNumber: true })}
                    placeholder="Value"
                    className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600 focus:border-transparent"
                    style={{ backgroundColor: getFieldBackgroundColor("total_amount") }}
                  />
                </div>
              </div>
              </>
              )}

              <button
                type="submit"
                disabled={isSaving}
                className="w-full rounded-lg bg-teal-600 px-6 py-3 text-sm font-medium text-white transition hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {isSaving ? (
                  <>
                    <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Enregistrement...
                  </>
                ) : (
                  "Enregistrer"
                )}
              </button>
            </form>
          </div>
        )}

        {!hasExtraction && (
          <section className="card space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-slate-800">Importer une facture</h2>
                <p className="text-sm text-slate-500">Déposez votre PDF pour lancer l'extraction automatiquement.</p>
              </div>
            </div>
            <PdfDropzone
              file={file}
              onFileSelected={handleFileSelected}
            />
            {isExtracting && (
              <div className="flex items-center justify-center gap-3 rounded-xl bg-brand/5 px-6 py-4">
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-brand border-t-transparent"></div>
                <p className="text-sm font-medium text-brand">Extraction en cours...</p>
              </div>
            )}
          </section>
        )}
      </div>
      {hasExtraction && (
        <div className="sticky top-24 flex flex-col h-[calc(100vh-8rem)]">
          <div className="flex items-center justify-center gap-2 rounded-full card !p-1 mb-4">
            <button
              type="button"
              onClick={() => setActivePdf("original")}
              className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                activePdf === "original" ? "bg-teal-600 text-white" : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              Originale
            </button>
            <button
              type="button"
              onClick={() => setActivePdf("annotated")}
              disabled={!annotatedAvailable}
              className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                activePdf === "annotated" ? "bg-teal-600 text-white" : "text-gray-600 hover:bg-gray-100"
              } ${!annotatedAvailable ? "opacity-50 cursor-not-allowed" : ""}`}
              title={annotatedAvailable ? undefined : "Disponible après extraction"}
            >
              Annotée
            </button>
          </div>
          <div className="flex-1 min-h-0">
            <PdfViewer
              url={
                activePdf === "annotated"
                  ? annotatedPreviewUrl
                  : localPreviewUrl
              }
            />
          </div>
        </div>
      )}
    </div>
  );
};
