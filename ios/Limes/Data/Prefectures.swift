import Foundation

/// A prefecture as published: `slug` is its key in manifest.json (JARTIC's file name).
struct Prefecture: Identifiable, Hashable {
    let slug: String
    let name: String
    let region: String
    var id: String { slug }
}

/// The eight regions in display order.
let regions = ["北海道", "東北", "関東", "中部", "近畿", "中国", "四国", "九州・沖縄"]

/// All 47, in JIS order; slugs as in data-pipeline/prefectures.json.
let prefectures: [Prefecture] = [
    Prefecture(slug: "hokkaido", name: "北海道", region: "北海道"),
    Prefecture(slug: "aomori", name: "青森県", region: "東北"),
    Prefecture(slug: "iwate", name: "岩手県", region: "東北"),
    Prefecture(slug: "miyagi", name: "宮城県", region: "東北"),
    Prefecture(slug: "akita", name: "秋田県", region: "東北"),
    Prefecture(slug: "yamagata", name: "山形県", region: "東北"),
    Prefecture(slug: "fukushima", name: "福島県", region: "東北"),
    Prefecture(slug: "ibaraki", name: "茨城県", region: "関東"),
    Prefecture(slug: "tochigi", name: "栃木県", region: "関東"),
    Prefecture(slug: "gumma", name: "群馬県", region: "関東"),
    Prefecture(slug: "saitama", name: "埼玉県", region: "関東"),
    Prefecture(slug: "chiba", name: "千葉県", region: "関東"),
    Prefecture(slug: "tokyo", name: "東京都", region: "関東"),
    Prefecture(slug: "kanagawa", name: "神奈川県", region: "関東"),
    Prefecture(slug: "niigata", name: "新潟県", region: "中部"),
    Prefecture(slug: "toyama", name: "富山県", region: "中部"),
    Prefecture(slug: "ishikawa", name: "石川県", region: "中部"),
    Prefecture(slug: "fukui", name: "福井県", region: "中部"),
    Prefecture(slug: "yamanashi", name: "山梨県", region: "中部"),
    Prefecture(slug: "nagano", name: "長野県", region: "中部"),
    Prefecture(slug: "gifu", name: "岐阜県", region: "中部"),
    Prefecture(slug: "shizuoka", name: "静岡県", region: "中部"),
    Prefecture(slug: "aichi", name: "愛知県", region: "中部"),
    Prefecture(slug: "mie", name: "三重県", region: "近畿"),
    Prefecture(slug: "shiga", name: "滋賀県", region: "近畿"),
    Prefecture(slug: "kyoto", name: "京都府", region: "近畿"),
    Prefecture(slug: "osaka", name: "大阪府", region: "近畿"),
    Prefecture(slug: "hyogo", name: "兵庫県", region: "近畿"),
    Prefecture(slug: "nara", name: "奈良県", region: "近畿"),
    Prefecture(slug: "wakayama", name: "和歌山県", region: "近畿"),
    Prefecture(slug: "tottori", name: "鳥取県", region: "中国"),
    Prefecture(slug: "shimane", name: "島根県", region: "中国"),
    Prefecture(slug: "okayama", name: "岡山県", region: "中国"),
    Prefecture(slug: "hiroshima", name: "広島県", region: "中国"),
    Prefecture(slug: "yamaguchi", name: "山口県", region: "中国"),
    Prefecture(slug: "tokushima", name: "徳島県", region: "四国"),
    Prefecture(slug: "kagawa", name: "香川県", region: "四国"),
    Prefecture(slug: "ehime", name: "愛媛県", region: "四国"),
    Prefecture(slug: "kochi", name: "高知県", region: "四国"),
    Prefecture(slug: "fukuoka", name: "福岡県", region: "九州・沖縄"),
    Prefecture(slug: "saga", name: "佐賀県", region: "九州・沖縄"),
    Prefecture(slug: "nagasaki", name: "長崎県", region: "九州・沖縄"),
    Prefecture(slug: "kumamoto", name: "熊本県", region: "九州・沖縄"),
    Prefecture(slug: "oita", name: "大分県", region: "九州・沖縄"),
    Prefecture(slug: "miyazaki", name: "宮崎県", region: "九州・沖縄"),
    Prefecture(slug: "kagoshima", name: "鹿児島県", region: "九州・沖縄"),
    Prefecture(slug: "okinawa", name: "沖縄県", region: "九州・沖縄"),
]

private let bySlug = Dictionary(uniqueKeysWithValues: prefectures.map { ($0.slug, $0) })

func prefecture(_ slug: String) -> Prefecture? { bySlug[slug] }
