///|
/// Reads one list-mode dataset. Offsets are relative to the dataset HEADER.
pub fn parse(
  data : Bytes,
  offset? : Int = 0,
  strict? : Bool = false,
  allow_exclusive_end? : Bool = false,
  latin1? : Bool = false,
  allow_text_padding? : Bool = false,
  allow_offset_padding? : Bool = false,
) -> Dataset raise FcsError {
  need(data, offset, 58)
  let version = ascii(data, offset, 6)
  if version != "FCS2.0" && version != "FCS3.0" && version != "FCS3.1" {
    raise Unsupported("FCS version \{version}")
  }
  let warnings : Array[String] = []
  if strict && latin1 {
    raise Invalid("strict mode cannot enable legacy Latin-1 fallback")
  }
  if strict && allow_text_padding {
    raise Invalid("strict mode cannot enable TEXT padding compatibility")
  }
  if strict && allow_offset_padding {
    raise Invalid("strict mode cannot enable offset padding compatibility")
  }
  if latin1 {
    warnings.push(
      "explicit UTF-8 to Latin-1 fallback enabled for legacy keyword values",
    )
  }
  if ascii(data, offset + 6, 4) != "    " {
    if strict {
      raise Invalid("HEADER reserved bytes are not spaces")
    }
    warnings.push("HEADER reserved bytes are not spaces")
  }
  let ts = header_offset(data, offset, 10)
  let te = header_offset(data, offset, 18)
  if ts < 58 {
    raise Invalid("TEXT overlaps HEADER")
  }
  need(data, offset, te + 1)
  let meta = read_segment(
    data,
    offset + ts,
    offset + te,
    None,
    latin1,
    allow_text_padding,
    warnings,
    "primary TEXT",
  )
  let strict_keys = [
    "$BEGINANALYSIS", "$ENDANALYSIS", "$BEGINSTEXT", "$ENDSTEXT", "$NEXTDATA",
  ]
  if version != "FCS2.0" {
    for key in strict_keys {
      if lookup(meta, key) == None {
        if strict {
          raise Invalid("missing required keyword \{key}")
        }
        warnings.push(
          "missing required keyword \{key}; treated as absent segment",
        )
      }
    }
  }
  let st = offset_number(
    lookup(meta, "$BEGINSTEXT").unwrap_or("0"),
    "$BEGINSTEXT",
    allow_offset_padding,
    warnings,
  )
  let se = offset_number(
    lookup(meta, "$ENDSTEXT").unwrap_or("0"),
    "$ENDSTEXT",
    allow_offset_padding,
    warnings,
  )
  if (st == 0) != (se == 0) {
    raise Invalid("incomplete supplemental TEXT range")
  }
  if st > 0 {
    if st < 58 || se < st || !(se < ts || st > te) {
      raise Invalid("overlapping supplemental TEXT")
    }
    need(data, offset, se + 1)
    merge_text(
      meta,
      read_segment(
        data,
        offset + st,
        offset + se,
        Some(data[offset + ts]),
        latin1,
        allow_text_padding,
        warnings,
        "supplemental TEXT",
      ),
    )
  }
  let mode = match required(meta, "$MODE") {
    "L" => ListMode
    "C" => Correlated
    "U" => Uncorrelated
    _ => raise Invalid("invalid FCS MODE")
  }
  let kind = match required(meta, "$DATATYPE") {
    "I" => Integer
    "F" => Float32
    "D" => Float64
    "A" => Ascii
    other => raise Unsupported("DATA type \{other}")
  }
  let order = match required(meta, "$BYTEORD") {
    "1,2,3,4" => LittleEndian
    "4,3,2,1" => BigEndian
    "1,2" | "2,1" as old => {
      if strict && version == "FCS3.1" {
        raise Invalid("legacy BYTEORD in FCS3.1")
      }
      warnings.push("legacy two-byte BYTEORD")
      if old == "1,2" {
        LittleEndian
      } else {
        BigEndian
      }
    }
    other => raise Unsupported("BYTEORD \{other}")
  }
  let count = natural(required(meta, "$PAR"))
  let total_events = required(meta, "$TOT")
  if decimal_integer(total_events).compare_int(0) < 0 {
    raise Invalid("negative event total")
  }
  let events = if mode == ListMode { natural(total_events) } else { 0 }
  if count < 1 {
    raise Invalid("PAR must be positive")
  }
  let channels : Array[Channel] = []
  let offsets = []
  let integer_masks = []
  let mut width = 0
  let names : Map[String, Bool] = Map([])
  for i = 1; i <= count; i = i + 1 {
    let name = required(meta, "$P\{i}N")
    if name.is_empty() {
      raise Invalid("empty channel name")
    }
    if names.contains(name) {
      if strict {
        raise Invalid("duplicate channel name \{name}")
      }
      warnings.push("duplicate channel name \{name}; use numeric indexes")
    }
    names[name] = true
    let stain = lookup(meta, "$P\{i}S").unwrap_or("")
    let bits_text = required(meta, "$P\{i}B")
    let bits = if kind == Ascii && bits_text == "*" {
      0
    } else {
      natural(bits_text)
    }
    if (kind == Float32 && bits != 32) || (kind == Float64 && bits != 64) {
      raise Invalid("floating DATA width does not match DATATYPE")
    }
    if kind == Integer && bits < 1 {
      raise Invalid("integer width must be positive")
    }
    if kind == Ascii && bits_text != "*" && bits < 1 {
      raise Invalid("ASCII character width must be positive or star")
    }
    if bits > 2147483647 - width {
      raise Invalid("event width cannot be indexed by this runtime")
    }
    let range = required(meta, "$P\{i}R")
    if kind == Integer || kind == Ascii {
      if decimal_integer(range).compare_int(0) <= 0 {
        raise Invalid("channel range must be positive")
      }
    } else {
      let positive = try decimal_integer(range).compare_int(0) > 0 catch {
        _ => number(range) > 0.0
      }
      if !positive {
        raise Invalid("channel range must be positive")
      }
    }
    integer_masks.push(
      if kind == Integer && mode == ListMode {
        integer_mask(range, bits)
      } else {
        @bigint.BigInt::from_int(0)
      },
    )
    let amp = match lookup(meta, "$P\{i}E") {
      Some(v) => v
      None => {
        if strict {
          raise Invalid("missing amplification metadata")
        }
        warnings.push("missing $P\{i}E; using linear amplification")
        "0,0"
      }
    }
    let amps = amp.split(",").map(s => s.to_owned()).to_array()
    if amps.length() != 2 {
      raise Invalid("invalid amplification pair")
    }
    let decades = number(amps[0])
    let mut zero = number(amps[1])
    if decades < 0.0 || zero < 0.0 || (decades == 0.0 && zero != 0.0) {
      raise Invalid("invalid amplification")
    }
    if decades > 0.0 && zero == 0.0 {
      if strict {
        raise Invalid("zero logarithmic baseline")
      }
      zero = 1.0
      warnings.push(
        "$P\{i}E logarithmic baseline 0 interpreted as 1 per FCS3.1 recommendation",
      )
    }
    if (kind == Float32 || kind == Float64) && (decades != 0.0 || zero != 0.0) {
      raise Invalid("floating-point DATA requires linear PnE=0,0")
    }
    let gain = number(lookup(meta, "$P\{i}G").unwrap_or("1"))
    if decades > 0.0 && gain != 1.0 {
      raise Invalid("gain must not combine with logarithmic amplification")
    }
    if gain <= 0.0 {
      if strict {
        raise Invalid("non-positive gain")
      }
      warnings.push("non-positive $P\{i}G: scaled access is unavailable")
    }
    offsets.push(width)
    width = width + bits
    channels.push({ name, stain, bits, range, decades, zero, gain, })
  }
  let hs = header_offset(data, offset, 26)
  let he = header_offset(data, offset, 34)
  let ds = if version == "FCS2.0" {
    hs
  } else {
    offset_number(
      required(meta, "$BEGINDATA"),
      "$BEGINDATA",
      allow_offset_padding,
      warnings,
    )
  }
  let declared_end = if version == "FCS2.0" {
    he
  } else {
    offset_number(
      required(meta, "$ENDDATA"),
      "$ENDDATA",
      allow_offset_padding,
      warnings,
    )
  }
  if (hs != 0 && hs != ds) || (he != 0 && he != declared_end) {
    raise Invalid("HEADER/TEXT DATA offset discrepancy")
  }
  let expected = if mode != ListMode {
    (declared_end - ds + 1).max(0)
  } else if kind == Ascii {
    if channels.any(c => c.bits == 0) {
      (declared_end - ds + 1).max(0)
    } else {
      if width > 0 && events > 2147483647 / width {
        raise Invalid("ASCII DATA size overflows runtime index")
      }
      events * width
    }
  } else {
    packed_length(events, width)
  }
  let mut de = declared_end
  if expected > 0 &&
    declared_end >= ds &&
    declared_end - ds == expected &&
    allow_exclusive_end {
    de = declared_end - 1
    warnings.push("accepted explicitly requested exclusive DATA end correction")
  }
  if ds < 58 ||
    (expected > 0 && (de < ds || de - ds + 1 != expected)) ||
    (expected == 0 && de != ds - 1) {
    raise Invalid("DATA extent does not match TOT/PAR/PnB")
  }
  need(data, offset + ds, expected)
  if expected > 0 &&
    (!(de < ts || ds > te) || (st > 0 && !(de < st || ds > se))) {
    raise Invalid("DATA overlaps TEXT")
  }
  let ahs = header_offset(data, offset, 42)
  let ahe = header_offset(data, offset, 50)
  let astart = offset_number(
    lookup(meta, "$BEGINANALYSIS").unwrap_or(ahs.to_string()),
    "$BEGINANALYSIS",
    allow_offset_padding,
    warnings,
  )
  let aend = offset_number(
    lookup(meta, "$ENDANALYSIS").unwrap_or(ahe.to_string()),
    "$ENDANALYSIS",
    allow_offset_padding,
    warnings,
  )
  if (astart == 0) != (aend == 0) ||
    (ahs != 0 && astart != ahs) ||
    (ahe != 0 && aend != ahe) {
    raise Invalid("ANALYSIS offset discrepancy")
  }
  let analysis = if astart > 0 {
    if astart < 58 ||
      aend < astart ||
      !(aend < ts || astart > te) ||
      (expected > 0 && !(aend < ds || astart > de)) ||
      (st > 0 && !(aend < st || astart > se)) {
      raise Invalid("ANALYSIS overlaps another segment")
    }
    need(data, offset, aend + 1)
    read_segment(
      data,
      offset + astart,
      offset + aend,
      Some(data[offset + ts]),
      latin1,
      allow_text_padding,
      warnings,
      "ANALYSIS",
    )
  } else {
    []
  }
  let next = offset_number(
    lookup(meta, "$NEXTDATA").unwrap_or("0"),
    "$NEXTDATA",
    allow_offset_padding,
    warnings,
  )
  if next > 0 {
    if next <= te || next <= de || next <= se || next <= aend {
      raise Invalid("NEXTDATA overlaps current dataset")
    }
    need(data, offset + next, 58)
  }
  let raw = part(data, offset + ds, expected)
  let fields = if kind == Ascii && mode == ListMode {
    ascii_fields(raw, channels, events)
  } else {
    []
  }
  let dataset = {
    version,
    channels,
    events,
    total_events,
    mode,
    histogram_shape_data: if mode == ListMode {
      []
    } else {
      channels.map(c => natural(c.range))
    },
    histogram_values: if mode == ListMode {
      []
    } else {
      decode_histogram(raw, mode, kind, order, channels)
    },
    compensation_cache: None,
    kind,
    order,
    metadata: meta,
    analysis,
    diagnostics: warnings,
    file_offset: offset,
    next_offset: next,
    raw,
    width,
    offsets,
    integer_masks,
    ascii_fields: fields,
  }
  dataset.validate_histogram_totals()
  ignore(dataset.spillover())
  dataset
}

///|
pub fn parse_all(
  data : Bytes,
  strict? : Bool = false,
  allow_exclusive_end? : Bool = false,
  latin1? : Bool = false,
  allow_text_padding? : Bool = false,
  allow_offset_padding? : Bool = false,
) -> Array[Dataset] raise FcsError {
  let result = []
  let mut offset = 0
  while true {
    let d = parse(
      data,
      offset~,
      strict~,
      allow_exclusive_end~,
      latin1~,
      allow_text_padding~,
      allow_offset_padding~,
    )
    result.push(d)
    if d.next_offset == 0 {
      break
    }
    offset = offset + d.next_offset
  }
  result
}
