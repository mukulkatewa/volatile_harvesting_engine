use serde::{Deserialize, Serialize};
use vhe_core::StrategyIntent;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RiskDecision {
    pub approved: bool,
    pub final_quantity: u32,
    pub checks: Vec<String>,
}

pub fn approve_intent(intent: &StrategyIntent, max_quantity: u32) -> RiskDecision {
    if intent.quantity == 0 {
        return RiskDecision {
            approved: false,
            final_quantity: 0,
            checks: vec!["quantity_non_zero".to_string()],
        };
    }

    let final_quantity = intent.quantity.min(max_quantity);
    let approved = final_quantity > 0;
    RiskDecision {
        approved,
        final_quantity,
        checks: vec!["quantity_cap".to_string()],
    }
}

