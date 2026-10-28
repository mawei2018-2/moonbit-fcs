///|
fn step(
  id : String,
  parent : String?,
  predicate : @fcs.GatePredicate,
) -> @fcs.GateStep {
  { id, parent, predicate, scaled: false, compensated: false, }
}

///|
fn main {
  let d = try! @fcs.parse(
    try! @fcs.create(
      ["X", "Y", "M", "ID"],
      [],
      integer_values=[
        "10", "1", "0", "18446744073709551616", "20", "2", "5", "18446744073709551617",
        "30", "3", "9", "18446744073709551618", "40", "4", "9", "18446744073709551619",
        "50", "5", "2", "18446744073709551620", "20", "4", "8", "18446744073709551621",
      ],
      encoding={
        kind: @fcs.Integer,
        widths: [8, 8, 8, 65],
        order: @fcs.BigEndian,
      },
    ),
  )
  let populations = try! d.gate_plan([
    step(
      "id_window",
      Some("shape"),
      @fcs.Exact([
        {
          channel: 3,
          lower: "18446744073709551618",
          upper: "18446744073709551622",
        },
      ]),
    ),
    step(
      "high",
      Some("window"),
      @fcs.Rectangle([{ channel: 2, lower: 8.0, upper: 10.0, }]),
    ),
    step(
      "window",
      None,
      @fcs.Rectangle([{ channel: 0, lower: 15.0, upper: 45.0, }]),
    ),
    step(
      "shape",
      Some("window"),
      @fcs.Polygon(0, 1, [(15.0, 0.0), (35.0, 0.0), (35.0, 5.0), (15.0, 5.0)]),
    ),
    step(
      "low",
      Some("window"),
      @fcs.Rectangle([{ channel: 2, lower: 0.0, upper: 6.0, }]),
    ),
  ])
  println(populations.to_json().stringify())
}
