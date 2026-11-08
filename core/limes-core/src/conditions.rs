//! JARTIC regulation conditions (規制条件): when and to which vehicles a regulation applies.
//!
//! Spec: 拡張版標準フォーマット説明書 ver「k_2.1」, items NO.41-85 (対象, 5 blocks) and
//! NO.86-130 (除外, 5 blocks), each block being period start/end (MMDD), time
//! start/end (hhmm), weekday code and vehicle codes A-D. The pipeline passes the
//! raw strings; all interpretation happens here so the app and the pipeline agree.
//!
//! Combination rule (the spec gives none explicitly, so this is our reading):
//! a regulation applies when any used target block matches (or no target block
//! is used) and no used exclusion block matches. A block matches when every field
//! it sets matches.

use serde::{Deserialize, Serialize};

/// One condition block as written in the CSV, in column order.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct RawBlock {
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub period_start: String,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub period_end: String,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub time_start: String,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub time_end: String,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub weekday: String,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub vehicle_a: String,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub vehicle_b: String,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub vehicle_c: String,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub vehicle_d: String,
}

/// Local date and time at which a regulation is evaluated.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct DriveTime {
    pub month: u8,
    pub day: u8,
    /// Minutes since 0:00.
    pub minute_of_day: u16,
    /// 0 = Monday ... 6 = Sunday.
    pub weekday: u8,
    /// National holiday (国民の祝日・休日).
    pub holiday: bool,
}

impl DriveTime {
    /// Weekday noon, used where no real time is known (e.g. the speed map tiles).
    pub const REPRESENTATIVE: DriveTime = DriveTime {
        month: 6,
        day: 10,
        minute_of_day: 12 * 60,
        weekday: 2,
        holiday: false,
    };
}

/// What the app is driving. Only ordinary passenger cars (普通乗用自動車) for now.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
pub enum Vehicle {
    #[default]
    OrdinaryCar,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Weekdays {
    SatSun,
    SatSunHoliday,
    SunHoliday,
    Sat,
    Sun,
    Holiday,
}

/// 共通コード「曜日コード」. 99 (その他, see 規制内容) and codes outside the table
/// (e.g. 9 in Aichi) carry no usable restriction and are treated as unset.
fn weekdays(code: &str) -> Option<Weekdays> {
    match code {
        "1" => Some(Weekdays::SatSun),
        "2" => Some(Weekdays::SatSunHoliday),
        "3" => Some(Weekdays::SunHoliday),
        "4" => Some(Weekdays::Sat),
        "5" => Some(Weekdays::Sun),
        "6" => Some(Weekdays::Holiday),
        _ => None,
    }
}

fn weekday_matches(w: Weekdays, t: &DriveTime) -> bool {
    let (sat, sun, hol) = (t.weekday == 5, t.weekday == 6, t.holiday);
    match w {
        Weekdays::SatSun => sat || sun,
        Weekdays::SatSunHoliday => sat || sun || hol,
        Weekdays::SunHoliday => sun || hol,
        Weekdays::Sat => sat,
        Weekdays::Sun => sun,
        Weekdays::Holiday => hol,
    }
}

fn number(s: &str) -> Option<u16> {
    let s = s.trim();
    if s.is_empty() { None } else { s.parse().ok() }
}

/// Period as (start, end) in MMDD. All year (blank, 0101-1231) is None.
fn period(start: &str, end: &str) -> Option<(u16, u16)> {
    let (s, e) = (number(start).unwrap_or(0), number(end).unwrap_or(0));
    let all_year = matches!(s, 0 | 101) && matches!(e, 0 | 1231);
    if all_year {
        None
    } else {
        Some((if s == 0 { 101 } else { s }, if e == 0 { 1231 } else { e }))
    }
}

/// Time window as (start, end) in minutes. All day (blank, 0-0, 0-2400) is None.
fn time_window(start: &str, end: &str) -> Option<(u16, u16)> {
    let (s, e) = (number(start).unwrap_or(0), number(end).unwrap_or(0));
    if s == 0 && matches!(e, 0 | 2400) {
        return None;
    }
    let minutes = |hhmm: u16| (hhmm / 100) * 60 + hhmm % 100;
    Some((minutes(s), if e == 0 { 24 * 60 } else { minutes(e) }))
}

/// Inclusive range that may wrap around (e.g. 1201-0331, 22:00-06:00).
fn in_range(value: u16, (start, end): (u16, u16)) -> bool {
    if start <= end {
        start <= value && value <= end
    } else {
        value >= start || value <= end
    }
}

/// Half-open time window [start, end), wrapping past midnight.
fn in_window(minute: u16, (start, end): (u16, u16)) -> bool {
    if start <= end {
        start <= minute && minute < end
    } else {
        minute >= start || minute < end
    }
}

/// Decimal-digit bit flags (共通コード「対象コード」): digit n from the right is flag n.
fn has_flag(code: &str, n: usize) -> bool {
    code.trim().chars().rev().nth(n - 1) == Some('1')
}

fn unset(code: &str) -> bool {
    matches!(code.trim(), "" | "0")
}

/// Category A flags 1-5 (車両, 自動車, 乗用, 普乗, 普通) all include ordinary passenger cars.
const ORDINARY_CAR_A_FLAGS: [usize; 5] = [1, 2, 3, 4, 5];
/// Category D flag 15: その他, described only in 規制条件 (NO.131).
const D_OTHER_FLAG: usize = 15;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum VehicleMatch {
    Unset,
    Yes,
    No,
    /// Only "その他": the target can't be read from the codes.
    Unclear,
}

fn vehicle_match(block: &RawBlock, vehicle: Vehicle) -> VehicleMatch {
    let (a, b, c, d) = (
        &block.vehicle_a,
        &block.vehicle_b,
        &block.vehicle_c,
        &block.vehicle_d,
    );
    if [a, b, c, d].iter().all(|v| unset(v)) {
        return VehicleMatch::Unset;
    }
    match vehicle {
        Vehicle::OrdinaryCar => {
            if ORDINARY_CAR_A_FLAGS.iter().any(|&n| has_flag(a, n)) {
                VehicleMatch::Yes
            } else if unset(a) && unset(b) && unset(c) && has_flag(d, D_OTHER_FLAG) {
                VehicleMatch::Unclear
            } else {
                VehicleMatch::No
            }
        }
    }
}

impl RawBlock {
    fn is_used(&self) -> bool {
        period(&self.period_start, &self.period_end).is_some()
            || time_window(&self.time_start, &self.time_end).is_some()
            || weekdays(&self.weekday).is_some()
            || vehicle_match(self, Vehicle::OrdinaryCar) != VehicleMatch::Unset
    }

