//! limes-cli: the data pipeline's entry to limes-core.
//!
//!   limes-cli decide [--at MMDD-hhmm-W[-H]] < evidence.ndjson > decisions.ndjson
//!   limes-cli golden [cases.json]
//!   limes-cli build-db --out pref.sqlite [--meta key=value]... < evidence.ndjson
//!   limes-cli locate --db pref.sqlite lon,lat[,heading,speed_mps]...
//!   limes-cli package --db pref.sqlite --out-dir dist [--level 1-22]
//!
//! `decide` reads one WayEvidence JSON object per line and writes one line per
//! way: {"osm_id", "decision", "time_dependent"}. `--at` sets the date and time
//! (W: 0 = Monday ... 6 = Sunday, trailing -H for a holiday); the default is a
//! weekday noon. `golden` runs decision cases, prints the count and exits 1 on
//! any failure.
//! `build-db` decides every segment of the pipeline's evidence NDJSON and writes
//! the prefecture database, then prints the length per stage and confidence.
//! `locate` map-matches fixes against a database (one result line per fix).
//! `package` compresses a database (meta `prefecture` and `version` required)
//! to `<out-dir>/<prefecture>-<version>.sqlite.zst` and adds or replaces its
//! entry in `<out-dir>/manifest.json`.

use std::io::{self, BufRead, BufWriter, Write};
use std::process::ExitCode;

use std::collections::BTreeMap;
use std::path::PathBuf;

use limes_core::db::{Reader, SegmentRecord, Writer};
use limes_core::matcher::{Fix, Matcher};
use limes_core::update::{self, Manifest};
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
    let cases = serde_json::from_str::<Vec<serde_json::Value>>(&json).map_or(0, |c| c.len());
    eprintln!("{cases} cases, {} failed", failures.len());
    Ok(failures.is_empty())
}

fn run_build_db(args: &[String]) -> Result<(), String> {
    let usage = || "usage: limes-cli build-db --out pref.sqlite [--meta key=value]...".to_string();
    let (mut out, mut meta) = (None, Vec::new());
    let mut it = args.iter();
    while let Some(flag) = it.next() {
        let value = it.next().ok_or_else(usage)?;
        match flag.as_str() {
            "--out" => out = Some(PathBuf::from(value)),
            "--meta" => meta.push(value.split_once('=').ok_or_else(usage)?),
            _ => return Err(usage()),
        }
    }
    let out = out.ok_or_else(usage)?;
    let mut writer = Writer::create(&out).map_err(|e| e.to_string())?;
    for (key, value) in meta {
        writer.set_meta(key, value).map_err(|e| e.to_string())?;
    }
    let mut km: BTreeMap<(i32, &str), f64> = BTreeMap::new();
    for (n, line) in io::stdin().lock().lines().enumerate() {
        let line = line.map_err(|e| e.to_string())?;
        if line.trim().is_empty() {
            continue;
        }
        let record: SegmentRecord =
            serde_json::from_str(&line).map_err(|e| format!("line {}: {e}", n + 1))?;
        let d = writer
            .add(&record)
            .map_err(|e| format!("line {}: {e}", n + 1))?;
        *km.entry((d.stage.number(), d.confidence.as_str()))
            .or_default() += record.length_m / 1000.0;
    }
    let count = writer.finish().map_err(|e| e.to_string())?;
    let total: f64 = km.values().sum();
    eprintln!("{count} segments, {total:.1} km -> {}", out.display());
    for ((stage, confidence), length) in &km {
        eprintln!(
            "  stage {stage} {confidence:<4} {length:>9.1} km {:>5.1}%",
            length / total * 100.0
        );
    }
    Ok(())
}

fn parse_fix(s: &str) -> Result<Fix, String> {
    let v: Vec<f64> = s
        .split(',')
        .map(str::parse)
        .collect::<Result<_, _>>()
        .map_err(|_| format!("bad fix {s}"))?;
    match v[..] {
        [lon, lat] => Ok(Fix {
            lon,
            lat,
            heading: None,
            speed_mps: None,
        }),
        [lon, lat, heading, speed] => Ok(Fix {
            lon,
            lat,
            heading: Some(heading),
            speed_mps: Some(speed),
        }),
        _ => Err(format!("fix must be lon,lat[,heading,speed_mps]: {s}")),
    }
}

fn run_locate(args: &[String]) -> Result<(), String> {
    let [flag, db, fixes @ ..] = args else {
        return Err(
            "usage: limes-cli locate --db pref.sqlite lon,lat[,heading,speed_mps]...".into(),
        );
    };
    if flag != "--db" {
        return Err(
            "usage: limes-cli locate --db pref.sqlite lon,lat[,heading,speed_mps]...".into(),
        );
    }
    let reader = Reader::open(std::path::Path::new(db)).map_err(|e| e.to_string())?;
    let mut matcher = Matcher::new();
    for f in fixes {
        let fix = parse_fix(f)?;
        let started = std::time::Instant::now();
        let found = matcher.locate(
            &reader,
            &fix,
            &DriveTime::REPRESENTATIVE,
            Vehicle::OrdinaryCar,
        );
        let micros = started.elapsed().as_micros();
        let line = match found {
            Some(m) => serde_json::json!({
                "fix": f, "osm_id": m.segment.osm_id, "seq": m.segment.seq, "name": m.segment.name,
                "ref": m.segment.ref_, "highway": m.segment.highway, "distance_m": (m.distance_m * 10.0).round() / 10.0,
                "decision": m.decision, "micros": micros,
            }),
            None => serde_json::json!({"fix": f, "unknown": true, "micros": micros}),
        };
        println!("{line}");
    }
    Ok(())
}

