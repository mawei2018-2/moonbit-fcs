///|
fn binary_component(value : Double) -> (@bigint.BigInt, Int) {
  let bits = value.reinterpret_as_uint64()
  let exponent = ((bits >> 52) & 2047UL).to_int()
  let coefficient = @bigint.BigInt::from_uint64(
    (bits & 0xfffffffffffffUL) |
    (if exponent == 0 { 0UL } else { 0x10000000000000UL }),
  )
  (
    if bits >> 63 != 0UL {
      -coefficient
    } else {
      coefficient
    },
    if exponent == 0 {
      -1074
    } else {
      exponent - 1075
    },
  )
}

///|
// Filter ordinary well-separated determinants in Double; exact binary integer
// fallback handles cancellation, underflow and overflow without coordinate caps.
fn orientation(
  x : Double,
  y : Double,
  ax : Double,
  ay : Double,
  bx : Double,
  by : Double,
) -> Int {
  let left = (x - ax) * (by - ay)
  let right = (y - ay) * (bx - ax)
  let determinant = left - right
  if finite(determinant) &&
    determinant.abs() > (left.abs() + right.abs()) * 8.881784197001252e-16 {
    return if determinant > 0.0 { 1 } else { -1 }
  }
  let components = [x, y, ax, ay, bx, by].map(binary_component)
  let exponent = components.fold(init=0, (e, c) => e.min(c.1))
  let units = components.map(c => c.0 << (c.1 - exponent))
  ((units[0] - units[2]) * (units[5] - units[3]) -
  (units[1] - units[3]) * (units[4] - units[2])).compare_int(0)
}
