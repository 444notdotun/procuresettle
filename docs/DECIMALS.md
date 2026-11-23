# Quantities, unit prices and token decimals

A purchase-order quantity counts whole items (unsigned 64-bit `u64`). A receipt records how many
of those items were delivered. Ordered quantities and receipt deltas must be
positive. Choose the counting unit before creating the order. For example,
order 1,500 grams to represent 1.5 kilograms.

A unit price is the price of **one counting unit**, expressed as a positive
`i128` in the settlement token's smallest unit. PO totals, funding, payouts and
refunds use that same base unit and signed 128-bit integer type. Scale the price once at the
client boundary, then multiply by the unscaled item count.

| Input or calculation | Contract value |
| --- | ---: |
| 1.0 XLM at seven decimals | 10,000,000 stroops |
| Unit price of 0.125 XLM | 1,250,000 stroops per item |
| Order of 8 items at that price | 10,000,000 stroops total |
| Accepted receipt for 3 items | 3,750,000 stroops paid |

For a seven-decimal asset, parse the price as decimal text, pad the fractional
part to seven places and combine the digits as an integer. Reject prices that
cannot be represented exactly or would overflow. Use the settlement token's
actual decimal precision when formatting and parsing other assets.

Integer arithmetic keeps each payout exact and reproducible across clients.
A binary floating-point approximation can place an amount on the wrong side
of a base-unit boundary. The contract uses checked integer multiplication
and addition. Its [numeric limitations](LIMITATIONS.md#current-limitations)
exclude fractional item counts, currency conversion, fees and rounding tolerances.
