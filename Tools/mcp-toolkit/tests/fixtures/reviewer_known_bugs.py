"""Test file with KNOWN bugs that the reviewer SHOULD catch.

Each function/section is labeled with the expected rule ID.
"""
import json
import os
import pickle
import re
import subprocess
import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Set


# === PY-SEC-01: eval() usage ===
def process_user_input(data):
    result = eval(data)  # SHOULD flag: PY-SEC-01
    return result


# === PY-SEC-02: os.system / shell=True ===
def run_command(cmd):
    os.system(cmd)  # SHOULD flag: PY-SEC-02
    subprocess.run(cmd, shell=True)  # SHOULD flag: PY-SEC-02


# === PY-SEC-03: pickle.load ===
def load_data(filepath):
    with open(filepath, "rb") as f:
        return pickle.load(f)  # SHOULD flag: PY-SEC-03


# === PY-SEC-04: f-string injection ===
def query_db(cursor, user_id):
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")  # SHOULD flag: PY-SEC-04


# === PY-SEC-05: exec() ===
def dynamic_code(code_str):
    exec(code_str)  # SHOULD flag: PY-SEC-05


# === PY-COR-01: Mutable default argument ===
def append_item(item, items=[]):  # SHOULD flag: PY-COR-01
    items.append(item)
    return items


def merge_dicts(data, extra={}):  # SHOULD flag: PY-COR-01
    extra.update(data)
    return extra


# === PY-COR-02: Bare except ===
def risky_operation():
    try:
        do_something()
    except:  # SHOULD flag: PY-COR-02
        pass


# === PY-COR-06: dict.get with mutable default that IS mutated ===
def build_mapping(config):
    items = config.get("items", [])
    items.append("new_item")  # Mutating the default - SHOULD flag: PY-COR-06
    return items


# === PY-COR-12: Broad except that silently swallows ===
def silent_swallow():
    try:
        do_something()
    except Exception as e:  # SHOULD flag: PY-COR-12 (silent swallow)
        pass


# === PY-COR-15: Lambda in loop captures loop var ===
def make_callbacks():
    callbacks = []
    for i in range(10):
        callbacks.append(lambda: i)  # SHOULD flag: PY-COR-15 - late binding bug
    return callbacks


# === PY-COR-10: Float equality ===
def check_value(x):
    if x == 0.5:  # SHOULD flag: PY-COR-10
        return True
    return False


# === PY-COR-04: open() without context manager ===
def read_file(path):
    f = open(path)  # SHOULD flag: PY-COR-04
    data = f.read()
    f.close()
    return data


# === PY-COR-03: Comparing with None using == ===
def check_none(val):
    if val == None:  # SHOULD flag: PY-COR-03
        return True
    return False


# === PY-STY-04: Global variable mutation ===
_counter = 0


def increment():
    global _counter  # SHOULD flag: PY-STY-04
    _counter += 1


# Helper to make do_something exist
def do_something():
    pass


# ===========================================================================
# TERRAIN AUDIT CORPUS (2026-04-09) — 4 new reviewer rules + ≥5 fixtures each
# Each fixture is a minimal reproduction of a real P0 bug from the terrain
# branch audit. `fn_that_returns_delta` et al. are stand-ins for the real
# producer functions; the bug is in the call site.
# ===========================================================================


def fn_that_returns_delta():
    return [0.0]


def carve_cave_volume(stack, path, spec):
    return [0.0]


def solve_outflow(network, stack):
    return [0.0]


def apply_wind_erosion(stack, params):
    return [0.0]


def compute_ridge_mask(stack):
    return [0.0]


class _FakeState:
    def rollback(self):
        pass

    def commit(self):
        pass


# === PY-COR-16: Discarded underscore-prefixed return value (terrain_caves.py:821) ===
def pass_caves_bug(state, path, spec):
    _delta = carve_cave_volume(state.mask_stack, path, spec)  # SHOULD flag: PY-COR-16
    state.commit()


def pass_waterfalls_bug(state):
    _pool_delta = fn_that_returns_delta()  # SHOULD flag: PY-COR-16
    _outflow_delta = solve_outflow(state, state)  # SHOULD flag: PY-COR-16
    return state


def pass_wind_erosion_bug(state, params):
    _eroded = apply_wind_erosion(state, params)  # SHOULD flag: PY-COR-16
    return state


def pass_ridges_bug(state):
    _ridge_mask = compute_ridge_mask(state)  # SHOULD flag: PY-COR-16
    return state


def pass_scatter_bug(state):
    _scatter_delta = fn_that_returns_delta()  # SHOULD flag: PY-COR-16
    return state


def pass_legit_discard():
    # Bare _ is explicit discard — should NOT flag
    _ = fn_that_returns_delta()


def pass_side_effect_ok():
    # function starts with "apply" — heuristic skips it
    _result = apply_wind_erosion(None, None)
    return _result  # read, so not discarded anyway


# === PY-COR-17: Frozen dataclass with mutable collection field ===
@dataclass(frozen=True)
class TerrainIntentStateBug:
    name: str
    intents: Dict[str, float] = field(default_factory=dict)  # SHOULD flag: PY-COR-17


@dataclass(frozen=True)
class HeroFeatureSpecBug:
    feature_id: str
    tags: List[str] = field(default_factory=list)  # SHOULD flag: PY-COR-17


@dataclass(frozen=True)
class PassResultBug:
    pass_name: str
    dirty_channels: Set[str] = field(default_factory=set)  # SHOULD flag: PY-COR-17


