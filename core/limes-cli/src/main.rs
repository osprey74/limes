//! limes-cli: the data pipeline's entry to limes-core.
//!
//!   limes-cli decide [--at MMDD-hhmm-W[-H]] < evidence.ndjson > decisions.ndjson
//!   limes-cli golden [cases.json]
//!
//! `decide` reads one WayEvidence JSON object per line and writes one line per
//! way: {"osm_id", "decision", "time_dependent"}. `--at` sets the date and time
//! (W: 0 = Monday ... 6 = Sunday, trailing -H for a holiday); the default is a
//! weekday noon. `golden` runs decision cases and exits 1 on any failure.

use std::io::{self, BufRead, BufWriter, Write};
use std::process::ExitCode;

use limes_core::{DriveTime, Vehicle, WayEvidence, decide, golden};
use serde::Serialize;

#[derive(Serialize)]
struct Output<'a> {
    osm_id: i64,
    decision: &'a limes_core::Decision,
    /// Some regulation on the way depends on date, time or weekday, so the
    /// decision is only valid for the time given.
    time_dependent: bool,
}

fn parse_at(s: &str) -> Result<DriveTime, String> {
    let parts: Vec<&str> = s.split('-').collect();
    let bad = || format!("--at expects MMDD-hhmm-W[-H], got {s}");
    if !(3..=4).contains(&parts.len()) || parts[0].len() != 4 || parts[1].len() != 4 {
        return Err(bad());
    }
    let num = |p: &str| p.parse::<u16>().map_err(|_| bad());
    let (mmdd, hhmm, weekday) = (num(parts[0])?, num(parts[1])?, num(parts[2])?);
    if weekday > 6 || (parts.len() == 4 && parts[3] != "H") {
        return Err(bad());
    }
    Ok(DriveTime {
        month: (mmdd / 100) as u8,
        day: (mmdd % 100) as u8,
        minute_of_day: hhmm / 100 * 60 + hhmm % 100,
        weekday: weekday as u8,
        holiday: parts.len() == 4,
    })
}

fn run_decide(args: &[String]) -> Result<(), String> {
    let t = match args {
        [] => DriveTime::REPRESENTATIVE,
        [flag, value] if flag == "--at" => parse_at(value)?,
        _ => return Err("usage: limes-cli decide [--at MMDD-hhmm-W[-H]]".into()),
    };
    let stdout = io::stdout();
    let mut out = BufWriter::new(stdout.lock());
    for (n, line) in io::stdin().lock().lines().enumerate() {
        let line = line.map_err(|e| e.to_string())?;
        if line.trim().is_empty() {
            continue;
        }
        let evidence: WayEvidence =
            serde_json::from_str(&line).map_err(|e| format!("line {}: {e}", n + 1))?;
        let decision = decide(&evidence, &t, Vehicle::OrdinaryCar);
        let time_dependent = evidence
            .regulations
            .iter()
            .any(|r| r.conditions.is_time_dependent());
        let record = Output {
            osm_id: evidence.osm_id,
            decision: &decision,
            time_dependent,
        };
        serde_json::to_writer(&mut out, &record).map_err(|e| e.to_string())?;
        out.write_all(b"\n").map_err(|e| e.to_string())?;
    }
    out.flush().map_err(|e| e.to_string())
}

fn run_golden(args: &[String]) -> Result<bool, String> {
    let json = match args {
        [] => golden::CASES.to_string(),
        [path] => std::fs::read_to_string(path).map_err(|e| format!("{path}: {e}"))?,
        _ => return Err("usage: limes-cli golden [cases.json]".into()),
    };
    let failures = golden::check(&json).map_err(|e| e.to_string())?;
    for f in &failures {
        eprintln!("FAIL {f}");
    }
    Ok(failures.is_empty())
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let result = match args.first().map(String::as_str) {
        Some("decide") => run_decide(&args[1..]).map(|()| true),
        Some("golden") => run_golden(&args[1..]),
        _ => Err("usage: limes-cli <decide|golden> ...".into()),
    };
    match result {
        Ok(true) => ExitCode::SUCCESS,
        Ok(false) => ExitCode::FAILURE,
        Err(e) => {
            eprintln!("{e}");
            ExitCode::from(2)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::parse_at;

    #[test]
    fn at_format() {
        let t = parse_at("1231-2215-6-H").unwrap();
        assert_eq!(
            (t.month, t.day, t.minute_of_day, t.weekday, t.holiday),
            (12, 31, 22 * 60 + 15, 6, true)
        );
        assert!(!parse_at("0101-0800-0").unwrap().holiday);
        assert!(parse_at("101-0800-0").is_err());
        assert!(parse_at("0101-0800-7").is_err());
    }
}
