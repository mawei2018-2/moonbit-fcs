///|
fn set_encoding_metadata(
  meta : Array[(String, String)],
  names : Array[String],
  ranges : Array[String],
  encoding : Encoding,
  mode : StorageMode,
  events : Int,
  require_unique_names? : Bool = true,
) -> Unit raise FcsError {
  encoding.validate(names.length())
  if names.is_empty() ||
    names.length() != ranges.length() ||
    names.length() != encoding.widths.length() ||
    events < 0 {
    raise Invalid("encoding shape")
  }
  let seen : Map[String, Bool] = Map([])
  put(
    meta,
    "$MODE",
    match mode {
      ListMode => "L"
      Correlated => "C"
      Uncorrelated => "U"
    },
  )
  put(
    meta,
    "$DATATYPE",
    match encoding.kind {
      Integer => "I"
      Ascii => "A"
      Float32 => "F"
      Float64 => "D"
    },
  )
  put(
    meta,
    "$BYTEORD",
    if encoding.order == LittleEndian {
      "1,2,3,4"
    } else {
      "4,3,2,1"
    },
  )
  put(meta, "$PAR", names.length().to_string())
  put(meta, "$TOT", events.to_string())
  put(meta, "$ORIGINALITY", "Non-Original")
  for c in 0..<names.length() {
    if names[c].is_empty() || (require_unique_names && seen.contains(names[c])) {
      raise Invalid("unique nonempty channel names required")
    }
    seen[names[c]] = true
    let width = encoding.widths[c]
    if width < 0 || (encoding.kind != Ascii && width == 0) {
      raise Invalid("positive binary width required")
    }
    put(meta, "$P\{c+1}N", names[c])
    put(
      meta,
      "$P\{c+1}B",
      if encoding.kind == Ascii && width == 0 {
        "*"
      } else {
        width.to_string()
      },
    )
    put(meta, "$P\{c+1}R", ranges[c])
    if lookup(meta, "$P\{c+1}E") is None ||
      encoding.kind == Float32 ||
      encoding.kind == Float64 {
      put(meta, "$P\{c+1}E", "0,0")
    }
  }
}

///|
fn Dataset::write_histogram(
  self : Dataset,
  channels : Array[Int]?,
  updates : Array[(String, String)],
  drop_spillover : Bool,
  drop_analysis : Bool,
  encoding : Encoding?,
) -> Bytes raise FcsError {
  let cs = channels.unwrap_or_else(() => {
    Array::makei(self.channels.length(), i => i)
  })
  let seen : Map[Int, Bool] = Map([])
  for c in cs {
    self.check_channel(c)
    if seen.contains(c) {
      raise Invalid("duplicate output channel")
    }
    seen[c] = true
  }
  let changed = cs.length() != self.channels.length() ||
    cs.mapi((i, c) => i != c).contains(true)
  if changed && !self.analysis.is_empty() && !drop_analysis {
    raise Invalid(
      "histogram projection invalidates ANALYSIS; explicitly drop_analysis",
    )
  }
  let meta = []
  for (key, value) in self.metadata {
    let k = key.to_upper()
    if k == "$CRC" || k == "$UNICODE" {
      continue
    }
    match parameter_key(k) {
      Some((old, suffix)) =>
        for i in 0..<cs.length() {
          if cs[i] == old - 1 {
            meta.push(("$P\{i+1}\{suffix}", value))
          }
        }
      None => meta.push((k, value))
    }
  }
  let shape = cs.map(c => self.histogram_shape_data[c])
  let frequencies = self.project_histogram(cs)
  let mut chosen = encoding.unwrap_or({
    kind: self.kind,
    widths: cs.map(c => self.channels[c].bits),
    order: self.order,
  })
  if encoding is None && self.mode == Correlated {
    if self.kind == Integer {
      let needed = frequencies.fold(init=1, (n, v) => {
        n.max(decimal_integer(v).bit_length())
      })
      chosen = { ..chosen, widths: chosen.widths.map(n => n.max(needed)), }
    } else if self.kind == Ascii && !chosen.widths.contains(0) {
      let needed = frequencies.fold(init=1, (n, v) => n.max(v.length()))
      chosen = { ..chosen, widths: chosen.widths.map(n => n.max(needed)), }
    } else if self.kind == Float32 &&
      frequencies.any(v => {
        !finite(Float::from_double(double_text(v)).to_double())
      }) {
      chosen = {
        kind: Float64,
        widths: Array::make(cs.length(), 64),
        order: self.order,
      }
    }
  }
  set_encoding_metadata(
    meta,
    cs.map(c => self.channels[c].name),
    shape.map(n => n.to_string()),
    chosen,
    self.mode,
    self.events,
    require_unique_names=false,
  )
  put(meta, "$TOT", self.total_events)
  self.sync_spillover(meta, cs, drop_spillover)
  if changed && !drop_spillover {
    self.sync_histogram_comp(meta, cs)
  }
  edits(meta, updates)
  assemble(
    meta,
    encode_fields(
      frequencies,
      histogram_widths(self.mode, shape, chosen.widths, chosen.kind),
      chosen.kind,
      chosen.order,
    ),
    if drop_analysis {
      []
    } else {
      self.analysis
    },
  )
}
