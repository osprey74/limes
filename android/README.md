# android

Android app (Kotlin / Jetpack Compose, Play Billing). Phase 2: the project builds and loads the Rust core; the driving, settings and download screens come next.

| Item | Value |
| --- | --- |
| Application ID | `com.osprey74.limes` (debug: `com.osprey74.limes.debug`) |
| SDK | compileSdk / targetSdk 36, minSdk 26 |
| Build | AGP 8.11.1, Gradle 8.13, Kotlin 2.1.0, JDK 17+ |
| ABIs | arm64-v8a, x86_64 (emulator) |

## Rust core

`preBuild` runs two tasks in `app/build.gradle.kts`:

- `cargoNdk`: builds `../core/limes-ffi` for each ABI with cargo-ndk into `app/build/rust/jniLibs`
- `uniffiBindings`: generates the Kotlin bindings (`com.osprey74.limes.core`, through JNA) into `app/build/generated/uniffi`

Neither output is committed. Requirements: Rust with the Android targets, cargo-ndk and the NDK version in `ndkVersion`.

```sh
rustup target add aarch64-linux-android x86_64-linux-android
cargo install cargo-ndk --locked
# NDK: Android Studio > Settings > Android SDK > SDK Tools > NDK (Side by side)
```

## Build

Open this folder in Android Studio, or:

```sh
./gradlew assembleDebug   # app/build/outputs/apk/debug/app-debug.apk
```

`local.properties` (not committed) holds `sdk.dir`; Android Studio writes it.
