package com.osprey74.limes.data

/** A prefecture as published: `slug` is its key in manifest.json (JARTIC's file name). */
data class Prefecture(val slug: String, val name: String, val region: String)

/** The eight regions in display order. */
val REGIONS = listOf("北海道", "東北", "関東", "中部", "近畿", "中国", "四国", "九州・沖縄")

/** All 47, in JIS order; slugs as in data-pipeline/prefectures.json. */
val PREFECTURES = listOf(
    Prefecture("hokkaido", "北海道", "北海道"),
    Prefecture("aomori", "青森県", "東北"),
    Prefecture("iwate", "岩手県", "東北"),
    Prefecture("miyagi", "宮城県", "東北"),
    Prefecture("akita", "秋田県", "東北"),
    Prefecture("yamagata", "山形県", "東北"),
    Prefecture("fukushima", "福島県", "東北"),
    Prefecture("ibaraki", "茨城県", "関東"),
    Prefecture("tochigi", "栃木県", "関東"),
    Prefecture("gumma", "群馬県", "関東"),
    Prefecture("saitama", "埼玉県", "関東"),
    Prefecture("chiba", "千葉県", "関東"),
    Prefecture("tokyo", "東京都", "関東"),
    Prefecture("kanagawa", "神奈川県", "関東"),
    Prefecture("niigata", "新潟県", "中部"),
    Prefecture("toyama", "富山県", "中部"),
    Prefecture("ishikawa", "石川県", "中部"),
    Prefecture("fukui", "福井県", "中部"),
    Prefecture("yamanashi", "山梨県", "中部"),
    Prefecture("nagano", "長野県", "中部"),
    Prefecture("gifu", "岐阜県", "中部"),
    Prefecture("shizuoka", "静岡県", "中部"),
    Prefecture("aichi", "愛知県", "中部"),
    Prefecture("mie", "三重県", "近畿"),
    Prefecture("shiga", "滋賀県", "近畿"),
    Prefecture("kyoto", "京都府", "近畿"),
    Prefecture("osaka", "大阪府", "近畿"),
    Prefecture("hyogo", "兵庫県", "近畿"),
    Prefecture("nara", "奈良県", "近畿"),
    Prefecture("wakayama", "和歌山県", "近畿"),
    Prefecture("tottori", "鳥取県", "中国"),
    Prefecture("shimane", "島根県", "中国"),
    Prefecture("okayama", "岡山県", "中国"),
    Prefecture("hiroshima", "広島県", "中国"),
    Prefecture("yamaguchi", "山口県", "中国"),
    Prefecture("tokushima", "徳島県", "四国"),
    Prefecture("kagawa", "香川県", "四国"),
    Prefecture("ehime", "愛媛県", "四国"),
    Prefecture("kochi", "高知県", "四国"),
    Prefecture("fukuoka", "福岡県", "九州・沖縄"),
    Prefecture("saga", "佐賀県", "九州・沖縄"),
    Prefecture("nagasaki", "長崎県", "九州・沖縄"),
    Prefecture("kumamoto", "熊本県", "九州・沖縄"),
    Prefecture("oita", "大分県", "九州・沖縄"),
    Prefecture("miyazaki", "宮崎県", "九州・沖縄"),
    Prefecture("kagoshima", "鹿児島県", "九州・沖縄"),
    Prefecture("okinawa", "沖縄県", "九州・沖縄"),
)

private val bySlug = PREFECTURES.associateBy { it.slug }

fun prefecture(slug: String): Prefecture? = bySlug[slug]
