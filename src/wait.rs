//! Wait strategies (delay between retries).

use pyo3::prelude::*;
use pyo3::types::PyTuple;
use rand::Rng;

/// Wait strategy: how long to sleep before the next attempt.
#[derive(Clone, Debug)]
pub enum WaitStrategy {
    None,
    Fixed(f64),
    Random {
        min: f64,
        max: f64,
    },
    Exponential {
        multiplier: f64,
        min: f64,
        max: f64,
        exp_base: f64,
    },
    RandomExponential {
        multiplier: f64,
        max: f64,
        exp_base: f64,
    },
    #[allow(dead_code)]
    Chain(Vec<WaitStrategy>),
    #[allow(dead_code)]
    Sum(Box<WaitStrategy>, Box<WaitStrategy>),
}

impl WaitStrategy {
    /// Returns seconds to wait before next attempt.
    /// `attempt_number` is 1-based (first attempt = 1).
    pub fn compute(&self, attempt_number: u64) -> f64 {
        match self {
            WaitStrategy::None => 0.0,

            WaitStrategy::Fixed(secs) => *secs,

            WaitStrategy::Random { min, max } => {
                if *min >= *max {
                    return *min;
                }
                let mut rng = rand::thread_rng();
                rng.gen_range(*min..*max)
            }

            WaitStrategy::Exponential {
                multiplier,
                min,
                max,
                exp_base,
            } => {
                let raw = multiplier * exp_base.powf((attempt_number - 1) as f64);
                raw.max(*min).min(*max)
            }

            WaitStrategy::RandomExponential {
                multiplier,
                max,
                exp_base,
            } => {
                let ceiling = (multiplier * exp_base.powf(attempt_number as f64)).min(*max);
                if ceiling <= 0.0 {
                    return 0.0;
                }
                let mut rng = rand::thread_rng();
                rng.gen_range(0.0..ceiling)
            }

            WaitStrategy::Chain(strategies) => {
                if strategies.is_empty() {
                    return 0.0;
                }
                let idx = ((attempt_number - 1) as usize).min(strategies.len() - 1);
                strategies[idx].compute(attempt_number)
            }

            WaitStrategy::Sum(a, b) => a.compute(attempt_number) + b.compute(attempt_number),
        }
    }
}

// --- Python bindings: 7 separate classes ---

/// WaitNone() — zero wait.
#[pyclass(module = "tenacity_rs.tenacity_rs", name = "WaitNone")]
#[derive(Clone)]
pub struct PyWaitNone {}

#[pymethods]
impl PyWaitNone {
    #[new]
    fn new() -> Self {
        Self {}
    }

    fn compute(&self, attempt_number: u64) -> f64 {
        WaitStrategy::None.compute(attempt_number)
    }

    fn __add__(&self, other: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<PyWaitSum> {
        Ok(PyWaitSum {
            left: self.clone().into_py(py),
            right: other.as_borrowed().into_py(py),
        })
    }
}

/// WaitFixed(seconds).
#[pyclass(module = "tenacity_rs.tenacity_rs", name = "WaitFixed")]
#[derive(Clone)]
pub struct PyWaitFixed {
    seconds: f64,
}

#[pymethods]
impl PyWaitFixed {
    #[new]
    fn new(seconds: f64) -> Self {
        Self { seconds }
    }

    fn compute(&self, attempt_number: u64) -> f64 {
        WaitStrategy::Fixed(self.seconds).compute(attempt_number)
    }

    fn __add__(&self, other: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<PyWaitSum> {
        Ok(PyWaitSum {
            left: self.clone().into_py(py),
            right: other.as_borrowed().into_py(py),
        })
    }
}

/// WaitRandom(min, max).
#[pyclass(module = "tenacity_rs.tenacity_rs", name = "WaitRandom")]
#[derive(Clone)]
pub struct PyWaitRandom {
    min: f64,
    max: f64,
}

#[pymethods]
impl PyWaitRandom {
    #[new]
    fn new(min: f64, max: f64) -> Self {
        Self { min, max }
    }

    fn compute(&self, attempt_number: u64) -> f64 {
        WaitStrategy::Random {
            min: self.min,
            max: self.max,
        }
        .compute(attempt_number)
    }

