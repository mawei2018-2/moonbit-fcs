///|
fn integer_mask(text : String, width : Int) -> @bigint.BigInt raise FcsError {
  if text.is_empty() || !text.iter().all(c => c >= '0' && c <= '9') {
    raise Invalid("integer PnR must be a decimal integer")
  }
  let range = @bigint.BigInt::from_string(text)
  if range.compare_int(0) <= 0 {
    raise Invalid("channel range must be positive")
  }
  let bits = (range - @bigint.BigInt::from_int(1)).bit_length()
  if bits > width {
    raise Invalid("integer range exceeds allocated bits")
  }
  (@bigint.BigInt::from_int(1) << bits) - @bigint.BigInt::from_int(1)
}

///|
// Binary DATA is continuous across parameters and events, without row padding.
fn packed_word(
  raw : Bytes,
  start : Int64,
  width : Int,
  order : ByteOrder,
) -> @bigint.BigInt {
  if start % 8L == 0L && width % 8 == 0 && width <= 64 {
    return @bigint.BigInt::from_uint64(
      uword(raw, (start / 8L).to_int(), width / 8, order),
    )
  }
  let mut value = @bigint.BigInt::from_int(0)
  for i in 0..<width {
    let p = start + i.to_int64()
    let shift = if order == LittleEndian {
      (p % 8L).to_int()
    } else {
      7 - (p % 8L).to_int()
    }
    let bit = @bigint.BigInt::from_int(
      (raw[(p / 8L).to_int()].to_int() >> shift) & 1,
    )
    if order == LittleEndian {
      value = value | (bit << i)
    } else {
      value = (value << 1) | bit
    }
  }
  value
}

///|
fn ascii_delimiter(c : Byte) -> Bool {
  c == b' ' || c == b'\t' || c == b',' || c == b'\r' || c == b'\n'
}

///|
fn ascii_integer(raw : Bytes, start : Int, size : Int) -> String raise FcsError {
  let text = ascii(raw, start, size).trim().to_owned()
  let first = if text.has_prefix("+") || text.has_prefix("-") { 1 } else { 0 }
  if text.length() == first {
    raise Invalid("empty ASCII DATA integer")
  }
  for i in first..<text.length() {
    if text[i] < '0' || text[i] > '9' {
      raise Invalid("ASCII DATA requires decimal integers")
    }
  }
  text
}

///|
fn ascii_fields(
  raw : Bytes,
  channels : Array[Channel],
  events : Int,
) -> Array[(Int, Int)] raise FcsError {
  let variable = channels.any(c => c.bits == 0)
  let fields = []
  let mut at = 0
  for _event in 0..<events {
    for channel in channels {
      if variable {
        while at < raw.length() && ascii_delimiter(raw[at]) {
          at += 1
        }
        let start = at
        while at < raw.length() && !ascii_delimiter(raw[at]) {
          at += 1
        }
        if start == at {
          raise Invalid("ASCII DATA contains fewer values than TOT/PAR")
        }
        if channel.bits > 0 && at - start > channel.bits {
          raise Invalid("ASCII value exceeds its declared character width")
        }
        ignore(ascii_integer(raw, start, at - start))
        fields.push((start, at - start))
      } else {
        need(raw, at, channel.bits)
        ignore(ascii_integer(raw, at, channel.bits))
        fields.push((at, channel.bits))
        at += channel.bits
      }
    }
  }
  if variable {
    while at < raw.length() && ascii_delimiter(raw[at]) {
      at += 1
    }
  }
  if at != raw.length() {
    raise Invalid("ASCII DATA contains excess values or bytes")
  }
  fields
}

///|
fn Dataset::ascii_value(
  self : Dataset,
  event : Int,
  channel : Int,
) -> String raise FcsError {
  let field = self.ascii_fields[event * self.channels.length() + channel]
  ascii_integer(self.raw, field.0, field.1)
}

///|
/// Exact integer text. Unlike value(), this does not round values above 2^53.
pub fn Dataset::integer_text(
  self : Dataset,
  event : Int,
  channel : Int,
) -> String raise FcsError {
  self.check_channel(channel)
  if event < 0 || event >= self.events {
    raise Invalid("event index out of bounds")
  }
  match self.kind {
    Integer =>
      (packed_word(
        self.raw,
        event.to_int64() * self.width.to_int64() +
        self.offsets[channel].to_int64(),
        self.channels[channel].bits,
        self.order,
      ) &
      self.integer_masks[channel]).to_string()
    Ascii => {
      let text = self.ascii_value(event, channel)
      let first = if text.has_prefix("+") || text.has_prefix("-") {
        1
      } else {
        0
      }
      let mut at = first
      while at + 1 < text.length() && text[at] == '0' {
        at += 1
      }
      let digits = text[at:].to_owned()
      (if text.has_prefix("-") && digits != "0" { "-" } else { "" }) + digits
    }
    _ => raise Invalid("integer_text requires integer or ASCII DATA")
  }
}

///|
fn Dataset::write_ascii(
  self : Dataset,
  events : Array[Int],
  channels : Array[Int],
) -> Bytes raise FcsError {
  let variable = channels.any(c => self.channels[c].bits == 0)
  let values = []
  let mut total = 0
  for event in events {
    for channel in channels {
      let value = self.ascii_value(event, channel)
      let width = if variable {
        value.length()
      } else {
        self.channels[channel].bits
      }
      if value.length() > width {
        raise Invalid("ASCII value does not fit output width")
      }
      let separator = if variable && !values.is_empty() { 1 } else { 0 }
      if width > 2147483647 - total - separator {
        raise Invalid("ASCII output exceeds runtime String address space")
      }
      total += width + separator
      values.push(
        if variable {
          value
        } else {
          String::make(width - value.length(), ' ') + value
        },
      )
    }
  }
  @utf8.encode(values.join(if variable { " " } else { "" }))
}

///|
fn Dataset::write_binary(
  self : Dataset,
  events : Array[Int],
  channels : Array[Int],
) -> Bytes raise FcsError {
  let widths = channels.map(c => self.channels[c].bits)
  let width = widths.fold(init=0, (total, n) => total + n)
  if self.width % 8 == 0 &&
    channels.all(c => self.offsets[c] % 8 == 0 && self.channels[c].bits % 8 == 0) {
    let row_offsets : Array[Int] = []
    for c in channels {
      for j in 0..<(self.channels[c].bits / 8) {
        row_offsets.push(self.offsets[c] / 8 + j)
      }
    }
    return Bytes::makei(packed_length(events.length(), width), i => {
      self.raw[events[i / (width / 8)] * (self.width / 8) +
      row_offsets[i % (width / 8)]]
    })
  }
  let out = Array::make(packed_length(events.length(), width), b'\x00')
  let mut target = 0L
  for event in events {
    for c in channels {
      for j in 0..<self.channels[c].bits {
        let source = event.to_int64() * self.width.to_int64() +
          self.offsets[c].to_int64() +
          j.to_int64()
        let from_shift = if self.order == LittleEndian {
          (source % 8L).to_int()
        } else {
          7 - (source % 8L).to_int()
        }
        let to_shift = if self.order == LittleEndian {
          (target % 8L).to_int()
        } else {
          7 - (target % 8L).to_int()
        }
        let bit = (self.raw[(source / 8L).to_int()].to_int() >> from_shift) & 1
        out[(target / 8L).to_int()] = (out[(target / 8L).to_int()].to_int() |
        (bit << to_shift)).to_byte()
        target += 1L
      }
    }
  }
  Bytes::from_array(out)
}