fn utc_now() -> String {
    utc(std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_or(0, |d| d.as_secs() as i64))
}

/// Unix seconds as `YYYY-MM-DDThh:mm:ssZ`.
fn utc(secs: i64) -> String {
    let (days, rem) = (secs.div_euclid(86400), secs.rem_euclid(86400));
    // Civil date from days since 1970-01-01 (H. Hinnant, days_from_civil inverse).
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = doy - (153 * mp + 2) / 5 + 1;
    let month = if mp < 10 { mp + 3 } else { mp - 9 };
    let year = yoe + era * 400 + i64::from(month <= 2);
    format!(
        "{year:04}-{month:02}-{day:02}T{:02}:{:02}:{:02}Z",
        rem / 3600,
        rem / 60 % 60,
        rem % 60
    )
}

fn run_package(args: &[String]) -> Result<(), String> {
    let usage =
        || "usage: limes-cli package --db pref.sqlite --out-dir dist [--level 1-22]".to_string();
    let (mut db, mut out_dir, mut level) = (None, None, 19);
    let mut it = args.iter();
    while let Some(flag) = it.next() {
        let value = it.next().ok_or_else(usage)?;
        match flag.as_str() {
            "--db" => db = Some(PathBuf::from(value)),
            "--out-dir" => out_dir = Some(PathBuf::from(value)),
            "--level" => level = value.parse().map_err(|_| usage())?,
            _ => return Err(usage()),
        }
    }
    let (db, out_dir) = (db.ok_or_else(usage)?, out_dir.ok_or_else(usage)?);
    let reader = Reader::open(&db).map_err(|e| format!("{}: {e}", db.display()))?;
    let meta = |key| {
        reader.meta(key).map_err(|e| e.to_string())?.ok_or_else(|| {
            format!(
                "{}: no meta {key} (set it with build-db --meta)",
                db.display()
            )
        })
    };
    let (prefecture, version) = (meta("prefecture")?, meta("version")?);
    drop(reader);
    let safe = |s: &str| {
        !s.is_empty()
            && s.chars()
                .all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '_' | '-'))
    };
    if !safe(&prefecture) || !safe(&version) {
        return Err(format!(
            "prefecture and version must be [A-Za-z0-9._-]: {prefecture} {version}"
        ));
    }

    std::fs::create_dir_all(&out_dir).map_err(|e| e.to_string())?;
    let name = format!("{prefecture}-{version}.sqlite.zst");
    let (prefecture, entry) =
        update::package(&db, &out_dir.join(&name), &name, level).map_err(|e| e.to_string())?;
    eprintln!(
        "{} -> {name}: {} -> {} bytes ({:.1}%)",
        db.display(),
        entry.raw_size,
        entry.size,
        entry.size as f64 / entry.raw_size as f64 * 100.0
    );

    let manifest_path = out_dir.join("manifest.json");
    let mut manifest = match std::fs::read_to_string(&manifest_path) {
        Ok(json) => Manifest::parse(&json).map_err(|e| e.to_string())?,
        Err(e) if e.kind() == io::ErrorKind::NotFound => Manifest {
            format: update::MANIFEST_FORMAT,
            generated_at: String::new(),
            prefectures: BTreeMap::new(),
        },
        Err(e) => return Err(e.to_string()),
    };
    manifest.format = update::MANIFEST_FORMAT;
    manifest.generated_at = utc_now();
    manifest.prefectures.insert(prefecture, entry);
    let json = serde_json::to_string_pretty(&manifest).map_err(|e| e.to_string())?;
    std::fs::write(&manifest_path, json + "\n").map_err(|e| e.to_string())?;
    Ok(())
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let result = match args.first().map(String::as_str) {
        Some("decide") => run_decide(&args[1..]).map(|()| true),
        Some("golden") => run_golden(&args[1..]),
        Some("build-db") => run_build_db(&args[1..]).map(|()| true),
        Some("locate") => run_locate(&args[1..]).map(|()| true),
        Some("package") => run_package(&args[1..]).map(|()| true),
        _ => Err("usage: limes-cli <decide|golden|build-db|locate|package> ...".into()),
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
    use super::{parse_at, utc};

    #[test]
    fn utc_format() {
        assert_eq!(utc(0), "1970-01-01T00:00:00Z");
        assert_eq!(utc(951_782_400), "2000-02-29T00:00:00Z");
        assert_eq!(utc(1_793_976_245), "2026-11-06T14:44:05Z");
    }

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