    fn __add__(&self, other: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<PyWaitSum> {
        Ok(PyWaitSum {
            left: self.clone().into_py(py),
            right: other.as_borrowed().into_py(py),
        })
    }
}

/// WaitExponential(multiplier=1.0, min=0.0, max=..., exp_base=2.0).
#[pyclass(module = "tenacity_rs.tenacity_rs", name = "WaitExponential")]
#[derive(Clone)]
pub struct PyWaitExponential {
    multiplier: f64,
    min: f64,
    max: f64,
    exp_base: f64,
}

#[pymethods]
impl PyWaitExponential {
    #[new]
    #[pyo3(signature = (multiplier=1.0, min=0.0, max=None, exp_base=2.0))]
    fn new(multiplier: f64, min: f64, max: Option<f64>, exp_base: f64) -> Self {
        Self {
            multiplier,
            min,
            max: max.unwrap_or(f64::MAX),
            exp_base,
        }
    }

    fn compute(&self, attempt_number: u64) -> f64 {
        WaitStrategy::Exponential {
            multiplier: self.multiplier,
            min: self.min,
            max: self.max,
            exp_base: self.exp_base,
        }
        .compute(attempt_number)
    }

    fn __add__(&self, other: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<PyWaitSum> {
        Ok(PyWaitSum {
            left: self.clone().into_py(py),
            right: other.as_borrowed().into_py(py),
        })
    }
}

/// WaitRandomExponential(multiplier=1.0, max=..., exp_base=2.0).
#[pyclass(module = "tenacity_rs.tenacity_rs", name = "WaitRandomExponential")]
#[derive(Clone)]
pub struct PyWaitRandomExponential {
    multiplier: f64,
    max: f64,
    exp_base: f64,
}

#[pymethods]
impl PyWaitRandomExponential {
    #[new]
    #[pyo3(signature = (multiplier=1.0, max=None, exp_base=2.0))]
    fn new(multiplier: f64, max: Option<f64>, exp_base: f64) -> Self {
        Self {
            multiplier,
            max: max.unwrap_or(f64::MAX),
            exp_base,
        }
    }

    fn compute(&self, attempt_number: u64) -> f64 {
        WaitStrategy::RandomExponential {
            multiplier: self.multiplier,
            max: self.max,
            exp_base: self.exp_base,
        }
        .compute(attempt_number)
    }

    fn __add__(&self, other: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<PyWaitSum> {
        Ok(PyWaitSum {
            left: self.clone().into_py(py),
            right: other.as_borrowed().into_py(py),
        })
    }
}

/// WaitChain(*strategies).
#[pyclass(module = "tenacity_rs.tenacity_rs", name = "WaitChain")]
#[derive(Clone)]
pub struct PyWaitChain {
    strategies: Vec<Py<PyAny>>,
}

#[pymethods]
impl PyWaitChain {
    #[new]
    #[pyo3(signature = (*args))]
    fn new(args: &Bound<'_, PyTuple>, py: Python<'_>) -> PyResult<Self> {
        let strategies = args.iter().map(|o| o.into_py(py)).collect::<Vec<_>>();
        Ok(Self { strategies })
    }

    fn compute(&self, attempt_number: u64, py: Python<'_>) -> PyResult<f64> {
        if self.strategies.is_empty() {
            return Ok(0.0);
        }
        let idx = ((attempt_number - 1) as usize).min(self.strategies.len() - 1);
        let strategy = self.strategies[idx].bind(py);
        let compute = strategy.getattr("compute")?;
        let result: f64 = compute.call1((attempt_number,))?.extract()?;
        Ok(result)
    }

    fn __add__(&self, other: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<PyWaitSum> {
        Ok(PyWaitSum {
            left: self.clone().into_py(py),
            right: other.as_borrowed().into_py(py),
        })
    }
}

/// WaitSum — internal, returned by __add__.
#[pyclass(module = "tenacity_rs.tenacity_rs", name = "WaitSum")]
#[derive(Clone)]
pub struct PyWaitSum {
    left: Py<PyAny>,
    right: Py<PyAny>,
}

#[pymethods]
impl PyWaitSum {
    #[new]
    fn new(left: Py<PyAny>, right: Py<PyAny>) -> Self {
        Self { left, right }
    }

    fn compute(&self, attempt_number: u64, py: Python<'_>) -> PyResult<f64> {
        let left_val: f64 = self
            .left
            .bind(py)
            .call_method1("compute", (attempt_number,))?
            .extract()?;
        let right_val: f64 = self
            .right
            .bind(py)
            .call_method1("compute", (attempt_number,))?
            .extract()?;
        Ok(left_val + right_val)
    }

