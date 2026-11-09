"""Command line: python -m app.synthetic generate --seed S --count N [--out FILE]."""

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from app.synthetic.generator import generate_profiles
from app.synthetic.params import GeneratorParams
from app.synthetic.serialize import population_document

DEFAULT_SEED = 42
DEFAULT_COUNT = 60


def _positive(value: str) -> int:
    """Parse a positive integer for argparse."""
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def _parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(prog="python -m app.synthetic", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="write profiles as JSON, no database access")
    generate.add_argument("--out", help="write to a file instead of stdout")
    generate.add_argument("--seed", type=int, default=DEFAULT_SEED)
    generate.add_argument("--count", type=_positive, default=DEFAULT_COUNT)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command line.

    :param argv: Arguments without the program name; defaults to ``sys.argv``.
    :return: Process exit code.
    """
    args = _parser().parse_args(argv)
    params = dataclasses.replace(GeneratorParams(), count=args.count)
    profiles = generate_profiles(params, args.seed)
    text = json.dumps(population_document(params, args.seed, profiles), indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
