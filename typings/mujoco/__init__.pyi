# mujoco's bindings are compiled modules without type information, so pyright can't see
# MjModel, MjSpec, mj_kinematics and the rest. This partial stub types the top-level names as
# Any; submodules (mujoco.viewer, ...) still resolve to the installed package (py.typed: partial).
from typing import Any

def __getattr__(name: str) -> Any: ...
