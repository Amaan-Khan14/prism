"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "./AuthProvider";
import { PrismLogo, TopNav } from "./TopNav";
import { SiteFooter } from "./SiteFooter";

const items = [
  { href: "/dashboard", label: "Workspace", icon: "M3 3h7v7H3z M14 3h7v7h-7z M14 14h7v7h-7z M3 14h7v7H3z" },
  { href: "/reviews", label: "Reviews", icon: "M5 4h14v16H5z M8 8h8 M8 12h8 M8 16h5" },
  { href: "/repositories", label: "Repositories", icon: "M3 6h18v13H3z M3 9h18 M8 6V4h8v2" },
  { href: "/about", label: "Method", icon: "M12 18h.01 M9.1 9a3 3 0 1 1 5.8 1c-.8 1-2.9 1.5-2.9 3.5" },
];

function SidebarLink({ href, label, icon, active, collapsed, onClick }: { href: string; label: string; icon: string; active: boolean; collapsed: boolean; onClick?: () => void }) {
  return <Link href={href} onClick={onClick} title={collapsed ? label : undefined} aria-current={active ? "page" : undefined} className={`group flex items-center rounded-md py-2.5 text-[13px] transition-colors ${collapsed ? "justify-center px-2" : "gap-3 px-3"} ${active ? "bg-brand-700 font-semibold text-white" : "text-slate-600 hover:bg-slate-100 hover:text-slate-950"}`}>
    <svg viewBox="0 0 24 24" className="h-[18px] w-[18px] shrink-0" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={icon} /></svg>
    {!collapsed && label}
  </Link>;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, status, signOut } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const isProductPage = pathname !== "/" && status === "signedIn";
  useEffect(() => { setMenuOpen(false); }, [pathname]);
  if (!isProductPage) return <><TopNav /><main className="mx-auto w-full max-w-6xl flex-1 px-4 pb-20 pt-10 sm:px-6">{children}</main><SiteFooter /></>;
  const active = (href: string) => pathname === href || (href === "/reviews" && pathname.startsWith("/analyses/"));
  const nav = (isCollapsed: boolean, onClick?: () => void) => items.map((item) => <SidebarLink key={item.href} {...item} active={active(item.href)} collapsed={isCollapsed} onClick={onClick} />);
  return <div className="workspace-theme min-h-screen text-slate-900"><div className="flex min-h-screen">
    <aside className={`fixed inset-y-0 left-0 z-40 hidden flex-col border-r border-slate-200 bg-white px-3 transition-[width] duration-200 lg:flex ${collapsed ? "w-[72px]" : "w-[224px]"}`}>
      <div className={`flex h-16 items-center border-b border-slate-100 ${collapsed ? "justify-center" : "justify-between px-2"}`}><Link href="/dashboard" className="flex items-center gap-2.5"><PrismLogo className="h-7 w-7" />{!collapsed && <span className="text-[17px] font-semibold tracking-[-0.03em] text-slate-950">PRism</span>}</Link><button type="button" onClick={() => setCollapsed((value) => !value)} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} className={`rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-900 ${collapsed ? "absolute -right-3 top-5 border border-slate-200 bg-white" : ""}`}>{collapsed ? "›" : "‹"}</button></div>
      {!collapsed && <div className="px-3 pb-2 pt-7 text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-400">Workspace</div>}
      <nav aria-label="Workspace" className={`space-y-1 ${collapsed ? "pt-6" : ""}`}>{nav(collapsed)}</nav>
      <div className="mt-auto border-t border-slate-100 py-4"><div className={`flex items-center py-2 ${collapsed ? "justify-center" : "gap-3 px-2"}`}><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-700 text-xs font-semibold text-white">{user?.github_login.slice(0, 1).toUpperCase()}</span>{!collapsed && <div className="min-w-0"><p className="truncate text-sm font-medium text-slate-900">{user?.github_name || user?.github_login}</p><p className="truncate text-xs text-slate-600">@{user?.github_login}</p></div>}</div><button type="button" onClick={() => void signOut()} data-testid="nav-sign-out" title={collapsed ? "Sign out" : undefined} className={`mt-1 rounded-md py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 hover:text-slate-950 ${collapsed ? "mx-auto block px-2" : "w-full px-3 text-left"}`}>{collapsed ? "↪" : "Sign out"}</button></div>
    </aside>
    <div className={`min-w-0 flex-1 transition-[padding] duration-200 ${collapsed ? "lg:pl-[72px]" : "lg:pl-[224px]"}`}><header className="workspace-mobile-header sticky top-0 z-30 flex h-14 items-center justify-between border-b border-slate-200 bg-white px-4 lg:hidden"><Link href="/dashboard" className="flex items-center gap-2 font-semibold text-slate-950"><PrismLogo className="h-6 w-6" /> PRism</Link><button type="button" aria-expanded={menuOpen} onClick={() => setMenuOpen((open) => !open)} className="rounded-md border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700">{menuOpen ? "Close" : "Menu"}</button></header>{menuOpen && <nav aria-label="Workspace" className="sticky top-14 z-30 space-y-1 border-b border-slate-200 bg-white p-3 lg:hidden">{nav(false, () => setMenuOpen(false))}</nav>}<main className="mx-auto w-full max-w-[1440px] px-5 pb-16 pt-6 sm:px-8">{children}</main><div className="px-5 pb-6 text-center text-xs text-slate-400">PRism · Evidence-backed pull-request review</div></div>
  </div></div>;
}
