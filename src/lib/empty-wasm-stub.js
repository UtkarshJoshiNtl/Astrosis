// Empty stub for satellite.js WASM modules that we don't use.
// The fallback.ts code only uses the pure JS SGP4 implementation,
// not the WASM-accelerated bulk propagator.
export default async function emptyModule() {
  throw new Error("WASM not used");
}
