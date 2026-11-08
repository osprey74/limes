#[test]
fn golden_decisions() {
    let failures = limes_core::golden::check(limes_core::golden::CASES).unwrap();
    assert!(failures.is_empty(), "{}", failures.join("\n"));
}
