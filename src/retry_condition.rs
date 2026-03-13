//! Retry conditions (when to retry based on exception or return value).

use pyo3::prelude::*;
use pyo3::types::{PyTuple, PyType};

/// Internal enum representing retry conditions. All logic runs with GIL.
#[derive(Clone)]
pub enum RetryCondition {
    IfException(Py<PyAny>),
    IfExceptionType(Py<PyAny>),
    IfNotExceptionType(Py<PyAny>),
    UnlessExceptionType(Py<PyAny>),
    IfResult(Py<PyAny>),
    IfNotResult(Py<PyAny>),
    IfExceptionMessage {
        message: Option<String>,
        match_pattern: Option<String>,
    },
    IfNotExceptionMessage {
        message: Option<String>,
        match_pattern: Option<String>,
    },
    Any(Vec<RetryCondition>),
    All(Vec<RetryCondition>),
    Or(Box<RetryCondition>, Box<RetryCondition>),
    And(Box<RetryCondition>, Box<RetryCondition>),
}

impl RetryCondition {
    /// Returns true if we should retry given an exception instance (Python exception object).
    pub fn should_retry_on_exception(
        &self,
        py: Python<'_>,
        exc: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        match self {
            RetryCondition::IfException(pred) => {
                let pred = pred.bind(py);
                let result = pred.call1((exc,))?;
                result.extract()
            }
            RetryCondition::IfExceptionType(exc_type) => {
                let ty = exc_type.bind(py).downcast::<PyType>()?;
                Ok(exc.is_instance(ty)?)
            }
            RetryCondition::IfNotExceptionType(exc_type) => {
                let ty = exc_type.bind(py).downcast::<PyType>()?;
                Ok(!exc.is_instance(ty)?)
            }
            RetryCondition::UnlessExceptionType(exc_type) => {
                let ty = exc_type.bind(py).downcast::<PyType>()?;
                Ok(!exc.is_instance(ty)?)
            }
            RetryCondition::IfResult(_) => Ok(false),
            RetryCondition::IfNotResult(_) => Ok(false),
            RetryCondition::IfExceptionMessage {
                message,
                match_pattern,
            } => {
                let msg = exc.str()?.to_string_lossy().into_owned();
                if let Some(m) = message {
                    return Ok(msg == *m);
                }
                if let Some(pattern) = match_pattern {
                    let re = py.import_bound("re")?;
                    let compiled = re.getattr("compile")?.call1((pattern,))?;
                    let m = compiled.call_method1("match", (&msg,))?;
                    return Ok(!m.is_none());
                }
                Ok(false)
            }
            RetryCondition::IfNotExceptionMessage {
                message,
                match_pattern,
            } => {
                let msg = exc.str()?.to_string_lossy().into_owned();
                if let Some(m) = message {
                    return Ok(msg != *m);
                }
                if let Some(pattern) = match_pattern {
                    let re = py.import_bound("re")?;
                    let compiled = re.getattr("compile")?.call1((pattern,))?;
                    let m = compiled.call_method1("match", (&msg,))?;
                    return Ok(m.is_none());
                }
                Ok(true)
            }
            RetryCondition::Any(conditions) => {
                for c in conditions {
                    if c.should_retry_on_exception(py, exc)? {
                        return Ok(true);
                    }
                }
                Ok(false)
            }
            RetryCondition::All(conditions) => {
                for c in conditions {
                    if !c.should_retry_on_exception(py, exc)? {
                        return Ok(false);
                    }
                }
                Ok(true)
            }
            RetryCondition::Or(a, b) => Ok(
                a.should_retry_on_exception(py, exc)? || b.should_retry_on_exception(py, exc)?
            ),
            RetryCondition::And(a, b) => Ok(
                a.should_retry_on_exception(py, exc)? && b.should_retry_on_exception(py, exc)?
            ),
        }
    }

