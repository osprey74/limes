//! Speed-line vector tiles (Mapbox Vector Tile 2.1 in PMTiles v3) from a
//! prefecture database, for the speed map.
//!
//! One layer, `speed`, with the decision baked at build time: `speed`, `conf`
//! (high/mid/low), `class` (road class for line width) and `td` = 1 when the
//! speed depends on date or time. Consecutive segments with the same
//! properties are joined into one line and carry no id: the app finds the
//! segment under a tap in its own database. Roads appear from a zoom set by
//! their class (major roads in wide views, local roads only when zoomed in);
//! lines are simplified to about half a pixel at each zoom and clipped to the
//! tile plus a buffer.

use std::collections::HashMap;
use std::f64::consts::PI;
use std::fs::File;
use std::io::BufWriter;
use std::path::Path;

use limes_core::Confidence;
use limes_core::db::{BakedSegment, Reader};
use pmtiles::{PmTilesWriter, TileCoord, TileId, TileType};

pub const LAYER: &str = "speed";
pub const MIN_ZOOM: u8 = 5;
pub const MAX_ZOOM: u8 = 14;
const EXTENT: u32 = 4096;
/// Tile buffer in tile units (8 px of a 512 px tile), so line joins and caps
/// at tile edges render without gaps.
const BUFFER: f64 = 64.0;
/// Douglas-Peucker tolerance in tile units: half a pixel of a 512 px tile,
/// and at the highest zoom (overzoomed beyond it) about 1 m.
const TOLERANCE: f64 = 4.0;
const MAX_ZOOM_TOLERANCE: f64 = 2.0;
const KEYS: [&str; 4] = ["speed", "conf", "class", "td"];

/// Road class for styling and the first zoom it is drawn at; None leaves the
/// road out of the tiles.
pub fn road_class(highway: &str) -> Option<(&'static str, u8)> {
    let (base, link) = match highway.strip_suffix("_link") {
        Some(base) => (base, true),
        None => (highway, false),
    };
    let (class, zoom) = match base {
        "motorway" => ("motorway", 5),
        "trunk" => ("trunk", 6),
        "primary" => ("primary", 8),
        "secondary" => ("secondary", 9),
        "tertiary" => ("tertiary", 10),
        "unclassified" | "residential" | "living_street" | "road" => ("minor", 12),
        "service" => ("service", 14),
        _ => return None,
    };
    Some((class, if link { zoom.max(10) } else { zoom }))
}

/// Web Mercator position in [0, 1].
fn project([lon, lat]: [f64; 2]) -> [f64; 2] {
    let x = (lon + 180.0) / 360.0;
    let y = (1.0 - lat.to_radians().tan().asinh() / PI) / 2.0;
    [x, y]
}

