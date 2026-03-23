import React from "react";
import PdfUploadPanel from "./components/PdfUploadPanel";
import TypeaheadSearch from "./components/TypeaheadSearch";

export default function App() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto max-w-2xl px-4 py-6 sm:px-6">
        <TypeaheadSearch />

        <section className="mt-6">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <h2 className="text-lg font-bold tracking-tight text-slate-900">
                  Upload PDF price list
                </h2>
                <p className="mt-1 text-sm text-slate-600">
                  Parse and import tables so the part search can use them.
                </p>
              </div>
            </div>

            <div className="mt-4">
              <PdfUploadPanel />
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
