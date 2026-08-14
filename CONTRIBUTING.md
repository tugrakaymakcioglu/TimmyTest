# Contributing to TimmyTest ⚡

Thank you for your interest in improving **TimmyTest**! We welcome contributions from the community.

---

## 🛠️ Development Setup

1. **Fork and Clone the Repository**:
   ```bash
   git clone https://github.com/tugrakaymakcioglu/TimmyTest.git
   cd TimmyTest
   ```

2. **Create Virtual Environment with `uv`**:
   ```bash
   uv venv
   # On Linux/macOS:
   source .venv/bin/activate
   # On Windows:
   .\.venv\Scripts\activate
   ```

3. **Install in Editable Mode with Dev Dependencies**:
   ```bash
   uv pip install -e .[dev]
   ```

---

## 🧪 Testing & Code Quality

Before submitting a pull request, please ensure all checks pass:

1. **Run Pytest Suite**:
   ```bash
   pytest -v
   ```

2. **Run Linter (Ruff)**:
   ```bash
   ruff check .
   ```

3. **Run Type Checker (Mypy)**:
   ```bash
   mypy src
   ```

---

## 🧠 A note on `registry/learned.yaml`

`src/timmytest/registry/learned.yaml` is **machine-generated** — it is an overlay
of detection rules mined from real open-source repositories and merged on top of
the hand-curated `ecosystems.yaml` at load time. Do not edit it by hand; changes
there are overwritten on the next regeneration. To adjust detection, edit
`ecosystems.yaml`, which always wins on anything the overlay is not allowed to
touch (test commands in particular).

---

## 📝 Pull Request Guidelines

- Create a feature branch (`git checkout -b feature/my-new-feature`).
- Write meaningful commit messages.
- Ensure new features include corresponding unit tests in `tests/`.
- Open a Pull Request against the `main` branch with a clear description of changes.

---

## 📜 Code of Conduct

We are committed to providing a friendly, safe, and welcoming environment for all contributors.
