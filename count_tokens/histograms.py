"""Script to generate histograms of token counts from run.py output.

Usage:
    uv run python -m count_tokens.histograms INPUT

Arguments:
    INPUT   Path to JSON file produced by count_tokens.run
    -o / --output   Optional directory to save histogram images (default: show interactively)

Examples:
    uv run python -m count_tokens.histograms out.json
    uv run python -m count_tokens.histograms out.json -o ./plots
"""

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(
        description="Generate histograms of token counts from count_tokens.run output."
    )
    parser.add_argument("input", help="Path to JSON file produced by count_tokens.run")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Directory to save histogram images (default: show interactively)",
    )
    args = parser.parse_args()

    with open(args.input) as f:
        data = json.load(f)

    if not data:
        print("No data found in input file.", file=sys.stderr)
        sys.exit(1)

    rcv = [entry["rcv_ub_n_tokens"] for entry in data]
    prd = [entry["prd_ub_n_tokens"] for entry in data]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Token Count Distributions")

    axes[0].hist(rcv, bins="auto", color="steelblue", edgecolor="white")
    axes[0].set_title("rcv_ub_n_tokens")
    axes[0].set_xlabel("Tokens")
    axes[0].set_ylabel("Count")

    axes[1].hist(prd, bins="auto", color="darkorange", edgecolor="white")
    axes[1].set_title("prd_ub_n_tokens")
    axes[1].set_xlabel("Tokens")
    axes[1].set_ylabel("Count")

    plt.tight_layout()

    if args.output is None:
        plt.show()
    else:
        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "token_histograms.png"
        fig.savefig(out_path, dpi=150)
        print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
