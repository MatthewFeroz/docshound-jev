"""Serve the built DocsHound Jev demo on localhost with existing local credentials."""

import argparse
import os

from run_t3code import ROOT, configure

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8017)
    parser.add_argument(
        "--replay",
        action="store_true",
        help="View the imported recording without credentials or live calls",
    )
    args = parser.parse_args()
    if args.replay:
        os.environ["JEV_SHADOW_ENABLED"] = "false"
        os.environ["DOCSHOUND_DB_PATH"] = str(ROOT / "backend/data/jev-t3code.db")
    else:
        configure()
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port)
