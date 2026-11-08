//! Per-prefecture road database: one row per road segment with its evidence and
//! the decision baked at build time, plus an R*Tree for spatial lookup.
//!
//! The pipeline writes it (`limes-cli build-db`); the app reads it. Segments
//! whose regulations depend on date or time are re-decided on the device from
//! the stored evidence.

use std::path::Path;

use rusqlite::{Connection, OptionalExtension, params};
use serde::{Deserialize, Serialize};

use crate::conditions::{DriveTime, Vehicle};
use crate::decide::{Confidence, Decision, Stage, WayEvidence, decide};

/// Bumped on any incompatible change; the app refuses newer versions.
pub const SCHEMA_VERSION: u32 = 1;

const SCHEMA: &str = "
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE segments (
    id INTEGER PRIMARY KEY,
    osm_id INTEGER NOT NULL,
    seq INTEGER NOT NULL,
    highway TEXT NOT NULL,
    name TEXT NOT NULL,
    ref TEXT NOT NULL,
    oneway INTEGER NOT NULL,      -- 1 along the geometry, -1 against it, 0 both ways
    geom BLOB NOT NULL,           -- (lon, lat) pairs as little-endian i32 in 1e-7 degrees
    evidence TEXT,                -- WayEvidence JSON; NULL when bare (only osm_id and highway)
    speed INTEGER NOT NULL,       -- decision at DriveTime::REPRESENTATIVE for an ordinary car
    confidence TEXT NOT NULL,
    stage INTEGER NOT NULL,
    reason TEXT NOT NULL,
    time_dependent INTEGER NOT NULL
);
CREATE VIRTUAL TABLE segments_index USING rtree(id, min_lon, max_lon, min_lat, max_lat);
";

/// One line of the pipeline's evidence NDJSON.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SegmentRecord {
    pub seq: u32,
    #[serde(default)]
    pub name: String,
    #[serde(default, rename = "ref")]
    pub ref_: String,
    #[serde(default)]
    pub oneway: String,
    /// Projected length, for reporting only.
    #[serde(default)]
    pub length_m: f64,
    pub coords: Vec<[f64; 2]>,
    #[serde(flatten)]
    pub evidence: WayEvidence,
}

fn oneway_code(tag: &str) -> i32 {
    match tag {
        "yes" | "1" | "true" => 1,
        "-1" | "reverse" => -1,
        _ => 0,
    }
}

const SCALE: f64 = 1e7;

pub fn encode_coords(coords: &[[f64; 2]]) -> Vec<u8> {
    let mut out = Vec::with_capacity(coords.len() * 8);
    for [lon, lat] in coords {
        out.extend_from_slice(&((lon * SCALE).round() as i32).to_le_bytes());
        out.extend_from_slice(&((lat * SCALE).round() as i32).to_le_bytes());
    }
    out
}

pub fn decode_coords(blob: &[u8]) -> Vec<[f64; 2]> {
    blob.as_chunks::<8>().0.iter()
        .map(|c| {
            let lon = i32::from_le_bytes(c[0..4].try_into().unwrap());
            let lat = i32::from_le_bytes(c[4..8].try_into().unwrap());
            [f64::from(lon) / SCALE, f64::from(lat) / SCALE]
        })
        .collect()
}

/// Writes a new database; `finish` must be called to commit.
pub struct Writer {
    conn: Connection,
    count: u64,
}

impl Writer {
    pub fn create(path: &Path) -> rusqlite::Result<Self> {
        if path.exists() {
            std::fs::remove_file(path)
                .map_err(|e| rusqlite::Error::ToSqlConversionFailure(Box::new(e)))?;
        }
        let conn = Connection::open(path)?;
        conn.execute_batch("PRAGMA journal_mode = OFF; PRAGMA synchronous = OFF;")?;
        conn.execute_batch(SCHEMA)?;
        conn.execute_batch("BEGIN")?;
        conn.execute(
            "INSERT INTO meta VALUES ('schema_version', ?1)",
            [SCHEMA_VERSION.to_string()],
        )?;
        Ok(Self { conn, count: 0 })
    }

    pub fn set_meta(&self, key: &str, value: &str) -> rusqlite::Result<()> {
        self.conn.execute(
            "INSERT OR REPLACE INTO meta VALUES (?1, ?2)",
            params![key, value],
        )?;
        Ok(())
    }

    /// Decide and store one segment; returns the baked decision.
    pub fn add(&mut self, record: &SegmentRecord) -> rusqlite::Result<Decision> {
        let e = &record.evidence;
        let decision = decide(e, &DriveTime::REPRESENTATIVE, Vehicle::OrdinaryCar);
        let time_dependent = e
            .regulations
            .iter()
            .any(|r| r.conditions.is_time_dependent());
        let evidence = serde_json::to_string(e)
            .map_err(|err| rusqlite::Error::ToSqlConversionFailure(Box::new(err)))?;
        self.count += 1;
        let id = self.count as i64;
        self.conn
            .prepare_cached(
                "INSERT INTO segments VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14)",
            )?
            .execute(params![
                id,
                e.osm_id,
                record.seq,
                e.highway,
                record.name,
                record.ref_,
                oneway_code(&record.oneway),
                encode_coords(&record.coords),
                evidence,
                decision.speed,
                decision.confidence.as_str(),
                decision.stage.number(),
                decision.reason,
                time_dependent,
            ])?;
        let (mut min_lon, mut max_lon, mut min_lat, mut max_lat) =
            (f64::MAX, f64::MIN, f64::MAX, f64::MIN);
        for [lon, lat] in &record.coords {
            min_lon = min_lon.min(*lon);
            max_lon = max_lon.max(*lon);
            min_lat = min_lat.min(*lat);
            max_lat = max_lat.max(*lat);
        }
        self.conn
            .prepare_cached("INSERT INTO segments_index VALUES (?1, ?2, ?3, ?4, ?5)")?
            .execute(params![id, min_lon, max_lon, min_lat, max_lat])?;
        Ok(decision)
    }

