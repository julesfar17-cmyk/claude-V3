import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Menu, X, Clapperboard, LogOut } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export const Logo = ({ className = "" }) => (
  <Link to="/" data-testid="nav-logo" className={`font-display text-xl font-extrabold tracking-tight text-foreground ${className}`}>
    BEAT<span className="text-primary">CUT</span>
  </Link>
);

export default function Navbar({ landing = false }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate("/");
  };

  const links = landing
    ? [
        { href: "#fonctionnalites", label: "Fonctionnalités" },
        { href: "#comment", label: "Comment ça marche" },
        { href: "#tarifs", label: "Tarifs" },
      ]
    : [];

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-xl">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="rec-dot" aria-hidden="true" />
          <Logo />
        </div>

        <nav className="hidden md:flex items-center gap-8">
          {links.map((l) => (
            <a key={l.href} href={l.href} className="text-sm text-muted-foreground hover:text-foreground transition-colors">
              {l.label}
            </a>
          ))}
        </nav>

        <div className="hidden md:flex items-center gap-3">
          {user ? (
            <>
              <Link
                to="/dashboard"
                data-testid="nav-dashboard-link"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Mon compte
              </Link>
              <Link
                to="/studio"
                data-testid="nav-studio-link"
                className="inline-flex items-center gap-2 bg-primary text-white text-sm font-bold px-5 py-2.5 hover:bg-[#d32f2f] transition-all hover:-translate-y-0.5 shadow-[0_0_15px_rgba(255,59,48,0.35)]"
              >
                <Clapperboard size={16} /> Ouvrir le studio
              </Link>
              <button
                onClick={handleLogout}
                data-testid="nav-logout-button"
                title="Se déconnecter"
                className="text-muted-foreground hover:text-foreground transition-colors p-2"
              >
                <LogOut size={16} />
              </button>
            </>
          ) : (
            <>
              <Link to="/login" data-testid="nav-login-link" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                Se connecter
              </Link>
              <Link
                to="/register"
                data-testid="nav-register-link"
                className="bg-primary text-white text-sm font-bold px-5 py-2.5 hover:bg-[#d32f2f] transition-all hover:-translate-y-0.5 shadow-[0_0_15px_rgba(255,59,48,0.35)]"
              >
                Commencer gratuitement
              </Link>
            </>
          )}
        </div>

        <button
          className="md:hidden p-2 text-foreground"
          onClick={() => setOpen(!open)}
          data-testid="nav-mobile-toggle"
          aria-label="Menu"
        >
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>

      {open && (
        <div className="md:hidden border-t border-border bg-background px-5 py-4 flex flex-col gap-4" data-testid="nav-mobile-menu">
          {links.map((l) => (
            <a key={l.href} href={l.href} onClick={() => setOpen(false)} className="text-sm text-muted-foreground">
              {l.label}
            </a>
          ))}
          {user ? (
            <>
              <Link to="/dashboard" onClick={() => setOpen(false)} className="text-sm text-foreground" data-testid="nav-mobile-dashboard">
                Mon compte
              </Link>
              <Link
                to="/studio"
                onClick={() => setOpen(false)}
                className="bg-primary text-white text-sm font-bold px-5 py-3 text-center"
                data-testid="nav-mobile-studio"
              >
                Ouvrir le studio
              </Link>
              <button onClick={handleLogout} className="text-sm text-muted-foreground text-left" data-testid="nav-mobile-logout">
                Se déconnecter
              </button>
            </>
          ) : (
            <>
              <Link to="/login" onClick={() => setOpen(false)} className="text-sm text-foreground" data-testid="nav-mobile-login">
                Se connecter
              </Link>
              <Link
                to="/register"
                onClick={() => setOpen(false)}
                className="bg-primary text-white text-sm font-bold px-5 py-3 text-center"
                data-testid="nav-mobile-register"
              >
                Commencer gratuitement
              </Link>
            </>
          )}
        </div>
      )}
    </header>
  );
}