fn douglas_peucker(points: &[[f64; 2]], tolerance: f64) -> Vec<[f64; 2]> {
    if points.len() < 3 {
        return points.to_vec();
    }
    let mut keep = vec![false; points.len()];
    keep[0] = true;
    keep[points.len() - 1] = true;
    let mut stack = vec![(0, points.len() - 1)];
    while let Some((first, last)) = stack.pop() {
        let (a, b) = (points[first], points[last]);
        let (dx, dy) = (b[0] - a[0], b[1] - a[1]);
        let len2 = dx * dx + dy * dy;
        let mut farthest = (0.0, first);
        for (i, p) in points.iter().enumerate().take(last).skip(first + 1) {
            let d2 = if len2 == 0.0 {
                (p[0] - a[0]).powi(2) + (p[1] - a[1]).powi(2)
            } else {
                let t = (((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2).clamp(0.0, 1.0);
                (p[0] - a[0] - t * dx).powi(2) + (p[1] - a[1] - t * dy).powi(2)
            };
            if d2 > farthest.0 {
                farthest = (d2, i);
            }
        }
        if farthest.0 > tolerance * tolerance {
            keep[farthest.1] = true;
            stack.push((first, farthest.1));
            stack.push((farthest.1, last));
        }
    }
    points
        .iter()
        .zip(keep)
        .filter_map(|(p, k)| k.then_some(*p))
        .collect()
}

/// Liang-Barsky: the part of segment a-b inside the box, as parameters t0..t1.
fn clip_segment(a: [f64; 2], b: [f64; 2], min: [f64; 2], max: [f64; 2]) -> Option<(f64, f64)> {
    let (mut t0, mut t1) = (0.0_f64, 1.0_f64);
    let d = [b[0] - a[0], b[1] - a[1]];
    for axis in 0..2 {
        for (p, q) in [
            (-d[axis], a[axis] - min[axis]),
            (d[axis], max[axis] - a[axis]),
        ] {
            if p == 0.0 {
                if q < 0.0 {
                    return None;
                }
            } else {
                let r = q / p;
                if p < 0.0 {
                    t0 = t0.max(r);
                } else {
                    t1 = t1.min(r);
                }
            }
        }
    }
    (t0 <= t1).then_some((t0, t1))
}

/// The pieces of a line inside the box.
pub fn clip_line(points: &[[f64; 2]], min: [f64; 2], max: [f64; 2]) -> Vec<Vec<[f64; 2]>> {
    let lerp =
        |a: [f64; 2], b: [f64; 2], t: f64| [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
    let mut pieces: Vec<Vec<[f64; 2]>> = Vec::new();
    let mut current: Vec<[f64; 2]> = Vec::new();
    for w in points.windows(2) {
        let (a, b) = (w[0], w[1]);
        match clip_segment(a, b, min, max) {
            Some((t0, t1)) => {
                let (p0, p1) = (lerp(a, b, t0), lerp(a, b, t1));
                if current.is_empty() || t0 > 0.0 {
                    if current.len() > 1 {
                        pieces.push(std::mem::take(&mut current));
                    }
                    current = vec![p0];
                }
                current.push(p1);
                if t1 < 1.0 {
                    pieces.push(std::mem::take(&mut current));
                }
            }
            None => {
                if current.len() > 1 {
                    pieces.push(std::mem::take(&mut current));
                } else {
                    current.clear();
                }
            }
        }
    }
    if current.len() > 1 {
        pieces.push(current);
    }
    pieces
}

// --- MVT encoding --------------------------------------------------------

fn varint(out: &mut Vec<u8>, mut v: u64) {
    while v >= 0x80 {
        out.push((v as u8) | 0x80);
        v >>= 7;
    }
    out.push(v as u8);
}

fn key(out: &mut Vec<u8>, field: u32, wire: u32) {
    varint(out, u64::from(field << 3 | wire));
}

fn bytes(out: &mut Vec<u8>, field: u32, data: &[u8]) {
    key(out, field, 2);
    varint(out, data.len() as u64);
    out.extend_from_slice(data);
}

fn zigzag(v: i32) -> u32 {
    ((v << 1) ^ (v >> 31)) as u32
}

#[derive(Clone, PartialEq, Eq, Hash)]
enum Value {
    Str(&'static str),
    Uint(u64),
}

#[derive(Default)]
struct TileBuilder {
    features: Vec<u8>,
    values: Vec<Value>,
    index: HashMap<Value, u32>,
}

impl TileBuilder {
    fn value(&mut self, v: Value) -> u32 {
        if let Some(&i) = self.index.get(&v) {
            return i;
        }
        let i = self.values.len() as u32;
        self.values.push(v.clone());
        self.index.insert(v, i);
        i
    }

    fn add(&mut self, props: &[(usize, Value)], lines: &[Vec<[i32; 2]>]) {
        let mut tags = Vec::new();
        for (k, v) in props {
            varint(&mut tags, *k as u64);
            let i = self.value(v.clone());
            varint(&mut tags, u64::from(i));
        }
        let mut geometry = Vec::new();
        let mut cursor = [0i32; 2];
        for line in lines {
            varint(&mut geometry, 1 | 1 << 3); // MoveTo, 1 point
            for (n, p) in line.iter().enumerate() {
                if n == 1 {
                    varint(&mut geometry, u64::from(2 | ((line.len() as u32 - 1) << 3))); // LineTo
                }
                varint(&mut geometry, u64::from(zigzag(p[0] - cursor[0])));
                varint(&mut geometry, u64::from(zigzag(p[1] - cursor[1])));
                cursor = *p;
            }
        }
        let mut feature = Vec::new();
        bytes(&mut feature, 2, &tags);
        key(&mut feature, 3, 0);
        varint(&mut feature, 2); // LINESTRING
        bytes(&mut feature, 4, &geometry);
        bytes(&mut self.features, 2, &feature);
    }

    fn encode(&self) -> Vec<u8> {
        let mut layer = Vec::new();
        key(&mut layer, 15, 0);
        varint(&mut layer, 2);
        bytes(&mut layer, 1, LAYER.as_bytes());
        layer.extend_from_slice(&self.features);
        for k in KEYS {
            bytes(&mut layer, 3, k.as_bytes());
        }
        for v in &self.values {
            let mut value = Vec::new();
            match v {
                Value::Str(s) => bytes(&mut value, 1, s.as_bytes()),
                Value::Uint(u) => {
                    key(&mut value, 5, 0);
                    varint(&mut value, *u);
                }
            }
            bytes(&mut layer, 4, &value);
        }
        key(&mut layer, 5, 0);
        varint(&mut layer, u64::from(EXTENT));
        let mut tile = Vec::new();
        bytes(&mut tile, 3, &layer);
        tile
    }
}

// --- tiling --------------------------------------------------------------

#[derive(Clone)]
struct Road {
    class: &'static str,
    min_zoom: u8,
    speed: u16,
    confidence: &'static str,
    time_dependent: bool,
    /// Web Mercator in [0, 1].
    points: Vec<[f64; 2]>,
}

fn confidence_str(c: Confidence) -> &'static str {
    match c {
        Confidence::High => "high",
        Confidence::Mid => "mid",
        Confidence::Low => "low",
    }
}

/// Joins each road to the previous one when it continues it (same properties,
/// starting where the previous one ends). Segments of one OSM way are stored
/// consecutively, so this restores ways split only by length.
fn chain(roads: &[Road]) -> Vec<Road> {
    let mut out: Vec<Road> = Vec::new();
    for road in roads {
        if let Some(prev) = out.last_mut()
            && (
                prev.class,
                prev.min_zoom,
                prev.speed,
                prev.confidence,
                prev.time_dependent,
            ) == (
                road.class,
                road.min_zoom,
                road.speed,
                road.confidence,
                road.time_dependent,
            )
            && prev.points.last() == road.points.first()
        {
            prev.points.extend_from_slice(&road.points[1..]);
            continue;
        }
        out.push(road.clone());
    }
    out
}

/// Encoded tiles of one zoom, in tile id order.
fn zoom_tiles(roads: &[Road], z: u8, max_zoom: u8) -> Vec<(TileCoord, Vec<u8>)> {
    let scale = f64::from(1u32 << z) * f64::from(EXTENT);
    let last = (1u32 << z) - 1;
    let mut tiles: HashMap<(u32, u32), TileBuilder> = HashMap::new();
    for road in roads.iter().filter(|r| r.min_zoom <= z) {
        let points: Vec<[f64; 2]> = road
            .points
            .iter()
            .map(|p| [p[0] * scale, p[1] * scale])
            .collect();
        let tolerance = if z < max_zoom {
            TOLERANCE
        } else {
            MAX_ZOOM_TOLERANCE
        };
        let points = douglas_peucker(&points, tolerance);
        let (mut min, mut max) = ([f64::MAX; 2], [f64::MIN; 2]);
        for p in &points {
            for a in 0..2 {
                min[a] = min[a].min(p[a]);
                max[a] = max[a].max(p[a]);
            }
        }
        let e = f64::from(EXTENT);
        let tile_range = |lo: f64, hi: f64| {
            let first = ((lo - BUFFER) / e).floor().max(0.0) as u32;
            let end = (((hi + BUFFER) / e).floor().max(0.0) as u32).min(last);
            first..=end
        };
        let mut props = vec![
            (0, Value::Uint(u64::from(road.speed))),
            (1, Value::Str(road.confidence)),
            (2, Value::Str(road.class)),
        ];
        if road.time_dependent {
            props.push((3, Value::Uint(1)));
        }
        for tx in tile_range(min[0], max[0]) {
            for ty in tile_range(min[1], max[1]) {
                let origin = [f64::from(tx) * e, f64::from(ty) * e];
                let lo = [origin[0] - BUFFER, origin[1] - BUFFER];
                let hi = [origin[0] + e + BUFFER, origin[1] + e + BUFFER];
                let lines: Vec<Vec<[i32; 2]>> = clip_line(&points, lo, hi)
                    .into_iter()
                    .map(|piece| {
                        let mut line: Vec<[i32; 2]> = piece
                            .iter()
                            .map(|p| {
                                [
                                    (p[0] - origin[0]).round() as i32,
                                    (p[1] - origin[1]).round() as i32,
                                ]
                            })
                            .collect();
                        line.dedup();
                        line
                    })
                    .filter(|line| line.len() > 1)
                    .collect();
                if !lines.is_empty() {
                    tiles.entry((tx, ty)).or_default().add(&props, &lines);
                }
            }
        }
    }
    let mut out: Vec<(TileCoord, Vec<u8>)> = tiles
        .into_iter()
        .map(|((x, y), b)| (TileCoord::new(z, x, y).expect("tile in range"), b.encode()))
        .collect();
    out.sort_by_key(|(c, _)| TileId::from(*c).value());
    out
}

pub struct Summary {
    /// Segments drawn, and the lines they were joined into.
    pub segments: usize,
    pub lines: usize,
    pub tiles: usize,
    pub bytes: u64,
}

pub fn write(db: &Path, out: &Path, min_zoom: u8, max_zoom: u8) -> Result<Summary, String> {
    let reader = Reader::open(db).map_err(|e| format!("{}: {e}", db.display()))?;
    let meta = |k: &str| reader.meta(k).map_err(|e| e.to_string());
    let (prefecture, version) = (meta("prefecture")?, meta("version")?);
    let (jartic_month, osm_date) = (meta("jartic_month")?, meta("osm_date")?);
    let mut roads = Vec::new();
    let (mut min, mut max) = ([f64::MAX; 2], [f64::MIN; 2]);
    reader
        .for_each_baked(|s: BakedSegment| {
            let Some((class, zoom)) = road_class(&s.highway) else {
                return;
            };
            for p in &s.coords {
                for a in 0..2 {
                    min[a] = min[a].min(p[a]);
                    max[a] = max[a].max(p[a]);
                }
            }
            roads.push(Road {
                class,
                min_zoom: zoom,
                speed: s.speed,
                confidence: confidence_str(s.confidence),
                time_dependent: s.time_dependent,
                points: s.coords.iter().copied().map(project).collect(),
            });
        })
        .map_err(|e| e.to_string())?;
    drop(reader);
    if roads.is_empty() {
        return Err(format!("{}: no roads to draw", db.display()));
    }

    let metadata = serde_json::json!({
        "name": format!("limes-speed-{}", prefecture.as_deref().unwrap_or("unknown")),
        "description": "Estimated maximum speed per road segment (Limes)",
        "version": version,
        "jartic_month": jartic_month,
        "osm_date": osm_date,
        "attribution": "出典：『交通規制情報』（公益財団法人日本道路交通情報センター）（https://www.jartic.or.jp/service/opendata/）を加工して作成 / © OpenStreetMap contributors (ODbL)",
        "vector_layers": [{
            "id": LAYER,
            "minzoom": min_zoom,
            "maxzoom": max_zoom,
            "fields": {"speed": "Number", "conf": "String", "class": "String", "td": "Number"},
        }],
    });
    let center = [(min[0] + max[0]) / 2.0, (min[1] + max[1]) / 2.0];
    let file = BufWriter::new(File::create(out).map_err(|e| format!("{}: {e}", out.display()))?);
    let mut writer = PmTilesWriter::new(TileType::Mvt)
        .min_zoom(min_zoom)
        .max_zoom(max_zoom)
        .bounds(min[0], min[1], max[0], max[1])
        .center(center[0], center[1])
        .center_zoom(min_zoom.max(8).min(max_zoom))
        .metadata(metadata.to_string())
        .create(file)
        .map_err(|e| e.to_string())?;
    let segments = roads.len();
    let roads = chain(&roads);
    let mut tiles = 0;
    for z in min_zoom..=max_zoom {
        let encoded = zoom_tiles(&roads, z, max_zoom);
        let bytes: usize = encoded.iter().map(|(_, t)| t.len()).sum();
        eprintln!(
            "  z{z:<2} {:>7} tiles {:>9.1} MB raw",
            encoded.len(),
            bytes as f64 / 1e6
        );
        tiles += encoded.len();
        for (coord, data) in encoded {
            writer.add_tile(coord, &data).map_err(|e| e.to_string())?;
        }
    }
    writer.finalize().map_err(|e| e.to_string())?;
    Ok(Summary {
        segments,
        lines: roads.len(),
        tiles,
        bytes: std::fs::metadata(out).map_err(|e| e.to_string())?.len(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn classes_and_zooms() {
        assert_eq!(road_class("motorway"), Some(("motorway", 5)));
        assert_eq!(road_class("motorway_link"), Some(("motorway", 10)));
        assert_eq!(road_class("tertiary_link"), Some(("tertiary", 10)));
        assert_eq!(road_class("residential"), Some(("minor", 12)));
        assert_eq!(road_class("service"), Some(("service", 14)));
        assert_eq!(road_class("footway"), None);
    }

    #[test]
    fn projection_corners() {
        assert_eq!(project([-180.0, 0.0]), [0.0, 0.5]);
        let [x, y] = project([180.0, 85.051_128_78]);
        assert!((x - 1.0).abs() < 1e-12 && y.abs() < 1e-9);
    }

    #[test]
    fn simplify_drops_points_within_tolerance() {
        let line = [[0.0, 0.0], [5.0, 1.0], [10.0, 0.0], [10.0, 10.0]];
        assert_eq!(
            douglas_peucker(&line, 2.0),
            vec![[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]]
        );
        assert_eq!(douglas_peucker(&line, 0.5), line.to_vec());
    }

    #[test]
    fn clip_splits_a_line_leaving_and_reentering() {
        // In, out across the right edge, back in.
        let line = [[1.0, 1.0], [3.0, 1.0], [3.0, 3.0], [1.0, 3.0]];
        let pieces = clip_line(&line, [0.0, 0.0], [2.0, 4.0]);
        assert_eq!(
            pieces,
            vec![vec![[1.0, 1.0], [2.0, 1.0]], vec![[2.0, 3.0], [1.0, 3.0]]]
        );
        assert!(clip_line(&[[5.0, 5.0], [6.0, 6.0]], [0.0, 0.0], [2.0, 2.0]).is_empty());
        // Passing straight through.
        assert_eq!(
            clip_line(&[[-1.0, 1.0], [3.0, 1.0]], [0.0, 0.0], [2.0, 2.0]),
            vec![vec![[0.0, 1.0], [2.0, 1.0]]]
        );
    }

    #[test]
    fn mvt_geometry_and_values() {
        let mut b = TileBuilder::default();
        let props = [(0, Value::Uint(60)), (1, Value::Str("mid"))];
        b.add(&props, &[vec![[2, 2], [2, 10], [10, 10]]]);
        b.add(&props, &[vec![[0, 0], [1, 0]]]);
        assert_eq!(b.values.len(), 2); // shared between the features
        let tile = b.encode();
        // MoveTo(1) +2,+2 then LineTo(2) 0,+8 +8,0, zigzag encoded.
        let geometry = [9u8, 4, 4, 18, 0, 16, 16, 0];
        assert!(tile.windows(geometry.len()).any(|w| w == geometry));
        assert!(tile.windows(5).any(|w| w == b"speed"));
    }

    #[test]
    fn chain_joins_continuing_segments_only() {
        let road = |speed, points: Vec<[f64; 2]>| Road {
            class: "primary",
            min_zoom: 8,
            speed,
            confidence: "high",
            time_dependent: false,
            points,
        };
        let joined = chain(&[
            road(60, vec![[0.0, 0.0], [1.0, 0.0]]),
            road(60, vec![[1.0, 0.0], [2.0, 0.0]]),
            road(40, vec![[2.0, 0.0], [3.0, 0.0]]),
            road(40, vec![[5.0, 0.0], [6.0, 0.0]]),
        ]);
        let lines: Vec<_> = joined.iter().map(|r| (r.speed, r.points.len())).collect();
        assert_eq!(lines, [(60, 3), (40, 2), (40, 2)]);
    }
}