    /// Returns true if we should retry given a successful return value.
    pub fn should_retry_on_result(
        &self,
        py: Python<'_>,
        value: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        match self {
            RetryCondition::IfException(_)
            | RetryCondition::IfExceptionType(_)
            | RetryCondition::IfNotExceptionType(_)
            | RetryCondition::UnlessExceptionType(_)
            | RetryCondition::IfExceptionMessage { .. }
            | RetryCondition::IfNotExceptionMessage { .. } => Ok(false),
            RetryCondition::IfResult(pred) => {
                let pred = pred.bind(py);
                let result = pred.call1((value,))?;
                result.extract()
            }
            RetryCondition::IfNotResult(pred) => {
                let pred = pred.bind(py);
                let result = pred.call1((value,))?;
                let b: bool = result.extract()?;
                Ok(!b)
            }
            RetryCondition::Any(conditions) => {
                for c in conditions {
                    if c.should_retry_on_result(py, value)? {
                        return Ok(true);
                    }
                }
                Ok(false)
            }
            RetryCondition::All(conditions) => {
                for c in conditions {
                    if !c.should_retry_on_result(py, value)? {
                        return Ok(false);
                    }
                }
                Ok(true)
            }
            RetryCondition::Or(a, b) => {
                Ok(a.should_retry_on_result(py, value)? || b.should_retry_on_result(py, value)?)
            }
            RetryCondition::And(a, b) => {
                Ok(a.should_retry_on_result(py, value)? && b.should_retry_on_result(py, value)?)
            }
        }
    }
}

// --- Python bindings: one wrapper class + combinators ---

/// Python-exposed retry condition (wraps enum so __or__/__and__ return same type).
#[pyclass(module = "tenacity_rs.tenacity_rs", name = "RetryCondition")]
pub struct PyRetryCondition {
    pub inner: RetryCondition,
}

#[pymethods]
impl PyRetryCondition {
    fn should_retry_on_exception(&self, exc: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<bool> {
        self.inner.should_retry_on_exception(py, exc)
    }

    fn should_retry_on_result(&self, value: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<bool> {
        self.inner.should_retry_on_result(py, value)
    }

    fn __or__(&self, other: &Bound<'_, PyRetryCondition>) -> PyResult<PyRetryCondition> {
        Ok(PyRetryCondition {
            inner: RetryCondition::Or(
                Box::new(self.inner.clone()),
                Box::new(other.borrow().inner.clone()),
            ),
        })
    }

    fn __and__(&self, other: &Bound<'_, PyRetryCondition>) -> PyResult<PyRetryCondition> {
        Ok(PyRetryCondition {
            inner: RetryCondition::And(
                Box::new(self.inner.clone()),
                Box::new(other.borrow().inner.clone()),
            ),
        })
    }
}

// Factory functions return PyRetryCondition so | and & work uniformly.

#[pyfunction]
fn retry_if_exception(predicate: &Bound<'_, PyAny>) -> PyRetryCondition {
    PyRetryCondition {
        inner: RetryCondition::IfException(predicate.into_py(predicate.py())),
    }
}

#[pyfunction]
#[pyo3(signature = (exc_type=None))]
fn retry_if_exception_type(
    py: Python<'_>,
    exc_type: Option<&Bound<'_, PyAny>>,
) -> PyResult<PyRetryCondition> {
    let exc_type = match exc_type {
        Some(t) => t.into_py(py),
        None => py
            .import_bound("builtins")?
            .getattr("Exception")?
            .into_py(py),
    };
    Ok(PyRetryCondition {
        inner: RetryCondition::IfExceptionType(exc_type),
    })
}

#[pyfunction]
#[pyo3(signature = (exc_type=None))]
fn retry_if_not_exception_type(
    py: Python<'_>,
    exc_type: Option<&Bound<'_, PyAny>>,
) -> PyResult<PyRetryCondition> {
    let exc_type = match exc_type {
        Some(t) => t.into_py(py),
        None => py
            .import_bound("builtins")?
            .getattr("Exception")?
            .into_py(py),
    };
    Ok(PyRetryCondition {
        inner: RetryCondition::IfNotExceptionType(exc_type),
    })
}

#[pyfunction]
#[pyo3(signature = (exc_type=None))]
fn retry_unless_exception_type(
    py: Python<'_>,
    exc_type: Option<&Bound<'_, PyAny>>,
) -> PyResult<PyRetryCondition> {
    let exc_type = match exc_type {
        Some(t) => t.into_py(py),
        None => py
            .import_bound("builtins")?
            .getattr("Exception")?
            .into_py(py),
    };
    Ok(PyRetryCondition {
        inner: RetryCondition::UnlessExceptionType(exc_type),
    })
}

#[pyfunction]
fn retry_if_result(predicate: &Bound<'_, PyAny>) -> PyRetryCondition {
    PyRetryCondition {
        inner: RetryCondition::IfResult(predicate.into_py(predicate.py())),
    }
}

#[pyfunction]
fn retry_if_not_result(predicate: &Bound<'_, PyAny>) -> PyRetryCondition {
    PyRetryCondition {
        inner: RetryCondition::IfNotResult(predicate.into_py(predicate.py())),
    }
}

#[pyfunction]
#[pyo3(signature = (message=None, match_pattern=None))]
fn retry_if_exception_message(
    _py: Python<'_>,
    message: Option<&str>,
    match_pattern: Option<&str>,
) -> PyResult<PyRetryCondition> {
    if message.is_some() && match_pattern.is_some() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "retry_if_exception_message() takes either 'message' or 'match', not both",
        ));
    }
    if message.is_none() && match_pattern.is_none() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "retry_if_exception_message() missing 1 required argument 'message' or 'match'",
        ));
    }
    Ok(PyRetryCondition {
        inner: RetryCondition::IfExceptionMessage {
            message: message.map(String::from),
            match_pattern: match_pattern.map(String::from),
        },
    })
}

