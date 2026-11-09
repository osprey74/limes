//! UniFFI surface of limes-core for the apps.
//!
//! The app opens the prefecture databases it has downloaded, then calls
//! `locate` for every GPS fix with the local time. Everything else (decision,
//! map matching, conditions) stays in limes-core.
//!
//! Updates: `open_store` once at launch, `plan_updates` with the fetched
//! manifest.json, download each `UpdateDownload.path` (relative to the
//! manifest URL), then `install_update`. The app does the transfers.
//! `installed_databases` and `remove_prefecture` back the storage settings.

use std::path::Path;
use std::sync::{Arc, Mutex};

use limes_core::db::{Reader, SCHEMA_VERSION};
use limes_core::matcher::{Fix, Matcher};
use limes_core::update::{self, Action, Entry, Manifest, Store};
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
    #[error("update error: {message}")]
    Update { message: String },
    /// The download does not match the manifest; delete it and fetch again.
    #[error("download mismatch: {message}")]
    DownloadMismatch { message: String },
    #[error("open_store has not been called")]
    NoStore,
}

impl From<update::Error> for LimesError {
    fn from(e: update::Error) -> Self {
        match e {
            update::Error::Mismatch(message) => LimesError::DownloadMismatch { message },
            e => LimesError::Update {
                message: e.to_string(),
            },
        }
    }
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
    pub version: Option<String>,
    pub jartic_month: Option<String>,
    pub osm_date: Option<String>,
}

/// A prefecture to download, as listed in the manifest.
#[derive(Debug, Clone, uniffi::Record)]
pub struct UpdateDownload {
    pub prefecture: String,
    pub version: String,
    pub schema_version: u32,
    pub jartic_month: Option<String>,
    pub osm_date: Option<String>,
    /// Relative to the manifest URL.
    pub path: String,
    pub size: u64,
    pub sha256: String,
    /// Disk space needed after decompression.
    pub raw_size: u64,
}

impl From<(String, Entry)> for UpdateDownload {
    fn from((prefecture, e): (String, Entry)) -> Self {
        Self {
            prefecture,
            version: e.version,
            schema_version: e.schema_version,
            jartic_month: e.jartic_month,
            osm_date: e.osm_date,
            path: e.path,
            size: e.size,
            sha256: e.sha256,
            raw_size: e.raw_size,
        }
    }
}

impl From<&UpdateDownload> for Entry {
    fn from(d: &UpdateDownload) -> Self {
        Entry {
            version: d.version.clone(),
            schema_version: d.schema_version,
            jartic_month: d.jartic_month.clone(),
            osm_date: d.osm_date.clone(),
            path: d.path.clone(),
            size: d.size,
            sha256: d.sha256.clone(),
            raw_size: d.raw_size,
        }
    }
}

#[derive(Debug, Clone, uniffi::Record)]
pub struct InstalledDatabase {
    pub prefecture: String,
    /// None when the file cannot be read (it is then downloaded again).
    pub version: Option<String>,
    pub bytes: u64,
}

#[derive(Debug, Clone, Default, uniffi::Record)]
pub struct UpdatePlan {
    pub downloads: Vec<UpdateDownload>,
    pub up_to_date: Vec<String>,
    /// Published with a newer database schema; prompt for an app update.
    pub app_update_required: Vec<String>,
    pub not_published: Vec<String>,
}

#[derive(uniffi::Object)]
pub struct Engine {
    databases: Mutex<Vec<(String, Reader)>>,
    matcher: Mutex<Matcher>,
    store: Mutex<Option<Store>>,
}

