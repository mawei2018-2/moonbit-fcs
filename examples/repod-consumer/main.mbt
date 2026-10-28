///|
fn main raise {
  let bytes = @base64.decode(fixture()[:])
  let data = @fcs.parse(bytes, allow_offset_padding=true)
  let indices = data.rectangle([
    @fcs.Bounds::{ channel: 0, lower: 500000.0, upper: 1000000.0, },
  ])
  let selected = data.write(
    event_indices=indices,
    channel_indices=[2, 0, 1],
    drop_spillover=true,
    drop_analysis=true,
  )
  let output = @fcs.parse(selected, strict=true)
  let original_offsets = [
    "$BEGINSTEXT", "$ENDSTEXT", "$BEGINANALYSIS", "$ENDANALYSIS",
  ].map(key => (key, data.keyword(key).unwrap()))
  let values = Array::makei(output.events, row => {
    Array::makei(3, column => output.value(row, column))
  })
  let report : Json = {
    "sourceEvents": data.events.to_json(),
    "sourceChannels": data.channel_info().length().to_json(),
    "sourceWarnings": data.warnings().to_json(),
    "originalOffsetMetadata": original_offsets.to_json(),
    "indices": indices.to_json(),
    "outputChannels": output.channel_info().to_json(),
    "selectedValues": values.to_json(),
    "encodedOutput": @base64.encode(selected[:]).to_json(),
    "outputWarnings": output.warnings().to_json(),
  }
  println(report.stringify())
}
