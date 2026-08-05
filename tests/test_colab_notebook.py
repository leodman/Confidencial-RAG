import json
from pathlib import Path

def test_notebook_is_clean_and_colab_ready():
    nb=json.loads(Path('colab/confidencial_rag_launcher.ipynb').read_text())
    src='\n'.join(''.join(c.get('source',[])) for c in nb['cells'])
    assert all(c.get('outputs',[])==[] for c in nb['cells'] if c['cell_type']=='code')
    assert all(c.get('execution_count') is None for c in nb['cells'] if c['cell_type']=='code')
    assert 'sys.executable' in src and 'sys.path.insert' in src and 'import confidencial_rag' in src
    assert 'GIT_REF' in src and "fetch', 'origin', GIT_REF" in src
    assert "checkout', '--detach', 'FETCH_HEAD" in src and 'rev-parse' in src
    assert 'getpass' in src and 'share=True' in src and 'password' in src
