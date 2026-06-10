"""Smoke-test KHDA open-data registry download and row count."""

from __future__ import annotations

from dubai.data_sources import fetch_registry


def main() -> int:
    sources = fetch_registry()
    if not sources:
        print("Registry fetch returned zero schools.")
        return 1

    sample = sources[0]
    print(
        f"OK: {len(sources)} schools loaded "
        f"(sample: {sample.get('school_name', sample.get('school_id'))})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
