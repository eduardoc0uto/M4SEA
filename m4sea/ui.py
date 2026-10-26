from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import copy
import json
import streamlit as st
from .config import ROOT, load_configuration, load_json, save_working
from .validation import validate
from .cases import generate_case, run_case
from .ui_editors import parameter_editor, mooring_editor
from .ui_results import results

@st.cache_resource
def executor():
    return ThreadPoolExecutor(max_workers=1)

def show_validation(config, execution=False):
    messages = validate(config, ROOT, execution)
    for m in messages:
        {'ERROR':st.error,'WARNING':st.warning,'INFO':st.info}[m.severity](m.text)
    return messages

def dashboard(config):
    st.subheader('Dashboard')
    states = Counter(p.get('status') for g in ['structure','environment'] for p in config[g].values())
    a,b,c = st.columns(3)
    a.metric('Confirmados', states['company_confirmed'] + states['public_confirmed'])
    b.metric('Assumidos', states['assumed'])
    c.metric('Desconhecidos', states['unknown'])
    st.write('Estrutura:', config['project']['structure_name'])
    st.write('Baseline:', config['project']['baseline'])
    messages = validate(config, ROOT, True)
    errors = sum(m.severity == 'ERROR' for m in messages)
    st.metric('Erros que impedem execução', errors)
    for m in [m for m in messages if m.severity == 'WARNING'][:5]:
        st.warning(m.text)
    metadata = sorted((ROOT/'05_Simulations').rglob('metadata.json'),key=lambda p:p.stat().st_mtime)
    if metadata:
        last = load_json(metadata[-1])
        st.write('Última simulação:', last['id'], '—', last['status'])
    else:
        st.info('Ainda não existem simulações.')
    if st.button('Validate Configuration'):
        show_validation(config, True)
    def go_run():
        st.session_state.page = 'Run OpenFAST'
    st.button('Run OpenFAST →', on_click=go_run)

def run_page(config):
    st.subheader('Run OpenFAST')
    st.caption('Preparing → Validating → Running OpenFAST → Processing output → Completed / Failed')
    with st.form('paths'):
        baseline = st.text_input('Diretório baseline (somente leitura)',config['project']['baseline'])
        fst = st.text_input('Ficheiro .fst relativo ao baseline',config['project']['main_fst'])
        exe = st.text_input('Executável OpenFAST neste sistema',config['project']['openfast_executable'])
        mappings = st.text_area('Mappings explícitos JSON',json.dumps(config['project']['mappings'],indent=2))
        st.caption('Exemplo de formato: {"structure.platform_mass": {"file": "ElastoDyn.dat", "field": "PtfmMass"}}. Confirme o campo e as unidades no seu modelo.')
        if st.form_submit_button('Apply Paths and Mappings'):
            try:
                data = json.loads(mappings)
                if not isinstance(data,dict):
                    raise ValueError('Mappings devem ser objeto JSON.')
                config['project'].update(baseline=baseline,main_fst=fst,openfast_executable=exe,mappings=data)
                st.success('Paths aplicados à configuração de trabalho.')
            except ValueError as exc:
                st.error(str(exc))
    if st.button('Validate Configuration', key='run_validate'):
        show_validation(config, True)
    acknowledged = st.checkbox('Li os warnings e reconheço que parâmetros sem mapping não alteram o baseline copiado.')
    if st.button('Generate Case', disabled=not acknowledged):
        try:
            with st.status('Preparing / Validating', expanded=True):
                st.session_state.case = generate_case(copy.deepcopy(config), ROOT)
            st.success(f'Caso criado: {st.session_state.case.name}')
        except Exception as exc:
            st.error(str(exc))
    case = st.session_state.get('case')
    if case:
        st.write('Caso atual:', str(case))
    future = st.session_state.get('future')
    busy = future is not None and not future.done()
    if st.button('Run OpenFAST',disabled=not case or busy or not acknowledged):
        if case.exists() and case.parent.name == 'Pending':
            st.session_state.future = executor().submit(run_case,case,ROOT)
            st.rerun()
        else:
            st.error('Gere um novo caso Pending para executar.')
    @st.fragment(run_every='1s' if busy else None)
    def progress():
        job = st.session_state.get('future')
        if not job:
            return
        if not job.done():
            st.info('Running OpenFAST — execução em segundo plano.')
            running = ROOT / '05_Simulations/Running' / st.session_state.case.name
            log = running / 'stdout.log'
            if log.exists():
                st.code(log.read_text(errors='replace')[-12000:])
        else:
            try:
                destination = job.result()
                st.session_state.case = destination
                meta = load_json(destination/'metadata.json')
                st.success(meta['status']) if meta['status']=='Completed' else st.error(meta.get('error','Failed'))
                log = destination/'stdout.log'
                if log.exists():
                    st.code(log.read_text(errors='replace')[-20000:])
                diagnostics = destination/'diagnostics.json'
                if diagnostics.exists():
                    st.json(load_json(diagnostics))
            except Exception as exc:
                st.error(str(exc))
    progress()