    /// Whether every condition this block sets holds. `unclear_vehicle` decides
    /// blocks whose vehicles are only "その他".
    fn matches(&self, t: &DriveTime, vehicle: Vehicle, unclear_vehicle: bool) -> bool {
        if let Some(p) = period(&self.period_start, &self.period_end)
            && !in_range(u16::from(t.month) * 100 + u16::from(t.day), p)
        {
            return false;
        }
        if let Some(w) = time_window(&self.time_start, &self.time_end)
            && !in_window(t.minute_of_day, w)
        {
            return false;
        }
        if let Some(w) = weekdays(&self.weekday)
            && !weekday_matches(w, t)
        {
            return false;
        }
        match vehicle_match(self, vehicle) {
            VehicleMatch::Unset | VehicleMatch::Yes => true,
            VehicleMatch::No => false,
            VehicleMatch::Unclear => unclear_vehicle,
        }
    }
}

/// Target and exclusion blocks of one regulation.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct Conditions {
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub targets: Vec<RawBlock>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub exclusions: Vec<RawBlock>,
    /// 規制条件 (NO.131), free text.
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub note: String,
}

impl Conditions {
    pub fn is_empty(&self) -> bool {
        self.targets.is_empty() && self.exclusions.is_empty() && self.note.is_empty()
    }

    /// Whether the regulation applies to `vehicle` at `t`.
    ///
    /// A target block naming only "その他" is taken to include the vehicle
    /// (decided 2026-11-08: the codes don't say who is meant, so apply it — mostly
    /// Nagano and Okayama, where 規制条件 is blank). An exclusion block naming only
    /// "その他" is taken not to exclude it, for the same reason.
    pub fn applies(&self, t: &DriveTime, vehicle: Vehicle) -> bool {
        let targets: Vec<_> = self.targets.iter().filter(|b| b.is_used()).collect();
        let targeted = targets.is_empty() || targets.iter().any(|b| b.matches(t, vehicle, true));
        targeted
            && !self
                .exclusions
                .iter()
                .filter(|b| b.is_used())
                .any(|b| b.matches(t, vehicle, false))
    }

