# ios

iOS app (Swift / SwiftUI, StoreKit 2). So far: the driving, settings, download and plans screens, data updates (at launch, on return to the front and daily while in use; foreground transfers only), the free trial (recorded by `server/`, with the limits once it is over) and the subscription (StoreKit 2: the plans with their prices from the store, purchase, restore, and the system's manage-subscriptions sheet), the icon and the launch screen. Still to come: updates in the background. What the app has to do, screen by screen, is in `../docs/ios-handoff.md` (taken from the Android app).

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

## Icon and launch screen

The icon is the gauge of the Android app (`../android/app/src/main/res/drawable/ic_launcher_foreground.xml`). `scripts/render-icon.swift` draws it from the same figures and writes the PNGs in `Limes/Assets.xcassets` (the 1024 app icon, and the gauge alone for the launch screens); they are committed, so run it only after changing the icon:

```sh
swift scripts/render-icon.swift
```

The system's launch screen (`Info.plist`, `UILaunchScreen`) is the gauge on the ground color, with no text. The app's own screen (`Limes/UI/LaunchScreen.swift`) follows at every launch for about 1.5 seconds, with the name and a word on safe driving around the gauge at the same place; a tap skips it.

## Subscription

The products are `com.osprey74.limes.premium.monthly` and `com.osprey74.limes.premium.yearly`, in one subscription group, with no introductory offer (the free trial is the app's own). Prices come from the store; none is written in the app.

`Limes.storekit` is a StoreKit configuration for local testing, and the shared `Limes` scheme uses it, so a run from Xcode shows the two plans and lets you buy, renew, expire and refund them without App Store Connect (Debug > StoreKit > Manage Transactions). Its prices are ¥500 a month and ¥4,800 a year. The note under the yearly plan ("月あたり ¥400（月額の12か月分より20%お得）") is worked out from the displayed prices, because Xcode's test store (27.2) gives `Product.price` as 4 for ¥4,800. It applies only to runs started from Xcode: an app launched any other way asks the App Store, and until the products exist in App Store Connect the plans screen says it can't show them.

Signing: choose your team under Signing & Capabilities before running on a device (none is set in the project). The simulator needs no team.
