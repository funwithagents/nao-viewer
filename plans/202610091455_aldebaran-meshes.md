# Aldebaran meshes

**Status:** Done

Implements [specs/meshes.md](../specs/meshes.md): the `fetch-meshes` command (license prompt, the pinned nao-meshes archive downloaded and unlocked, `--archive`, `--force`, `--remove`), the committed visual table, `variant="aldebaran"` loading, and both test tiers. It also catches up the specs it updated: `trimesh` dropped ([project.md](../specs/project.md)), the command's flags ([cli.md](../specs/cli.md)), the e2e meshes gate ([testing.md](../specs/testing.md)) and the `meshes` CI job ([ci.md](../specs/ci.md)). The release pins (tag, archive SHA-256, password) wait for nao-meshes' first release, a separate repository with its own spec. Until then the fast tier covers everything with an archive it builds itself, and the e2e test skips.

## Scope

- `pyproject.toml`, `uv.lock`: drop `trimesh` from the runtime dependencies
- `.gitignore`: also block `*.zip`
- `src/nao_viewer/models/aldebaran_visuals.json`: new, the visual table (39 entries)
- `src/nao_viewer/meshes.py`: new: pins, `data_dir()`, `installed()`, `remove()`, `fetch()`, `apply_visuals()`
- `src/nao_viewer/model.py`: `resolve_variant` reads `meshes.installed()`; `load_world` calls `apply_visuals` for `"aldebaran"`
- `src/nao_viewer/cli.py`: the `fetch-meshes` sub-command with `--archive`, `--force`, `--remove`
- `tests/test_meshes.py`: new, the fast tier, with a test-built encrypted archive
- `tests/test_model.py`: `resolve_variant` and `load_world` with an install present
- `tests/test_cli.py`: `fetch-meshes --remove`, and the refusal on a non-terminal stdin
- `tests-e2e/support.py`: `require_meshes()`
- `tests-e2e/test_meshes_live.py`: new, a real install loaded and rendered offscreen
- `scripts/ci_fetch_meshes.py`: new, drives `nao-viewer fetch-meshes` through a pseudo-terminal
- `.github/workflows/ci.yml`: the `meshes` job
- `AGENTS.md`: `meshes.py` in the project map, `scripts/` in the top-level layout
- specs, `specs/_index.md`, this plan, `plans/_index.md`: statuses

## Steps

1. **Visual table**: write `aldebaran_visuals.json` once with a throwaway script (not committed), from the vendored URDF's `<visual>` elements. Each entry is `{"body", "mesh", "pos", "quat", "scale"}`: the mesh is the path after `package://nao_meshes/meshes/`, and the URDF `rpy` is converted to a `w x y z` quaternion (MuJoCo's convention). Keep the URDF's link order.
2. **`meshes.py`**:
   - Pins: `RELEASE`, `ARCHIVE_SHA256`, `LICENSE_SHA256` (`993af1e3…`), `_PASSWORD`, and the two URLs built from `RELEASE`. `MESH_SET` is `V40`, and `RELEASE` is `None` until nao-meshes publishes `r1`, and `fetch` then stops with a clear message.
   - `data_dir()` is `platformdirs.user_data_dir("nao-viewer")/meshes`. `installed(release=RELEASE)` and `load_manifest(dir)` follow the spec.
   - `fetch(*, archive, force, stdin, stdout)` follows the spec's steps 1 to 8. It reads and writes the streams it is given, and downloads through one module-level `_download(url) -> bytes` that tests replace. Errors are `MeshesError`.
   - Extraction reads every member with `zipfile.ZipFile.open(name, pwd=…)`. Members outside `nao-meshes-<release>/`, and any whose resolved path leaves the staging directory, are refused.
   - `remove()` deletes `data_dir()` and returns the path it removed, or `None`.
   - `apply_visuals(spec, directory)` follows the spec. Names are prefixed `aldebaran_`.
3. **Model**:
   - `resolve_variant` asks `meshes.installed()`.
   - `load_world` applies the visuals to the robot spec before `attach_body`.
   - `viewer_process.py` already passes the attribution for `"aldebaran"`.
4. **CLI**: `fetch-meshes [--archive PATH] [--force] [--remove]`, where `--remove` excludes the other two. `MeshesError` goes through `_error` and exits 1, and Ctrl-C exits 130.
5. **Fast tests**: a fixture builds a nao-meshes-shaped archive in `tmp_path`:
   - one hand-written textured OBJ (with `vt`), one flat OBJ and a 2×2 PNG, reused under every table mesh's name;
   - the manifest;
   - `zip -r -e -P`, skipping the archive-based tests when `zip` is missing.
   It monkeypatches the pins, `_download` and `data_dir`, and the cases follow the spec's Testing list.
6. **E2e**:
   - `support.require_meshes()`;
   - `test_meshes_live.py` follows the spec, and skips without offscreen GL.
7. **CI**:
   - `scripts/ci_fetch_meshes.py` uses `pty.fork()`, `exec`s `nao-viewer fetch-meshes`, waits for the prompt, writes `yes\n`, echoes the session, and returns the child's exit code (with a timeout).
   - The `meshes` job runs on `ubuntu-24.04` with a 15-minute timeout and Mesa's EGL. Its steps are `uv sync --locked`, the script, then the e2e test with `MUJOCO_GL=egl` and `NAO_VIEWER_REQUIRE_MESHES=1`.
   - Until the first release is pinned, the job would fail by design (`RELEASE` is `None`), so it is added with the pins.
8. **Project map** and statuses: once the pins are in and the `meshes` job passes, mark this plan `Done`, meshes.md `Implemented`, and project, cli, testing and ci back to `Implemented`.

## Progress

- Done: every step. nao-meshes published `r1` (`nao-meshes-V40-r1.zip`, SHA-256 `583a2bdc…`), pinned in `meshes.py`. The fast tier keeps the developer's own meshes out (an autouse fixture). Lint, types and the fast tier pass (184 tests). A real `nao-viewer fetch-meshes` on macOS installed `r1`, the e2e meshes test passed against it, and `nao-viewer view` showed the meshes with the attribution.
- The `meshes` CI job first runs on the push of this change.

## Verification

- `uv run ruff check .`, `uv run ruff format .`, `uv run pyright`, `uv run pytest`: all pass, with no network and no Aldebaran file.
- After nao-meshes `r1`: `nao-viewer fetch-meshes` on macOS and Linux, `NAO_VIEWER_REQUIRE_MESHES=1 uv run pytest tests-e2e/test_meshes_live.py`, a look at `nao-viewer view` with `variant: "aldebaran"`, and the `meshes` CI job passing.
