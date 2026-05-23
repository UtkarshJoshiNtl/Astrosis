// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - tanstackStart, viteReact, tailwindcss, tsConfigPaths, cloudflare (build-only),
//     componentTagger (dev-only), VITE_* env injection, @ path alias, React/TanStack dedupe,
//     error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... } }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// satellite.js v7 has WASM modules (#wasm-single-thread and #wasm-multi-thread)
// that use top-level await. However, our fallback.ts code only uses the PURE
// JavaScript SGP4 implementation (twoline2satrec, propagate, etc.), not the
// optional WASM-accelerated bulk propagator. We stub these out to prevent
// Rollup from trying to bundle modules with top-level await into IIFE format.
const emptyWasmStub = path.resolve(__dirname, "src/lib/empty-wasm-stub.js");

// Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
// @cloudflare/vite-plugin builds from this — wrangler.jsonc main alone is insufficient.
export default defineConfig({
  tanstackStart: {
    server: { entry: "server" },
  },
  vite: {
    plugins: [
      {
        name: "stub-satellite-wasm",
        enforce: "pre",
        resolveId(source: string) {
          // Catch satellite.js internal WASM imports before they resolve to the actual files
          if (
            source === "#wasm-single-thread" ||
            source === "#wasm-multi-thread"
          ) {
            return emptyWasmStub;
          }
          return null;
        },
      },
    ],
  },
});
