///|
pub suberror FcsError {
  Invalid(String)
  Unsupported(String)
  Limit(String)
} derive(Debug)

///|
pub(all) enum NumberType {
  Integer
  Float32
  Float64
  Ascii
} derive(Eq, Debug, ToJson)

///|
pub(all) enum ByteOrder {
  LittleEndian
  BigEndian
} derive(Eq, Debug, ToJson)

///|
pub struct Channel {
  name : String
  stain : String
  bits : Int
  range : String
  decades : Double
  zero : Double
  gain : Double
} derive(Debug, ToJson)

///|
pub struct Dataset {
  version : String
  priv channels : Array[Channel]
  events : Int
  total_events : String
  mode : StorageMode
  priv histogram_shape_data : Array[Int]
  priv histogram_values : Array[String]
  priv mut compensation_cache : Compensation?
  kind : NumberType
  order : ByteOrder
  priv metadata : Array[(String, String)]
  priv analysis : Array[(String, String)]
  priv diagnostics : Array[String]
  file_offset : Int
  next_offset : Int
  priv raw : Bytes
  priv width : Int
  priv offsets : Array[Int]
  priv integer_masks : Array[@bigint.BigInt]
  priv ascii_fields : Array[(Int, Int)]
} derive(Debug)

///|
pub struct ChannelStats {
  count : Int
  nonfinite : Int
  minimum : Double?
  maximum : Double?
  mean : Double?
  variance : Double?
} derive(Debug, ToJson)

///|
pub struct ChannelQuantiles {
  method_id : String
  count : Int
  nonfinite : Int
  probabilities : Array[Double]
  values : Array[Double?]
} derive(Debug)

///|
pub(all) struct Bounds {
  channel : Int
  lower : Double
  upper : Double
} derive(Debug)

///|
fn finite(x : Double) -> Bool {
  !x.is_nan() && !x.is_inf()
}

///|
fn need(b : Bytes, p : Int, n : Int) -> Unit raise FcsError {
  if p < 0 || n < 0 || p > b.length() || n > b.length() - p {
    raise Invalid("truncated or invalid byte range at \{p}, length \{n}")
  }
}

///|
fn part(b : Bytes, p : Int, n : Int) -> Bytes {
  Bytes::makei(n, i => b[p + i])
}

///|
fn natural(s : String) -> Int raise FcsError {
  if s.is_empty() {
    raise Invalid("empty unsigned integer")
  }
  let mut n = 0
  for i = 0; i < s.length(); i = i + 1 {
    let c = s[i].to_int() - 48
    if c < 0 || c > 9 || n > (2147483647 - c) / 10 {
      raise Invalid("invalid or oversized unsigned integer: \{s}")
    }
    n = n * 10 + c
  }
  n
}

///|
fn number(s : String) -> Double raise FcsError {
  if s.is_empty() || s.trim().to_owned() != s {
    raise Invalid("invalid numeric metadata")
  }
  let x = @string.parse_double(s) catch {
    _ => raise Invalid("invalid number: \{s}")
  }
  if !finite(x) {
    raise Invalid("non-finite numeric metadata")
  }
  x
}

///|
fn lookup(pairs : Array[(String, String)], key : String) -> String? {
  let key = key.to_upper()
  for pair in pairs {
    if pair.0.to_upper() == key {
      return Some(pair.1)
    }
  }
  None
}

///|
fn required(
  pairs : Array[(String, String)],
  key : String,
) -> String raise FcsError {
  match lookup(pairs, key) {
    Some(v) => v
    None => raise Invalid("missing required keyword \{key}")
  }
}

///|
fn put(pairs : Array[(String, String)], key : String, value : String) -> Unit {
  for i = 0; i < pairs.length(); i = i + 1 {
    if pairs[i].0.to_upper() == key.to_upper() {
      pairs[i] = (key, value)
      return
    }
  }
  pairs.push((key, value))
}

///|
fn ascii(b : Bytes, p : Int, n : Int) -> String raise FcsError {
  need(b, p, n)
  let chars = []
  for i = 0; i < n; i = i + 1 {
    let c = b[p + i].to_int()
    if c < 32 || c > 126 {
      raise Invalid("non-ASCII header at \{p+i}")
    }
    chars.push(c.to_char().unwrap())
  }
  String::from_iter(chars.iter())
}

///|
fn header_offset(b : Bytes, base : Int, p : Int) -> Int raise FcsError {
  let s = ascii(b, base + p, 8).trim().to_owned()
  if s.is_empty() {
    0
  } else {
    natural(s)
  }
}

///|
fn uword(b : Bytes, p : Int, n : Int, order : ByteOrder) -> UInt64 {
  let mut v = 0UL
  for i = 0; i < n; i = i + 1 {
    let j = if order == LittleEndian { n - 1 - i } else { i }
    v = (v << 8) | b[p + j].to_uint64()
  }
  v
}

///|
fn emit_word(out : Array[Byte], v : UInt64, n : Int, order : ByteOrder) -> Unit {
  for i = 0; i < n; i = i + 1 {
    let shift = if order == LittleEndian { i * 8 } else { (n - 1 - i) * 8 }
    out.push(((v >> shift) & 255UL).to_byte())
  }
}
