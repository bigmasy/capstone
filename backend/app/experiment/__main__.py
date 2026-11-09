"""Command line of the offline experiment and of the demo model training.

``python -m app.experiment h1|h2 --config smoke|full|FILE [--out FILE]`` runs a hypothesis.
``python -m app.experiment train --out DIR [--config demo] [--seed S]`` trains the plain ranker on
the synthetic world and writes the model artifact (``model.txt`` and ``manifest.json``) to DIR.
"""

import argparse
import dataclasses
import sys
from pathlib import Path

from app.experiment.config import load_config
from app.experiment.h2 import run_h2
from app.experiment.report import write_result
from app.experiment.world import WORLD_NAMES


def _parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(prog="python -m app.experiment", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, text in (("h1", "learned ranker against the baselines"), ("h2", "density sweep")):
        command = commands.add_parser(name, help=text)
        command.add_argument(
            "--config", required=True, help="preset name (smoke, full) or path of a JSON file"
        )
        command.add_argument("--out", help="write the result to a file instead of stdout")
        command.add_argument("--world", choices=WORLD_NAMES, help="override the world")
        if name == "h1":
            command.add_argument(
                "--artifact-dir", help="export the model of generation 0 as an artifact"
            )
    train = commands.add_parser("train", help="train the ranker and write a model artifact")
    train.add_argument("--out", required=True, help="directory of the artifact")
    train.add_argument("--config", default="demo", help="preset name or path of a JSON file")
    train.add_argument("--seed", type=int, help="seed of the synthetic data (default: the preset)")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command line.

    :param argv: Arguments without the program name; defaults to ``sys.argv``.
    :return: Process exit code.
    """
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
    except (OSError, ValueError) as error:
        parser.error(f"cannot use the configuration: {error}")
    if getattr(args, "world", None):
        config = dataclasses.replace(config, world=args.world)
    if args.command == "train":
        # Imported here for the same reason as run_h1
        from app.experiment.h1 import train_artifact  # noqa: PLC0415

        if args.seed is not None:
            config = dataclasses.replace(config, base_seed=args.seed)
        train_artifact(config, Path(args.out))
        return 0
    if args.command == "h1":
        # Imported here so that h2 and the help text work without LightGBM
        from app.experiment.h1 import run_h1  # noqa: PLC0415

        artifact_dir = Path(args.artifact_dir) if args.artifact_dir else None
        write_result(run_h1(config, artifact_dir), args.out)
    else:
        write_result(run_h2(config), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
