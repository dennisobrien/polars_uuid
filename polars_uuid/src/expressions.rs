#![allow(clippy::unused_unit)]
use polars::prelude::*;
use pyo3_polars::derive::polars_expr;
use serde::Deserialize;
use std::fmt::Write;
use uuid::Uuid;

// Length-only input: the output doesn't depend on the input values, only on
// how many rows to produce. Note this means the same expression instance
// evaluated twice via CSE would be deduplicated by polars, so avoid reusing
// a single `uuid4(...)` expression to populate more than one column.
#[polars_expr(output_type=String)]
fn uuid4(inputs: &[Series]) -> PolarsResult<Series> {
    let len = inputs[0].len();
    let out: StringChunked = (0..len)
        .map(|_| Some(Uuid::new_v4().to_string()))
        .collect_ca(PlSmallStr::EMPTY);
    Ok(out.into_series())
}

// Length-only input; see the note on `uuid4` above — the same CSE caveat applies.
#[polars_expr(output_type=String)]
fn uuid7(inputs: &[Series]) -> PolarsResult<Series> {
    let len = inputs[0].len();
    let out: StringChunked = (0..len)
        .map(|_| Some(Uuid::now_v7().to_string()))
        .collect_ca(PlSmallStr::EMPTY);
    Ok(out.into_series())
}

#[derive(Deserialize)]
struct Uuid5Kwargs {
    namespace: String,
}

#[polars_expr(output_type=String)]
fn uuid5(inputs: &[Series], kwargs: Uuid5Kwargs) -> PolarsResult<Series> {
    let ca: &StringChunked = inputs[0].str()?;
    let namespace = Uuid::parse_str(&kwargs.namespace).map_err(|e| {
        PolarsError::ComputeError(
            format!("invalid `namespace` UUID {:?}: {e}", kwargs.namespace).into(),
        )
    })?;
    let out: StringChunked = ca.apply_into_string_amortized(|value: &str, output: &mut String| {
        write!(output, "{}", Uuid::new_v5(&namespace, value.as_bytes())).unwrap()
    });
    Ok(out.into_series())
}

// Null (not `false`) for null input, so "unknown" stays distinguishable from "invalid".
#[polars_expr(output_type=Boolean)]
fn is_valid_uuid(inputs: &[Series]) -> PolarsResult<Series> {
    let ca: &StringChunked = inputs[0].str()?;
    let out: BooleanChunked = ca
        .iter()
        .map(|opt_v: Option<&str>| opt_v.map(|v| Uuid::parse_str(v).is_ok()))
        .collect_ca(PlSmallStr::EMPTY);
    Ok(out.into_series())
}

// UInt8/Int8 aren't compiled in without the `dtype-u8`/`dtype-i8` polars
// features, so UInt32 is used here — version numbers are tiny (1-8) either way.
#[polars_expr(output_type=UInt32)]
fn uuid_version(inputs: &[Series]) -> PolarsResult<Series> {
    let ca: &StringChunked = inputs[0].str()?;
    let out: UInt32Chunked = ca
        .iter()
        .map(|opt_v: Option<&str>| {
            opt_v
                .and_then(|v| Uuid::parse_str(v).ok())
                .map(|u| u.get_version_num() as u32)
        })
        .collect_ca(PlSmallStr::EMPTY);
    Ok(out.into_series())
}

fn extract_timestamp_output(input_fields: &[Field]) -> PolarsResult<Field> {
    Ok(Field::new(
        input_fields[0].name.clone(),
        DataType::Datetime(TimeUnit::Milliseconds, None),
    ))
}

// Null for invalid UUIDs, null input, or UUID versions without an embedded
// timestamp (only v1, v6, and v7 carry one).
#[polars_expr(output_type_func=extract_timestamp_output)]
fn extract_timestamp(inputs: &[Series]) -> PolarsResult<Series> {
    let ca: &StringChunked = inputs[0].str()?;
    let out: Int64Chunked = ca
        .iter()
        .map(|opt_v: Option<&str>| {
            let (secs, nanos) = opt_v
                .and_then(|v| Uuid::parse_str(v).ok())
                .and_then(|u| u.get_timestamp())?
                .to_unix();
            Some(secs as i64 * 1_000 + (nanos / 1_000_000) as i64)
        })
        .collect_ca(PlSmallStr::EMPTY);
    out.into_series()
        .cast(&DataType::Datetime(TimeUnit::Milliseconds, None))
}
