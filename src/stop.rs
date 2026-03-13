//! Stop strategies (when to stop retrying).

use pyo3::prelude::*;

/// Stop condition: when to stop retrying.
#[derive(Clone)]
#[allow(clippy::enum_variant_names)]
pub enum StopStrategy {
    /// Never stop (retry indefinitely until another condition applies).
    StopNever,
    /// Stop when attempt number >= max_attempt (0-based; e.g. 3 = after 3 attempts).
    StopAfterAttempt(u64),
    /// Stop when elapsed time since start >= max_delay seconds.
    StopAfterDelay(f64),
    /// Stop when elapsed time >= max_delay seconds (same as StopAfterDelay for this API).
    StopBeforeDelay(f64),
    /// Stop when either strategy says stop.
    StopOr(Box<StopStrategy>, Box<StopStrategy>),
}

impl StopStrategy {
    /// Returns true if retrying should stop given current attempt (0-based) and elapsed seconds.
    pub fn should_stop(&self, attempt: u64, elapsed_secs: f64) -> bool {
        match self {
            StopStrategy::StopNever => false,
            StopStrategy::StopAfterAttempt(max) => attempt >= *max,
            StopStrategy::StopAfterDelay(max_delay) => elapsed_secs >= *max_delay,
            StopStrategy::StopBeforeDelay(max_delay) => elapsed_secs >= *max_delay,
            StopStrategy::StopOr(a, b) => {
                a.should_stop(attempt, elapsed_secs) || b.should_stop(attempt, elapsed_secs)
            }
        }
    }
}

/// Python-exposed stop strategy.
#[pyclass(module = "tenacity_rs.tenacity_rs")]
#[derive(Clone)]
pub struct PyStopStrategy {
    pub inner: StopStrategy,
}

#[pymethods]
impl PyStopStrategy {
    /// Whether to stop: attempt is 0-based, elapsed_secs is seconds since first attempt.
    fn should_stop(&self, attempt: u64, elapsed_secs: f64) -> bool {
        self.inner.should_stop(attempt, elapsed_secs)
    }

    /// Combine with another strategy: stop when either says stop (stop_any semantics).
    fn __or__(&self, other: &Bound<'_, PyStopStrategy>) -> PyResult<PyStopStrategy> {
        Ok(PyStopStrategy {
            inner: StopStrategy::StopOr(
                Box::new(self.inner.clone()),
                Box::new(other.borrow().inner.clone()),
            ),
        })
    }
}

/// Never stop retrying.
#[pyfunction]
fn stop_never() -> PyStopStrategy {
    PyStopStrategy {
        inner: StopStrategy::StopNever,
    }
}

/// Stop when attempt number >= max_attempt (0-based).
#[pyfunction]
fn stop_after_attempt(max_attempt_number: u64) -> PyStopStrategy {
    PyStopStrategy {
        inner: StopStrategy::StopAfterAttempt(max_attempt_number),
    }
}

/// Stop when elapsed time since start >= max_delay seconds.
#[pyfunction]
fn stop_after_delay(max_delay: f64) -> PyStopStrategy {
    PyStopStrategy {
        inner: StopStrategy::StopAfterDelay(max_delay),
    }
}

/// Stop when elapsed time >= max_delay seconds.
#[pyfunction]
fn stop_before_delay(max_delay: f64) -> PyStopStrategy {
    PyStopStrategy {
        inner: StopStrategy::StopBeforeDelay(max_delay),
    }
}

/// Register stop strategy types and functions into the module.
pub fn register_stop(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyStopStrategy>()?;
    m.add_function(wrap_pyfunction!(stop_never, m)?)?;
    m.add_function(wrap_pyfunction!(stop_after_attempt, m)?)?;
    m.add_function(wrap_pyfunction!(stop_after_delay, m)?)?;
    m.add_function(wrap_pyfunction!(stop_before_delay, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::StopStrategy;

    #[test]
    fn stop_never_never_stops() {
        let s = StopStrategy::StopNever;
        assert!(!s.should_stop(0, 0.0));
        assert!(!s.should_stop(100, 1000.0));
    }

    #[test]
    fn stop_after_attempt() {
        let s = StopStrategy::StopAfterAttempt(3);
        assert!(!s.should_stop(0, 0.0));
        assert!(!s.should_stop(1, 0.0));
        assert!(!s.should_stop(2, 0.0));
        assert!(s.should_stop(3, 0.0));
        assert!(s.should_stop(4, 0.0));
    }

    #[test]
    fn stop_after_delay() {
        let s = StopStrategy::StopAfterDelay(10.0);
        assert!(!s.should_stop(0, 0.0));
        assert!(!s.should_stop(0, 9.9));
        assert!(s.should_stop(0, 10.0));
        assert!(s.should_stop(0, 10.1));
    }

    #[test]
    fn stop_before_delay() {
        let s = StopStrategy::StopBeforeDelay(5.0);
        assert!(!s.should_stop(0, 0.0));
        assert!(!s.should_stop(0, 4.9));
        assert!(s.should_stop(0, 5.0));
        assert!(s.should_stop(0, 5.1));
    }

    #[test]
    fn stop_or_either() {
        let a = StopStrategy::StopAfterAttempt(2);
        let b = StopStrategy::StopAfterDelay(10.0);
        let or = StopStrategy::StopOr(Box::new(a), Box::new(b));

        // Neither: attempt 0, 0s
        assert!(!or.should_stop(0, 0.0));
        // After attempt kicks in: attempt 2
        assert!(or.should_stop(2, 0.0));
        // After delay kicks in: 10s
        assert!(or.should_stop(0, 10.0));
        // Both
        assert!(or.should_stop(2, 10.0));
    }

    #[test]
    fn stop_or_with_never() {
        let never = StopStrategy::StopNever;
        let after_3 = StopStrategy::StopAfterAttempt(3);
        let or = StopStrategy::StopOr(Box::new(never), Box::new(after_3));
        assert!(!or.should_stop(0, 0.0));
        assert!(!or.should_stop(2, 0.0));
        assert!(or.should_stop(3, 0.0));
    }
}
