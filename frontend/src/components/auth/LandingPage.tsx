import { Component, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  Bell,
  BarChart2,
  Brain,
  CheckCircle,
  Menu,
  Settings,
  ShieldCheck,
  TrendingUp,
  X,
  Zap,
} from "lucide-react";
import { useAuth } from "../../hooks/useAuth";
import { LaserFlow } from "@/components/ui/laser-flow";
import { Button } from "@/components/ui/button";

const NAV_LINKS = [
  { label: "Features",  href: "#features" },
  { label: "Strategy",  href: "#strategy" },
  { label: "Risk",      href: "#risk" },
  { label: "About",     href: "#about" },
];

const MOCK_QUOTES = [
  { symbol: "RELIANCE",  ltp: "2,847.55", change: "+1.24%", positive: true  },
  { symbol: "INFY",      ltp: "1,632.10", change: "+0.87%", positive: true  },
  { symbol: "TCS",       ltp: "3,918.40", change: "-0.31%", positive: false },
  { symbol: "HDFCBANK",  ltp: "1,743.80", change: "+0.56%", positive: true  },
  { symbol: "ICICIBANK", ltp: "1,128.65", change: "+1.08%", positive: true  },
];

const MOCK_STATS = [
  { label: "Virtual Equity",  value: "₹75,432",  sub: "+₹432 today",       positive: true  },
  { label: "Session P&L",     value: "+₹432",     sub: "+0.58%",            positive: true  },
  { label: "Gross Exposure",  value: "₹22,100",   sub: "29.3% deployed",    positive: null  },
  { label: "Active Grids",    value: "3",          sub: "RELIANCE·INFY·TCS", positive: null  },
];

const FEATURES = [
  {
    icon: TrendingUp,
    title: "ATR-Driven Grid Strategy",
    desc: "Dynamically sizes grid spacing using Average True Range so position density adapts to real intraday volatility — not fixed percentages.",
  },
  {
    icon: Brain,
    title: "Sentiment Engine",
    desc: "Scans Reddit, news headlines, and social feeds in real time. Biases symbol selection and position limits based on sentiment score.",
  },
  {
    icon: BarChart2,
    title: "Monte Carlo Risk Engine",
    desc: "Bootstrap-resamples your trade log 10,000 times to produce P&L distributions, VaR 95%, CVaR, probability of ruin, and Kelly fraction.",
  },
  {
    icon: ShieldCheck,
    title: "Walk-Forward Validation",
    desc: "Proves parameters aren't curve-fitted by rolling 60-day train / 15-day out-of-sample windows. Walk-Forward Efficiency > 0.5 = not overfit.",
  },
  {
    icon: Zap,
    title: "Real-Time WebSocket Feed",
    desc: "Live state pushed to every connected tab via WebSocket. Quotes, fills, events, and portfolio stats update without polling.",
  },
  {
    icon: Activity,
    title: "Event-Driven Backtester",
    desc: "Replays historical bar-by-bar with the same risk guard, position sizing, and broker execution path used in live paper trading.",
  },
];

const ERROR_MESSAGES: Record<string, string> = {
  oauth_not_configured:
    "Google OAuth is not configured. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to your .env file and restart the server.",
  oauth_failed:
    "Google authentication failed. Check that your OAuth credentials are correct and the redirect URI is registered.",
  no_code:
    "No authorisation code was returned by Google. Try signing in again.",
  session_failed:
    "Your session could not be established. Please try signing in again.",
  no_db:
    "Database is unavailable. Ensure the server started correctly.",
};

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
}

class LaserErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; }
  render() {
    if (this.state.hasError) return null;
    return this.props.children;
  }
}

