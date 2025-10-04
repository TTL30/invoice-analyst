"use client";

import { useEffect, useMemo, useState } from "react";
import { useSupabase } from "../../hooks/useSupabase";

interface Product {
  id: number;
  reference: string | null;
  designation: string | null;
  fournisseur_id: number | null;
  categorie_id: number | null;
  marque_id: number | null;
  collisage?: number | null;
  fournisseur_nom?: string;
  categorie_nom?: string;
  marque_nom?: string;
}

interface ProductSelectionTableProps {
  selectedIds: number[];
  onSelectionChange: (ids: number[]) => void;
  maxSelection?: number;
}

export const ProductSelectionTable = ({
  selectedIds,
  onSelectionChange,
  maxSelection = 10,
}: ProductSelectionTableProps) => {
  const { supabase, session } = useSupabase();
  const userId = session?.user.id;

  const [products, setProducts] = useState<Product[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [fournisseurs, setFournisseurs] = useState<{ id: number; nom: string }[]>([]);
  const [categories, setCategories] = useState<{ id: number; nom: string }[]>([]);
  const [marques, setMarques] = useState<{ id: number; nom: string }[]>([]);
  const [filters, setFilters] = useState({
    fournisseurId: "all",
    marqueId: "all",
    categorieId: "all",
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

        // Fetch packaging (collisage) from lignes_facture
        const productIds = (data ?? []).map((p) => p.id);
        let packagingMap: Record<number, number> = {};

        if (productIds.length > 0) {
          const { data: linesData } = await supabase
            .from("lignes_facture")
            .select("produit_id, collisage")
            .in("produit_id", productIds)
            .eq("user_id", userId)
            .not("collisage", "is", null);

          // Get most recent non-null collisage for each product
          const collisageByProduct: Record<number, number[]> = {};
          (linesData ?? []).forEach((line) => {
            const pid = line.produit_id;
            if (pid && line.collisage != null) {
              if (!collisageByProduct[pid]) collisageByProduct[pid] = [];
              collisageByProduct[pid].push(line.collisage);
            }
          });

          // Use the most common collisage value
          packagingMap = Object.fromEntries(
            Object.entries(collisageByProduct).map(([pid, values]) => [
              pid,
              values[values.length - 1], // Use last value (most recent)
            ])
          );
        }

        const mapped = (data ?? []).map((row) => ({
          ...row,
          fournisseur_nom: fournisseurs.find((f) => f.id === row.fournisseur_id)?.nom ?? "",
          categorie_nom: categories.find((c) => c.id === row.categorie_id)?.nom ?? "",
          marque_nom: marques.find((m) => m.id === row.marque_id)?.nom ?? "",
          collisage: packagingMap[row.id] ?? null,
        }));
        setProducts(mapped);
      } catch (error) {
        console.error(error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchProducts();
  }, [categories, fournisseurs, marques, filters, supabase, userId]);

  const filteredProducts = useMemo(() => {
    if (!filters.searchKeyword) return products;
    const keyword = filters.searchKeyword.toLowerCase();
    return products.filter(
      (product) =>
        product.reference?.toLowerCase().includes(keyword) ||
        product.designation?.toLowerCase().includes(keyword) ||
        product.fournisseur_nom?.toLowerCase().includes(keyword) ||
        product.marque_nom?.toLowerCase().includes(keyword) ||
        product.categorie_nom?.toLowerCase().includes(keyword)
    );
  }, [products, filters.searchKeyword]);

  const toggleSelection = (id: number) => {
    if (selectedIds.includes(id)) {
      onSelectionChange(selectedIds.filter((value) => value !== id));
    } else if (selectedIds.length < maxSelection) {
      onSelectionChange([...selectedIds, id]);
    }
  };

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="space-y-3">
        <input
          type="text"
          value={filters.searchKeyword}
          onChange={(e) => setFilters((current) => ({ ...current, searchKeyword: e.target.value }))}
          placeholder="Rechercher un produit..."
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand focus:outline-none"
        />
        <select
          value={filters.fournisseurId}
          onChange={(e) => setFilters((current) => ({ ...current, fournisseurId: e.target.value }))}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand focus:outline-none"
        >
          <option value="all">Tous les fournisseurs</option>
          {fournisseurs.map((item) => (
            <option key={item.id} value={item.id}>
              {item.nom}
            </option>
          ))}
        </select>
        <select
          value={filters.marqueId}
          onChange={(e) => setFilters((current) => ({ ...current, marqueId: e.target.value }))}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand focus:outline-none"
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
          onChange={(e) => setFilters((current) => ({ ...current, categorieId: e.target.value }))}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand focus:outline-none"
        >
          <option value="all">Toutes les catégories</option>
          {categories.map((item) => (
            <option key={item.id} value={item.id}>
              {item.nom}
            </option>
          ))}
        </select>
      </div>

      {/* Selection counter */}
      <div className="text-sm text-slate-600">
        {selectedIds.length} / {maxSelection} produits sélectionnés
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-lg border border-slate-200">
        <div className="max-h-96 overflow-auto">
          <table className="w-full">
            <thead className="sticky top-0 bg-slate-50">
              <tr>
                <th className="bg-slate-50 px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500">
                  <input
                    type="checkbox"
                    checked={selectedIds.length === filteredProducts.length && filteredProducts.length > 0}
                    onChange={() => {
                      if (selectedIds.length === filteredProducts.length) {
                        onSelectionChange([]);
                      } else {
                        onSelectionChange(filteredProducts.slice(0, maxSelection).map((p) => p.id));
                      }
                    }}
                  />
                </th>
                <th className="bg-slate-50 px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500">
                  Référence
                </th>
                <th className="bg-slate-50 px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500">
                  Désignation
                </th>
                <th className="bg-slate-50 px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500">
                  Collisage
                </th>
                <th className="bg-slate-50 px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500">
                  Fournisseur
                </th>
                <th className="bg-slate-50 px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500">
                  Marque
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="px-3 py-4 text-center text-sm text-slate-500">
                    Chargement...
                  </td>
                </tr>
              ) : filteredProducts.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-3 py-4 text-center text-sm text-slate-500">
                    Aucun produit trouvé
                  </td>
                </tr>
              ) : (
                filteredProducts.map((product) => (
                  <tr
                    key={product.id}
                    className={`cursor-pointer hover:bg-slate-50 ${
                      selectedIds.includes(product.id) ? "bg-brand/5" : "bg-white"
                    }`}
                    onClick={() => toggleSelection(product.id)}
                  >
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(product.id)}
                        onChange={() => toggleSelection(product.id)}
                        disabled={!selectedIds.includes(product.id) && selectedIds.length >= maxSelection}
                      />
                    </td>
                    <td className="px-3 py-2 text-sm text-slate-700">{product.reference || "-"}</td>
                    <td className="px-3 py-2 text-sm text-slate-600">{product.designation || "-"}</td>
                    <td className="px-3 py-2 text-sm text-slate-500">{product.collisage ?? "-"}</td>
                    <td className="px-3 py-2 text-sm text-slate-500">{product.fournisseur_nom || "-"}</td>
                    <td className="px-3 py-2 text-sm text-slate-500">{product.marque_nom || "-"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};