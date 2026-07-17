import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider } from "@/context/AuthContext";
import { I18nProvider } from "@/i18n";
import AuthCallback from "@/components/AuthCallback";
import ProtectedRoute from "@/components/ProtectedRoute";
import Landing from "@/pages/Landing";
import AuthPage from "@/pages/AuthPage";
import ForgotPassword from "@/pages/ForgotPassword";
import ResetPassword from "@/pages/ResetPassword";
import Dashboard from "@/pages/Dashboard";
import Studio from "@/pages/Studio";
import Projects from "@/pages/Projects";
import Admin from "@/pages/Admin";

function AppRouter() {
  // Lien affilié : beat-cut.com/?promo=CODE → mémorisé, la remise s'appliquera au paiement
  const promo = new URLSearchParams(window.location.search).get("promo");
  if (promo) {
    localStorage.setItem("bc_affiliate", promo.toUpperCase());
    window.history.replaceState({}, "", window.location.pathname);
  }
  // Le session_id du callback Google arrive en fragment d'URL : traité AVANT le routing normal
  if (window.location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<AuthPage />} />
      <Route path="/register" element={<AuthPage />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects"
        element={
          <ProtectedRoute>
            <Projects />
          </ProtectedRoute>
        }
      />
      <Route
        path="/studio"
        element={
          <ProtectedRoute>
            <Studio />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin"
        element={
          <ProtectedRoute>
            <Admin />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <I18nProvider>
        <AuthProvider>
          <AppRouter />
          <Toaster position="top-center" theme="dark" richColors />
        </AuthProvider>
      </I18nProvider>
    </BrowserRouter>
  );
}

export default App;
