///|
// Round one exact binary integer times 2^exponent, nearest with ties to even.
// Keeping subnormal units at 2^-1074 avoids a second rounded scale operation.
fn compensation_round_binary(
  coefficient : @bigint.BigInt,
  exponent : Int,
) -> Double {
  if coefficient.is_zero() {
    return 0.0
  }
  let negative = coefficient.compare_int(0) < 0
  let magnitude = if negative { -coefficient } else { coefficient }
  let sign = if negative { 0x8000000000000000UL } else { 0UL }
  let mut quantum = (exponent + magnitude.bit_length() - 53).max(-1074)
  let shift = quantum - exponent
  let mut significand = if shift > 0 {
    magnitude >> shift
  } else {
    magnitude << -shift
  }
  if shift > 0 {
    let remainder = magnitude - (significand << shift)
    let one = @bigint.BigInt::from_int(1)
    let halfway = one << (shift - 1)
    if remainder > halfway ||
      (remainder == halfway && (significand & one).compare_int(0) != 0) {
      significand += one
    }
  }
  if significand.is_zero() {
    return sign.reinterpret_as_double()
  }
  if significand.bit_length() > 53 {
    significand = significand >> 1
    quantum += 1
  }
  let highest = quantum + significand.bit_length() - 1
  let bits = if highest > 1023 {
    sign | 0x7ff0000000000000UL
  } else if highest < -1022 {
    sign | significand.to_uint64()
  } else {
    sign |
    ((highest + 1023).to_uint64() << 52) |
    (significand.to_uint64() - 0x10000000000000UL)
  }
  bits.reinterpret_as_double()
}

///|
// Called only after the normal compensation sum becomes nonfinite, with
// finite measured values and finite cached inverse coefficients. The exact
// binary components are shared with the existing robust orientation kernel.
fn compensation_exact_dot(terms : Array[(Double, Double)]) -> Double {
  let products : Array[(@bigint.BigInt, Int)] = []
  for (value, weight) in terms {
    let (a, ae) = binary_component(value)
    let (b, be) = binary_component(weight)
    if !a.is_zero() && !b.is_zero() {
      products.push((a * b, ae + be))
    }
  }
  if products.is_empty() {
    return 0.0
  }
  let exponent = products.fold(init=products[0].1, (smallest, p) => {
    smallest.min(p.1)
  })
  let coefficient = products.fold(init=@bigint.BigInt::from_int(0), (sum, p) => {
    sum + (p.0 << (p.1 - exponent))
  })
  compensation_round_binary(coefficient, exponent)
}
