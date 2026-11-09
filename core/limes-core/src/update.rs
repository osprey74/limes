//! Data updates: the pipeline publishes `manifest.json` and one
//! `<prefecture>-<version>.sqlite.zst` per prefecture; the app compares the
//! manifest with what it holds, downloads the changed prefectures (the app does
//! the transfer) and installs them here.
//!
//! Store layout (one directory):
//!
//!   <prefecture>.sqlite        the database in use
//!   <prefecture>.prev.sqlite   the one it replaced, kept for one rollback
//!   <prefecture>.sqlite.part   staging; removed on failure or by `Store::open`
//!
//! Install order: verify size and sha256 of the download, decompress to the
//! staging file, check its meta, link the current file to `.prev`, then rename
//! the staging file over the current one. The rename is the switch, so a crash
//! at any point leaves either the old or the new database in place.

use std::collections::BTreeMap;
use std::fs::{self, File};
use std::io::{self, BufWriter, Read};
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::db::{Reader, SCHEMA_VERSION};

/// Bumped on any incompatible change to the manifest itself.
pub const MANIFEST_FORMAT: u32 = 1;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Manifest {
    pub format: u32,
    pub generated_at: String,
    pub prefectures: BTreeMap<String, Entry>,
}

/// One prefecture database as published.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Entry {
    /// Build identifier, also stored as meta `version` in the database.
    pub version: String,
    /// `db::SCHEMA_VERSION` the database was written with.
    pub schema_version: u32,
    #[serde(default)]
    pub jartic_month: Option<String>,
    #[serde(default)]
    pub osm_date: Option<String>,
    /// Path of the `.sqlite.zst`, relative to the manifest.
    pub path: String,
    /// Size and sha256 (lowercase hex) of the `.sqlite.zst`.
    pub size: u64,
    pub sha256: String,
    /// Size after decompression, for the free-space check.
    pub raw_size: u64,
    /// Speed-line vector tiles (PMTiles) built from the same database.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tiles: Option<FileRef>,
}

/// A published file other than the database.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct FileRef {
    /// Relative to the manifest.
    pub path: String,
    pub size: u64,
    /// Lowercase hex.
    pub sha256: String,
}

impl FileRef {
    /// Copies `source` to `<out_dir>/<path>` and describes the copy.
    pub fn publish(source: &Path, out_dir: &Path, path: &str) -> Result<Self, Error> {
        let target = out_dir.join(path);
        fs::copy(source, &target)?;
        let (sha256, size) = sha256_hex(&mut File::open(&target)?)?;
        Ok(Self {
            path: path.to_string(),
            size,
            sha256,
        })
    }
}

impl Manifest {
    pub fn parse(json: &str) -> Result<Self, Error> {
        let m: Manifest = serde_json::from_str(json).map_err(|e| Error::Manifest(e.to_string()))?;
        if m.format > MANIFEST_FORMAT {
            return Err(Error::Manifest(format!(
                "format {} is newer than {MANIFEST_FORMAT}",
                m.format
            )));
        }
        Ok(m)
    }
}

#[derive(Debug)]
pub enum Error {
    Io(io::Error),
    Database(rusqlite::Error),
    Manifest(String),
    /// The download does not match the manifest entry.
    Mismatch(String),
    NothingToRollBack,
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Error::Io(e) => write!(f, "{e}"),
            Error::Database(e) => write!(f, "database: {e}"),
            Error::Manifest(m) => write!(f, "manifest: {m}"),
            Error::Mismatch(m) => write!(f, "download mismatch: {m}"),
            Error::NothingToRollBack => write!(f, "no previous version to roll back to"),
        }
    }
}

impl std::error::Error for Error {}

impl From<io::Error> for Error {
    fn from(e: io::Error) -> Self {
        Error::Io(e)
    }
}

impl From<rusqlite::Error> for Error {
    fn from(e: rusqlite::Error) -> Self {
        Error::Database(e)
    }
}

/// What to do for one wanted prefecture.
#[derive(Debug, Clone, PartialEq)]
pub enum Action {
    Download(Entry),
    UpToDate,
    /// Published with a newer schema than this app reads.
    AppUpdateRequired,
    /// Not in the manifest.
    NotPublished,
}

