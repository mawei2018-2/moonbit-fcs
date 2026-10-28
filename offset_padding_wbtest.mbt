///|
fn padded_offset_fixture(
  input : Bytes,
  key : String,
  value : String,
) -> Bytes raise {
  let marker = @utf8.encode("|" + key + "|")
  let replacement = @utf8.encode(value)
  assert_eq(replacement.length(), 10)
  for start = 0
      start <= input.length() - marker.length() - 10
      start = start + 1 {
    if Array::makei(marker.length(), i => input[start + i] == marker[i]).contains(
        false,
      ) {
      continue
    }
    let at = start + marker.length()
    return Bytes::makei(input.length(), i => {
      if i >= at && i < at + 10 {
        replacement[i - at]
      } else {
        input[i]
      }
    })
  }
  abort("fixture field not found")
}

///|
test "padded offsets require explicit compatibility, preserve metadata and canonicalize on write" {
  let mut input = fixture("float_le")
  for key in ["$BEGINSTEXT", "$ENDSTEXT", "$BEGINANALYSIS", "$ENDANALYSIS"] {
    input = padded_offset_fixture(input, key, "0         ")
  }
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
      ignore(parse(input, strict=true, allow_offset_padding=true))
      false
    } catch {
      _ => true
    },
  )
  let d = parse(input, allow_offset_padding=true)
  assert_eq(d.warnings().length(), 4)
  assert_eq(d.keyword("$BEGINSTEXT"), Some("0         "))
  assert_eq(d.raw, parse(fixture("float_le")).raw)
  assert_eq(parse_all(input, allow_offset_padding=true)[0].raw, d.raw)
  let canonical = parse(d.write(), strict=true)
  assert_eq(canonical.raw, d.raw)
  assert_eq(canonical.warnings(), [])
  assert_eq(canonical.keyword("$BEGINSTEXT"), Some("0"))
}

///|
test "offset compatibility rejects non-space padding, overflow, overlap and offset disagreement" {
  for
    value in [
      "0\t        ", "-1        ", "          ", "0 1       ", "2147483648",
    ] {
    let input = padded_offset_fixture(fixture("float_le"), "$NEXTDATA", value)
    assert_true(
      try {
        ignore(parse(input, allow_offset_padding=true))
        false
      } catch {
        _ => true
      },
    )
  }
  let overlap = padded_offset_fixture(
    padded_offset_fixture(fixture("float_le"), "$BEGINSTEXT", "256       "),
    "$ENDSTEXT",
    "256       ",
  )
  assert_true(
    try {
      ignore(parse(overlap, allow_offset_padding=true))
      false
    } catch {
      _ => true
    },
  )
  let mismatch = padded_offset_fixture(
    fixture("float_le"),
    "$BEGINDATA",
    "559       ",
  )
  assert_true(
    try {
      ignore(parse(mismatch, allow_offset_padding=true))
      false
    } catch {
      _ => true
    },
  )
  assert_true(
    try {
      ignore(natural("3 "))
      false
    } catch {
      _ => true
    },
  )
  assert_true(
    try {
      ignore(number("32 "))
      false
    } catch {
      _ => true
    },
  )
  let warnings : Array[String] = []
  assert_eq(offset_number(" 0000     ", "$NEXTDATA", true, warnings), 0)
  assert_eq(warnings.length(), 1)
}
