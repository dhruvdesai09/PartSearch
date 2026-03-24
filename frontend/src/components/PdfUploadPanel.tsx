import React, { useCallback, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  uploadPdf,
  uploadErrorMessage,
  type UploadResponse,
} from "../api";

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export default function PdfUploadPanel() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [sourceLabel, setSourceLabel] = useState("");
  const [priceListType, setPriceListType] = useState<"automotive" | "industrial">(
    "automotive",
  );
  const [lastResult, setLastResult] = useState<UploadResponse | null>(null);
  const [hint, setHint] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("No file selected");
      return uploadPdf(file, priceListType, sourceLabel || file.name);
    },
    onSuccess: (data) => {
      setLastResult(data);
    },
  });

  const pickFile = useCallback((f: File | undefined | null) => {
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".pdf")) {
      setHint("Please choose a PDF file.");
      return;
    }
    setHint(null);
    setFile(f);
    setLastResult(null);
    mutation.reset();
    setSourceLabel((prev) => (prev.trim() ? prev : f.name));
  }, [mutation]);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const f = e.dataTransfer.files[0];
      pickFile(f);
    },
    [pickFile],
  );

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    pickFile(e.target.files?.[0] ?? null);
    e.target.value = "";
  };

  const error =
    mutation.isError && !mutation.isPending
      ? uploadErrorMessage(mutation.error)
      : null;

  return (
    <section
      className="animate-fade-in-up rounded-2xl border border-teal-200/50 bg-white/95 p-6 shadow-card ring-1 ring-teal-500/10 backdrop-blur-sm [animation-delay:0ms]"
      aria-labelledby="upload-heading"
    >
      <div className="flex items-start gap-3">
        <span
          className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-teal-500 to-cyan-500 text-white shadow-md shadow-teal-600/25"
          aria-hidden
        >
          <svg
            className="h-5 w-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m6.75 12l-3-3m0 0l-3 3m3-3v11.25m6-2.25h1.5m-1.5 0a11.25 11.25 0 01-11.25-11.25V7.5"
            />
          </svg>
        </span>
        <div className="min-w-0 flex-1">
          <h2
            id="upload-heading"
            className="text-lg font-semibold tracking-tight text-slate-900"
          >
            Import price list
          </h2>
          <p className="mt-0.5 text-sm text-slate-600">
            Drop a PDF here or choose a file. Rows are parsed and stored for
            search.
          </p>
        </div>
      </div>

      <div
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        onClick={() => inputRef.current?.click()}
        onDragEnter={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDrop={onDrop}
        className={`mt-5 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-10 transition-all duration-300 ease-out ${
          dragOver
            ? "scale-[1.02] border-teal-400 bg-gradient-to-b from-teal-50 to-cyan-50 shadow-brand"
            : "border-slate-200/90 bg-gradient-to-b from-slate-50/80 to-white hover:border-teal-300/80 hover:bg-teal-50/30"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,application/pdf"
          className="hidden"
          onChange={onInputChange}
        />
        <svg
          className={`h-10 w-10 transition-colors duration-300 ${
            dragOver ? "text-teal-500" : "text-slate-400"
          }`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
          aria-hidden
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m6.75 12l-3-3m0 0l-3 3m3-3v11.25m6-2.25h1.5m-1.5 0a11.25 11.25 0 01-11.25-11.25V7.5"
          />
        </svg>
        <p className="mt-3 text-center text-sm font-medium text-slate-700">
          Click to browse or drag a PDF
        </p>
        <p className="mt-1 text-center text-xs font-medium text-teal-600/80">
          .pdf only
        </p>
      </div>

      {file && (
        <div className="mt-4 animate-fade-in rounded-xl border border-teal-100 bg-gradient-to-br from-teal-50/50 to-white px-4 py-3 text-slate-800 shadow-inner shadow-teal-900/5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-slate-900">
                {file.name}
              </div>
              <div className="text-xs text-teal-700/80">
                {formatBytes(file.size)}
              </div>
            </div>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setFile(null);
                setLastResult(null);
                setHint(null);
                mutation.reset();
              }}
              className="shrink-0 rounded-lg px-2 py-1 text-xs font-medium text-slate-600 transition-colors duration-150 hover:bg-white hover:text-slate-900"
            >
              Clear
            </button>
          </div>
          <label className="mt-3 block text-xs font-medium text-slate-600">
            Price list type
            <select
              value={priceListType}
              onChange={(e) =>
                setPriceListType(e.target.value as "automotive" | "industrial")
              }
              className="mt-1 w-full rounded-lg border border-slate-200/90 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-teal-500/0 transition duration-200 ease-out focus:border-teal-400 focus:ring-2 focus:ring-teal-500/20"
            >
              <option value="automotive">Automotive (6-column table)</option>
              <option value="industrial">Industrial (designation-price pairs)</option>
            </select>
          </label>
          <label className="mt-3 block text-xs font-medium text-slate-600">
            Source name (optional)
            <input
              value={sourceLabel}
              onChange={(e) => setSourceLabel(e.target.value)}
              placeholder={file.name}
              className="mt-1 w-full rounded-lg border border-slate-200/90 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-teal-500/0 transition duration-200 ease-out focus:border-teal-400 focus:ring-2 focus:ring-teal-500/20"
            />
          </label>
          <button
            type="button"
            disabled={mutation.isPending}
            onClick={(e) => {
              e.stopPropagation();
              mutation.mutate();
            }}
            className="mt-3 w-full rounded-xl bg-gradient-to-r from-teal-600 to-cyan-600 px-4 py-2.5 text-sm font-semibold text-white shadow-md shadow-teal-600/25 transition duration-200 ease-out hover:from-teal-500 hover:to-cyan-500 hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-60"
          >
            {mutation.isPending ? "Uploading & parsing…" : "Upload & import"}
          </button>
        </div>
      )}

      {hint && (
        <div className="mt-4 animate-fade-in rounded-lg border border-amber-300/60 bg-amber-50 px-4 py-3 text-sm text-amber-950">
          {hint}
        </div>
      )}

      {error && (
        <div
          className="mt-4 animate-fade-in rounded-lg border border-rose-300/60 bg-rose-50 px-4 py-3 text-sm text-rose-900"
          role="alert"
        >
          {error}
        </div>
      )}

      {lastResult && !mutation.isPending && !error && (
        <div
          className={`mt-4 animate-fade-in rounded-lg border px-4 py-3 text-sm ${
            lastResult.parsed === 0
              ? "border-amber-300/60 bg-amber-50 text-amber-950"
              : "border-emerald-300/60 bg-emerald-50 text-emerald-950"
          }`}
          role="status"
        >
          {lastResult.parsed === 0 ? (
            <>
              <div className="font-semibold">No rows recognized</div>
              <p className="mt-2 text-amber-900/85">
                The PDF uploaded, but no price rows were detected. Try a
                different file or check that it matches a supported layout.
              </p>
            </>
          ) : (
            <>
              <div className="font-semibold text-emerald-900">Import complete</div>
              <ul className="mt-2 list-inside list-disc space-y-0.5 text-emerald-900/90">
                <li>{lastResult.parsed} rows parsed</li>
                <li>{lastResult.upserted} rows saved</li>
                <li>
                  {lastResult.unique_normalized} unique part numbers in this
                  file
                </li>
              </ul>

              {lastResult.sample && lastResult.sample.length > 0 && (
                <div className="mt-4 rounded-lg border border-emerald-200/70 bg-white/60 px-3 py-2">
                  <div className="text-xs font-semibold uppercase tracking-wide text-emerald-800">
                    Debug sample (first {Math.min(8, lastResult.sample.length)} rows)
                  </div>
                  <div className="mt-2 space-y-1 text-xs text-emerald-900">
                    {lastResult.sample.slice(0, 8).map((r) => (
                      <div key={r.normalized_designation} className="truncate">
                        {r.designation} : price={r.price}
                        {r.case_qty != null ? `, case=${r.case_qty}` : ""}
                        {r.pack_code != null ? `, pack=${r.pack_code}` : ""}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </section>
  );
}
