plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "com.osprey74.limes"
    compileSdk = 36
    ndkVersion = "30.0.16248370"

    defaultConfig {
        applicationId = "com.osprey74.limes"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
        // Where manifest.json and the databases are published. r2.dev while in
        // development; the release domain (limes-app.com) replaces it.
        buildConfigField("String", "DATA_BASE_URL", "\"https://pub-f67fb68aa5714cc7b4694371d04c0bf4.r2.dev/\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
        debug {
            applicationIdSuffix = ".debug"
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    sourceSets["main"].apply {
        jniLibs.srcDir(layout.buildDirectory.dir("rust/jniLibs"))
        java.srcDir(layout.buildDirectory.dir("generated/uniffi"))
    }
}

// Rust core (../../core): limes-ffi built for each ABI with cargo-ndk, and its
// UniFFI Kotlin bindings generated from the built library. Cargo rebuilds only
// what changed.
val coreDir = rootProject.projectDir.resolve("../core")
val rustJniLibs = layout.buildDirectory.dir("rust/jniLibs")
val uniffiOut = layout.buildDirectory.dir("generated/uniffi")

val cargoNdk by tasks.registering(Exec::class) {
    group = "rust"
    description = "Builds limes-ffi for Android with cargo-ndk"
    workingDir = coreDir
    inputs.files(fileTree(coreDir) { include("Cargo.toml", "Cargo.lock", "*/Cargo.toml", "*/src/**", "*/tests/golden/**", "limes-ffi/uniffi.toml") })
    outputs.dir(rustJniLibs)
    environment("ANDROID_NDK_HOME", android.ndkDirectory.absolutePath)
    commandLine(
        "cargo", "ndk", "-t", "arm64-v8a", "-t", "x86_64", "-P", "26",
        "-o", rustJniLibs.get().asFile.absolutePath,
        "build", "--release", "-p", "limes-ffi",
    )
}

val uniffiBindings by tasks.registering(Exec::class) {
    group = "rust"
    description = "Generates the Kotlin bindings of limes-ffi"
    dependsOn(cargoNdk)
    workingDir = coreDir
    inputs.dir(rustJniLibs)
    outputs.dir(uniffiOut)
    commandLine(
        "cargo", "run", "--release", "-p", "limes-ffi", "--bin", "uniffi-bindgen", "--",
        "generate", "--library", rustJniLibs.get().file("arm64-v8a/liblimes_ffi.so").asFile.absolutePath,
        "--language", "kotlin", "--no-format",
        "--out-dir", uniffiOut.get().asFile.absolutePath,
    )
}

tasks.named("preBuild") { dependsOn(uniffiBindings) }

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.core.splashscreen)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.play.services.location)
    implementation(libs.androidx.work.runtime.ktx)
    implementation(libs.androidx.datastore.preferences)
    implementation("${libs.jna.get()}@aar")
    debugImplementation(libs.androidx.compose.ui.tooling)
}
