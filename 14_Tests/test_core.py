import copy
import json
from pathlib import Path
import pytest
import os
from m4sea.config import ROOT, load_configuration, load_json, save_working, resolve_path, inside
from m4sea.validation import distance, validate
from m4sea.cases import generate_case, manifest, run_case, diagnose
from m4sea.openfast import apply_parameters, read_output

@pytest.fixture
def project(tmp_path):
    config = copy.deepcopy(load_configuration())
    config['structure']['platform_mass']['value'] = 1
    config['environment']['water_depth']['value'] = 100
    baseline = tmp_path/'baseline'
    baseline.mkdir()
    (baseline/'Main.fst').write_text('Example test input\n')
    exe = tmp_path/'fake_openfast'
    exe.write_text('#!/bin/sh\necho "NaN state detected"\nexit 1\n')
    exe.chmod(0o755)
    config['project'].update(baseline='baseline',main_fst='Main.fst',openfast_executable=str(exe))
    return tmp_path,config

def test_load_unknowns():
    config = load_configuration()
    assert config['structure']['platform_mass']['value'] is None
    assert config['structure']['platform_mass']['status'] == 'unknown'

def test_working_does_not_change_baseline(tmp_path):
    config = load_configuration()
    before = manifest(ROOT/'02_Configs/WindFloat_Research')
    path = save_working(config,tmp_path)
    assert load_json(path) == config
    assert manifest(ROOT/'02_Configs/WindFloat_Research') == before

def test_distance():
    assert distance([0,0,0],[3,4,0]) == 5
    with pytest.raises(ValueError): distance([0],[1])

def test_paths(tmp_path):
    assert resolve_path(tmp_path,'model/Main.fst') == tmp_path/'model/Main.fst'
    with pytest.raises(ValueError): inside(tmp_path,'../escape')

def test_negative_and_nan(project):
    root,c = project
    c['structure']['platform_mass']['value'] = -1
    c['environment']['water_depth']['value'] = float('nan')
    assert sum(m.severity=='ERROR' for m in validate(c,root)) == 2

def test_mooring_impossible(project):
    root,c = project
    def p(v): return {'value':v,'status':'assumed'}
    c['mooring']['lines'] = [dict(id='L1',anchor=p([0,0,-90]),fairlead=p([0,0,0]),unstretched_length=p(1),EA=p(-1))]
    messages = validate(c,root)
    assert any('distância' in m.text for m in messages)
    assert any('seabed' in m.text for m in messages)
    assert any('EA' in m.text for m in messages)

def test_case_is_independent(project):
    root,c = project
    before = manifest(root/'baseline')
    case = generate_case(c,root)
    another = generate_case(c,root)
    assert case != another
    assert load_json(case/'config_snapshot.json') == c
    (case/'Main.fst').write_text('changed')
    assert manifest(root/'baseline') == before
    assert (another/'Main.fst').read_text() == 'Example test input\n'

def test_external_reference_rejected(project):
    root,c = project
    (root/'baseline/Main.fst').write_text('"../outside.dat" File\n')
    with pytest.raises(ValueError, match='Referência'):
        generate_case(c,root)

def test_missing_executable_blocks(project):
    root,c = project
    c['project']['openfast_executable'] = 'missing'
    with pytest.raises(ValueError, match='Executável'):
        generate_case(c,root)

@pytest.mark.skipif(os.name == "nt", reason="Runner sintético POSIX; não é o executável OpenFAST Windows")
def test_failed_execution_and_logs(project):
    root,c = project
    case = generate_case(c,root)
    result = run_case(case,root)
    assert result.parent.name == 'Failed'
    assert load_json(result/'metadata.json')['returncode'] == 1
    assert 'NaN state detected' in (result/'stdout.log').read_text()
    assert load_json(result/'diagnostics.json')

def test_tamper_rejected(project):
    root,c = project
    case = generate_case(c,root)
    (case/'Main.fst').write_text('tampered')
    result = run_case(case,root)
    assert 'alterados' in load_json(result/'metadata.json')['error']

def test_toolbox_mapping_preserves_source(project):
    root,c = project
    (root/'baseline/ElastoDyn.dat').write_text('1.0 PtfmMass - mass\n2.0 OtherParam - dummy\n3.0 AnotherParam - dummy\n')
    c['project']['mappings'] = {'structure.platform_mass':{'file':'ElastoDyn.dat','field':'PtfmMass'}}
    c['structure']['platform_mass']['value'] = 42
    case = generate_case(c,root)
    from openfast_toolbox.io import FASTInputFile
    assert FASTInputFile(str(case/'ElastoDyn.dat'))['PtfmMass'] == 42
    assert FASTInputFile(str(root/'baseline/ElastoDyn.dat'))['PtfmMass'] == 1

def test_streamlit_pages():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(str(ROOT/'08_DigitalTwin/WebApp/app.py')).run()
    assert not app.exception
    for page in ['Structure','Environment','Mooring','Run OpenFAST','Results','Calibration']:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, page
        assert not app.error, page

def test_binary_output_and_metrics(tmp_path):
    import numpy as np
    from openfast_toolbox.io.fast_output_file import writeBinary
    from m4sea.openfast import metrics
    path = tmp_path/'synthetic.outb'
    writeBinary(str(path), np.array([[0.,1.,2.],[1.,3.,4.],[2.,5.,6.]]), ['Time','PtfmHeave','PtfmPitch'], ['s','m','deg'])
    frame = read_output(path)
    channel = next(c for c in frame if 'PtfmHeave' in c)
    assert metrics(frame).loc[channel,'mean'] == pytest.approx(3,abs=0.001)

@pytest.mark.skipif(os.name == "nt", reason="Runner sintético POSIX; não é o executável OpenFAST Windows")
def test_success_lifecycle(project):
    import numpy as np
    from openfast_toolbox.io.fast_output_file import writeBinary
    root,c = project
    fixture = root/'synthetic.outb'
    writeBinary(str(fixture),np.array([[0.,1.],[1.,3.],[2.,5.]]),['Time','PtfmHeave'],['s','m'])
    exe = Path(c['project']['openfast_executable'])
    import sys
    exe.write_text(f'#!{sys.executable}\nimport shutil\nshutil.copyfile({str(fixture)!r}, "result.outb")\nprint("Synthetic runner: not a scientific simulation")\n')
    case = generate_case(c,root)
    result = run_case(case,root)
    assert result.parent.name == 'Completed'
    assert (result/'metrics.json').is_file()
    assert load_json(result/'metadata.json')['status'] == 'Completed'


def test_required_missing(project):
    root,c = project
    del c['structure']['platform_mass']
    assert any(m.severity == 'ERROR' and 'obrigatório inexistente' in m.text for m in validate(c,root))
