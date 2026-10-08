---
code:
  - src/nao_viewer/model.py
  - src/nao_viewer/build_model.py
  - src/nao_viewer/models/nao_primitive.xml
  - src/nao_viewer/scenes/empty.xml
  - third_party/nao_description/nao.urdf
tests:
  - tests/test_model.py
  - tests/test_build_model.py
---

# Model

**Status:** Draft

## Purpose

The NAO as a MuJoCo model, and the one place that turns a NAOqi pose into MuJoCo state. Every other part of nao-viewer (the viewer, check-model) loads the robot and poses it through this module. The committed model uses primitive shapes only, so it can ship under MIT. The mesh variant is built on the user's machine (see [meshes.md](meshes.md)) on top of the same kinematics.

## Decided

### Source of truth: the vendored URDF

- `third_party/nao_description/nao.urdf` is the NAO V5 (H25) URDF from [ros-naoqi/nao_robot](https://github.com/ros-naoqi/nao_robot) `nao_description`, already expanded from xacro, taken at a pinned commit. Its `LICENSE` (BSD-3-Clause) sits next to it. A `SOURCE` file records the upstream repository, commit and path. `THIRD_PARTY_NOTICES.md` carries the copyright notice.
- The URDF is the only source of kinematics (link frames, joint axes, limits), masses and inertias. Its `<visual>` and `<collision>` mesh references (`package://nao_meshes/...`) are never resolved in the primitive build.

### Build: `nao-viewer build-model --variant primitive`

`build_model.py` regenerates `src/nao_viewer/models/nao_primitive.xml` from the URDF. It is a maintainer command, and its output is committed. The model sits inside the package so it ships in the wheel.

1. Parse the URDF with `xml.etree` and drop every `<visual>` and `<collision>` element, so MuJoCo never looks for a mesh.
2. Load the result with `mujoco.MjSpec` (MuJoCo's URDF importer). Then edit the spec in code:
   - make `torso` the root body with a free joint (fold the URDF's fixed `base_link` into it);
   - drop fixed-joint frame links that carry no mass, keeping their poses as sites (cameras, effectors, sole frames);
   - add the collision primitives from a hand-tuned table in `build_model.py` (body name → geom type, size, pos, quat): capsules for limbs, boxes for feet and torso, a sphere-capped capsule for the head;
   - add equality constraints, actuators, sensors, sites and cameras (see below).
3. Write the spec with `spec.to_xml()`. The build is deterministic: running it twice on the same URDF produces byte-identical XML.

### Model contents

- **Root**: `torso` body with a free joint named `root`. A world pose maps directly to `qpos[0:7]` as position, then quaternion `(w, x, y, z)`.
- **Joints**: the 26 H25 body joints, named exactly as NAOqi's `ALMotion.getBodyNames("Body")`, with ranges from the URDF limits. In NAOqi order:
  `HeadYaw HeadPitch LShoulderPitch LShoulderRoll LElbowYaw LElbowRoll LWristYaw LHand LHipYawPitch LHipRoll LHipPitch LKneePitch LAnklePitch LAnkleRoll RHipYawPitch RHipRoll RHipPitch RKneePitch RAnklePitch RAnkleRoll RShoulderPitch RShoulderRoll RElbowYaw RElbowRoll RWristYaw RHand`.
  `model.JOINT_NAMES` exposes this tuple.
- **Hands**: `LHand` and `RHand` are joints with range `[0, 1]` (NAOqi's open fraction). The URDF finger joints are kept and follow the hand joint through its `mimic` multiplier and offset.
- **Couplings**: `LHipYawPitch`/`RHipYawPitch` (one motor) and the finger mimics are joint equality constraints in the model, for any future physics use. Since nao-viewer never steps physics, constraints are not enforced at render time. `PoseWriter` applies the finger couplings itself (see below). `RHipYawPitch` is taken as reported by NAOqi.
- **Collision**: primitives only, with contacts between adjacent bodies excluded. Meshes are visual-only (`contype=conaffinity=0`), so collision is identical in both variants.
- **Actuators**: one `position` actuator per joint, named after the joint, all in a default class `nao_joint` that holds `kp`, `forcerange` and `damping` as named parameters. The values are placeholders until system identification, and they are unused by the viewer.
- **Sensors**: `jointpos` per joint; `gyro` and `accelerometer` at the `imu` site in the torso; 4 `force` sites per foot at the FSR positions (`LFsrFL LFsrFR LFsrRL LFsrRR`, same for `R`).
- **Cameras**: `CameraTop` and `CameraBottom` at the URDF camera frames, oriented so that MuJoCo's view (−Z forward, +Y up) matches the NAO image (not mirrored, horizon level when the head is level). `fovy` uses the V5 vertical field of view, 47.64°.
- **Effector sites**: `Head`, `LArm`, `RArm`, `LLeg`, `RLeg`, at the positions of NAOqi's end effectors for those chains, so [check_model.md](check_model.md) can compare `ALMotion.getTransform(name, FRAME_TORSO, True)` with the site frame directly.
- **Masses and inertias** come from the URDF.

### Scenes

The model holds the robot only. A scene is an MJCF file with the world around it (floor, lights, objects). `load_world(scene, variant)` attaches the robot into the scene with `MjSpec.attach`, so any scene works with either variant. Scenes ship in `src/nao_viewer/scenes/`. `empty.xml` (checker floor, one light) is the default; the other bundled scenes are listed in [api.md](api.md). `load_world` takes a bundled scene name or a path to a user file.

### Runtime API (`model.py`)

```python
JOINT_NAMES: tuple[str, ...]                        # the 26 names above, NAOqi order

def model_path(variant: Literal["auto", "primitive", "meshes"] = "auto") -> Path
def load_world(scene: str | Path | None = None, variant=...) -> mujoco.MjModel

@dataclass(frozen=True)
class NaoPose:
    angles: Mapping[str, float]                     # joint name -> rad (LHand/RHand: 0..1)
    torso_pos: tuple[float, float, float]           # m, world frame
    torso_quat: tuple[float, float, float, float]   # w, x, y, z

    @classmethod
    def from_naoqi(cls, names, angles, torso_transform) -> NaoPose   # transform: 16 floats, row-major 4x4

class PoseWriter:
    def __init__(self, model: mujoco.MjModel): ...  # resolves joint -> qpos address once
    def apply(self, data: mujoco.MjData, pose: NaoPose) -> None     # writes qpos, finger couplings, runs mj_kinematics
```

- `model_path("auto")` returns the mesh model when [meshes.md](meshes.md)'s `nao_meshes.xml` exists in the user data directory, and the primitive model otherwise. Asking for `"meshes"` when it is missing raises an error that names `nao-viewer fetch-meshes`.
- `PoseWriter.apply` ignores names the model doesn't know (logged once) and leaves joints missing from the pose unchanged. Values outside a joint's range are written as given: the viewer shows what NAOqi reports.

## Open questions

1. **Pinned commit and file**: which `nao_robot` commit, and whether the upstream repository already ships a generated V5 URDF (`naoV50_generated_urdf/nao.urdf`) or the xacro must be expanded once. To settle when vendoring; it doesn't change the design.
2. **Effector offsets**: the exact NAOqi end-effector points (hand and foot effectors are offset from the wrist and ankle frames). These come from the URDF frames where they match, otherwise from the NAOqi documentation. `check-model` validates them.
3. **NAO V6**: v1 is V5 geometry. Whether V6 (NAOqi 2.8) needs its own URDF and camera field of view is open.
