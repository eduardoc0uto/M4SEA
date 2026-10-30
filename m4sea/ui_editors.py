"""Streamlit configuration editors; all edits remain in session state."""
import json
import pandas as pd
import streamlit as st
from .config import STATUSES, COLORS
from .numbers import normalize_parameters, parse_number


def parameter_frame(parameters, group, mappings):
    """Always use a float column, including all-null and integer-only JSON."""
    rows = [
        {'parameter': name, **normalize_parameters(parameter),
         'OpenFAST': 'implementado' if f'{group}.{name}' in mappings else 'apenas armazenado'}
        for name, parameter in parameters.items()
    ]
    frame = pd.DataFrame(rows)
    frame['value'] = pd.Series([row['value'] for row in rows], dtype='float64')
    return frame

def parameter_editor(config, group):
    st.subheader(group.title())
    st.caption('Estados: ' + ' · '.join(f'{COLORS[s]} {s}' for s in STATUSES))
    frame = parameter_frame(config[group], group, config['project']['mappings'])
    with st.form(f'edit_{group}'):
        edited = st.data_editor(frame, hide_index=True, disabled=['parameter','OpenFAST','implemented'], column_config={'status':st.column_config.SelectboxColumn(options=STATUSES), 'value':st.column_config.NumberColumn(format='%.12g')}, key=f'table_{group}')
        st.caption('Valores decimais, inteiros e notação científica (E/e). Para introduzir expoentes diretamente, utilize o campo de texto abaixo; a coluna da tabela mantém valores float.')
        parameter = st.selectbox('Parâmetro para introdução científica', list(config[group]), key=f'numeric_parameter_{group}')
        scientific = st.text_input('Valor numérico (opcional)', placeholder='Ex.: 5.86450E8, 1E-3 ou -3.2e6', key=f'numeric_value_{group}')
        if st.form_submit_button('Apply Working Changes'):
            try:
                updated = {}
                for row in edited.to_dict('records'):
                    name = row.pop('parameter')
                    row.pop('OpenFAST', None)
                    row['value'] = parse_number(None if pd.isna(row['value']) else row['value'])
                    updated[name] = row
                if scientific.strip():
                    updated[parameter]['value'] = parse_number(scientific)
                config[group] = updated
                st.success('Configuração de trabalho atualizada; baseline preservado.')
            except ValueError as exc:
                st.error(str(exc))

def mooring_editor(config):
    st.subheader('Mooring')
    st.caption('Linhas armazenadas na configuração. A escrita das tabelas MoorDyn ainda não está implementada. Coordenadas XYZ em metros, Z positivo para cima.')
    st.json(config['mooring'])
    with st.form('mooring'):
        text = st.text_area('Editar linhas JSON (número variável)', json.dumps(config['mooring'], indent=2), height=350)
        st.caption('Cada campo físico é um objeto com value, unit, status, source e description. Exemplo disponível em 02_Configs/Templates/mooring_line.json.')
        if st.form_submit_button('Apply Mooring Changes'):
            try:
                data = normalize_parameters(json.loads(text))
                if not isinstance(data.get('lines'),list) or not all(isinstance(line,dict) for line in data['lines']):
                    raise ValueError('lines deve ser uma lista de objetos.')
                config['mooring'] = data
                st.success('Linhas atualizadas em memória.')
            except (ValueError, TypeError) as exc:
                st.error(str(exc))
