///|
fn histogram_cells(
  mode : StorageMode,
  shape : Array[Int],
) -> Int raise FcsError {
  let mut cells = if mode == Correlated { 1 } else { 0 }
  for n in shape {
    if n < 1 {
      raise Invalid("histogram axis must contain bins")
    }
    if mode == Correlated {
      if cells > 2147483647 / n {
        raise Invalid("histogram size overflows runtime index")
      }
      cells *= n
    } else {
      if cells > 2147483647 - n {
        raise Invalid("histogram size overflows runtime index")
      }
      cells += n
    }
  }
  cells
}

///|
fn histogram_widths(
  mode : StorageMode,
  shape : Array[Int],
  widths : Array[Int],
  kind : NumberType,
) -> Array[Int] raise FcsError {
  if mode == Correlated {
    return Array::make(
      histogram_cells(mode, shape),
      if kind == Ascii && widths.contains(0) {
        0
      } else {
        widths.fold(init=0, (a, b) => a.max(b))
      },
    )
  }
  let result = []
  for c in 0..<shape.length() {
    for _ in 0..<shape[c] {
      result.push(widths[c])
    }
  }
  result
}

///|
fn decode_histogram(
  raw : Bytes,
  mode : StorageMode,
  kind : NumberType,
  order : ByteOrder,
  channels : Array[Channel],
) -> Array[String] raise FcsError {
  let shape = channels.map(c => natural(c.range))
  let cells = histogram_cells(mode, shape)
  let mut expected_bits = 0L
  if kind == Ascii && channels.any(c => c.bits == 0) {
    if cells > raw.length() {
      raise Invalid("histogram dimensions exceed available ASCII fields")
    }
  } else {
    if mode == Correlated {
      expected_bits = cells.to_int64() *
        channels.fold(init=0, (n, c) => n.max(c.bits)).to_int64()
    } else {
      for c in 0..<shape.length() {
        expected_bits += shape[c].to_int64() * channels[c].bits.to_int64()
      }
    }
    let expected_bytes = if kind == Ascii {
      expected_bits
    } else {
      (expected_bits + 7L) / 8L
    }
    if expected_bytes != raw.length().to_int64() {
      raise Invalid("histogram dimensions disagree with DATA size")
    }
  }
  let widths = histogram_widths(mode, shape, channels.map(c => c.bits), kind)
  let result = []
  if kind == Ascii {
    let variable = widths.contains(0)
    let mut at = 0
    for width in widths {
      if variable {
        while at < raw.length() && ascii_delimiter(raw[at]) {
          at += 1
        }
        let first = at
        while at < raw.length() && !ascii_delimiter(raw[at]) {
          at += 1
        }
        if first == at || (width > 0 && at - first > width) {
          raise Invalid("histogram ASCII field shape")
        }
        result.push(ascii_integer(raw, first, at - first))
      } else {
        need(raw, at, width)
        result.push(ascii_integer(raw, at, width))
        at += width
      }
    }
    if variable {
      while at < raw.length() && ascii_delimiter(raw[at]) {
        at += 1
      }
    }
    if at != raw.length() {
      raise Invalid("histogram DATA extent mismatch")
    }
  } else {
    let mut at = 0L
    for width in widths {
      if width < 1 || width.to_int64() > raw.length().to_int64() * 8L - at {
        raise Invalid("truncated histogram frequency")
      }
      let value = match kind {
        Integer => packed_word(raw, at, width, order).to_string()
        Float32 =>
          Float::reinterpret_from_uint(
            uword(raw, (at / 8L).to_int(), 4, order).to_uint(),
          )
          .to_double()
          .to_string()
        Float64 =>
          uword(raw, (at / 8L).to_int(), 8, order)
          .reinterpret_as_double()
          .to_string()
        Ascii => abort("ASCII handled above")
      }
      result.push(value)
      at += width.to_int64()
    }
    if (at + 7L) / 8L != raw.length().to_int64() {
      raise Invalid("histogram DATA extent mismatch")
    }
  }
  for value in result {
    if kind == Integer || kind == Ascii {
      if decimal_integer(value).compare_int(0) < 0 {
        raise Invalid("negative histogram frequency")
      }
    } else if double_text(value) < 0.0 || !finite(double_text(value)) {
      raise Invalid("invalid histogram frequency")
    }
  }
  result
}

///|
pub fn Dataset::histogram_shape(self : Dataset) -> Array[Int] {
  self.histogram_shape_data.copy()
}

///|
pub fn Dataset::histogram_frequencies(self : Dataset) -> Array[String] {
  self.histogram_values.copy()
}

///|
pub fn Dataset::histogram_events(
  self : Dataset,
) -> @bigint.BigInt raise FcsError {
  if self.mode == ListMode {
    raise Invalid("histogram dataset required")
  }
  decimal_integer(self.total_events)
}

