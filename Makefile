.PHONY: fmt test build check-evidence clean

fmt:
	cargo fmt --all -- --check

test:
	cargo test --workspace --locked

build:
	stellar contract build --locked --package procuresettle

check-evidence:
	python3 scripts/verify-evidence-checksums.py

clean:
	cargo clean
