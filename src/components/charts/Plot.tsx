import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { ReactNode } from "react";

interface PlotProps {
  data: Record<string, unknown>[];
  xKey: string;
  lines: { key: string; color?: string; name?: string }[];
  type?: "line" | "bar";
  height?: number;
  yLabel?: string;
  children?: ReactNode;
}

const TOOLTIP_STYLE = {
  background: "oklch(0.19 0.005 250)",
  border: "1px solid oklch(1 0 0 / 10%)",
  borderRadius: 2,
  fontSize: 11,
};

export function Plot({ data, xKey, lines, type = "line", height = 160, yLabel }: PlotProps) {
  const chart =
    type === "bar" ? (
      <BarChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="oklch(1 0 0 / 6%)" />
        <XAxis dataKey={xKey} tick={{ fontSize: 9, fill: "oklch(0.65 0.01 250)" }} />
        <YAxis
          tick={{ fontSize: 9, fill: "oklch(0.65 0.01 250)" }}
          label={
            yLabel
              ? {
                  value: yLabel,
                  angle: -90,
                  position: "insideLeft",
                  style: { fill: "oklch(0.65 0.01 250)", fontSize: 9 },
                }
              : undefined
          }
        />
        <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: "oklch(0.95 0.005 250)" }} />
        {lines.map((l) => (
          <Bar
            key={l.key}
            dataKey={l.key}
            fill={l.color ?? "var(--primary)"}
            name={l.name ?? l.key}
          />
        ))}
      </BarChart>
    ) : (
      <LineChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="oklch(1 0 0 / 6%)" />
        <XAxis dataKey={xKey} tick={{ fontSize: 9, fill: "oklch(0.65 0.01 250)" }} />
        <YAxis
          tick={{ fontSize: 9, fill: "oklch(0.65 0.01 250)" }}
          label={
            yLabel
              ? {
                  value: yLabel,
                  angle: -90,
                  position: "insideLeft",
                  style: { fill: "oklch(0.65 0.01 250)", fontSize: 9 },
                }
              : undefined
          }
        />
        <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: "oklch(0.95 0.005 250)" }} />
        {lines.map((l) => (
          <Line
            key={l.key}
            type="monotone"
            dataKey={l.key}
            stroke={l.color ?? "var(--primary)"}
            dot={false}
            strokeWidth={1}
            name={l.name ?? l.key}
          />
        ))}
      </LineChart>
    );

  return (
    <ResponsiveContainer width="100%" height={height}>
      {chart}
    </ResponsiveContainer>
  );
}
