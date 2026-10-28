///|
test "repair06 floating Time conversion preserves raw ticks and TIMESTEP" {
  for double_precision in [false, true] {
    for step in ["0.5", "2"] {
      let original = parse(
        create(["Time"], [1.0, 2.0], double_precision~, metadata=[
          ("$TIMESTEP", step),
        ]),
      )
      for kind in [Integer, Ascii] {
        let converted = parse(
          original.write(encoding={
            kind,
            widths: [if kind == Integer { 10 } else { 4 }],
            order: BigEndian,
          }),
        )
        assert_eq(converted.integer_text(0, 0), "1")
        assert_eq(converted.integer_text(1, 0), "2")
        assert_eq(converted.keyword("$TIMESTEP"), Some(step))
        for event in 0..<2 {
          assert_eq(
            converted.value(event, 0, scaled=true),
            original.value(event, 0, scaled=true),
          )
        }
      }
    }
  }
}

///|
test "repair06 histogram rejects list-only statistics and gates" {
  for mode in [Correlated, Uncorrelated] {
    let d = parse(
      create_histogram(
        ["A", "B"],
        [2, 2],
        if mode == Correlated {
          ["1", "2", "3", "4"]
        } else {
          ["1", "2", "1", "2"]
        },
        mode~,
        encoding={ kind: Integer, widths: [8, 8], order: LittleEndian, },
      ),
    )
    try d.statistics(0) catch {
      Invalid(_) => ()
      _ => fail("wrong mode error")
    } noraise {
      _ => fail("histogram reported fake empty event statistics")
    }
    try d.rectangle([{ channel: 0, lower: 0.0, upper: 2.0, }]) catch {
      Invalid(_) => ()
      _ => fail("wrong mode error")
    } noraise {
      _ => fail("histogram reported fake empty event gate")
    }
    try d.polygon(0, 1, [(0.0, 0.0), (2.0, 0.0), (0.0, 2.0)]) catch {
      Invalid(_) => ()
      _ => fail("wrong mode error")
    } noraise {
      _ => fail("histogram reported fake empty polygon gate")
    }
    assert_eq(
      d.histogram_axis(0),
      if mode == Correlated {
        ["4", "6"]
      } else {
        ["1", "2"]
      },
    )
  }
}

///|
test "repair06 finite opposite extremes retain a representable mean" {
  let d = parse(create(["A"], [1.0e308, -1.0e308], double_precision=true))
  let stats = d.statistics(0)
  assert_eq(stats.count, 2)
  assert_eq(stats.nonfinite, 0)
  assert_eq(stats.mean, Some(0.0))
  assert_eq(stats.minimum, Some(-1.0e308))
  assert_eq(stats.maximum, Some(1.0e308))
  // The variance itself exceeds Double, unlike the mean.
  assert_eq(stats.variance, None)
}

///|
test "repair06 representable variance survives an overflowing sum of squares" {
  let d = parse(
    create(["A"], [1.0e154, -1.0e154, 0.0, 0.0], double_precision=true),
  )
  let stats = d.statistics(0)
  let expected = 1.0e154 / 3.0 * 1.0e154 * 2.0
  assert_true((stats.variance.unwrap() / expected - 1.0).abs() < 1.0e-12)
}
