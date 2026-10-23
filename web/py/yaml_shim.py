"""Minimal `yaml` stand-in used inside Pyodide.

tools/build_web.py pre-converts every YAML file the simulation reads into JSON and writes
that JSON at the original *.yaml path in the Pyodide filesystem (JSON is valid YAML, but the
pure-Python YAML parser is far too slow in WebAssembly). This shim makes `yaml.load` /
`yaml.safe_load` parse that JSON and restores integer dict keys encoded as "__int__:<n>".
"""

import json

INT_KEY_PREFIX = "__int__:"


class SafeLoader:  # pragma: no cover - only used as a marker by sim/state.py
    pass


CSafeLoader = SafeLoader


def _decode_pairs(pairs):
    out = {}
    for k, v in pairs:
        if isinstance(k, str) and k.startswith(INT_KEY_PREFIX):
            k = int(k[len(INT_KEY_PREFIX):])
        out[k] = v
    return out


def load(stream, Loader=None):  # noqa: N803 - mirrors the PyYAML signature
    text = stream.read() if hasattr(stream, "read") else stream
    return json.loads(text, object_pairs_hook=_decode_pairs)


def safe_load(stream):
    return load(stream)
