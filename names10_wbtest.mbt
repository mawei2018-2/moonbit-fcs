///|
test "channel_index uses exact PnN identity across reordered data" {
  for
    (names, values, expected) in [
      (["FSC-A", "SSC-A", "0"], [20.0, 10.0, 7.0], 0),
      (["0", "SSC-A", "FSC-A"], [7.0, 10.0, 20.0], 2),
    ] {
    let d = parse(create(names, values))
    assert_eq(d.channel_index("FSC-A"), expected)
    assert_eq(d.value(0, d.channel_index("FSC-A")), 20.0)
    assert_eq(d.value(0, d.channel_index("0")), 7.0)
    let result = d.gate_plan([
      {
        id: "window",
        parent: None,
        predicate: Rectangle([
          { channel: d.channel_index("FSC-A"), lower: 15.0, upper: 35.0, },
        ]),
        scaled: false,
        compensated: false,
      },
    ])
    assert_eq(result[0].event_indices, [0])
    for missing in ["", "fsc-a", "missing"] {
      try d.channel_index(missing) catch {
        Invalid(_) => ()
        _ => fail("wrong missing-name error")
      } noraise {
        _ => fail("unknown name silently resolved")
      }
    }
  }
}

///|
test "ambiguous names fail without rejecting numeric access to compatible DATA" {
  let original = parse(create(["A", "B"], [1.0, 2.0]))
  let meta = original.keywords()
  put(meta, "$P2N", "A")
  let d = parse(assemble(meta, original.raw, []))
  assert_true(!d.warnings().is_empty())
  try d.channel_index("A") catch {
    Invalid(_) => ()
    _ => fail("wrong ambiguous-name error")
  } noraise {
    _ => fail("ambiguous name silently chose a channel")
  }
  assert_eq(d.value(0, 1), 2.0)
  assert_eq(
    d.gate_plan([
      {
        id: "numeric",
        parent: None,
        predicate: Rectangle([{ channel: 1, lower: 1.5, upper: 2.5, }]),
        scaled: false,
        compensated: false,
      },
    ])[0].event_indices,
    [0],
  )
}
