"""Load and expose the Locust rig configuration.

All tunables live in ``load/load_config.json`` (the capacity-calculator knobs);
this module reads that once, layers environment-variable overrides on top for
secrets and CI, and hands the rest of the rig plain Python constants.

Nothing here launches Locust or touches the system under test.
"""

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
_CONFIG_PATH = os.path.join(_HERE, "load_config.json")


def _load_config():
    with open(_CONFIG_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


CONFIG = _load_config()

# --- Target -----------------------------------------------------------------
HOST = os.getenv("QGPT_LOAD_HOST", CONFIG["host"])

# --- Auth -------------------------------------------------------------------
_auth = CONFIG["auth"]
AUTH_MODE = os.getenv("QGPT_LOAD_AUTH_MODE", _auth["mode"])
LOGIN_PATH = _auth["login_path"]
API_KEY = os.getenv(_auth["api_key_env"], "")


def _fallback_creds():
    """Read the functional suite's valid_login only as a dev convenience.

    Preferred path is the QGPT_LOAD_USER / QGPT_LOAD_PASSWORD env vars; this
    fallback keeps a local run working without duplicating secrets into the
    load config. Returns ("", "") if the file is missing.
    """
    path = os.path.join(_PROJECT_ROOT, "data", "input_data.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            valid = json.load(fh).get("valid_login", {})
            return valid.get("username", ""), valid.get("password", "")
    except (OSError, ValueError):
        return "", ""


_fb_user, _fb_pass = _fallback_creds()
USERNAME = os.getenv(_auth["username_env"], _fb_user)
PASSWORD = os.getenv(_auth["password_env"], _fb_pass)

# --- Model isolation --------------------------------------------------------
_model = CONFIG["model"]
# Env override lets CI flip between infra-isolation (stub) and end-to-end runs.
STUB_MODEL = os.getenv("QGPT_LOAD_STUB_MODEL", str(_model["stub_model"])).lower() in (
    "1", "true", "yes", "on",
)
MODEL_NAME = _model["stub_model_name"] if STUB_MODEL else _model["real_model_name"]

# --- Pacing / timeouts ------------------------------------------------------
WAIT_MIN = CONFIG["pacing"]["wait_min_seconds"]
WAIT_MAX = CONFIG["pacing"]["wait_max_seconds"]
CONNECT_TIMEOUT = CONFIG["timeouts"]["connect_seconds"]
STREAM_HOLD_TIMEOUT = CONFIG["timeouts"]["stream_hold_seconds"]

# --- Mix (S12) --------------------------------------------------------------
# Percentages double as Locust task weights (relative integers).
MIX = CONFIG["mix_percent"]

# --- Per-scenario parameters ------------------------------------------------
_p = CONFIG["scenario_params"]
CONVERSATION_TURNS = _p["conversation_turns"]
LIGHT_FILE_BYTES = _p["light_file_bytes"]
HEAVY_FILE_BYTES = _p["heavy_file_bytes"]
RAG_TOP_K = _p["rag_top_k"]
AGENTIC_EXPECTED_CALLS = _p["agentic_expected_calls"]

# --- Endpoints (TODO CONFIRM) -----------------------------------------------
EP = CONFIG["endpoints"]
