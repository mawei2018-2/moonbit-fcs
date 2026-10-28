///|
pub(all) struct Spillover {
  channels : Array[String]
  coefficients : Array[Double]
} derive(Debug, ToJson)

///|
pub fn Dataset::channel_info(self : Dataset) -> Array[Channel] {
  self.channels.copy()
}

///|
pub fn Dataset::keywords(self : Dataset) -> Array[(String, String)] {
  self.metadata.copy()
}

///|
pub fn Dataset::warnings(self : Dataset) -> Array[String] {
  self.diagnostics.copy()
}

///|
pub fn Dataset::analysis_keywords(self : Dataset) -> Array[(String, String)] {
  self.analysis.copy()
}

///|
pub fn Dataset::keyword(self : Dataset, key : String) -> String? {
  lookup(self.metadata, key)
}

///|
pub fn Dataset::spillover(self : Dataset) -> Spillover? raise FcsError {
  let modern = self.keyword("$SPILLOVER")
  let legacy = self.keyword("$SPILL")
  if modern is Some(a) && legacy is Some(b) && a != b {
    raise Invalid("conflicting SPILL and SPILLOVER")
  }
  let value = match modern {
    Some(v) => v
    None =>
      match legacy {
        Some(v) => v
        None => return None
      }
  }
  let words = value.split(",").map(s => s.trim().to_owned()).to_array()
  let n = natural(words[0])
  if n < 1 || n > self.channels.length() {
    raise Invalid("spillover dimension must fit parameters")
  }
  if words.length() != 1 + n + n * n {
    raise Invalid("spillover matrix dimension mismatch")
  }
  let channels = []
  for i = 0; i < n; i = i + 1 {
    let name = words[i + 1]
    if channels.contains(name) {
      raise Invalid("duplicate spillover channel")
    }
    let mut found = 0
    for c in self.channels {
      if c.name == name {
        found = found + 1
      }
    }
    if found != 1 {
      raise Invalid(
        "spillover channel must identify exactly one parameter: \{name}",
      )
    }
    channels.push(name)
  }
  let coefficients = Array::makei(n * n, i => number(words[1 + n + i]))
  Some({ channels, coefficients, })
}

///|
fn Dataset::check_channel(self : Dataset, channel : Int) -> Unit raise FcsError {
  if channel < 0 || channel >= self.channels.length() {
    raise Invalid("channel index out of bounds")
  }
}

///|
/// Raw instrument value; integer padding bits above ceil(log2(PnR)) are masked.
pub fn Dataset::value(
  self : Dataset,
  event : Int,
  channel : Int,
  scaled? : Bool = false,
  compensated? : Bool = false,
) -> Double raise FcsError {
  self.check_channel(channel)
  if self.mode != ListMode {
    raise Invalid("use histogram APIs for histogram frequencies")
  }
  if compensated {
    return self.compensated_value(event, channel)
  }
  if event < 0 || event >= self.events {
    raise Invalid("event index out of bounds")
  }
  let c = self.channels[channel]
  let x = match self.kind {
    Float32 =>
      Float::reinterpret_from_uint(
        uword(
          self.raw,
          ((
            event.to_int64() * self.width.to_int64() +
            self.offsets[channel].to_int64()
          ) /
          8L).to_int(),
          4,
          self.order,
        ).to_uint(),
      ).to_double()
    Float64 =>
      uword(
        self.raw,
        ((
          event.to_int64() * self.width.to_int64() +
          self.offsets[channel].to_int64()
        ) /
        8L).to_int(),
        8,
        self.order,
      ).reinterpret_as_double()
    Integer =>
      (packed_word(
        self.raw,
        event.to_int64() * self.width.to_int64() +
        self.offsets[channel].to_int64(),
        c.bits,
        self.order,
      ) &
      self.integer_masks[channel]).to_string()
      |> double_text
    Ascii => {
      let value = @string.parse_double(self.ascii_value(event, channel)) catch {
        _ => raise Invalid("invalid ASCII DATA integer")
      }
      value
    }
  }
  if !scaled {
    return x
  }
  // Time is an explicitly named channel; amplifier gain does not apply to time.
  if c.name.to_upper() == "TIME" {
    let step = number(self.keyword("$TIMESTEP").unwrap_or("1"))
    if step <= 0.0 {
      raise Invalid("TIMESTEP must be positive")
    }
    return x * step
  }
  if c.gain <= 0.0 {
    raise Invalid("non-positive gain prevents scaled access")
  }
  (if c.decades > 0.0 {
    c.zero * @math.pow(10.0, c.decades * x / double_text(c.range))
  } else {
    x
  }) /
  c.gain
}

