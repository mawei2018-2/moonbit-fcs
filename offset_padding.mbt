///|
// FCS 3.1 section 3.2.17 forbids padding numerical TEXT values. This explicit
// compatibility path only covers segment offsets; other numbers stay strict.
fn offset_number(
  raw : String,
  key : String,
  allow : Bool,
  warnings : Array[String],
) -> Int raise FcsError {
  let mut first = 0
  let mut last = raw.length()
  if allow {
    while first < last && raw[first] == ' ' {
      first = first + 1
    }
    while last > first && raw[last - 1] == ' ' {
      last = last - 1
    }
  }
  let value = natural(raw[first:last].to_owned())
  if first != 0 || last != raw.length() {
    warnings.push("accepted explicitly requested ASCII space padding in \{key}")
  }
  value
}
