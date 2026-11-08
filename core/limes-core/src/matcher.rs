//! Map matching: which stored road segment a GPS fix is on.
//!
//! A segment qualifies when it lies within MAX_DISTANCE_M of the fix and, when
//! the heading is known (moving), its direction is within MAX_ANGLE_DEG of the
//! heading (either way on two-way roads, along the allowed direction on one-way
//! roads). Among qualifying segments the closest wins, with a bonus for staying
//! on the way matched last time so the result doesn't flicker at junctions and
//! along parallel roads. No qualifying segment means "unknown" (stage 8).

use crate::conditions::{DriveTime, Vehicle};
use crate::db::{Reader, Segment};
use crate::decide::{Decision, decide};

pub const MAX_DISTANCE_M: f64 = 20.0;
pub const MAX_ANGLE_DEG: f64 = 45.0;
/// Below this speed the heading is unreliable and is not used.
pub const MIN_SPEED_FOR_HEADING_MPS: f64 = 2.0;
/// Distance credit for the way matched on the previous fix.
pub const STICKINESS_M: f64 = 5.0;

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Fix {
    pub lon: f64,
    pub lat: f64,
    /// Degrees clockwise from north, if known.
    pub heading: Option<f64>,
    /// Meters per second, if known.
    pub speed_mps: Option<f64>,
}

/// Where segments come from (the prefecture databases, or a list in tests).
pub trait SegmentSource {
    fn segments_near(&self, lon: f64, lat: f64, radius_m: f64) -> Vec<Segment>;
}

impl SegmentSource for Reader {
    fn segments_near(&self, lon: f64, lat: f64, radius_m: f64) -> Vec<Segment> {
        let (dlon, dlat) = degrees(radius_m, lat);
        self.segments_in(lon - dlon, lat - dlat, lon + dlon, lat + dlat)
            .unwrap_or_default()
    }
}

impl<S: SegmentSource + ?Sized> SegmentSource for &S {
    fn segments_near(&self, lon: f64, lat: f64, radius_m: f64) -> Vec<Segment> {
        (**self).segments_near(lon, lat, radius_m)
    }
}

impl<S: SegmentSource> SegmentSource for [S] {
    fn segments_near(&self, lon: f64, lat: f64, radius_m: f64) -> Vec<Segment> {
        self.iter()
            .flat_map(|s| s.segments_near(lon, lat, radius_m))
            .collect()
    }
}

#[derive(Debug, Clone)]
pub struct Matched {
    pub segment: Segment,
    /// Decided now for the given time and vehicle.
    pub decision: Decision,
    pub distance_m: f64,
}

/// Keeps the previous match between fixes.
#[derive(Debug, Default)]
pub struct Matcher {
    last_osm_id: Option<i64>,
}

const METERS_PER_DEGREE_LAT: f64 = 110_540.0;
const METERS_PER_DEGREE_LON_EQUATOR: f64 = 111_320.0;

fn degrees(meters: f64, lat: f64) -> (f64, f64) {
    (
        meters / (METERS_PER_DEGREE_LON_EQUATOR * lat.to_radians().cos()),
        meters / METERS_PER_DEGREE_LAT,
    )
}

/// Distance in meters from the fix to the polyline, and the bearing (degrees
/// clockwise from north) of the closest piece.
fn nearest(coords: &[[f64; 2]], lon: f64, lat: f64) -> Option<(f64, f64)> {
    let kx = METERS_PER_DEGREE_LON_EQUATOR * lat.to_radians().cos();
    let to_m = |[x, y]: [f64; 2]| ((x - lon) * kx, (y - lat) * METERS_PER_DEGREE_LAT);
    coords
        .windows(2)
        .filter_map(|w| {
            let (a, b) = (to_m(w[0]), to_m(w[1]));
            let (dx, dy) = (b.0 - a.0, b.1 - a.1);
            let len2 = dx * dx + dy * dy;
            if len2 == 0.0 {
                return None;
            }
            let t = (-(a.0 * dx + a.1 * dy) / len2).clamp(0.0, 1.0);
            let (px, py) = (a.0 + t * dx, a.1 + t * dy);
            Some((
                (px * px + py * py).sqrt(),
                dx.atan2(dy).to_degrees().rem_euclid(360.0),
            ))
        })
        .min_by(|a, b| a.0.total_cmp(&b.0))
}

