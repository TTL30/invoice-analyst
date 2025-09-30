"use client";

import { useEffect, useMemo, useState } from "react";
import dayjs from "dayjs";
import toast from "react-hot-toast";

import { deleteInvoices, downloadInvoices, deleteProduct, updateProduct } from "../../lib/api/extraction";
import { useSupabase } from "../../hooks/useSupabase";

const today = dayjs();
const oneYearAgo = today.subtract(1, "year");

interface InvoiceRow {
  id: number;
  numero: string;
  nom_fichier: string;
  date: string;
  total_ht: number | null;
  total_ttc: number | null;
  tva_amount: number | null;
  fournisseur_id: number;
  fournisseur_nom?: string;
}

interface ProductRow {
  id: number;
  reference: string | null;
  designation: string | null;
  fournisseur_id: number | null;
  categorie_id: number | null;
  marque_id: number | null;
  fournisseur_nom?: string;
  categorie_nom?: string;
  marque_nom?: string;
}

export const GestionWorkspace = () => {
  const { supabase, session } = useSupabase();
  const userId = session?.user.id;

  const [mode, setMode] = useState<"factures" | "produits">("factures");
  const [invoices, setInvoices] = useState<InvoiceRow[]>([]);
  const [products, setProducts] = useState<ProductRow[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [fournisseurs, setFournisseurs] = useState<{ id: number; nom: string }[]>([]);
  const [categories, setCategories] = useState<{ id: number; nom: string }[]>([]);
  const [marques, setMarques] = useState<{ id: number; nom: string }[]>([]);
  const [editingCell, setEditingCell] = useState<{ productId: number; field: string } | null>(null);
  const [editValue, setEditValue] = useState<string>("");
  const [filters, setFilters] = useState({
    fournisseurId: "all",
    marqueId: "all",
    categorieId: "all",
    start: oneYearAgo.format("YYYY-MM-DD"),
    end: today.format("YYYY-MM-DD"),
    searchKeyword: "",
  });

  useEffect(() => {
    if (!userId) {
      return;
    }
    const bootstrap = async () => {
      const [{ data: fournisseursData }, { data: categoriesData }, { data: marquesData }] = await Promise.all([
        supabase.from("fournisseurs").select("id, nom").eq("user_id", userId),
        supabase.from("categories").select("id, nom").eq("user_id", userId),
        supabase.from("marques").select("id, nom").eq("user_id", userId),
      ]);
      setFournisseurs(fournisseursData ?? []);
      setCategories(categoriesData ?? []);
      setMarques(marquesData ?? []);
    };
    bootstrap();
  }, [supabase, userId]);

  useEffect(() => {
    if (!userId) {
      return;
    }
    const fetchInvoices = async () => {
      setIsLoading(true);
      try {
        const query = supabase
          .from("factures")
          .select("id, numero, nom_fichier, date, total_ht, total_ttc, tva_amount, fournisseur_id")
          .eq("user_id", userId)
          .gte("date", filters.start)
          .lte("date", filters.end)
          .order("date", { ascending: false });
        if (filters.fournisseurId !== "all") {
          query.eq("fournisseur_id", Number(filters.fournisseurId));
        }
        const { data, error } = await query;
        if (error) throw error;
        const mapped = (data ?? []).map((row) => ({
          ...row,
          fournisseur_nom: fournisseurs.find((f) => f.id === row.fournisseur_id)?.nom ?? "",
        }));
        setInvoices(mapped);
      } catch (error) {
        console.error(error);
        toast.error("Impossible de charger les factures");
      } finally {
        setIsLoading(false);
      }
    };

    const fetchProducts = async () => {
      setIsLoading(true);
      try {
        const query = supabase
          .from("produits")
          .select("id, reference, designation, fournisseur_id, categorie_id, marque_id")
          .eq("user_id", userId)
          .order("designation");
        if (filters.fournisseurId !== "all") {
          query.eq("fournisseur_id", Number(filters.fournisseurId));
        }
        if (filters.marqueId !== "all") {
          query.eq("marque_id", Number(filters.marqueId));
        }
        if (filters.categorieId !== "all") {
          query.eq("categorie_id", Number(filters.categorieId));
        }
        const { data, error } = await query;
        if (error) throw error;
        const mapped = (data ?? []).map((row) => ({
          ...row,
          fournisseur_nom: fournisseurs.find((f) => f.id === row.fournisseur_id)?.nom ?? "",
          categorie_nom: categories.find((c) => c.id === row.categorie_id)?.nom ?? "",
          marque_nom: marques.find((m) => m.id === row.marque_id)?.nom ?? "",
        }));
        setProducts(mapped);
      } catch (error) {
        console.error(error);
        toast.error("Impossible de charger les produits");
      } finally {
        setIsLoading(false);
      }
    };

    if (mode === "factures") {
      fetchInvoices();
    } else {
      fetchProducts();
    }
    setSelectedIds([]);
  }, [categories, fournisseurs, marques, filters, mode, supabase, userId]);

  const toggleSelection = (id: number) => {
    setSelectedIds((current) => (current.includes(id) ? current.filter((value) => value !== id) : [...current, id]));
  };

  const handleDelete = async () => {
    if (!userId || selectedIds.length === 0) {
      return;
    }
    try {
      await deleteInvoices(userId, selectedIds);
      toast.success("Factures supprimées");
      setFilters((current) => ({ ...current }));
    } catch (error) {
      console.error(error);
      toast.error("Suppression impossible");
    }
  };

  const handleDownload = async () => {
    if (!userId || selectedIds.length === 0) {
      return;
    }
    try {
      const blob = await downloadInvoices(userId, selectedIds);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "factures.zip";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error(error);
      toast.error("Téléchargement impossible");
    }
  };

  const viewInvoice = async (row: InvoiceRow) => {
    if (!userId) {
      return;
    }
    try {
      const path = `${userId}/${row.id}_${row.nom_fichier}`;
      const { data, error } = await supabase.storage.from("invoices").createSignedUrl(path, 3600);
      if (error || !data?.signedUrl) {
        throw error;
      }
      window.open(data.signedUrl, "_blank");
    } catch (error) {
      console.error(error);
      toast.error("Impossible d'ouvrir la facture");
    }
  };

  const handleDeleteProduct = async (productId: number) => {
    if (!userId || !confirm("Êtes-vous sûr de vouloir supprimer ce produit ?")) {
      return;
    }
    try {
      await deleteProduct(userId, productId);
      toast.success("Produit supprimé");
      setFilters((current) => ({ ...current }));
    } catch (error) {
      console.error(error);
      toast.error(error instanceof Error ? error.message : "Suppression impossible");
    }
  };

  const startEditing = (productId: number, field: string, currentValue: string | null) => {
    setEditingCell({ productId, field });
    setEditValue(currentValue || "");
  };

  const cancelEditing = () => {
    setEditingCell(null);
    setEditValue("");
  };

  const saveEdit = async (productId: number, field: string) => {
    if (!userId) {
      return;
    }
    try {
      const updates: Record<string, string | number> = {};

      if (field === "fournisseur_nom" || field === "marque_nom" || field === "categorie_nom") {
        const idField = field.replace("_nom", "_id");
        let entityId: number | undefined;

        if (field === "fournisseur_nom") {
          entityId = fournisseurs.find((f) => f.nom === editValue)?.id;
        } else if (field === "marque_nom") {
          entityId = marques.find((m) => m.nom === editValue)?.id;
        } else if (field === "categorie_nom") {
          entityId = categories.find((c) => c.nom === editValue)?.id;
        }

        if (entityId !== undefined) {
          updates[idField] = entityId;
        }
      } else {
        updates[field] = editValue;
      }

      await updateProduct(userId, productId, updates);
      toast.success("Produit mis à jour");
      setEditingCell(null);
      setEditValue("");
      setFilters((current) => ({ ...current }));
    } catch (error) {
      console.error(error);
      toast.error(error instanceof Error ? error.message : "Mise à jour impossible");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent, productId: number, field: string) => {
    if (e.key === "Enter") {
      saveEdit(productId, field);
    } else if (e.key === "Escape") {
      cancelEditing();
    }
  };

  const invoicesTable = useMemo(() => (
    <div className="overflow-hidden rounded-2xl border border-slate-200">
      <div className="overflow-auto max-h-[calc(100vh-280px)]">
        <table className="w-full">
          <thead className="bg-slate-50 sticky top-0 z-10">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500 bg-slate-50 w-20">Sélection</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500 bg-slate-50">Numéro</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500 bg-slate-50">Fichier</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500 bg-slate-50">Fournisseur</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500 bg-slate-50">Date</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500 bg-slate-50">Total TTC</th>
              <th className="px-4 py-3 bg-slate-50 w-24" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {invoices.map((row) => (
              <tr key={row.id} className="bg-white">
                <td className="px-4 py-3 w-20">
                  <input type="checkbox" checked={selectedIds.includes(row.id)} onChange={() => toggleSelection(row.id)} />
                </td>
                <td className="px-4 py-3 text-sm text-slate-700">{row.numero}</td>
                <td className="px-4 py-3 text-sm text-slate-500">{row.nom_fichier}</td>
                <td className="px-4 py-3 text-sm text-slate-500">{row.fournisseur_nom}</td>
                <td className="px-4 py-3 text-sm text-slate-500">{dayjs(row.date).format("DD/MM/YYYY")}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{(row.total_ttc ?? 0).toLocaleString("fr-FR", { style: "currency", currency: "EUR" })}</td>
                <td className="px-4 py-3 text-right w-24">
                  <button
                    type="button"
                    onClick={() => viewInvoice(row)}
                    className="rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-700"
                  >
                    Voir
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  ), [invoices, selectedIds]);

  const productsTable = useMemo(() => {
    const filteredProducts = products.filter((product) => {
      if (!filters.searchKeyword) return true;
      const keyword = filters.searchKeyword.toLowerCase();
      return (
        (product.reference?.toLowerCase().includes(keyword)) ||
        (product.designation?.toLowerCase().includes(keyword)) ||
        (product.fournisseur_nom?.toLowerCase().includes(keyword)) ||
        (product.marque_nom?.toLowerCase().includes(keyword)) ||
        (product.categorie_nom?.toLowerCase().includes(keyword))
      );
    });

    const renderCell = (row: ProductRow, field: string, value: string | null) => {
      const isEditing = editingCell?.productId === row.id && editingCell?.field === field;
      const isDropdown = field === "fournisseur_nom" || field === "marque_nom" || field === "categorie_nom";

      if (isEditing) {
        if (isDropdown) {
          let options: { id: number; nom: string }[] = [];
          if (field === "fournisseur_nom") options = fournisseurs;
          else if (field === "marque_nom") options = marques;
          else if (field === "categorie_nom") options = categories;

          return (
            <select
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onBlur={() => saveEdit(row.id, field)}
              onKeyDown={(e) => handleKeyDown(e, row.id, field)}
              autoFocus
              className="w-full rounded border border-blue-500 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Sélectionner</option>
              {options.map((opt) => (
                <option key={opt.id} value={opt.nom}>
                  {opt.nom}
                </option>
              ))}
            </select>
          );
        }

        return (
          <input
            type="text"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onBlur={() => saveEdit(row.id, field)}
            onKeyDown={(e) => handleKeyDown(e, row.id, field)}
            autoFocus
            className="w-full rounded border border-blue-500 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        );
      }

      return (
        <span
          onClick={() => startEditing(row.id, field, value)}
          className="cursor-pointer hover:bg-slate-100 block px-2 py-1 rounded"
        >
          {value || "-"}
        </span>
      );
    };

    return (
      <div className="overflow-hidden rounded-2xl border border-slate-200">
        <div className="overflow-auto max-h-[calc(100vh-280px)]">
          <table className="w-full">
            <thead className="bg-slate-50 sticky top-0 z-10">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500 bg-slate-50 w-1/6">Référence</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500 bg-slate-50 w-1/6">Désignation</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500 bg-slate-50 w-1/6">Fournisseur</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500 bg-slate-50 w-1/6">Marque</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500 bg-slate-50 w-1/6">Catégorie</th>
                <th className="px-4 py-3 bg-slate-50 w-1/6" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredProducts.map((row) => (
                <tr key={row.id} className="bg-white hover:bg-slate-50">
                  <td className="px-4 py-3 text-sm text-slate-700 w-1/6">{renderCell(row, "reference", row.reference)}</td>
                  <td className="px-4 py-3 text-sm text-slate-500 w-1/6">{renderCell(row, "designation", row.designation)}</td>
                  <td className="px-4 py-3 text-sm text-slate-500 w-1/6">{renderCell(row, "fournisseur_nom", row.fournisseur_nom)}</td>
                  <td className="px-4 py-3 text-sm text-slate-500 w-1/6">{renderCell(row, "marque_nom", row.marque_nom)}</td>
                  <td className="px-4 py-3 text-sm text-slate-500 w-1/6">{renderCell(row, "categorie_nom", row.categorie_nom)}</td>
                  <td className="px-4 py-3 text-right w-1/6">
                    <button
                      type="button"
                      onClick={() => handleDeleteProduct(row.id)}
                      className="rounded-lg bg-red-500 px-3 py-2 text-xs font-semibold text-white hover:bg-red-600"
                    >
                      Supprimer
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }, [products, filters.searchKeyword, editingCell, editValue, fournisseurs, marques, categories]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="inline-flex rounded-full bg-white p-1 shadow-card">
          <button
            type="button"
            onClick={() => setMode("factures")}
            className={`rounded-full px-4 py-2 text-sm font-semibold ${mode === "factures" ? "bg-brand text-white" : "text-slate-600"}`}
          >
            Factures
          </button>
          <button
            type="button"
            onClick={() => setMode("produits")}
            className={`rounded-full px-4 py-2 text-sm font-semibold ${mode === "produits" ? "bg-brand text-white" : "text-slate-600"}`}
          >
            Produits
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <select
            value={filters.fournisseurId}
            onChange={(event) => setFilters((current) => ({ ...current, fournisseurId: event.target.value }))}
            className="rounded-xl border border-slate-200 px-4 py-2 text-sm focus:border-brand focus:outline-none"
          >
            <option value="all">Tous les fournisseurs</option>
            {fournisseurs.map((item) => (
              <option key={item.id} value={item.id}>
                {item.nom}
              </option>
            ))}
          </select>
          {mode === "produits" && (
            <>
              <select
                value={filters.marqueId}
                onChange={(event) => setFilters((current) => ({ ...current, marqueId: event.target.value }))}
                className="rounded-xl border border-slate-200 px-4 py-2 text-sm focus:border-brand focus:outline-none"
              >
                <option value="all">Toutes les marques</option>
                {marques.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.nom}
                  </option>
                ))}
              </select>
              <select
                value={filters.categorieId}
                onChange={(event) => setFilters((current) => ({ ...current, categorieId: event.target.value }))}
                className="rounded-xl border border-slate-200 px-4 py-2 text-sm focus:border-brand focus:outline-none"
              >
                <option value="all">Toutes les catégories</option>
                {categories.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.nom}
                  </option>
                ))}
              </select>
              <input
                type="text"
                value={filters.searchKeyword}
                onChange={(event) => setFilters((current) => ({ ...current, searchKeyword: event.target.value }))}
                placeholder="Rechercher..."
                className="rounded-xl border border-slate-200 px-4 py-2 text-sm focus:border-brand focus:outline-none"
              />
            </>
          )}
          {mode === "factures" && (
            <div className="flex items-center gap-2 rounded-2xl bg-white px-4 py-2 shadow-card">
              <input
                type="date"
                value={filters.start}
                onChange={(event) => setFilters((current) => ({ ...current, start: event.target.value }))}
                className="rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand focus:outline-none"
              />
              <span className="text-sm text-slate-500">→</span>
              <input
                type="date"
                value={filters.end}
                onChange={(event) => setFilters((current) => ({ ...current, end: event.target.value }))}
                className="rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand focus:outline-none"
              />
            </div>
          )}
        </div>
      </div>

      {mode === "factures" && (
        <div className="space-y-4">
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={handleDownload}
              disabled={selectedIds.length === 0}
              className="rounded-xl border border-slate-200 px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 disabled:opacity-50"
            >
              Télécharger
            </button>
            <button
              type="button"
              onClick={handleDelete}
              disabled={selectedIds.length === 0}
              className="rounded-xl bg-red-500 px-4 py-2 text-sm font-semibold text-white hover:bg-red-600 disabled:opacity-50"
            >
              Supprimer
            </button>
          </div>
          {invoicesTable}
        </div>
      )}

      {mode === "produits" && productsTable}

      {isLoading && <div className="text-sm text-slate-500">Chargement...</div>}
    </div>
  );
};
