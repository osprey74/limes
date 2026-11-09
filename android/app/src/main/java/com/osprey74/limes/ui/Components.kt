package com.osprey74.limes.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Icon
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

val CardShape = RoundedCornerShape(16.dp)
val ButtonShape = RoundedCornerShape(12.dp)

/** The "‹ 設定" style back button at the top of a screen. */
@Composable
fun BackButton(label: String, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .height(44.dp)
            .clip(ButtonShape)
            .background(Palette.Card)
            .clickable(role = Role.Button, onClick = onClick)
            .padding(start = 8.dp, end = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null, tint = Palette.Text, modifier = Modifier.size(20.dp))
        Text(label, color = Palette.Text, fontSize = 15.sp, fontWeight = FontWeight.Medium)
    }
}

/** A titled group of rows on a card. */
@Composable
fun Section(title: String, trailing: @Composable (() -> Unit)? = null, content: @Composable ColumnScope.() -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 4.dp), verticalAlignment = Alignment.Bottom) {
            Text(title, color = Palette.Muted, fontSize = 13.sp, fontWeight = FontWeight.Medium, modifier = Modifier.weight(1f))
            trailing?.invoke()
        }
        Column(Modifier.fillMaxWidth().clip(CardShape).background(Palette.Card), content = content)
    }
}

/** A row on a card, with a divider above unless it is the first. */
@Composable
fun CardRow(
    first: Boolean = false,
    minHeight: Int = 56,
    onClick: (() -> Unit)? = null,
    content: @Composable RowScope.() -> Unit,
) {
    Column {
        if (!first) Box(Modifier.fillMaxWidth().height(1.dp).background(Palette.Line))
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = minHeight.dp)
                .then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier)
                .padding(horizontal = 16.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            content = content,
        )
    }
}

/** Label (and an optional note) with a switch. */
@Composable
fun ToggleRow(label: String, note: String? = null, checked: Boolean, first: Boolean = false, onChange: (Boolean) -> Unit) {
    CardRow(first = first) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(label, color = Palette.Text, fontSize = 15.sp)
            if (note != null) Text(note, color = Palette.Muted, fontSize = 12.sp, lineHeight = 18.sp)
        }
        Switch(
            checked = checked,
            onCheckedChange = onChange,
            colors = SwitchDefaults.colors(
                checkedTrackColor = Palette.Accent,
                checkedThumbColor = Palette.Ground,
                uncheckedTrackColor = Palette.Border,
                uncheckedThumbColor = Palette.Text,
                uncheckedBorderColor = Palette.Border,
            ),
        )
    }
}

/** A status with a dot, e.g. 最新 / 更新待ち. */
@Composable
fun StatusLabel(text: String, color: Color) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        Box(Modifier.size(8.dp).clip(CircleShape).background(color))
        Text(text, color = color, fontSize = 12.sp, maxLines = 1)
    }
}

/** Outlined or filled text button of the design. */
@Composable
fun FlatButton(
    text: String,
    modifier: Modifier = Modifier,
    filled: Color? = null,
    textColor: Color = if (filled != null) Palette.Ground else Palette.Text,
    enabled: Boolean = true,
    onClick: () -> Unit,
) {
    Box(
        modifier = modifier
            .heightIn(min = 44.dp)
            .clip(ButtonShape)
            .then(if (filled != null) Modifier.background(if (enabled) filled else Palette.Line) else Modifier.border(1.dp, Palette.Border, ButtonShape))
            .clickable(enabled = enabled, role = Role.Button, onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 10.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text,
            color = if (enabled) textColor else Palette.Faint,
            fontSize = 15.sp,
            fontWeight = if (filled != null) FontWeight.Bold else FontWeight.Medium,
        )
    }
}
