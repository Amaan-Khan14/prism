"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { API_URL } from "@/lib/api";
import { useAuth } from "./AuthProvider";

export function PrismLogo({ className = "h-6 w-6" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" fill="none" className={className} aria-hidden="true">
      <path d="M16 3.5 28 26H4L16 3.5Z" stroke="currentColor" strokeWidth="2.4" strokeLinejoin="round" />
      <path d="M16 3.5v22" stroke="currentColor" strokeWidth="1.2" opacity="0.45" />
    </svg>
  );
}

export function TopNav() {
  const pathname = usePathname();
  const { status } = useAuth();
  const isHome = pathname === "/";
  return (
    <header className={isHome ? "marketing-header" : "border-b border-slate-200 bg-white"}>
      <div className={isHome ? "marketing-nav" : "mx-auto flex h-[68px] max-w-[1440px] items-center justify-between px-5 sm:px-8"}>
        <Link href="/" className={isHome ? "marketing-brand" : "flex items-center gap-2.5 text-slate-950"}>
          <PrismLogo className="h-7 w-7 text-brand-500" />
          <span className="text-[17px] font-semibold tracking-[-0.03em]">PRism</span>
        </Link>
        <nav aria-label="Main" className={isHome ? "marketing-links" : "flex items-center gap-5 text-sm"}>
          {isHome ? <>
            <a href="#evidence">Evidence</a><a href="#inspector">Inspector</a><a href="#workflow">Workflow</a><a href="#faq">FAQ</a>
            {status === "signedOut" && <a href={`${API_URL}/auth/github/login`} data-testid="nav-sign-in" className="marketing-signin">Sign in with GitHub</a>}
          </> : <>
            <Link href="/about" className={`transition-colors hover:text-brand-700 ${pathname === "/about" ? "font-medium text-slate-950" : "text-slate-600"}`}>How it works</Link>
            {status === "signedOut" && <a href={`${API_URL}/auth/github/login`} data-testid="nav-sign-in" className="rounded-lg bg-brand-700 px-4 py-2.5 font-medium text-white transition-colors hover:bg-brand-800">Sign in with GitHub</a>}
          </>}
        </nav>
      </div>
    </header>
  );
}

export function GitHubMark({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="currentColor" className={className} aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
    </svg>
  );
}
