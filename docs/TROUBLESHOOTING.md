# Troubleshooting

Common setup problems when building ProcureSettle or reproducing its local
proofs. Each entry lists the symptoms, the cause, and the fix. Tool versions
are pinned in [`rust-toolchain.toml`](../rust-toolchain.toml),
[`CONTRIBUTING.md`](../CONTRIBUTING.md), and
[`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

## `error[E0463]: can't find crate for core`

**Symptoms:** building the contract for WASM (for example with
`stellar contract build`) stops with `error[E0463]: can't find crate for
core`.

**Cause:** the `wasm32v1-none` compilation target is not installed for the
pinned Rust toolchain. This can happen when the toolchain was installed without
the target, such as with a plain `rustup toolchain install 1.95.0`.

**Fix:** install the target for the pinned toolchain, then confirm it is
listed:

```sh
rustup target add --toolchain 1.95.0 wasm32v1-none
rustup target list --installed --toolchain 1.95.0
```

## `stellar: command not found`

**Symptoms:** a build or proof command fails with `stellar: command not found`.

**Cause:** Stellar CLI is not installed, or the directory containing its binary
is not on your `PATH`. The repository pins Stellar CLI **28.1.0**.

**Fix:** install Stellar CLI 28.1.0 using the [official Stellar CLI
installation
instructions](https://developers.stellar.org/docs/tools/developer-tools/cli/stellar-cli),
make sure the install location is on your `PATH` (open a new shell if you just
changed it), and confirm the version:

```sh
stellar --version
```

The first line should report `28.1.0`, which is the version CI checks.

## Quickstart container fails to bind port 8000

**Symptoms:** starting the local network with `stellar container start local`
fails because Docker reports that port 8000 is already allocated or in use.

**Cause:** another process or container is already using port 8000. A common
source is a local proof container from an earlier run that was never stopped.
The CI workflow and `scripts/local-cancellation-proof.py` expect the local
network at `http://localhost:8000`.

**Fix:** find what holds the port and stop it, then start the network again:

```sh
docker ps --filter publish=8000
lsof -i :8000
```

Stop a leftover container with `stellar container stop <container-name>` (the
CI container is named `procuresettle-local-proof`) or `docker stop
<container-name>`. If the port is held by an unrelated program, stop that
program instead.

## Polling timeout with HTTP 404 for a local Horizon account

**Symptoms:** a script or command polling
`http://localhost:8000/accounts/<address>` keeps receiving HTTP 404 until its
attempts run out. In CI this ends with `Quickstart did not expose funded account
<identity> through Horizon after 30 attempts`.

**Cause:** Horizon returns 404 for an account that does not exist on the ledger
yet. A 404 before funding is normal and only shows that Horizon is serving
requests. A timeout means the account was never created: the local Friendbot
request failed or has not landed (Friendbot can return transient errors such as
HTTP 502; see [`docs/EVIDENCE.md`](EVIDENCE.md)), the network is not fully
ready, or the address being polled is not the one that was funded.

**Fix:**

1. Check that the network is ready. `curl http://localhost:8000/health` should
   report `database_connected`, `core_up`, and `core_synced` as `true`.
2. Confirm the address belongs to your identity with
   `stellar keys public-key <identity>`.
3. Request funding again, then poll until the response is HTTP 200:

   ```sh
   curl "http://localhost:8000/friendbot?addr=<address>"
   curl -i http://localhost:8000/accounts/<address>
   ```

4. If it still returns 404, stop the container and start a fresh local
   network, then repeat the steps above.
