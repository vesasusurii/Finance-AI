"""
Backward-compatible entry point — seeds finance + admin users.
Prefer: python scripts/seed_users.py
  docker compose exec backend python scripts/seed_users.py
"""
 
from pathlib import Path
import runpy
 
if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parent / "seed_users.py"), run_name="__main__")