//! Core retry engine: RetryCallState, Retrying, and the retry loop.

use pyo3::exceptions::PyStopIteration;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyTuple};

pyo3::create_exception!(tenacity_rs, RetryError, pyo3::exceptions::PyException);
pyo3::create_exception!(tenacity_rs, TryAgain, pyo3::exceptions::PyException);

/// Create a Future-like outcome (concurrent.futures.Future) with result or exception set.
fn make_outcome_future(py: Python<'_>, result: Result<Py<PyAny>, PyErr>) -> PyResult<Py<PyAny>> {
    let futures = py.import_bound("concurrent.futures")?;
    let future_class = futures.getattr("Future")?;
    let fut = future_class.call0()?;
    match result {
        Ok(val) => {
            fut.call_method1("set_result", (val,))?;
        }
        Err(err) => {
            let exc = err.into_value(py);
            fut.call_method1("set_exception", (exc,))?;
        }
    }
    Ok(fut.into_py(py))
}

/// State for a single retry call.
#[pyclass(module = "tenacity_rs.tenacity_rs", name = "RetryCallState")]
#[derive(Clone)]
pub struct RetryCallState {
    #[pyo3(get, set)]
    pub attempt_number: u64,
    #[pyo3(get)]
    pub start_time: f64,
    #[pyo3(get, set)]
    pub idle_for: f64,
    #[pyo3(get, set)]
    pub outcome: Option<Py<PyAny>>,
    #[pyo3(get, set)]
    pub fn_ref: Option<Py<PyAny>>,
}

#[pymethods]
impl RetryCallState {
    #[new]
    fn new(start_time: f64) -> Self {
        Self {
            attempt_number: 1,
            start_time,
            idle_for: 0.0,
            outcome: None,
            fn_ref: None,
        }
    }

    fn elapsed_time(&self, py: Python<'_>) -> PyResult<f64> {
        let time_mod = py.import_bound("time")?;
        let now: f64 = time_mod.getattr("monotonic")?.call0()?.extract()?;
        Ok(now - self.start_time)
    }

    /// Tenacity-compatible alias: the wrapped function (same as fn_ref).
    #[getter]
    fn fn_attr(&self) -> Option<Py<PyAny>> {
        self.fn_ref.clone()
    }
}

/// Retrying controller: runs the retry loop.
#[pyclass(module = "tenacity_rs.tenacity_rs", name = "Retrying")]
pub struct Retrying {
    #[pyo3(get)]
    stop: Py<PyAny>,
    #[pyo3(get)]
    wait: Py<PyAny>,
    #[pyo3(get)]
    retry: Py<PyAny>,
    before: Option<Py<PyAny>>,
    after: Option<Py<PyAny>>,
    #[pyo3(get)]
    before_sleep: Option<Py<PyAny>>,
    #[pyo3(get)]
    retry_error_callback: Option<Py<PyAny>>,
    #[pyo3(get)]
    reraise: bool,
    #[pyo3(get)]
    sleep: Py<PyAny>,
    #[pyo3(get)]
    pub statistics: Py<PyDict>,
}