@dataclass(frozen=True)
class ExportManifestBug:
    path: str
    metadata: dict = field(default_factory=dict)  # SHOULD flag: PY-COR-17


@dataclass(frozen=True)
class CaveSpecBug:
    archetype: str
    segments: list = field(default_factory=list)  # SHOULD flag: PY-COR-17


@dataclass(frozen=True)
class FrozenOKScalar:
    name: str
    value: float = 0.0  # Should NOT flag — scalar is hashable


# === PY-COR-18: Validator calls self.rollback() on failure path ===
class TerrainValidatorBug:
    def validate_unity_export_ready(self, state):
        if not state:
            self.rollback()  # SHOULD flag: PY-COR-18
            return False
        return True

    def validate_heightmap_bounds(self, state):
        if state is None:
            self.rollback()  # SHOULD flag: PY-COR-18
            return False
        return True

    def validate_bit_depth_contract(self, manifest):
        if manifest is None:
            self.rollback()  # SHOULD flag: PY-COR-18
            return False
        return True

    def validate_axis_swap(self, export):
        if not export:
            self.rollback()  # SHOULD flag: PY-COR-18
        return True

    def validate_registrar_complete(self):
        state = _FakeState()
        state.rollback()  # SHOULD flag: PY-COR-18 (state.rollback too)
        return False

    def validate_ok(self, state):
        # No rollback — should NOT flag
        return state is not None


# === PY-COR-19: Fallback branch returns before primary check ===
def is_in_frustum_bug(obj, camera):
    # fallback path returns OK before primary (forward dot) check
    if camera.basis_fallback:
        return True  # SHOULD flag: PY-COR-19 (fallback ok before primary)
    forward = camera.forward
    dot = forward.dot(obj.position)
    return dot > 0


def detect_kartst_bug(obj, state):
    # Comment marks fallback; primary check appears later
    if state.lattice_fallback:  # SHOULD flag: PY-COR-19
        return True  # fallback ok
    primary = obj.primary_check
    return primary


def import_dem_bug(tile):
    if tile.npy_fallback:  # SHOULD flag: PY-COR-19
        return True  # fallback
    primary = tile.tif_primary
    return primary


def shadow_clipmap_bug(tile):
    if tile.cloud_fallback:  # SHOULD flag: PY-COR-19
        return True  # fallback
    return tile.forward_sample


def water_variant_bug(variant, detector):
    if detector.fallback_enabled:  # SHOULD flag: PY-COR-19
        return True  # fallback branch
    main_check = detector.primary(variant)
    return main_check


# === PY-SEC-08: Path traversal ===
def read_user_file(user_path):
    return open(user_path).read()  # SHOULD flag: PY-SEC-08


def load_requested_asset(request_path):
    return Path(request_path).read_text()  # SHOULD flag: PY-SEC-08


# === PY-SEC-09: SSRF ===
def fetch_remote(user_url):
    return requests.get(user_url)  # SHOULD flag: PY-SEC-09


def post_remote(endpoint):
    return requests.post(endpoint)  # SHOULD flag: PY-SEC-09


# === PY-SEC-10: Template injection ===
def render_preview(template_source):
    return render_template_string(template_source)  # SHOULD flag: PY-SEC-10


def render_email(user_markup):
    return render_template_string(user_markup, user="demo")  # SHOULD flag: PY-SEC-10


# === PY-COR-20: Await while holding a lock ===
async def async_locked_write(lock):
    with lock:
        await save_state()  # SHOULD flag: PY-COR-20


async def async_locked_flush(self):
    async with self.cache_lock:
        await self.flush()  # SHOULD flag: PY-COR-20


# === PY-COR-21: Unlocked global mutation ===
SHARED_CACHE = {}
SHARED_LIST = []


def mutate_shared_cache(key, value):
    global SHARED_CACHE  # SHOULD flag: PY-COR-21
    SHARED_CACHE[key] = value


def append_shared(item):
    global SHARED_LIST  # SHOULD flag: PY-COR-21
    SHARED_LIST.append(item)


# === PY-COR-22: asyncio.gather without return_exceptions ===
async def gather_jobs(job1, job2):
    return await asyncio.gather(job1, job2)  # SHOULD flag: PY-COR-22


async def gather_more(tasks):
    return await asyncio.gather(*tasks)  # SHOULD flag: PY-COR-22


# === PY-PERF-04: logger f-string ===
def log_error(value):
    logger.error(f"bad value={value}")  # SHOULD flag: PY-PERF-04


def log_warning(name):
    logger.warning(f"missing asset {name}")  # SHOULD flag: PY-PERF-04


# === PY-RES-08: Popen without wait/communicate ===
def spawn_process(cmd):
    proc = subprocess.Popen(cmd)  # SHOULD flag: PY-RES-08
    return proc.pid


def spawn_detached(cmd):
    subprocess.Popen(cmd)  # SHOULD flag: PY-RES-08
    return True


# === PY-RES-09: requests without timeout ===
def fetch_json(url):
    return requests.get(url).json()  # SHOULD flag: PY-RES-09


def send_data(url, payload):
    return requests.post(url, json=payload)  # SHOULD flag: PY-RES-09


# === PY-COR-23: Optional-like result dereferenced without None check ===
def unsafe_lookup(repo, user_id):
    user = repo.find_user(user_id)  # SHOULD flag: PY-COR-23
    return user.name


def unsafe_resolve(locator, key):
    value = locator.resolve_optional(key)  # SHOULD flag: PY-COR-23
    return value["id"]

