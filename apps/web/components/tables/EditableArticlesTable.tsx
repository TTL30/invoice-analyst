"use client";

import { ArticleRow } from "../../types/invoice";

const numericKeys: (keyof ArticleRow)[] = ["Prix Unitaire", "Packaging", "Quantité", "Total"];
const textKeys: (keyof ArticleRow)[] = ["Reference", "Désignation"];

interface EditableArticlesTableProps {
  articles: ArticleRow[];
  onChange: (articles: ArticleRow[]) => void;
  categories: string[];
  marques: string[];
}

export const EditableArticlesTable = ({ articles, onChange, categories, marques }: EditableArticlesTableProps) => {
  const updateArticle = (index: number, key: keyof ArticleRow, value: string) => {
    const next = [...articles];
    if (numericKeys.includes(key)) {
      const parsed = value === "" ? null : Number(value);
      next[index] = { ...next[index], [key]: isNaN(parsed as number) ? null : parsed };
    } else {
      next[index] = { ...next[index], [key]: value };
    }
    onChange(next);
  };

  const addRow = () => {
    onChange([...articles, {}]);
  };

  const removeRow = (index: number) => {
    const next = articles.filter((_, i) => i !== index);
    onChange(next.length ? next : [{}]);
  };

  return (
    <div className="card h-full flex flex-col !p-0">
      <div className="overflow-auto flex-1">
        <table className="w-full table-fixed divide-y divide-gray-100">
        <thead className="bg-gray-50 sticky top-0 z-10">
          <tr>
            <th className="w-[10%] px-2 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-700 bg-gray-50">Référence</th>
            <th className="w-[20%] px-2 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-700 bg-gray-50">Désignation</th>
            <th className="w-[10%] px-2 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-700 bg-gray-50">Prix Unit.</th>
            <th className="w-[8%] px-2 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-700 bg-gray-50">Pack.</th>
            <th className="w-[8%] px-2 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-700 bg-gray-50">Qté</th>
            <th className="w-[10%] px-2 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-700 bg-gray-50">Total</th>
            <th className="w-[12%] px-2 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-700 bg-gray-50">Marque</th>
            <th className="w-[12%] px-2 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-700 bg-gray-50">Catégorie</th>
            <th className="w-[10%] px-2 py-3 bg-gray-50" />
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {articles.map((article, index) => {
            // Apply color based on validation status from PDF annotation
            let rowBgClass = "bg-white";
            if (article.validationStatus === "correct") {
              rowBgClass = "bg-green-50"; // Green like PDF (0.0, 0.5, 0.0) with opacity
            } else if (article.validationStatus === "error") {
              rowBgClass = "bg-red-50"; // Red like PDF (1.0, 0.0, 0.0) with opacity
            }

            return (
            <tr key={index} className={rowBgClass} title={article.validationStatus === "error" && article.missingFields ? `Potential issues with: ${article.missingFields.join(", ")}` : undefined}>
              {textKeys.map((key) => (
                <td key={key as string} className="px-2 py-2">
                  <input
                    type="text"
                    value={(article[key] as string | null | undefined) ?? ""}
                    onChange={(event) => updateArticle(index, key, event.target.value)}
                    className="w-full rounded border border-gray-300 px-2 py-1 text-xs focus:border-teal-600 focus:outline-none"
                  />
                </td>
              ))}
              {numericKeys.map((key) => (
                <td key={key as string} className="px-2 py-2">
                  <input
                    type="number"
                    value={(article[key] as number | null | undefined) ?? ""}
                    onChange={(event) => updateArticle(index, key, event.target.value)}
                    className="w-full rounded border border-gray-300 px-2 py-1 text-xs focus:border-teal-600 focus:outline-none"
                    step="0.01"
                  />
                </td>
              ))}
              <td className="px-2 py-2">
                <input
                  type="text"
                  value={article.Marque ?? ""}
                  onChange={(event) => updateArticle(index, "Marque", event.target.value)}
                  list="marques-list"
                  className="w-full rounded border border-gray-300 px-2 py-1 text-xs focus:border-teal-600 focus:outline-none"
                />
              </td>
              <td className="px-2 py-2">
                <select
                  value={article["Catégorie"] ?? ""}
                  onChange={(event) => updateArticle(index, "Catégorie", event.target.value)}
                  className="w-full rounded border border-gray-300 px-2 py-1 text-xs focus:border-teal-600 focus:outline-none"
                >
                  <option value="">-</option>
                  {categories.map((category) => (
                    <option key={category} value={category}>
                      {category}
                    </option>
                  ))}
                </select>
              </td>
              <td className="px-2 py-2 text-center">
                <button
                  type="button"
                  onClick={() => removeRow(index)}
                  className="rounded bg-red-50 px-2 py-1 text-xs font-semibold text-red-600 hover:bg-red-100 whitespace-nowrap"
                >
                  ✕
                </button>
              </td>
            </tr>
          )})}
        </tbody>
      </table>
      </div>
      <datalist id="marques-list">
        {marques.map((marque) => (
          <option key={marque} value={marque} />
        ))}
      </datalist>
      <div className="border-t border-gray-200 bg-gray-50 px-4 py-3 text-right">
        <button
          type="button"
          onClick={addRow}
          className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700"
        >
          Ajouter un article
        </button>
      </div>
    </div>
  );
};
