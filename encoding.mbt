///|
pub(all) enum StorageMode {
  ListMode
  Correlated
  Uncorrelated
} derive(Eq, Debug, ToJson)

///|
pub extend StorageMode with Eq::{equal, not_equal}

///|
pub extend StorageMode with @debug.Debug::{to_repr}

///|
pub extend StorageMode with ToJson::{to_json}

///|
pub(all) struct Encoding {
  kind : NumberType
  widths : Array[Int]
  order : ByteOrder
} derive(Debug)

///|
pub extend Encoding with @debug.Debug::{to_repr}

///|
fn Encoding::validate(self : Encoding, channels : Int) -> Unit raise FcsError {
  if self.widths.length() != channels {
    raise Invalid("encoding width count must match channels")
  }
  for width in self.widths {
    if width < 0 ||
      (self.kind != Ascii && width == 0) ||
      (self.kind == Float32 && width != 32) ||
      (self.kind == Float64 && width != 64) {
      raise Invalid("invalid width for chosen encoding")
    }
  }
}

///|
fn decimal_integer(text : String) -> @bigint.BigInt raise FcsError {
  let first = if text.has_prefix("-") || text.has_prefix("+") { 1 } else { 0 }
  if text.length() == first {
    raise Invalid("integer requires decimal digits")
  }
  for i in first..<text.length() {
    if text[i] < '0' || text[i] > '9' {
      raise Invalid("integer requires decimal digits")
    }
  }
  @bigint.BigInt::from_string(text)
}

///|
fn double_text(text : String) -> Double raise FcsError {
  @string.parse_double(text) catch {
    _ => raise Invalid("invalid numeric data")
  }
}

///|
fn floating_integer(value : Double) -> @bigint.BigInt raise FcsError {
  if !finite(value) || value != value.trunc() {
    raise Invalid("integer encoding requires an integral finite value")
  }
  if value == 0.0 {
    return @bigint.BigInt::from_int(0)
  }
  let bits = value.abs().reinterpret_as_uint64()
  let exponent = ((bits >> 52) & 2047UL).to_int() - 1023
  let mantissa = @bigint.BigInt::from_uint64(
    (bits & 0xfffffffffffffUL) | 0x10000000000000UL,
  )
  let integer = if exponent >= 52 {
    mantissa << (exponent - 52)
  } else {
    mantissa >> (52 - exponent)
  }
  if value < 0.0 {
    -integer
  } else {
    integer
  }
}

///|
fn packed_length(count : Int, width : Int) -> Int raise FcsError {
  let bytes = (count.to_int64() * width.to_int64() + 7L) / 8L
  if width < 0 || count < 0 || bytes > 2147483647L {
    raise Invalid("DATA exceeds runtime Bytes address space")
  }
  bytes.to_int()
}

///|
fn encode_fields(
  values : Array[String],
  widths : Array[Int],
  kind : NumberType,
  order : ByteOrder,
) -> Bytes raise FcsError {
  if values.length() != widths.length() {
    raise Invalid("encoded field shape mismatch")
  }
  if kind == Ascii {
    let variable = widths.contains(0)
    let fields = values.mapi((i, text) => {
      let value = decimal_integer(text).to_string()
      if widths[i] < 0 || (widths[i] > 0 && value.length() > widths[i]) {
        raise Invalid("ASCII value exceeds width")
      }
      if variable {
        value
      } else {
        String::make(widths[i] - value.length(), ' ') + value
      }
    })
    return @utf8.encode(fields.join(if variable { " " } else { "" }))
  }
  let mut total = 0L
  for width in widths {
    if width <= 0 || width.to_int64() > 17179869176L - total {
      raise Invalid("invalid encoded width")
    }
    if (kind == Float32 && width != 32) || (kind == Float64 && width != 64) {
      raise Invalid("floating width mismatch")
    }
    total += width.to_int64()
  }
  let out = Array::make(((total + 7L) / 8L).to_int(), b'\x00')
  let mut at = 0L
  for i in 0..<values.length() {
    let width = widths[i]
    let value = match kind {
      Integer => {
        let n = decimal_integer(values[i])
        if n.compare_int(0) < 0 || n.bit_length() > width {
          raise Invalid("integer cannot fit chosen storage width")
        }
        n
      }
      Float32 => {
        let original = double_text(values[i])
        let narrowed = Float::from_double(original)
        if finite(original) && !finite(narrowed.to_double()) {
          raise Invalid("Float32 conversion overflow")
        }
        @bigint.BigInt::from_uint(narrowed.reinterpret_as_uint())
      }
      Float64 =>
        @bigint.BigInt::from_uint64(
          double_text(values[i]).reinterpret_as_uint64(),
        )
      Ascii => abort("ASCII handled above")
    }
    for j in 0..<width {
      let source = if order == LittleEndian { j } else { width - 1 - j }
      let bit = ((value >> source) & @bigint.BigInt::from_int(1)).to_int()
      let target = if order == LittleEndian {
        (at % 8L).to_int()
      } else {
        7 - (at % 8L).to_int()
      }
      out[(at / 8L).to_int()] = (out[(at / 8L).to_int()].to_int() |
      (bit << target)).to_byte()
      at += 1L
    }
  }
  Bytes::from_array(out)
}

///|
pub fn Dataset::integer_value(
  self : Dataset,
  event : Int,
  channel : Int,
) -> @bigint.BigInt raise FcsError {
  self.check_channel(channel)
  if self.mode != ListMode || event < 0 || event >= self.events {
    raise Invalid("list event index required")
  }
  match self.kind {
    Integer =>
      packed_word(
        self.raw,
        event.to_int64() * self.width.to_int64() +
        self.offsets[channel].to_int64(),
        self.channels[channel].bits,
        self.order,
      ) &
      self.integer_masks[channel]
    Ascii => decimal_integer(self.ascii_value(event, channel))
    _ => raise Invalid("integer access requires I or A DATA")
  }
}

///|
pub(all) struct IntegerBounds {
  channel : Int
  lower : String
  upper : String
} derive(Debug)

///|
pub extend IntegerBounds with @debug.Debug::{to_repr}

///|
pub fn Dataset::rectangle_exact(
  self : Dataset,
  bounds : Array[IntegerBounds],
) -> Array[Int] raise FcsError {
  let parsed = bounds.map(b => {
    self.check_channel(b.channel)
    let lo = decimal_integer(b.lower)
    let hi = decimal_integer(b.upper)
    if lo.compare(hi) >= 0 {
      raise Invalid("gate requires lower < upper")
    }
    (b.channel, lo, hi)
  })
  if self.mode != ListMode || (self.kind != Integer && self.kind != Ascii) {
    raise Invalid("exact integer gate requires list I/A DATA")
  }
  let result = []
  for event in 0..<self.events {
    let mut keep = true
    for (c, lo, hi) in parsed {
      let value = self.integer_value(event, c)
      if value.compare(lo) < 0 || value.compare(hi) >= 0 {
        keep = false
        break
      }
    }
    if keep {
      result.push(event)
    }
  }
  result
}
