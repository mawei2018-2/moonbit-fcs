///|
pub(all) enum GatePredicate {
  Rectangle(Array[Bounds])
  Polygon(Int, Int, Array[(Double, Double)])
  Exact(Array[IntegerBounds])
  AllOf(Array[String])
  AnyOf(Array[String])
  Not(String)
} derive(Debug)

///|
pub extend GatePredicate with @debug.Debug::{to_repr}

///|
/// A unique ID and optional parent describe a single-parent hierarchy.
/// Boolean references add dependencies on other completed populations.
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
  referenced : Array[Array[Int]],
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
    AllOf(_) | AnyOf(_) => {
      let is_intersection = match self.predicate {
        AllOf(_) => true
        _ => false
      }
      let membership = Array::make(dataset.events, is_intersection)
      for hits in referenced {
        if is_intersection {
          let present = Array::make(dataset.events, false)
          for event in hits {
            present[event] = true
          }
          for event in 0..<dataset.events {
            membership[event] = membership[event] && present[event]
          }
        } else {
          for event in hits {
            membership[event] = true
          }
        }
      }
      Array::makei(dataset.events, event => event).filter(event => {
        membership[event]
      })
    }
    Not(_) => {
      let membership = Array::make(dataset.events, true)
      for event in referenced[0] {
        membership[event] = false
      }
      Array::makei(dataset.events, event => event).filter(event => {
        membership[event]
      })
    }
  }
}

///|
fn GateStep::boolean_references(
  self : GateStep,
) -> Array[String] raise FcsError {
  match self.predicate {
    AllOf(references) | AnyOf(references) => {
      if self.scaled || self.compensated {
        raise Invalid(
          "Boolean gate view flags must be false; choose views on source gates",
        )
      }
      if references.is_empty() {
        raise Invalid("Boolean gates require nonempty references")
      }
      references
    }
    Not(reference) => {
      if self.scaled || self.compensated {
        raise Invalid(
          "Boolean gate view flags must be false; choose views on source gates",
        )
      }
      [reference]
    }
    _ => []
  }
}

///|
/// Evaluate predicates and Boolean membership references, then intersect with
/// each declared parent. Forward references and geometric children of Boolean
/// gates are supported through one parent/reference DAG. Results retain the
/// input plan order. Empty parents never hide invalid predicates or references.
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
  let references = steps.map(step => {
    let resolved : Array[Int] = []
    for name in step.boolean_references() {
      let index = match ids.get(name) {
        Some(index) => index
        None => raise Invalid("unknown Boolean gate reference: \{name}")
      }
      if !resolved.contains(index) {
        resolved.push(index)
      }
    }
    resolved
  })
  let dependents : Array[Array[Int]] = Array::makei(steps.length(), _ => [])
  let pending : Array[Int] = Array::make(steps.length(), 0)
  let ready : Array[Int] = []
  for i in 0..<steps.length() {
    let dependencies = references[i].copy()
    match parents[i] {
      None => ()
      Some(parent) =>
        if !dependencies.contains(parent) {
          dependencies.push(parent)
        }
    }
    pending[i] = dependencies.length()
    for dependency in dependencies {
      dependents[dependency].push(i)
    }
    if dependencies.is_empty() {
      ready.push(i)
    }
  }
  let populations : Array[Population?] = Array::make(steps.length(), None)
  let mut cursor = 0
  while cursor < ready.length() {
    let i = ready[cursor]
    cursor += 1
    let step = steps[i]
    // Evaluate before intersection so an empty parent cannot hide a bad gate.
    let hits = step.evaluate(
      self,
      references[i].map(reference => {
        populations[reference].unwrap().event_indices
      }),
    )
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
    for dependent in dependents[i] {
      pending[dependent] -= 1
      if pending[dependent] == 0 {
        ready.push(dependent)
      }
    }
  }
  if cursor != steps.length() {
    raise Invalid(
      if references.any(refs => !refs.is_empty()) {
        "gate plan contains a parent/Boolean dependency cycle"
      } else {
        "gate plan contains a parent cycle"
      },
    )
  }
  populations.map(population => population.unwrap())
}
