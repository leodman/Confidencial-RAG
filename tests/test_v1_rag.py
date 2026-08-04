from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import json
from confidencial_rag.controller import ApplicationController, KnowledgeBaseError
from confidencial_rag.rag_services import PrivacyGateway, SafeZip, RAGError, RecursiveChunker
from confidencial_rag.models import DocumentRecord

class FakeExternal:
    def __init__(self): self.called=False; self.payload=None
    def generate(self,q,results,citations):
        self.called=True; self.payload=(q,[c.text for c,_ in results]); return 'Contact <EMAIL_0001> about Aurora [1]'

def write(p:Path, text:str): p.write_text(text,encoding='utf-8'); return p

def make_docx(path: Path, text: str) -> Path:
    files = {
        '[Content_Types].xml': '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        '_rels/.rels': '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        'word/document.xml': '<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>' + text + '</w:t></w:r></w:p></w:body></w:document>',
    }
    with ZipFile(path, 'w', ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return path

def test_ingestion_retrieval_export_import_roundtrip(tmp_path):
    c=ApplicationController(runtime_dir=tmp_path); c.start(); c.create_knowledge_base('demo')
    docs=[write(tmp_path/'network_policy.md','# Security Architecture\nAurora Segment keeps audit logs for 180 days.'), write(tmp_path/'support.txt','Support for Aurora Segment uses Sev-2 tickets.')]
    report=c.ingest_files(docs); assert sum(r.get('chunks',0) for r in report) >= 2
    ans=c.ask('How long are Aurora audit logs kept?', minimum_similarity=0.0)
    assert '180 days' in ans['answer']; assert ans['citations']; assert ans['external_called'] is False
    pkg=c.export_knowledge_base(tmp_path/'demo.zip'); c2=ApplicationController(runtime_dir=tmp_path/'r2'); c2.start(); c2.import_knowledge_base(pkg)
    ans2=c2.ask('How long are Aurora audit logs kept?', minimum_similarity=0.0)
    assert '180 days' in ans2['answer']

def test_loaders_and_duplicates_and_docx_example(tmp_path):
    c=ApplicationController(runtime_dir=tmp_path); c.start(); c.create_knowledge_base('kb')
    files=[write(tmp_path/'a.txt','alpha'),write(tmp_path/'b.qmd','# H\nbeta'),write(tmp_path/'c.html','<b>gamma</b>'),write(tmp_path/'d.json','{"delta": 1}'),write(tmp_path/'e.csv','name,value\nepsilon,2'),make_docx(tmp_path/'customer_requirements.docx', 'The fictional customer requires Aurora Segment recovery within four hours.')]
    rep=c.ingest_files(files); assert len(rep)==6
    dup=c.ingest_files([files[0]])[0]; assert dup['status']=='duplicate'
    assert any(d.content_hash for d in c.kb.documents.values())

def test_zip_safety(tmp_path):
    z=tmp_path/'bad.zip'
    with ZipFile(z,'w',ZIP_DEFLATED) as f: f.writestr('../evil.txt','x')
    try: SafeZip().expand(z); assert False
    except RAGError as e: assert 'unsafe path' in str(e)
    z2=tmp_path/'abs.zip'
    with ZipFile(z2,'w',ZIP_DEFLATED) as f: f.writestr('/evil.txt','x')
    try: SafeZip().expand(z2); assert False
    except RAGError: pass
    z3=tmp_path/'many.zip'
    with ZipFile(z3,'w',ZIP_DEFLATED) as f:
        for i in range(3): f.writestr(f'{i}.txt','x')
    try: SafeZip(max_files=2).expand(z3); assert False
    except RAGError: pass

def test_chunking_deterministic_overlap_heading():
    doc=DocumentRecord('d','f.md','f.md','.md','h',10,'now')
    text='# Heading\n' + 'word '*100
    a=RecursiveChunker(120,20).chunks(doc,text); b=RecursiveChunker(120,20).chunks(doc,text)
    assert [x.chunk_id for x in a]==[x.chunk_id for x in b]; assert a[0].section=='Heading'; assert len(a)>1

def test_privacy_gateway_and_confidential_external(tmp_path):
    g=PrivacyGateway(); s,v,r=g.sanitize('Email jane@example.com at 10.0.0.1 about Alpha AlphaBeta', ['AlphaBeta','Alpha'])
    assert 'jane@example.com' not in s and '<EMAIL_0001>' in s and '<IP_0001>' in s and r['CUSTOM']==2
    assert g.restore(s,v).startswith('Email jane@example.com')
    c=ApplicationController(runtime_dir=tmp_path); c.start(); c.create_knowledge_base('kb'); c.ingest_files([write(tmp_path/'p.txt','Aurora contact jane@example.com for help.')])
    fake=FakeExternal(); res=c.ask('Who helps jane@example.com?', mode='External, confidential', minimum_similarity=0.0, external_provider=fake)
    assert fake.called and res['external_called'] and 'jane@example.com' in res['answer']
    assert 'jane@example.com' not in fake.payload[0] and all('jane@example.com' not in t for t in fake.payload[1])

def test_colab_notebook_static():
    nb=json.loads(Path('colab/confidencial_rag_launcher.ipynb').read_text())
    assert all(c.get('outputs',[])==[] for c in nb['cells'] if c['cell_type']=='code')
    assert all(c.get('execution_count') is None for c in nb['cells'] if c['cell_type']=='code')
    src='\n'.join(''.join(c['source']) for c in nb['cells'])
    for needle in ['sys.executable','sys.path.insert','import confidencial_rag','getpass','share=True','auth']:
        assert needle in src
    assert 'sk-' not in src