def calibration():
    st.subheader('Calibration — registo manual')
    st.info('Infraestrutura de registo. Não executa otimização nem recomenda alterações físicas.')
    with st.form('calibration'):
        target_parameter = st.text_input('Target parameter')
        metric = st.text_input('Target metric / unidade')
        target = st.number_input('Target value',value=None)
        current = st.number_input('Current metric',value=None)
        adjustable = st.text_input('Parâmetro ajustável')
        lower = st.number_input('Limite mínimo',value=None)
        upper = st.number_input('Limite máximo',value=None)
        if st.form_submit_button('Save Calibration Trial'):
            if lower is not None and upper is not None and lower > upper:
                st.error('Limites inválidos.')
            else:
                entry = dict(target_parameter=target_parameter,metric=metric,target=target,current=current,difference=None if target is None or current is None else current-target,adjustable=adjustable,minimum=lower,maximum=upper,case=str(st.session_state.get('case','')))
                path = save_working({'calibration':entry})
                st.success(f'Ensaio guardado: {path.name}')
    trials = []
    for p in (ROOT/'02_Configs/Working').glob('*.json'):
        data = load_json(p)
        if 'calibration' in data:
            trials.append(data['calibration'])
    st.dataframe(trials)

def main():
    st.set_page_config(page_title='M4SEA · Floating Structures',layout='wide')
    st.title('M4SEA · Floating Structures')
    if 'config' not in st.session_state:
        st.session_state.config = load_configuration()
    config = st.session_state.config
    with st.sidebar:
        st.header('Digital Twin · OpenFAST')
        available = sorted(p.name for p in (ROOT/'02_Configs').iterdir() if p.is_dir() and (p/'structure.json').exists())
        structure = st.selectbox('Estrutura',available)
        if structure != config['project']['structure_name']:
            for group in ['structure','environment','mooring']:
                config[group] = load_json(ROOT/'02_Configs'/structure/f'{group}.json')
            config['project'].update(structure_name=structure,baseline=f'01_Models/{structure}')
            st.rerun()
        working = [p for p in sorted((ROOT/'02_Configs/Working').glob('*.json')) if 'project' in load_json(p)]
        choice = st.selectbox('Configuração', ['Em memória']+working,format_func=lambda p:p.name if hasattr(p,'name') else p)
        if st.button('Load Working Configuration') and choice != 'Em memória':
            st.session_state.config = load_json(choice)
            st.rerun()
        st.caption(f'Caso: {st.session_state.get("case", "nenhum")}')
        page = st.radio('Página',['Dashboard','Structure','Environment','Mooring','Run OpenFAST','Results','Calibration'],key='page')
        if st.button('Save Working Configuration'):
            st.success(str(save_working(config).relative_to(ROOT)))
    try:
        if page == 'Dashboard': dashboard(config)
        elif page in ['Structure','Environment']: parameter_editor(config,page.lower())
        elif page == 'Mooring': mooring_editor(config)
        elif page == 'Run OpenFAST': run_page(config)
        elif page == 'Results': results(ROOT)
        else: calibration()
    except Exception as exc:
        st.error(f'Não foi possível concluir a operação: {exc}')
