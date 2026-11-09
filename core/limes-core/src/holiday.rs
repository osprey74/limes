//! Japanese public holidays (国民の祝日に関する法律), for regulations that
//! apply on Sundays and holidays.
//!
//! Computed from the rules in force since 2000: fixed days, Happy Monday
//! days, the equinoxes, the 2019 enthronement days, the 2020/2021 Olympic
//! moves, 国民の休日 (a day between two holidays) and 振替休日 (a holiday on
//! a Sunday moves to the next working day; before 2007, to the Monday).
//! Checked against the Cabinet Office list for 2000-2027
//! (tests/golden/holidays.txt). Years before 2000 are not supported.

/// Days since 1970-01-01 (H. Hinnant's days_from_civil).
fn days_from_civil(year: i32, month: u32, day: u32) -> i64 {
    let y = i64::from(if month <= 2 { year - 1 } else { year });
    let era = y.div_euclid(400);
    let yoe = y - era * 400;
    let m = i64::from(month);
    let doy = (153 * (if m > 2 { m - 3 } else { m + 9 }) + 2) / 5 + i64::from(day) - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146_097 + doe - 719_468
}

/// 0 = Monday ... 6 = Sunday (1970-01-01 was a Thursday).
pub fn weekday(year: i32, month: u32, day: u32) -> u8 {
    (days_from_civil(year, month, day) + 3).rem_euclid(7) as u8
}

fn days_in_month(year: i32, month: u32) -> u32 {
    match month {
        2 if year % 4 == 0 && (year % 100 != 0 || year % 400 == 0) => 29,
        2 => 28,
        4 | 6 | 9 | 11 => 30,
        _ => 31,
    }
}

/// Day of the month of the `n`th Monday.
fn nth_monday(year: i32, month: u32, n: u32) -> u32 {
    let first = u32::from(weekday(year, month, 1));
    1 + (7 - first) % 7 + 7 * (n - 1)
}

/// Equinox days by the usual approximation (valid 1980-2099).
fn equinox(year: i32, base: f64) -> u32 {
    let y = f64::from(year - 1980);
    (base + 0.242_194 * y - (y / 4.0).floor()).floor() as u32
}

/// The national holidays (祝日) of a year as (month, day), before 国民の休日
/// and 振替休日 are added.
fn national(year: i32) -> Vec<(u32, u32)> {
    let mut days = vec![
        (1, 1),
        (1, nth_monday(year, 1, 2)), // 成人の日
        (2, 11),                     // 建国記念の日
        (3, equinox(year, 20.8431)), // 春分の日
        (4, 29),                     // みどりの日, 昭和の日 from 2007
        (5, 3),
        (5, 5),
        (9, equinox(year, 23.2488)), // 秋分の日
        (11, 3),
        (11, 23),
    ];
    if year >= 2007 {
        days.push((5, 4)); // みどりの日
    }
    // 天皇誕生日
    match year {
        ..=2018 => days.push((12, 23)),
        2019 => {}
        _ => days.push((2, 23)),
    }
    // 海の日, スポーツの日 (体育の日), 山の日, with the Olympic moves.
    match year {
        2020 => days.extend([(7, 23), (7, 24), (8, 10)]),
        2021 => days.extend([(7, 22), (7, 23), (8, 8)]),
        _ => {
            days.push(if year >= 2003 {
                (7, nth_monday(year, 7, 3))
            } else {
                (7, 20)
            });
            days.push((10, nth_monday(year, 10, 2)));
            if year >= 2016 {
                days.push((8, 11));
            }
        }
    }
    // 敬老の日
    days.push(if year >= 2003 {
        (9, nth_monday(year, 9, 3))
    } else {
        (9, 15)
    });
    if year == 2019 {
        days.extend([(5, 1), (10, 22)]); // 即位の日, 即位礼正殿の儀
    }
    days
}

/// All holidays of a year, sorted: national ones, 国民の休日 and 振替休日.
pub fn holidays(year: i32) -> Vec<(u32, u32)> {
    let base = national(year);
    let is_base = |m: u32, d: u32| base.contains(&(m, d));
    let next = |m: u32, d: u32| {
        if d < days_in_month(year, m) {
            (m, d + 1)
        } else {
            (m + 1, 1)
        }
    };
    let mut all = base.clone();

    // 国民の休日: a day between two national holidays, also across a month
    // end (2019-04-30). Before 2007 a Sunday stayed a Sunday.
    let dates: Vec<(u32, u32)> = (1..=12)
        .flat_map(|m| (1..=days_in_month(year, m)).map(move |d| (m, d)))
        .collect();
    for w in dates.windows(3) {
        let (m, d) = w[1];
        if !is_base(m, d)
            && is_base(w[0].0, w[0].1)
            && is_base(w[2].0, w[2].1)
            && (year >= 2007 || weekday(year, m, d) != 6)
        {
            all.push((m, d));
        }
    }
    // 振替休日
    for &(m, d) in &base {
        if weekday(year, m, d) != 6 {
            continue;
        }
        let mut day = next(m, d);
        if year >= 2007 {
            while all.contains(&day) {
                day = next(day.0, day.1);
            }
        }
        if !all.contains(&day) {
            all.push(day);
        }
    }
    all.sort_unstable();
    all.dedup();
    all
}

pub fn is_holiday(year: i32, month: u32, day: u32) -> bool {
    holidays(year).contains(&(month, day))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn weekdays() {
        assert_eq!(weekday(1970, 1, 1), 3); // Thursday
        assert_eq!(weekday(2026, 11, 9), 0); // Monday
        assert_eq!(weekday(2000, 2, 29), 1); // Tuesday
    }

    #[test]
    fn rules_in_recent_years() {
        // 2026: 振替休日 for 5/3 (Sunday) falls on 5/6 past 5/4 and 5/5;
        // 9/22 is 国民の休日 between 敬老の日 (9/21) and 秋分の日 (9/23).
        let h = holidays(2026);
        assert!(h.contains(&(5, 6)));
        assert!(h.contains(&(9, 22)));
        assert!(!is_holiday(2026, 11, 9));
        // 2019: 4/30 and 5/2 between the enthronement and its neighbours.
        assert!(is_holiday(2019, 4, 30) && is_holiday(2019, 5, 1) && is_holiday(2019, 5, 2));
        assert!(!is_holiday(2019, 12, 23));
    }
}
