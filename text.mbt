///|
fn read_text(
  b : Bytes,
  start : Int,
  end : Int,
  delimiter : Byte?,
  latin1? : Bool = false,
) -> Array[(String, String)] raise FcsError {
  if end < start {
    raise Invalid("invalid TEXT range")
  }
  need(b, start, end - start + 1)
  let sep = b[start]
  if sep.to_int() < 1 || sep.to_int() > 126 {
    raise Invalid("TEXT delimiter must be ASCII 1..126")
  }
  if delimiter is Some(expected) && sep != expected {
    raise Invalid("inconsistent TEXT delimiter")
  }
  if b[end] != sep {
    raise Invalid("TEXT is missing its terminating delimiter")
  }
  let tokens : Array[String] = []
  let buf : Array[Byte] = []
  let mut i = start + 1
  while i <= end {
    if b[i] == sep {
      if i < end && b[i + 1] == sep {
        if buf.is_empty() {
          raise Invalid(
            "delimiter cannot be first character of a keyword/value",
          )
        }
        buf.push(sep)
        i = i + 2
        continue
      }
      if buf.is_empty() {
        raise Invalid("empty TEXT keyword or value")
      }
      tokens.push(
        @utf8.decode(Bytes::from_array(buf), ignore_bom=false) catch {
          _ =>
            if latin1 && tokens.length() % 2 == 1 {
              String::from_iter(
                buf.iter().map(b => b.to_int().to_char().unwrap()),
              )
            } else {
              raise Invalid(
                "invalid UTF-8 in TEXT; legacy encoding requires explicit latin1 fallback",
              )
            }
        },
      )
      buf.clear()
    } else {
      buf.push(b[i])
    }
    i = i + 1
  }
  if !buf.is_empty() || tokens.length() % 2 != 0 {
    raise Invalid("unpaired TEXT keyword/value")
  }
  let result : Array[(String, String)] = []
  let keys : Map[String, Bool] = Map([])
  for i = 0; i < tokens.length(); i = i + 2 {
    let key = tokens[i]
    for c in key.iter() {
      if c.to_int() < 32 || c.to_int() > 126 {
        raise Invalid("nonprintable TEXT keyword")
      }
    }
    let folded = key.to_upper()
    if keys.contains(folded) {
      raise Invalid("duplicate TEXT keyword: \{key}")
    }
    keys[folded] = true
    result.push((key, tokens[i + 1]))
  }
  result
}

///|
fn read_segment(
  b : Bytes,
  start : Int,
  end : Int,
  delimiter : Byte?,
  latin1 : Bool,
  allow_text_padding : Bool,
  warnings : Array[String],
  segment : String,
) -> Array[(String, String)] raise FcsError {
  // Keep the declared range for overlap checks. Only the token parser's end
  // moves, and only after checking the original extent against the limits.
  if end < start {
    raise Invalid("invalid TEXT range")
  }
  need(b, start, end - start + 1)
  let mut stop = end
  if allow_text_padding && b[start] != b' ' {
    while stop > start && b[stop] == b' ' {
      stop -= 1
    }
  }
  let pairs = read_text(b, start, stop, delimiter, latin1~)
  if stop != end {
    warnings.push(
      "ignored \{end - stop} trailing ASCII spaces in \{segment}; declared extent retained",
    )
  }
  pairs
}

///|
fn merge_text(
  primary : Array[(String, String)],
  extra : Array[(String, String)],
) -> Unit raise FcsError {
  for (key, value) in extra {
    if lookup(primary, key) is Some(_) {
      raise Invalid("duplicate supplemental keyword: \{key}")
    }
    primary.push((key, value))
  }
}

///|
fn text_delimiter(pairs : Array[(String, String)]) -> String raise FcsError {
  // Prefer the historical control delimiter, then all other legal bytes.
  let candidates = [28]
  for i in 1..<127 {
    if i != 28 {
      candidates.push(i)
    }
  }
  for candidate in candidates {
    let sep = String::make(1, candidate.to_char().unwrap())
    if pairs.all(pair => {
        !pair.0.to_upper().has_prefix(sep) && !pair.1.has_prefix(sep)
      }) {
      return sep
    }
  }
  raise Invalid("no legal TEXT delimiter for metadata prefixes")
}

///|
fn encode_text(
  pairs : Array[(String, String)],
  delimiter? : String,
) -> Bytes raise FcsError {
  let sep = match delimiter {
    Some(value) => value
    None => text_delimiter(pairs)
  }
  let chunks = [sep]
  let seen : Map[String, Bool] = Map([])
  for (key, value) in pairs {
    if key.is_empty() || value.is_empty() {
      raise Invalid("cannot write empty metadata")
    }
    for c in key.iter() {
      if c.to_int() < 32 || c.to_int() > 126 {
        raise Invalid("non-ASCII metadata key")
      }
    }
    if value.has_prefix(sep) || key.to_upper().has_prefix(sep) {
      raise Invalid("metadata key/value starts with delimiter")
    }
    let k = key.to_upper()
    if seen.contains(k) {
      raise Invalid("duplicate output metadata")
    }
    seen[k] = true
    chunks.push(k.replace_all(old=sep, new=sep + sep))
    chunks.push(sep)
    chunks.push(value.replace_all(old=sep, new=sep + sep))
    chunks.push(sep)
  }
  let b = @utf8.encode(chunks.join(""))
  b
}
