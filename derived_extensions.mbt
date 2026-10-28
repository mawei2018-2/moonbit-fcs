///|
pub extend Bounds with @moonbitlang/core/debug.Debug::{to_repr}

///|
pub extend ByteOrder with @moonbitlang/core/debug.Debug::{to_repr}

///|
pub extend ByteOrder with Eq::{not_equal, equal}

///|
pub extend ByteOrder with ToJson::{to_json}

///|
pub extend Channel with @moonbitlang/core/debug.Debug::{to_repr}

///|
pub extend Channel with ToJson::{to_json}

///|
pub extend ChannelStats with @moonbitlang/core/debug.Debug::{to_repr}

///|
pub extend ChannelStats with ToJson::{to_json}

///|
pub extend Dataset with @moonbitlang/core/debug.Debug::{to_repr}

///|
pub extend FcsError with @moonbitlang/core/debug.Debug::{to_repr}

///|
pub extend NumberType with @moonbitlang/core/debug.Debug::{to_repr}

///|
pub extend NumberType with Eq::{not_equal, equal}

///|
pub extend NumberType with ToJson::{to_json}

///|
pub extend Spillover with @moonbitlang/core/debug.Debug::{to_repr}

///|
pub extend Spillover with ToJson::{to_json}
