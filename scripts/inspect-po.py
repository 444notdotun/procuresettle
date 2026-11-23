#!/usr/bin/env python3
"""Print a deployed purchase order and its lines as JSON using Stellar CLI."""

import argparse
import json
import subprocess
import sys
from urllib.request import Request, urlopen


# CLI 28.1.0 requires a source even for simulations. The all-zero public key
# satisfies the CLI without requiring an identity or signing any transaction.
SIMULATION_SOURCE = "GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWHF"


def rpc_passphrase(url):
    """Stellar CLI requires the network passphrase with an explicit RPC URL."""
    if not url.startswith(("http://", "https://")):
        raise ValueError("--rpc-url requires an HTTP or HTTPS URL")
    request = Request(
        url,
        data=b'{"jsonrpc":"2.0","id":1,"method":"getNetwork"}',
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=15) as response:
        reply = json.load(response)
    if "error" in reply:
        raise ValueError(f"getNetwork failed: {reply['error']}")
    return reply["result"]["passphrase"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract-id", required=True)
    parser.add_argument("--po-id", required=True, type=int)
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--network", default="local", help="Stellar CLI network (default: local)")
    target.add_argument("--rpc-url", help="use this RPC endpoint directly")
    args = parser.parse_args()
    if not 0 <= args.po_id < 2**64:
        parser.error("--po-id must be an unsigned 64-bit integer")

    try:
        network = ["--network", args.network]
        if args.rpc_url:
            network = [
                "--rpc-url", args.rpc_url,
                "--network-passphrase", rpc_passphrase(args.rpc_url),
            ]
        invoke = [
            "stellar", "contract", "invoke", "--send=no",
            "--source-account", SIMULATION_SOURCE,
            "--contract-id", args.contract_id, *network, "--",
        ]

        def query(method, *params):
            command = [*invoke, method, "--po_id", str(args.po_id), *params]
            result = subprocess.run(command, stdout=subprocess.PIPE, text=True, check=True)
            return json.loads(result.stdout)

        header = query("get_po")
        lines = [query("get_line", "--line_id", str(line_id)) for line_id in header["line_ids"]]
        print(json.dumps({"header": header, "lines": lines}, indent=2))
    except subprocess.CalledProcessError:
        # Stellar prints the contract or network error to stderr.
        return 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Cannot inspect PO {args.po_id}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