pub fn sha256_hex(reader: &mut impl Read) -> io::Result<(String, u64)> {
    let mut hasher = Sha256::new();
    let mut buf = vec![0u8; 1 << 16];
    let mut size = 0u64;
    loop {
        let n = reader.read(&mut buf)?;
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
        size += n as u64;
    }
    let hex = hasher
        .finalize()
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect();
    Ok((hex, size))
}

/// The directory holding the app's prefecture databases.
pub struct Store {
    dir: PathBuf,
}

impl Store {
    /// Opens (creating) the directory and removes staging files left by an
    /// interrupted install.
    pub fn open(dir: &Path) -> Result<Self, Error> {
        fs::create_dir_all(dir)?;
        for entry in fs::read_dir(dir)? {
            let path = entry?.path();
            if path.extension().is_some_and(|e| e == "part") {
                fs::remove_file(&path)?;
            }
        }
        Ok(Self {
            dir: dir.to_path_buf(),
        })
    }

    pub fn current(&self, prefecture: &str) -> PathBuf {
        self.dir.join(format!("{prefecture}.sqlite"))
    }

    pub fn previous(&self, prefecture: &str) -> PathBuf {
        self.dir.join(format!("{prefecture}.prev.sqlite"))
    }

    fn staging(&self, prefecture: &str) -> PathBuf {
        self.dir.join(format!("{prefecture}.sqlite.part"))
    }

    /// Prefectures with a database in use, sorted.
    pub fn installed(&self) -> Result<Vec<String>, Error> {
        let mut out = Vec::new();
        for entry in fs::read_dir(&self.dir)? {
            let name = entry?.file_name();
            let name = name.to_string_lossy();
            if let Some(p) = name.strip_suffix(".sqlite")
                && !p.ends_with(".prev")
            {
                out.push(p.to_string());
            }
        }
        out.sort();
        Ok(out)
    }

    /// Meta `version` of the database in use; None when absent or unreadable
    /// (then it is downloaded again).
    pub fn installed_version(&self, prefecture: &str) -> Option<String> {
        let path = self.current(prefecture);
        if !path.exists() {
            return None;
        }
        Reader::open(&path).ok()?.meta("version").ok()?
    }

    pub fn plan(&self, manifest: &Manifest, prefectures: &[String]) -> Vec<(String, Action)> {
        prefectures
            .iter()
            .map(|p| {
                let action = match manifest.prefectures.get(p) {
                    None => Action::NotPublished,
                    Some(e) if e.schema_version > SCHEMA_VERSION => Action::AppUpdateRequired,
                    Some(e) if self.installed_version(p).as_deref() == Some(&e.version) => {
                        Action::UpToDate
                    }
                    Some(e) => Action::Download(e.clone()),
                };
                (p.clone(), action)
            })
            .collect()
    }

    /// Verifies a downloaded `.sqlite.zst` against its manifest entry and
    /// switches to it. The caller must close the current database first on
    /// platforms that cannot rename over an open file. The download is left
    /// for the caller to delete.
    pub fn install(&self, prefecture: &str, entry: &Entry, download: &Path) -> Result<(), Error> {
        let (sha256, size) = sha256_hex(&mut File::open(download)?)?;
        if size != entry.size || sha256 != entry.sha256 {
            return Err(Error::Mismatch(format!(
                "{prefecture}: {size} bytes sha256 {sha256}, expected {} bytes sha256 {}",
                entry.size, entry.sha256
            )));
        }
        let staging = self.staging(prefecture);
        let result = self.stage(prefecture, entry, download, &staging);
        if result.is_err() {
            fs::remove_file(&staging).ok();
        }
        result?;

        let (current, previous) = (self.current(prefecture), self.previous(prefecture));
        if current.exists() {
            if previous.exists() {
                fs::remove_file(&previous)?;
            }
            if fs::hard_link(&current, &previous).is_err() {
                fs::copy(&current, &previous)?;
            }
        }
        fs::rename(&staging, &current)?;
        Ok(())
    }

    fn stage(
        &self,
        prefecture: &str,
        entry: &Entry,
        download: &Path,
        staging: &Path,
    ) -> Result<(), Error> {
        let mut decoder = zstd::Decoder::new(File::open(download)?)?;
        let mut out = BufWriter::new(File::create(staging)?);
        let written = io::copy(&mut decoder, &mut out)?;
        out.into_inner().map_err(|e| e.into_error())?.sync_all()?;
        if written != entry.raw_size {
            return Err(Error::Mismatch(format!(
                "{prefecture}: {written} bytes decompressed, expected {}",
                entry.raw_size
            )));
        }
        let reader = Reader::open(staging)?;
        let check = |key: &str, expected: &str| -> Result<(), Error> {
            match reader.meta(key)? {
                Some(v) if v == expected => Ok(()),
                found => Err(Error::Mismatch(format!(
                    "{prefecture}: meta {key} is {found:?}, expected {expected}"
                ))),
            }
        };
        check("prefecture", prefecture)?;
        check("version", &entry.version)?;
        check("schema_version", &entry.schema_version.to_string())?;
        Ok(())
    }

