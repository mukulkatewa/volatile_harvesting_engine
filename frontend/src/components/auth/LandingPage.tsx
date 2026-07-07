import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Bell, Menu, Settings, TrendingUp, X, Zap } from "lucide-react";
import { useAuth } from "../../hooks/useAuth";
import { LaserFlow } from "@/components/ui/laser-flow";
import { Button } from "@/components/ui/button";

const NAV_LINKS = [
  { label: "Features", href: "#features" },
  { label: "Strategy", href: "#strategy" },
  { label: "Risk", href: "#risk" },
  { label: "About", href: "#about" },
];

const MOCK_QUOTES = [
  { symbol: "RELIANCE", ltp: "2,847.55", change: "+1.24%", positive: true },
  { symbol: "INFY",     ltp: "1,632.10", change: "+0.87%", positive: true },
  { symbol: "TCS",      ltp: "3,918.40", change: "-0.31%", positive: false },
  { symbol: "HDFCBANK", ltp: "1,743.80", change: "+0.56%", positive: true },
  { symbol: "ICICIBANK",ltp: "1,128.65", change: "+1.08%", positive: true },
];

const MOCK_STATS = [
  { label: "Virtual Equity",  value: "₹75,432",  sub: "+₹432 today",   positive: true  },
  { label: "Session P&L",     value: "+₹432",     sub: "+0.58%",        positive: true  },
  { label: "Gross Exposure",  value: "₹22,100",   sub: "29.3% deployed", positive: null  },
  { label: "Active Grids",    value: "3",          sub: "RELIANCE · INFY · TCS", positive: null },
];

