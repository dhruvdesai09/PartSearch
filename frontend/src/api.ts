import axios from "axios";

export type SearchResult = {
  designation: string;
  normalized_designation: string;
  price: number;
  pack_code?: string | null;
  case_qty?: number | null;
  score: number;
};

export type UploadResponse = {
  parsed: number;
  upserted: number;
  unique_normalized: number;
};

/** Resolved API base (no trailing slash). */
export function getApiBase(): string {
  const raw = import.meta.env.VITE_API_BASE?.toString()?.trim() || "";
  const base = raw || "http://localhost:8000";
  return base.replace(/\/+$/, "");
}

const API_BASE = getApiBase();

/**
 * Production build but VITE_API_BASE missing/wrong → browser still calls localhost or HTTP.
 */
export function apiBaseMisconfiguredForProduction(): boolean {
  if (!import.meta.env.PROD) return false;
  const raw = import.meta.env.VITE_API_BASE?.toString()?.trim() || "";
  if (!raw) return true;
  if (raw.includes("localhost") || raw.includes("127.0.0.1")) return true;
  if (typeof window !== "undefined") {
    if (window.location.protocol === "https:" && raw.startsWith("http:")) {
      return true;
    }
  }
  return false;
}

export function uploadErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d: { msg?: string }) => d.msg)
        .filter(Boolean)
        .join(", ");
    }
    if (err.response?.status === 0 || err.code === "ERR_NETWORK") {
      return [
        "Cannot reach the API.",
        apiBaseMisconfiguredForProduction()
          ? "This build has no VITE_API_BASE (or it points at localhost/HTTP). In Vercel, set VITE_API_BASE to your Render HTTPS URL (no trailing slash) and redeploy."
          : "Check that the backend URL is correct, HTTPS (if the site is HTTPS), and that the server is up. Free Render services can take a minute to wake—try again.",
      ].join(" ");
    }
  }
  return err instanceof Error ? err.message : "Upload failed";
}

export async function searchProducts(q: string): Promise<SearchResult[]> {
  const url = `${API_BASE}/search`;
  const resp = await axios.get(url, {
    params: { q },
  });
  return resp.data as SearchResult[];
}

/** Uploads can exceed default timeouts on cold Render free tiers. */
const UPLOAD_TIMEOUT_MS = 180_000;

export async function uploadPdf(
  file: File,
  sourceFile?: string,
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  if (sourceFile?.trim()) {
    form.append("source_file", sourceFile.trim());
  }
  const resp = await axios.post<UploadResponse>(`${API_BASE}/upload`, form, {
    timeout: UPLOAD_TIMEOUT_MS,
  });
  return resp.data;
}

