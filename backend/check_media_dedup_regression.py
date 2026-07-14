import sys
from pathlib import Path

from app.media.deduplication_regression import checkDeduplicationRegression
from app.media.deduplication_thresholds import loadMediaDeduplicationThresholds


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    config = root / "configs" / "media_dedup_thresholds.json"
    approval = root / "configs" / "media_dedup_approval.json"
    try:
        result = checkDeduplicationRegression(
            loadMediaDeduplicationThresholds(config), approval
        )
    except ValueError as error:
        sys.stderr.write(f"Media deduplication regression: {error}\n")
        return 1
    sys.stdout.write(
        f"Media deduplication regression: {result.groupsChecked} groups passed "
        f"at precision >= {result.minimumPrecision:.3f}.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
