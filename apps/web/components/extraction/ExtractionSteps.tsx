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

interface ExtractionStepsProps {
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

interface ArticleFormValues {
  reference: string;
  designation: string;
  packaging: number | null;
  quantity: number | null;
  unitPrice: number | null;
  total: number | null;
  marque: string;
  category: string;
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

const buildDefaultArticleValues = (): ArticleFormValues => ({
  reference: "",
  designation: "",
  packaging: null,
  quantity: null,
  unitPrice: null,
  total: null,
  marque: "",
  category: "",
});

export const ExtractionSteps = ({ categories, marques, fournisseurs }: ExtractionStepsProps) => {
  const { session } = useSupabase();
  const userId = session?.user.id;

  // Session storage key
  const SESSION_STORAGE_KEY = `extraction_state_${userId}`;

  // Step state
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3>(1);

  // File state
  const [file, setFile] = useState<File | null>(null);
  const [localPreviewUrl, setLocalPreviewUrl] = useState<string | null>(null);
  const [annotatedPreviewUrl, setAnnotatedPreviewUrl] = useState<string | null>(null);
  const [activePdf, setActivePdf] = useState<"original" | "annotated">("original");

  // Article reference state (Step 2)
  const [articleForm, setArticleForm] = useState<ArticleFormValues>(buildDefaultArticleValues());

  // Extraction result state
  const [isExtracting, setIsExtracting] = useState(false);
  const [result, setResult] = useState<ExtractionResponse | null>(null);
  const [articles, setArticles] = useState<ArticleRow[]>([emptyArticle]);

  // Invoice form state (Step 3)
  const [isSaving, setIsSaving] = useState(false);
  const { register, handleSubmit, reset, watch } = useForm<InvoiceFormValues>({
    defaultValues: buildDefaultFormValues(),
  });

  // Watch the packageCount value for validation
  const packageCount = watch("packageCount");

  // Restore state from sessionStorage on mount
  useEffect(() => {
    if (typeof window === "undefined" || !userId) return;

    const savedState = sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (!savedState) return;

    try {
      const parsed = JSON.parse(savedState);

      if (parsed.currentStep) setCurrentStep(parsed.currentStep);
      if (parsed.articleForm) setArticleForm(parsed.articleForm);
      if (parsed.result) setResult(parsed.result);
      if (parsed.articles) setArticles(parsed.articles);
      if (parsed.activePdf) setActivePdf(parsed.activePdf);

      // Restore annotated PDF URL if exists
      if (parsed.result?.annotatedPdfBase64) {
        const annotatedUrl = convertBase64PdfToUrl(parsed.result.annotatedPdfBase64);
        setAnnotatedPreviewUrl(annotatedUrl);
      }

      // Note: We can't restore the actual File object or blob URLs
      // User will need to re-upload if they refresh the page
    } catch (error) {
      console.error("Failed to restore extraction state:", error);
      sessionStorage.removeItem(SESSION_STORAGE_KEY);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  // Save state to sessionStorage whenever it changes
  useEffect(() => {
    if (typeof window === "undefined" || !userId) return;

    // Only save if extraction has been performed (result exists)
    // This prevents saving partial state when user is just uploading/filling form
    if (!result) {
      sessionStorage.removeItem(SESSION_STORAGE_KEY);
      return;
    }

    const stateToSave = {
      currentStep,
      articleForm,
      result,
      articles,
      activePdf,
    };

    try {
      sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(stateToSave));
    } catch (error) {
      console.error("Failed to save extraction state:", error);
    }
  }, [currentStep, articleForm, result, articles, activePdf, userId, SESSION_STORAGE_KEY]);

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

  // Update form when extraction result changes
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

  // Cleanup URLs on unmount
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

  const clearSession = () => {
    // Clear session storage
    if (typeof window !== "undefined") {
      sessionStorage.removeItem(SESSION_STORAGE_KEY);
    }

    // Reset all state
    setResult(null);
    setArticles([emptyArticle]);
    setFile(null);
    setArticleForm(buildDefaultArticleValues());
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
    reset(buildDefaultFormValues());
    setCurrentStep(1);
    setActivePdf("original");
  };

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

    reset(buildDefaultFormValues());
    setArticles([emptyArticle]);
    setResult(null);
    setActivePdf("original");
    setArticleForm(buildDefaultArticleValues());

    // Automatically switch to step 2 when file is selected
    if (selected) {
      setCurrentStep(2);
    } else {
      setCurrentStep(1);
    }
  };

  const articleFormValid = useMemo(() => {
    const { reference, designation, packaging, quantity, unitPrice, total, marque, category } = articleForm;

    const numericValues = [packaging, quantity, unitPrice, total];
    const numericFieldsValid = numericValues.every((value) => {
      if (value === null || value === undefined) {
        return false;
      }
      return !Number.isNaN(value) && value > 0;
    });

    const textFieldsValid = [reference, designation, marque, category].every((value) => {
      if (typeof value === "string") {
        return value.trim().length > 0;
      }
      return Boolean(value);
    });

    return Boolean(textFieldsValid && numericFieldsValid);
  }, [articleForm]);

  const canProceedToStep2 = Boolean(file);
  const canExtract = Boolean(file && articleFormValid);
  const annotatedAvailable = Boolean(annotatedPreviewUrl);

  useEffect(() => {
    if (activePdf === "annotated" && !annotatedAvailable) {
      setActivePdf("original");
    }
  }, [activePdf, annotatedAvailable]);

  const handleExtraction = async () => {
    if (!file) {
      toast.error("Veuillez sélectionner un PDF");
      return;
    }
    if (!userId) {
      toast.error("Session utilisateur introuvable");
      return;
    }

    const confirmationRow: ArticleRow = {
      Reference: articleForm.reference,
      "Désignation": articleForm.designation,
      Packaging: articleForm.packaging,
      "Quantité": articleForm.quantity,
      "Prix Unitaire": articleForm.unitPrice,
      Total: articleForm.total,
      Marque: articleForm.marque,
      "Catégorie": articleForm.category,
    };

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
        userId,
      });
      setResult(extraction);
      setCurrentStep(3);
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

      // Clear session storage on successful save
      if (typeof window !== "undefined") {
        sessionStorage.removeItem(SESSION_STORAGE_KEY);
      }

      // Reset everything
      setResult(null);
      setArticles([emptyArticle]);
      setFile(null);
      setArticleForm(buildDefaultArticleValues());
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
      setCurrentStep(1);
      return response;
    } catch (error) {
      console.error(error);
      toast.error(error instanceof Error ? error.message : "Enregistrement impossible");
    } finally {
      setIsSaving(false);
    }
  };

