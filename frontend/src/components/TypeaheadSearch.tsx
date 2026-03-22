import React, { useEffect, useMemo, useRef, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { searchProducts, type SearchResult } from "../api";
import { useDebouncedValue } from "../hooks/useDebouncedValue";
import { useClickOutside } from "../hooks/useClickOutside";
import VoiceSearchButton from "./VoiceSearchButton";

const priceFmt = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 0,
});

export default function TypeaheadSearch() {
  const [query, setQuery] = useState("");
  const [panelDismissed, setPanelDismissed] = useState(false);
  const debounced = useDebouncedValue(query, 180);
  const containerRef = useRef<HTMLDivElement>(null);

  const enabled = useMemo(() => debounced.trim().length >= 1, [debounced]);

  useEffect(() => {
    setPanelDismissed(false);
  }, [debounced]);

  const {
    data,
    isFetching,
    isError,
    isPlaceholderData,
  } = useQuery({
    queryKey: ["search", debounced],
    queryFn: () => searchProducts(debounced.trim()),
    enabled,
    placeholderData: keepPreviousData,
    staleTime: 400,
  });

  useClickOutside(containerRef, () => setPanelDismissed(true), enabled);

  const results: SearchResult[] = data ?? [];

  const showEmpty =
    !isFetching &&
    !isError &&
    results.length === 0 &&
    enabled &&
    !isPlaceholderData;

  const showPanel =
    enabled &&
    !panelDismissed &&
    (isFetching || isError || results.length > 0 || showEmpty);

  const onSelect = (r: SearchResult) => {
    setQuery(r.designation);
    setPanelDismissed(true);
  };

  return (
    <section
      className="animate-fade-in-up rounded-2xl border border-violet-200/60 bg-white p-6 shadow-card ring-1 ring-violet-500/5 [animation-delay:60ms]"
      aria-labelledby="search-heading"
    >
      <div className="flex items-start gap-3">
        <span
          className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-brand-500 text-white shadow-md shadow-violet-500/25"
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
              d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
            />
          </svg>
        </span>
        <div className="min-w-0 flex-1">
          <h2
            id="search-heading"
            className="text-lg font-semibold tracking-tight text-slate-900"
          >
            Search parts
          </h2>
          <p className="mt-0.5 text-sm text-slate-600">
            Typeahead and fuzzy matching — try a fragment of a part number.
          </p>
        </div>
      </div>

      <div className="mt-5 flex items-stretch gap-2 sm:gap-3">
        <div ref={containerRef} className="relative min-w-0 flex-1">
          <span className="pointer-events-none absolute left-3 top-1/2 z-10 -translate-y-1/2 text-brand-500 transition-colors duration-200">
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
          </span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => setPanelDismissed(false)}
            placeholder="e.g. VKTC 0904, 6201…"
            className="w-full rounded-xl border border-slate-200/90 bg-gradient-to-b from-white to-slate-50/80 py-3 pl-10 pr-3 text-sm text-slate-900 shadow-inner shadow-slate-200/30 outline-none ring-brand-500/0 transition duration-200 ease-out placeholder:text-slate-400 focus:border-brand-400 focus:bg-white focus:shadow-brand focus:ring-2 focus:ring-brand-500/25"
            aria-label="Search parts"
            aria-expanded={showPanel}
            aria-controls="search-results"
            autoComplete="off"
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                setQuery("");
                setPanelDismissed(true);
              }
            }}
          />

          {showPanel && (
            <div
              id="search-results"
              role="listbox"
              className="absolute z-20 mt-2 w-full origin-top overflow-hidden rounded-xl border border-slate-200/80 bg-white/95 shadow-xl shadow-violet-950/10 ring-1 ring-slate-900/5 backdrop-blur-sm animate-fade-in"
            >
              {isFetching && (
                <div
                  className="h-0.5 w-full overflow-hidden bg-slate-100"
                  aria-hidden
                >
                  <div className="h-full w-1/4 rounded-full bg-gradient-to-r from-brand-400 to-violet-500 animate-load-bar" />
                </div>
              )}
              {isFetching && results.length === 0 && (
                <div className="space-y-2 px-4 py-3">
                  <div className="h-4 w-3/4 animate-pulse rounded bg-slate-100" />
                  <div className="h-4 w-1/2 animate-pulse rounded bg-slate-100" />
                  <div className="h-4 w-2/3 animate-pulse rounded bg-slate-100" />
                </div>
              )}
              {isError && !isFetching && (
                <div className="px-4 py-3 text-sm text-red-700">
                  Could not search. Is the backend running?
                </div>
              )}
              {showEmpty && (
                <div className="px-4 py-3 text-sm text-slate-500">
                  No matches for that query.
                </div>
              )}
              {!isError &&
                results.length > 0 &&
                results.slice(0, 8).map((r) => (
                  <button
                    key={r.normalized_designation}
                    type="button"
                    role="option"
                    onClick={() => onSelect(r)}
                    className="flex w-full items-start gap-3 border-t border-slate-100/90 px-4 py-3 text-left text-sm transition-colors duration-150 first:border-t-0 hover:bg-gradient-to-r hover:from-violet-50/80 hover:to-brand-50/50"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="font-semibold text-slate-900">
                        {r.designation}
                      </div>
                      {(r.pack_code != null || r.case_qty != null) && (
                        <div className="mt-0.5 text-xs text-slate-500">
                          Pack {r.pack_code ?? "—"}
                          {r.case_qty != null
                            ? ` · case qty ${r.case_qty}`
                            : ""}
                        </div>
                      )}
                    </div>
                    <div className="shrink-0 text-right">
                      <div className="text-[10px] font-semibold uppercase tracking-wider text-brand-600">
                        Price
                      </div>
                      <div className="font-semibold tabular-nums text-violet-700">
                        {priceFmt.format(r.price)}
                      </div>
                    </div>
                  </button>
                ))}
              {isPlaceholderData && isFetching && results.length > 0 && (
                <div className="border-t border-brand-100/80 bg-brand-50/50 px-3 py-1.5 text-center text-[11px] font-medium text-brand-700">
                  Updating results…
                </div>
              )}
            </div>
          )}
        </div>

        <VoiceSearchButton
          onTranscript={(t) => {
            setQuery(t);
            setPanelDismissed(false);
          }}
        />
      </div>

      <div className="mt-6 flex items-start gap-2 rounded-xl border border-teal-200/60 bg-gradient-to-r from-teal-50/90 to-brand-50/50 px-4 py-3 text-sm text-teal-900/90">
        <span
          className="mt-0.5 text-lg leading-none text-teal-600"
          aria-hidden
        >
          ✦
        </span>
        <p>
          <span className="font-semibold text-teal-900">Tip:</span> voice
          input may add extra words — say only the part number for best
          results.
        </p>
      </div>
    </section>
  );
}