#[pyfunction]
#[pyo3(signature = (message=None, match_pattern=None))]
fn retry_if_not_exception_message(
    _py: Python<'_>,
    message: Option<&str>,
    match_pattern: Option<&str>,
) -> PyResult<PyRetryCondition> {
    if message.is_some() && match_pattern.is_some() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "retry_if_not_exception_message() takes either 'message' or 'match', not both",
        ));
    }
    if message.is_none() && match_pattern.is_none() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "retry_if_not_exception_message() missing 1 required argument 'message' or 'match'",
        ));
    }
    Ok(PyRetryCondition {
        inner: RetryCondition::IfNotExceptionMessage {
            message: message.map(String::from),
            match_pattern: match_pattern.map(String::from),
        },
    })
}

#[pyfunction]
#[pyo3(signature = (*args))]
fn retry_any(args: &Bound<'_, PyTuple>) -> PyResult<PyRetryCondition> {
    let mut conditions = Vec::with_capacity(args.len());
    for i in 0..args.len() {
        let item = args.get_item(i)?;
        let cond = item.downcast::<PyRetryCondition>()?;
        conditions.push(cond.borrow().inner.clone());
    }
    Ok(PyRetryCondition {
        inner: RetryCondition::Any(conditions),
    })
}

#[pyfunction]
#[pyo3(signature = (*args))]
fn retry_all(args: &Bound<'_, PyTuple>) -> PyResult<PyRetryCondition> {
    let mut conditions = Vec::with_capacity(args.len());
    for i in 0..args.len() {
        let item = args.get_item(i)?;
        let cond = item.downcast::<PyRetryCondition>()?;
        conditions.push(cond.borrow().inner.clone());
    }
    Ok(PyRetryCondition {
        inner: RetryCondition::All(conditions),
    })
}

/// Register retry condition types and functions into the module.
pub fn register_retry_condition(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyRetryCondition>()?;
    m.add_function(wrap_pyfunction!(retry_if_exception, m)?)?;
    m.add_function(wrap_pyfunction!(retry_if_exception_type, m)?)?;
    m.add_function(wrap_pyfunction!(retry_if_not_exception_type, m)?)?;
    m.add_function(wrap_pyfunction!(retry_unless_exception_type, m)?)?;
    m.add_function(wrap_pyfunction!(retry_if_result, m)?)?;
    m.add_function(wrap_pyfunction!(retry_if_not_result, m)?)?;
    m.add_function(wrap_pyfunction!(retry_if_exception_message, m)?)?;
    m.add_function(wrap_pyfunction!(retry_if_not_exception_message, m)?)?;
    m.add_function(wrap_pyfunction!(retry_any, m)?)?;
    m.add_function(wrap_pyfunction!(retry_all, m)?)?;
    Ok(())
}
