//! The speed decision: stages evaluated top to bottom, the first that settles wins.
//!
//! Legal basis (道路交通法施行令第11条, in force 2026-09-01): ordinary roads keep
//! 60 km/h when they have a center line or vehicle lanes marked by road signs or
//! markings, or are separated by direction (structure, fences); others are 30 km/h.
//! On expressways (高速自動車国道) the main carriageway and its acceleration and
//! deceleration lanes are 100 km/h for ordinary cars (令第27条); other parts such
//! as ramps are 60 (令第11条第1号イ).
//!
//! Every result carries a confidence; the app never shows a speed without it.

use serde::{Deserialize, Serialize};

use crate::conditions::{Conditions, DriveTime, Vehicle};

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Confidence {
    Low,
    Mid,
    High,
}

impl Confidence {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Low => "low",
            Self::Mid => "mid",
            Self::High => "high",
        }
    }

    pub fn parse(s: &str) -> Option<Self> {
        [Self::Low, Self::Mid, Self::High]
            .into_iter()
            .find(|c| c.as_str() == s)
    }
}

/// JARTIC 道路種別コード (NO.32); often blank, then OSM decides.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RoadType {
    #[default]
    Unknown,
    General,
    /// 高速自動車国道
    Expressway,
    /// 自動車専用道路
    MotorRoad,
}

impl RoadType {
    fn is_unknown(&self) -> bool {
        *self == Self::Unknown
    }
}

/// A maximum speed regulation (JARTIC 112 line / 113 variable line / 114 area) on the way.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SpeedRegulation {
    /// km/h (NO.138)
    pub speed: u16,
    /// JARTIC regulation code: 112, 113 or 114.
    pub code: u16,
    /// JARTIC unique key (NO.21), for tracing.
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub key: String,
    #[serde(default, skip_serializing_if = "Conditions::is_empty")]
    pub conditions: Conditions,
}

/// Evidence that the road has a center line, vehicle lanes or a median (令第11条第1号ハ).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CenterEvidence {
    /// JARTIC 15 中央線
    JarticCenterLine,
    /// JARTIC 20 車両通行帯 (designated vehicle lanes, valid on one-way roads too)
    JarticLanes,
    /// JARTIC 17 はみ出し禁止 marked on both sides (or side code blank): doubles as
    /// the center line (交通規制基準 第10 留意事項1)
    JarticNoOvertaking,
    /// OSM lane_markings=yes
    OsmLaneMarkings,
    /// OSM lanes>=2 on a two-way road
    OsmLanes,
    /// Center line detected on GSI aerial photos (two-way roads only)
    AerialPhoto,
    /// Center line seen by the device camera (Phase 3)
    Camera,
}

impl CenterEvidence {
    pub fn confidence(self) -> Confidence {
        match self {
            Self::JarticCenterLine
            | Self::JarticLanes
            | Self::JarticNoOvertaking
            | Self::Camera => Confidence::High,
            // Aerial photos can be years old; OSM tags are unverified.
            Self::OsmLaneMarkings | Self::OsmLanes | Self::AerialPhoto => Confidence::Mid,
        }
    }

    fn label(self) -> &'static str {
        match self {
            Self::JarticCenterLine => "JARTIC 15 中央線",
            Self::JarticLanes => "JARTIC 20 車両通行帯",
            Self::JarticNoOvertaking => "JARTIC 17 はみ出し禁止（両側）",
            Self::OsmLaneMarkings => "OSM lane_markings=yes",
            Self::OsmLanes => "OSM lanes>=2",
            Self::AerialPhoto => "航空写真で中央線を検出",
            Self::Camera => "カメラで中央線を検出",
        }
    }
}

/// Everything known about one OSM way. Static parts come from the pipeline.
/// Defaults are left out when serialized, so most stored evidence is tiny.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct WayEvidence {
    pub osm_id: i64,
    /// OSM highway=*
    pub highway: String,
    #[serde(default, skip_serializing_if = "RoadType::is_unknown")]
    pub road_type: RoadType,
    /// OSM motorroad=yes
    #[serde(default, skip_serializing_if = "std::ops::Not::not")]
    pub motorroad: bool,
    /// Paired with an opposite one-way carriageway (median), or physically separated.
    #[serde(default, skip_serializing_if = "std::ops::Not::not")]
    pub separated: bool,
    /// OSM lane_markings=no
    #[serde(default, skip_serializing_if = "std::ops::Not::not")]
    pub no_lane_markings: bool,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub regulations: Vec<SpeedRegulation>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub center: Vec<CenterEvidence>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Stage {
    /// 1 規制速度
    Regulated = 1,
    /// 2 高速自動車国道
    Expressway = 2,
    /// 3 自動車専用道路
    MotorRoad = 3,
    /// 4 中央分離帯・構造分離
    Separated = 4,
    /// 5 中央線・車両通行帯
    CenterLine = 5,
    /// 6 農道・林道等
    Track = 6,
    /// 7 生活道路（証拠なし）
    NoEvidence = 7,
}

