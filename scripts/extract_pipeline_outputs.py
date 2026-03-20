from __future__ import annotations

import os
import sys
from pathlib import Path

from src.telemetry.pipeline_log_parser import extract_pipeline_outputs


def main() -> None:
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/pipeline.log")
    output_path = os.environ["GITHUB_OUTPUT"]

    log_text = log_path.read_text(encoding="utf-8")
    outputs = extract_pipeline_outputs(log_text)

    with open(output_path, "a", encoding="utf-8") as file:
        for key, value in outputs.items():
            file.write(f"{key}={value}\n")


if __name__ == "__main__":
    main()
