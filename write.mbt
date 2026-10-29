///|
fn parameter_key(key : String) -> (Int, String)? raise FcsError {
  let k = key.to_upper()
  if !k.has_prefix("$P") || k.length() < 4 {
    return None
  }
  let mut i = 2
  while i < k.length() && k[i].to_int() >= 48 && k[i].to_int() <= 57 {
    i = i + 1
  }
  if i == 2 || i == k.length() {
    return None
  }
  Some((natural(k[2:i].to_owned()), k[i:].to_owned()))
}

///|
fn padded(n : Int, width : Int) -> String raise FcsError {
  let s = n.to_string()
  if n < 0 || s.length() > width {
    raise Limit("offset field overflow")
  }
  String::make(width - s.length(), '0') + s
}

///|
fn assemble(
  meta : Array[(String, String)],
  raw : Bytes,
  analysis : Array[(String, String)],
) -> Bytes raise FcsError {
  put(meta, "$BEGINSTEXT", "0")
  put(meta, "$ENDSTEXT", "0")
  put(meta, "$NEXTDATA", "0")
  for key in ["$BEGINDATA", "$ENDDATA", "$BEGINANALYSIS", "$ENDANALYSIS"] {
    put(meta, key, "0000000000")
  }
  // TEXT and ANALYSIS must use the same delimiter, including fallback choices.
  let delimiter = text_delimiter(meta + analysis)
  let a = if analysis.is_empty() {
    b""
  } else {
    encode_text(analysis, delimiter~)
  }
  let size = encode_text(meta, delimiter~).length()
  let start = 256 + size
  let stop = start + raw.length() - 1
  let ast = if a.is_empty() { 0 } else { stop + 1 }
  let ae = if a.is_empty() { 0 } else { ast + a.length() - 1 }
  put(meta, "$BEGINDATA", padded(start, 10))
  put(meta, "$ENDDATA", padded(stop, 10))
  put(meta, "$BEGINANALYSIS", padded(ast, 10))
  put(meta, "$ENDANALYSIS", padded(ae, 10))
  let txt = encode_text(meta, delimiter~)
  if txt.length() != size {
    raise Invalid("internal TEXT layout mismatch")
  }
  let hdrfield = fn(n) raise FcsError {
    padded(if n <= 99999999 { n } else { 0 }, 8)
  }
  let hdr = @utf8.encode(
    "FCS3.1    " +
    padded(256, 8) +
    padded(255 + size, 8) +
    hdrfield(start) +
    hdrfield(stop) +
    hdrfield(ast) +
    hdrfield(ae),
  )
  let total = start + raw.length() + a.length()
  Bytes::makei(total, i => {
    if i < 58 {
      hdr[i]
    } else if i < 256 {
      b' '
    } else if i < start {
      txt[i - 256]
    } else if i <= stop {
      raw[i - start]
    } else {
      a[i - ast]
    }
  })
}

///|
fn edits(
  meta : Array[(String, String)],
  updates : Array[(String, String)],
) -> Unit raise FcsError {
  let reserved = [
    "$BEGINDATA", "$ENDDATA", "$BEGINANALYSIS", "$ENDANALYSIS", "$BEGINSTEXT", "$ENDSTEXT",
    "$NEXTDATA", "$BYTEORD", "$DATATYPE", "$MODE", "$PAR", "$TOT", "$SPILL", "$SPILLOVER",
    "$COMP", "$CRC", "$ORIGINALITY",
  ]
  for (k, v) in updates {
    if reserved.contains(k.to_upper()) || parameter_key(k) is Some(_) {
      raise Invalid("structural keyword cannot be edited: \{k}")
    }
    put(meta, k, v)
  }
}

