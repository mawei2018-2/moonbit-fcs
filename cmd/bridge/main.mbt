///|
extern "js" fn fail_bytes(message : String) -> Bytes =
  #| (message) => { throw new Error(message); }

///|
extern "js" fn fail_string(message : String) -> String =
  #| (message) => { throw new Error(message); }

///|
extern "js" fn fail_dataset(message : String) -> @lib.Dataset =
  #| (message) => { throw new Error(message); }

///|
pub fn load(data : Bytes, options : String) -> @lib.Dataset {
  dataset(data, object(options)) catch {
    e => fail_dataset(@debug.to_string(e))
  }
}

///|
pub fn query(d : @lib.Dataset, options : String) -> String {
  do_query(d, object(options)) catch {
    e => fail_string(@debug.to_string(e))
  }
}

///|
fn object(text : String) -> Map[String, Json] raise {
  match @json.parse(text) {
    Object(o) => {
      // core/json's Int decoder truncates fractions. Event and channel IDs
      // must be exact so a malformed request cannot select different data.
      for
        key in [
          "dataset", "start", "count", "x", "y", "axis", "channel", "events_count",
        ] {
        if o.get(key) is Some(value) {
          exact_index(value)
        }
      }
      for key in ["events", "bins", "shape"] {
        match o.get(key) {
          None | Some(Null) => ()
          Some(Array(values)) => values.each(exact_index)
          _ => raise Failure(key + " must be an array of exact integers")
        }
      }
      match o.get("channels") {
        None | Some(Null) => ()
        Some(Array(values)) =>
          values.each(value => {
            match value {
              String(_) => () // Resolve exact PnN labels after loading DATA metadata.
              _ => exact_index(value)
            }
          })
        _ => raise Failure("channels must be an array of indices or PnN names")
      }
      let selectors = [
        "events", "bounds", "vertices", "integer_bounds", "population",
      ].filter(key => {
        match o.get(key) {
          None | Some(Null) => false
          _ => true
        }
      })
      if selectors.length() > 1 {
        raise Failure(
          "choose exactly one event selector: events, bounds or vertices",
        )
      }
      o
    }
    _ => raise Failure("options must be an object")
  }
}

///|
fn exact_index(value : Json) -> Unit raise {
  guard value is Number(n, ..) &&
    !n.is_nan() &&
    !n.is_inf() &&
    n == n.trunc() &&
    n >= -2147483648.0 &&
    n <= 2147483647.0 else {
    raise Failure("event/channel/range indices must be exact 32-bit integers")
  }
}

///|
fn[T : @json.FromJson] required(o : Map[String, Json], key : String) -> T raise {
  match o.get(key) {
    Some(j) => @json.from_json(j)
    None => raise Failure("missing option: " + key)
  }
}

///|
fn[T : @json.FromJson] optional(
  o : Map[String, Json],
  key : String,
  fallback : T,
) -> T raise {
  match o.get(key) {
    Some(j) => @json.from_json(j)
    None => fallback
  }
}

///|
fn[T : @json.FromJson] maybe(o : Map[String, Json], key : String) -> T? raise {
  match o.get(key) {
    Some(Null) | None => None
    Some(j) => Some(@json.from_json(j))
  }
}

///|
fn dataset(data : Bytes, o : Map[String, Json]) -> @lib.Dataset raise {
  let all = @lib.parse_all(
    data,
    strict=optional(o, "strict", false),
    allow_exclusive_end=optional(o, "allow_exclusive_end", false),
    latin1=optional(o, "latin1", false),
    allow_text_padding=optional(o, "allow_text_padding", false),
    allow_offset_padding=optional(o, "allow_offset_padding", false),
  )
  let i : Int = optional(o, "dataset", 0)
  if i < 0 || i >= all.length() {
    raise Failure("dataset index out of bounds")
  }
  all[i]
}

///|
fn channel_reference(d : @lib.Dataset, value : Json) -> Int raise {
  match value {
    String(name) => d.channel_index(name)
    _ => {
      exact_index(value)
      let index : Int = @json.from_json(value)
      if index < 0 || index >= d.channel_info().length() {
        raise Failure("channel index out of bounds")
      }
      index
    }
  }
}

