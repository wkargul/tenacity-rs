# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [0.1.0] - 2025-02-17

### Added

- Initial release: drop-in replacement for [tenacity](https://github.com/jd/tenacity) with Rust core.
- API parity: `@retry`, stop strategies (`stop_after_attempt`, `stop_after_delay`, etc.), wait strategies (`wait_none`, `wait_fixed`, `wait_exponential`, `wait_random`, combined/chain), retry conditions (`retry_if_exception_type`, `retry_if_result`, etc.), callbacks (`before`, `after`, `before_sleep`), iterator pattern (`Retrying`), `RetryError`, `TryAgain`.
- Async support via same decorator and `AsyncRetrying`.
- Benchmark suite in `benchmarks/` comparing tenacity-rs vs tenacity.
- Docs: README, MIGRATION.md, CONTRIBUTING.md, PUBLISHING.md (PyPI + Trusted Publishing), LICENSE (MIT), NOTICE.

[Unreleased]: https://github.com/wkargul/tenacity-rs/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/wkargul/tenacity-rs/releases/tag/v0.1.0
