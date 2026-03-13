use pyo3::prelude::*;

mod retry_condition;
mod retrying;
mod stop;
mod wait;

/// Tenacity-rs: Rust implementation of tenacity with Python bindings.
#[pymodule]
fn tenacity_rs(py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    stop::register_stop(m)?;
    wait::register_wait(m)?;
    retry_condition::register_retry_condition(m)?;
    retrying::register_retrying(m, py)?;
    Ok(())
}
