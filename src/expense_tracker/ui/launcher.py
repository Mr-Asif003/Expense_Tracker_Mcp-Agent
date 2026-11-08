"""``expense-tracker-ui`` console script: start the Streamlit app."""

from __future__ import annotations

import sys
from pathlib import Path

APP_PATH = Path(__file__).with_name("app.py")


def main() -> None:
    """Run ``streamlit run app.py`` with any extra CLI arguments passed through."""
    from streamlit.web import cli as stcli

    sys.argv = ["streamlit", "run", str(APP_PATH), *sys.argv[1:]]
    raise SystemExit(stcli.main())


if __name__ == "__main__":
    main()
