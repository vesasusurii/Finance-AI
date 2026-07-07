import { Link, useLocation, useNavigate } from "react-router-dom";
import { Search, ChevronDown, Menu, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/auth/AuthContext";
import { roleLabel } from "@/types/auth";
import { BrandLogo } from "./BrandLogo";
import { GlobalSearchDialog } from "./GlobalSearchDialog";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { useIsMobile } from "@/hooks/use-mobile";

const financeNav = [
  { to: "/", label: "Upload" },
  { to: "/documents", label: "Documents" },
  { to: "/bank-statements", label: "Bank Statements" },
  { to: "/matching", label: "Matching" },
  { to: "/manual-review", label: "Manual Review" },
  { to: "/exports", label: "Reports" },
];

const adminNav = [
  { to: "/admin/users", label: "Users" },
  { to: "/bank-statements", label: "Bank statements" },
  { to: "/admin/permissions", label: "Permissions" },
  { to: "/admin/ocr-metrics", label: "OCR metrics" },
  { to: "/admin/audit-logs", label: "Audit Logs" },
  { to: "/admin/settings", label: "Settings" },
];

export function Navbar() {
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const searchContainerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { user, logout, isAdmin } = useAuth();
  const isMobile = useIsMobile();

  const nav = isAdmin ? adminNav : financeNav;
  const homeTo = isAdmin ? "/admin/users" : "/";
  const showFinanceTools = !isAdmin;

  const displayName = user?.email?.split("@")[0] ?? "User";
  const initials = displayName.slice(0, 2).toUpperCase();
  const role = user?.role ? roleLabel(user.role) : "";

  const openSearch = useCallback(() => {
    setSearchOpen(true);
    if (!isMobile) {
      searchInputRef.current?.focus();
    }
  }, [isMobile]);

  const submitSearch = useCallback(() => {
    const trimmed = searchQuery.trim();
    if (trimmed.length < 2) return;
    setSearchOpen(false);
    navigate(`/documents?search=${encodeURIComponent(trimmed)}`);
  }, [navigate, searchQuery]);

  useEffect(() => {
    setMobileNavOpen(false);
    setUserMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!showFinanceTools) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        openSearch();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [openSearch, showFinanceTools]);

  useEffect(() => {
    if (!searchOpen) return;
    const onPointerDown = (event: MouseEvent) => {
      if (searchContainerRef.current?.contains(event.target as Node)) return;
      setSearchOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [searchOpen]);

  async function handleSignOut() {
    setUserMenuOpen(false);
    await logout();
    navigate("/login", { replace: true });
  }

  function navLinkClass(active: boolean, isAdminLink: boolean, mobile = false) {
    return cn(
      "rounded-md font-medium transition-colors",
      mobile ? "block px-3 py-2.5 text-[14px]" : "px-3 py-1.5 text-[13px]",
      active
        ? "bg-accent text-primary"
        : "text-muted-foreground hover:bg-secondary hover:text-foreground",
      isAdminLink && !active && "text-muted-foreground/90",
    );
  }

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-border bg-background">
        <div className="mx-auto flex h-14 max-w-[1600px] items-center gap-3 px-4 sm:gap-6 sm:px-6">
          <Link to={homeTo} className="flex shrink-0 items-center">
            <BrandLogo imageClassName="h-8 sm:h-9" />
          </Link>

          <nav className="hidden flex-1 items-center gap-1 md:flex">
            {nav.map((n) => {
              const active =
                n.to === "/" ? pathname === "/" : pathname.startsWith(n.to);
              const isAdminLink = n.to.startsWith("/admin");
              return (
                <Link
                  key={n.to}
                  to={n.to}
                  className={navLinkClass(active, isAdminLink)}
                >
                  {n.label}
                </Link>
              );
            })}
          </nav>

          <div className="ml-auto flex items-center gap-1 sm:gap-2">
            {showFinanceTools ? (
              <>
                <button
                  type="button"
                  onClick={() => setSearchOpen(true)}
                  className="grid h-8 w-8 place-items-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground md:hidden"
                  aria-label="Search invoices"
                >
                  <Search className="h-4 w-4" />
                </button>
                <div ref={searchContainerRef} className="relative hidden md:block">
                  <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                  <input
                    ref={searchInputRef}
                    type="search"
                    value={searchQuery}
                    onChange={(event) => {
                      setSearchQuery(event.target.value);
                      setSearchOpen(true);
                    }}
                    onFocus={() => setSearchOpen(true)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        submitSearch();
                      }
                      if (event.key === "Escape") {
                        setSearchOpen(false);
                        searchInputRef.current?.blur();
                      }
                    }}
                    placeholder="Search invoices, vendors, transactions…"
                    className={cn(
                      "h-8 w-[240px] rounded-md border border-input bg-background pl-8 pr-12 text-[13px] text-foreground lg:w-[320px]",
                      "placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring/60",
                      "[&::-webkit-search-cancel-button]:appearance-none",
                    )}
                    aria-label="Search invoices"
                    aria-expanded={searchOpen}
                    aria-controls="global-search-results"
                    autoComplete="off"
                  />
                  <button
                    type="button"
                    onClick={openSearch}
                    className="absolute right-2 top-1/2 -translate-y-1/2 rounded border border-border bg-background px-1 text-[10px] text-muted-foreground hover:text-foreground"
                    title="Focus search (⌘K)"
                  >
                    ⌘K
                  </button>
                  {isMobile ? null : (
                    <GlobalSearchDialog
                      anchored
                      open={searchOpen}
                      onOpenChange={setSearchOpen}
                      query={searchQuery}
                      onQueryChange={setSearchQuery}
                      onSubmit={submitSearch}
                    />
                  )}
                </div>
              </>
            ) : null}

            <ThemeToggle />

            <div className="relative">
              <button
                type="button"
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                className="flex h-8 items-center gap-2 rounded-md pl-1 pr-2 hover:bg-secondary"
              >
                <div className="grid h-6 w-6 place-items-center rounded-full bg-soft-navy text-[10px] font-semibold text-primary-foreground">
                  {initials}
                </div>
                <span className="hidden text-[13px] font-medium text-foreground md:inline">
                  {displayName}
                </span>
                <ChevronDown className="hidden h-3 w-3 text-muted-foreground md:block" />
              </button>
              {userMenuOpen && (
                <div className="absolute right-0 top-9 z-50 w-56 overflow-hidden rounded-md border border-border bg-popover py-1 shadow-md">
                  <div className="border-b border-border px-3 py-2">
                    <div className="text-[13px] font-medium text-foreground">
                      {displayName}
                    </div>
                    <div className="text-[11px] text-muted-foreground">
                      {user?.email ?? ""}
                    </div>
                    {role ? (
                      <div className="mt-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                        {role}
                      </div>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    onClick={() => void handleSignOut()}
                    className="block w-full px-3 py-2 text-left text-[13px] text-foreground hover:bg-accent"
                  >
                    Sign out
                  </button>
                </div>
              )}
            </div>

            <button
              type="button"
              onClick={() => setMobileNavOpen(!mobileNavOpen)}
              className="grid h-8 w-8 place-items-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground md:hidden"
              aria-expanded={mobileNavOpen}
              aria-label={mobileNavOpen ? "Close menu" : "Open menu"}
            >
              {mobileNavOpen ? (
                <X className="h-4 w-4" />
              ) : (
                <Menu className="h-4 w-4" />
              )}
            </button>
          </div>
        </div>

        {mobileNavOpen ? (
          <nav className="border-t border-border px-4 py-3 md:hidden">
            <div className="flex flex-col gap-0.5">
              {nav.map((n) => {
                const active =
                  n.to === "/" ? pathname === "/" : pathname.startsWith(n.to);
                const isAdminLink = n.to.startsWith("/admin");
                return (
                  <Link
                    key={n.to}
                    to={n.to}
                    className={navLinkClass(active, isAdminLink, true)}
                  >
                    {n.label}
                  </Link>
                );
              })}
            </div>
          </nav>
        ) : null}
      </header>

      {showFinanceTools && isMobile ? (
        <GlobalSearchDialog
          open={searchOpen}
          onOpenChange={setSearchOpen}
          query={searchQuery}
          onQueryChange={setSearchQuery}
          onSubmit={submitSearch}
        />
      ) : null}
    </>
  );
}