export function LandingPage() {
  const { user, isLoading } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!isLoading && user) navigate("/dashboard", { replace: true });
  }, [user, isLoading, navigate]);

  const params = new URLSearchParams(window.location.search);
  const error = params.get("error");

  return (
    <section className="relative min-h-screen flex flex-col overflow-hidden bg-bg-deep w-full">
      {/* WebGL laser background */}
      <div className="absolute inset-0 z-0">
        <LaserFlow
          color="#00d09c"
          horizontalBeamOffset={0.25}
          verticalBeamOffset={0.0}
          flowSpeed={0.35}
          verticalSizing={30.0}
          horizontalSizing={0.5}
          fogIntensity={0.8}
          fogScale={0.28}
          wispSpeed={10.0}
          wispIntensity={6.0}
          flowStrength={0.3}
          decay={1.2}
          falloffStart={1.8}
          wispDensity={1.0}
          mouseTiltStrength={0.005}
          className="w-full h-full"
        />
      </div>

      {/* Ambient glow blobs */}
      <div className="absolute top-4 left-8 h-48 w-48 rounded-full bg-vhe-green/30 blur-[180px] z-0 pointer-events-none" />
      <div className="absolute top-20 right-16 h-32 w-32 rounded-full bg-vhe-blue/20 blur-[140px] z-0 pointer-events-none" />

      {/* Glassmorphic navbar */}
      <nav className="relative z-20 w-full">
        <div className="absolute inset-0 bg-bg-deep/30 backdrop-blur-md border-b border-white/[0.08]" />
        <div className="relative max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Logo */}
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-vhe-blue to-vhe-green flex items-center justify-center font-bold text-sm text-bg-deep shadow-lg shadow-vhe-green/20">
                V
              </div>
              <div>
                <span className="text-text-primary font-sans font-bold text-[15px]">VHE</span>
                <span className="hidden sm:inline text-text-faint font-mono text-[11px] ml-2 uppercase tracking-widest">
                  Volatility Engine
                </span>
              </div>
            </div>

            {/* Desktop nav links */}
            <div className="hidden md:flex items-center gap-8">
              {NAV_LINKS.map(({ label, href }) => (
                <a
                  key={label}
                  href={href}
                  className="text-text-muted hover:text-text-primary text-sm font-sans transition-colors"
                >
                  {label}
                </a>
              ))}
            </div>

            {/* CTA + mobile toggle */}
            <div className="flex items-center gap-3">
              <Button asChild variant="outline" size="sm" className="hidden md:inline-flex">
                <a href="/auth/google/login">Sign in</a>
              </Button>
              <button
                onClick={() => setMenuOpen(!menuOpen)}
                className="md:hidden p-2 text-text-muted hover:text-text-primary transition-colors"
                aria-label="Toggle menu"
              >
                {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            </div>
          </div>

          {/* Mobile menu */}
          {menuOpen && (
            <div className="md:hidden mt-4 pb-4 border-t border-white/[0.08] pt-4 flex flex-col gap-4">
              {NAV_LINKS.map(({ label, href }) => (
                <a key={label} href={href} className="text-text-muted hover:text-text-primary text-sm font-sans">
                  {label}
                </a>
              ))}
              <Button asChild variant="outline" size="sm" className="self-start">
                <a href="/auth/google/login">Sign in</a>
              </Button>
            </div>
          )}
        </div>
      </nav>

      {/* Hero content */}
      <div className="relative z-10 flex-1 flex flex-col justify-center pt-16 pb-12">
        <div className="max-w-7xl mx-auto px-6 w-full">

          {/* Badge pill */}
          <div className="inline-flex items-center gap-2 px-2 py-1 rounded-full bg-bg-card/60 backdrop-blur-sm border border-white/[0.12] mb-8">
            <span className="px-2 py-0.5 bg-vhe-green text-bg-deep text-xs font-bold rounded-full font-mono">New</span>
            <span className="text-sm text-text-muted font-sans pr-1">
              Walk-Forward Validation is live
            </span>
          </div>

          {/* Headline */}
          <h1 className="text-5xl md:text-7xl font-bold text-white leading-tight mb-6 max-w-3xl">
            Harvest Volatility.
            <br />
            <span className="text-text-muted">Maximize Alpha.</span>
          </h1>

          {/* Subheadline */}
          <p className="text-xl text-text-muted max-w-2xl leading-relaxed mb-10 font-sans">
            Systematic intraday grid trading on NSE equities — ATR-driven, sentiment-aware,
            Monte Carlo risk-validated. Paper trade with real market data.
          </p>

          {/* Feature pills */}
          <div className="flex flex-wrap gap-2 mb-10">
            {["ATR Grid Strategy", "Sentiment Engine", "Monte Carlo Risk", "Walk-Forward Validation", "Real-time WebSocket"].map((f) => (
              <span key={f} className="px-3 py-1 rounded-full bg-bg-card/50 border border-white/[0.10] text-text-muted text-xs font-mono backdrop-blur-sm">
                {f}
              </span>
            ))}
          </div>

          {/* CTA row */}
          {error && (
            <div className="mb-6 px-4 py-2.5 rounded-lg bg-vhe-red/10 border border-vhe-red/30 text-vhe-red text-sm font-mono inline-block">
              Authentication failed: {error}
            </div>
          )}

          <div className="flex flex-col sm:flex-row gap-4">
            <Button asChild size="lg">
              <a href="/auth/google/login" className="flex items-center gap-2">
                <svg viewBox="0 0 24 24" className="w-5 h-5 shrink-0" aria-hidden="true">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                Sign in with Google
                <ArrowRight className="w-4 h-4" />
              </a>
            </Button>
            <Button variant="outline" size="lg" asChild>
              <a href="#features">View Strategy</a>
            </Button>
          </div>

          <p className="mt-6 text-text-faint text-xs font-mono">
            Paper trading only · No real money · NSE equities simulation
          </p>
        </div>
      </div>

      {/* Mock dashboard preview */}
      <div className="relative z-10 px-6 pb-10">
        <div className="max-w-7xl mx-auto w-full">
          <div className="bg-bg-deep/80 backdrop-blur-xl rounded-2xl border border-white/[0.10] overflow-hidden shadow-2xl shadow-black/60">
            {/* Dashboard top bar */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
              <div className="flex items-center gap-6">
                <div className="flex items-center gap-2">
                  <Zap className="w-4 h-4 text-vhe-green" />
                  <span className="text-text-primary font-sans font-bold text-sm">VHE Terminal</span>
                </div>
                <div className="hidden sm:flex items-center gap-4 text-sm">
                  <button className="text-text-primary font-semibold font-sans">Trade</button>
                  <button className="text-text-muted hover:text-text-primary font-sans transition-colors">Strategies</button>
                  <button className="text-text-muted hover:text-text-primary font-sans transition-colors">Risk</button>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-vhe-green animate-pulse" />
                  <span className="text-text-muted text-xs font-mono hidden sm:block">Live</span>
                </div>
                <Bell className="w-4 h-4 text-text-faint" />
                <Settings className="w-4 h-4 text-text-faint" />
              </div>
            </div>

            {/* Dashboard content */}
            <div className="grid grid-cols-1 lg:grid-cols-5 gap-0 divide-y lg:divide-y-0 lg:divide-x divide-white/[0.06]">
              {/* Left: stat cards */}
              <div className="lg:col-span-2 p-5 space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  {MOCK_STATS.map(({ label, value, sub, positive }) => (
                    <div
                      key={label}
                      className="bg-gradient-to-br from-bg-card to-bg-panel rounded-xl border border-white/[0.07] p-3"
                    >
                      <div className="text-[10px] font-mono font-bold text-text-faint uppercase tracking-wider mb-1">
                        {label}
                      </div>
                      <div
                        className={`text-lg font-mono font-semibold ${
                          positive === true
                            ? "text-vhe-green"
                            : positive === false
                            ? "text-vhe-red"
                            : "text-text-primary"
                        }`}
                      >
                        {value}
                      </div>
                      <div className="text-[10px] font-mono text-text-faint mt-0.5">{sub}</div>
                    </div>
                  ))}
                </div>

                {/* Mini control strip */}
                <div className="flex gap-2">
                  {["Pause", "Resume", "Kill Switch"].map((label, i) => (
                    <span
                      key={label}
                      className={`px-3 py-1 rounded-full border text-xs font-mono font-semibold ${
                        i === 0
                          ? "border-vhe-amber/30 text-vhe-amber bg-vhe-amber/5"
                          : i === 1
                          ? "border-vhe-green/30 text-vhe-green bg-vhe-green/5"
                          : "border-vhe-red/30 text-vhe-red bg-vhe-red/5"
                      }`}
                    >
                      {label}
                    </span>
                  ))}
                </div>
              </div>

              {/* Right: live quotes table */}
              <div className="lg:col-span-3 p-5">
                <div className="flex items-center gap-2 mb-3">
                  <TrendingUp className="w-4 h-4 text-vhe-green" />
                  <span className="text-[11px] font-mono font-bold text-text-muted uppercase tracking-wider">
                    Live Quotes — NSE
                  </span>
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-[10px] font-mono font-bold text-text-faint uppercase border-b border-white/[0.06]">
                      <th className="text-left pb-2">Symbol</th>
                      <th className="text-right pb-2">LTP</th>
                      <th className="text-right pb-2">Change</th>
                      <th className="text-right pb-2 hidden sm:table-cell">Regime</th>
                    </tr>
                  </thead>
                  <tbody>
                    {MOCK_QUOTES.map((q) => (
                      <tr key={q.symbol} className="border-t border-white/[0.04] hover:bg-white/[0.02] transition-colors">
                        <td className="py-2.5 font-mono font-semibold text-text-primary">{q.symbol}</td>
                        <td className="py-2.5 font-mono text-right text-text-primary">₹{q.ltp}</td>
                        <td className={`py-2.5 font-mono text-right text-sm ${q.positive ? "text-vhe-green" : "text-vhe-red"}`}>
                          {q.change}
                        </td>
                        <td className="py-2.5 font-mono text-right text-text-faint text-xs hidden sm:table-cell">
                          {q.positive ? "trending" : "ranging"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom gradient fade */}
      <div className="absolute inset-0 z-[1] bg-gradient-to-t from-bg-deep/70 via-transparent to-bg-deep/40 pointer-events-none" />
    </section>
  );
}
