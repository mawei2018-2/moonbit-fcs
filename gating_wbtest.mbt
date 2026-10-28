///|
fn gate09_step(
  id : String,
  parent : String?,
  predicate : GatePredicate,
  scaled? : Bool = false,
  compensated? : Bool = false,
) -> GateStep {
  { id, parent, predicate, scaled, compensated, }
}

///|
test "named gate plans retain original indices across forward parents and branches" {
  let d = parse(
    create(
      ["X", "Y", "M", "ID"],
      [],
      integer_values=[
        "10", "1", "0", "18446744073709551616", "20", "2", "5", "18446744073709551617",
        "30", "3", "9", "18446744073709551618", "40", "4", "9", "18446744073709551619",
        "50", "5", "2", "18446744073709551620", "20", "4", "8", "18446744073709551621",
      ],
      encoding={ kind: Integer, widths: [8, 8, 8, 65], order: BigEndian, },
    ),
  )
  let steps = [
    gate09_step(
      "id_window",
      Some("shape"),
      Exact([
        {
          channel: 3,
          lower: "18446744073709551618",
          upper: "18446744073709551622",
        },
      ]),
    ),
    gate09_step(
      "high",
      Some("window"),
      Rectangle([{ channel: 2, lower: 8.0, upper: 10.0, }]),
    ),
    gate09_step(
      "window",
      None,
      Rectangle([{ channel: 0, lower: 15.0, upper: 45.0, }]),
    ),
    gate09_step(
      "shape",
      Some("window"),
      Polygon(0, 1, [(15.0, 0.0), (35.0, 0.0), (35.0, 5.0), (15.0, 5.0)]),
    ),
    gate09_step(
      "low",
      Some("window"),
      Rectangle([{ channel: 2, lower: 0.0, upper: 6.0, }]),
    ),
  ]
  let results = d.gate_plan(steps)
  assert_eq(results.map(p => p.id), [
    "id_window", "high", "window", "shape", "low",
  ])
  assert_eq(results.map(p => p.event_indices), [
    [2, 5],
    [2, 3, 5],
    [1, 2, 3, 5],
    [1, 2, 5],
    [1],
  ])
  assert_eq(results.map(p => p.parent_count), [3, 4, 6, 4, 4])
  assert_eq(results.map(p => p.count), [2, 3, 4, 3, 1])
  assert_eq(results[0].parent_fraction, Some(2.0 / 3.0))
  assert_eq(results[0].total_fraction, Some(2.0 / 6.0))
  let selected = parse(d.write(event_indices=results[0].event_indices))
  assert_eq(selected.integer_text(1, 3), "18446744073709551621")
}

///|
test "empty parent and empty DATA have explicit zero denominators" {
  let steps = [
    gate09_step(
      "parent",
      None,
      Rectangle([{ channel: 0, lower: 10.0, upper: 20.0, }]),
    ),
    gate09_step(
      "child",
      Some("parent"),
      Rectangle([{ channel: 0, lower: 0.0, upper: 5.0, }]),
    ),
  ]
  let d = parse(create(["A"], [1.0, 2.0]))
  assert_eq(d.gate_plan([]).length(), 0)
  let r = d.gate_plan(steps)
  assert_eq(r[0].parent_fraction, Some(0.0))
  assert_eq(r[1].parent_count, 0)
  assert_eq(r[1].parent_fraction, None)
  assert_eq(r[1].total_fraction, Some(0.0))
  let empty = parse(create(["A"], []))
  for p in empty.gate_plan(steps) {
    assert_eq(p.event_indices, [])
    assert_eq(p.total_count, 0)
    assert_eq(p.parent_fraction, None)
    assert_eq(p.total_fraction, None)
  }
  let invalid_child = [
    steps[0],
    gate09_step(
      "bad",
      Some("parent"),
      Rectangle([{ channel: 99, lower: 0.0, upper: 1.0, }]),
    ),
  ]
  try d.gate_plan(invalid_child) catch {
    Invalid(_) => ()
    _ => fail("wrong gate error")
  } noraise {
    _ => fail("empty parent hid invalid channel")
  }
}

///|
test "gate plan rejects duplicate IDs unknown parents and cycles" {
  let d = parse(create(["A"], [1.0]))
  let predicate = Rectangle([{ channel: 0, lower: 0.0, upper: 2.0, }])
  for
    steps in [
      [gate09_step("", None, predicate)],
      [
        gate09_step("same", None, predicate),
        gate09_step("same", None, predicate),
      ],
      [gate09_step("orphan", Some("missing"), predicate)],
      [gate09_step("self", Some("self"), predicate)],
      [
        gate09_step("a", Some("b"), predicate),
        gate09_step("b", Some("a"), predicate),
      ],
    ] {
    try d.gate_plan(steps) catch {
      Invalid(_) => ()
      _ => fail("wrong graph error")
    } noraise {
      _ => fail("invalid gate graph accepted")
    }
  }
}

///|
test "gate plans validate predicate mode flags and bounds" {
  let d = parse(
    create(["A"], [], integer_values=["1"], encoding={
      kind: Integer,
      widths: [8],
      order: LittleEndian,
    }),
  )
  let exact = Exact([{ channel: 0, lower: "0", upper: "2", }])
  for
    step in [
      gate09_step("scaled", None, exact, scaled=true),
      gate09_step("compensated", None, exact, compensated=true),
      gate09_step("empty", None, Exact([])),
      gate09_step(
        "invalid",
        None,
        Rectangle([{ channel: 0, lower: 2.0, upper: 1.0, }]),
      ),
      gate09_step(
        "polygon",
        None,
        Polygon(0, 0, [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]),
      ),
    ] {
    try d.gate_plan([step]) catch {
      Invalid(_) => ()
      _ => fail("wrong predicate error")
    } noraise {
      _ => fail("invalid gate predicate accepted")
    }
  }
  let histogram = parse(
    create_histogram(["A"], [2], ["1", "2"], mode=Correlated, encoding={
      kind: Integer,
      widths: [8],
      order: LittleEndian,
    }),
  )
  try histogram.gate_plan([]) catch {
    Invalid(_) => ()
    _ => fail("wrong storage mode error")
  } noraise {
    _ => fail("histogram accepted an event plan")
  }
}

///|
test "gate plan view flags belong to each step" {
  let d = parse(
    create(
      ["TIME", "A", "B"],
      [1.0, 10.0, 15.0, 2.0, 20.0, 35.0, 3.0, 30.0, 65.0],
      double_precision=true,
      metadata=[("$TIMESTEP", "0.5")],
      spillover={ channels: ["A", "B"], coefficients: [1.0, 1.0, 0.0, 1.0], },
    ),
  )
  let r = d.gate_plan([
    gate09_step(
      "time",
      None,
      Rectangle([{ channel: 0, lower: 0.5, upper: 1.5, }]),
      scaled=true,
    ),
    gate09_step(
      "corrected",
      Some("time"),
      Rectangle([{ channel: 2, lower: 10.0, upper: 20.0, }]),
      compensated=true,
    ),
    gate09_step(
      "raw",
      Some("time"),
      Rectangle([{ channel: 2, lower: 10.0, upper: 20.0, }]),
    ),
  ])
  assert_eq(r.map(p => p.event_indices), [[0, 1], [1], [0]])
}
