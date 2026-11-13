# Releasing ftqc

Source repository: https://github.com/ftqc/ftqc
Package index: https://pypi.org/project/ftqc/

1. Review the scientific assumptions, Apache-2.0 license, version, and README.
   Update versions in `pyproject.toml`, `src/ftqc/__init__.py`, and report metadata
   in `src/ftqc/estimator.py` together.
2. In a clean virtual environment, install the package, `build` and `twine`.
   Run `python -m unittest discover -s tests -v`, then `python -m build`
   and `python -m twine check dist/*`. Remove old release artifacts first.
3. Install the wheel in another clean environment. Run `ftqc --version`, the
   README example, and `python examples/compare_hardware.py`. Verify there are no
   source-directory imports or undeclared runtime dependencies.
4. For a test release, use a separately configured TestPyPI token with
   `python -m twine upload --repository testpypi dist/*`. Install that exact
   version from the test index into a clean environment and repeat the smoke test.
5. Upload the reviewed artifacts with `python -m twine upload dist/*`, using
   configured PyPI publishing credentials. Do not commit API tokens. Tag the
   matching source and retain artifact checksums. Published versions cannot be reused.
6. Confirm PyPI metadata, install that exact version from PyPI in a clean
   environment, and run tests again against the installed package.

The included GitHub Actions workflow tests and builds; it does not publish.
Only claim support on additional Python versions after CI has run successfully.