///|
fn channel_array(d : @lib.Dataset, value : Json) -> Array[Int] raise {
  let references : Array[Json] = @json.from_json(value)
  references.map(value => channel_reference(d, value))
}

///|
fn report_channels(d : @lib.Dataset, o : Map[String, Json]) -> Array[Int] raise {
  match o.get("channels") {
    None => Array::makei(d.channel_info().length(), i => i)
    Some(value) => channel_array(d, value)
  }
}

///|
fn gate_steps(
  d : @lib.Dataset,
  o : Map[String, Json],
) -> Array[@lib.GateStep] raise {
  if o.contains("scaled") || o.contains("compensated") {
    raise Failure("gate plan view flags belong to each step")
  }
  let rows : Array[Map[String, Json]] = required(o, "gates")
  rows.map(row => {
    let allowed = [
      "id", "parent", "bounds", "vertices", "x", "y", "integer_bounds", "scaled",
      "compensated",
    ]
    for key in row.keys() {
      if !allowed.contains(key) {
        raise Failure("unknown gate step option: " + key)
      }
    }
    let predicates = ["bounds", "vertices", "integer_bounds"].filter(key => {
      row.contains(key)
    })
    if predicates.length() != 1 {
      raise Failure("gate step requires exactly one predicate")
    }
    if !row.contains("vertices") && (row.contains("x") || row.contains("y")) {
      raise Failure("x/y apply only to polygon gate steps")
    }
    let predicate : @lib.GatePredicate = if row.contains("integer_bounds") {
      let bounds : Array[Map[String, Json]] = required(row, "integer_bounds")
      @lib.Exact(
        bounds.map(b => {
          let channel : Json = required(b, "channel")
          @lib.IntegerBounds::{
            channel: channel_reference(d, channel),
            lower: required(b, "lower"),
            upper: required(b, "upper"),
          }
        }),
      )
    } else if row.contains("bounds") {
      let bounds : Array[Array[Json]] = required(row, "bounds")
      @lib.Rectangle(
        bounds.map(b => {
          if b.length() != 3 {
            raise Failure("gate bounds must be [channel,lower,upper]")
          }
          @lib.Bounds::{
            channel: channel_reference(d, b[0]),
            lower: @json.from_json(b[1]),
            upper: @json.from_json(b[2]),
          }
        }),
      )
    } else {
      let x : Json = required(row, "x")
      let y : Json = required(row, "y")
      @lib.Polygon(
        channel_reference(d, x),
        channel_reference(d, y),
        required(row, "vertices"),
      )
    }
    @lib.GateStep::{
      id: required(row, "id"),
      parent: maybe(row, "parent"),
      predicate,
      scaled: optional(row, "scaled", false),
      compensated: optional(row, "compensated", false),
    }
  })
}

///|
fn selected(d : @lib.Dataset, o : Map[String, Json]) -> Array[Int]? raise {
  if o.contains("gates") || o.contains("population") {
    let id : String = required(o, "population")
    let populations = d.gate_plan(gate_steps(d, o))
    for population in populations {
      if population.id == id {
        return Some(population.event_indices)
      }
    }
    raise Failure("unknown population: " + id)
  }
  if o.contains("bounds") && o.contains("vertices") {
    raise Failure("choose rectangle or polygon, not both")
  }
  if o.contains("integer_bounds") {
    let rows : Array[Map[String, Json]] = required(o, "integer_bounds")
    let bounds : Array[@lib.IntegerBounds] = rows.map(b => {
      let index : Json = required(b, "channel")
      exact_index(index)
      {
        channel: required(b, "channel"),
        lower: required(b, "lower"),
        upper: required(b, "upper"),
      }
    })
    return Some(d.rectangle_exact(bounds))
  }
  if o.contains("bounds") {
    let rows : Array[Array[Double]] = required(o, "bounds")
    let bounds = rows.map(row => {
      if row.length() != 3 ||
        row[0] != row[0].trunc() ||
        row[0] < 0.0 ||
        row[0] > 2147483647.0 {
        raise Failure("bounds rows must be [channel,lower,upper]")
      }
      @lib.Bounds::{ channel: row[0].to_int(), lower: row[1], upper: row[2], }
    })
    return Some(
      d.rectangle(
        bounds,
        scaled=optional(o, "scaled", false),
        compensated=optional(o, "compensated", false),
      ),
    )
  }
  if o.contains("vertices") {
    let vertices : Array[(Double, Double)] = required(o, "vertices")
    return Some(
      d.polygon(
        required(o, "x"),
        required(o, "y"),
        vertices,
        scaled=optional(o, "scaled", false),
        compensated=optional(o, "compensated", false),
      ),
    )
  }
  let events : Array[Int]? = maybe(o, "events")
  if events is Some(indices) {
    for event in indices {
      if event < 0 || event >= d.events {
        raise Failure("selected event out of bounds")
      }
    }
  }
  events
}

