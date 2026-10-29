///|
fn main {
  let source = try! @fcs.parse(fixture())
  let d = try! @fcs.parse(
    try! source.write(event_indices=[1, 2, 3, 4, 5, 6], drop_analysis=true),
  )
  let probabilities = [1.0, 0.5, 0.0, 0.25, 0.75, 0.5]
  let report : Json = {
    "raw": (try! d.quantiles(1, probabilities)).to_json(),
    "scaled": (try! d.quantiles(1, probabilities, scaled=true)).to_json(),
    "compensated": (try! d.quantiles(1, probabilities, compensated=true)).to_json(),
  }
  println(report.stringify())
}