#[pymethods]
impl Retrying {
    #[new]
    #[pyo3(signature = (stop, wait, retry=None, before=None, after=None, before_sleep=None, retry_error_callback=None, reraise=false, sleep=None))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        py: Python<'_>,
        stop: Py<PyAny>,
        wait: Py<PyAny>,
        retry: Option<Py<PyAny>>,
        before: Option<Py<PyAny>>,
        after: Option<Py<PyAny>>,
        before_sleep: Option<Py<PyAny>>,
        retry_error_callback: Option<Py<PyAny>>,
        reraise: bool,
        sleep: Option<Py<PyAny>>,
    ) -> PyResult<Self> {
        let retry = retry.unwrap_or_else(|| {
            let tenacity_rs = py.import_bound("tenacity_rs").unwrap();
            let tr = tenacity_rs.getattr("tenacity_rs").unwrap();
            let fn_ = tr.getattr("retry_if_exception_type").unwrap();
            fn_.call0().unwrap().into_py(py)
        });
        let sleep = sleep.unwrap_or_else(|| {
            py.import_bound("time")
                .unwrap()
                .getattr("sleep")
                .unwrap()
                .into_py(py)
        });
        let statistics = PyDict::new_bound(py);
        statistics.set_item("attempt_number", 0u64)?;
        statistics.set_item("start_time", 0.0f64)?;
        statistics.set_item("delay_since_first_attempt", 0.0f64)?;
        statistics.set_item("idle_for", 0.0f64)?;
        Ok(Self {
            stop,
            wait,
            retry,
            before,
            after,
            before_sleep,
            retry_error_callback,
            reraise,
            sleep,
            statistics: statistics.unbind(),
        })
    }

    /// Return an iterator yielding attempt context managers for `for attempt in Retrying(...): with attempt: ...`.
    fn __iter__(slf: PyRef<Self>, py: Python<'_>) -> PyResult<Py<RetryingIterator>> {
        let retrying: Py<PyAny> = slf.into_py(py).bind(py).clone().into_any().unbind();
        Py::new(
            py,
            RetryingIterator {
                retrying,
                attempt_number: 0,
                start_time: None,
                idle_for: 0.0,
            },
        )
    }

    /// Call with (fn_, *args, **kwargs): runs the retry loop and returns the result.
    #[pyo3(signature = (fn_, *args, **kwargs))]
    fn __call__(
        slf: PyRef<Self>,
        fn_: Py<PyAny>,
        args: &Bound<'_, PyTuple>,
        kwargs: Option<&Bound<'_, PyDict>>,
        py: Python<'_>,
    ) -> PyResult<Py<PyAny>> {
        let kwargs_any = kwargs.map(|k| k.as_ref());
        slf.do_retry(py, fn_.bind(py).clone(), args, kwargs_any)
    }

    /// Internal: run the retry loop for the given function and arguments.
    #[pyo3(signature = (fn_, args, kwargs=None))]
    fn do_retry(
        &self,
        py: Python<'_>,
        fn_: Bound<'_, PyAny>,
        args: &Bound<'_, PyTuple>,
        kwargs: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Py<PyAny>> {
        let kwargs = kwargs.and_then(|k| k.downcast::<PyDict>().ok());
        let time_mod = py.import_bound("time")?;
        let start: f64 = time_mod.getattr("monotonic")?.call0()?.extract()?;
        let mut state = RetryCallState::new(start);
        state.fn_ref = Some(fn_.clone().into_py(py));

        // Reset/init statistics
        self.statistics
            .bind(py)
            .set_item("attempt_number", state.attempt_number)?;
        self.statistics.bind(py).set_item("start_time", start)?;
        self.statistics
            .bind(py)
            .set_item("delay_since_first_attempt", 0.0f64)?;
        self.statistics.bind(py).set_item("idle_for", 0.0f64)?;

        loop {
            // 1. Before callback
            if let Some(ref before) = self.before {
                let state_ref = Py::new(py, state.clone())?;
                before.bind(py).call1((state_ref,))?;
            }

            // 2. Call the wrapped function
            let result = if let Some(kw) = kwargs {
                fn_.call(args, Some(kw))
            } else {
                fn_.call(args, None)
            };

            // 3. Update state.outcome
            let outcome_result = result
                .as_ref()
                .map(|v| v.clone().into_py(py))
                .map_err(|e| e.clone_ref(py));
            state.outcome = Some(make_outcome_future(py, outcome_result)?);

            match result {
                Ok(value) => {
                    // 4a. After callback
                    if let Some(ref after) = self.after {
                        let state_ref = Py::new(py, state.clone())?;
                        after.bind(py).call1((state_ref,))?;
                    }

                    // 4b. Check retry_if_result
                    let should_retry: bool = self
                        .retry
                        .bind(py)
                        .call_method1("should_retry_on_result", (value.as_borrowed(),))?
                        .extract()?;
                    if !should_retry {
                        self.statistics
                            .bind(py)
                            .set_item("attempt_number", state.attempt_number)?;
                        self.statistics
                            .bind(py)
                            .set_item("idle_for", state.idle_for)?;
                        return Ok(value.into_py(py));
                    }
                }
                Err(ref exc) => {
                    let is_try_again = exc.is_instance_of::<TryAgain>(py);

                    if !is_try_again {
                        // 5b. After callback
                        if let Some(ref after) = self.after {
                            let state_ref = Py::new(py, state.clone())?;
                            after.bind(py).call1((state_ref,))?;
                        }

                        // 5c. Check stop
                        let elapsed = state.elapsed_time(py)?;
                        let stop_val: bool = self
                            .stop
                            .bind(py)
                            .call_method1("should_stop", (state.attempt_number, elapsed))?
                            .extract()?;
                        if stop_val {
                            if self.reraise {
                                return Err(exc.clone_ref(py));
                            }
                            if let Some(ref cb) = self.retry_error_callback {
                                let state_ref = Py::new(py, state.clone())?;
                                return cb.bind(py).call1((state_ref,)).map(|v| v.into_py(py));
                            }
                            let py_err = RetryError::new_err("Retrying failed");
                            let inst = py_err.value_bound(py);
                            if let Some(ref out) = state.outcome {
                                inst.setattr("last_attempt", out.bind(py))?;
                            }
                            return Err(py_err);
                        }

                        // 5d. Check retry on exception
                        let exc_value = exc.value_bound(py);
                        let should_retry: bool = self
                            .retry
                            .bind(py)
                            .call_method1("should_retry_on_exception", (exc_value,))?
                            .extract()?;
                        if !should_retry {
                            return Err(exc.clone_ref(py));
                        }
                    }
                }
            }

            // Before waiting: check stop (we're about to retry)
            let elapsed = state.elapsed_time(py)?;
            let stop_val: bool = self
                .stop
                .bind(py)
                .call_method1("should_stop", (state.attempt_number, elapsed))?
                .extract()?;
            if stop_val {
                if let Some(ref cb) = self.retry_error_callback {
                    let state_ref = Py::new(py, state.clone())?;
                    return cb.bind(py).call1((state_ref,)).map(|v| v.into_py(py));
                }
                let py_err = RetryError::new_err("Retrying failed");
                let inst = py_err.value_bound(py);
                if let Some(ref out) = state.outcome {
                    inst.setattr("last_attempt", out.bind(py))?;
                }
                return Err(py_err);
            }

            // 6. Wait
            let wait_secs: f64 = self
                .wait
                .bind(py)
                .call_method1("compute", (state.attempt_number,))?
                .extract()?;
            state.idle_for += wait_secs;

            // 7. Before sleep
            if let Some(ref bs) = self.before_sleep {
                let state_ref = Py::new(py, state.clone())?;
                bs.bind(py).call1((state_ref,))?;
            }

            // 8. Sleep
            self.sleep.bind(py).call1((wait_secs,))?;

            // 9. Increment attempt
            state.attempt_number += 1;

            // Update statistics
            self.statistics
                .bind(py)
                .set_item("attempt_number", state.attempt_number)?;
            self.statistics
                .bind(py)
                .set_item("delay_since_first_attempt", state.idle_for)?;
            self.statistics
                .bind(py)
                .set_item("idle_for", state.idle_for)?;
        }
    }
}

