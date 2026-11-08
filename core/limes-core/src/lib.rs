//! Limes core: estimates the maximum speed of the road being driven from public
//! data (JARTIC traffic regulations, OpenStreetMap, GSI). Shared by the apps
//! (through limes-ffi) and the data pipeline (through limes-cli) so both decide
//! the same way.

pub mod conditions;
pub mod decide;
pub mod golden;

pub use conditions::{Conditions, DriveTime, RawBlock, Vehicle};
pub use decide::{
    CenterEvidence, Confidence, Decision, RoadType, SpeedRegulation, Stage, WayEvidence, decide,
};
