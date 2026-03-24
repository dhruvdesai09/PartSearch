import React, { useEffect, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { searchProductsWithOptions, type SearchResult } from "../api";
import { useDebouncedValue } from "../hooks/useDebouncedValue";
import VoiceSearchButton from "./VoiceSearchButton";

const priceFmt = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 0,
});

function cleanQuery(raw: string): string {
  let s = (raw || "").toLowerCase();
  s = s.replace(
    /\b(price|bearing|bearings|cost|rate|for|of|mrp|rsp|inr|skf)\b/g,
    " ",
  );
  // Keep common part-number characters; replace others with spaces.
  s = s.replace(/[^a-z0-9/\-()\s]/g, " ");
  s = s.replace(/\s+/g, " ").trim();
  return s;
}

function normalizeForExact(raw: string): string {
  return (raw || "")
    .toLowerCase()
    .replace(/\s+/g, "")
    .replace(/[-/()]/g, "");
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function highlightMatch(text: string, q: string): React.ReactNode {
  const cleaned = q.replace(/\s+/g, "");
  if (cleaned.length < 2) return text;
  const escaped = escapeRegExp(cleaned);
  const re = new RegExp(escaped, "ig");
  const parts = text.split(re);
  if (parts.length <= 1) return text;

  const matches = text.match(re);
  if (!matches) return text;

  return (
    <>
      {parts.map((p, idx) => (
        <React.Fragment key={idx}>
          {p}
          {idx < matches.length && (
            <mark className="rounded bg-amber-100 px-1 py-0.5 text-inherit font-semibold text-amber-700">
              {matches[idx]}
            </mark>
          )}
        </React.Fragment>
      ))}
    </>
  );
}

export default function TypeaheadSearch() {
  const [query, setQuery] = useState("");
  const debounced = useDebouncedValue(query, 200);

  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    setExpanded(null);
  }, [debounced]);

  const enabled = debounced.trim().length >= 1;
  const normQ = normalizeForExact(debounced);

  const primary = useQuery({
    queryKey: ["search", debounced, 0.15],
    queryFn: () =>
      searchProductsWithOptions(debounced.trim(), {
        minSimilarity: 0.15,
      }),
    enabled,
    staleTime: 300,
    placeholderData: keepPreviousData,
  });

  const fallback = useQuery({
    queryKey: ["search", debounced, 0.05],
    queryFn: () =>
      searchProductsWithOptions(debounced.trim(), {
        minSimilarity: 0.05,
      }),
    enabled:
      enabled &&
      primary.isSuccess &&
      (primary.data?.length ?? 0) === 0 &&
      !primary.isFetching,
    staleTime: 300,
    placeholderData: keepPreviousData,
  });

  const primaryResults: SearchResult[] = primary.data ?? [];
  const fallbackResults: SearchResult[] = fallback.data ?? [];
  const usingFallback = primaryResults.length === 0 && fallbackResults.length > 0;
  const results: SearchResult[] = usingFallback ? fallbackResults : primaryResults;

  const showList = enabled && (primary.isFetching || results.length > 0 || primary.isError);

  const showNoResults =
    enabled &&
    primary.isSuccess &&
    (primary.data?.length ?? 0) === 0 &&
    fallback.isSuccess &&
    (fallback.data?.length ?? 0) === 0;

  const showError = primary.isError && !primary.isFetching;

  return (
    <div className="mx-auto max-w-2xl px-4 pb-10 pt-4 sm:px-6">
      <div className="sticky top-0 z-20 -mx-4 px-4 pb-3 sm:-mx-6 sm:px-6">
        <div className="rounded-2xl border border-slate-200 bg-white/90 p-3 shadow-sm backdrop-blur">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-700">
              <svg
                className="h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.75}
                aria-hidden
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
                />
              </svg>
            </div>

            <div className="flex min-w-0 flex-1 items-center gap-2">
              <input
                value={query}
                onChange={(e) => setQuery(cleanQuery(e.target.value))}
                placeholder="Search part… e.g. 6201 or VKTC 0904"
                className="w-full min-w-0 bg-transparent text-base font-medium outline-none placeholder:text-slate-400"
                aria-label="Search parts"
                autoComplete="off"
              />
              <VoiceSearchButton
                compact
                onTranscript={(t) => {
                  setQuery(cleanQuery(t));
                }}
              />
            </div>
          </div>

          <div className="mt-2 text-xs text-slate-500">
            Type or speak a part number. Price will appear instantly.
          </div>
        </div>
      </div>

      <div className="mt-4">
        {usingFallback && (
          <div className="mb-3 text-sm text-slate-600">
            Closest matches
          </div>
        )}

        {showError && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
            Could not reach the backend. Is it deployed?
          </div>
        )}

        {showNoResults && (
          <div className="rounded-xl border border-slate-200 bg-white px-4 py-4 text-sm text-slate-600">
            No matches. Try a shorter query like{" "}
            <span className="font-semibold">62</span>.
          </div>
        )}

        {!showList && enabled && primary.isFetching && (
          <div className="text-sm text-slate-600">Searching…</div>
        )}

        <div className="space-y-3">
          {results.slice(0, 30).map((r) => {
            const key = r.normalized_designation;
            const isOpen = expanded === key;

            return (
              <button
                key={key}
                type="button"
                onClick={() => setExpanded(isOpen ? null : key)}
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-4 text-left shadow-sm"
                aria-expanded={isOpen}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold text-slate-900">
                      {highlightMatch(r.designation, debounced)}
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-1.5">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                          r.source_type === "automotive"
                            ? "bg-sky-100 text-sky-800"
                            : "bg-violet-100 text-violet-800"
                        }`}
                      >
                        {r.source_type}
                      </span>
                    {normQ && r.normalized_designation === normQ && (
                      <div className="inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">
                        Exact match
                      </div>
                    )}
                    </div>

                    {(r.pack_code != null || r.case_qty != null) && (
                      <div className="mt-1 text-xs text-slate-500">
                        {r.pack_code != null ? `Pack ${r.pack_code}` : ""}
                        {r.pack_code != null && r.case_qty != null ? " · " : ""}
                        {r.case_qty != null ? `Case ${r.case_qty}` : ""}
                      </div>
                    )}
                  </div>

                  <div className="shrink-0 text-right">
                    <div className="text-[11px] font-extrabold uppercase tracking-wide text-amber-700">
                      Price
                    </div>
                    <div className="mt-0.5 text-3xl font-extrabold leading-none tabular-nums text-amber-600">
                      {priceFmt.format(r.price)}
                    </div>
                  </div>
                </div>

                <div className="mt-3 flex items-center justify-between">
                  <div className="text-xs text-slate-500">
                    {isOpen ? "Tap to collapse" : "Tap to expand"}
                  </div>
                  <svg
                    className={`h-5 w-5 text-slate-400 transition-transform ${isOpen ? "rotate-180" : "rotate-0"}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={1.75}
                    aria-hidden
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M19 9l-7 7-7-7"
                    />
                  </svg>
                </div>

                {isOpen && (
                  <div className="mt-4 rounded-xl border border-slate-100 bg-slate-50 px-3 py-3">
                    <div className="text-sm font-semibold text-slate-800">
                      Details
                    </div>
                    <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <div className="text-slate-500">Pack</div>
                        <div className="font-semibold text-slate-800">
                          {r.pack_code ?? "—"}
                        </div>
                      </div>
                      <div>
                        <div className="text-slate-500">Case qty</div>
                        <div className="font-semibold text-slate-800">
                          {r.case_qty ?? "—"}
                        </div>
                      </div>
                      <div className="col-span-2">
                        <div className="text-slate-500">Normalized</div>
                        <div className="break-all font-semibold text-slate-700">
                          {r.normalized_designation}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </button>
            );
          })}
        </div>

        {(primary.isFetching || fallback.isFetching) && enabled && (
          <div className="mt-4 text-center text-sm text-slate-500">
            Updating…
          </div>
        )}
      </div>
    </div>
  );
}
