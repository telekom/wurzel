# Wurzel

## Environment Setup
`make install` every make command like test will also run make install automatically.



## Testing instructions
Run `make test` to run all Tests in the folder

## Linting
Run `make lint` to run linting will run all pre-commit hooks


## Testing Standards

- Add tests for new behavior — cover success, failure, and edge cases.
- Use pytest patterns, not unittest.TestCase.
- Use `@pytest.mark.parametrize` for multiple similar inputs.


## TODOs

You are only done if `make lint` and `make test` are passing.
