---
code:
  - src/nao_viewer/meshes.py
  - src/nao_viewer/model.py
  - src/nao_viewer/models/aldebaran_visuals.json
  - src/nao_viewer/cli.py
tests:
  - tests/test_meshes.py
---

# Meshes

**Status:** Draft

## Purpose

Giving each user Aldebaran's NAO meshes in a way the license allows, and loading them in place of the placeholder visuals ([model.md](model.md)). The meshes are CC BY-NC-ND 4.0, not MIT. Aldebaran allows redistribution only through an installer where the user explicitly types or clicks "yes". So nothing from or derived from them may enter the repository, a package or an image. Without them, nao-viewer works fully with its placeholder visuals.

## Decided

### Location

- Everything lives in `platformdirs.user_data_dir("nao-viewer")/meshes/<installer-version>/`:
  - `meshes/` and `texture/` as installed;
  - `converted/`: the meshes after local conversion;
  - `ACCEPTANCE.json`.
- Nothing is ever written to the working tree. `.gitignore` and the asset guard back this up.
- `meshes.installed() -> Path | None` returns the `converted/` directory when `ACCEPTANCE.json` and every mesh listed in the visual table are present, and `None` otherwise. [model.md](model.md)'s `resolve_variant` relies on it.

### `nao-viewer fetch-meshes [--installer PATH]`

1. **Notice**: what is downloaded and from where, that it is Aldebaran's work under CC BY-NC-ND 4.0, that it is **non-commercial**, and that nao-viewer's MIT license does not cover it.
2. **License text**: the full text, fetched from `ros-naoqi/nao_meshes` at a pinned commit and checked against a stored SHA-256. On a mismatch the command stops.
3. **Acceptance**: the user must type `yes` in full. No default, no `y`, no flag, no environment variable. Anything else, including EOF or a non-interactive stdin, aborts before any download.
4. **Download**: the pinned `naomeshes-0.6.7-linux-x64-installer.run` from `ros-naoqi/nao_meshes_installer`. It is checked against MD5 `5f897a3328f217bae6c0ed2a934e524c` and a SHA-256 recorded at implementation, and refused on mismatch. `--installer PATH` uses a local copy with the same checks.
5. **Install**: run the installer with `--mode text` into a temporary directory, so Aldebaran's own terms are shown too. On macOS and Windows it runs inside a throwaway `linux/amd64` Docker container, with the terminal attached so the installer prompt reaches the user.
6. **Copy**: `meshes/` and `texture/` go into the data directory. `ACCEPTANCE.json` records the UTC timestamp, the license SHA-256, the installer SHA-256 and the nao-viewer version.
7. **Convert**: convert each mesh named in the visual table with `trimesh` to a format MuJoCo loads (OBJ, or STL where there's no texture) into `converted/`. MuJoCo can't load the installer's format directly, so this step runs on the user's machine.

### Aldebaran visual table (`models/aldebaran_visuals.json`)

- A committed table, one entry per URDF link that has a visual mesh: body name in `nao.xml`, mesh file name, position, orientation and scale.
- It is taken once from the vendored URDF's `<visual>` elements (`<mesh filename="package://nao_meshes/...">` with its origin and scale), which are BSD-3 like the rest of the URDF. It holds names and placements only, never mesh data.
- Like `nao.xml`, it is maintained by hand. `tests/test_meshes.py` checks it against the URDF and checks that every body it names exists in `nao.xml`.

### Loading (`variant="aldebaran"`)

[model.md](model.md)'s `load_world` calls `meshes.apply_visuals(spec, converted_dir)` on the `nao.xml` spec before compiling:

- removes every geom of class `nao_visual` (the placeholder visuals);
- adds one mesh asset per table entry, with its absolute path in `converted/`, and one visual-only mesh geom (`contype=conaffinity=0`, group 1) on the matching body, at the table's placement.

Kinematics, joints, sensors, cameras and collision geoms are untouched, so both variants behave the same.

### What never happens

There is no command to export converted meshes or a model that includes them, and no caching to a shared location. The compiled model with Aldebaran meshes exists only in memory.

## Open questions

1. **Installer layout and format**: confirm after a first fetch that the meshes are Collada (`.dae`) and where they sit. `trimesh` needs `pycollada` for DAE, an added dependency (or an optional `[meshes]` extra together with `trimesh`).
2. **Textures**: whether the meshes use textures that MuJoCo can map (OBJ with UVs plus PNG), or flat colors are good enough for v1.
3. **Docker attach on Windows**: the interactive prompt through `docker run -it` on Windows terminals is untested.
4. **Legal**: confirm with Aldebaran (or a lawyer) that typed acceptance plus their installer meets the redistribution condition, and that local format conversion is fine under the ND clause.
