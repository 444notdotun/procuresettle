# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| `0.1.x` | Yes |
| Earlier versions | No |

Security fixes are considered for the current `0.1.x` release line. Users
should upgrade to the latest available release in that line.

See [`CHANGELOG.md`](CHANGELOG.md) for release history and
[`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) for the security boundaries of
the project.

## Scope

This policy covers the ProcureSettle Soroban contract
(`contracts/po-settlement/`), its authorization and settlement behavior,
arithmetic, token interactions, storage lifecycle, and the repository's
verification scripts where a security impact is demonstrated. Issues that only
affect external networks, assets, RPC services, or third-party dependencies
should still be reported if they identify project behavior that creates or
amplifies the impact.

Repository tests and execution evidence are not a third-party security audit
or a production-readiness assessment. The known boundaries and security
disclaimers are documented in [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## Reporting a vulnerability

Please do not disclose suspected vulnerabilities in public issues or pull
requests. Vulnerabilities include issues with contract authorization,
quantities or accounting, token interaction edge cases, denial of service on
the contract state machine, and unsafe handling of cryptographic or contract
data.

### Private reporting channels currently available

The upstream repository does not currently have GitHub private vulnerability
reporting enabled, and no dedicated security email address or PGP key has been
published. Until a dedicated channel exists, the private-contact procedure is:

1. Do **not** post vulnerability details in a public GitHub issue, pull
   request, or discussion.
2. Contact the maintainer through their [GitHub
   profile](https://github.com/starboytiimz) to request a private reporting
   channel.
3. Share technical details only after a private channel has been confirmed.
   The project intends to enable GitHub private vulnerability reporting or
   publish a dedicated security contact so that confidential reports become
   directly available.

### What to include in a report

When a private channel is confirmed, include:

- The affected release version or the exact commit you tested.
- The relevant component (for example, a specific contract entry point,
  storage key, or verification script).
- The potential security impact and the conditions required to trigger it.
- Concise reproduction information: inputs, prerequisites, and the observed
  versus expected result.
- Any supporting logs or transaction data that do not contain secrets.

Do not include real credentials, private keys, seed phrases, or other users'
data in the report.

## Reaction and response timeline

The project aims to:

- **Acknowledge** a report within **five business days** of receiving it.
- Provide an **initial assessment or status update** within **30 calendar
  days**.

These are targets, not guarantees; the actual time depends on severity,
complexity, and maintainer availability. The project will coordinate
remediation and disclosure with the reporter where practical.

## Assessment, remediation, and disclosure

After a report is received, the maintainers will:

- Confirm receipt within the acknowledgement target above.
- Triage the report and assess its severity and applicability on the contract's
  actual behavior and the recorded evidence.
- Work on a fix in the supported `0.1.x` line. Because this is an open-source
  Soroban contract project, remediation is coordinated through the normal
  contribution process, and the repository's pinned toolchain and CI checks
  apply to any fix.
- Keep the reporter informed of progress and decisions where practical, while
  avoiding premature publication of details.

### Coordinated disclosure

The project follows a coordinated disclosure approach. The reporter is asked
to allow a reasonable time window for the maintainers to assess and fix the
issue and to prepare a release before public disclosure. The project will
propose a disclosure date when the fix is ready, and will credit the reporter
unless they ask not to be credited. If the reporter believes an issue is being
actively exploited or is otherwise critical, they should say so in the initial
report so triage priority can be adjusted.

## Security limitations

- The repository's tests and CI are correctness and reproducibility checks;
  they are not a substitute for an independent security audit.
- The contract is not a general escrow or dispute-resolution product: it
  records supplier assertions and buyer acceptances and does not verify
  physical delivery.
- The settlement token's behavior, issuer policy, and the network environment
  are external to the contract; see
  [docs/TOKEN-COMPATIBILITY.md](docs/TOKEN-COMPATIBILITY.md).
- Storage TTL is a lifecycle mechanism and not an access-control boundary;
  anyone can extend or restore entries. See
  [docs/STORAGE-TTL.md](docs/STORAGE-TTL.md).
- No Mainnet deployment exists; the only public network evidence is recorded on
  Stellar Testnet.
