import copy
import json

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from m4sea.config import ROOT, load_configuration, load_json, save_working
from m4sea.numbers import normalize_parameters, parse_number
from m4sea.ui_editors import parameter_frame
from m4sea.validation import validate


@pytest.mark.parametrize(('text', 'expected'), [
    ('5.86450E8', 586450000.0),
    ('5.86450e8', 586450000.0),
    ('2.13E9', 2130000000.0),
    ('1E-3', 0.001),
    ('-3.2e6', -3200000.0),
    ('-2.13E9', -2130000000.0),
    ('23.19', 23.19),
    ('42', 42.0),
    (' 1e+3 ', 1000.0),
    (42, 42.0),
    (23.19, 23.19),
])
def test_parse_number(text, expected):
    actual = parse_number(text)
    assert actual == expected
    assert isinstance(actual, float)


@pytest.mark.parametrize('value', [None, '', '   '])
def test_unknown_stays_unknown(value):
    assert parse_number(value) is None


@pytest.mark.parametrize('value', ['1E', 'abc', '1.2.3', 'NaN', 'inf', '1E9999', True, {}, []])
def test_invalid_numbers_rejected(value):
    with pytest.raises(ValueError):
        parse_number(value)


def test_json_numbers_and_numeric_strings(tmp_path):
    path = tmp_path / 'parameters.json'
    path.write_text('{"mass":{"value":5.86450E8,"source":"1E-3"},'
                    '"length":{"value":"1E-3"},"count":3,"id":"123",'
                    '"anchor":{"value":["1e2",0,"-2.13E9"]}}')
    data = load_json(path)
    assert data['mass']['value'] == 586450000.0
    assert isinstance(data['mass']['value'], float)
    assert data['length']['value'] == 0.001
    assert data['anchor']['value'] == [100.0, 0.0, -2130000000.0]
    assert data['mass']['source'] == '1E-3'
    assert data['count'] == 3 and isinstance(data['count'], int)
    assert data['id'] == '123'
    saved = save_working(data, tmp_path)
    raw = json.loads(saved.read_text())
    assert isinstance(raw['mass']['value'], float)
    assert isinstance(raw['length']['value'], float)


def test_normalization_does_not_mutate_input():
    original = {'value': '2.13E9', 'status': 'assumed'}
    assert normalize_parameters(original)['value'] == 2130000000.0
    assert original['value'] == '2.13E9'


def test_validation_parses_before_physical_rules():
    config = load_configuration()
    config['structure']['platform_mass']['value'] = '5.86450E8'
    config['environment']['water_depth']['value'] = '1E2'
    def p(value):
        return {'value': value, 'status': 'assumed'}
    config['mooring']['lines'] = [dict(
        id='L1', anchor=p(['0','0','-1e2']), fairlead=p(['0','0','0']),
        unstretched_length=p('1.1E2'), EA=p('2.13E9'),
        diameter=p('1E-1'), mass_density=p('1e2'), Cd=p('1'),
        Ca=p('1'), pretension=p('1E3'),
    )]
    original = copy.deepcopy(config)
    assert not [m for m in validate(config, ROOT) if m.severity == 'ERROR']
    assert config == original
    config['structure']['platform_mass']['value'] = '-3.2e6'
    assert any('fisicamente inválido' in m.text for m in validate(config, ROOT))


@pytest.mark.parametrize('values', [[None, None], [1, 2], ['1E-3', '5.86450E8']])
def test_editor_value_column_is_float(values):
    parameters = {str(i): {'value': v, 'unit': 'm'} for i, v in enumerate(values)}
    frame = parameter_frame(parameters, 'structure', {})
    assert pd.api.types.is_float_dtype(frame['value'])


def test_scientific_input_in_structure_form():
    app = AppTest.from_file(str(ROOT/'08_DigitalTwin/WebApp/app.py')).run()
    app.sidebar.radio[0].set_value('Structure').run()
    app.text_input(key='numeric_value_structure').set_value('5.86450E8')
    next(b for b in app.button if b.label == 'Apply Working Changes').click().run()
    assert not app.exception and not app.error
    value = app.session_state['config']['structure']['platform_mass']['value']
    assert value == 586450000.0 and isinstance(value, float)


def test_invalid_scientific_input_does_not_apply_changes():
    app = AppTest.from_file(str(ROOT/'08_DigitalTwin/WebApp/app.py')).run()
    app.sidebar.radio[0].set_value('Environment').run()
    app.text_input(key='numeric_value_environment').set_value('1E')
    next(b for b in app.button if b.label == 'Apply Working Changes').click().run()
    assert not app.exception
    assert app.error
    assert app.session_state['config']['environment']['water_depth']['value'] is None


def test_calibration_scientific_fields(monkeypatch, tmp_path):
    import m4sea.ui
    monkeypatch.setattr(m4sea.ui, 'save_working', lambda data: save_working(data, tmp_path))
    app = AppTest.from_file(str(ROOT/'08_DigitalTwin/WebApp/app.py')).run()
    app.sidebar.radio[0].set_value('Calibration').run()
    values = {'Target value':'2.13E9','Current metric':'5.86450e8',
              'Limite mínimo':'-3.2e6','Limite máximo':'2.13E9'}
    for widget in app.text_input:
        if widget.label in values:
            widget.set_value(values[widget.label])
    next(b for b in app.button if b.label == 'Save Calibration Trial').click().run()
    assert not app.exception and not app.error
    data = load_json(next((tmp_path/'02_Configs/Working').glob('*.json')))['calibration']
    assert data['target'] == 2130000000.0
    assert data['current'] == 586450000.0
    assert data['minimum'] == -3200000.0
    assert isinstance(data['target'], float)


def test_mooring_json_form_normalizes_coordinates_and_ea():
    app = AppTest.from_file(str(ROOT/'08_DigitalTwin/WebApp/app.py')).run()
    app.sidebar.radio[0].set_value('Mooring').run()
    data = {'lines': [{'id': '1E3', 'EA': {'value': '2.13E9', 'status': 'assumed'},
                       'anchor': {'value': ['1E-3', 0, '-3.2e6'], 'status': 'assumed'}}]}
    app.text_area[0].set_value(json.dumps(data))
    next(b for b in app.button if b.label == 'Apply Mooring Changes').click().run()
    assert not app.exception and not app.error
    line = app.session_state['config']['mooring']['lines'][0]
    assert line['EA']['value'] == 2130000000.0
    assert line['anchor']['value'] == [0.001, 0.0, -3200000.0]
    assert line['id'] == '1E3'
