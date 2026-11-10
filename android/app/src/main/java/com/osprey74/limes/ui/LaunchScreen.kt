package com.osprey74.limes.ui

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.osprey74.limes.R

private const val SHOW_MS = 1500

/** Shown at every launch: name, icon and a word on safe driving. A tap skips it. */
@Composable
fun LaunchScreen(onDone: () -> Unit) {
    val done by rememberUpdatedState(onDone)
    val progress = remember { Animatable(0f) }
    LaunchedEffect(Unit) {
        progress.animateTo(1f, tween(SHOW_MS, easing = LinearEasing))
        done()
    }
    Column(
        Modifier
            .fillMaxSize()
            .background(Palette.Ground)
            .clickable(interactionSource = remember { MutableInteractionSource() }, indication = null) { done() }
            .systemBarsPadding(),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Column(
            Modifier.weight(1f).padding(top = 80.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            // The drawable is the 108 adaptive grid; the gauge fills its inner 72 (128 dp here).
            Image(painterResource(R.drawable.ic_launcher_foreground), contentDescription = null, modifier = Modifier.size(192.dp))
            Text("Limes", color = Palette.Text, fontSize = 44.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.7.sp)
            Text("リメス", color = Palette.Muted, fontSize = 13.sp, letterSpacing = 2.6.sp)
        }
        Text(
            "道路状況や実際の交通規制にあわせ、\n安全運転を心がけましょう",
            color = Palette.Text,
            fontSize = 17.sp,
            fontWeight = FontWeight.Medium,
            lineHeight = 30.sp,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(horizontal = 32.dp),
        )
        Spacer(Modifier.height(28.dp))
        Box(
            Modifier
                .padding(bottom = 56.dp)
                .width(120.dp)
                .height(3.dp)
                .clip(RoundedCornerShape(2.dp))
                .background(Palette.Line),
        ) {
            Box(Modifier.fillMaxHeight().fillMaxWidth(progress.value).background(Palette.Muted))
        }
    }
}
