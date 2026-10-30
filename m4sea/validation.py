"""Deterministic checks; no inferred scientific values."""
from dataclasses import dataclass, asdict
from pathlib import Path
import math
from .config import resolve_path, inside, STATUSES
from .numbers import parse_number

@dataclass
class Message:
    severity: str
    text: str

    def to_dict(self):
        return asdict(self)

def distance(a, b) -> float:
    if len(a) != 3 or len(b) != 3:
        raise ValueError('Coordenadas devem conter XYZ.')
    return math.dist(a, b)

def validate(config: dict, root: Path, execution: bool = False) -> list[Message]:
    messages = []
    def add(level, text):
        messages.append(Message(level, text))
    for group, name in [('structure','platform_mass'),('environment','water_depth')]:
        if name not in config.get(group, {}):
            add('ERROR', f'{name}: parâmetro obrigatório inexistente.')
    for group in ['structure', 'environment']:
        for name, p in config[group].items():
            try:
                v = parse_number(p.get('value'))
            except ValueError as exc:
                add('ERROR', f'{name}: {exc}')
                continue
            if p.get('status') not in STATUSES:
                add('ERROR', f'{name}: estado inválido.')
            if v is None:
                add('ERROR' if name in ['platform_mass', 'water_depth'] else 'WARNING', f'{name}: valor desconhecido.')
                continue
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
                add('ERROR', f'{name}: valor numérico finito obrigatório.')
                continue
            positive = name in ['platform_mass','water_depth','inertia_x','inertia_y','inertia_z','length','width','height','wave_tp']
            if (positive and v <= 0) or (name in ['wind_speed','wave_hs','current_speed','turbulence'] and v < 0):
                add('ERROR', f'{name}: valor fisicamente inválido.')
            if not p.get('source') or p.get('status') in ['unknown','unvalidated','assumed']:
                add('WARNING', f'{name}: origem/validação pendente.')
    try:
        depth = parse_number(config['environment'].get('water_depth', {}).get('value'))
    except ValueError:
        depth = None  # The field error was already reported above.
    ids = set()
    for line in config['mooring']['lines']:
        ident = line.get('id')
        if not ident or ident in ids:
            add('ERROR', 'ID de amarração vazio ou duplicado.')
        ids.add(ident)
        try:
            def val(key):
                p = line[key]
                if p.get('status') not in STATUSES:
                    raise ValueError(f'{key}: estado inválido')
                value = p['value']
                return [parse_number(v) for v in value] if isinstance(value, list) else parse_number(value)
            anchor, fairlead = val('anchor'), val('fairlead')
            length, ea = val('unstretched_length'), val('EA')
            nums = [*anchor, *fairlead, length, ea]
            if not all(isinstance(n, (int,float)) and not isinstance(n,bool) and math.isfinite(n) for n in nums):
                raise ValueError('valores desconhecidos ou não finitos')
            if ea <= 0 or length <= 0:
                add('ERROR', f'Linha {ident}: EA e comprimento devem ser positivos.')
            if length < distance(anchor, fairlead):
                add('ERROR', f'Linha {ident}: comprimento inferior à distância anchor–fairlead.')
            if isinstance(depth,(int,float)) and not math.isclose(anchor[2], -depth, abs_tol=0.1):
                add('ERROR', f'Linha {ident}: anchor incompatível com seabed Z = -water_depth.')
            for key in ['diameter','mass_density','Cd','Ca','pretension']:
                p = line.get(key,{})
                value = parse_number(p.get('value'))
                if value is None:
                    add('WARNING', f'Linha {ident}: {key} desconhecido.')
                elif not isinstance(value,(int,float)) or not math.isfinite(value) or value < 0 or (key in ['diameter','mass_density'] and value == 0):
                    add('ERROR', f'Linha {ident}: {key} inválido.')
        except (KeyError, TypeError, ValueError) as exc:
            add('ERROR', f'Linha {ident}: configuração incompleta ({exc}).')
    if not config['mooring']['lines']:
        add('WARNING', 'Nenhuma linha definida; o baseline pode conter amarrações não editadas.')
    mappings = config['project'].get('mappings', {})
    add('INFO', 'Apenas parâmetros com mapping explícito são escritos no OpenFAST; os restantes são armazenados.')
    if execution:
        try:
            baseline = resolve_path(root, config['project']['baseline'])
            fst = inside(baseline, config['project']['main_fst'])
            if not fst.is_file():
                add('ERROR', f'Ficheiro principal inexistente: {fst}')
            executable = resolve_path(root, config['project']['openfast_executable'])
            if not executable.is_file():
                add('ERROR', 'Executável OpenFAST inexistente neste sistema.')
            for key, mapping in mappings.items():
                if not inside(baseline, mapping['file']).is_file():
                    add('ERROR', f'{key}: ficheiro mapeado inexistente.')
        except (KeyError, ValueError) as exc:
            add('ERROR', f'Paths/mappings inválidos: {exc}')
    return messages
