# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| `0.1.x` | Yes |
| Earlier versions | No |

Security fixes are considered for the current `0.1.x` release line. Users
should upgrade to the latest available release in that line.

## Reporting a vulnerability

Please do not disclose suspected vulnerabilities in public issues or pull
requests.

The upstream repository does not currently have GitHub private vulnerability
reporting enabled, and no private reporting email or PGP key has been
published. Do not send vulnerability details through a public GitHub channel.
Contact the maintainer through their [GitHub
profile](https://github.com/starboytiimz) to request a private reporting
channel; share technical details only after a private channel has been
confirmed. The project should enable GitHub private vulnerability reporting or
publish a dedicated security contact to make confidential reports directly
available.

When a private channel is confirmed, include the affected version or commit,
the relevant component, the potential impact, and concise reproduction
information. Do not include real credentials, private keys, or other users'
data. There is currently no published PGP key.

## Response expectations

The project aims to acknowledge a report within five business days and provide
an initial assessment or status update within 30 calendar days. These are
targets, not guarantees; investigation time depends on severity, complexity,
and maintainer availability. The project will coordinate remediation and
disclosure with the reporter where practical.

## Scope and limitations

Reports may cover the Soroban contract, authorization and settlement behavior,
arithmetic, token interactions, storage lifecycle, and project verification
scripts where a security impact is demonstrated. Issues in external networks,
assets, RPC services, or dependencies should identify the project behavior
that creates or amplifies the impact.

Repository tests and execution evidence are not a third-party security audit
or a production-readiness assessment. The known boundaries and security
disclaimers are documented in [docs/LIMITATIONS.md](docs/LIMITATIONS.md).
