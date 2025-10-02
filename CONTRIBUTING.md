
# Contributing to PhaseBridge

🎉 Thanks for your interest in contributing! PhaseBridge is a small, dependable core for **lossless discrete ↔ phase ↔ discrete** interchange.

> **Golden rule:** The *lossless round-trip contract* is sacred:
> `decode(encode(x)) == x` for the declared alphabet.

---

## Getting Started

1. **Fork & clone**

    ```bash
   git clone https://github.com/synqratech/phasebridge.git
   cd phasebridge
    ```

2. **Set up Python 3.10+**

    ```bash
    python -m venv .venv
    source .venv/bin/activate   # Windows: .venv\Scripts\activate
    pip install -e .[dev]
    
    ```

3. **Run tests**

    ```bash
    pytest -q
    ```

---

## Ways to Contribute

- **Code** — new adapters, bug fixes, performance.
- **Docs** — clarify, add examples, fix typos.
- **Tests** — expand coverage, property checks.
- **Tooling** — CI, packaging, developer UX.
- **Integrations** — connectors, bindings, demos.

---

## Core Principles

- **Lossless first**: round-trip must be exact unless explicitly marked `processed:*`.
- **Numeric discipline**: `theta` is float64, wrapped to `[0, 2π)`.
- **Schema discipline**: `schema.alphabet.type="uint"`, valid `M ∈ [2..2^32]`.
- **API style**: keep it small (`encode`, `decode`, `kappa`, `validate`), clear errors, type hints.

For detailed developer guidelines, see `docs/development.md`.

---

## Commit & PR Process

1. **Branch**: `feat/...`, `fix/...`, `docs/...`, `test/...`.
2. **Write tests** for fixes and new features.
3. **Run tests** before pushing: `pytest -q`.
4. **Commit messages**: use concise imperatives, e.g.
    - `feat: add MessagePack encoder`
    - `fix: wrap theta to [0, 2π)`
    - `docs: add image round-trip demo`
5. **Open a PR** with a clear description and link issues if relevant.

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

🙌 Thank you for helping make PhaseBridge reliable and useful!
