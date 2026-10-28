///|
fn isolation08_source(
  kind : NumberType,
  order : ByteOrder,
  coefficients : Array[Double],
) -> Dataset raise FcsError {
  let width = if kind == Float32 { 32 } else { 64 }
  let template = parse(
    create(
      ["A", "B", "C"],
      Array::make(9, 0.0),
      encoding={ kind, widths: [width, width, width], order, },
      spillover={ channels: ["A", "B", "C"], coefficients, },
    ),
  )
  parse(
    assemble(
      template.keywords(),
      encode_fields(
        ["2", "NaN", "5", "3", "Infinity", "7", "4", "-Infinity", "9"],
        Array::make(9, width),
        kind,
        order,
      ),
      [],
    ),
  )
}

///|
test "repair08 zero compensation coefficients isolate nonfinite measurements" {
  for kind in [Float32, Float64] {
    for order in [LittleEndian, BigEndian] {
      let d = isolation08_source(kind, order, [
        1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0,
      ])
      for e in 0..<3 {
        // Deliberately access different channel orders with the same cache.
        assert_eq(d.value(e, 2, compensated=true), (5 + 2 * e).to_double())
        assert_eq(d.value(e, 0, compensated=true), (2 + e).to_double())
        assert_true(!finite(d.value(e, 1, compensated=true)))
        assert_eq(d.value(e, 0, compensated=true), d.value(e, 0))
      }
      let a = d.statistics(0, compensated=true)
      assert_eq(a.count, 3)
      assert_eq(a.nonfinite, 0)
      assert_eq(a.mean, Some(3.0))
      assert_eq(a.variance, Some(1.0))
      let b = d.statistics(1, compensated=true)
      assert_eq(b.count, 0)
      assert_eq(b.nonfinite, 3)
      assert_eq(
        d.rectangle([{ channel: 0, lower: 1.0, upper: 4.0, }], compensated=true),
        [0, 1],
      )
      assert_eq(
        d.polygon(
          0,
          2,
          [(1.0, 4.0), (5.0, 4.0), (5.0, 10.0), (1.0, 10.0)],
          compensated=true,
        ),
        [0, 1, 2],
      )
    }
  }
}

///|
test "repair08 sparse blocks keep real nonzero compensation dependencies" {
  let independent = isolation08_source(Float64, BigEndian, [
    1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.5, 0.0, 1.0,
  ])
  // Inverse column A is [1,0,-0.5], so A=M_A-0.5*M_C.
  for e in 0..<3 {
    assert_eq(independent.value(e, 0, compensated=true), -0.5)
    assert_true(!finite(independent.value(e, 1, compensated=true)))
  }
  let dependent = isolation08_source(Float64, LittleEndian, [
    1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 1.0,
  ])
  // Inverse column A is [1,-1,0]; B really contributes to A here.
  assert_true(dependent.value(0, 0, compensated=true).is_nan())
  assert_eq(dependent.value(1, 0, compensated=true), -1.0e308 * 2.0)
  assert_eq(dependent.value(2, 0, compensated=true), 1.0e308 * 2.0)
  assert_eq(dependent.value(2, 2, compensated=true), 9.0)
  let a = dependent.statistics(0, compensated=true)
  assert_eq(a.count, 0)
  assert_eq(a.nonfinite, 3)
  assert_eq(
    dependent.rectangle(
      [{ channel: 0, lower: -10.0, upper: 10.0, }],
      compensated=true,
    ),
    [],
  )
}
