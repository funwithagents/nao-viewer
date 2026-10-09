---
code:
  - src/nao_viewer/config.py
  - examples/configs/mirror.json
  - examples/configs/sim-table.json
  - examples/configs/sim-headless.json
tests:
  - tests/test_config.py
---

# Configuration

**Status:** Implemented

## Purpose

One declarative description of a viewer: which NAOqi to watch, in which mode, in which world, with which options. A `NaoViewer` ([api.md](api.md)) is built from it, the viewer process receives it, and `nao-viewer view --config` reads it from a file ([cli.md](cli.md)). A setup becomes reproducible and shareable as one JSON file, and a program embedding nao-viewer (nao-sim) can carry a viewer config as one block of its own config.

It follows the configuration pattern of nao-bridge (`NaoBridgeConfig`): frozen dataclasses, the same three loaders, defaults declared once, unknown keys rejected, errors naming the key path. nao-viewer can't import nao-bridge (the dependency chain stays one-way), so `config.py` carries its own small copy of the pattern.

## Decided

### `NaoViewerConfig` — structure

```json
{
  "mode": "sim",
  "headless": false,
  "naoqi": { "url": "tcp://127.0.0.1:9559", "rate_hz": 50 },
  "world": { "scene": "table", "variant": "auto" },
  "ghost": false,
  "launch_timeout_s": 30
}
```

```python
@dataclass(frozen=True)
class NaoViewerConfig:
    mode: Mode = "mirror"                        # "mirror" | "sim" (api.md, two modes)
    headless: bool = False                       # no window, offscreen rendering only (api.md, Headless)
    naoqi: NaoqiSettings = field(default_factory=NaoqiSettings)
    world: WorldSettings = field(default_factory=WorldSettings)
    ghost: bool = False                          # draw the commanded pose (viewer.md, Ghost)
    launch_timeout_s: float = 30.0               # how long launch() waits for the window

@dataclass(frozen=True)
class NaoqiSettings:
    url: str = "tcp://127.0.0.1:9559"            # tcp://host:port, host:port, or a bare host (port 9559)
    rate_hz: float = 50.0                        # pose polling rate (source.md)

@dataclass(frozen=True)
class WorldSettings:
    scene: str = "empty"                         # a bundled scene name, or a path to an MJCF file
    variant: Variant = "auto"                    # "auto" | "placeholder" | "aldebaran" (model.md)
```

- `mode` sits at the top level: it decides what the viewer is for (and which requests it accepts), not a detail of one block. `headless` sits next to it for the same reason: it decides whether the viewer has a window at all ([api.md](api.md), Headless).
- Every block and field is optional. Missing ones take the defaults above. **A default is declared once**, on the dataclass field; the loaders read only the keys present and let the dataclass apply the rest, so a default can't drift between code and JSON.
- **The default URL is the local machine** (`tcp://127.0.0.1:9559`: a local nao-sim or `naoqi-bin`). `NaoViewerConfig()` is therefore valid: a viewer built from it opens and waits for a NAOqi to appear, as any viewer does when NAOqi is unreachable ([source.md](source.md)).

### Loaders and validation

- Every config class has the same three constructors: `from_dict(data)`, `from_json(text)` (parses, then `from_dict`), and `from_json_file(path)` (reads, then `from_json`; an error about the file names its path). All share one validation path.
- `to_dict()` returns the full config, every field included, as JSON-compatible data. `from_dict(config.to_dict()) == config`. It is how a `NaoViewer` hands its config to the viewer process ([api.md](api.md)).
- Errors raise `ConfigError(ValueError)`, whose message names the offending key path (e.g. `naoqi.rate_hz must be a positive, finite number, got 0`). It carries `key` (the path, empty when the error isn't about one key) and `detail`.
- **Unknown keys are errors**, so a typo fails when the config loads.
- **Type and range checks:** `mode` ∈ `{"mirror", "sim"}`; `naoqi.url` a non-empty string; `naoqi.rate_hz` and `launch_timeout_s` positive, finite numbers; `world.scene` a non-empty string; `world.variant` ∈ `{"auto", "placeholder", "aldebaran"}`; `ghost` and `headless` booleans. Booleans are not accepted as numbers.
- **Headless combinations:** `headless: true` requires `mode: "sim"`. A headless mirror would have nothing to show, since mirror mode serves no camera frames, so it is a `ConfigError` on `headless`. `headless: true` with `ghost: true` is a `ConfigError` on `ghost`, because the ghost is drawn only in the window, never in camera frames.
- Whether the machine can render offscreen (an OpenGL backend for headless mode) is checked when the viewer starts, not at load, like the meshes below.
- **Scenes:** a `scene` ending in `.xml` is a path, anything else a bundled scene name (as `load_world` reads it, [model.md](model.md)). An unknown bundled name is a `ConfigError` when the config loads, listing the bundled scenes. A path is checked when the viewer starts, not at load (the file may be written later); a relative path read by `from_json_file` is resolved against the config file's directory, so a config and its scene can travel together.
- Whether Aldebaran's meshes are installed (`variant: "aldebaran"`) is checked when the viewer starts, not at load: it's a property of the machine, not of the file.
- `config.py` imports neither `mujoco` nor `qi`, so building a config costs a caller nothing (the same rule as `client.py`).

### Embedding

The whole `NaoViewerConfig` is one JSON object with no top-level key of its own, so another program's config can hold it as a block (for example nao-sim's `"viewer": { … }`) and build it with `NaoViewerConfig.from_dict(block)`. A `ConfigError` raised there names keys relative to the block; the embedding program prefixes its own path, as nao-bridge's server configs do with their `bridge` block.

### Example files

`examples/configs/` holds ready-to-use files kept in sync with this spec:

- `mirror.json`: mirror mode on a robot (its URL to fill in), ghost on;
- `sim-table.json`: sim mode on a local NAOqi, the `table` scene;
- `sim-headless.json`: the same, headless, as a CI job would run it.

## Open questions

1. **Shared config helpers**: nao-bridge and nao-viewer each carry the same small config pattern. If a third package needs it, extracting it into a shared package (that all three may depend on) is cheaper than a third copy. Deferred until then.
