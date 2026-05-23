import { createFileRoute } from "@tanstack/react-router";

// Same-origin proxy for Celestrak GP TLEs. Lets the offline SGP4 fallback
// run without hitting Celestrak's CORS-less endpoint directly.

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Accept",
  "Cache-Control": "public, s-maxage=3600, max-age=600",
} as const;

export const Route = createFileRoute("/api/public/tle")({
  server: {
    handlers: {
      OPTIONS: async () => new Response(null, { status: 204, headers: CORS }),
      GET: async ({ request }) => {
        const u = new URL(request.url);
        const raw = u.searchParams.get("group") ?? "active";
        const group = /^[a-z0-9-]{1,32}$/i.test(raw) ? raw : "active";
        try {
          const upstream = await fetch(
            `https://celestrak.org/NORAD/elements/gp.php?GROUP=${group}&FORMAT=tle`,
            { headers: { Accept: "text/plain" } },
          );
          const text = await upstream.text();
          return new Response(text, {
            status: upstream.ok ? 200 : upstream.status,
            headers: { "Content-Type": "text/plain; charset=utf-8", ...CORS },
          });
        } catch (e) {
          return new Response(`# TLE upstream failed: ${String((e as Error).message)}\n`, {
            status: 502,
            headers: { "Content-Type": "text/plain; charset=utf-8", ...CORS },
          });
        }
      },
    },
  },
});