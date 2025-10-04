import { API_BASE_URL, API_KEY } from "../env";

export interface MonthlyTotal {
  month: string;
  total: number;
}

export interface InvoiceVolume {
  month: string;
  count: number;
}

export interface SupplierTotal {
  fournisseur: string;
  total: number;
}

export interface ProductQuantity {
  designation: string;
  quantite: number;
}

export interface CategorySpending {
  categorie: string;
  total: number;
}

export interface BrandSpending {
  marque: string;
  total: number;
}

export interface GlobalDashboardData {
  totalTtc: number;
  invoiceCount: number;
  avgInvoiceAmount: number;
  activeSuppliers: number;
  totalTtcChange: number;
  invoiceCountChange: number;
  avgInvoiceAmountChange: number;
  activeSuppliersChange: number;
  monthlyTotals: MonthlyTotal[];
  invoiceVolume: InvoiceVolume[];
  supplierTotals: SupplierTotal[];
  supplierConcentration: SupplierTotal[];
  topProducts: ProductQuantity[];
  categorySpending: CategorySpending[];
  topBrands: BrandSpending[];
  momChange: number;
}

export const fetchGlobalDashboard = async (
  userId: string,
  startDate: string,
  endDate: string
): Promise<GlobalDashboardData> => {
  const response = await fetch(`${API_BASE_URL}/dashboard/global`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(API_KEY && { "X-API-Key": API_KEY }),
    },
    body: JSON.stringify({
      userId,
      startDate,
      endDate,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || "Impossible de récupérer les données du dashboard");
  }

  return response.json() as Promise<GlobalDashboardData>;
};

export interface TimeDataPoint {
  date: string;
  value: number;
  unitPrice?: number | null;
  quantity?: number | null;
  amount?: number | null;
}

export interface ProductTimeSeries {
  productId: number;
  productName: string;
  supplierName?: string;
  unite?: string;
  collisage?: number;
  dataPoints: TimeDataPoint[];
}

export interface ProductEvolutionData {
  series: ProductTimeSeries[];
}

export const fetchProductEvolution = async (
  userId: string,
  productIds: number[],
  metric: "unit_price" | "quantity" | "amount",
  startDate: string,
  endDate: string
): Promise<ProductEvolutionData> => {
  const response = await fetch(`${API_BASE_URL}/dashboard/product-evolution`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(API_KEY && { "X-API-Key": API_KEY }),
    },
    body: JSON.stringify({
      userId,
      productIds,
      metric,
      startDate,
      endDate,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || "Impossible de récupérer les données d'évolution des produits");
  }

  return response.json() as Promise<ProductEvolutionData>;
};