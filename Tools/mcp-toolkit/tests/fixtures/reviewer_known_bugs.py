"""Test file with KNOWN bugs that the reviewer SHOULD catch.

Each function/section is labeled with the expected rule ID.
"""
import json
import os
import pickle
import re
import subprocess
import datetime


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
