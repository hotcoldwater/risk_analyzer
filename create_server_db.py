from pathlib import Path
import runpy


runpy.run_path(
    str(Path(__file__).resolve().parent / "scripts" / "pipeline" / "create_server_db.py"),
    run_name="__main__",
)
