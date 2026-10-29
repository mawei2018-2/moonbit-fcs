///|
fn number(value : Double) -> Json {
  if value != value {
    "NaN".to_json()
  } else if (value.reinterpret_as_uint64() & 0x7ff0000000000000UL) ==
    0x7ff0000000000000UL {
    (if value > 0.0 { "Infinity" } else { "-Infinity" }).to_json()
  } else {
    value.to_json()
  }
}

///|
fn main {
  let reports = fixtures().map(pair => {
    let (id, bytes) = pair
    let d = try! @fcs.parse(bytes)
    let values = Array::makei(d.events, event => {
      Array::makei(d.channel_info().length(), channel => {
        try! d.value(event, channel, compensated=true)
      })
    })
    let report : Json = {
      "id": id.to_json(),
      "inverse": (try! (try! d.spillover()).unwrap().inverse()).to_json(),
      "values": values.map(row => row.map(number)).to_json(),
      "bits": values
      .map(row => {
        row.map(value => {
          if value != value {
            "NaN"
          } else {
            value.reinterpret_as_uint64().to_string()
          }
        })
      })
      .to_json(),
    }
    report
  })
  println(reports.to_json().stringify())
}
