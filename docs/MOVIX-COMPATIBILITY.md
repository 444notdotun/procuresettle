# Movix compatibility boundary and verification method

ProcureSettle contains a bounded, read-only compatibility proof for one pinned
Movix integer line-item fixture. The proof checks that the fixture can be
represented by ProcureSettle's integer quantity and integer token-base-unit
model, then independently recomputes the fixture total. It is a source-model
check, not an integration test.

## What is—and is not—claimed

The proof does not establish an official Movix integration, partnership,
maintainer review, endorsement, adoption, or compatibility with Movix's entire
product. It does not invoke Movix code, change Movix state, share a deployment,
or validate Movix's UI, identity, shipment, dispute, amendment, or production
escrow workflows. The same boundary applies to the separate Testnet experiment
that uses mapped numeric terms: it exercises ProcureSettle with those terms,
not Movix itself.

This scope agrees with [`docs/LIMITATIONS.md`](LIMITATIONS.md) and the review
boundary in [`docs/EXTERNAL-VALIDATION.md`](EXTERNAL-VALIDATION.md).

## Pinned fixture and numeric mapping

`scripts/movix-compatibility-proof.py` requires Movix commit
`05f2ba1dbe72a8f46e546b4509281e54933708e4` and verifies the selected source
blob identities before extracting the public `MOVIX-PO-0001` fixture. Its two
lines are mapped without rounding or currency conversion:

| Line | Movix quantity | Movix unit price (base units) | ProcureSettle line value |
| --- | ---: | ---: | ---: |
| 1 | 2 | 125,000,000 | 250,000,000 |
| 2 | 3 | 72,500,000 | 217,500,000 |
| **Total** |  |  | **467,500,000** |

The mapping preserves integer quantities, integer unit prices, and the
quantity-times-unit-price calculation. ProcureSettle treats these values as
token base units; it does not infer decimals, currency exchange rates, taxes,
fees, or Movix-specific semantics.

## Verification workflow

Run the checker from a checkout of the pinned Movix revision:

```sh
python3 scripts/movix-compatibility-proof.py \
  --movix-checkout /path/to/pinned/Movix \
  --output /path/to/report.json
```

The checker verifies the commit and expected blobs, extracts the line tuples,
recomputes both line values and the total, checks Movix's independent domain
calculation, and verifies the documented whole-order settlement and deferred
partial-release boundaries. A successful result is evidence only for those
checks. It should be reported as a read-only compatibility proof against the
pinned fixture, not as external validation or integration.
