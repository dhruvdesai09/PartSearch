import React from "react";
import { apiBaseMisconfiguredForProduction, getApiBase } from "../api";

/**
 * Shown when the production bundle is still targeting localhost or missing VITE_API_BASE.
 */
export default function ApiConfigBanner() {
  if (!apiBaseMisconfiguredForProduction()) return null;

  return (
    <div
      className="mx-auto max-w-3xl px-4 pt-4 sm:px-6"
      role="alert"
    >
      <div className="rounded-xl border border-amber-400/80 bg-amber-50 px-4 py-3 text-sm text-amber-950 shadow-sm">
        <p className="font-semibold">API URL is not set for production</p>
        <p className="mt-2 leading-relaxed">
          <span className="font-medium">Vite embeds</span>{" "}
          <code className="rounded bg-amber-100/80 px-1 py-0.5 text-xs">
            VITE_API_BASE
          </code>{" "}
          when the site is <strong>built</strong>. This app is calling{" "}
          <code className="rounded bg-amber-100/80 px-1 py-0.5 text-xs">
            {getApiBase()}
          </code>
          , which will not work for visitors.
        </p>
        <p className="mt-2 leading-relaxed">
          In Vercel: <strong>Project → Settings → Environment Variables</strong>{" "}
          add{" "}
          <code className="rounded bg-amber-100/80 px-1 py-0.5 text-xs">
            VITE_API_BASE
          </code>{" "}
          = your Render HTTPS URL (no trailing slash), e.g.{" "}
          <code className="rounded bg-amber-100/80 px-1 py-0.5 text-xs">
            https://partsearch.onrender.com
          </code>
          , then <strong>Redeploy</strong>.
        </p>
      </div>
    </div>
  );
}
