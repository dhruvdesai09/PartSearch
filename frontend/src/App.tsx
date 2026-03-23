import React, { useEffect, useState } from "react";
import PdfUploadPanel from "./components/PdfUploadPanel";
import TypeaheadSearch from "./components/TypeaheadSearch";

export default function App() {
  const [hash, setHash] = useState(() =>
    typeof window === "undefined" ? "" : window.location.hash,
  );

  useEffect(() => {
    const onHash = () => setHash(window.location.hash);
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const adminMode = import.meta.env.VITE_ADMIN_MODE === "true";
  const isUpload = hash === "#/upload" && adminMode;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {isUpload ? (
        <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Admin upload
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            Import a PDF price list. Rows will be parsed and stored for search.
          </p>
          <div className="mt-6">
            <PdfUploadPanel />
          </div>
          <div className="mt-6 text-sm text-slate-500">
            Tip: switch back to search with{" "}
            <a
              className="font-semibold text-amber-700 hover:text-amber-800"
              href="#/"
            >
              #/
            </a>
          </div>
        </div>
      ) : (
        <>
          <TypeaheadSearch />
          <div className="mt-2 px-4 pb-6 text-center text-xs text-slate-500">
            {adminMode ? (
              <a
                className="font-semibold text-amber-700 hover:text-amber-800"
                href="#/upload"
              >
                Admin upload
              </a>
            ) : (
              <span> </span>
            )}
          </div>
        </>
      )}
    </div>
  );
}
