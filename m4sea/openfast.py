"""Toolbox integration. Explicit scalar mappings only; never guess model fields."""
from pathlib import Path
from openfast_toolbox.io import FASTInputFile, FASTOutputFile
from .config import inside

def apply_parameters(case: Path, config: dict) -> None:
    files = {}
    for dotted, mapping in config['project'].get('mappings', {}).items():
        group, name = dotted.split('.', 1)
        value = config[group][name]['value']
        if value is None:
            raise ValueError(f'{dotted}: valor desconhecido.')
        path = inside(case, mapping['file'])
        if path not in files:
            files[path] = FASTInputFile(str(path))
        data = files[path]
        if mapping['field'] not in data.keys():
            raise ValueError(f'Campo inexistente: {mapping["field"]}')
        data[mapping['field']] = value
    for path, data in files.items():
        data.write(str(path))

def read_output(path: Path):
    frame = FASTOutputFile(str(path)).toDataFrame()
    if frame.empty:
        raise ValueError('Output sem amostras.')
    return frame

def metrics(frame):
    numeric = frame.select_dtypes(include='number')
    return numeric.agg(['min', 'max', 'mean', 'std']).T