    fn __add__(&self, other: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<PyWaitSum> {
        Ok(PyWaitSum {
            left: self.clone().into_py(py),
            right: other.as_borrowed().into_py(py),
        })
    }
}

// --- Factory functions (return instances for convenience) ---

#[pyfunction]
fn wait_none() -> PyWaitNone {
    PyWaitNone {}
}

#[pyfunction]
fn wait_fixed(seconds: f64) -> PyWaitFixed {
    PyWaitFixed { seconds }
}

#[pyfunction]
fn wait_random(min: f64, max: f64) -> PyWaitRandom {
    PyWaitRandom { min, max }
}

#[pyfunction]
#[pyo3(signature = (multiplier=1.0, min=0.0, max=None, exp_base=2.0))]
fn wait_exponential(
    multiplier: f64,
    min: f64,
    max: Option<f64>,
    exp_base: f64,
) -> PyWaitExponential {
    PyWaitExponential {
        multiplier,
        min,
        max: max.unwrap_or(f64::MAX),
        exp_base,
    }
}

#[pyfunction]
#[pyo3(signature = (multiplier=1.0, max=None, exp_base=2.0))]
fn wait_random_exponential(
    multiplier: f64,
    max: Option<f64>,
    exp_base: f64,
) -> PyWaitRandomExponential {
    PyWaitRandomExponential {
        multiplier,
        max: max.unwrap_or(f64::MAX),
        exp_base,
    }
}

#[pyfunction]
fn wait_chain(args: &Bound<'_, PyTuple>, py: Python<'_>) -> PyResult<PyWaitChain> {
    PyWaitChain::new(args, py)
}

/// Register wait strategy types and functions into the module.
pub fn register_wait(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyWaitNone>()?;
    m.add_class::<PyWaitFixed>()?;
    m.add_class::<PyWaitRandom>()?;
    m.add_class::<PyWaitExponential>()?;
    m.add_class::<PyWaitRandomExponential>()?;
    m.add_class::<PyWaitChain>()?;
    m.add_class::<PyWaitSum>()?;
    m.add_function(wrap_pyfunction!(wait_none, m)?)?;
    m.add_function(wrap_pyfunction!(wait_fixed, m)?)?;
    m.add_function(wrap_pyfunction!(wait_random, m)?)?;
    m.add_function(wrap_pyfunction!(wait_exponential, m)?)?;
    m.add_function(wrap_pyfunction!(wait_random_exponential, m)?)?;
    m.add_function(wrap_pyfunction!(wait_chain, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_wait_none() {
        assert_eq!(WaitStrategy::None.compute(1), 0.0);
    }

    #[test]
    fn test_wait_fixed() {
        let w = WaitStrategy::Fixed(3.5);
        assert_eq!(w.compute(1), 3.5);
        assert_eq!(w.compute(10), 3.5);
    }

    #[test]
    fn test_wait_exponential() {
        let w = WaitStrategy::Exponential {
            multiplier: 1.0,
            min: 0.0,
            max: 100.0,
            exp_base: 2.0,
        };
        assert_eq!(w.compute(1), 1.0);
        assert_eq!(w.compute(2), 2.0);
        assert_eq!(w.compute(3), 4.0);
    }

    #[test]
    fn test_wait_exponential_max() {
        let w = WaitStrategy::Exponential {
            multiplier: 1.0,
            min: 0.0,
            max: 10.0,
            exp_base: 2.0,
        };
        assert_eq!(w.compute(10), 10.0);
    }

    #[test]
    fn test_wait_chain() {
        let w = WaitStrategy::Chain(vec![
            WaitStrategy::Fixed(3.0),
            WaitStrategy::Fixed(3.0),
            WaitStrategy::Fixed(7.0),
        ]);
        assert_eq!(w.compute(1), 3.0);
        assert_eq!(w.compute(2), 3.0);
        assert_eq!(w.compute(3), 7.0);
        assert_eq!(w.compute(99), 7.0);
    }

    #[test]
    fn test_wait_sum() {
        let w = WaitStrategy::Sum(
            Box::new(WaitStrategy::Fixed(3.0)),
            Box::new(WaitStrategy::Fixed(2.0)),
        );
        assert_eq!(w.compute(1), 5.0);
    }
}
