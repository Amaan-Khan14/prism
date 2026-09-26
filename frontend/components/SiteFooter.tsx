import Link from "next/link";
import { PrismLogo } from "./TopNav";

export function SiteFooter() {
  return (
    <footer className="border-t border-slate-200">
      <div className="mx-auto flex w-full max-w-6xl flex-col items-center justify-between gap-6 px-4 py-10 sm:flex-row sm:px-6">
        <div className="flex items-center gap-2 text-slate-950">
          <PrismLogo className="h-5 w-5 text-brand-500" />
          <span className="text-sm font-semibold tracking-tight">PRism</span>
          <span className="ml-2 hidden text-sm text-slate-400 sm:inline">
            Evidence-backed pull-request review
          </span>
        </div>
        <nav className="flex items-center gap-6 text-sm text-slate-500" aria-label="Footer">
          <Link href="/about" className="transition-colors hover:text-slate-950">
            How it works
          </Link>
          <a
            href="https://github.com"
            target="_blank"
            rel="noreferrer"
            className="transition-colors hover:text-slate-950"
          >
            GitHub
          </a>
        </nav>
        <p className="text-xs text-slate-400">© {new Date().getFullYear()} PRism</p>
      </div>
    </footer>
  );
}
