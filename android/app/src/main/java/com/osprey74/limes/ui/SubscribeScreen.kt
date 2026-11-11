package com.osprey74.limes.ui

import android.app.Activity
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.osprey74.limes.LimesApp
import com.osprey74.limes.access.AccessState
import com.osprey74.limes.access.Billing
import com.osprey74.limes.access.Plan
import kotlinx.coroutines.launch
import java.text.NumberFormat
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Currency
import java.util.Locale

/** The plans, what they include, and what stays free. */
@Composable
fun SubscribeScreen(app: LimesApp, backLabel: String, onBack: () -> Unit) {
    val context = LocalContext.current
    val access by app.access.state.collectAsState()
    val plans by app.billing.plans.collectAsState()
    val error by app.billing.error.collectAsState()
    val removed by app.settings.dataRemovedNotice.collectAsState(initial = false)

    LaunchedEffect(Unit) {
        app.billing.loadPlans()
        app.access.refresh()
    }
    // The deletion notice is said once: cleared on leaving this screen.
    DisposableEffect(Unit) {
        onDispose { if (removed) app.scope.launch { app.settings.setDataRemovedNotice(false) } }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Palette.Ground)
            .verticalScroll(rememberScrollState())
            .statusBarsPadding()
            .padding(start = 16.dp, end = 16.dp, top = 16.dp, bottom = 40.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp),
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            BackButton(backLabel, onBack)
            Text("有料プラン", color = Palette.Text, fontSize = 30.sp, fontWeight = FontWeight.Bold)
        }

        if (removed) {
            Notice("無料期間が終わったため、保存していた道路データを削除しました。登録すると、もう一度ダウンロードできます。", Palette.Waiting)
        }
        Notice(statusText(access), if (access == AccessState.Expired) Palette.Waiting else Palette.Ok)

        Section("有料プランでできること") {
            Bullet("走行中の道路の最高速度（推定）の表示", first = true)
            Bullet("都道府県データのダウンロードと自動更新")
            Bullet("登録しなくても、GPS による現在の速度はいつでも表示されます")
        }

        if (access != AccessState.Subscribed) {
            Section("プラン") {
                if (plans.isEmpty()) {
                    Text(
                        "Google Play に接続できないため、プランを表示できません。通信できる環境で開き直してください。",
                        color = Palette.Muted, fontSize = 14.sp, lineHeight = 22.sp,
                        modifier = Modifier.padding(16.dp),
                    )
                } else {
                    val monthly = plans.firstOrNull { it.id == "monthly" }
                    plans.forEachIndexed { i, plan ->
                        PlanRow(plan, monthly, first = i == 0) { app.billing.purchase(context as Activity, plan) }
                    }
                }
            }
            error?.let { Text(it, color = Palette.DangerText, fontSize = 13.sp, lineHeight = 20.sp) }
        }

        Text(
            "有料プランは Google Play の定期購入です。期間の終わりに自動で更新され、同じ料金が請求されます。" +
                "解約は Google Play の「定期購入」からいつでもでき、解約しても期間の終わりまでは使えます。",
            color = Palette.Muted, fontSize = 12.sp, lineHeight = 20.sp,
        )
        FlatButton("Google Play で定期購入を管理", Modifier.fillMaxWidth()) {
            val uri = Uri.parse("https://play.google.com/store/account/subscriptions?sku=${Billing.PRODUCT}&package=${context.packageName}")
            context.startActivity(Intent(Intent.ACTION_VIEW, uri))
        }
    }
}

private fun statusText(access: AccessState?): String = when (access) {
    AccessState.NotStarted -> "データを初めてダウンロードした日から14日間、すべての機能を無料で使えます。"
    is AccessState.Trial -> {
        val days = ((access.ends - System.currentTimeMillis()) / (24 * 60 * 60 * 1000L) + 1).coerceAtLeast(1)
        val date = Instant.ofEpochMilli(access.ends).atZone(ZoneId.of("Asia/Tokyo")).format(DateTimeFormatter.ofPattern("M月d日"))
        "無料期間中です。あと${days}日（${date}まで）"
    }
    AccessState.Subscribed -> "有料プランに登録済みです。"
    AccessState.Expired -> "無料期間は終了しました。"
    null -> "確認しています…"
}

@Composable
private fun Notice(text: String, color: androidx.compose.ui.graphics.Color) {
    Row(Modifier.fillMaxWidth().clip(CardShape).background(Palette.Card).padding(16.dp)) {
        Text(text, color = color, fontSize = 14.sp, lineHeight = 22.sp)
    }
}

@Composable
private fun Bullet(text: String, first: Boolean = false) {
    CardRow(first = first) {
        Text(text, color = Palette.Text, fontSize = 15.sp, lineHeight = 22.sp)
    }
}

@Composable
private fun PlanRow(plan: Plan, monthly: Plan?, first: Boolean, onBuy: () -> Unit) {
    val yearly = plan.id == "yearly"
    CardRow(first = first) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(if (yearly) "年額" else "月額", color = Palette.Text, fontSize = 15.sp, fontWeight = FontWeight.Medium)
            Text(plan.price + if (yearly) "／年" else "／月", color = Palette.Text, fontSize = 18.sp, fontWeight = FontWeight.Bold)
            if (yearly) yearlyNote(plan, monthly)?.let { Text(it, color = Palette.Muted, fontSize = 12.sp) }
        }
        FlatButton("登録する", filled = Palette.Accent, onClick = onBuy)
    }
}

/** "月あたり ¥400（月額の12か月分より20%お得）", from the prices Play gave. */
private fun yearlyNote(yearly: Plan, monthly: Plan?): String? {
    val format = NumberFormat.getCurrencyInstance(Locale.JAPAN).apply {
        currency = runCatching { Currency.getInstance(yearly.currency) }.getOrNull() ?: return null
        maximumFractionDigits = 0
    }
    val perMonth = "月あたり " + format.format(yearly.priceMicros / 12 / 1_000_000.0)
    if (monthly == null || monthly.currency != yearly.currency || monthly.priceMicros == 0L) return perMonth
    val saving = (100 - yearly.priceMicros * 100 / (monthly.priceMicros * 12)).toInt()
    return if (saving > 0) "$perMonth（月額の12か月分より${saving}%お得）" else perMonth
}
