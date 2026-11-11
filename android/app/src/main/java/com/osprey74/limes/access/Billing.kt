package com.osprey74.limes.access

import android.app.Activity
import com.android.billingclient.api.AcknowledgePurchaseParams
import com.android.billingclient.api.BillingClient
import com.android.billingclient.api.BillingClient.BillingResponseCode
import com.android.billingclient.api.BillingClient.ProductType
import com.android.billingclient.api.BillingClientStateListener
import com.android.billingclient.api.BillingFlowParams
import com.android.billingclient.api.BillingResult
import com.android.billingclient.api.PendingPurchasesParams
import com.android.billingclient.api.ProductDetails
import com.android.billingclient.api.Purchase
import com.android.billingclient.api.PurchasesUpdatedListener
import com.android.billingclient.api.QueryProductDetailsParams
import com.android.billingclient.api.QueryPurchasesParams
import com.osprey74.limes.LimesApp
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeoutOrNull
import kotlin.coroutines.resume

/** A base plan of the subscription as Google Play offers it to this user. */
data class Plan(
    val id: String,
    val price: String,
    val priceMicros: Long,
    val currency: String,
    val offerToken: String,
)

/**
 * The Limes subscription on Google Play: one product with a monthly and a
 * yearly base plan, no store trial (the trial is the app's own, see Access).
 */
class Billing(private val app: LimesApp) : PurchasesUpdatedListener {
    private val client = BillingClient.newBuilder(app)
        .setListener(this)
        .enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build())
        .enableAutoServiceReconnection()
        .build()
    private val connecting = Mutex()
    private var details: ProductDetails? = null

    private val _plans = MutableStateFlow<List<Plan>>(emptyList())
    val plans: StateFlow<List<Plan>> = _plans.asStateFlow()

    /** Why the last purchase did not go through, for the subscribe screen. */
    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    /** True when an active subscription is held, null when Play can't be asked. */
    suspend fun subscribed(): Boolean? {
        if (!connect()) return null
        val (result, purchases) = suspendCancellableCoroutine { cont ->
            client.queryPurchasesAsync(QueryPurchasesParams.newBuilder().setProductType(ProductType.SUBS).build()) { r, list ->
                if (cont.isActive) cont.resume(r to list)
            }
        }
        if (result.responseCode != BillingResponseCode.OK) return null
        return accept(purchases)
    }

    /** Fetches the plans and prices to show. */
    suspend fun loadPlans() {
        if (!connect()) return
        val params = QueryProductDetailsParams.newBuilder().setProductList(
            listOf(QueryProductDetailsParams.Product.newBuilder().setProductId(PRODUCT).setProductType(ProductType.SUBS).build()),
        ).build()
        val product = suspendCancellableCoroutine<ProductDetails?> { cont ->
            client.queryProductDetailsAsync(params) { r, result ->
                if (cont.isActive) cont.resume(result.productDetailsList.takeIf { r.responseCode == BillingResponseCode.OK }?.firstOrNull())
            }
        } ?: return
        details = product
        // Base plans only: offers (offerId set) are not used.
        _plans.value = product.subscriptionOfferDetails.orEmpty()
            .filter { it.offerId == null && it.basePlanId in PLANS }
            .sortedBy { PLANS.indexOf(it.basePlanId) }
            .mapNotNull { offer ->
                val phase = offer.pricingPhases.pricingPhaseList.lastOrNull() ?: return@mapNotNull null
                Plan(offer.basePlanId, phase.formattedPrice, phase.priceAmountMicros, phase.priceCurrencyCode, offer.offerToken)
            }
    }

    fun purchase(activity: Activity, plan: Plan) {
        val product = details ?: return
        _error.value = null
        val params = BillingFlowParams.newBuilder().setProductDetailsParamsList(
            listOf(BillingFlowParams.ProductDetailsParams.newBuilder().setProductDetails(product).setOfferToken(plan.offerToken).build()),
        ).build()
        val result = client.launchBillingFlow(activity, params)
        if (result.responseCode != BillingResponseCode.OK) _error.value = message(result)
    }

    override fun onPurchasesUpdated(result: BillingResult, purchases: MutableList<Purchase>?) {
        when (result.responseCode) {
            BillingResponseCode.OK -> app.scope.launch {
                accept(purchases.orEmpty())
                app.access.refresh()
            }
            BillingResponseCode.USER_CANCELED -> Unit
            else -> _error.value = message(result)
        }
    }

    /** Acknowledges new purchases (Play refunds them otherwise); true when one is active. */
    private suspend fun accept(purchases: List<Purchase>): Boolean {
        val active = purchases.filter { it.purchaseState == Purchase.PurchaseState.PURCHASED && PRODUCT in it.products }
        for (p in active.filter { !it.isAcknowledged }) {
            val params = AcknowledgePurchaseParams.newBuilder().setPurchaseToken(p.purchaseToken).build()
            suspendCancellableCoroutine { cont -> client.acknowledgePurchase(params) { if (cont.isActive) cont.resume(Unit) } }
        }
        return active.isNotEmpty()
    }

    private suspend fun connect(): Boolean = connecting.withLock {
        if (client.isReady) return@withLock true
        withTimeoutOrNull(10_000) {
            suspendCancellableCoroutine { cont ->
                client.startConnection(object : BillingClientStateListener {
                    override fun onBillingSetupFinished(result: BillingResult) {
                        if (cont.isActive) cont.resume(result.responseCode == BillingResponseCode.OK)
                    }

                    override fun onBillingServiceDisconnected() = Unit
                })
            }
        } ?: false
    }

    private fun message(result: BillingResult): String = when (result.responseCode) {
        BillingResponseCode.ITEM_ALREADY_OWNED -> "すでに登録されています"
        BillingResponseCode.BILLING_UNAVAILABLE, BillingResponseCode.SERVICE_UNAVAILABLE ->
            "Google Play に接続できませんでした。通信できる環境でもう一度お試しください"
        else -> "登録を完了できませんでした（コード ${result.responseCode}）"
    }

    companion object {
        const val PRODUCT = "premium"
        val PLANS = listOf("monthly", "yearly")
    }
}