    /// Puts the previous database back in use; the replaced one is discarded.
    pub fn roll_back(&self, prefecture: &str) -> Result<(), Error> {
        let previous = self.previous(prefecture);
        if !previous.exists() {
            return Err(Error::NothingToRollBack);
        }
        fs::rename(&previous, self.current(prefecture))?;
        Ok(())
    }

    /// Removes a prefecture (current and previous).
    pub fn remove(&self, prefecture: &str) -> Result<(), Error> {
        for path in [self.current(prefecture), self.previous(prefecture)] {
            if path.exists() {
                fs::remove_file(path)?;
            }
        }
        Ok(())
    }
}

/// Compresses a built database for publishing and returns its manifest entry.
/// Used by the pipeline (`limes-cli package`); `path` is the output file name.
pub fn package(db: &Path, out: &Path, path: &str, level: i32) -> Result<(String, Entry), Error> {
    let reader = Reader::open(db)?;
    let meta = |key: &str| reader.meta(key);
    let required = |key: &str| -> Result<String, Error> {
        meta(key)?.ok_or_else(|| Error::Manifest(format!("{}: no meta {key}", db.display())))
    };
    let prefecture = required("prefecture")?;
    let version = required("version")?;
    let schema_version = required("schema_version")?
        .parse()
        .map_err(|_| Error::Manifest("schema_version is not a number".into()))?;
    let (jartic_month, osm_date) = (meta("jartic_month")?, meta("osm_date")?);
    drop(reader);

    let raw_size = fs::metadata(db)?.len();
    {
        let mut encoder = zstd::Encoder::new(BufWriter::new(File::create(out)?), level)?;
        io::copy(&mut File::open(db)?, &mut encoder)?;
        encoder
            .finish()?
            .into_inner()
            .map_err(|e| e.into_error())?
            .sync_all()?;
    }
    let (sha256, size) = sha256_hex(&mut File::open(out)?)?;
    Ok((
        prefecture,
        Entry {
            version,
            schema_version,
            jartic_month,
            osm_date,
            path: path.to_string(),
            size,
            sha256,
            raw_size,
            tiles: None,
        },
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::{SegmentRecord, Writer};

    fn temp_dir(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("limes-update-{name}-{}", std::process::id()));
        fs::remove_dir_all(&dir).ok();
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    fn build(path: &Path, version: &str) {
        let record: SegmentRecord = serde_json::from_str(
            r#"{"osm_id":1,"seq":0,"highway":"residential","coords":[[141.35,43.09],[141.351,43.091]]}"#,
        )
        .unwrap();
        let mut writer = Writer::create(path).unwrap();
        writer.set_meta("prefecture", "hokkaido").unwrap();
        writer.set_meta("version", version).unwrap();
        writer.add(&record).unwrap();
        writer.finish().unwrap();
    }

    /// Builds and packages one version; returns the download and its entry.
    fn publish(dir: &Path, version: &str) -> (PathBuf, Entry) {
        let db = dir.join(format!("build-{version}.sqlite"));
        build(&db, version);
        let name = format!("hokkaido-{version}.sqlite.zst");
        let (prefecture, entry) = package(&db, &dir.join(&name), &name, 3).unwrap();
        assert_eq!(prefecture, "hokkaido");
        (dir.join(name), entry)
    }

    fn manifest(entry: &Entry) -> Manifest {
        Manifest {
            format: MANIFEST_FORMAT,
            generated_at: "2026-11-09T00:00:00Z".into(),
            prefectures: BTreeMap::from([("hokkaido".to_string(), entry.clone())]),
        }
    }

    #[test]
    fn install_update_and_roll_back() {
        let dir = temp_dir("install");
        let store = Store::open(&dir.join("store")).unwrap();
        let wanted = ["hokkaido".to_string(), "aomori".to_string()];

        let (v1, e1) = publish(&dir, "v1");
        let plan = store.plan(&manifest(&e1), &wanted);
        assert_eq!(plan[0].1, Action::Download(e1.clone()));
        assert_eq!(plan[1].1, Action::NotPublished);
        store.install("hokkaido", &e1, &v1).unwrap();
        assert_eq!(store.installed().unwrap(), ["hokkaido"]);
        assert_eq!(store.plan(&manifest(&e1), &wanted)[0].1, Action::UpToDate);

        let (v2, e2) = publish(&dir, "v2");
        store.install("hokkaido", &e2, &v2).unwrap();
        assert_eq!(store.installed_version("hokkaido").as_deref(), Some("v2"));
        assert_eq!(store.installed().unwrap(), ["hokkaido"]);

        store.roll_back("hokkaido").unwrap();
        assert_eq!(store.installed_version("hokkaido").as_deref(), Some("v1"));
        assert!(matches!(
            store.roll_back("hokkaido"),
            Err(Error::NothingToRollBack)
        ));
        fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn rejects_a_corrupt_or_mislabelled_download() {
        let dir = temp_dir("reject");
        let store = Store::open(&dir.join("store")).unwrap();
        let (v1, e1) = publish(&dir, "v1");
        store.install("hokkaido", &e1, &v1).unwrap();

        let (v2, e2) = publish(&dir, "v2");
        let mut bytes = fs::read(&v2).unwrap();
        let mid = bytes.len() / 2;
        bytes[mid] ^= 0xff;
        let corrupt = dir.join("corrupt.zst");
        fs::write(&corrupt, bytes).unwrap();
        assert!(matches!(
            store.install("hokkaido", &e2, &corrupt),
            Err(Error::Mismatch(_))
        ));

        // Right bytes, wrong version in the entry: caught by the meta check.
        let wrong = Entry {
            version: "v3".into(),
            ..e2.clone()
        };
        assert!(matches!(
            store.install("hokkaido", &wrong, &v2),
            Err(Error::Mismatch(_))
        ));
        assert!(!dir.join("store/hokkaido.sqlite.part").exists());
        assert_eq!(store.installed_version("hokkaido").as_deref(), Some("v1"));
        assert!(!store.previous("hokkaido").exists());
        fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn tiles_entry_is_optional_and_published_with_its_hash() {
        let dir = temp_dir("tiles");
        let (_, mut e) = publish(&dir, "v1");
        let json = serde_json::to_value(&e).unwrap();
        assert!(json.get("tiles").is_none()); // older apps' manifests stay unchanged

        fs::write(dir.join("speed.pmtiles"), b"abc").unwrap();
        let out = dir.join("dist");
        fs::create_dir_all(&out).unwrap();
        let file =
            FileRef::publish(&dir.join("speed.pmtiles"), &out, "hokkaido-v1.pmtiles").unwrap();
        assert_eq!(fs::read(out.join("hokkaido-v1.pmtiles")).unwrap(), b"abc");
        assert_eq!(
            (file.size, file.sha256.as_str()),
            (
                3,
                "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
            )
        );
        e.tiles = Some(file);
        let back: Entry = serde_json::from_value(serde_json::to_value(&e).unwrap()).unwrap();
        assert_eq!(back, e);
        fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn newer_schema_asks_for_an_app_update() {
        let dir = temp_dir("schema");
        let store = Store::open(&dir).unwrap();
        let (_, mut e) = publish(&dir, "v1");
        e.schema_version = SCHEMA_VERSION + 1;
        let plan = store.plan(&manifest(&e), &["hokkaido".to_string()]);
        assert_eq!(plan[0].1, Action::AppUpdateRequired);
        fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn open_clears_staging_and_manifest_round_trips() {
        let dir = temp_dir("open");
        fs::write(dir.join("hokkaido.sqlite.part"), b"x").unwrap();
        Store::open(&dir).unwrap();
        assert!(!dir.join("hokkaido.sqlite.part").exists());

        let (_, e) = publish(&dir, "v1");
        let m = manifest(&e);
        assert_eq!(
            Manifest::parse(&serde_json::to_string(&m).unwrap()).unwrap(),
            m
        );
        let newer = serde_json::json!({"format": MANIFEST_FORMAT + 1, "generated_at": "", "prefectures": {}});
        assert!(Manifest::parse(&newer.to_string()).is_err());
        fs::remove_dir_all(&dir).ok();
    }
}