///|
fn do_query(d : @lib.Dataset, o : Map[String, Json]) -> String raise {
  let cmd : String = optional(o, "command", "inspect")
  if d.mode != @lib.ListMode &&
    ["values", "stats", "selected-stats", "gate", "populations"].contains(cmd) {
    raise Failure("event queries require list DATA; use histogram APIs")
  }
  let result : Json = match cmd {
    "inspect" | "validate" =>
      {
        "version": d.version.to_json(),
        "events": if d.mode == @lib.ListMode {
          d.events.to_json()
        } else {
          d.total_events.to_json()
        },
        "mode": d.mode.to_json(),
        "channels": d.channel_info().to_json(),
        "datatype": d.kind.to_json(),
        "byte_order": d.order.to_json(),
        "warnings": d.warnings().to_json(),
        "spillover": d.spillover().to_json(),
        "next_offset": d.next_offset.to_json(),
        "timestep": d.keyword("$TIMESTEP").to_json(),
      }
    "histogram" =>
      {
        "shape": d.histogram_shape().to_json(),
        "frequencies": d.histogram_frequencies().to_json(),
      }
    "histogram-axis" => d.histogram_axis(required(o, "channel")).to_json()
    "histogram-bin" =>
      d
      .histogram_frequency(required(o, "bins"), axis=optional(o, "axis", 0))
      .to_json()
    "compensation" =>
      match d.spillover() {
        Some(matrix) => matrix.inverse().to_json()
        None => ().to_json()
      }
    "metadata" => d.keywords().to_json()
    "stats" =>
      Array::makei(d.channel_info().length(), i => {
        d.statistics(
          i,
          scaled=optional(o, "scaled", false),
          compensated=optional(o, "compensated", false),
        )
      }).to_json()
    "selected-stats" => {
      // Keep the complete Dataset for compensation dependencies, but do not
      // evaluate unrelated output calibrations. Duplicate reports reuse JSON.
      let scaled = optional(o, "scaled", false)
      let compensated = optional(o, "compensated", false)
      let cache : Map[Int, Json] = Map([])
      report_channels(d, o)
      .map(channel => {
        match cache.get(channel) {
          Some(statistic) => statistic
          None => {
            let statistic = d
              .statistics(channel, scaled~, compensated~)
              .to_json()
            cache[channel] = statistic
            statistic
          }
        }
      })
      .to_json()
    }
    "populations" => d.gate_plan(gate_steps(d, o)).to_json()
    // The Node CSV adapter uses the same MoonBit resolution as values.
    "channel-indices" => report_channels(d, o).to_json()
    "gate" =>
      match selected(d, o) {
        Some(es) => es.to_json()
        None => raise Failure("gate requires bounds or vertices")
      }
    "values" => {
      let start : Int = optional(o, "start", 0)
      let count : Int = optional(o, "count", (d.events - start).min(10))
      let cs = report_channels(d, o)
      if start < 0 ||
        start > d.events ||
        count < 0 ||
        count > d.events - start ||
        cs.is_empty() {
        raise Failure("values range exceeds dataset or 100000 sample chunk")
      }
      Array::makei(count, i => {
        cs.map(c => {
          if optional(
              o,
              "exact_integers",
              (d.kind == @lib.Integer || d.kind == @lib.Ascii) &&
              !optional(o, "scaled", false) &&
              !optional(o, "compensated", false),
            ) {
            if optional(o, "scaled", false) || optional(o, "compensated", false) {
              raise Failure("exact integer output applies to raw values")
            }
            return d.integer_text(start + i, c).to_json()
          }
          let v = d.value(
            start + i,
            c,
            scaled=optional(o, "scaled", false),
            compensated=optional(o, "compensated", false),
          )
          if v.is_nan() {
            Json::string("NaN")
          } else if v.is_inf() {
            Json::string(if v > 0.0 { "Infinity" } else { "-Infinity" })
          } else {
            v.to_json()
          }
        })
      }).to_json()
    }
    _ => raise Failure("unknown report command")
  }
  result.stringify()
}

