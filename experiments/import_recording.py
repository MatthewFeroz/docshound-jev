"""Import the captured Jev demo without overwriting an existing run."""

import os

from run_t3code import ROOT

os.environ["DOCSHOUND_DB_PATH"] = str(ROOT / "backend/data/jev-t3code.db")

if __name__ == "__main__":
    from app.run_store import load_run, save_run
    from app.state import AgentState

    path = ROOT / "demo/jev/recorded-run.json"
    state = AgentState.model_validate_json(path.read_text(encoding="utf-8"))
    if load_run(state.run_id) is None:
        save_run(state)
        print(f"Imported recorded run {state.run_id}")
    else:
        print(f"Run {state.run_id} is already present; kept the existing record")
