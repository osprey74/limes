//! The computed holidays match the Cabinet Office list for 2000-2027.

use std::collections::BTreeSet;

use limes_core::holiday;

#[test]
fn matches_cabinet_office_list() {
    let expected: BTreeSet<(i32, u32, u32)> = include_str!("golden/holidays.txt")
        .lines()
        .filter(|l| !l.starts_with('#') && !l.trim().is_empty())
        .map(|l| {
            let mut p = l.trim().split('-').map(|v| v.parse::<u32>().unwrap());
            let (y, m, d) = (p.next().unwrap(), p.next().unwrap(), p.next().unwrap());
            (y as i32, m, d)
        })
        .collect();
    let computed: BTreeSet<(i32, u32, u32)> = (2000..=2027)
        .flat_map(|y| {
            holiday::holidays(y)
                .into_iter()
                .map(move |(m, d)| (y, m, d))
        })
        .collect();
    let missing: Vec<_> = expected.difference(&computed).collect();
    let extra: Vec<_> = computed.difference(&expected).collect();
    assert!(
        missing.is_empty() && extra.is_empty(),
        "missing {missing:?}, extra {extra:?}"
    );
}
