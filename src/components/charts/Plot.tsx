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

const TOOLTIP_STYLE: Record<string, string> = {
  background: "var(--surface-2)",
  border: "1px solid var(--border)",
  borderRadius: "0",
  fontSize: "11px",
};

export function Plot({ data, xKey, lines, type = "line", height = 160, yLabel }: PlotProps) {
  const chart =
    type === "bar" ? (
      <BarChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="var(--border)" />
        <XAxis
          dataKey={xKey}
          tick={{ fontSize: 9, fill: "var(--muted-foreground)", fontFamily: "IBM Plex Mono" }}
        />
        <YAxis
          tick={{ fontSize: 9, fill: "var(--muted-foreground)", fontFamily: "IBM Plex Mono" }}
          label={
            yLabel
              ? {
                  value: yLabel,
                  angle: -90,
                  position: "insideLeft",
                  style: {
                    fill: "var(--muted-foreground)",
                    fontSize: 9,
                    fontFamily: "IBM Plex Mono",
                  },
                }
              : undefined
          }
        />
        <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: "var(--foreground)" }} />
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
        <CartesianGrid stroke="var(--border)" />
        <XAxis
          dataKey={xKey}
          tick={{ fontSize: 9, fill: "var(--muted-foreground)", fontFamily: "IBM Plex Mono" }}
        />
        <YAxis
          tick={{ fontSize: 9, fill: "var(--muted-foreground)", fontFamily: "IBM Plex Mono" }}
          label={
            yLabel
              ? {
                  value: yLabel,
                  angle: -90,
                  position: "insideLeft",
                  style: {
                    fill: "var(--muted-foreground)",
                    fontSize: 9,
                    fontFamily: "IBM Plex Mono",
                  },
                }
              : undefined
          }
        />
        <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: "var(--foreground)" }} />
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