  const renderPdfViewer = () => (
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
  );

  // Step 1 - Only dropzone, centered
  if (currentStep === 1) {
    // Check if we have a saved session
    const hasSavedSession = typeof window !== "undefined" && sessionStorage.getItem(SESSION_STORAGE_KEY);

    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <div className="w-full max-w-2xl">
          <PdfDropzone file={file} onFileSelected={handleFileSelected} />
        </div>
        {hasSavedSession && (
          <p className="text-sm text-gray-600">
            Vous avez une extraction en cours.{" "}
            <button
              onClick={clearSession}
              className="text-teal-600 hover:text-teal-700 font-medium underline"
            >
              Recommencer depuis le début
            </button>
          </p>
        )}
      </div>
    );
  }

  // Steps 2 & 3 - Two column layout
  const gridCols = currentStep === 3 ? "lg:grid-cols-[minmax(0,0.6fr)_minmax(0,0.4fr)]" : "lg:grid-cols-[minmax(0,0.4fr)_minmax(0,0.6fr)]";

  return (
    <div className={`grid gap-8 ${gridCols}`}>
      <div className="space-y-6">
        {currentStep === 2 && (
          <>
            <div className="flex items-center justify-center rounded-full card !p-1 mb-4">
              <div className="px-4 py-2">
                <h3 className="text-sm font-medium text-gray-900">Renseignez un premier article pour guider l&apos;extraction.</h3>
              </div>
            </div>

            <div className="card space-y-4">
              <div>
                <label className="block text-sm text-gray-700 mb-1">Reference</label>
                <input
                  type="text"
                  value={articleForm.reference}
                  onChange={(e) => setArticleForm({ ...articleForm, reference: e.target.value })}
                  placeholder="Value"
                  className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-700 mb-1">Designation</label>
                <input
                  type="text"
                  value={articleForm.designation}
                  onChange={(e) => setArticleForm({ ...articleForm, designation: e.target.value })}
                  placeholder="Value"
                  className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-700 mb-1">Packaging</label>
                <input
                  type="number"
                  value={articleForm.packaging ?? ""}
                  onChange={(e) => setArticleForm({ ...articleForm, packaging: e.target.value ? Number(e.target.value) : null })}
                  placeholder="Value"
                  className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-700 mb-1">Quantite</label>
                <input
                  type="number"
                  value={articleForm.quantity ?? ""}
                  onChange={(e) => setArticleForm({ ...articleForm, quantity: e.target.value ? Number(e.target.value) : null })}
                  placeholder="Value"
                  className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-700 mb-1">Prix unitaire</label>
                <input
                  type="number"
                  step="0.01"
                  value={articleForm.unitPrice ?? ""}
                  onChange={(e) => setArticleForm({ ...articleForm, unitPrice: e.target.value ? Number(e.target.value) : null })}
                  placeholder="Value"
                  className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-700 mb-1">Total</label>
                <input
                  type="number"
                  step="0.01"
                  value={articleForm.total ?? ""}
                  onChange={(e) => setArticleForm({ ...articleForm, total: e.target.value ? Number(e.target.value) : null })}
                  placeholder="Value"
                  className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-700 mb-1">Marque</label>
                <input
                  type="text"
                  value={articleForm.marque}
                  onChange={(e) => setArticleForm({ ...articleForm, marque: e.target.value })}
                  list="marques-list"
                  placeholder="Value"
                  className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600 focus:border-transparent"
                />
                <datalist id="marques-list">
                  {marques.map((m) => (
                    <option key={m} value={m} />
                  ))}
                </datalist>
              </div>

              <div>
                <label className="block text-sm text-gray-700 mb-1">Categorie</label>
                <input
                  type="text"
                  value={articleForm.category}
                  onChange={(e) => setArticleForm({ ...articleForm, category: e.target.value })}
                  list="categories-list"
                  placeholder="Value"
                  className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600 focus:border-transparent"
                />
                <datalist id="categories-list">
                  {categories.map((c) => (
                    <option key={c} value={c} />
                  ))}
                </datalist>
              </div>

              <button
                type="button"
                onClick={handleExtraction}
                disabled={!canExtract || isExtracting}
                className="w-full rounded-lg bg-teal-600 px-6 py-3 text-sm font-medium text-white transition hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {isExtracting ? (
                  <>
                    <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Extraction en cours...
                  </>
                ) : (
                  "Lancer l&apos;extraction"
                )}
              </button>
            </div>
          </>
        )}

        {currentStep === 3 && result && (
          <div className="card flex flex-col h-[calc(100vh-8rem)]">
            <div className="mb-4 flex items-start justify-between">
              <div>
                <h3 className="text-base font-semibold text-gray-900">Vérifier les données extraites</h3>
                <p className="text-sm text-gray-600">Revoyez les informations générées automatiquement.</p>
              </div>
              <button
                type="button"
                onClick={clearSession}
                className="text-sm text-gray-600 hover:text-gray-900 underline"
              >
                Recommencer
              </button>
            </div>

            <form onSubmit={handleSubmit(onSave)} className="flex flex-col flex-1 min-h-0 space-y-4">
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
                  />
                </div>

                <div>
                  <label className="block text-sm text-gray-700 mb-1">Date</label>
                  <input
                    type="date"
                    {...register("invoiceDate")}
                    placeholder="Value"
                    className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600 focus:border-transparent"
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

              <div className="flex-1 min-h-0 overflow-auto">
                <EditableArticlesTable
                  articles={articles}
                  categories={categories}
                  marques={marques}
                  onChange={setArticles}
                />
              </div>

              {/* Package count validation warning */}
              {(() => {
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

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm text-gray-700 mb-1">Total HT</label>
                  <input
                    type="number"
                    step="0.01"
                    {...register("total_ht", { valueAsNumber: true })}
                    placeholder="Value"
                    className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600 focus:border-transparent"
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
                  />
                </div>
              </div>

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
      </div>

      {/* Right column - PDF Viewer */}
      <div>{renderPdfViewer()}</div>
    </div>
  );
};