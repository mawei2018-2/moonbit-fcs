///|
test "standard 12-bit packed integer hand vectors in both byte orders" {
  for name in ["packed12_little", "packed12_big"] {
    let d = parse(standard_fixture(name), strict=true)
    assert_eq([d.integer_text(0, 0), d.integer_text(0, 1)], ["2748", "3567"])
    let changed = parse(d.write(channel_indices=[1, 0]), strict=true)
    assert_eq([changed.integer_text(0, 0), changed.integer_text(0, 1)], [
      "3567", "2748",
    ])
    assert_eq(
      changed.raw,
      if name == "packed12_little" {
        b"\xef\xcd\xab"
      } else {
        b"\xde\xfa\xbc"
      },
    )
  }
}

///|
test "non-byte-aligned event boundaries are repacked after event and channel selection" {
  for name in ["cross_event_little", "cross_event_big"] {
    let d = parse(standard_fixture(name), strict=true)
    assert_eq(d.value(1, 1), 1023.0)
    assert_eq(d.integer_text(2, 1), "1")
    let changed = parse(
      d.write(event_indices=[2, 0], channel_indices=[2, 0]),
      strict=true,
    )
    assert_eq(changed.events, 2)
    assert_eq(changed.keyword("$P1N"), Some("C3"))
    assert_eq(changed.keyword("$P1B"), Some("5"))
    assert_eq(changed.keyword("$P2B"), Some("3"))
    assert_eq(
      changed.raw,
      if name == "cross_event_little" {
        b"\x00\xb1"
      } else {
        b"\x00\x8d"
      },
    )
    assert_eq(changed.integer_text(1, 0), "17")
    assert_eq(parse(d.write(event_indices=[]), strict=true).events, 0)
  }
}

///|
test "64-bit and exact range masks retain integer identity beyond Double precision" {
  for name in ["mixed_wide_little", "mixed_wide_big"] {
    let d = parse(standard_fixture(name), strict=true)
    assert_eq(d.integer_text(0, 4), "18446744073709551615")
    assert_eq(d.integer_text(1, 4), "9007199254740993")
    let selected = parse(
      d.write(event_indices=[1, 0], channel_indices=[4, 2, 0]),
      strict=true,
    )
    assert_eq(selected.integer_text(0, 0), "9007199254740993")
    assert_eq(selected.integer_text(1, 0), "18446744073709551615")
    assert_eq(selected.integer_text(1, 1), "511")
  }
  let exact = parse(standard_fixture("exact_range_above_double"), strict=true)
  assert_eq(exact.integer_text(0, 0), "9007199254740993")
}

///|
test "fixed ASCII fields support selection metadata remapping and unchanged raw copy" {
  let d = parse(standard_fixture("ascii_fixed"), strict=true)
  assert_eq(d.kind, Ascii)
  assert_eq(d.value(0, 0), 12.0)
  assert_eq(d.value(0, 1), 7.0)
  assert_eq(parse(d.write(), strict=true).raw, d.raw)
  let selected = parse(
    d.write(event_indices=[1, 0], channel_indices=[1, 0]),
    strict=true,
  )
  assert_eq(selected.raw, b"4560003  70012")
  assert_eq(selected.keyword("$P1B"), Some("3"))
  assert_eq(selected.integer_text(0, 0), "456")
  assert_eq(
    parse(standard_fixture("ascii_wide_integer"), strict=true).integer_text(
      0, 0,
    ),
    "184467440737095516160",
  )
}

///|
test "free ASCII collapses all specified delimiters and keeps explicit zero values" {
  let d = parse(standard_fixture("ascii_variable"), strict=true)
  assert_eq(Array::makei(3, e => Array::makei(2, c => d.integer_text(e, c))), [
    ["1", "3"],
    ["3", "0"],
    ["17", "2"],
  ])
  let selected = parse(
    d.write(event_indices=[2, 0], channel_indices=[1]),
    strict=true,
  )
  assert_eq(selected.raw, b"2 3")
  assert_eq(selected.keyword("$P1B"), Some("*"))
  let mixed = parse(standard_fixture("ascii_mixed_width"), strict=true)
  let fixed = parse(
    mixed.write(event_indices=[1, 0], channel_indices=[1]),
    strict=true,
  )
  assert_eq(fixed.raw, b"00170003")
  assert_eq(fixed.integer_text(0, 0), "17")
  assert_eq(parse(d.write(event_indices=[]), strict=true).events, 0)
}

///|
test "malformed ASCII cardinality decimal fractions and truncation are rejected" {
  let d = parse(standard_fixture("ascii_variable"), strict=true)
  for raw in [b"1,2", b"1,2,3,4,5,6,7", b"1,2,3,4,5,1.5", b"1,2,3,, ,5"] {
    try parse(assemble(d.metadata.copy(), raw, []), strict=true) catch {
      Invalid(_) => ()
      _ => fail("unexpected malformed ASCII error kind")
    } noraise {
      _ => fail("malformed ASCII values were accepted")
    }
  }
  let data = standard_fixture("cross_event_little")
  try parse(part(data, 0, data.length() - 1), strict=true) catch {
    Invalid(_) => ()
    _ => fail("unexpected packed truncation error kind")
  } noraise {
    _ => fail("packed DATA truncation was accepted")
  }
}
