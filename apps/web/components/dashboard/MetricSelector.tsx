"use client";

interface MetricSelectorProps {
  value: "unit_price" | "quantity" | "amount";
  onChange: (metric: "unit_price" | "quantity" | "amount") => void;
}

export const MetricSelector = ({ value, onChange }: MetricSelectorProps) => {
  return (
    <div className="flex items-center gap-2">
      <span className="text-sm font-medium text-slate-700">Métrique :</span>
      <div className="inline-flex rounded-lg bg-slate-100 p-1">
        <button
          type="button"
          onClick={() => onChange("unit_price")}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            value === "unit_price"
              ? "bg-white text-brand shadow-sm"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          Prix Unitaire
        </button>
        <button
          type="button"
          onClick={() => onChange("quantity")}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            value === "quantity"
              ? "bg-white text-brand shadow-sm"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          Quantité
        </button>
        <button
          type="button"
          onClick={() => onChange("amount")}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            value === "amount"
              ? "bg-white text-brand shadow-sm"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          Montant
        </button>
      </div>
    </div>
  );
};