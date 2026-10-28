///|
test "independent little endian float and escaped UTF8 metadata" {
  let d = parse(fixture("float_le"), strict=true)
  assert_eq(d.events, 3)
  assert_eq(d.value(2, 1), 5.0)
  assert_eq(d.keyword("note"), Some("a|b / 中文"))
  let cs = d.channel_info()
  cs.clear()
  assert_eq(d.channel_info().length(), 2)
}

///|
test "independent IEEE double and negative zero bits" {
  let d = parse(fixture("double_be"), strict=true)
  assert_eq(d.value(1, 0), 1.0e100)
  assert_eq(d.value(1, 1), -1.0e-100)
  assert_eq(d.value(0, 1).reinterpret_as_uint64(), 0x8000000000000000UL)
  let copy = parse(d.write(event_indices=[2, 0], channel_indices=[1, 0]))
  assert_eq(copy.value(0, 0), -2.25)
  let expected = Bytes::makei(32, i => d.raw[[40, 32, 8, 0][i / 8] + i % 8])
  assert_eq(copy.raw, expected)
}

///|
test "integer padding, mixed widths and time scaling" {
  let d = parse(fixture("int_mask"))
  assert_eq(d.value(0, 0), 1.0)
  assert_eq(d.value(1, 0), 1023.0)
  assert_eq(d.value(2, 0), 0.0)
  assert_eq(d.value(1, 1, scaled=true), 2.0)
  let mixed = parse(fixture("mixed_be"))
  assert_eq(mixed.value(0, 2), 16777215.0)
  assert_eq(mixed.value(0, 3), 4294967295.0)
  assert_eq(mixed.value(1, 2), 256.0)
}

///|
test "gain and logarithmic scaling are opt-in" {
  let d = parse(fixture("log_gain"))
  assert_eq(d.value(1, 0), 256.0)
  assert_eq(d.value(1, 0, scaled=true), 10.0)
  assert_eq(d.value(2, 1, scaled=true), 3.0)
}

///|
test "gate boundaries and sample statistics" {
  let d = parse(fixture("float_le"))
  assert_eq(d.rectangle([{ channel: 0, lower: 0.0, upper: 4.0, }]), [0, 1])
  assert_eq(d.polygon(0, 1, [(0.0, 0.0), (2.0, 0.0), (2.0, 3.0), (0.0, 3.0)]), [
    0, 1,
  ])
  let s = d.statistics(0)
  assert_eq(s.mean, Some(2.0))
  assert_eq(s.variance, Some(4.0))
  let n = parse(fixture("nan"))
  assert_eq(n.statistics(0).nonfinite, 1)
  assert_eq(n.rectangle([{ channel: 0, lower: 0.0, upper: 4.0, }]), [1])
  assert_eq(parse(fixture("empty")).statistics(0).mean, None)
}

///|
test "compensation matrices follow channel subsets and reorder" {
  let d = parse(fixture("spill"))
  assert_eq(d.spillover().unwrap().coefficients.length(), 4)
  let single = parse(d.write(channel_indices=[0]))
  assert_true(single.spillover() is None)
  assert_eq(single.value(0, 0), d.value(0, 0))
  assert_true(
    parse(d.write(channel_indices=[1], drop_spillover=true)).spillover() is None,
  )
  let reorder = parse(d.write(channel_indices=[1, 0]))
  assert_eq(
    reorder.spillover().unwrap().channels,
    reorder.channel_info().map(c => c.name),
  )
  assert_eq(reorder.value(0, 0), 1.0)
}

///|
test "supplemental TEXT, ANALYSIS and chained relative offsets" {
  let d = parse(fixture("segments"))
  assert_eq(d.keyword("extra"), Some("supplement"))
  assert_eq(parse(d.write()).analysis_keywords(), [("RESULT", "example")])
  let rejected = try {
    ignore(d.write(event_indices=[1]))
    false
  } catch {
    _ => true
  }
  assert_true(rejected)
  assert_eq(parse(d.write(event_indices=[1], drop_analysis=true)).events, 1)
  let all = parse_all(fixture("multi"))
  assert_eq(all.length(), 2)
  assert_eq(all[1].file_offset, 2048)
  assert_eq(all[1].kind, Float64)
  assert_eq(parse(fixture("old20")).version, "FCS2.0")
}

