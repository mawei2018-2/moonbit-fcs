///|
priv struct Compensation {
  indices : Array[Int]
  inverse : Array[Double]
} derive(Debug)

///|
pub fn Spillover::text(self : Spillover) -> String {
  ([self.channels.length().to_string()] +
  self.channels +
  self.coefficients.map(x => x.to_string())).join(",")
}

///|
/// Pivoted Gauss-Jordan inverse. Rows of the FCS matrix are source dyes;
/// compensated row vectors are measured linear-scale rows times S^-1.
pub fn Spillover::inverse(self : Spillover) -> Array[Double] raise FcsError {
  let n = self.channels.length()
  if self.coefficients.length() != n * n || n == 0 {
    raise Invalid("matrix dimensions")
  }
  if self.coefficients.any(x => !finite(x)) {
    raise Invalid("spillover coefficients must be finite")
  }
  // Equilibrate columns before elimination. This avoids overflowing a finite
  // matrix such as [[a,a],[a,-a]] while its inverse is representable.
  let column_scales = Array::makei(n, column => {
    let mut scale = 0.0
    for row in 0..<n {
      let value = self.coefficients[row * n + column].abs()
      if value > scale {
        scale = value
      }
    }
    scale
  })
  if column_scales.any(x => x == 0.0) {
    raise Invalid("singular spillover matrix")
  }
  // A very small row may underflow during column scaling. Use row
  // equilibration in that case, carrying the same scaling on the identity.
  let mut use_rows = false
  for i in 0..<(n * n) {
    if self.coefficients[i] != 0.0 &&
      self.coefficients[i] / column_scales[i % n] == 0.0 {
      use_rows = true
    }
  }
  let row_scales = Array::makei(n, row => {
    let mut scale = 0.0
    for column in 0..<n {
      let value = self.coefficients[row * n + column].abs()
      if value > scale {
        scale = value
      }
    }
    scale
  })
  if row_scales.any(x => x == 0.0) {
    raise Invalid("singular spillover matrix")
  }
  let rows = Array::makei(n, i => {
    Array::makei(2 * n, j => {
      if j < n {
        self.coefficients[i * n + j] /
        (if use_rows { row_scales[i] } else { column_scales[j] })
      } else if j - n == i {
        if use_rows {
          1.0 / row_scales[i]
        } else {
          1.0
        }
      } else {
        0.0
      }
    })
  })
  for column in 0..<n {
    let mut pivot = column
    for row in (column + 1)..<n {
      if rows[row][column].abs() > rows[pivot][column].abs() {
        pivot = row
      }
    }
    if rows[pivot][column] == 0.0 {
      raise Invalid("singular spillover matrix")
    }
    let swap = rows[column]
    rows[column] = rows[pivot]
    rows[pivot] = swap
    let divisor = rows[column][column]
    for j in 0..<(2 * n) {
      rows[column][j] /= divisor
    }
    for row in 0..<n {
      if row == column {
        continue
      }
      let factor = rows[row][column]
      for j in 0..<(2 * n) {
        rows[row][j] -= factor * rows[column][j]
      }
    }
  }
  let result = Array::makei(n * n, i => {
    let value = rows[i / n][n + i % n]
    if use_rows {
      value
    } else {
      value / column_scales[i / n]
    }
  })
  if result.any(x => !finite(x)) {
    raise Invalid("spillover inverse is not numerically representable")
  }
  result
}

///|
fn Dataset::compensated_value(
  self : Dataset,
  event : Int,
  channel : Int,
) -> Double raise FcsError {
  if self.compensation_cache is None {
    match self.spillover() {
      None => return self.value(event, channel, scaled=true)
      Some(matrix) => {
        let indices = matrix.channels.map(name => {
          let mut found = -1
          for c in 0..<self.channels.length() {
            if self.channels[c].name == name {
              found = c
            }
          }
          found
        })
        self.compensation_cache = Some({ indices, inverse: matrix.inverse(), })
      }
    }
  }
  let cached = self.compensation_cache.unwrap()
  let mut target = -1
  for i in 0..<cached.indices.length() {
    if cached.indices[i] == channel {
      target = i
    }
  }
  if target < 0 {
    return self.value(event, channel, scaled=true)
  }
  let mut value = 0.0
  for i in 0..<cached.indices.length() {
    let weight = cached.inverse[i * cached.indices.length() + target]
    // A zero coefficient creates no dependency on that measured channel.
    // In particular, 0*NaN/Infinity must not pollute an independent block.
    if weight != 0.0 {
      value += self.value(event, cached.indices[i], scaled=true) * weight
    }
  }
  value
}

///|
fn remove_keyword(meta : Array[(String, String)], key : String) -> Unit {
  let remaining = meta.filter(pair => pair.0.to_upper() != key)
  meta.clear()
  meta.append(remaining)
}

///|
fn Dataset::sync_spillover(
  self : Dataset,
  meta : Array[(String, String)],
  channels : Array[Int],
  drop : Bool,
) -> Unit raise FcsError {
  remove_keyword(meta, "$SPILL")
  remove_keyword(meta, "$SPILLOVER")
  if drop {
    remove_keyword(meta, "$COMP")
    return
  }
  if self.spillover() is Some(matrix) {
    let indices = []
    let names = []
    for c in channels {
      for i in 0..<matrix.channels.length() {
        if self.channels[c].name == matrix.channels[i] {
          indices.push(i)
          names.push(matrix.channels[i])
        }
      }
    }
    // A single retained dye has no cross-channel spillover; FCS3.1 requires n>1.
    if indices.length() < 2 {
      return
    }
    let values = [indices.length().to_string()]
    values.append(names)
    for row in indices {
      for column in indices {
        values.push(
          matrix.coefficients[row * matrix.channels.length() + column].to_string(),
        )
      }
    }
    put(meta, "$SPILLOVER", values.join(","))
  }
}
