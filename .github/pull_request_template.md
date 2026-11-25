## Summary

<!-- What changes, and why? Keep it focused on the user-visible or reviewer-visible change. -->

## Related Issues

<!-- Reference any related GitHub issues, for example `Fixes #123` or `Closes #123` so the issue closes when this PR merges. -->

Fixes #

## Checklist

- [ ] Tests added or updated where necessary.
- [ ] Existing tests pass (`cargo test --workspace --locked`).
- [ ] `cargo fmt --all -- --check` executed successfully.
- [ ] Documentation updated where necessary.
- [ ] No unrelated changes introduced.

## Verification

- [ ] `cargo fmt --all -- --check`
- [ ] `cargo test --workspace --locked`
- [ ] `stellar contract build --locked --package procuresettle`

## Breaking changes or public interface changes

<!-- Optional. List any change to public contract functions, storage structures, or error codes. Write "None" if there are none. -->
