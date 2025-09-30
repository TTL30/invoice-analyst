"use client";

import dynamic from "next/dynamic";
import type { Config, Data, Layout } from "plotly.js";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface PlotlyChartProps {
  data: Partial<Data>[];
  layout?: Partial<Layout>;
  config?: Partial<Config>;
}

export const PlotlyChart = ({ data, layout, config }: PlotlyChartProps) => {
  return (
    <Plot
      data={data}
      layout={{ margin: { t: 40, r: 24, l: 48, b: 48 }, autosize: true, ...layout }}
      config={{ displaylogo: false, responsive: true, ...config }}
      style={{ width: "100%", height: "100%" }}
      useResizeHandler
    />
  );
};
