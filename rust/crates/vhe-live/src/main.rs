use clap::Parser;
use tracing::info;
use vhe_core::{OrderSide, OrderType, StrategyIntent};
use vhe_risk::approve_intent;

#[derive(Debug, Parser)]
#[command(name = "vhe-live")]
struct Args {
    #[arg(long, default_value = "paper")]
    mode: String,

    #[arg(long, default_value_t = 25_000)]
    capital_cap: u32,
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();
    let args = Args::parse();

    let sample_intent = StrategyIntent {
        strategy_id: "bootstrap".to_string(),
        symbol: "RELIANCE".to_string(),
        side: OrderSide::Buy,
        order_type: OrderType::Limit,
        price: "100.00".parse().expect("valid decimal"),
        quantity: 10,
        reason: "bootstrap_check".to_string(),
        expires_at: chrono::DateTime::parse_from_rfc3339("2026-06-14T15:10:00+05:30")
            .expect("valid timestamp"),
    };

    let decision = approve_intent(&sample_intent, args.capital_cap / 2_500);
    info!(mode = %args.mode, approved = decision.approved, final_quantity = decision.final_quantity, "vhe-live bootstrap");
}

