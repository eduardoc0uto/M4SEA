from pathlib import Path
import streamlit as st
from .openfast import read_output, metrics

def results(root: Path):
    st.subheader('Results / comparação de casos')
    files = sorted((root / '05_Simulations').rglob('*.outb'))
    if not files:
        st.info('Sem outputs .outb. Execute um caso real ou copie um caso completo para 05_Simulations/Archive.')
        return
    selected = st.multiselect('Outputs (até dois para comparação)', files, format_func=lambda p:str(p.relative_to(root)), max_selections=2)
    frames = {}
    for path in selected:
        try:
            frames[str(path.relative_to(root))] = read_output(path)
        except Exception as exc:
            st.error(f'{path.name}: {exc}')
    if not frames:
        return
    channels = sorted(set.intersection(*(set(f.select_dtypes('number').columns) for f in frames.values())))
    preferred = [c for c in channels if 'PtfmHeave' in c or 'PtfmPitch' in c]
    chosen = st.multiselect('Canais', channels, default=preferred[:2] or channels[:1])
    for label, frame in frames.items():
        st.write(label)
        time = next((c for c in frame if c.lower().startswith('time')), None)
        if chosen:
            st.line_chart(frame.set_index(time)[chosen] if time else frame[chosen])
            st.dataframe(metrics(frame[chosen]))
