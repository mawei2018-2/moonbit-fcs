///|
fn ascii23_source(
  values : Array[String],
  range : String,
  width? : Int = 0,
  name? : String = "Signal",
) -> Dataset raise FcsError {
  parse(
    create([name], [], integer_values=values, ranges=[range], encoding={
      kind: Ascii,
      widths: [width],
      order: LittleEndian,
    }),
  )
}

///|
test "repair23 ASCII to integer preserves selected values and linear gain" {
  for width in [0, 4] {
    let original = ascii23_source(["20", "21", "5"], "10", width~)
    let meta = original.keywords()
    put(meta, "$P1G", "2")
    let source = parse(assemble(meta, original.raw, []), strict=true)
    for order in [LittleEndian, BigEndian] {
      let output = parse(
        source.write(event_indices=[1, 0, 1], encoding={
          kind: Integer,
          widths: [8],
          order,
        }),
        strict=true,
      )
      assert_eq(output.keyword("$P1R"), Some("22"))
      assert_eq(output.keyword("$P1G"), Some("2"))
      assert_eq([0, 1, 2].map(e => output.integer_text(e, 0)), [
        "21", "20", "21",
      ])
      assert_eq([0, 1, 2].map(e => output.value(e, 0, scaled=true)), [
        10.5, 10.0, 10.5,
      ])
      assert_eq(output.rectangle([{ channel: 0, lower: 19.0, upper: 22.0, }]), [
        0, 1, 2,
      ])
    }
  }
}

///|
test "repair23 ASCII range expansion only considers exported rows" {
  let source = ascii23_source(["20", "21", "5"], "10")
  for indices in [[], [2]] {
    let output = parse(
      source.write(event_indices=indices, encoding={
        kind: Integer,
        widths: [8],
        order: LittleEndian,
      }),
      strict=true,
    )
    assert_eq(output.keyword("$P1R"), Some("10"))
    assert_eq(output.events, indices.length())
    if !indices.is_empty() {
      assert_eq(output.integer_text(0, 0), "5")
    }
  }
}

///|
test "repair23 range one keeps a selected one bit" {
  let source = ascii23_source(["0", "1"], "1")
  for order in [LittleEndian, BigEndian] {
    let output = parse(
      source.write(encoding={ kind: Integer, widths: [1], order, }),
    )
    assert_eq(output.keyword("$P1R"), Some("2"))
    assert_eq(output.integer_text(0, 0), "0")
    assert_eq(output.integer_text(1, 0), "1")
  }
}

///|
test "repair23 covered non-power-of-two logarithmic ranges stay unchanged" {
  let original = ascii23_source(["20"], "17")
  let meta = original.keywords()
  put(meta, "$P1E", "2,1")
  let source = parse(assemble(meta, original.raw, []), strict=true)
  let output = parse(
    source.write(encoding={ kind: Integer, widths: [5], order: BigEndian, }),
  )
  assert_eq(output.keyword("$P1R"), Some("17"))
  assert_eq(output.keyword("$P1E"), Some("2,1"))
  assert_eq(output.integer_text(0, 0), "20")
  assert_eq(output.value(0, 0, scaled=true), source.value(0, 0, scaled=true))
}

///|
test "repair23 impossible detector log range conversion fails explicitly" {
  let original = ascii23_source(["20"], "10")
  let meta = original.keywords()
  put(meta, "$P1E", "2,1")
  let source = parse(assemble(meta, original.raw, []), strict=true)
  try
    source.write(encoding={ kind: Integer, widths: [8], order: LittleEndian, })
  catch {
    Invalid(_) => ()
    _ => fail("wrong logarithmic conversion error")
  } noraise {
    _ => fail("lossy logarithmic conversion accepted")
  }
  let retained = parse(
    source.write(encoding={ kind: Ascii, widths: [0], order: LittleEndian, }),
  )
  assert_eq(retained.integer_text(0, 0), "20")
  assert_eq(retained.keyword("$P1R"), Some("10"))
  assert_eq(source.integer_text(0, 0), "20")
}

///|
test "repair23 Time range can grow while retaining tick calibration" {
  let original = ascii23_source(["20"], "10", name="TiMe")
  let meta = original.keywords()
  put(meta, "$P1E", "2,1")
  put(meta, "$TIMESTEP", "0.25")
  let source = parse(assemble(meta, original.raw, []), strict=true)
  let output = parse(
    source.write(encoding={ kind: Integer, widths: [8], order: LittleEndian, }),
  )
  assert_eq(output.keyword("$P1R"), Some("21"))
  assert_eq(output.keyword("$TIMESTEP"), Some("0.25"))
  assert_eq(output.integer_text(0, 0), "20")
  assert_eq(output.value(0, 0, scaled=true), 5.0)
}

///|
test "repair23 widening is arbitrary precision and width errors stay explicit" {
  let value = (@bigint.BigInt::from_int(1) << 128) + @bigint.BigInt::from_int(3)
  let source = ascii23_source([value.to_string()], "10")
  let output = parse(
    source.write(encoding={ kind: Integer, widths: [129], order: BigEndian, }),
  )
  assert_eq(output.integer_text(0, 0), value.to_string())
  assert_eq(
    output.keyword("$P1R"),
    Some((value + @bigint.BigInt::from_int(1)).to_string()),
  )
  for text in ["300", "-1"] {
    let unrepresentable = ascii23_source([text], "10")
    try
      unrepresentable.write(encoding={
        kind: Integer,
        widths: [8],
        order: LittleEndian,
      })
    catch {
      Invalid(_) => ()
      _ => fail("wrong storage-width error")
    } noraise {
      _ => fail("unrepresentable ASCII value accepted")
    }
  }
}
