"""Serve the built DocsHound Jev demo on localhost with existing local credentials."""

import argparse

from run_t3code import configure

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8017)
    args = parser.parse_args()
    configure()
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port)
