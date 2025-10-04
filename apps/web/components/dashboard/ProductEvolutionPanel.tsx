"use client";

import { useEffect, useState } from "react";
import toast from "react-hot-toast";

import { useSupabase } from "../../hooks/useSupabase";
import { fetchProductEvolution, ProductEvolutionData } from "../../lib/api/dashboard";
import { PlotlyChart } from "../charts/PlotlyChart";
import { MetricSelector } from "./MetricSelector";
import { ProductSelectionTable } from "./ProductSelectionTable";

interface ProductEvolutionPanelProps {
  startDate: string;
  endDate: string;
}

const CHART_COLORS = [
  "#008080", // Brand teal
  "#FF6B6B", // Red
  "#4ECDC4", // Light teal
  "#FFE66D", // Yellow
  "#95E1D3", // Mint
  "#F38181", // Pink
  "#AA96DA", // Purple
  "#FCBAD3", // Light pink
  "#A8E6CF", // Light green
  "#FFD3B6", // Peach
];

export const ProductEvolutionPanel = ({ startDate, endDate }: ProductEvolutionPanelProps) => {
  const { session } = useSupabase();
  const userId = session?.user.id;

  const [selectedProductIds, setSelectedProductIds] = useState<number[]>([]);
  const [metric, setMetric] = useState<"unit_price" | "quantity" | "amount">("unit_price");
  const [evolutionData, setEvolutionData] = useState<ProductEvolutionData | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!userId || selectedProductIds.length === 0) {
      setEvolutionData(null);
      return;
    }

    const fetchData = async () => {
      try {
        setIsLoading(true);
        const data = await fetchProductEvolution(userId, selectedProductIds, metric, startDate, endDate);
        setEvolutionData(data);
      } catch (error) {
        console.error(error);
        toast.error("Impossible de récupérer les données d'évolution");
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [userId, selectedProductIds, metric, startDate, endDate]);

  const getMetricLabel = () => {
    switch (metric) {
      case "unit_price":
        return "Prix Unitaire (€)";
      case "quantity":
        return "Quantité";
      case "amount":
        return "Montant (€)";
    }
  };

  const chartData = evolutionData?.series.map((series, index) => {
    let name = series.productName;
    if (series.supplierName || series.collisage) {
      const parts = [];
      if (series.supplierName) parts.push(series.supplierName);
      if (series.collisage) parts.push(`x${series.collisage}`);
      name = `${series.productName} (${parts.join(" - ")})`;
    }
    return {
      type: "scatter" as const,
      mode: "lines+markers" as const,
      name,
      x: series.dataPoints.map((point) => point.date),
      y: series.dataPoints.map((point) => point.value),
    customdata: series.dataPoints.map((point) => [
      point.unitPrice ?? 0,
      point.quantity ?? 0,
      point.amount ?? 0,
    ]),
    hovertemplate:
      "<b>%{fullData.name}</b><br>" +
      "Mois: %{x}<br>" +
      "Prix Unitaire: %{customdata[0]:.2f} €<br>" +
      "Quantité: %{customdata[1]:.0f}<br>" +
      "Montant: %{customdata[2]:.2f} €<br>" +
      "<extra></extra>",
    line: {
      color: CHART_COLORS[index % CHART_COLORS.length],
      width: 2,
    },
    marker: {
      color: CHART_COLORS[index % CHART_COLORS.length],
      size: 6,
    },
    };
  }) || [];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
      {/* Left: Product Selection */}
      <div className="lg:col-span-1 flex flex-col">
        <div className="card bg-white flex-1">
          <h3 className="mb-4 text-lg font-semibold text-slate-900">Sélection des produits</h3>
          <ProductSelectionTable
            selectedIds={selectedProductIds}
            onSelectionChange={setSelectedProductIds}
            maxSelection={10}
          />
        </div>
      </div>

      {/* Right: Chart + Controls */}
      <div className="lg:col-span-2 flex flex-col gap-4">
        {/* Controls */}
        <div className="card bg-white flex items-center justify-between">
          <MetricSelector value={metric} onChange={setMetric} />
          {selectedProductIds.length > 0 && (
            <button
              type="button"
              onClick={() => setSelectedProductIds([])}
              className="text-sm text-slate-600 hover:text-slate-900"
            >
              Tout désélectionner
            </button>
          )}
        </div>

        {/* Chart */}
        <div className="card bg-white flex-1 flex flex-col" style={{ minHeight: "600px" }}>
          {isLoading ? (
            <div className="flex h-full items-center justify-center text-slate-500">
              Chargement des données...
            </div>
          ) : selectedProductIds.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <svg
                className="mb-4 h-16 w-16 text-slate-300"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                />
              </svg>
              <p className="text-lg font-medium text-slate-600">Sélectionnez des produits</p>
              <p className="mt-1 text-sm text-slate-500">
                Choisissez jusqu&apos;à 10 produits dans la liste pour visualiser leur évolution
              </p>
            </div>
          ) : evolutionData && chartData.length > 0 ? (
            <PlotlyChart
              data={chartData}
              layout={{
                title: {
                  text: `Évolution - ${getMetricLabel()}`,
                  font: { size: 18, color: "#0f172a" },
                },
                xaxis: {
                  title: { text: "Mois" },
                  type: "category",
                  gridcolor: "#e2e8f0",
                },
                yaxis: {
                  title: { text: getMetricLabel() },
                  gridcolor: "#e2e8f0",
                },
                margin: { t: 60, r: 24, l: 60, b: 60 },
                hovermode: "closest",
                showlegend: true,
                legend: {
                  orientation: "h",
                  yanchor: "bottom",
                  y: -0.3,
                  xanchor: "center",
                  x: 0.5,
                },
              }}
              config={{
                displaylogo: false,
                responsive: true,
                locale: "fr",
              }}
            />
          ) : (
            <div className="flex h-full items-center justify-center text-slate-500">
              Aucune donnée disponible pour la période sélectionnée
            </div>
          )}
        </div>
      </div>
    </div>
  );
};