/// Iterator returned by `for attempt in Retrying(...)`.
#[pyclass(module = "tenacity_rs.tenacity_rs", name = "RetryingIterator")]
pub struct RetryingIterator {
    retrying: Py<PyAny>,
    attempt_number: u64,
    start_time: Option<f64>,
    #[allow(dead_code)]
    idle_for: f64,
}

#[pymethods]
impl RetryingIterator {
    fn __iter__(slf: PyRef<Self>) -> PyRef<Self> {
        slf
    }

    fn __next__(mut slf: PyRefMut<Self>, py: Python<'_>) -> PyResult<Option<Py<AttemptContext>>> {
        if slf.start_time.is_none() {
            let time_mod = py.import_bound("time")?;
            let now: f64 = time_mod.getattr("monotonic")?.call0()?.extract()?;
            slf.start_time = Some(now);
        }

        slf.attempt_number += 1;

        if slf.attempt_number > 1 {
            let time_mod = py.import_bound("time")?;
            let now: f64 = time_mod.getattr("monotonic")?.call0()?.extract()?;
            let elapsed = now - slf.start_time.unwrap();

            let retrying = slf.retrying.bind(py);
            let stop = retrying.getattr("stop")?;
            let should_stop: bool = stop
                .call_method1("should_stop", (slf.attempt_number - 1, elapsed))?
                .extract()?;

            if should_stop {
                return Err(PyStopIteration::new_err("Retry limit reached"));
            }
        }

        let attempt = Py::new(
            py,
            AttemptContext {
                retrying: slf.retrying.clone(),
                attempt_number: slf.attempt_number,
                start_time: slf.start_time.unwrap(),
            },
        )?;
        Ok(Some(attempt))
    }
}

/// Context manager for one attempt in `for attempt in Retrying(...): with attempt: ...`.
#[pyclass(module = "tenacity_rs.tenacity_rs", name = "AttemptContext")]
pub struct AttemptContext {
    retrying: Py<PyAny>,
    attempt_number: u64,
    start_time: f64,
}

