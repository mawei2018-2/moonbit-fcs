///|
test "TEXT padding requires opt-in and preserves all data and value spaces" {
  let input = fixture("text_padding")
  assert_true(
    try {
      ignore(parse(input))
      false
    } catch {
      _ => true
    },
  )
  assert_true(
    try {
      ignore(parse(input, strict=true, allow_text_padding=true))
      false
    } catch {
      _ => true
    },
  )
  let d = parse(input, allow_text_padding=true)
  assert_eq(d.warnings().length(), 3)
  assert_eq(d.keyword("NOTE"), Some("value ending in spaces  "))
  assert_eq(d.keyword("EXTRA"), Some("a|b  "))
  assert_eq(d.analysis_keywords(), [("RESULT", "example  ")])
  assert_eq(d.raw, parse(fixture("float_le")).raw)
  let clean = parse(d.write(), strict=true)
  assert_eq(clean.raw, d.raw)
  assert_eq(clean.keyword("NOTE"), d.keyword("NOTE"))
  assert_eq(clean.analysis_keywords(), d.analysis_keywords())
  assert_eq(clean.warnings(), [])
  assert_eq(parse_all(input, allow_text_padding=true)[0].raw, d.raw)
}

///|
test "padding compatibility still requires complete pairs and a delimiter" {
  for
    input in [
      b"|NOTE|value  ", b"|NOTE|value|orphan|  ", b"|NOTE|value|\t", b"|NOTE|value|\x00",
      b"|NOTE|value|\n",
    ] {
    assert_true(
      try {
        ignore(
          read_segment(
            input,
            0,
            input.length() - 1,
            None,
            false,
            true,
            [],
            "test",
          ),
        )
        false
      } catch {
        _ => true
      },
    )
  }
  let warnings : Array[String] = []
  assert_eq(
    read_segment(b" NOTE value ", 0, 11, None, false, true, warnings, "test"),
    [("NOTE", "value")],
  )
  assert_eq(warnings, [])
  for sep in [b'\x00', b'\x7f'] {
    let bytes = Bytes::from_array([sep, b'K', sep, b'V', sep])
    assert_true(
      try {
        ignore(read_text(bytes, 0, 4, None))
        false
      } catch {
        _ => true
      },
    )
  }
}

///|
test "padding does not shrink the declared TEXT overlap protection" {
  let input = fixture("float_le")
  let extended_end = header_offset(input, 0, 26) + 3
  let digits = @utf8.encode(padded(extended_end, 8))
  let altered = Bytes::makei(input.length(), i => {
    if i >= 18 && i < 26 {
      digits[i - 18]
    } else if i >= header_offset(input, 0, 26) && i <= extended_end {
      b' '
    } else {
      input[i]
    }
  })
  assert_true(
    try {
      ignore(parse(altered, allow_text_padding=true))
      false
    } catch {
      _ => true
    },
  )
}
