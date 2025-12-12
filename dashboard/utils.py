import os

DATA_DIR = "../data"
VERSION_FILE = os.path.join(DATA_DIR, "current_census_data_version.txt")


def get_current_version():
    """Read version from current version file or return None."""
    try:
        with open(VERSION_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def set_current_version(version: str):
    """Write version number to current_version.txt."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(VERSION_FILE, "w") as f:
        f.write(str(version))


def data_path_for_version(version: str):
    """Return full path to the parquet file associated with this version."""
    return os.path.join(DATA_DIR, f"sms_census_data_version_{version}.parquet")
