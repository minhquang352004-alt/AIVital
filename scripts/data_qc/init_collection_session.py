"""Create a metadata-only collection session; never invent capture measurements."""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "docs" / "CollectionPackage_V1"


def session_directory(subject: str, session: str, base: Path) -> Path:
    for value in (subject, session):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
            raise ValueError("IDs must contain only letters, digits, underscore or hyphen")
    path = (base / subject / session).resolve()
    if not path.is_relative_to(PACKAGE.resolve()):
        raise ValueError("Output must stay inside docs/CollectionPackage_V1")
    return path


def initialize(subject: str, session: str, base: Path, dry_run: bool = False) -> Path:
    path = session_directory(subject, session, base)
    if path.exists():
        raise FileExistsError(f"Session already exists: {path}")
    metadata = json.loads((PACKAGE / "SESSION_METADATA_TEMPLATE.json").read_text(encoding="utf-8"))
    metadata.update(subject_id=subject, session_id=session, sample_id=f"{subject}_{session}",
                    initialization_timestamp=datetime.now(timezone.utc).isoformat(),
                    session_mode="video_only")
    if not dry_run:
        path.mkdir(parents=True, exist_ok=False)
        (path / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--output-base", type=Path, default=PACKAGE / "data_samples")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(initialize(args.subject_id, args.session_id, args.output_base, args.dry_run))


if __name__ == "__main__":
    main()
