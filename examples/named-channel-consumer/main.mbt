///|
fn main {
  let d = try! @fcs.parse(
    try! @fcs.create(
      ["SSC-A", "ID", "FSC-A"],
      [],
      integer_values=[
        "100", "18446744073709551616", "10", "10", "18446744073709551617", "20",
        "200", "18446744073709551618", "30",
      ],
      encoding={
        kind: @fcs.Integer,
        widths: [8, 65, 8],
        order: @fcs.LittleEndian,
      },
    ),
  )
  let x = try! d.channel_index("FSC-A")
  let id = try! d.channel_index("ID")
  let populations = try! d.gate_plan([
    {
      id: "window",
      parent: None,
      predicate: @fcs.Rectangle([{ channel: x, lower: 15.0, upper: 35.0, }]),
      scaled: false,
      compensated: false,
    },
    {
      id: "exact",
      parent: Some("window"),
      predicate: @fcs.Exact([
        {
          channel: id,
          lower: "18446744073709551618",
          upper: "18446744073709551619",
        },
      ]),
      scaled: false,
      compensated: false,
    },
  ])
  let selected = try! @fcs.parse(
    try! d.write(event_indices=populations[1].event_indices, channel_indices=[
      id, x,
    ]),
    strict=true,
  )
  let result : Json = {
    "populations": populations.to_json(),
    "fsc_index": x.to_json(),
    "selected_values": [
      try! selected.integer_text(0, 0),
      try! selected.integer_text(0, 1),
    ].to_json(),
  }
  println(result.stringify())
}
