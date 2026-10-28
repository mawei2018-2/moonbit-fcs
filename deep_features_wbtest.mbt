///|
test "arbitrary-width binary and ASCII use exact integer gates on both byte orders" {
  let high = @bigint.BigInt::from_int(1) << 1023
  let values = [
    "18446744073709551617",
    (high + @bigint.BigInt::from_int(1)).to_string(),
    "18446744073709551618",
    (high + @bigint.BigInt::from_int(2)).to_string(),
  ]
  for order in [LittleEndian, BigEndian] {
    let d = parse(
      create(["A", "B"], [], integer_values=values, encoding={
        kind: Integer,
        widths: [65, 1024],
        order,
      }),
    )
    assert_eq(d.integer_text(1, 1), values[3])
    assert_eq(
      d.rectangle_exact([
        {
          channel: 1,
          lower: values[3],
          upper: (high + @bigint.BigInt::from_int(3)).to_string(),
        },
      ]),
      [1],
    )
    let rewritten = parse(d.write(event_indices=[1, 0], channel_indices=[1, 0]))
    assert_eq(rewritten.integer_text(0, 0), values[3])
    let ascii = parse(d.write(encoding={ kind: Ascii, widths: [0, 0], order, }))
    assert_eq(ascii.integer_text(0, 1), values[1])
    let binary = parse(
      ascii.write(encoding={ kind: Integer, widths: [65, 1024], order, }),
    )
    assert_eq(binary.integer_text(1, 0), values[2])
  }
}

///|
test "the create and write paths support each DATA encoding" {
  for kind in [Integer, Ascii, Float32, Float64] {
    let width = match kind {
      Integer => 10
      Ascii => 4
      Float32 => 32
      Float64 => 64
    }
    let d = parse(
      create(["A", "B"], [1.0, 2.0, 3.0, 4.0], encoding={
        kind,
        widths: [width, width],
        order: BigEndian,
      }),
    )
    assert_eq(d.value(1, 1), 4.0)
    let f = parse(
      d.write(encoding={ kind: Float64, widths: [64, 64], order: LittleEndian, }),
    )
    assert_eq(f.value(1, 0), 3.0)
  }
}

///|
test "correlated first-axis-fast bins and uncorrelated streams rewrite with projected axes" {
  let c = parse(
    create_histogram(
      ["A", "B"],
      [2, 3],
      ["1", "2", "3", "4", "5", "6"],
      mode=Correlated,
      encoding={ kind: Integer, widths: [16, 16], order: LittleEndian, },
      events=21,
    ),
  )
  assert_eq(c.histogram_frequency([1, 2]), "6")
  assert_eq(c.histogram_axis(1), ["3", "7", "11"])
  let reordered = parse(c.write(channel_indices=[1, 0]))
  assert_eq(reordered.histogram_shape(), [3, 2])
  assert_eq(reordered.histogram_frequencies(), ["1", "3", "5", "2", "4", "6"])
  assert_eq(parse(c.write(channel_indices=[0])).histogram_frequencies(), [
    "9", "12",
  ])
  let u = parse(
    create_histogram(
      ["A", "B"],
      [2, 3],
      ["5", "7", "12", "0", "0"],
      mode=Uncorrelated,
      encoding={ kind: Ascii, widths: [0, 0], order: BigEndian, },
      events=12,
    ),
  )
  assert_eq(u.histogram_frequency([0], axis=1), "12")
  assert_eq(parse(u.write(channel_indices=[1])).histogram_axis(0), [
    "12", "0", "0",
  ])
}

///|
test "histogram marginalization widens frequency storage instead of losing counts" {
  let c = parse(
    create_histogram(
      ["A", "B"],
      [2, 2],
      ["255", "255", "255", "255"],
      mode=Correlated,
      encoding={ kind: Integer, widths: [8, 8], order: BigEndian, },
      events=1020,
    ),
  )
  let projected = parse(c.write(channel_indices=[0]))
  assert_eq(projected.histogram_frequencies(), ["510", "510"])
  assert_eq(projected.channel_info()[0].bits, 9)
}

///|
test "encoding conversion retains amplifier range and time calibration" {
  let source = parse(fixture("log_gain"))
  let integer = parse(
    source.write(encoding={
      kind: Integer,
      widths: [16, 16],
      order: LittleEndian,
    }),
  )
  assert_eq(integer.value(1, 0, scaled=true), source.value(1, 0, scaled=true))
  let timed = parse(fixture("int_mask"))
  let floating = parse(
    timed.write(encoding={
      kind: Float64,
      widths: [64, 64],
      order: LittleEndian,
    }),
  )
  assert_eq(floating.value(1, 1, scaled=true), timed.value(1, 1, scaled=true))
}

///|
test "polygon geometry has no artificial magnitude bound and uses exact fallback" {
  let d = parse(
    create(
      ["X", "Y"],
      [1.0e300, 1.0e300, 0.0, 0.0, 1.0e-300, 1.0e-300],
      double_precision=true,
    ),
  )
  assert_eq(
    d.polygon(0, 1, [
      (0.5e300, 0.5e300),
      (1.5e300, 0.5e300),
      (1.5e300, 1.5e300),
      (0.5e300, 1.5e300),
    ]),
    [0],
  )
  assert_eq(
    d.polygon(0, 1, [
      (0.5e-300, 0.5e-300),
      (1.5e-300, 0.5e-300),
      (1.5e-300, 1.5e-300),
      (0.5e-300, 1.5e-300),
    ]),
    [2],
  )
}

///|
test "spillover inverse uses dye rows and is shared by values statistics and gates" {
  let matrix : Spillover = {
    channels: ["A", "B", "C"],
    coefficients: [1.0, 0.1, 0.03, 0.02, 1.0, 0.05, 0.1, 0.03, 1.0],
  }
  let d = parse(
    create(
      ["A", "B", "C"],
      [13.4, 21.9, 31.3],
      double_precision=true,
      spillover=matrix,
    ),
  )
  for c in 0..<3 {
    assert_true(
      (d.value(0, c, compensated=true) - (c + 1).to_double() * 10.0).abs() <
      1.0e-10,
    )
  }
  assert_true(
    (d.statistics(0, compensated=true).mean.unwrap() - 10.0).abs() < 1.0e-10,
  )
  assert_eq(
    d.rectangle([{ channel: 0, lower: 9.0, upper: 11.0, }], compensated=true),
    [0],
  )
  assert_eq(
    d.polygon(
      0,
      1,
      [(9.0, 19.0), (11.0, 19.0), (11.0, 21.0), (9.0, 21.0)],
      compensated=true,
    ),
    [0],
  )
  let subset = parse(d.write(channel_indices=[2, 0])).spillover().unwrap()
  assert_eq(subset.channels, ["C", "A"])
  assert_eq(subset.coefficients, [1.0, 0.1, 0.03, 1.0])
  let singular = parse(
    create(["A", "B"], [1.0, 2.0], spillover={
      channels: ["A", "B"],
      coefficients: [1.0, 1.0, 1.0, 1.0],
    }),
  )
  try singular.value(0, 0, compensated=true) catch {
    Invalid(_) => ()
    _ => fail("wrong matrix error")
  } noraise {
    _ => fail("singular matrix accepted")
  }
}