///|
/// Welford sample variance (n-1), with scaled fallback for intermediate overflow.
/// Non-finite measurements are counted separately.
pub fn Dataset::statistics(
  self : Dataset,
  channel : Int,
  scaled? : Bool = false,
  compensated? : Bool = false,
) -> ChannelStats raise FcsError {
  self.check_channel(channel)
  if self.mode != ListMode {
    raise Invalid("event statistics require list DATA; use histogram APIs")
  }
  let mut count = 0
  let mut nonfinite = 0
  let mut lo = 0.0
  let mut hi = 0.0
  let mut mean = 0.0
  let mut m2 = 0.0
  for e = 0; e < self.events; e = e + 1 {
    let x = self.value(e, channel, scaled~, compensated~)
    if !finite(x) {
      nonfinite = nonfinite + 1
      continue
    }
    count = count + 1
    if count == 1 {
      lo = x
      hi = x
    }
    if x < lo {
      lo = x
    }
    if x > hi {
      hi = x
    }
    let delta = x - mean
    mean = mean +
      (if finite(delta) {
        delta / count.to_double()
      } else {
        // A finite mean can exist even if subtracting opposite extremes
        // overflows. Divide each finite operand before subtraction.
        x / count.to_double() - mean / count.to_double()
      })
    m2 = m2 + delta * (x - mean)
  }
  let variance = if count <= 1 {
    None
  } else if finite(m2) {
    Some(m2 / (count - 1).to_double())
  } else if finite(mean) {
    // M2 itself may overflow even when M2/(n-1) is representable. A rare
    // second pass accumulates dimensionless squares, then divides before
    // restoring the scale. The ordinary finite Welford path is unchanged.
    let mut scale = 0.0
    let mut squares = 0.0
    for event in 0..<self.events {
      let x = self.value(event, channel, scaled~, compensated~)
      if !finite(x) {
        continue
      }
      let distance = (x - mean).abs()
      if !finite(distance) {
        scale = distance
        break
      }
      if distance > scale {
        let ratio = scale / distance
        squares = 1.0 + squares * ratio * ratio
        scale = distance
      } else if scale > 0.0 {
        let ratio = distance / scale
        squares += ratio * ratio
      }
    }
    let value = scale * (scale * (squares / (count - 1).to_double()))
    if finite(value) {
      Some(value)
    } else {
      None
    }
  } else {
    None
  }
  {
    count,
    nonfinite,
    minimum: if count > 0 {
      Some(lo)
    } else {
      None
    },
    maximum: if count > 0 {
      Some(hi)
    } else {
      None
    },
    mean: if count > 0 && finite(mean) {
      Some(mean)
    } else {
      None
    },
    variance,
  }
}

///|
/// Intersection of half-open intervals [lower, upper). NaN and infinities excluded.
pub fn Dataset::rectangle(
  self : Dataset,
  bounds : Array[Bounds],
  scaled? : Bool = false,
  compensated? : Bool = false,
) -> Array[Int] raise FcsError {
  if self.mode != ListMode {
    raise Invalid("event gates require list DATA; use histogram APIs")
  }
  if bounds.is_empty() {
    raise Invalid("at least one gate interval is required")
  }
  for b in bounds {
    self.check_channel(b.channel)
    if !finite(b.lower) || !finite(b.upper) || b.lower >= b.upper {
      raise Invalid("invalid gate bounds")
    }
  }
  let selected = []
  for e = 0; e < self.events; e = e + 1 {
    let mut keep = true
    for b in bounds {
      let v = self.value(e, b.channel, scaled~, compensated~)
      if !finite(v) || v < b.lower || v >= b.upper {
        keep = false
        break
      }
    }
    if keep {
      selected.push(e)
    }
  }
  selected
}

///|
/// Even-odd polygon gate; exact floating-point edge points included, no epsilon.
pub fn Dataset::polygon(
  self : Dataset,
  x_channel : Int,
  y_channel : Int,
  vertices : Array[(Double, Double)],
  scaled? : Bool = false,
  compensated? : Bool = false,
) -> Array[Int] raise FcsError {
  self.check_channel(x_channel)
  self.check_channel(y_channel)
  if self.mode != ListMode {
    raise Invalid("event gates require list DATA; use histogram APIs")
  }
  if x_channel == y_channel || vertices.length() < 3 {
    raise Invalid("invalid polygon dimensions")
  }
  for (x, y) in vertices {
    if !finite(x) || !finite(y) {
      raise Invalid("invalid polygon vertex")
    }
  }
  let selected = []
  for e = 0; e < self.events; e = e + 1 {
    let x = self.value(e, x_channel, scaled~, compensated~)
    let y = self.value(e, y_channel, scaled~, compensated~)
    if !finite(x) || !finite(y) {
      continue
    }
    let mut inside = false
    for i = 0; i < vertices.length(); i = i + 1 {
      let (ax, ay) = vertices[i]
      let (bx, by) = vertices[(i + 1) % vertices.length()]
      let direction = orientation(x, y, ax, ay, bx, by)
      if direction == 0 &&
        x >= ax.min(bx) &&
        x <= ax.max(bx) &&
        y >= ay.min(by) &&
        y <= ay.max(by) {
        inside = true
        break
      }
      if (ay > y) != (by > y) && (direction < 0) == (by > ay) {
        inside = !inside
      }
    }
    if inside {
      selected.push(e)
    }
  }
  selected
}
