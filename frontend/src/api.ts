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

const API_BASE =
  import.meta.env.VITE_API_BASE?.toString()?.trim() || "http://localhost:8000";

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
      return "Cannot reach the API. Is the backend running?";
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

export async function uploadPdf(
  file: File,
  sourceFile?: string,
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  if (sourceFile?.trim()) {
    form.append("source_file", sourceFile.trim());
  }
  const resp = await axios.post<UploadResponse>(`${API_BASE}/upload`, form);
  return resp.data;
}