    pub fn finish(self) -> rusqlite::Result<u64> {
        self.conn.execute_batch("COMMIT; VACUUM;")?;
        Ok(self.count)
    }
}

/// A stored segment.
#[derive(Debug, Clone)]
pub struct Segment {
    pub id: i64,
    pub osm_id: i64,
    pub seq: u32,
    pub highway: String,
    pub name: String,
    pub ref_: String,
    pub oneway: i32,
    pub coords: Vec<[f64; 2]>,
    pub evidence: WayEvidence,
    pub baked: Decision,
    pub time_dependent: bool,
}

/// Read-only access to a prefecture database.
pub struct Reader {
    conn: Connection,
}

impl Reader {
    pub fn open(path: &Path) -> rusqlite::Result<Self> {
        let conn = Connection::open_with_flags(path, rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY)?;
        Ok(Self { conn })
    }

    pub fn meta(&self, key: &str) -> rusqlite::Result<Option<String>> {
        self.conn
            .query_row("SELECT value FROM meta WHERE key = ?1", [key], |r| r.get(0))
            .optional()
    }

    /// Segments whose bounding boxes intersect the given box (degrees).
    pub fn segments_in(
        &self,
        min_lon: f64,
        min_lat: f64,
        max_lon: f64,
        max_lat: f64,
    ) -> rusqlite::Result<Vec<Segment>> {
        let mut stmt = self.conn.prepare_cached(
            "SELECT s.id, s.osm_id, s.seq, s.highway, s.name, s.ref, s.oneway, s.geom, s.evidence,
                    s.speed, s.confidence, s.stage, s.reason, s.time_dependent
             FROM segments_index i JOIN segments s ON s.id = i.id
             WHERE i.max_lon >= ?1 AND i.min_lon <= ?3 AND i.max_lat >= ?2 AND i.min_lat <= ?4",
        )?;
        let rows = stmt.query_map(params![min_lon, min_lat, max_lon, max_lat], |r| {
            let evidence: Option<String> = r.get(8)?;
            let (osm_id, highway): (i64, String) = (r.get(1)?, r.get(3)?);
            let confidence: String = r.get(10)?;
            let stage: i32 = r.get(11)?;
            let bad = |col: usize, msg: String| {
                rusqlite::Error::FromSqlConversionFailure(
                    col,
                    rusqlite::types::Type::Text,
                    msg.into(),
                )
            };
            Ok(Segment {
                id: r.get(0)?,
                osm_id,
                seq: r.get(2)?,
                highway: highway.clone(),
                name: r.get(4)?,
                ref_: r.get(5)?,
                oneway: r.get(6)?,
                coords: decode_coords(&r.get::<_, Vec<u8>>(7)?),
                evidence: match evidence {
                    Some(json) => serde_json::from_str(&json).map_err(|e| bad(8, e.to_string()))?,
                    None => WayEvidence {
                        osm_id,
                        highway: highway.clone(),
                        ..Default::default()
                    },
                },
                baked: Decision {
                    speed: r.get(9)?,
                    confidence: Confidence::parse(&confidence)
                        .ok_or_else(|| bad(10, confidence.clone()))?,
                    stage: Stage::from_number(stage).ok_or_else(|| bad(11, stage.to_string()))?,
                    reason: r.get(12)?,
                },
                time_dependent: r.get(13)?,
            })
        })?;
        rows.collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn coords_round_trip_to_a_centimeter() {
        let coords = [[141.3459339, 43.0980358], [-0.0000001, 0.0]];
        let back = decode_coords(&encode_coords(&coords));
        for (a, b) in coords.iter().zip(&back) {
            assert!((a[0] - b[0]).abs() < 1e-7 && (a[1] - b[1]).abs() < 1e-7);
        }
    }

    #[test]
    fn write_then_read_by_box() {
        let dir = std::env::temp_dir().join(format!("limes-db-test-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("test.sqlite");
        let line = r#"{"osm_id":7,"seq":0,"highway":"residential","name":"x","ref":"","oneway":"yes",
            "coords":[[141.35,43.09],[141.351,43.091]],"center":["jartic_lanes"],
            "regulations":[{"speed":20,"code":112,"conditions":{"targets":[{"time_start":"700","time_end":"900"}]}}]}"#;
        let record: SegmentRecord = serde_json::from_str(line).unwrap();
        let mut writer = Writer::create(&path).unwrap();
        writer.set_meta("prefecture", "hokkaido").unwrap();
        let baked = writer.add(&record).unwrap();
        assert_eq!(baked.speed, 60); // 12:00, outside 7-9
        assert_eq!(writer.finish().unwrap(), 1);

        let reader = Reader::open(&path).unwrap();
        assert_eq!(reader.meta("schema_version").unwrap().as_deref(), Some("1"));
        assert_eq!(
            reader.meta("prefecture").unwrap().as_deref(),
            Some("hokkaido")
        );
        let found = reader
            .segments_in(141.3505, 43.0905, 141.3506, 43.0906)
            .unwrap();
        assert_eq!(found.len(), 1);
        let s = &found[0];
        assert_eq!((s.osm_id, s.oneway, s.time_dependent), (7, 1, true));
        assert_eq!(s.baked, baked);
        assert_eq!(s.evidence.regulations[0].speed, 20);
        assert!(
            reader
                .segments_in(141.4, 43.2, 141.5, 43.3)
                .unwrap()
                .is_empty()
        );
        std::fs::remove_dir_all(&dir).ok();
    }
}
