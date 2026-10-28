///|
pub(all) enum GatePredicate {
  Rectangle(Array[Bounds])
  Polygon(Int, Int, Array[(Double, Double)])
  Exact(Array[IntegerBounds])
} derive(Debug)

///|
pub extend GatePredicate with @debug.Debug::{to_repr}

///|
/// A unique ID and optional parent ID describe a single-parent gate forest.
/// Exact predicates use raw integers and require both view flags to be false.
pub(all) struct GateStep {
  id : String
  parent : String?
  predicate : GatePredicate
  scaled : Bool
  compensated : Bool
} derive(Debug)

///|
pub extend GateStep with @debug.Debug::{to_repr}

///|
/// Indices always refer to the original Dataset, in ascending order.
/// Fractions are absent when their denominator is zero.
pub struct Population {
  id : String
  parent : String?
  event_indices : Array[Int]
  count : Int
  parent_count : Int
  total_count : Int
  parent_fraction : Double?
  total_fraction : Double?
} derive(Debug, ToJson)

///|
pub extend Population with @debug.Debug::{to_repr}

///|
pub extend Population with ToJson::{to_json}

///|
/// Resolve an exact PnN label. Duplicate labels remain usable by numeric index,
/// but cannot be chosen by name without ambiguity.
pub fn Dataset::channel_index(
  self : Dataset,
  name : String,
) -> Int raise FcsError {
  let mut found = -1
  for i in 0..<self.channels.length() {
    if self.channels[i].name == name {
      if found >= 0 {
        raise Invalid("ambiguous channel name: \{name}")
      }
      found = i
    }
  }
  if found < 0 {
    raise Invalid("unknown channel name: \{name}")
  }
  found
}

///|
fn GateStep::evaluate(
  self : GateStep,
  dataset : Dataset,
) -> Array[Int] raise FcsError {
  match self.predicate {
    Rectangle(bounds) =>
      dataset.rectangle(
        bounds,
        scaled=self.scaled,
        compensated=self.compensated,
      )
    Polygon(x, y, vertices) =>
      dataset.polygon(
        x,
        y,
        vertices,
        scaled=self.scaled,
        compensated=self.compensated,
      )
    Exact(bounds) => {
      if self.scaled || self.compensated || bounds.is_empty() {
        raise Invalid("exact gate steps require nonempty raw integer bounds")
      }
      dataset.rectangle_exact(bounds)
    }
  }
}

///|
/// Evaluate named gates as parent intersections. Forward references and
/// branches are supported; results retain the input plan order. Every step's
/// predicate is validated even when its parent selects no events.
pub fn Dataset::gate_plan(
  self : Dataset,
  steps : Array[GateStep],
) -> Array[Population] raise FcsError {
  if self.mode != ListMode {
    raise Invalid("gate plans require list DATA")
  }
  let ids : Map[String, Int] = Map([])
  for i in 0..<steps.length() {
    let id = steps[i].id
    if id.is_empty() || ids.contains(id) {
      raise Invalid("gate step IDs must be unique and nonempty: \{id}")
    }
    ids[id] = i
  }
  let parents = steps.map(step => {
    match step.parent {
      None => None
      Some(parent) =>
        match ids.get(parent) {
          Some(index) => Some(index)
          None => raise Invalid("unknown parent gate: \{parent}")
        }
    }
  })
  let children : Array[Array[Int]] = Array::makei(steps.length(), _ => [])
  let ready : Array[Int] = []
  for i in 0..<steps.length() {
    match parents[i] {
      None => ready.push(i)
      Some(parent) => children[parent].push(i)
    }
  }
  let populations : Array[Population?] = Array::make(steps.length(), None)
  let mut cursor = 0
  while cursor < ready.length() {
    let i = ready[cursor]
    cursor += 1
    let step = steps[i]
    // Evaluate before intersection so an empty parent cannot hide a bad gate.
    let hits = step.evaluate(self)
    let (event_indices, parent_count) = match parents[i] {
      None => (hits, self.events)
      Some(parent) => {
        let parent_events = populations[parent].unwrap().event_indices
        let membership = Array::make(self.events, false)
        for event in parent_events {
          membership[event] = true
        }
        (hits.filter(event => membership[event]), parent_events.length())
      }
    }
    let count = event_indices.length()
    populations[i] = Some({
      id: step.id,
      parent: step.parent,
      event_indices,
      count,
      parent_count,
      total_count: self.events,
      parent_fraction: if parent_count == 0 {
        None
      } else {
        Some(count.to_double() / parent_count.to_double())
      },
      total_fraction: if self.events == 0 {
        None
      } else {
        Some(count.to_double() / self.events.to_double())
      },
    })
    ready.append(children[i])
  }
  if cursor != steps.length() {
    raise Invalid("gate plan contains a parent cycle")
  }
  populations.map(population => population.unwrap())
}