///|
pub fn report(data : Bytes, options : String) -> String {
  let o = object(options) catch { e => return fail_string(@debug.to_string(e)) }
  do_query(dataset(data, o), o) catch {
    e => fail_string(@debug.to_string(e))
  }
}

///|
fn do_transform(data : Bytes, text : String) -> Bytes raise {
  let o = object(text)
  let cmd : String = optional(o, "command", "rewrite")
  let encoding : @lib.Encoding? = match o.get("encoding") {
    None | Some(Null) => None
    Some(value) => {
      let e : Map[String, Json] = @json.from_json(value)
      let widths : Array[Json] = required(e, "widths")
      widths.each(exact_index)
      let kind = match required(e, "datatype") {
        "I" => @lib.Integer
        "A" => @lib.Ascii
        "F" => @lib.Float32
        "D" => @lib.Float64
        _ => raise Failure("invalid datatype")
      }
      Some({
        kind,
        widths: required(e, "widths"),
        order: if optional(e, "big_endian", false) {
          @lib.BigEndian
        } else {
          @lib.LittleEndian
        },
      })
    }
  }
  if cmd == "create-histogram" {
    if encoding is None {
      raise Failure("histogram requires encoding")
    }
    let mode = match required(o, "mode") {
      "C" => @lib.Correlated
      "U" => @lib.Uncorrelated
      _ => raise Failure("histogram mode must be C or U")
    }
    return @lib.create_histogram(
      required(o, "names"),
      required(o, "shape"),
      required(o, "frequencies"),
      mode~,
      encoding=encoding.unwrap(),
      events=optional(o, "events_count", -1),
      total_events?=maybe(o, "total_events"),
      metadata=optional(o, "metadata", []),
    )
  }
  if cmd == "create" {
    let spillover : @lib.Spillover? = match o.get("spillover") {
      None | Some(Null) => None
      Some(value) => {
        let m : Map[String, Json] = @json.from_json(value)
        Some({
          channels: required(m, "channels"),
          coefficients: required(m, "coefficients"),
        })
      }
    }
    return @lib.create(
      required(o, "names"),
      optional(o, "values", []),
      integer_values?=maybe(o, "integer_values"),
      encoding?,
      ranges?=maybe(o, "ranges"),
      spillover?,
      double_precision=optional(o, "double_precision", false),
      order=if optional(o, "big_endian", false) {
        @lib.BigEndian
      } else {
        @lib.LittleEndian
      },
      metadata=optional(o, "metadata", []),
    )
  }
  if cmd != "rewrite" && cmd != "subset" {
    raise Failure("unknown transform command")
  }
  let d = dataset(data, o)
  let channels = match o.get("channels") {
    None | Some(Null) => None
    Some(value) => Some(channel_array(d, value))
  }
  d.write(
    event_indices?=selected(d, o),
    channel_indices?=channels,
    updates=optional(o, "metadata", []),
    drop_spillover=optional(o, "drop_spillover", false),
    drop_analysis=optional(o, "drop_analysis", false),
    encoding?,
  )
}

///|
pub fn transform(data : Bytes, options : String) -> Bytes {
  do_transform(data, options) catch {
    e => fail_bytes(@debug.to_string(e))
  }
}

///|
fn main {

}