///|
fn Dataset::validate_histogram_totals(self : Dataset) -> Unit raise FcsError {
  if self.mode != Uncorrelated || (self.kind != Integer && self.kind != Ascii) {
    return
  }
  let total = decimal_integer(self.total_events)
  let mut offset = 0
  for bins in self.histogram_shape_data {
    let mut sum = @bigint.BigInt::from_int(0)
    for i in offset..<(offset + bins) {
      sum = sum + decimal_integer(self.histogram_values[i])
    }
    if sum != total {
      raise Invalid(
        "uncorrelated histogram axes must share the declared event total",
      )
    }
    offset += bins
  }
}

///|
pub fn Dataset::histogram_frequency(
  self : Dataset,
  bins : Array[Int],
  axis? : Int = 0,
) -> String raise FcsError {
  let shape = self.histogram_shape_data
  if self.mode == ListMode {
    raise Invalid("histogram dataset required")
  }
  if self.mode == Uncorrelated {
    self.check_channel(axis)
    if bins.length() != 1 || bins[0] < 0 || bins[0] >= shape[axis] {
      raise Invalid("histogram bin index")
    }
    let mut at = bins[0]
    for c in 0..<axis {
      at += shape[c]
    }
    return self.histogram_values[at]
  }
  if bins.length() != shape.length() {
    raise Invalid("correlated histogram coordinate dimension")
  }
  let mut offset = 0
  let mut stride = 1
  for c in 0..<shape.length() {
    if bins[c] < 0 || bins[c] >= shape[c] {
      raise Invalid("histogram bin index")
    }
    offset += stride * bins[c]
    stride *= shape[c]
  }
  self.histogram_values[offset]
}

///|
fn Dataset::project_histogram(
  self : Dataset,
  channels : Array[Int],
) -> Array[String] raise FcsError {
  if self.mode == Uncorrelated {
    let result = []
    for c in channels {
      for bin in 0..<self.histogram_shape_data[c] {
        result.push(self.histogram_frequency([bin], axis=c))
      }
    }
    return result
  }
  let shape = channels.map(c => self.histogram_shape_data[c])
  let result = Array::make(histogram_cells(Correlated, shape), "0")
  for old in 0..<self.histogram_values.length() {
    let mut rest = old
    let coordinates = self.histogram_shape_data.map(n => {
      let value = rest % n
      rest /= n
      value
    })
    let mut target = 0
    let mut stride = 1
    for c in channels {
      target += coordinates[c] * stride
      stride *= self.histogram_shape_data[c]
    }
    result[target] = if self.kind == Integer || self.kind == Ascii {
      (decimal_integer(result[target]) +
      decimal_integer(self.histogram_values[old])).to_string()
    } else {
      (double_text(result[target]) + double_text(self.histogram_values[old])).to_string()
    }
  }
  result
}

///|
pub fn Dataset::histogram_axis(
  self : Dataset,
  channel : Int,
) -> Array[String] raise FcsError {
  self.check_channel(channel)
  if self.mode == ListMode {
    raise Invalid("histogram dataset required")
  }
  self.project_histogram([channel])
}

///|
pub fn create_histogram(
  names : Array[String],
  shape : Array[Int],
  frequencies : Array[String],
  mode~ : StorageMode,
  encoding~ : Encoding,
  events? : Int = -1,
  total_events? : String,
  metadata? : Array[(String, String)] = [],
) -> Bytes raise FcsError {
  if mode == ListMode ||
    names.is_empty() ||
    names.length() != shape.length() ||
    names.length() != encoding.widths.length() ||
    frequencies.length() != histogram_cells(mode, shape) {
    raise Invalid("histogram creation shape")
  }
  let meta = []
  edits(meta, metadata)
  let mut total = @bigint.BigInt::from_int(0)
  let length = if mode == Uncorrelated {
    shape[0]
  } else {
    frequencies.length()
  }
  for i in 0..<length {
    total = total +
      (if encoding.kind == Integer || encoding.kind == Ascii {
        decimal_integer(frequencies[i])
      } else {
        floating_integer(double_text(frequencies[i]))
      })
  }
  let total = total_events.unwrap_or(
    if events >= 0 {
      events.to_string()
    } else {
      total.to_string()
    },
  )
  if decimal_integer(total).compare_int(0) < 0 {
    raise Invalid("negative histogram event total")
  }
  set_encoding_metadata(
    meta,
    names,
    shape.map(n => n.to_string()),
    encoding,
    mode,
    0,
  )
  put(meta, "$TOT", total)
  let bytes = assemble(
    meta,
    encode_fields(
      frequencies,
      histogram_widths(mode, shape, encoding.widths, encoding.kind),
      encoding.kind,
      encoding.order,
    ),
    [],
  )
  ignore(parse(bytes))
  bytes
}
