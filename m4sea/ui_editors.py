"""Streamlit configuration editors; all edits remain in session state."""
import json
import pandas as pd
import streamlit as st
from .config import STATUSES, COLORS

def parameter_editor(config, group):
    st.subheader(group.title())
    st.caption('Estados: ' + ' · '.join(f'{COLORS[s]} {s}' for s in STATUSES))
    rows = []
    for name, parameter in config[group].items():
        rows.append({'parameter':name, **parameter, 'OpenFAST':'implementado' if f'{group}.{name}' in config['project']['mappings'] else 'apenas armazenado'})
    with st.form(f'edit_{group}'):
        edited = st.data_editor(pd.DataFrame(rows), hide_index=True, disabled=['parameter','OpenFAST','implemented'], column_config={'status':st.column_config.SelectboxColumn(options=STATUSES), 'value':st.column_config.NumberColumn()}, key=f'table_{group}')
        if st.form_submit_button('Apply Working Changes'):
            for row in edited.to_dict('records'):
                name = row.pop('parameter')
                row.pop('OpenFAST', None)
                row['value'] = None if pd.isna(row['value']) else row['value']
                config[group][name] = row
            st.success('Configuração de trabalho atualizada; baseline preservado.')

def mooring_editor(config):
    st.subheader('Mooring')
    st.caption('Linhas armazenadas na configuração. A escrita das tabelas MoorDyn ainda não está implementada. Coordenadas XYZ em metros, Z positivo para cima.')
    st.json(config['mooring'])
    with st.form('mooring'):
        text = st.text_area('Editar linhas JSON (número variável)', json.dumps(config['mooring'], indent=2), height=350)
        st.caption('Cada campo físico é um objeto com value, unit, status, source e description. Exemplo disponível em 02_Configs/Templates/mooring_line.json.')
        if st.form_submit_button('Apply Mooring Changes'):
            try:
                data = json.loads(text)
                if not isinstance(data.get('lines'),list) or not all(isinstance(line,dict) for line in data['lines']):
                    raise ValueError('lines deve ser uma lista de objetos.')
                config['mooring'] = data
                st.success('Linhas atualizadas em memória.')
            except (ValueError, TypeError) as exc:
                st.error(str(exc))
