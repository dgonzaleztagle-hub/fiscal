import "server-only";

export type FiscalRuntimeMode = "demo" | "certification" | "production";

export function fiscalRuntimeMode(): FiscalRuntimeMode {
  const value = process.env.FISCAL_RUNTIME_MODE;
  return value === "certification" || value === "production" ? value : "demo";
}

export function fiscalEngineCredentials() {
  if (fiscalRuntimeMode() === "demo") return null;
  const baseUrl = process.env.FISCAL_API_URL;
  const token = process.env.FISCAL_API_TOKEN;
  if (!baseUrl || !token) return null;
  const parsed = new URL(baseUrl);
  if (parsed.protocol !== "https:" && !["localhost", "127.0.0.1"].includes(parsed.hostname)) throw new Error("El motor fiscal debe usar HTTPS");
  return { baseUrl, token };
}

export function fiscalPublicEngineUrl() {
  return fiscalRuntimeMode() === "demo" ? null : process.env.FISCAL_API_URL ?? null;
}
