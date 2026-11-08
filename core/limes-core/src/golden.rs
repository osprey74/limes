//! Golden decision cases, shared by the test suite and the pipeline's validation gate.

use serde::Deserialize;

use crate::{DriveTime, Vehicle, WayEvidence, decide};

#[derive(Deserialize)]
struct Case {
    name: String,
    #[serde(default)]
    time: Option<DriveTime>,
    evidence: WayEvidence,
    /// Fields of the expected Decision; fields left out are not checked.
    expect: serde_json::Map<String, serde_json::Value>,
}

/// Run the cases in `json` (an array of {name, time?, evidence, expect}) and
/// return one message per failing case.
pub fn check(json: &str) -> Result<Vec<String>, serde_json::Error> {
    let cases: Vec<Case> = serde_json::from_str(json)?;
    let mut failures = Vec::new();
    for case in &cases {
        let t = case.time.unwrap_or(DriveTime::REPRESENTATIVE);
        let got = serde_json::to_value(decide(&case.evidence, &t, Vehicle::OrdinaryCar))?;
        if case.expect.iter().any(|(k, v)| got.get(k) != Some(v)) {
            failures.push(format!(
                "{}: expected {}, got {got}",
                case.name,
                serde_json::Value::Object(case.expect.clone())
            ));
        }
    }
    Ok(failures)
}

/// The cases kept with the source.
pub const CASES: &str = include_str!("../tests/golden/decide.json");
