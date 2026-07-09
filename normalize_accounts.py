from pathlib import Path
import runpy


runpy.run_path(
    str(Path(__file__).resolve().parent / "scripts" / "pipeline" / "normalize_accounts.py"),
    run_name="__main__",
)