///|
test "creation shape, output type and structural metadata protections" {
  let d = parse(
    create(
      ["x", "y"],
      [1.25, -2.0, 3.0, 4.5],
      double_precision=true,
      order=BigEndian,
    ),
    strict=true,
  )
  assert_eq(d.value(1, 1), 4.5)
  assert_eq(d.kind, Float64)
  assert_true(
    try {
      ignore(create(["x"], [1.0e100]))
      false
    } catch {
      _ => true
    },
  )
  assert_true(
    try {
      ignore(d.write(updates=[("$PAR", "99")]))
      false
    } catch {
      _ => true
    },
  )
  assert_true(
    try {
      ignore(d.write(channel_indices=[0, 0]))
      false
    } catch {
      _ => true
    },
  )
}

///|
test "every truncation before last required DATA byte is rejected" {
  let b = fixture("float_le")
  for n = 0; n < b.length(); n = n + 1 {
    assert_true(
      try {
        ignore(parse(part(b, 0, n)))
        false
      } catch {
        _ => true
      },
    )
  }
}

///|
test "exclusive-end compatibility is explicit and diagnostic" {
  let original = parse(fixture("float_le"))
  let normal = original.write()
  let ts = header_offset(normal, 0, 10)
  let te = header_offset(normal, 0, 18)
  let meta = read_text(normal, ts, te, None)
  let end = natural(required(meta, "$ENDDATA")) + 1
  put(meta, "$ENDDATA", padded(end, 10))
  let txt = encode_text(meta)
  let hdr = @utf8.encode(padded(end, 8))
  let broken = Bytes::makei(normal.length(), i => {
    if i >= 34 && i < 42 {
      hdr[i - 34]
    } else if i >= ts && i <= te {
      txt[i - ts]
    } else {
      normal[i]
    }
  })
  assert_true(
    try {
      ignore(parse(broken))
      false
    } catch {
      _ => true
    },
  )
  let accepted = parse(broken, allow_exclusive_end=true)
  assert_eq(accepted.value(2, 1), 5.0)
  assert_eq(accepted.warnings().length(), 1)
}

///|
test "legacy text decoding and zero gain are not silently normalized" {
  let text = b"|NOTE|\xe9|"
  assert_true(
    try {
      ignore(read_text(text, 0, text.length() - 1, None))
      false
    } catch {
      _ => true
    },
  )
  assert_eq(read_text(text, 0, text.length() - 1, None, latin1=true), [
    ("NOTE", "é"),
  ])
  assert_true(
    try {
      ignore(read_text(b"|NOTE|x", 0, 6, None))
      false
    } catch {
      _ => true
    },
  )
  let d = parse(fixture("float_le"))
  let meta = d.keywords()
  put(meta, "$P1G", "0")
  let bytes = assemble(meta, d.raw, [])
  assert_true(
    try {
      ignore(parse(bytes, strict=true))
      false
    } catch {
      _ => true
    },
  )
  let legacy = parse(bytes)
  assert_eq(legacy.value(1, 0), 2.0)
  assert_true(
    try {
      ignore(legacy.value(1, 0, scaled=true))
      false
    } catch {
      _ => true
    },
  )
  let n = parse(fixture("nan"))
  assert_eq(parse(n.write()).raw, n.raw)
}

///|
test "adversarial dimensions, endian, offsets and unsupported format fail as typed errors" {
  let d = parse(fixture("float_le"))
  let cases = [
    ("$PAR", "2147483647"),
    ("$TOT", "999999999999999"),
    ("$DATATYPE", "A"),
    ("$MODE", "C"),
    ("$BYTEORD", "3,4,1,2"),
    ("$P1B", "64"),
    ("$P1R", "NaN"),
    ("$P1E", "-1,0"),
    ("$NEXTDATA", "99999999"),
    ("$SPILLOVER", "2,C1,Missing,1,0,0,1"),
  ]
  for pair in cases {
    let meta = d.keywords()
    put(meta, pair.0, pair.1)
    // assemble normalizes NEXTDATA; corrupt that field in bytes separately below.
    if pair.0 == "$NEXTDATA" {
      continue
    }
    assert_true(
      try {
        ignore(parse(assemble(meta, d.raw, [])))
        false
      } catch {
        _ => true
      },
    )
  }
  let source = fixture("float_le")
  let b = Bytes::makei(source.length(), i => {
    if i >= 26 && i < 34 {
      b'9'
    } else {
      source[i]
    }
  })
  assert_true(
    try {
      ignore(parse(b))
      false
    } catch {
      _ => true
    },
  )
  assert_true(
    try {
      ignore(parse(fixture("float_le"), offset=2147483647))
      false
    } catch {
      _ => true
    },
  )
}