fn angle_between(a: f64, b: f64) -> f64 {
    let d = (a - b).rem_euclid(360.0);
    d.min(360.0 - d)
}

/// Heading difference allowed by the segment's direction of travel.
fn heading_gap(bearing: f64, oneway: i32, heading: f64) -> f64 {
    match oneway {
        1 => angle_between(bearing, heading),
        -1 => angle_between(bearing + 180.0, heading),
        _ => angle_between(bearing, heading).min(angle_between(bearing + 180.0, heading)),
    }
}

impl Matcher {
    pub fn new() -> Self {
        Self::default()
    }

    /// Match a fix; None means no road qualifies ("unknown"). The previous match
    /// is forgotten on a miss.
    pub fn locate<S: SegmentSource + ?Sized>(
        &mut self,
        source: &S,
        fix: &Fix,
        t: &DriveTime,
        vehicle: Vehicle,
    ) -> Option<Matched> {
        let heading = fix.heading.filter(|_| {
            fix.speed_mps
                .is_some_and(|v| v >= MIN_SPEED_FOR_HEADING_MPS)
        });
        let best = source
            .segments_near(fix.lon, fix.lat, MAX_DISTANCE_M)
            .into_iter()
            .filter_map(|s| {
                let (distance, bearing) = nearest(&s.coords, fix.lon, fix.lat)?;
                if distance > MAX_DISTANCE_M {
                    return None;
                }
                if let Some(h) = heading
                    && heading_gap(bearing, s.oneway, h) > MAX_ANGLE_DEG
                {
                    return None;
                }
                let bonus = if Some(s.osm_id) == self.last_osm_id {
                    STICKINESS_M
                } else {
                    0.0
                };
                Some((distance - bonus, distance, s))
            })
            .min_by(|a, b| a.0.total_cmp(&b.0));
        self.last_osm_id = best.as_ref().map(|(_, _, s)| s.osm_id);
        best.map(|(_, distance_m, segment)| Matched {
            decision: decide(&segment.evidence, t, vehicle),
            segment,
            distance_m,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::decide::{Confidence, Stage, WayEvidence};

    struct List(Vec<Segment>);

    impl SegmentSource for List {
        fn segments_near(&self, _: f64, _: f64, _: f64) -> Vec<Segment> {
            self.0.clone()
        }
    }

    fn segment(osm_id: i64, oneway: i32, highway: &str, coords: Vec<[f64; 2]>) -> Segment {
        let evidence = WayEvidence {
            osm_id,
            highway: highway.into(),
            ..Default::default()
        };
        let baked = decide(&evidence, &DriveTime::REPRESENTATIVE, Vehicle::OrdinaryCar);
        Segment {
            id: osm_id,
            osm_id,
            seq: 0,
            highway: highway.into(),
            name: String::new(),
            ref_: String::new(),
            oneway,
            coords,
            evidence,
            baked,
            time_dependent: false,
        }
    }

    // A north-south road and an east-west road crossing at 141.35, 43.09.
    fn crossing() -> List {
        List(vec![
            segment(
                1,
                0,
                "residential",
                vec![[141.35, 43.089], [141.35, 43.091]],
            ),
            segment(2, 0, "track", vec![[141.349, 43.09], [141.351, 43.09]]),
        ])
    }

    fn fix(dlon_m: f64, dlat_m: f64, heading: Option<f64>) -> Fix {
        let (kx, ky) = degrees(1.0, 43.09);
        Fix {
            lon: 141.35 + dlon_m * kx,
            lat: 43.09 + dlat_m * ky,
            heading,
            speed_mps: Some(10.0),
        }
    }

    fn locate(m: &mut Matcher, source: &List, f: Fix) -> Option<i64> {
        m.locate(source, &f, &DriveTime::REPRESENTATIVE, Vehicle::OrdinaryCar)
            .map(|x| x.segment.osm_id)
    }

    #[test]
    fn distance_limit_and_unknown() {
        let source = crossing();
        let mut m = Matcher::new();
        assert_eq!(locate(&mut m, &source, fix(5.0, 60.0, None)), Some(1));
        assert_eq!(locate(&mut m, &source, fix(25.0, 60.0, None)), None);
    }

    #[test]
    fn heading_picks_the_road_being_driven_at_a_junction() {
        let source = crossing();
        let mut m = Matcher::new();
        // 3 m from both roads: heading east means the east-west road.
        assert_eq!(locate(&mut m, &source, fix(3.0, 3.0, Some(85.0))), Some(2));
        let mut m = Matcher::new();
        assert_eq!(locate(&mut m, &source, fix(3.0, 3.0, Some(185.0))), Some(1));
        // Heading is ignored when nearly stopped.
        let slow = Fix {
            speed_mps: Some(0.5),
            ..fix(1.0, 8.0, Some(90.0))
        };
        assert_eq!(locate(&mut Matcher::new(), &source, slow), Some(1));
    }

    #[test]
    fn one_way_direction_counts() {
        let source = List(vec![segment(
            1,
            1,
            "primary",
            vec![[141.35, 43.089], [141.35, 43.091]],
        )]);
        assert_eq!(
            locate(&mut Matcher::new(), &source, fix(2.0, 0.0, Some(0.0))),
            Some(1)
        );
        assert_eq!(
            locate(&mut Matcher::new(), &source, fix(2.0, 0.0, Some(180.0))),
            None
        );
    }

    #[test]
    fn sticks_to_the_previous_way_on_parallel_roads() {
        // Two parallel roads 10 m apart.
        let (kx, _) = degrees(1.0, 43.09);
        let source = List(vec![
            segment(
                1,
                0,
                "residential",
                vec![[141.35, 43.089], [141.35, 43.091]],
            ),
            segment(
                2,
                0,
                "residential",
                vec![[141.35 + 10.0 * kx, 43.089], [141.35 + 10.0 * kx, 43.091]],
            ),
        ]);
        let mut m = Matcher::new();
        assert_eq!(locate(&mut m, &source, fix(2.0, 0.0, Some(0.0))), Some(1));
        // 6 m from road 1, 4 m from road 2: stays on road 1 thanks to the bonus.
        assert_eq!(locate(&mut m, &source, fix(6.0, 10.0, Some(0.0))), Some(1));
        assert_eq!(
            locate(&mut Matcher::new(), &source, fix(6.0, 10.0, Some(0.0))),
            Some(2)
        );
    }

    #[test]
    fn decision_is_made_for_the_given_time() {
        let mut s = segment(
            1,
            0,
            "residential",
            vec![[141.35, 43.089], [141.35, 43.091]],
        );
        s.evidence.regulations.push(crate::decide::SpeedRegulation {
            speed: 20,
            code: 112,
            key: String::new(),
            conditions: crate::conditions::Conditions {
                targets: vec![crate::conditions::RawBlock {
                    time_start: "700".into(),
                    time_end: "900".into(),
                    ..Default::default()
                }],
                ..Default::default()
            },
        });
        let source = List(vec![s]);
        let morning = DriveTime {
            minute_of_day: 8 * 60,
            ..DriveTime::REPRESENTATIVE
        };
        let got = Matcher::new()
            .locate(
                &source,
                &fix(1.0, 0.0, None),
                &morning,
                Vehicle::OrdinaryCar,
            )
            .unwrap();
        assert_eq!(
            (got.decision.speed, got.decision.stage),
            (20, Stage::Regulated)
        );
        let noon = Matcher::new()
            .locate(
                &source,
                &fix(1.0, 0.0, None),
                &DriveTime::REPRESENTATIVE,
                Vehicle::OrdinaryCar,
            )
            .unwrap();
        assert_eq!(
            (noon.decision.speed, noon.decision.confidence),
            (30, Confidence::Low)
        );
    }
}