    /// True when the result can depend on date, time or weekday (not only on the vehicle).
    pub fn is_time_dependent(&self) -> bool {
        self.targets.iter().chain(&self.exclusions).any(|b| {
            period(&b.period_start, &b.period_end).is_some()
                || time_window(&b.time_start, &b.time_end).is_some()
                || weekdays(&b.weekday).is_some()
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn at(month: u8, day: u8, hh: u16, mm: u16, weekday: u8, holiday: bool) -> DriveTime {
        DriveTime {
            month,
            day,
            minute_of_day: hh * 60 + mm,
            weekday,
            holiday,
        }
    }

    fn block(f: impl FnOnce(&mut RawBlock)) -> RawBlock {
        let mut b = RawBlock::default();
        f(&mut b);
        b
    }

    const CAR: Vehicle = Vehicle::OrdinaryCar;

    #[test]
    fn unset_encodings_are_unconditional() {
        // Encodings seen across prefectures for "all year / all day / all vehicles".
        let c = Conditions {
            targets: vec![
                block(|b| {
                    b.time_start = "0".into();
                    b.time_end = "2400".into();
                    b.vehicle_a = "1".into();
                    b.vehicle_b = "0".into();
                }),
                block(|b| {
                    b.period_start = "0101".into();
                    b.period_end = "1231".into();
                    b.weekday = "9".into();
                    b.vehicle_a = "10".into();
                }),
            ],
            exclusions: vec![block(|b| {
                b.time_start = "0".into();
                b.time_end = "0".into();
            })],
            note: String::new(),
        };
        assert!(c.applies(&at(3, 1, 3, 0, 0, false), CAR));
        assert!(!c.is_time_dependent());
    }

    #[test]
    fn time_window_wraps_midnight_and_is_half_open() {
        let c = Conditions {
            targets: vec![block(|b| {
                b.time_start = "2200".into();
                b.time_end = "600".into();
            })],
            ..Default::default()
        };
        assert!(c.applies(&at(1, 1, 23, 0, 0, false), CAR));
        assert!(c.applies(&at(1, 1, 5, 59, 0, false), CAR));
        assert!(!c.applies(&at(1, 1, 6, 0, 0, false), CAR));
        assert!(c.is_time_dependent());
    }

    #[test]
    fn period_wraps_new_year() {
        let c = Conditions {
            targets: vec![block(|b| {
                b.period_start = "1201".into();
                b.period_end = "331".into();
            })],
            ..Default::default()
        };
        assert!(c.applies(&at(12, 15, 12, 0, 0, false), CAR));
        assert!(c.applies(&at(3, 31, 12, 0, 0, false), CAR));
        assert!(!c.applies(&at(4, 1, 12, 0, 0, false), CAR));
    }

    #[test]
    fn weekday_codes() {
        let on = |code: &str, t: DriveTime| {
            Conditions {
                targets: vec![block(|b| b.weekday = code.into())],
                ..Default::default()
            }
            .applies(&t, CAR)
        };
        let (sat, sun, mon, mon_holiday) = (
            at(1, 6, 9, 0, 5, false),
            at(1, 7, 9, 0, 6, false),
            at(1, 8, 9, 0, 0, false),
            at(1, 8, 9, 0, 0, true),
        );
        assert!(on("1", sat) && on("1", sun) && !on("1", mon_holiday));
        assert!(on("2", mon_holiday) && !on("2", mon));
        assert!(on("3", sun) && on("3", mon_holiday) && !on("3", sat));
        assert!(on("4", sat) && !on("4", sun));
        assert!(on("5", sun) && !on("5", sat));
        assert!(on("6", mon_holiday) && !on("6", sun));
        assert!(on("99", mon)); // その他: no usable restriction
    }

    #[test]
    fn weekday_exclusion_means_weekdays_only() {
        let c = Conditions {
            targets: vec![block(|b| {
                b.time_start = "700".into();
                b.time_end = "900".into();
            })],
            exclusions: vec![block(|b| b.weekday = "2".into())],
            note: String::new(),
        };
        assert!(c.applies(&at(1, 8, 8, 0, 0, false), CAR));
        assert!(!c.applies(&at(1, 8, 8, 0, 0, true), CAR));
        assert!(!c.applies(&at(1, 6, 8, 0, 5, false), CAR));
    }

    #[test]
    fn vehicle_targets_and_exclusions() {
        let targets = |a: &str, b: &str, c: &str, d: &str| Conditions {
            targets: vec![block(|blk| {
                blk.vehicle_a = a.into();
                blk.vehicle_b = b.into();
                blk.vehicle_c = c.into();
                blk.vehicle_d = d.into();
            })],
            ..Default::default()
        };
        let t = DriveTime::REPRESENTATIVE;
        assert!(targets("1000", "", "", "").applies(&t, CAR)); // 普乗
        assert!(targets("10", "0", "1000000000", "1000").applies(&t, CAR)); // 自動車 + けん引 + 原付 (Shizuoka)
        assert!(!targets("100000", "", "", "").applies(&t, CAR)); // 中乗 only
        assert!(!targets("", "", "100000", "").applies(&t, CAR)); // 大貨 only
        assert!(!targets("", "", "", "1").applies(&t, CAR)); // 二輪 only
        assert!(targets("", "", "", "100000000000000").applies(&t, CAR)); // その他 only: applied

        let excluded = |a: &str, d: &str| Conditions {
            exclusions: vec![block(|blk| {
                blk.vehicle_a = a.into();
                blk.vehicle_d = d.into();
            })],
            ..Default::default()
        };
        assert!(!excluded("1000", "").applies(&t, CAR));
        assert!(excluded("", "100000000000000").applies(&t, CAR));
        assert!(excluded("100000", "").applies(&t, CAR));
    }
}