#[uniffi::export]
impl Engine {
    #[uniffi::constructor]
    pub fn new() -> Arc<Self> {
        Arc::new(Self {
            databases: Mutex::new(Vec::new()),
            matcher: Mutex::new(Matcher::new()),
            store: Mutex::new(None),
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
            version: reader.meta("version")?,
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

    /// Use `dir` for downloaded prefectures: clears interrupted installs and
    /// opens every installed database. A database that fails to open is
    /// skipped (it shows up again in `plan_updates` as a download).
    pub fn open_store(&self, dir: String) -> Result<Vec<DatabaseInfo>, LimesError> {
        let store = Store::open(Path::new(&dir))?;
        let mut opened = Vec::new();
        for prefecture in store.installed()? {
            let path = store.current(&prefecture).to_string_lossy().into_owned();
            if let Ok(info) = self.open_database(path) {
                opened.push(info);
            }
        }
        *self.store.lock().unwrap() = Some(store);
        Ok(opened)
    }

    /// Compare the manifest with the store for the wanted prefectures.
    pub fn plan_updates(
        &self,
        manifest_json: String,
        prefectures: Vec<String>,
    ) -> Result<UpdatePlan, LimesError> {
        let manifest = Manifest::parse(&manifest_json)?;
        let guard = self.store.lock().unwrap();
        let store = guard.as_ref().ok_or(LimesError::NoStore)?;
        let mut plan = UpdatePlan::default();
        for (prefecture, action) in store.plan(&manifest, &prefectures) {
            match action {
                Action::Download(entry) => plan.downloads.push((prefecture, entry).into()),
                Action::UpToDate => plan.up_to_date.push(prefecture),
                Action::AppUpdateRequired => plan.app_update_required.push(prefecture),
                Action::NotPublished => plan.not_published.push(prefecture),
            }
        }
        Ok(plan)
    }

    /// Verify a finished download and switch to it; the replaced version is
    /// deleted. The download file is left for the app to delete.
    pub fn install_update(
        &self,
        download: UpdateDownload,
        file: String,
    ) -> Result<DatabaseInfo, LimesError> {
        let guard = self.store.lock().unwrap();
        let store = guard.as_ref().ok_or(LimesError::NoStore)?;
        let prefecture = &download.prefecture;
        self.switch(store, prefecture, |s| {
            s.install(prefecture, &Entry::from(&download), Path::new(&file))
        })
    }

    /// The installed prefectures with their version and size on disk, for
    /// the storage view.
    pub fn installed_databases(&self) -> Result<Vec<InstalledDatabase>, LimesError> {
        let guard = self.store.lock().unwrap();
        let store = guard.as_ref().ok_or(LimesError::NoStore)?;
        Ok(store
            .installed()?
            .into_iter()
            .map(|prefecture| InstalledDatabase {
                version: store.installed_version(&prefecture),
                bytes: store.installed_size(&prefecture).unwrap_or(0),
                prefecture,
            })
            .collect())
    }

    /// Close and delete a prefecture.
    pub fn remove_prefecture(&self, prefecture: String) -> Result<(), LimesError> {
        let guard = self.store.lock().unwrap();
        let store = guard.as_ref().ok_or(LimesError::NoStore)?;
        self.close_database(store.current(&prefecture).to_string_lossy().into_owned());
        store.remove(&prefecture)?;
        Ok(())
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

impl Engine {
    /// Close the prefecture (a file in use cannot be replaced on every
    /// platform), run `change`, and reopen whichever version is in place.
    fn switch(
        &self,
        store: &Store,
        prefecture: &str,
        change: impl FnOnce(&Store) -> Result<(), update::Error>,
    ) -> Result<DatabaseInfo, LimesError> {
        let path = store.current(prefecture).to_string_lossy().into_owned();
        self.close_database(path.clone());
        let changed = change(store);
        let reopened = Path::new(&path).exists().then(|| self.open_database(path));
        changed?;
        reopened.ok_or(LimesError::Update {
            message: format!("{prefecture}: no database after the switch"),
        })?
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use limes_core::db::{SegmentRecord, Writer};
    use limes_core::update::{self, Manifest};

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

    #[test]
    fn update_through_the_store() {
        let dir = std::env::temp_dir().join(format!("limes-ffi-store-{}", std::process::id()));
        std::fs::remove_dir_all(&dir).ok();
        std::fs::create_dir_all(&dir).unwrap();
        let publish = |version: &str| {
            let db = dir.join(format!("{version}.sqlite"));
            let record: SegmentRecord = serde_json::from_str(
                r#"{"osm_id":5,"seq":0,"highway":"motorway","coords":[[141.35,43.089],[141.35,43.091]]}"#,
            )
            .unwrap();
            let mut writer = Writer::create(&db).unwrap();
            writer.set_meta("prefecture", "hokkaido").unwrap();
            writer.set_meta("version", version).unwrap();
            writer.add(&record).unwrap();
            writer.finish().unwrap();
            let name = format!("hokkaido-{version}.sqlite.zst");
            let (_, entry) = update::package(&db, &dir.join(&name), &name, 3).unwrap();
            let manifest = Manifest {
                format: update::MANIFEST_FORMAT,
                generated_at: String::new(),
                prefectures: [("hokkaido".to_string(), entry)].into(),
            };
            (
                dir.join(name).to_string_lossy().into_owned(),
                serde_json::to_string(&manifest).unwrap(),
            )
        };
        let wanted = vec!["hokkaido".to_string()];

        let engine = Engine::new();
        assert!(matches!(
            engine.plan_updates("{}".into(), wanted.clone()),
            Err(LimesError::Update { .. })
        ));
        let store = dir.join("store").to_string_lossy().into_owned();
        assert!(engine.open_store(store.clone()).unwrap().is_empty());

        let (file, manifest) = publish("v1");
        let plan = engine
            .plan_updates(manifest.clone(), wanted.clone())
            .unwrap();
        assert_eq!(plan.downloads.len(), 1);
        let info = engine
            .install_update(plan.downloads[0].clone(), file)
            .unwrap();
        assert_eq!(info.version.as_deref(), Some("v1"));
        assert_eq!(
            engine
                .plan_updates(manifest, wanted.clone())
                .unwrap()
                .up_to_date,
            wanted
        );

        let (file, manifest) = publish("v2");
        let mut download = engine
            .plan_updates(manifest, wanted.clone())
            .unwrap()
            .downloads[0]
            .clone();
        download.sha256 = "0".repeat(64);
        assert!(matches!(
            engine.install_update(download.clone(), file.clone()),
            Err(LimesError::DownloadMismatch { .. })
        ));
        let time = LocalTime {
            month: 11,
            day: 9,
            minute_of_day: 600,
            weekday: 0,
            holiday: false,
        };
        let fix = GpsFix {
            lon: 141.35001,
            lat: 43.09,
            heading: Some(0.0),
            speed_mps: Some(25.0),
        };
        // The old version stays open after a failed install.
        assert!(engine.locate(fix.clone(), time.clone()).is_some());

        let (_, manifest) = publish("v2");
        let download = engine
            .plan_updates(manifest, wanted.clone())
            .unwrap()
            .downloads[0]
            .clone();
        let info = engine.install_update(download, file).unwrap();
        assert_eq!(info.version.as_deref(), Some("v2"));
        let installed = engine.installed_databases().unwrap();
        assert_eq!(installed.len(), 1);
        assert_eq!(
            (
                installed[0].prefecture.as_str(),
                installed[0].version.as_deref()
            ),
            ("hokkaido", Some("v2"))
        );
        assert!(installed[0].bytes > 0);

        // A fresh engine finds the installed prefecture.
        let opened = Engine::new().open_store(store).unwrap();
        assert_eq!(opened[0].version.as_deref(), Some("v2"));
        engine.remove_prefecture("hokkaido".into()).unwrap();
        assert!(engine.locate(fix, time).is_none());
        assert!(engine.installed_databases().unwrap().is_empty());
        std::fs::remove_dir_all(&dir).ok();
    }
}
