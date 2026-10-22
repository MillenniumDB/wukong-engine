<!-- omit from toc -->
# 📏 Benchmarks

Benchmarks of the engine's general use: which LLMs to support, and which settings to give them by default or expose as configuration. Each one lives in its own directory, with its method, its setup and its results.

> ⚠️ These have nothing to do with [`paper/`](/paper), whose benchmark belongs to a research paper.

| Benchmark                     | Question                                                                                         | Status      |
| ----------------------------- | ------------------------------------------------------------------------------------------------ | ----------- |
| [`llm_effort/`](llm_effort/) | How do the supported models extract at each reasoning effort level, and at what cost?            | Done (2026-10-22) |

Every step that calls an LLM provider costs money, and the scripts only spend it when explicitly asked to (e.g. with `--submit`), after showing an estimate.
