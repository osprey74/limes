//! UniFFI surface of limes-core for the apps.
//!
//! The app opens the prefecture databases it has downloaded, then calls
//! `locate` for every GPS fix with the local time. Everything else (decision,
//! map matching, conditions) stays in limes-core.

use std::path::Path;
use std::sync::{Arc, Mutex};

use limes_core::db::{Reader, SCHEMA_VERSION};
use limes_core::matcher::{Fix, Matcher};
use limes_core::{DriveTime, Vehicle};

uniffi::setup_scaffolding!();

#[derive(Debug, thiserror::Error, uniffi::Error)]
pub enum LimesError {
    #[error("database error: {message}")]
    Database { message: String },
    #[error(
        "database schema {found} is newer than this app supports ({supported}); update the app"
    )]
    UnsupportedSchema { found: u32, supported: u32 },
}

impl From<limes_core::db::Error> for LimesError {
    fn from(e: limes_core::db::Error) -> Self {
        LimesError::Database {
            message: e.to_string(),
        }
    }
}

#[derive(Debug, Clone, uniffi::Record)]
pub struct GpsFix {
    pub lon: f64,
    pub lat: f64,
    /// Degrees clockwise from north.
    pub heading: Option<f64>,
    pub speed_mps: Option<f64>,
}

#[derive(Debug, Clone, uniffi::Record)]
pub struct LocalTime {
    pub month: u8,
    pub day: u8,
    pub minute_of_day: u16,
    /// 0 = Monday ... 6 = Sunday.
    pub weekday: u8,
    pub holiday: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, uniffi::Enum)]
pub enum Confidence {
    Low,
    Mid,
    High,
}

#[derive(Debug, Clone, uniffi::Record)]
pub struct RoadSpeed {
    pub speed_kmh: u16,
    pub confidence: Confidence,
    /// Decision stage 1-7 (see limes-core decide.rs).
    pub stage: u8,
    pub reason: String,
    pub road_name: String,
    pub road_ref: String,
    pub highway: String,
    pub osm_id: i64,
    pub distance_m: f64,
}

#[derive(Debug, Clone, uniffi::Record)]
pub struct DatabaseInfo {
    pub path: String,
    pub prefecture: Option<String>,
    pub jartic_month: Option<String>,
    pub osm_date: Option<String>,
}

#[derive(uniffi::Object)]
pub struct Engine {
    databases: Mutex<Vec<(String, Reader)>>,
    matcher: Mutex<Matcher>,
}

#[uniffi::export]
impl Engine {
    #[uniffi::constructor]
    pub fn new() -> Arc<Self> {
        Arc::new(Self {
            databases: Mutex::new(Vec::new()),
            matcher: Mutex::new(Matcher::new()),
        })
    }

    /// Open a prefecture database (replacing one already open at the same path).
    pub fn open_database(&self, path: String) -> Result<DatabaseInfo, LimesError> {
        let reader = Reader::open(Path::new(&path))?;
        let found: u32 = reader
            .meta("schema_version")?
            .and_then(|v| v.parse().ok())
            .unwrap_or(0);
        if found > SCHEMA_VERSION {
            return Err(LimesError::UnsupportedSchema {
                found,
                supported: SCHEMA_VERSION,
            });
        }
        let info = DatabaseInfo {
            path: path.clone(),
            prefecture: reader.meta("prefecture")?,
            jartic_month: reader.meta("jartic_month")?,
            osm_date: reader.meta("osm_date")?,
        };
        let mut databases = self.databases.lock().unwrap();
        databases.retain(|(p, _)| *p != path);
        databases.push((path, reader));
        Ok(info)
    }

    pub fn close_database(&self, path: String) {
        self.databases.lock().unwrap().retain(|(p, _)| *p != path);
    }

    /// The road at this fix and its maximum speed for an ordinary car, or None
    /// when no road matches (shown as "unknown").
    pub fn locate(&self, fix: GpsFix, time: LocalTime) -> Option<RoadSpeed> {
        let databases = self.databases.lock().unwrap();
        let readers: Vec<&Reader> = databases.iter().map(|(_, r)| r).collect();
        let fix = Fix {
            lon: fix.lon,
            lat: fix.lat,
            heading: fix.heading,
            speed_mps: fix.speed_mps,
        };
        let t = DriveTime {
            month: time.month,
            day: time.day,
            minute_of_day: time.minute_of_day,
            weekday: time.weekday,
            holiday: time.holiday,
        };
        let m = self.matcher.lock().unwrap().locate(
            readers.as_slice(),
            &fix,
            &t,
            Vehicle::OrdinaryCar,
        )?;
        Some(RoadSpeed {
            speed_kmh: m.decision.speed,
            confidence: match m.decision.confidence {
                limes_core::Confidence::Low => Confidence::Low,
                limes_core::Confidence::Mid => Confidence::Mid,
                limes_core::Confidence::High => Confidence::High,
            },
            stage: m.decision.stage.number() as u8,
            reason: m.decision.reason,
            road_name: m.segment.name,
            road_ref: m.segment.ref_,
            highway: m.segment.highway,
            osm_id: m.segment.osm_id,
            distance_m: m.distance_m,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use limes_core::db::{SegmentRecord, Writer};

    #[test]
    fn open_and_locate() {
        let dir = std::env::temp_dir().join(format!("limes-ffi-test-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("pref.sqlite");
        let record: SegmentRecord = serde_json::from_str(
            r#"{"osm_id":5,"seq":0,"highway":"tertiary","name":"テスト通","coords":[[141.35,43.089],[141.35,43.091]],
                "center":["aerial_photo"]}"#,
        )
        .unwrap();
        let mut writer = Writer::create(&path).unwrap();
        writer.set_meta("prefecture", "hokkaido").unwrap();
        writer.add(&record).unwrap();
        writer.finish().unwrap();

        let engine = Engine::new();
        let path = path.to_string_lossy().into_owned();
        let info = engine.open_database(path.clone()).unwrap();
        assert_eq!(info.prefecture.as_deref(), Some("hokkaido"));
        let time = LocalTime {
            month: 11,
            day: 9,
            minute_of_day: 600,
            weekday: 0,
            holiday: false,
        };
        let fix = |lon| GpsFix {
            lon,
            lat: 43.09,
            heading: Some(0.0),
            speed_mps: Some(10.0),
        };
        let got = engine.locate(fix(141.35001), time.clone()).unwrap();
        assert_eq!(
            (got.speed_kmh, got.confidence, got.stage),
            (60, Confidence::Mid, 5)
        );
        assert_eq!(got.road_name, "テスト通");
        assert!(engine.locate(fix(141.36), time.clone()).is_none());
        engine.close_database(path);
        assert!(engine.locate(fix(141.35001), time).is_none());
        std::fs::remove_dir_all(&dir).ok();
    }
}