export function LandingPage() {
  const { user, isLoading } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!isLoading && user) navigate("/dashboard", { replace: true });
  }, [user, isLoading, navigate]);

  const params = new URLSearchParams(window.location.search);
  const errorKey = params.get("error");
  const errorMsg = errorKey ? (ERROR_MESSAGES[errorKey] ?? `Authentication error: ${errorKey}`) : null;

  const handleNavClick = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    if (href.startsWith("#")) {
      e.preventDefault();
      const id = href.slice(1);
      setMenuOpen(false);
      scrollTo(id);
    }
  };

  return (
    <div className="bg-bg-deep text-text-primary">
      {/* ── HERO SECTION ──────────────────────────────────────── */}
      <section className="relative min-h-screen flex flex-col overflow-hidden w-full">
        {/* WebGL laser background */}
        <div className="absolute inset-0 z-0">
          <LaserErrorBoundary>
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
          </LaserErrorBoundary>
        </div>

        {/* Ambient glow */}
        <div className="absolute top-4 left-8 h-48 w-48 rounded-full bg-vhe-green/30 blur-[180px] z-0 pointer-events-none" />
        <div className="absolute top-20 right-16 h-32 w-32 rounded-full bg-vhe-blue/20 blur-[140px] z-0 pointer-events-none" />

        {/* Glassmorphic navbar */}
        <nav className="relative z-20 w-full">
          <div className="absolute inset-0 bg-bg-deep/30 backdrop-blur-md border-b border-white/[0.08]" />
          <div className="relative max-w-7xl mx-auto px-6 py-4">
            <div className="flex items-center justify-between">
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

              <div className="hidden md:flex items-center gap-8">
                {NAV_LINKS.map(({ label, href }) => (
                  <a
                    key={label}
                    href={href}
                    onClick={(e) => handleNavClick(e, href)}
                    className="text-text-muted hover:text-text-primary text-sm font-sans transition-colors"
                  >
                    {label}
                  </a>
                ))}
              </div>

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

            {menuOpen && (
              <div className="md:hidden mt-4 pb-4 border-t border-white/[0.08] pt-4 flex flex-col gap-4">
                {NAV_LINKS.map(({ label, href }) => (
                  <a
                    key={label}
                    href={href}
                    onClick={(e) => handleNavClick(e, href)}
                    className="text-text-muted hover:text-text-primary text-sm font-sans"
                  >
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
            <div className="inline-flex items-center gap-2 px-2 py-1 rounded-full bg-bg-card/60 backdrop-blur-sm border border-white/[0.12] mb-8">
              <span className="px-2 py-0.5 bg-vhe-green text-bg-deep text-xs font-bold rounded-full font-mono">New</span>
              <span className="text-sm text-text-muted font-sans pr-1">Walk-Forward Validation is live</span>
            </div>

            <h1 className="text-5xl md:text-7xl font-bold text-white leading-tight mb-6 max-w-3xl">
              Harvest Volatility.
              <br />
              <span className="text-text-muted">Maximize Alpha.</span>
            </h1>

            <p className="text-xl text-text-muted max-w-2xl leading-relaxed mb-10 font-sans">
              Systematic intraday grid trading on NSE equities — ATR-driven, sentiment-aware,
              Monte Carlo risk-validated. Paper trade with real market data.
            </p>

            <div className="flex flex-wrap gap-2 mb-10">
              {["ATR Grid Strategy", "Sentiment Engine", "Monte Carlo Risk", "Walk-Forward Validation", "Real-time WebSocket"].map((f) => (
                <span key={f} className="px-3 py-1 rounded-full bg-bg-card/50 border border-white/[0.10] text-text-muted text-xs font-mono backdrop-blur-sm">
                  {f}
                </span>
              ))}
            </div>

            {errorMsg && (
              <div className="mb-6 max-w-xl px-4 py-3 rounded-lg bg-vhe-red/10 border border-vhe-red/30 text-vhe-red text-sm font-sans">
                {errorMsg}
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
              <Button
                variant="outline"
                size="lg"
                onClick={() => scrollTo("strategy")}
              >
                View Strategy
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

              <div className="grid grid-cols-1 lg:grid-cols-5 gap-0 divide-y lg:divide-y-0 lg:divide-x divide-white/[0.06]">
                <div className="lg:col-span-2 p-5 space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    {MOCK_STATS.map(({ label, value, sub, positive }) => (
                      <div key={label} className="bg-gradient-to-br from-bg-card to-bg-panel rounded-xl border border-white/[0.07] p-3">
                        <div className="text-[10px] font-mono font-bold text-text-faint uppercase tracking-wider mb-1">{label}</div>
                        <div className={`text-lg font-mono font-semibold ${positive === true ? "text-vhe-green" : positive === false ? "text-vhe-red" : "text-text-primary"}`}>{value}</div>
                        <div className="text-[10px] font-mono text-text-faint mt-0.5">{sub}</div>
                      </div>
                    ))}
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    {["Pause", "Resume", "Kill Switch"].map((label, i) => (
                      <span key={label} className={`px-3 py-1 rounded-full border text-xs font-mono font-semibold ${i === 0 ? "border-vhe-amber/30 text-vhe-amber bg-vhe-amber/5" : i === 1 ? "border-vhe-green/30 text-vhe-green bg-vhe-green/5" : "border-vhe-red/30 text-vhe-red bg-vhe-red/5"}`}>{label}</span>
                    ))}
                  </div>
                </div>

                <div className="lg:col-span-3 p-5">
                  <div className="flex items-center gap-2 mb-3">
                    <TrendingUp className="w-4 h-4 text-vhe-green" />
                    <span className="text-[11px] font-mono font-bold text-text-muted uppercase tracking-wider">Live Quotes — NSE</span>
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
                          <td className={`py-2.5 font-mono text-right text-sm ${q.positive ? "text-vhe-green" : "text-vhe-red"}`}>{q.change}</td>
                          <td className="py-2.5 font-mono text-right text-text-faint text-xs hidden sm:table-cell">{q.positive ? "trending" : "ranging"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="absolute inset-0 z-[1] bg-gradient-to-t from-bg-deep/70 via-transparent to-bg-deep/40 pointer-events-none" />
      </section>

      {/* ── FEATURES SECTION ───────────────────────────────────── */}
      <section id="features" className="py-24 px-6 border-t border-white/[0.06]">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <span className="text-vhe-green font-mono text-xs uppercase tracking-widest">Platform Features</span>
            <h2 className="text-3xl md:text-4xl font-bold text-text-primary mt-3">
              Everything a quant needs
            </h2>
            <p className="text-text-muted mt-4 max-w-xl mx-auto font-sans">
              Built from first principles — no black boxes, every component is inspectable,
              testable, and explainable.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map(({ icon: Icon, title, desc }) => (
              <div
                key={title}
                className="bg-gradient-to-br from-bg-card to-bg-panel rounded-xl border border-white/[0.08] p-6 hover:border-vhe-green/20 transition-colors group"
              >
                <div className="w-10 h-10 rounded-lg bg-vhe-green/10 border border-vhe-green/20 flex items-center justify-center mb-4 group-hover:bg-vhe-green/15 transition-colors">
                  <Icon className="w-5 h-5 text-vhe-green" />
                </div>
                <h3 className="text-text-primary font-sans font-semibold mb-2">{title}</h3>
                <p className="text-text-muted text-sm font-sans leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── STRATEGY SECTION ───────────────────────────────────── */}
      <section id="strategy" className="py-24 px-6 border-t border-white/[0.06]">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
            <div>
              <span className="text-vhe-green font-mono text-xs uppercase tracking-widest">How it works</span>
              <h2 className="text-3xl md:text-4xl font-bold text-text-primary mt-3 mb-6">
                ATR-Driven Grid Strategy
              </h2>
              <div className="space-y-5">
                {[
                  { step: "01", title: "Regime Detection", desc: "Market Regime Classifier reads volatility, volume, and momentum to label each symbol trending, ranging, or volatile." },
                  { step: "02", title: "ATR Grid Placement", desc: "Grid levels are spaced at atr_multiplier × ATR(14). Wider in volatile regimes, tighter in ranges — always sized to true intraday movement." },
                  { step: "03", title: "Sentiment Overlay", desc: "Sentiment Engine scores news and social feeds. Negative sentiment halves position size; strongly positive doubles it, up to the risk cap." },
                  { step: "04", title: "Risk Guard & Exit", desc: "Hard daily loss limit, per-symbol exposure cap, and force-exit at 15:10 IST. Kill switch halts all new orders instantly." },
                ].map(({ step, title, desc }) => (
                  <div key={step} className="flex gap-4">
                    <div className="w-8 h-8 rounded-full bg-vhe-green/10 border border-vhe-green/25 flex items-center justify-center shrink-0 mt-0.5">
                      <span className="text-vhe-green font-mono text-xs font-bold">{step}</span>
                    </div>
                    <div>
                      <div className="text-text-primary font-sans font-semibold text-sm">{title}</div>
                      <div className="text-text-muted font-sans text-sm mt-1 leading-relaxed">{desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Code-style visual */}
            <div className="bg-gradient-to-br from-bg-card to-bg-panel rounded-2xl border border-white/[0.08] p-6 font-mono text-sm">
              <div className="flex items-center gap-2 mb-4 pb-4 border-b border-white/[0.06]">
                <div className="w-3 h-3 rounded-full bg-vhe-red/60" />
                <div className="w-3 h-3 rounded-full bg-vhe-amber/60" />
                <div className="w-3 h-3 rounded-full bg-vhe-green/60" />
                <span className="text-text-faint text-xs ml-2">adaptive_grid.py</span>
              </div>
              <pre className="text-sm leading-relaxed overflow-x-auto">
                <span className="text-vhe-blue">class</span>{" "}
                <span className="text-vhe-green">AdaptiveGridStrategy</span>
                {":\n"}
                {"  "}<span className="text-text-faint"># space levels by ATR</span>{"\n"}
                {"  "}<span className="text-text-muted">grid_spacing</span>{" = "}
                <span className="text-vhe-amber">atr_mult</span>
                {" × "}
                <span className="text-text-primary">ATR(14)</span>
                {"\n\n"}
                {"  "}<span className="text-vhe-blue">def</span>{" "}
                <span className="text-vhe-green">on_quote</span>
                {"(self, q):\n"}
                {"    "}<span className="text-text-muted">regime</span>{" = "}
                <span className="text-text-primary">classifier.label(q)</span>
                {"\n"}
                {"    "}<span className="text-text-muted">sentiment</span>{" = "}
                <span className="text-text-primary">engine.score(q.symbol)</span>
                {"\n"}
                {"    "}<span className="text-text-muted">levels</span>{" = "}
                <span className="text-text-primary">self.build_grid(regime)</span>
                {"\n"}
                {"    "}<span className="text-text-muted">orders</span>{" = "}
                <span className="text-text-primary">risk_guard.filter(levels)</span>
                {"\n"}
                {"    "}<span className="text-vhe-blue">return</span>{" "}
                <span className="text-text-primary">broker.submit(orders)</span>
              </pre>
            </div>
          </div>
        </div>
      </section>

      {/* ── RISK SECTION ───────────────────────────────────────── */}
      <section id="risk" className="py-24 px-6 border-t border-white/[0.06]">
        <div className="max-w-7xl mx-auto text-center">
          <span className="text-vhe-green font-mono text-xs uppercase tracking-widest">Risk Management</span>
          <h2 className="text-3xl md:text-4xl font-bold text-text-primary mt-3 mb-4">
            Statistician-grade validation
          </h2>
          <p className="text-text-muted max-w-xl mx-auto font-sans mb-16">
            Every strategy is stress-tested before deployment. Monte Carlo and Walk-Forward
            are first-class citizens, not afterthoughts.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              { label: "VaR 95%",              value: "−₹3,200",  note: "5th percentile outcome across 10k simulations" },
              { label: "Walk-Forward Eff.",    value: "0.64",     note: "> 0.5 = strategy survives out-of-sample" },
              { label: "Probability of Ruin",  value: "2.1%",     note: "Equity falling below 50% of starting capital" },
            ].map(({ label, value, note }) => (
              <div key={label} className="bg-gradient-to-br from-bg-card to-bg-panel rounded-xl border border-white/[0.08] p-6 text-center">
                <div className="text-3xl font-mono font-bold text-vhe-green mb-2">{value}</div>
                <div className="text-text-primary font-sans font-semibold text-sm mb-1">{label}</div>
                <div className="text-text-faint font-sans text-xs">{note}</div>
              </div>
            ))}
          </div>

          <div className="mt-8 flex flex-wrap justify-center gap-4">
            {["Bootstrap Monte Carlo", "10,000 simulations", "CVaR / Expected Shortfall", "Kelly Criterion", "Walk-Forward Windows", "Param Stability Score"].map((tag) => (
              <span key={tag} className="px-3 py-1 rounded-full bg-bg-card border border-white/[0.08] text-text-muted text-xs font-mono">
                {tag}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ── ABOUT / CTA SECTION ────────────────────────────────── */}
      <section id="about" className="py-24 px-6 border-t border-white/[0.06]">
        <div className="max-w-3xl mx-auto text-center">
          <span className="text-vhe-green font-mono text-xs uppercase tracking-widest">Open Platform</span>
          <h2 className="text-3xl md:text-4xl font-bold text-text-primary mt-3 mb-6">
            Built for engineers, by an engineer
          </h2>
          <p className="text-text-muted font-sans leading-relaxed mb-8">
            VHE is a portfolio project demonstrating production-grade quantitative trading
            infrastructure — event-driven backtester, risk analytics, and a React dashboard
            connected via WebSocket to a FastAPI backend. Paper trading only; no real money.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-8">
            {[
              { icon: CheckCircle, text: "FastAPI + SQLite backend" },
              { icon: CheckCircle, text: "React 18 + Vite + Tailwind" },
              { icon: CheckCircle, text: "Python 3.12, fully typed" },
              { icon: CheckCircle, text: "147 passing tests" },
            ].map(({ icon: Icon, text }) => (
              <div key={text} className="flex items-center gap-2 text-sm text-text-muted font-sans">
                <Icon className="w-4 h-4 text-vhe-green shrink-0" />
                {text}
              </div>
            ))}
          </div>

          <Button asChild size="lg">
            <a href="/auth/google/login" className="flex items-center gap-2">
              <svg viewBox="0 0 24 24" className="w-5 h-5 shrink-0" aria-hidden="true">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              Get Started — Sign in with Google
              <ArrowRight className="w-4 h-4" />
            </a>
          </Button>

          <p className="mt-6 text-text-faint text-xs font-mono">
            Requires Google OAuth credentials in <code className="bg-bg-card px-1.5 py-0.5 rounded text-text-muted">.env</code> — see setup instructions in the repo.
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/[0.06] py-8 px-6">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-text-faint text-xs font-mono">
          <span>VHE · Volatility Harvesting Engine · Paper trading only</span>
          <div className="flex items-center gap-4">
            {NAV_LINKS.map(({ label, href }) => (
              <a key={label} href={href} onClick={(e) => handleNavClick(e, href)} className="hover:text-text-muted transition-colors">
                {label}
              </a>
            ))}
          </div>
        </div>
      </footer>
    </div>
  );
}