impl Stage {
    pub fn number(self) -> i32 {
        self as i32
    }

    pub fn from_number(n: i32) -> Option<Self> {
        use Stage::*;
        [
            Regulated, Expressway, MotorRoad, Separated, CenterLine, Track, NoEvidence,
        ]
        .into_iter()
        .find(|s| s.number() == n)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Decision {
    pub speed: u16,
    pub confidence: Confidence,
    pub stage: Stage,
    pub reason: String,
}

const LEGAL_60: u16 = 60;
const LEGAL_30: u16 = 30;
const EXPRESSWAY: u16 = 100;

/// Decide the maximum speed of a way for `vehicle` at `t`.
///
/// Stage 8 (unknown) is not here: it means no way was matched, which the map
/// matcher reports. Every way gets a speed; without evidence it falls back to 30
/// with low confidence (decided 2026-11-08: lean to the safe side).
impl WayEvidence {
    /// Nothing beyond the OSM id and highway: decided by the highway tag alone.
    pub fn is_bare(&self) -> bool {
        *self
            == WayEvidence {
                osm_id: self.osm_id,
                highway: self.highway.clone(),
                ..Default::default()
            }
    }
}

pub fn decide(e: &WayEvidence, t: &DriveTime, vehicle: Vehicle) -> Decision {
    let applicable = e
        .regulations
        .iter()
        .filter(|r| r.conditions.applies(t, vehicle));
    // Overlapping regulations: the lowest speed is the one that binds.
    if let Some(r) = applicable.min_by_key(|r| r.speed) {
        let key = if r.key.is_empty() {
            String::new()
        } else {
            format!(" ({})", r.key)
        };
        return decision(
            r.speed,
            Confidence::High,
            Stage::Regulated,
            format!("JARTIC {}{key}", r.code),
        );
    }
    if e.road_type == RoadType::Expressway {
        return decision(
            EXPRESSWAY,
            Confidence::High,
            Stage::Expressway,
            "JARTIC 道路種別 高速自動車国道".into(),
        );
    }
    if e.highway == "motorway" {
        return decision(
            EXPRESSWAY,
            Confidence::High,
            Stage::Expressway,
            "OSM highway=motorway".into(),
        );
    }
    // Ramps are expressway parts other than the main carriageway (令第11条第1号イ): 60.
    // Acceleration lanes would be 100, but OSM doesn't tell them apart; lean low.
    if e.highway == "motorway_link" {
        return decision(
            LEGAL_60,
            Confidence::High,
            Stage::Expressway,
            "OSM highway=motorway_link（ランプ）".into(),
        );
    }
    if e.road_type == RoadType::MotorRoad {
        return decision(
            LEGAL_60,
            Confidence::High,
            Stage::MotorRoad,
            "JARTIC 道路種別 自動車専用道路".into(),
        );
    }
    if e.motorroad {
        return decision(
            LEGAL_60,
            Confidence::High,
            Stage::MotorRoad,
            "OSM motorroad=yes".into(),
        );
    }
    if e.separated {
        return decision(
            LEGAL_60,
            Confidence::High,
            Stage::Separated,
            "上下線分離".into(),
        );
    }
    if let Some(best) = e.center.iter().copied().max_by_key(|c| c.confidence()) {
        return decision(
            LEGAL_60,
            best.confidence(),
            Stage::CenterLine,
            best.label().into(),
        );
    }
    if e.highway == "track" {
        return decision(
            LEGAL_30,
            Confidence::Mid,
            Stage::Track,
            "OSM highway=track".into(),
        );
    }
    if e.no_lane_markings {
        return decision(
            LEGAL_30,
            Confidence::Mid,
            Stage::NoEvidence,
            "OSM lane_markings=no".into(),
        );
    }
    decision(
        LEGAL_30,
        Confidence::Low,
        Stage::NoEvidence,
        format!("証拠なし（OSM highway={}）", e.highway),
    )
}

fn decision(speed: u16, confidence: Confidence, stage: Stage, reason: String) -> Decision {
    Decision {
        speed,
        confidence,
        stage,
        reason,
    }
}
