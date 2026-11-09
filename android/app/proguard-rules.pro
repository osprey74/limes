# JNA and the UniFFI bindings are reached by reflection from native code.
-keep class com.sun.jna.** { *; }
-keep class * implements com.sun.jna.** { *; }
-keep class com.osprey74.limes.core.** { *; }
-dontwarn java.awt.**
