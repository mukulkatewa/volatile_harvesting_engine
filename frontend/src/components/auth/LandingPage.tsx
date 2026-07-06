import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";

export function LandingPage() {
  const { user, isLoading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isLoading && user) navigate("/dashboard", { replace: true });
  }, [user, isLoading, navigate]);

  const params = new URLSearchParams(window.location.search);
  const error = params.get("error");

  return (
    <div className="min-h-screen bg-bg-deep flex flex-col items-center justify-center relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-[10%] w-[400px] h-[400px] bg-vhe-blue/10 rounded-full blur-3xl" />
        <div className="absolute top-0 right-[5%] w-[300px] h-[300px] bg-vhe-green/[0.08] rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 flex flex-col items-center gap-8 max-w-md w-full px-6">
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-vhe-blue to-vhe-green flex items-center justify-center text-2xl font-bold shadow-lg">
            V
          </div>
          <div className="text-center">
            <h1 className="text-3xl font-bold text-text-primary font-sans tracking-tight">VHE</h1>
            <p className="text-text-muted text-sm font-mono uppercase tracking-widest mt-1">
              Volatility Harvesting Engine
            </p>
          </div>
        </div>

        <div className="text-center space-y-2">
          <p className="text-text-primary font-sans text-base leading-relaxed">
            Systematic intraday grid trading with real-time sentiment analysis, Monte Carlo risk
            simulation, and walk-forward validation.
          </p>
          <p className="text-text-muted font-sans text-sm">
            Paper trading · NSE equities · ATR-driven grid strategy
          </p>
        </div>

        <div className="flex flex-wrap gap-2 justify-center">
          {["Grid Strategy", "Pair Spread", "Sentiment Engine", "Monte Carlo", "Walk-Forward"].map(
            (f) => (
              <span
                key={f}
                className="px-3 py-1 rounded-full bg-bg-card border border-white/10 text-text-muted text-xs font-mono"
              >
                {f}
              </span>
            )
          )}
        </div>

        {error && (
          <div className="w-full p-3 rounded-lg bg-vhe-red/10 border border-vhe-red/30 text-vhe-red text-sm font-mono text-center">
            Authentication failed: {error}
          </div>
        )}

        <a
          href="/auth/google/login"
          className="w-full flex items-center justify-center gap-3 py-3 px-6 rounded-xl bg-bg-card border border-white/15 text-text-primary font-sans font-semibold text-sm hover:border-vhe-blue/50 hover:bg-bg-elevated transition-all duration-200 group"
        >
          <svg viewBox="0 0 24 24" className="w-5 h-5 shrink-0" aria-hidden="true">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
          </svg>
          Sign in with Google
          <span className="ml-auto text-text-faint group-hover:text-text-muted transition-colors">→</span>
        </a>

        <p className="text-text-faint text-xs font-mono text-center">
          Paper trading only · No real money · For portfolio demonstration
        </p>
      </div>
    </div>
  );
}
