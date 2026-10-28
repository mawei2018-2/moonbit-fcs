///|
test "repair07 floating conversion cannot mask normalized values above source range" {
  for double_precision in [false, true] {
    for order in [LittleEndian, BigEndian] {
      let original = parse(
        create(["ADC", "TIME"], [90.0, 180.0, 99.0, 198.0], double_precision~),
      )
      let meta = original.keywords()
      put(meta, "$P1R", "100")
      put(meta, "$P2R", "100")
      put(meta, "$P1G", "0.5")
      put(meta, "$TIMESTEP", "0.5")
      let source = parse(assemble(meta, original.raw, []), strict=true)
      for kind in [Integer, Ascii] {
        let output = parse(
          source.write(event_indices=[1, 0, 1], channel_indices=[1, 0], encoding={
            kind,
            widths: if kind == Integer {
              [16, 16]
            } else {
              [3, 3]
            },
            order,
          }),
          strict=true,
        )
        for event in 0..<3 {
          let expected = if event == 1 { "180" } else { "198" }
          assert_eq(output.integer_text(event, 0), expected)
          assert_eq(output.integer_text(event, 1), expected)
          assert_eq(
            output.value(event, 0, scaled=true),
            if event == 1 {
              90.0
            } else {
              99.0
            },
          )
          assert_eq(
            output.value(event, 1, scaled=true),
            if event == 1 {
              180.0
            } else {
              198.0
            },
          )
        }
      }
    }
  }
}

///|
test "repair07 accepted floating ranges produce positive integer output ranges" {
  for kind in [Float32, Float64] {
    let source = parse(
      create(["A", "B"], [2.0, 0.0], ranges=["2.5", "0.125"], encoding={
        kind,
        widths: if kind == Float32 {
          [32, 32]
        } else {
          [64, 64]
        },
        order: LittleEndian,
      }),
    )
    for kind in [Integer, Ascii] {
      for empty in [false, true] {
        let output = parse(
          source.write(event_indices=if empty { [] } else { [0] }, encoding={
            kind,
            widths: if kind == Integer {
              [8, 8]
            } else {
              [1, 1]
            },
            order: BigEndian,
          }),
          strict=true,
        )
        assert_eq(output.keyword("$P1R"), Some("3"))
        assert_eq(output.keyword("$P2R"), Some("1"))
        assert_eq(output.events, if empty { 0 } else { 1 })
        if !empty {
          assert_eq(output.integer_text(0, 0), "2")
          assert_eq(output.integer_text(0, 1), "0")
        }
      }
    }
  }
}

///|
test "repair07 actual width and nonintegral conversion failures remain explicit" {
  let original = parse(create(["A"], [90.0]))
  let meta = original.keywords()
  put(meta, "$P1G", "0.5")
  put(meta, "$P1R", "100")
  let source = parse(assemble(meta, original.raw, []))
  let fractional = parse(create(["A"], [1.5]))
  for
    (dataset, kind, width) in [
      (source, Integer, 7),
      (source, Ascii, 2),
      (fractional, Integer, 16),
      (fractional, Ascii, 4),
    ] {
    try
      dataset.write(encoding={ kind, widths: [width], order: LittleEndian, })
    catch {
      Invalid(_) => ()
      _ => fail("wrong conversion error")
    } noraise {
      _ => fail("unrepresentable conversion accepted")
    }
  }
}
