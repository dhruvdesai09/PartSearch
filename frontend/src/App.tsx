import React from "react";
import PdfUploadPanel from "./components/PdfUploadPanel";
import TypeaheadSearch from "./components/TypeaheadSearch";

export default function App() {
  return (
    <div className="relative min-h-screen overflow-x-hidden bg-gradient-to-br from-sky-100 via-violet-100/70 to-amber-50">
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(124,58,237,0.22),transparent)]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute right-0 top-1/4 h-64 w-64 rounded-full bg-cyan-300/25 blur-3xl"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute bottom-0 left-0 h-72 w-72 rounded-full bg-orange-300/20 blur-3xl"
        aria-hidden
      />

      <header className="relative border-b border-white/20 bg-gradient-to-r from-violet-600 via-indigo-600 to-sky-600 shadow-lg shadow-violet-900/20">
        <div className="mx-auto max-w-3xl px-4 py-7 sm:px-6 sm:py-8">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-violet-200/90">
            Price list tools
          </p>
          <h1 className="mt-2 text-2xl font-bold tracking-tight text-white drop-shadow-sm sm:text-3xl">
            Voice Searchable Price List
          </h1>
          <p className="mt-3 max-w-xl text-sm leading-relaxed text-violet-100 sm:text-base">
            Import PDF price lists, then search by typing or speaking a part
            number. Works on phone and desktop.
          </p>
        </div>
      </header>

      <main className="relative mx-auto max-w-3xl space-y-8 px-4 py-8 sm:px-6 sm:py-10">
        <PdfUploadPanel />
        <TypeaheadSearch />
      </main>

      <footer className="relative mx-auto max-w-3xl px-4 pb-10 pt-2 text-center text-xs text-slate-600/90 sm:px-6">
        Search and voice use your browser; uploads go to your configured API.
      </footer>
    </div>
  );
}
