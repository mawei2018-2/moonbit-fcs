///|
test "compensation overflow recovery matches complete independent binary64 files" {
  let sources = compensation_overflow_fixtures()
  let expected = compensation_overflow_expected_bits()
  for i in 0..<sources.length() {
    let d = parse(sources[i].1)
    let actual = Array::makei(d.events, event => {
      Array::makei(d.channel_info().length(), channel => {
        let value = d.value(event, channel, compensated=true)
        if value != value {
          "NaN"
        } else {
          value.reinterpret_as_uint64().to_string()
        }
      })
    })
    assert_eq(actual, expected[i])
  }
}

///|
test "compensated recovered events reach complete forward Boolean plans" {
  let d = parse(compensation_overflow_fixtures()[0].1)
  let populations = d.gate_plan([
    GateStep::{
      id: "zero",
      parent: Some("finite"),
      predicate: Rectangle([{ channel: 1, lower: -0.5, upper: 0.5, }]),
      scaled: false,
      compensated: true,
    },
    GateStep::{
      id: "rest",
      parent: Some("finite"),
      predicate: Not("zero"),
      scaled: false,
      compensated: false,
    },
    GateStep::{
      id: "finite",
      parent: None,
      predicate: Rectangle([{ channel: 1, lower: -1.0, upper: 7.0, }]),
      scaled: false,
      compensated: true,
    },
    GateStep::{
      id: "either",
      parent: None,
      predicate: AnyOf(["zero", "rest"]),
      scaled: false,
      compensated: false,
    },
  ])
  assert_eq(populations.map(p => p.event_indices), [
    [0, 1, 4],
    [2],
    [0, 1, 2, 4],
    [0, 1, 2, 4],
  ])
  assert_eq(populations[0].parent_count, 4)
  assert_eq(populations[0].parent_fraction, Some(0.75))
  assert_eq(populations[2].total_count, 7)
}

///|
test "compensation recovery keeps original raw observations and analysis" {
  let original = compensation_overflow_fixtures()[0].1
  let d = parse(original)
  let raw_bits = d.value(0, 1).reinterpret_as_uint64()
  assert_eq(d.value(0, 1, compensated=true), 0.0)
  assert_eq(d.value(0, 1).reinterpret_as_uint64(), raw_bits)
  assert_eq(d.analysis_keywords(), [
    ("NOTE", "original analysis is preserved in input"),
  ])
  let selected = parse(
    d.write(
      event_indices=[0, 1, 2, 4],
      channel_indices=[2, 1],
      drop_analysis=true,
      drop_spillover=true,
    ),
  )
  assert_eq(selected.value(0, 1).reinterpret_as_uint64(), raw_bits)
  assert_eq(selected.value(1, 0), 1.0)
  assert_eq(selected.analysis_keywords(), [])
  assert_eq(parse(original).value(0, 1).reinterpret_as_uint64(), raw_bits)
}
