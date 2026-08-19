"""Opt-in load shapes for the infra-profile scenarios.

These drive the *run profile* (how many users over time), which is what produces
the calculator's infra-shaped outputs — not a per-request task:

    S18  step   ramp in steps and hold each; find the utilisation knee / safe point
    S15  burst  steady floor, then a sudden spike and recovery; HA floor + burst headroom
    S20  soak   ramp to target and hold long; watch autoscaler scale-up and scale-down

Run one shape at a time (Locust allows a single active shape). Select via env::

    QGPT_LOAD_SHAPE=step  locust -f load/shapes.py
    QGPT_LOAD_SHAPE=burst locust -f load/shapes.py
    QGPT_LOAD_SHAPE=soak  locust -f load/shapes.py

Importing the user class here lets `-f load/shapes.py` run standalone.
Without this file (plain `locust -f load/locustfile.py`) you drive users
manually with -u/-r, which is fine for S01/S03/S05 isolated capacity probes.
"""

import os

from locust import LoadTestShape

from load.locustfile import QGPTUser  # noqa: F401  (registers the user class)


def _int(env, default):
    try:
        return int(os.getenv(env, default))
    except (TypeError, ValueError):
        return default


SHAPE = os.getenv("QGPT_LOAD_SHAPE", "step").lower()

# Tunables (override via env). Keep spawn rates gentle enough to read the curve.
STEP_USERS = _int("QGPT_LOAD_STEP_USERS", 25)        # users added per step
STEP_HOLD = _int("QGPT_LOAD_STEP_HOLD", 120)         # seconds held per step
STEP_COUNT = _int("QGPT_LOAD_STEP_COUNT", 8)         # number of steps

BURST_FLOOR = _int("QGPT_LOAD_BURST_FLOOR", 20)      # steady baseline users
BURST_PEAK = _int("QGPT_LOAD_BURST_PEAK", 200)       # spike users
BURST_WARM = _int("QGPT_LOAD_BURST_WARM", 120)       # floor duration before spike
BURST_HOLD = _int("QGPT_LOAD_BURST_HOLD", 120)       # spike duration
BURST_COOL = _int("QGPT_LOAD_BURST_COOL", 180)       # recovery at floor

SOAK_USERS = _int("QGPT_LOAD_SOAK_USERS", 100)       # sustained target
SOAK_RAMP = _int("QGPT_LOAD_SOAK_RAMP", 300)         # ramp-up seconds
SOAK_HOLD = _int("QGPT_LOAD_SOAK_HOLD", 1800)        # hold seconds (30 min)


class QGPTLoadShape(LoadTestShape):
    """Single configurable shape; behaviour selected by QGPT_LOAD_SHAPE."""

    def _step(self, run_time):
        step = int(run_time // STEP_HOLD)
        if step >= STEP_COUNT:
            return None
        users = STEP_USERS * (step + 1)
        return users, STEP_USERS  # spawn one step's worth per step

    def _burst(self, run_time):
        if run_time < BURST_WARM:
            return BURST_FLOOR, BURST_FLOOR
        if run_time < BURST_WARM + BURST_HOLD:
            # Spawn fast to simulate a genuine spike.
            return BURST_PEAK, BURST_PEAK
        if run_time < BURST_WARM + BURST_HOLD + BURST_COOL:
            return BURST_FLOOR, BURST_PEAK
        return None

    def _soak(self, run_time):
        total = SOAK_RAMP + SOAK_HOLD
        if run_time >= total:
            return None
        if run_time < SOAK_RAMP:
            spawn_rate = max(1, SOAK_USERS // max(1, SOAK_RAMP // 10))
            users = min(SOAK_USERS, int(SOAK_USERS * (run_time / SOAK_RAMP)) + 1)
            return users, spawn_rate
        return SOAK_USERS, SOAK_USERS

    def tick(self):
        run_time = self.get_run_time()
        if SHAPE == "burst":
            return self._burst(run_time)
        if SHAPE == "soak":
            return self._soak(run_time)
        return self._step(run_time)
