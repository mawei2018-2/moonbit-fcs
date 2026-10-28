///|
test "repair05 inverse rejects nonfinite source coefficients" {
  for coefficient in [1.0e308 * 2.0, -1.0e308 * 2.0] {
    let matrix : Spillover = { channels: ["A"], coefficients: [coefficient], }
    try matrix.inverse() catch {
      Invalid(_) => ()
      _ => fail("wrong matrix error")
    } noraise {
      _ => fail("infinite matrix coefficient accepted")
    }
  }
}

///|
test "repair05 finite inverse does not silently overflow elimination" {
  // [[a,a],[a,-a]]^-1 = [[1,1],[1,-1]]/(2*a).
  // 2*a overflows, but each inverse entry is representable.
  let matrix : Spillover = {
    channels: ["A", "B"],
    coefficients: [1.0e308, 1.0e308, 1.0e308, -1.0e308],
  }
  let inverse = matrix.inverse()
  for i in 0..<4 {
    let expected = if i == 3 { -5.0e-309 } else { 5.0e-309 }
    assert_true((inverse[i] / expected - 1.0).abs() < 1.0e-12)
  }
}

///|
test "repair05 default create validates spillover channel identity before returning bytes" {
  for double_precision in [false, true] {
    try
      create(["A", "B"], [1.0, 2.0], double_precision~, spillover={
        channels: ["A", "missing"],
        coefficients: [1.0, 0.1, 0.2, 1.0],
      })
    catch {
      Invalid(_) => ()
      _ => fail("wrong creation error")
    } noraise {
      _ => fail("create returned an unreadable file")
    }
  }
}

///|
test "repair05 writer chooses a usable delimiter for legal metadata" {
  let d = parse(
    create(["A"], [7.0], metadata=[("NOTE", "\u001cfirst\u001cinside")]),
  )
  assert_eq(d.keyword("NOTE"), Some("\u001cfirst\u001cinside"))
  // ANALYSIS must share the primary delimiter even when its values rule out
  // another candidate. These are valid UTF-8 keyword values under FCS3.1.
  d.analysis.push(("RESULT", "\u0001analysis"))
  let rewritten = parse(d.write())
  assert_eq(rewritten.analysis_keywords(), [("RESULT", "\u0001analysis")])
  assert_eq(rewritten.value(0, 0), 7.0)
}

///|
test "repair05 printable delimiter fallback escapes keyword and value" {
  let metadata = []
  for i in 1..<32 {
    metadata.push(("CONTROL\{i}", String::make(1, i.to_char().unwrap()) + "x"))
  }
  metadata.push(("KEY WITH SPACE", "middle space"))
  let encoded = encode_text(metadata)
  let decoded = read_text(encoded, 0, encoded.length() - 1, None) catch {
    e => fail("metadata-only: " + @debug.to_string(e))
  }
  assert_eq(decoded, metadata)
  let bytes = create(["A"], [9.0], metadata~) catch {
    e => fail(@debug.to_string(e))
  }
  let d = parse(bytes)
  for (key, value) in metadata {
    assert_eq(d.keyword(key), Some(value))
  }
  assert_eq(parse(d.write()).value(0, 0), 9.0)
}

///|
test "repair05 every repeated TEXT delimiter is escaped" {
  let value = "first\u001csecond\u001cthird"
  let d = parse(create(["A"], [1.0], metadata=[("NOTE", value)]))
  assert_eq(d.keyword("NOTE"), Some(value))
  assert_eq(parse(d.write()).keyword("NOTE"), Some(value))
}

///|
test "repair05 inverse equilibrates extreme row and column ranges" {
  for
    coefficients in [
      [1.0e308, 1.0e-308, 1.0e308, -1.0e-308],
      [1.0e308, 1.0e308, 1.0e-308, -1.0e-308],
    ] {
    let matrix : Spillover = { channels: ["A", "B"], coefficients, }
    let actual = matrix.inverse()
    let expected = if coefficients[1] == 1.0e-308 {
      [5.0e-309, 5.0e-309, 5.0e307, -5.0e307]
    } else {
      [5.0e-309, 5.0e307, 5.0e-309, -5.0e307]
    }
    for i in 0..<4 {
      assert_true((actual[i] / expected[i] - 1.0).abs() < 1.0e-12)
    }
  }
}