///|
/// Creates a standalone canonical FCS 3.1 dataset. Event bytes are not decoded/re-encoded.
/// Changing events/channels with ANALYSIS requires explicit drop_analysis=true.
pub fn Dataset::write(
  self : Dataset,
  event_indices? : Array[Int],
  channel_indices? : Array[Int],
  updates? : Array[(String, String)] = [],
  drop_spillover? : Bool = false,
  drop_analysis? : Bool = false,
  encoding? : Encoding,
) -> Bytes raise FcsError {
  if self.mode != ListMode {
    if event_indices is Some(_) {
      raise Invalid("histograms use bin projection, not list event indices")
    }
    return self.write_histogram(
      channel_indices, updates, drop_spillover, drop_analysis, encoding,
    )
  }
  let es = event_indices.unwrap_or_else(() => Array::makei(self.events, i => i))
  let cs = channel_indices.unwrap_or_else(() => {
    Array::makei(self.channels.length(), i => i)
  })
  if cs.is_empty() || cs.length() > self.channels.length() {
    raise Invalid("output channel shape")
  }
  let seen : Map[Int, Bool] = Map([])
  for c in cs {
    self.check_channel(c)
    if seen.contains(c) {
      raise Invalid("duplicate output channel")
    }
    seen[c] = true
  }
  for e in es {
    if e < 0 || e >= self.events {
      raise Invalid("selected event out of bounds")
    }
  }
  let changed_channels = cs.length() != self.channels.length() ||
    cs.mapi((i, c) => i != c).contains(true)
  let changed_events = es.length() != self.events ||
    es.mapi((i, e) => i != e).contains(true)
  if (changed_channels || changed_events) &&
    !self.analysis.is_empty() &&
    !drop_analysis {
    raise Invalid(
      "selection may invalidate ANALYSIS; explicitly request drop_analysis",
    )
  }
  if changed_channels && self.keyword("$COMP") != None && !drop_spillover {
    raise Invalid(
      "legacy COMP requires explicit removal before channel changes",
    )
  }
  let meta = []
  for (key, value) in self.metadata {
    let k = key.to_upper()
    if k == "$CRC" ||
      k == "$UNICODE" ||
      (drop_spillover && ["$SPILL", "$SPILLOVER", "$COMP"].contains(k)) {
      continue
    }
    match parameter_key(k) {
      Some((old, suffix)) =>
        for i = 0; i < cs.length(); i = i + 1 {
          if cs[i] == old - 1 {
            meta.push(("$P\{i + 1}\{suffix}", value))
          }
        }
      None => meta.push((k, value))
    }
  }
  // Normalize only required layout/amplification fields. Unknown metadata is retained.
  for i = 0; i < cs.length(); i = i + 1 {
    let c = self.channels[cs[i]]
    put(meta, "$P\{i+1}E", "\{c.decades},\{c.zero}")
  }
  put(
    meta,
    "$BYTEORD",
    if self.order == LittleEndian {
      "1,2,3,4"
    } else {
      "4,3,2,1"
    },
  )
  put(meta, "$PAR", cs.length().to_string())
  put(meta, "$TOT", es.length().to_string())
  put(meta, "$ORIGINALITY", "Non-Original")
  self.sync_spillover(meta, cs, drop_spillover)
  edits(meta, updates)
  let raw = if encoding is Some(chosen) {
    chosen.validate(cs.length())
    let values = []
    for e in es {
      for c in cs {
        values.push(
          if (chosen.kind == Integer || chosen.kind == Ascii) &&
            (self.kind == Integer || self.kind == Ascii) {
            self.integer_text(e, c)
          } else if chosen.kind == Integer || chosen.kind == Ascii {
            // TIME stores ticks; TIMESTEP remains in metadata. Applying it
            // here would apply the calibration twice after conversion.
            floating_integer(
              self.value(
                e,
                c,
                scaled=self.channels[c].name.to_upper() != "TIME",
              ),
            ).to_string()
          } else {
            self
            .value(e, c, scaled=self.channels[c].name.to_upper() != "TIME")
            .to_string()
          },
        )
      }
    }
    let ranges = cs.mapi((i, c) => {
      if chosen.kind == Integer ||
        (chosen.kind == Ascii && (self.kind == Float32 || self.kind == Float64)) {
        let mut original = decimal_integer(self.channels[c].range) catch {
          _ => floating_integer(double_text(self.channels[c].range).ceil())
        }
        if self.kind == Float32 || self.kind == Float64 {
          // Floating DATA may exceed PnR; gain normalization can also expand
          // values. An integer reader masks bits using PnR, so the converted
          // range must cover the selected encoded values, not just the old
          // display range. ASCII also requires integral range metadata.
          for row in 0..<es.length() {
            let needed = decimal_integer(values[row * cs.length() + i]) +
              @bigint.BigInt::from_int(1)
            if needed.compare(original) > 0 {
              original = needed
            }
          }
        }
        if self.kind == Ascii && chosen.kind == Integer {
          // ASCII values have no PnR mask. Preserve all selected value bits
          // when moving to I; changing a detector's logarithmic range would
          // change its calibration, whereas Time continues to store ticks.
          let meaningful_bits = (original - @bigint.BigInt::from_int(1)).bit_length()
          for row in 0..<es.length() {
            let value = decimal_integer(values[row * cs.length() + i])
            if value.compare_int(0) >= 0 && value.bit_length() > meaningful_bits {
              if self.channels[c].decades > 0.0 &&
                self.channels[c].name.to_upper() != "TIME" {
                raise Invalid(
                  "integer output cannot preserve ASCII values and logarithmic range",
                )
              }
              let needed = value + @bigint.BigInt::from_int(1)
              if needed.compare(original) > 0 {
                original = needed
              }
            }
          }
        }
        if chosen.kind == Integer {
          let capacity = @bigint.BigInt::from_int(1) << chosen.widths[i]
          if original.compare(capacity) > 0 {
            if self.channels[c].decades > 0.0 {
              raise Invalid("chosen width cannot preserve logarithmic range")
            }
            original = capacity
          }
        }
        // encode_fields still rejects values that exceed the actual width.
        original.to_string()
      } else {
        self.channels[c].range
      }
    })
    set_encoding_metadata(
      meta,
      cs.map(c => self.channels[c].name),
      ranges,
      chosen,
      ListMode,
      es.length(),
      require_unique_names=false,
    )
    for i in 0..<cs.length() {
      if chosen.kind == Float32 || chosen.kind == Float64 {
        put(meta, "$P\{i+1}G", "1")
      } else if self.kind == Float32 || self.kind == Float64 {
        put(meta, "$P\{i+1}G", "1")
        put(meta, "$P\{i+1}E", "0,0")
      }
    }
    encode_fields(
      values,
      Array::makei(values.length(), i => chosen.widths[i % cs.length()]),
      chosen.kind,
      chosen.order,
    )
  } else if self.kind == Ascii {
    if !changed_events && !changed_channels {
      self.raw
    } else {
      self.write_ascii(es, cs)
    }
  } else {
    self.write_binary(es, cs)
  }
  assemble(meta, raw, if drop_analysis { [] } else { self.analysis })
}

