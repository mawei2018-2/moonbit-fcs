///|
fn boolean_step(
  id : String,
  parent : String?,
  predicate : GatePredicate,
  scaled? : Bool = false,
  compensated? : Bool = false,
) -> GateStep {
  { id, parent, predicate, scaled, compensated, }
}

///|
test "Boolean full DAG preserves forward diamonds counts and original 65-bit members" {
  let d = parse(boolean_fixture())
  let result = d.gate_plan(boolean_steps())
  assert_eq(result.map(p => p.event_indices), [
    [5, 6],
    [6],
    [3, 4],
    [1, 2, 3, 4],
    [1, 2, 3, 4, 5, 6],
    [3, 4, 5, 6],
    [1, 2, 3, 4, 5, 6],
    [0, 5, 6, 7],
    [1, 2, 3, 4],
    [3, 4],
    [1, 2, 3, 4],
  ])
  assert_eq(result[2].id, "intersection")
  assert_eq(result[2].count, 2)
  assert_eq(result[2].parent_count, 6)
  assert_eq(result[2].total_count, 8)
  assert_eq(result[2].parent_fraction, Some(1.0 / 3.0))
  assert_eq(result[2].total_fraction, Some(0.25))
  assert_eq(
    d.integer_text(result[2].event_indices[0], 2),
    "18446744073709551619",
  )
}

///|
test "Boolean singleton and repeated operands are idempotent including parent edges" {
  let d = parse(boolean_fixture())
  let result = d.gate_plan([
    boolean_step("oneAnd", Some("A"), AllOf(["A", "A"])),
    boolean_step("oneOr", Some("A"), AnyOf(["A"])),
    boolean_step(
      "A",
      None,
      Rectangle([{ channel: 0, lower: 1.0, upper: 5.0, }]),
    ),
  ])
  assert_eq(result[0].event_indices, [1, 2, 3, 4])
  assert_eq(result[1].event_indices, result[0].event_indices)
  assert_eq(result[0].parent_fraction, Some(1.0))
}

///|
test "Boolean empty Dataset retains valid plan order and absent fractions" {
  let original = parse(boolean_fixture())
  let empty = parse(original.write(event_indices=[], drop_analysis=true))
  let result = empty.gate_plan(boolean_steps())
  assert_eq(result.length(), 11)
  for population in result {
    assert_eq(population.event_indices, [])
    assert_eq(population.count, 0)
    assert_eq(population.parent_count, 0)
    assert_eq(population.total_count, 0)
    assert_eq(population.parent_fraction, None)
    assert_eq(population.total_fraction, None)
  }
}

///|
test "Boolean unknown operands are validated before empty intersections" {
  let d = parse(boolean_fixture())
  for
    predicate in [
      AllOf(["empty", "missing"]),
      AnyOf(["all", "missing"]),
      Not("missing"),
    ] {
    try
      d.gate_plan([
        boolean_step(
          "empty",
          None,
          Rectangle([{ channel: 0, lower: 20.0, upper: 30.0, }]),
        ),
        boolean_step(
          "all",
          None,
          Rectangle([{ channel: 0, lower: -1.0, upper: 9.0, }]),
        ),
        boolean_step("bad", Some("empty"), predicate),
      ])
    catch {
      Invalid(_) => ()
      _ => fail("wrong Boolean reference error")
    } noraise {
      _ => fail("unknown Boolean reference hidden by membership")
    }
  }
}

///|
test "Boolean self mutual and mixed parent reference cycles reject whole plans" {
  let d = parse(boolean_fixture())
  for
    steps in [
      [boolean_step("A", None, Not("A"))],
      [
        boolean_step("A", None, AnyOf(["B"])),
        boolean_step("B", None, AllOf(["A"])),
      ],
      [
        boolean_step(
          "A",
          Some("B"),
          Rectangle([{ channel: 0, lower: -1.0, upper: 9.0, }]),
        ),
        boolean_step("B", None, Not("A")),
      ],
    ] {
    try d.gate_plan(steps) catch {
      Invalid(_) => ()
      _ => fail("wrong Boolean cycle error")
    } noraise {
      _ => fail("Boolean dependency cycle accepted")
    }
  }
}

///|
test "Boolean view and empty operand errors cannot hide under empty parents" {
  let d = parse(boolean_fixture())
  for predicate in [AllOf(["A"]), AnyOf(["A"]), Not("A")] {
    for scaled in [false, true] {
      try
        d.gate_plan([
          boolean_step(
            "empty",
            None,
            Rectangle([{ channel: 0, lower: 20.0, upper: 30.0, }]),
          ),
          boolean_step(
            "A",
            None,
            Rectangle([{ channel: 0, lower: -1.0, upper: 9.0, }]),
          ),
          boolean_step(
            "bad",
            Some("empty"),
            predicate,
            scaled~,
            compensated=!scaled,
          ),
        ])
      catch {
        Invalid(_) => ()
        _ => fail("wrong Boolean view error")
      } noraise {
        _ => fail("Boolean numeric view silently ignored")
      }
    }
  }
  for predicate in [AllOf([]), AnyOf([])] {
    try d.gate_plan([boolean_step("bad", None, predicate)]) catch {
      Invalid(_) => ()
      _ => fail("wrong empty operand error")
    } noraise {
      _ => fail("empty Boolean operands accepted")
    }
  }
}

///|
test "Boolean complements include nonfinite exclusions unless a parent qualifies them" {
  let d = parse(boolean_nonfinite_fixture())
  let result = d.gate_plan([
    boolean_step("notA", None, Not("A")),
    boolean_step("qualified", Some("finite"), Not("A")),
    boolean_step(
      "A",
      None,
      Rectangle([{ channel: 0, lower: 0.0, upper: 1.0, }]),
    ),
    boolean_step(
      "finite",
      None,
      Rectangle([{ channel: 0, lower: -1.0, upper: 3.0, }]),
    ),
  ])
  assert_eq(result[0].event_indices, [1, 2])
  assert_eq(result[1].event_indices, [2])
  assert_eq(result[1].parent_count, 2)
}

///|
test "Geometric predicates below empty Boolean populations still validate" {
  let d = parse(boolean_fixture())
  try
    d.gate_plan([
      boolean_step(
        "all",
        None,
        Rectangle([{ channel: 0, lower: -1.0, upper: 9.0, }]),
      ),
      boolean_step("empty", None, Not("all")),
      boolean_step(
        "bad",
        Some("empty"),
        Rectangle([{ channel: 99, lower: 0.0, upper: 1.0, }]),
      ),
    ])
  catch {
    Invalid(_) => ()
    _ => fail("wrong geometric child error")
  } noraise {
    _ => fail("empty Boolean parent hid invalid geometry")
  }
}
