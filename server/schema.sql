-- One row per device: the hash the app derives from a reinstall-stable ID
-- (Android: ANDROID_ID, iOS: an ID kept in the keychain) and when it was first
-- seen. Nothing else about the user is stored.
CREATE TABLE IF NOT EXISTS installs (
  id TEXT PRIMARY KEY,          -- 64 hex chars (SHA-256)
  platform TEXT NOT NULL,       -- 'android' | 'ios'
  first_seen TEXT NOT NULL      -- ISO 8601, UTC
) WITHOUT ROWID;