///|
/// Event-major values. Input is finite; Float32 overflow is rejected.
pub fn create(
  names : Array[String],
  values : Array[Double],
  double_precision? : Bool = false,
  order? : ByteOrder = LittleEndian,
  metadata? : Array[(String, String)] = [],
  encoding? : Encoding,
  integer_values? : Array[String],
  ranges? : Array[String],
  spillover? : Spillover,
) -> Bytes raise FcsError {
  if encoding is Some(_) || integer_values is Some(_) {
    let texts = integer_values.unwrap_or_else(() => {
      values.map(v => {
        if encoding is Some(e) && (e.kind == Integer || e.kind == Ascii) {
          floating_integer(v).to_string()
        } else {
          v.to_string()
        }
      })
    })
    if names.is_empty() || texts.length() % names.length() != 0 {
      raise Invalid("creation shape")
    }
    let chosen = encoding.unwrap_or({
      kind: Integer,
      widths: Array::make(names.length(), 64),
      order,
    })
    chosen.validate(names.length())
    let meta = []
    edits(meta, metadata)
    let ranges = ranges.unwrap_or_else(() => {
      chosen.widths.mapi((i, width) => {
        if chosen.kind == Integer {
          (@bigint.BigInt::from_int(1) << width).to_string()
        } else if chosen.kind == Ascii {
          let mut digits = 1
          for j in 0..<(texts.length() / names.length()) {
            digits = digits.max(texts[j * names.length() + i].length())
          }
          @bigint.BigInt::from_int(10)
          .pow(@bigint.BigInt::from_int(digits))
          .to_string()
        } else {
          "262144"
        }
      })
    })
    set_encoding_metadata(
      meta,
      names,
      ranges,
      chosen,
      ListMode,
      texts.length() / names.length(),
    )
    if spillover is Some(matrix) {
      put(meta, "$SPILLOVER", matrix.text())
    }
    let bytes = assemble(
      meta,
      encode_fields(
        texts,
        Array::makei(texts.length(), i => chosen.widths[i % names.length()]),
        chosen.kind,
        chosen.order,
      ),
      [],
    )
    ignore(parse(bytes))
    return bytes
  }
  if names.is_empty() || values.length() % names.length() != 0 {
    raise Invalid("creation shape")
  }
  let meta = [
    ("$MODE", "L"),
    ("$DATATYPE", if double_precision { "D" } else { "F" }),
    ("$BYTEORD", if order == LittleEndian { "1,2,3,4" } else { "4,3,2,1" }),
    ("$PAR", names.length().to_string()),
    ("$TOT", (values.length() / names.length()).to_string()),
    ("$ORIGINALITY", "Non-Original"),
  ]
  let seen : Map[String, Bool] = Map([])
  for i = 0; i < names.length(); i = i + 1 {
    let name = names[i]
    if name.is_empty() || seen.contains(name) {
      raise Invalid("creation requires unique nonempty channel names")
    }
    seen[name] = true
    put(meta, "$P\{i+1}N", name)
    put(meta, "$P\{i+1}B", if double_precision { "64" } else { "32" })
    put(meta, "$P\{i+1}R", "262144")
    put(meta, "$P\{i+1}E", "0,0")
  }
  edits(meta, metadata)
  if spillover is Some(matrix) {
    put(meta, "$SPILLOVER", matrix.text())
  }
  let out : Array[Byte] = []
  for v in values {
    if !finite(v) {
      raise Invalid("creation requires finite values")
    }
    let bits = if double_precision {
      v.reinterpret_as_uint64()
    } else {
      let f = Float::from_double(v)
      if !finite(f.to_double()) {
        raise Invalid("Float32 value overflow")
      }
      f.reinterpret_as_uint().to_uint64()
    }
    emit_word(out, bits, if double_precision { 8 } else { 4 }, order)
  }
  let bytes = assemble(meta, Bytes::from_array(out), [])
  // Match the explicit-Encoding creation path: no successful create may
  // return a file with invalid spillover/channel metadata.
  ignore(parse(bytes))
  bytes
}
