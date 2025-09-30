"use client";

import { useEffect, useState } from "react";
import dayjs from "dayjs";
import toast from "react-hot-toast";

import { useSupabase } from "../../hooks/useSupabase";
import { PlotlyChart } from "../charts/PlotlyChart";
import { fetchGlobalDashboard, GlobalDashboardData } from "../../lib/api/dashboard";
import { ProductEvolutionPanel } from "./ProductEvolutionPanel";

interface DateRange {
  start: string;
  end: string;
}

const today = dayjs();
const oneYearAgo = today.subtract(1, "year");

export const DashboardTabs = () => {
  const { session } = useSupabase();
  const [activeTab, setActiveTab] = useState<"global" | "products" | "anomalies">("global");
  const [range, setRange] = useState<DateRange>({ start: oneYearAgo.format("YYYY-MM-DD"), end: today.format("YYYY-MM-DD") });
  const [isLoading, setIsLoading] = useState(false);
  const [dashboardData, setDashboardData] = useState<GlobalDashboardData | null>(null);

  const userId = session?.user.id;

  useEffect(() => {
    if (!userId) {
      return;
    }
    const fetchData = async () => {
      try {
        setIsLoading(true);
        const data = await fetchGlobalDashboard(userId, range.start, range.end);
        setDashboardData(data);
      } catch (error) {
        console.error(error);
        toast.error("Impossible de récupérer les données du dashboard");
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [range.end, range.start, userId]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="inline-flex rounded-full bg-white p-1 shadow-card">
          <button
            type="button"
            onClick={() => setActiveTab("global")}
            className={`rounded-full px-4 py-2 text-sm font-semibold ${activeTab === "global" ? "bg-brand text-white" : "text-slate-600"}`}
          >
            Global
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("products")}
            className={`rounded-full px-4 py-2 text-sm font-semibold ${activeTab === "products" ? "bg-brand text-white" : "text-slate-600"}`}
          >
            Produits
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("anomalies")}
            className={`rounded-full px-4 py-2 text-sm font-semibold ${activeTab === "anomalies" ? "bg-brand text-white" : "text-slate-600"}`}
          >
            Anomalies
          </button>
        </div>
        <div className="flex items-center gap-2 rounded-2xl bg-white px-4 py-2 shadow-card">
          <input
            type="date"
            value={range.start}
            onChange={(event) => setRange((current) => ({ ...current, start: event.target.value }))}
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand focus:outline-none"
          />
          <span className="text-sm text-slate-500">→</span>
          <input
            type="date"
            value={range.end}
            onChange={(event) => setRange((current) => ({ ...current, end: event.target.value }))}
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand focus:outline-none"
          />
        </div>
      </div>

      {activeTab === "global" && dashboardData && (
        <div className="space-y-6">
          {/* KPI Cards */}
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            <div className="card flex flex-col items-start justify-center bg-white text-left">
              <p className="text-sm font-medium uppercase tracking-widest text-slate-500">Total Dépenses</p>
              <div className="mt-3 flex items-baseline gap-2">
                <p className="text-4xl font-bold text-brand">{dashboardData.totalTtc.toLocaleString("fr-FR", { style: "currency", currency: "EUR" })}</p>
                <span className={`text-sm font-semibold ${dashboardData.totalTtcChange >= 0 ? "text-red-600" : "text-green-600"}`}>
                  {dashboardData.totalTtcChange >= 0 ? "+" : ""}{dashboardData.totalTtcChange.toFixed(1)}%
                </span>
              </div>
              <p className="mt-2 text-sm text-slate-500">vs période précédente</p>
            </div>
            <div className="card flex flex-col items-start justify-center bg-white text-left">
              <p className="text-sm font-medium uppercase tracking-widest text-slate-500">Nombre de Factures</p>
              <div className="mt-3 flex items-baseline gap-2">
                <p className="text-4xl font-bold text-brand">{dashboardData.invoiceCount}</p>
                <span className={`text-sm font-semibold ${dashboardData.invoiceCountChange >= 0 ? "text-green-600" : "text-red-600"}`}>
                  {dashboardData.invoiceCountChange >= 0 ? "+" : ""}{dashboardData.invoiceCountChange.toFixed(1)}%
                </span>
              </div>
              <p className="mt-2 text-sm text-slate-500">vs période précédente</p>
            </div>
            <div className="card flex flex-col items-start justify-center bg-white text-left">
              <p className="text-sm font-medium uppercase tracking-widest text-slate-500">Montant Moyen</p>
              <div className="mt-3 flex items-baseline gap-2">
                <p className="text-4xl font-bold text-brand">{dashboardData.avgInvoiceAmount.toLocaleString("fr-FR", { style: "currency", currency: "EUR" })}</p>
                <span className={`text-sm font-semibold ${dashboardData.avgInvoiceAmountChange >= 0 ? "text-red-600" : "text-green-600"}`}>
                  {dashboardData.avgInvoiceAmountChange >= 0 ? "+" : ""}{dashboardData.avgInvoiceAmountChange.toFixed(1)}%
                </span>
              </div>
              <p className="mt-2 text-sm text-slate-500">vs période précédente</p>
            </div>
            <div className="card flex flex-col items-start justify-center bg-white text-left">
              <p className="text-sm font-medium uppercase tracking-widest text-slate-500">Fournisseurs Actifs</p>
              <div className="mt-3 flex items-baseline gap-2">
                <p className="text-4xl font-bold text-brand">{dashboardData.activeSuppliers}</p>
                <span className={`text-sm font-semibold ${dashboardData.activeSuppliersChange >= 0 ? "text-green-600" : "text-red-600"}`}>
                  {dashboardData.activeSuppliersChange >= 0 ? "+" : ""}{dashboardData.activeSuppliersChange.toFixed(1)}%
                </span>
              </div>
              <p className="mt-2 text-sm text-slate-500">vs période précédente</p>
            </div>
          </div>

          {/* Main Charts */}
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Temporal Evolution */}
            <div className="card">
              <PlotlyChart
                data={[
                  {
                    type: "scatter",
                    mode: "lines+markers",
                    x: dashboardData.monthlyTotals.map((item) => item.month),
                    y: dashboardData.monthlyTotals.map((item) => item.total),
                    marker: { color: "#008080" },
                    line: { color: "#008080", width: 3 },
                  },
                ]}
                layout={{
                  title: {
                    text: "Évolution des factures mensuelles",
                    font: { size: 18, color: "#0f172a" }
                  },
                  margin: { t: 60, r: 24, l: 60, b: 48 }
                }}
              />
            </div>

            {/* Category Pie Chart */}
            <div className="card">
              <PlotlyChart
                data={[
                  {
                    type: "pie",
                    labels: dashboardData.categorySpending.map((item) => item.categorie),
                    values: dashboardData.categorySpending.map((item) => item.total),
                    marker: {
                      colors: ["#008080", "#32a8a8", "#5cb8b8", "#86c8c8", "#b0d8d8", "#daeaea", "#f0f9f9"],
                    },
                  },
                ]}
                layout={{
                  title: {
                    text: "Répartition des catégories",
                    font: { size: 18, color: "#0f172a" }
                  },
                  margin: { t: 60, r: 24, l: 24, b: 48 }
                }}
              />
            </div>
          </div>
        </div>
      )}

      {activeTab === "products" && (
        <ProductEvolutionPanel startDate={range.start} endDate={range.end} />
      )}

      {activeTab === "anomalies" && (
        <div className="card h-[600px] flex items-center justify-center text-slate-500">
          Détection d&apos;anomalies en cours de conception
        </div>
      )}

      {isLoading && <div className="text-sm text-slate-500">Chargement des données...</div>}
    </div>
  );
};