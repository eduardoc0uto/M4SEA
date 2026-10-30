"""Configuration, safe path resolution and append-only working snapshots."""
from pathlib import Path
import json
import uuid
from .numbers import normalize_parameters

ROOT = Path(__file__).resolve().parents[1]
STATUSES = ['company_confirmed', 'public_confirmed', 'source', 'derived', 'adapted', 'assumed', 'calibrated', 'unvalidated', 'unknown']
COLORS = dict(zip(STATUSES, ['🟢', '🟢', '🔵', '🟡', '🟡', '🟠', '🟠', '🔴', '🔴']))

def load_json(path: Path) -> dict:
    with path.open(encoding='utf-8') as stream:
        return normalize_parameters(json.load(stream))

def resolve_path(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else root / path).resolve()

def inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f'Path fora do diretório permitido: {relative}')
    return path

def load_configuration(root: Path = ROOT) -> dict:
    project = load_json(root / 'project_config.json')
    folder = inside(root / '02_Configs', project['structure_name'])
    return {'project': project, **{name: load_json(folder / f'{name}.json') for name in ['structure', 'environment', 'mooring']}}

def save_working(config: dict, root: Path = ROOT) -> Path:
    config = normalize_parameters(config)
    folder = root / '02_Configs/Working'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'working_{uuid.uuid4().hex}.json'
    with path.open('x', encoding='utf-8') as stream:
        json.dump(config, stream, indent=2, allow_nan=False)
    return path
