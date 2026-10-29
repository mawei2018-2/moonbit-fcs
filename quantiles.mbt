///|
/// Finite-observation linear type-7 sample quantiles in the requested value view.
/// Probabilities are in [0, 1], retain their order and may repeat. An empty
/// finite sample produces None for every probability. This uses Double values,
/// not arbitrary-precision integer order statistics, and sorts an O(events) copy.
pub fn Dataset::quantiles(
  self : Dataset,
  channel : Int,
  probabilities : Array[Double],
  scaled? : Bool = false,
  compensated? : Bool = false,
) -> ChannelQuantiles raise FcsError {
  self.check_channel(channel)
  if self.mode != ListMode {
    raise Invalid("event quantiles require list DATA; use histogram APIs")
  }
  if probabilities.is_empty() ||
    probabilities.any(p => !finite(p) || p < 0.0 || p > 1.0) {
    raise Invalid("quantile probabilities must be nonempty and finite in [0,1]")
  }
  let samples : Array[Double] = []
  let mut nonfinite = 0
  for event = 0; event < self.events; event = event + 1 {
    let value = self.value(event, channel, scaled~, compensated~)
    if finite(value) {
      samples.push(value)
    } else {
      nonfinite = nonfinite + 1
    }
  }
  samples.sort()
  let values = probabilities.map(p => {
    if samples.is_empty() {
      return None
    }
    let rank = (samples.length() - 1).to_double() * p
    let lower = rank.to_int()
    let left = samples[lower]
    let weight = rank - lower.to_double()
    if weight == 0.0 {
      return Some(left)
    }
    let right = samples[lower + 1]
    let distance = right - left
    Some(
      if finite(distance) {
        left + weight * distance
      } else {
        // Opposite finite extremes can have an infinite difference while
        // their convex interpolation is finite and representable.
        (1.0 - weight) * left + weight * right
      },
    )
  })
  {
    method_id: "linear-type7",
    count: samples.length(),
    nonfinite,
    probabilities: probabilities.copy(),
    values,
  }
}

///|
pub impl ToJson for ChannelQuantiles with fn to_json(self) {
  {
    "method": self.method_id.to_json(),
    "count": self.count.to_json(),
    "nonfinite": self.nonfinite.to_json(),
    "probabilities": self.probabilities.to_json(),
    "values": self.values
    .map(value => {
      match value {
        Some(number) => number.to_json()
        None => ().to_json()
      }
    })
    .to_json(),
  }
}
