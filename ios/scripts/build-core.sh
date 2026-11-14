#!/bin/sh
# Builds the Rust core (../core/limes-ffi) for iOS and generates its Swift
# bindings. Run it once before opening the project in Xcode, and again after
# any change under core/.
#
#   ios/Frameworks/LimesCore.xcframework   static library, device and simulator
#   ios/Limes/Generated/LimesCore.swift    UniFFI Swift bindings
#
# Neither output is committed. Requirements: Xcode, and Rust with the iOS
# targets (rustup target add aarch64-apple-ios aarch64-apple-ios-sim).
set -eu

# Xcode and non-login shells do not have cargo on PATH.
PATH="$HOME/.cargo/bin:$PATH"
export PATH

# The app's deployment target (IPHONEOS_DEPLOYMENT_TARGET in the Xcode
# project). Without it the C parts (SQLite, zstd) are compiled for the SDK's
# version while rustc links for its own default, and the link fails.
IPHONEOS_DEPLOYMENT_TARGET=17.0
export IPHONEOS_DEPLOYMENT_TARGET

ios_dir=$(cd "$(dirname "$0")/.." && pwd)
core_dir="$ios_dir/../core"
framework="$ios_dir/Frameworks/LimesCore.xcframework"
generated="$ios_dir/Limes/Generated"
work="$core_dir/target/ios-bindings"

cd "$core_dir"
for target in aarch64-apple-ios aarch64-apple-ios-sim; do
    cargo build --release -p limes-ffi --target "$target"
done

rm -rf "$work"
mkdir -p "$work"
cargo run --release -p limes-ffi --bin uniffi-bindgen -- generate \
    --library target/aarch64-apple-ios/release/liblimes_ffi.a \
    --language swift --no-format --out-dir "$work"

# The header and its module map go into the framework (the map must be named
# module.modulemap there); the Swift file is compiled with the app.
mkdir -p "$work/headers/LimesCoreFFI" "$generated"
mv "$work/LimesCoreFFI.h" "$work/headers/LimesCoreFFI/"
mv "$work/LimesCoreFFI.modulemap" "$work/headers/LimesCoreFFI/module.modulemap"
mv "$work/LimesCore.swift" "$generated/"

rm -rf "$framework"
xcodebuild -create-xcframework \
    -library target/aarch64-apple-ios/release/liblimes_ffi.a -headers "$work/headers" \
    -library target/aarch64-apple-ios-sim/release/liblimes_ffi.a -headers "$work/headers" \
    -output "$framework"
