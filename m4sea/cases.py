"""Independent immutable-baseline cases, manifests and execution lifecycle."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import subprocess
import uuid
import logging

logger = logging.getLogger(__name__)
from .config import resolve_path, inside, load_json
from .validation import validate
from .openfast import apply_parameters, read_output, metrics

def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf-8')

def manifest(folder: Path):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}

def generate_case(config: dict, root: Path) -> Path:
    errors = [m.text for m in validate(config, root, execution=True) if m.severity == 'ERROR']
    if errors:
        raise ValueError('\n'.join(errors))
    baseline = resolve_path(root, config['project']['baseline'])
    simulations = (root / '05_Simulations').resolve()
    if simulations.is_relative_to(baseline) or baseline.is_relative_to(simulations):
        raise ValueError('Baseline e simulações devem ser diretórios separados.')
    for p in baseline.rglob('*'):
        if p.is_symlink():
            raise ValueError('Baseline com symlink não suportado; usar snapshot autocontido.')
    ident = f'CASE_{datetime.now(timezone.utc):%Y%m%dT%H%M%S}_{uuid.uuid4().hex[:12]}'
    case = simulations / 'Pending' / ident
    case.parent.mkdir(parents=True, exist_ok=True)
    reserved = ['config_snapshot.json','metadata.json','metrics.json','diagnostics.json','stdout.log']
    if any((baseline/name).exists() for name in reserved):
        raise ValueError('Baseline contém nomes reservados de metadata; selecione apenas os inputs do modelo.')
    shutil.copytree(baseline, case)
    # Outputs copied from a previous run must never count as new simulation results.
    for old_output in case.rglob('*.outb'):
        old_output.unlink()
    logger.info('Caso criado: %s', case.name)
    try:
        apply_parameters(case, config)
        # Reject external and missing file references in standard quoted OpenFAST fields.
        import re
        for p in list(case.rglob('*.fst')) + list(case.rglob('*.dat')):
            for ref in re.findall(r'"([^"\n]+\.(?:dat|fst|dll|bts|wnd|txt))"', p.read_text(errors='replace'), re.I):
                target = (p.parent / ref.replace('\\', '/')).resolve()
                if not target.is_relative_to(case.resolve()) or not target.is_file():
                    raise ValueError(f'Referência não autocontida/inexistente: {ref}')
        write_json(case / 'config_snapshot.json', config)
        write_json(case / 'metadata.json', {'id':ident, 'status':'Pending','created':datetime.now(timezone.utc).isoformat(),'baseline_manifest':manifest(baseline),'input_manifest':manifest(case)})
    except Exception:
        shutil.rmtree(case)
        raise
    return case

def diagnose(text: str):
    rules = [('catenary solve','Possível problema de geometria ou inicialização MoorDyn.'),('nan state detected','Estado numericamente inválido.'),('extreme pitch moment','Possível instabilidade ou configuração incompatível.')]
    return [{'severity':'WARNING','pattern':p,'hypothesis':message} for p,message in rules if p in text.lower()]

def run_case(case: Path, root: Path) -> Path:
    config = load_json(case / 'config_snapshot.json')
    running = root / '05_Simulations/Running' / case.name
    running.parent.mkdir(parents=True, exist_ok=True)
    case.rename(running)
    metadata = load_json(running / 'metadata.json')
    metadata['status'] = 'Running OpenFAST'
    write_json(running / 'metadata.json', metadata)
    success = False
    try:
        if metadata['input_manifest'] != {k:v for k,v in manifest(running).items() if k not in ['metadata.json']}:
            raise ValueError('Os ficheiros do caso foram alterados após geração.')
        executable = resolve_path(root, config['project']['openfast_executable'])
        fst = inside(running, config['project']['main_fst'])
        with (running / 'stdout.log').open('w', encoding='utf-8') as log:
            result = subprocess.run([str(executable), str(fst)], cwd=running, stdout=log, stderr=subprocess.STDOUT, timeout=3600, check=False)
        text = (running / 'stdout.log').read_text(errors='replace')
        diagnostics = diagnose(text)
        write_json(running / 'diagnostics.json', diagnostics)
        metadata['returncode'] = result.returncode
        outputs = list(running.rglob('*.outb'))
        if result.returncode != 0 or not outputs or 'nan state detected' in text.lower() or 'fatal error' in text.lower():
            raise RuntimeError('OpenFAST falhou ou não produziu output binário; consultar stdout.log.')
        metadata['status'] = 'Processing output'
        write_json(running / 'metadata.json', metadata)
        metrics(read_output(outputs[0])).to_json(running / 'metrics.json', orient='index', indent=2)
        success = True
    except Exception as exc:
        logger.exception('Falha no caso %s', running.name)
        metadata['error'] = str(exc)
        with (running / 'stdout.log').open('a', encoding='utf-8') as log:
            log.write(f'\nM4SEA: {exc}\n')
    metadata['status'] = 'Completed' if success else 'Failed'
    metadata['finished'] = datetime.now(timezone.utc).isoformat()
    write_json(running / 'metadata.json', metadata)
    destination = root / '05_Simulations' / metadata['status'] / running.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    running.rename(destination)
    return destination
