///|
fn main {
  let source = try! @fcs.parse(fixture())
  let result = try! source.gate_plan(plan())
  let selected = try! @fcs.parse(
    try! source.write(
      event_indices=result[2].event_indices,
      channel_indices=[2, 1],
      drop_analysis=true,
    ),
  )
  let report : Json = {
    "populations": result.to_json(),
    "selectedValues": Array::makei(selected.events, event => {
      [
        try! selected.integer_text(event, 0),
        try! selected.integer_text(event, 1),
      ]
    }).to_json(),
  }
  println(report.stringify())
}
