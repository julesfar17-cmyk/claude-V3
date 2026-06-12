import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

export default function ProtectedRoute({ children }) {
  const { user } = useAuth();

  if (user === undefined) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="font-osd text-sm text-[#d9ffd0] animate-pulse" data-testid="auth-loading">
          VÉRIFICATION…
        </div>
      </div>
    );
  }
  if (user === null) return <Navigate to="/login" replace />;
  return children;
}
