from pathlib import Path

PROJECT_ROOT = Path.cwd()
DATA_DIR = PROJECT_ROOT / "data"
VERSION_FILE = PROJECT_ROOT / "current_census_data_version.txt"
PREPROCESS_SCRIPT_ARG_PATH = "./dashboard/preprocess.py"
