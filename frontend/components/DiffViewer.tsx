"use client";

import { useCallback, useMemo } from "react";
import { countDiffRows, diffFileSlug, diffRowId, parseUnifiedDiff } from "@/lib/diff";
import { getAnalysisDiff } from "@/lib/api";
import { useEffect, useState } from "react";
import type { DiffFile } from "@/lib/diff";

interface DiffViewerProps {
  analysisId: string;
  /** File + new-side line number a citation points at, when focused. */
  focus: { path: string; line: number | null } | null;
  /** Scroll to focused evidence only after the reviewer explicitly opens it. */
  revealFocus?: boolean;
}

type DiffState =
  | { kind: "loading" }
  | { kind: "ready"; raw: string; files: DiffFile[] }
  | { kind: "empty" }
  | { kind: "error"; message: string };

export function DiffViewer({ analysisId, focus, revealFocus = true }: DiffViewerProps) {
  const [state, setState] = useState<DiffState>({ kind: "loading" });
  const [openFiles, setOpenFiles] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });
    getAnalysisDiff(analysisId)
      .then((raw) => {
        if (cancelled) return;
        const files = parseUnifiedDiff(raw);
        setState(
          files.length > 0 ? { kind: "ready", raw, files } : { kind: "empty" },
        );
      })
      .catch((error: Error) => {
        if (cancelled) return;
        if (error instanceof Error && /status 404/.test(error.message)) {
          setState({ kind: "empty" });
        } else {
          setState({ kind: "error", message: error.message });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [analysisId]);

  const counts = useMemo(
    () => (state.kind === "ready" ? countDiffRows(state.files) : null),
    [state],
  );

  // When a citation focuses a line, expand its file and scroll to the row.
  useEffect(() => {
    if (state.kind !== "ready" || !focus) return;
    const file = state.files.find(
      (candidate) => candidate.path === focus.path || candidate.oldPath === focus.path,
    );
    if (!file) return;
    setOpenFiles((prev) => ({ ...prev, [file.path]: true }));
    const rowId = focus.line !== null ? diffRowId(file.path, focus.line) : null;
    const targetId = rowId ?? `diff-file-${diffFileSlug(file.path)}`;
    // Wait a frame so the newly expanded rows exist before scrolling.
    if (!revealFocus) return;
    requestAnimationFrame(() => {
      const target = document.getElementById(targetId);
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "center" });
        target.classList.remove("diff-row-flash");
        void target.offsetWidth; // restart the flash animation on repeat clicks
        target.classList.add("diff-row-flash");
      }
    });
  }, [focus, state]);

  const toggleFile = useCallback((path: string) => {
    setOpenFiles((prev) => ({ ...prev, [path]: !prev[path] }));
  }, []);

  if (state.kind === "loading") {
    return (
      <div className="space-y-3" data-testid="diff-loading">
        <div className="h-12 animate-pulse rounded-xl bg-slate-100" />
        <div className="h-40 animate-pulse rounded-xl bg-slate-100" />
      </div>
    );
  }

  if (state.kind === "empty") {
    return (
      <p className="rounded-xl border border-slate-200 bg-white px-4 py-6 text-center text-sm text-slate-500">
        No diff artifact is attached to this analysis.
      </p>
    );
  }

  if (state.kind === "error") {
    return (
      <p className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-6 text-center text-sm text-rose-700">
        {state.message}
      </p>
    );
  }

  return (
    <div className="space-y-3" data-testid="diff-viewer">
      <p className="text-xs text-slate-500">
        {state.files.length} file{state.files.length === 1 ? "" : "s"} changed ·{" "}
        <span className="font-mono text-emerald-700">+{counts?.added ?? 0}</span>{" "}
        <span className="font-mono text-rose-600">−{counts?.removed ?? 0}</span>
      </p>
      {state.files.map((file) => {
        const isOpen = openFiles[file.path] ?? false;
        const isFocusedFile =
          focus !== null && (focus.path === file.path || focus.path === file.oldPath);
        return (
          <div
            key={file.path}
            id={`diff-file-${diffFileSlug(file.path)}`}
            className={`overflow-hidden rounded-xl border bg-white ${
              isFocusedFile ? "border-slate-950" : "border-slate-200"
            }`}
          >
            <button
              type="button"
              onClick={() => toggleFile(file.path)}
              aria-expanded={isOpen}
              className="flex w-full items-center justify-between gap-3 bg-slate-50 px-4 py-2.5 text-left transition-colors hover:bg-slate-100"
            >
              <span className="flex min-w-0 items-center gap-2">
                <svg
                  viewBox="0 0 20 20"
                  className={`h-3.5 w-3.5 shrink-0 text-slate-400 transition-transform ${isOpen ? "rotate-90" : ""}`}
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <path d="M7 5l6 5-6 5V5z" />
                </svg>
                <span className="truncate font-mono text-[13px] text-slate-900">
                  {file.path}
                </span>
                {file.isNew && <FileTag label="new" className="bg-emerald-50 text-emerald-700 ring-emerald-600/20" />}
                {file.isDeleted && <FileTag label="deleted" className="bg-rose-50 text-rose-700 ring-rose-600/20" />}
                {file.isRename && <FileTag label="renamed" className="bg-sky-50 text-sky-700 ring-sky-600/20" />}
                {file.isBinary && <FileTag label="binary" className="bg-slate-100 text-slate-600 ring-slate-500/20" />}
              </span>
              <span className="shrink-0 font-mono text-xs">
                <span className="text-emerald-700">
                  +{countFileRows(file).added}
                </span>{" "}
                <span className="text-rose-600">
                  −{countFileRows(file).removed}
                </span>
              </span>
            </button>
            {isOpen && !file.isBinary && (
              <div className="overflow-x-auto border-t border-slate-200">
                <table className="w-full border-collapse font-mono text-xs leading-5">
                  <tbody>
                    {file.hunks.map((hunk, hunkIndex) => (
                      <HunkRows
                        key={hunkIndex}
                        hunk={hunk}
                        path={file.path}
                        showHeader={hunkIndex > 0 || file.hunks.length > 1}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function FileTag({ label, className }: { label: string; className: string }) {
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ring-1 ring-inset ${className}`}
    >
      {label}
    </span>
  );
}

function countFileRows(file: DiffFile) {
  let added = 0;
  let removed = 0;
  for (const hunk of file.hunks) {
    for (const row of hunk.rows) {
      if (row.type === "added") added += 1;
      else if (row.type === "removed") removed += 1;
    }
  }
  return { added, removed };
}

function HunkRows({
  hunk,
  path,
  showHeader,
}: {
  hunk: { header: string; rows: { type: string; oldNumber: number | null; newNumber: number | null; content: string }[] };
  path: string;
  showHeader: boolean;
}) {
  return (
    <>
      {showHeader && (
        <tr>
          <td colSpan={3} className="bg-slate-50 px-4 py-1 text-[11px] text-slate-500">
            {hunk.header}
          </td>
        </tr>
      )}
      {hunk.rows.map((row, rowIndex) => {
        const rowId =
          row.newNumber !== null ? diffRowId(path, row.newNumber) : undefined;
        const rowStyle =
          row.type === "added"
            ? "bg-emerald-50"
            : row.type === "removed"
              ? "bg-rose-50"
              : "";
        return (
          <tr key={rowIndex} id={rowId} className={rowStyle}>
            <td className="w-12 select-none border-r border-slate-200 px-2 text-right text-slate-400">
              {row.oldNumber ?? ""}
            </td>
            <td className="w-12 select-none border-r border-slate-200 px-2 text-right text-slate-400">
              {row.newNumber ?? ""}
            </td>
            <td className="whitespace-pre-wrap break-all px-3 text-slate-800">
              {row.content || " "}
            </td>
          </tr>
        );
      })}
    </>
  );
}
