///|
test "quantiles preserve requested probability order over unsorted values" {
  let d = parse(create(["X"], [20.0, 1.0, 9.0, 5.0]))
  let probabilities = [1.0, 0.0, 0.5, 0.25, 0.75, 0.5]
  let q = d.quantiles(0, probabilities)
  assert_eq(q.method_id, "linear-type7")
  assert_eq(q.count, 4)
  assert_eq(q.nonfinite, 0)
  assert_eq(q.values, [
    Some(20.0),
    Some(1.0),
    Some(7.0),
    Some(4.0),
    Some(11.75),
    Some(7.0),
  ])
  probabilities[0] = 0.5
  assert_eq(q.probabilities[0], 1.0)
  assert_eq(d.value(0, 0), 20.0)
}

///|
test "quantiles exclude and count every nonfinite measurement" {
  let d = parse(quantile_fixture())
  let q = d.quantiles(1, [0.0, 0.5, 1.0])
  assert_eq(q.count, 5)
  assert_eq(q.nonfinite, 3)
  assert_eq(q.values, [Some(10.0), Some(30.0), Some(1000.0)])
}

///|
test "quantiles distinguish empty and singleton samples" {
  let empty = parse(create(["X"], []))
  let q = empty.quantiles(0, [0.0, 0.5, 1.0])
  assert_eq(q.count, 0)
  assert_eq(q.values, [None, None, None])
  let single = parse(create(["X"], [3.5]))
  assert_eq(single.quantiles(0, [0.0, 0.5, 1.0]).values, [
    Some(3.5),
    Some(3.5),
    Some(3.5),
  ])
}

///|
test "quantiles keep opposite finite extremes representable" {
  let d = parse(create(["X"], [-1.0e308, 1.0e308], double_precision=true))
  let q = d.quantiles(0, [0.0, 0.25, 0.5, 0.75, 1.0])
  assert_eq(q.values[0], Some(-1.0e308))
  assert_eq(q.values[2], Some(0.0))
  assert_eq(q.values[4], Some(1.0e308))
  assert_true((q.values[1].unwrap() / -5.0e307 - 1.0).abs() < 1.0e-15)
  assert_true((q.values[3].unwrap() / 5.0e307 - 1.0).abs() < 1.0e-15)
}

///|
test "quantiles retain a constant smallest Double subnormal" {
  let tiny = 5.0e-324
  let d = parse(create(["X"], [tiny, tiny], double_precision=true))
  assert_eq(d.quantiles(0, [0.25, 0.5, 0.75]).values, [
    Some(tiny),
    Some(tiny),
    Some(tiny),
  ])
}

///|
test "quantiles use existing gain and full compensation views" {
  let source = parse(quantile_fixture())
  let d = parse(
    source.write(event_indices=[1, 2, 3, 4, 5, 6], drop_analysis=true),
  )
  assert_eq(d.quantiles(1, [0.5]).values, [Some(25.0)])
  assert_eq(d.quantiles(1, [0.5], scaled=true).values, [Some(12.5)])
  assert_eq(d.quantiles(1, [0.5], compensated=true).values, [Some(10.75)])
}

///|
test "quantiles reject malformed probabilities and invalid empty-data channels" {
  let d = parse(create(["X"], []))
  let infinity = 1.0e308 * 2.0
  for
    probabilities in [
      [],
      [-0.1],
      [1.1],
      [infinity],
      [infinity - infinity],
      [0.5, -1.0],
    ] {
    try d.quantiles(0, probabilities) catch {
      Invalid(_) => ()
      _ => fail("wrong probability error")
    } noraise {
      _ => fail("invalid probabilities accepted")
    }
  }
  try d.quantiles(1, [0.5]) catch {
    Invalid(_) => ()
    _ => fail("wrong channel error")
  } noraise {
    _ => fail("empty DATA hid an invalid channel")
  }
}

///|
test "quantiles reject C and U list-statistic requests" {
  for mode in [Correlated, Uncorrelated] {
    let d = parse(
      create_histogram(["X"], [2], ["1", "2"], mode~, encoding={
        kind: Integer,
        widths: [8],
        order: LittleEndian,
      }),
    )
    try d.quantiles(0, [0.5]) catch {
      Invalid(_) => ()
      _ => fail("wrong histogram error")
    } noraise {
      _ => fail("histogram accepted list quantiles")
    }
  }
}

///|
test "quantiles read integer and free ASCII encodings through the value API" {
  for
    encoding in [
      Encoding::{ kind: Integer, widths: [8], order: BigEndian, },
      Encoding::{ kind: Ascii, widths: [0], order: LittleEndian, },
    ] {
    let d = parse(create(["X"], [], integer_values=["9", "1", "5"], encoding~))
    assert_eq(d.quantiles(0, [0.25, 0.5, 0.75]).values, [
      Some(3.0),
      Some(5.0),
      Some(7.0),
    ])
  }
}