#[pymethods]
impl AttemptContext {
    fn __enter__(slf: PyRef<Self>) -> PyRef<Self> {
        slf
    }

    fn __exit__(
        slf: PyRef<Self>,
        exc_type: Option<&Bound<'_, PyAny>>,
        exc_val: Option<&Bound<'_, PyAny>>,
        _exc_tb: Option<&Bound<'_, PyAny>>,
        py: Python<'_>,
    ) -> PyResult<bool> {
        if exc_type.is_none() {
            return Ok(false);
        }

        let exc_val = match exc_val {
            Some(v) => v.clone().unbind(),
            None => return Ok(true),
        };
        let exc = PyErr::from_value_bound(exc_val.bind(py).as_borrowed().to_owned());

        if exc.is_instance_of::<TryAgain>(py) {
            return Ok(true);
        }

        let retrying = slf.retrying.bind(py);
        let time_mod = py.import_bound("time")?;
        let now: f64 = time_mod.getattr("monotonic")?.call0()?.extract()?;
        let elapsed = now - slf.start_time;

        let stop = retrying.getattr("stop")?;
        let should_stop: bool = stop
            .call_method1("should_stop", (slf.attempt_number, elapsed))?
            .extract()?;

        if should_stop {
            let reraise: bool = retrying.getattr("reraise")?.extract()?;
            if reraise {
                return Err(exc);
            }
            if let Ok(cb) = retrying.getattr("retry_error_callback") {
                if !cb.is_none() {
                    let state = Py::new(
                        py,
                        RetryCallState {
                            attempt_number: slf.attempt_number,
                            start_time: slf.start_time,
                            idle_for: 0.0,
                            outcome: None,
                            fn_ref: None,
                        },
                    )?;
                    let _ = cb.call1((state,));
                }
            }
            return Err(RetryError::new_err("Retrying failed"));
        }

        let retry_cond = retrying.getattr("retry")?;
        let should_retry: bool = if let Ok(method) = retry_cond.getattr("should_retry_on_exception")
        {
            method.call1((exc_val.bind(py),))?.extract()?
        } else {
            true
        };

        if !should_retry {
            return Err(exc);
        }

        let wait = retrying.getattr("wait")?;
        let wait_secs: f64 = wait
            .call_method1("compute", (slf.attempt_number,))?
            .extract()?;

        let before_sleep = retrying.getattr("before_sleep")?;
        if !before_sleep.is_none() {
            let state = Py::new(
                py,
                RetryCallState {
                    attempt_number: slf.attempt_number,
                    start_time: slf.start_time,
                    idle_for: wait_secs,
                    outcome: None,
                    fn_ref: None,
                },
            )?;
            let _ = before_sleep.call1((state,));
        }

        let sleep = retrying.getattr("sleep")?;
        sleep.call1((wait_secs,))?;

        Ok(true)
    }
}

/// Wrapper returned by Retrying(fn); callable with (*args, **kwargs) to run the retry loop.
#[pyclass(module = "tenacity_rs.tenacity_rs", name = "RetryingWrapper")]
pub struct RetryingWrapper {
    retrying: Py<PyAny>,
    fn_: Py<PyAny>,
}

#[pymethods]
impl RetryingWrapper {
    #[new]
    fn new_py(retrying: Py<PyAny>, fn_: Py<PyAny>) -> Self {
        Self { retrying, fn_ }
    }

    #[pyo3(signature = (*args, **kwargs))]
    fn __call__(
        &self,
        py: Python<'_>,
        args: &Bound<'_, PyTuple>,
        kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Py<PyAny>> {
        let retrying = self.retrying.bind(py);
        let kwargs_obj = kwargs
            .map(|k| k.into_py(py))
            .unwrap_or_else(|| py.None().into_py(py));
        let result =
            retrying.call_method1("do_retry", (self.fn_.bind(py), args, kwargs_obj.bind(py)))?;
        result.extract()
    }
}

/// Register retrying types and exceptions.
pub fn register_retrying(m: &Bound<'_, PyModule>, py: Python<'_>) -> PyResult<()> {
    m.add_class::<RetryCallState>()?;
    m.add_class::<Retrying>()?;
    m.add_class::<RetryingIterator>()?;
    m.add_class::<AttemptContext>()?;
    m.add_class::<RetryingWrapper>()?;
    m.add("RetryError", py.get_type_bound::<RetryError>())?;
    m.add("TryAgain", py.get_type_bound::<TryAgain>())?;
    Ok(())
}
