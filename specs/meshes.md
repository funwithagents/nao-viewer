---
code:
  - src/nao_viewer/meshes.py
  - src/nao_viewer/build_model.py
tests:
  - tests/test_meshes.py
---

# Meshes

**Status:** Draft

## Purpose

Giving each user Aldebaran's NAO meshes in a way the license allows, and building the mesh model from them on their machine. The meshes are CC BY-NC-ND 4.0, not MIT. Aldebaran allows redistribution only through an installer where the user explicitly types or clicks "yes". So nothing from or derived from them may enter the repository, a package or an image.

## Decided

### Location

- Everything lives in `platformdirs.user_data_dir("nao-viewer")/meshes/<installer-version>/`:
  - `meshes/` and `texture/` as installed;
  - `converted/`: the meshes after local conversion;
  - `nao_meshes.xml`: the mesh model;
  - `ACCEPTANCE.json`.
- Nothing is ever written to the working tree. `.gitignore` and the asset guard back this up.

### `nao-viewer fetch-meshes [--installer PATH]`

1. **Notice**: what is downloaded and from where, that it is Aldebaran's work under CC BY-NC-ND 4.0, that it is **non-commercial**, and that nao-viewer's MIT license does not cover it.
2. **License text**: the full text, fetched from `ros-naoqi/nao_meshes` at a pinned commit and checked against a stored SHA-256. On a mismatch the command stops.
3. **Acceptance**: the user must type `yes` in full. No default, no `y`, no flag, no environment variable. Anything else, including EOF or a non-interactive stdin, aborts before any download.
4. **Download**: the pinned `naomeshes-0.6.7-linux-x64-installer.run` from `ros-naoqi/nao_meshes_installer`. It is checked against MD5 `5f897a3328f217bae6c0ed2a934e524c` and a SHA-256 recorded at implementation, and refused on mismatch. `--installer PATH` uses a local copy with the same checks.
5. **Install**: run the installer with `--mode text` into a temporary directory, so Aldebaran's own terms are shown too. On macOS and Windows it runs inside a throwaway `linux/amd64` Docker container, with the terminal attached so the installer prompt reaches the user.
6. **Copy**: `meshes/` and `texture/` go into the data directory. `ACCEPTANCE.json` records the UTC timestamp, the license SHA-256, the installer SHA-256 and the nao-viewer version.
7. **Build**: run the mesh build below.

### `nao-viewer build-model --variant meshes`

- Refuses without `ACCEPTANCE.json`.
- Reads the visual mesh of each link from the vendored URDF (`<visual><mesh filename="package://nao_meshes/...">` with its origin and scale). These are the elements the primitive build drops ([model.md](model.md)).
- Converts each one with `trimesh` to a format MuJoCo loads (OBJ, or STL where there's no texture) into `converted/`.
- Builds the model from the same `MjSpec` code path as the primitive model, adding visual-only mesh geoms (`contype=conaffinity=0`, group 1) to the matching bodies. The primitive collision geoms stay, hidden in a non-default group. Writes `nao_meshes.xml` with `meshdir` pointing at `converted/`.
- Kinematics, joints, sensors and cameras are therefore identical in both variants.

### What never happens

There is no command to export converted meshes or the mesh model, and no caching to a shared location.

## Open questions

1. **Installer layout and format**: confirm after a first fetch that the meshes are Collada (`.dae`) and where they sit. `trimesh` needs `pycollada` for DAE, an added dependency (or an optional `[meshes]` extra).
2. **Textures**: whether the meshes use textures that MuJoCo can map (OBJ with UVs plus PNG), or flat colors are good enough for v1.
3. **Docker attach on Windows**: the interactive prompt through `docker run -it` on Windows terminals is untested.
4. **Legal**: confirm with Aldebaran (or a lawyer) that typed acceptance plus their installer meets the redistribution condition, and that local conversion is fine under the ND clause.
