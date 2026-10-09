# Check-model and the command line

**Status:** Done

Implements [specs/check_model.md](../specs/check_model.md) (`check_model.run` and its report) and [specs/cli.md](../specs/cli.md) (`nao-viewer view` and `nao-viewer check-model`). It leaves out `fetch-meshes`, which arrives with the meshes plan.

## Scope

- `src/nao_viewer/check_model.py`: new. `run`, `CheckReport`, `EffectorResult`, `TargetRefused`
- `src/nao_viewer/cli.py`: new. `main(argv) -> int` with `view` and `check-model`
- `src/nao_viewer/source.py`: `_identify` becomes public `identify`, so check-model identifies the target the way the pose source does
- `pyproject.toml`: `[project.scripts] nao-viewer = "nao_viewer.cli:main"`
- `tests/mock_naoqi.py`: `clip_joint(name, lo, hi)`, so `angleInterpolation` can land somewhere other than the request, as NAOqi's own clipping does
- `tests/test_check_model.py`, `tests/test_cli.py`: new
- `tests-e2e/test_check_model_live.py`: new, against `NAOQI_URL`
- `AGENTS.md`: project map rows for `check_model.py` and `cli.py`
- `specs/check_model.md`, `specs/cli.md`, `specs/_index.md`, this plan, `plans/_index.md`: statuses

## Steps

1. **`source.identify`**: rename, keep the behavior.
2. **`check_model.py`**:
   - Validate the arguments, `connect(url)`, `identify`. If the target is `real` and `allow_real` is false, raise `TargetRefused`.
   - Joints: the `getBodyNames("Body")` names in `JOINT_NAMES`, each with the model's `jnt_range` shrunk by 10% at both ends.
   - `numpy.random.default_rng(seed)`; with `seed=None`, draw it from `secrets.randbits(32)` and log it.
   - `setStiffnesses("Body", 1.0)` once. Then, per sample: `angleInterpolation(names, angles, 0.5, True)`, `getAngles("Body", True)`, one `getTransform(effector, 0, True)` per effector.
   - Pose the model (`load_world(variant="placeholder")`, `PoseWriter`) with the read-back angles, torso at the origin. Position error is the distance between the site position and the NAOqi translation, in mm. Rotation error is the angle of `R_naoqiᵀ · R_site`, in degrees.
   - Keep the worst position and worst rotation per effector with their sample numbers, and close the session at the end.
   - `CheckReport.format()`: a header (URL, target, NAOqi version, samples, seed), one row per effector, then `PASS` or `FAIL: <effectors> over 2 mm / 1°`.
3. **`cli.py`**: argparse with global `-v`/`-q` and subcommands `view [--config PATH]` and `check-model URL [--samples N] [--seed N] [--tolerance-mm X] [--tolerance-deg X] [--allow-real]`. Positive-number argument types, so a bad value is argparse's own exit 2.
   - `view`: `NaoViewer.from_json_file` (or `NaoViewer()`), `launch()`, `wait()`. `ConfigError` gives exit 2, `LaunchError` exit 1, Ctrl-C `close()` and exit 130.
   - `check-model`: print `report.format()`, then exit 0 or 1. `TargetRefused` and `ConnectionError` give exit 1.
   - Errors go to stderr as `nao-viewer: error: <message>`.
4. **Entry point** in `pyproject.toml`, then `uv sync`.
5. **Tests, project map, statuses.**

## Verification

- `tests/test_check_model.py`, against the mock NAOqi:
  - the mock's own kinematics give errors of about 0 and `passed`;
  - an injected 5 mm `LArm` offset is reported as about 5 mm on `LArm` only, which fails;
  - an injected 2° rotation on `Head` is reported as about 2°;
  - a clipped joint still passes, because the model is posed with the read-back angles;
  - every sent angle is within the shrunk range;
  - the same seed sends the same configurations, and a report's seed replays a `seed=None` run;
  - stiffness is set once;
  - a `real` target is refused before any motion and accepted with `allow_real`, and `nao-sim` is accepted;
  - bad arguments raise `ValueError`;
  - `format()` names the seed and the failing effectors.
- `tests/test_cli.py`:
  - `check-model` exits 0 and prints the report, and exits 1 on an injected error or a refused real target;
  - `--samples 0` exits 2;
  - `view` with the fake viewer process exits 0 when the window closes;
  - a bad config file exits 2 and names the key;
  - a launch failure exits 1;
  - `-q` and `-v` set the log level.
- `tests-e2e/test_check_model_live.py`: `run(NAOQI_URL)` passes. Run it against nao-sim's NAOqi 2.1 container.
- `uv run ruff check .`, `uv run ruff format --check src tests tests-e2e typings`, `uv run pyright`, `uv run pytest`. Then mark this plan `Done` and check_model.md and cli.md `Implemented`.

## Outcome

`nao-viewer check-model` against a bare NAOqi 2.1.4.13 (`naoqi-bin` in nao-sim's image) with seed 1 and 20 samples passes. Every effector is within 0.03° and RArm is the worst at 0.18 mm. That 0.18 mm is the URDF's `r_gripper` z offset (−0.01213), which differs from `l_gripper`'s (−0.01231). NAOqi treats the two arms as symmetric, so `nao.xml`'s `RArm` now uses −0.01231. `test_model.py` records this as a deliberate correction to the URDF, and model.md documents it. After the fix every effector is within 0.00 mm and 0.03°.
