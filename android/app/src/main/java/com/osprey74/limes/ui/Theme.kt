package com.osprey74.limes.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

/** Colors of the design canvas (dark ground, high-contrast text). */
object Palette {
    val Ground = Color(0xFF0B0D10)
    val Card = Color(0xFF15181D)
    val Inset = Color(0xFF1E2228)
    val Line = Color(0xFF23272E)
    val Border = Color(0xFF3A414B)
    val Text = Color(0xFFF2F4F7)
    val Sub = Color(0xFFC3C9D0)
    val Muted = Color(0xFF9AA3AE)
    val Faint = Color(0xFF6B7480)
    val Accent = Color(0xFFC8F169)
    val Ok = Color(0xFF34D3B8)
    val Waiting = Color(0xFFFFB020)
    val Danger = Color(0xFFFF6B6B)
    val DangerText = Color(0xFFFF8A8A)

    /** One color per region (in REGIONS order); labels and sizes go with them. */
    val Regions = listOf(
        Color(0xFFC8F169), Color(0xFF34D3B8), Color(0xFF8F7CFF), Color(0xFFFFB020),
        Color(0xFFF27FB0), Color(0xFF6FA8FF), Color(0xFFE8E1C4), Color(0xFFFF8A5C),
    )
}

@Composable
fun LimesTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = Palette.Accent,
            onPrimary = Palette.Ground,
            background = Palette.Ground,
            onBackground = Palette.Text,
            surface = Palette.Card,
            onSurface = Palette.Text,
            outline = Palette.Border,
            error = Palette.Danger,
        ),
        content = content,
    )
}
