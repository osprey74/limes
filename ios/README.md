# ios

iOS app (Swift / SwiftUI, StoreKit 2). So far: the driving, settings and download screens and data updates (at launch, on return to the front and daily while in use; foreground transfers only). Still to come: the launch screen and icon, the free trial, the subscription, and updates in the background. What the app has to do, screen by screen, is in `../docs/ios-handoff.md` (taken from the Android app).

| Item | Value |
| --- | --- |
| Bundle ID | `com.osprey74.limes` |
| Deployment target | iOS 17.0, iPhone, portrait and landscape |
| Build | Xcode 27.2, Swift 5 language mode |
| Project | `Limes.xcodeproj`; the `Limes/` folder is synchronized, so files added to it join the target without editing the project |

## Rust core

`scripts/build-core.sh` builds `../core/limes-ffi` for the device and the simulator and generates the UniFFI Swift bindings:

- `Frameworks/LimesCore.xcframework`: the static library with its C header (module `LimesCoreFFI`)
- `Limes/Generated/LimesCore.swift`: the Swift API (`Engine`, `localTime`, ...), compiled with the app

Neither output is committed. Run the script once before opening the project in Xcode, and again after any change under `core/`. Requirements: Rust with the iOS targets.

```sh
rustup target add aarch64-apple-ios aarch64-apple-ios-sim
scripts/build-core.sh
```

The script sets `IPHONEOS_DEPLOYMENT_TARGET` to the app's deployment target; keep the two equal (a mismatch between the C parts and Rust fails the link).

## Build

```sh
scripts/build-core.sh
open Limes.xcodeproj
```

Signing: choose your team under Signing & Capabilities before running on a device (none is set in the project). The simulator needs no team.
