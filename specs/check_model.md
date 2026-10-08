---
code:
  - src/nao_viewer/check_model.py
tests:
  - tests/test_check_model.py
  - tests-e2e/test_check_model_live.py
---

# Model check

**Status:** Draft

## Purpose

Proving the model's kinematics match NAOqi's. `nao-viewer check-model` puts a NAOqi robot in random configurations and compares where NAOqi says the head, hands and feet are with where MuJoCo's forward kinematics puts them. It is the acceptance test for [model.md](model.md), and it catches a wrong axis, offset or effector site that a picture would hide.

## Decided

- **Entry points**: `check_model.run(url, samples=20, seed=None, tolerance_mm=2, tolerance_deg=1, allow_real=False) -> CheckReport` from Python, and `nao-viewer check-model URL [...]` from the [CLI](cli.md).
- **Targets**: a virtual robot or nao-sim. A target identified as `real` ([source.md](source.md)) is refused unless `allow_real` (`--allow-real`) is set, since the check moves every joint.
- **Per sample**:
  1. Draw a configuration uniformly within each joint's range, shrunk by 10% at both ends. The draw is seeded, and the seed is printed so a failure can be replayed.
  2. Make the body stiff with `setStiffnesses("Body", 1.0)` (once, at start), then send the configuration with `ALMotion.angleInterpolation(names, angles, 0.5, True)`, which blocks until reached.
  3. Read back `getAngles("Body", True)`, and `getTransform(effector, 0, True)` (frame 0 = torso) for `Head`, `LArm`, `RArm`, `LLeg`, `RLeg`.
  4. Pose the model with the **angles read back**, not the requested ones. NAOqi may clip or couple joints (arm self-collision avoidance, the shared hip motor), and the check is about kinematics, not control.
  5. Compare each effector with the matching model site, expressed in the `torso` frame: position error (mm) and rotation error (angle of the relative rotation, degrees).
- **Result**: a table of the worst position and rotation error per effector, with the sample where it occurred. Exit code 0 when every sample is under both tolerances, 1 otherwise.
- **Afterwards**: stiffness and posture are left as they are; the target is a simulated robot.

## Open questions

None currently.
