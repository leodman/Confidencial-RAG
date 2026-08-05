from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import builtins
import json
import sys

import pytest
from confidencial_rag.controller import ApplicationController, KnowledgeBaseError
from confidencial_rag.chunking.base import RecursiveChunker
from confidencial_rag.embeddings.sentence_transformers import HashEmbeddingProvider, SentenceTransformersEmbeddingProvider
from confidencial_rag.ingestion.base import RAGError
from confidencial_rag.ingestion.zip_validator import SafeZip
from confidencial_rag.privacy.base import PrivacyGateway
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
    c=ApplicationController(runtime_dir=tmp_path, embedding_provider=HashEmbeddingProvider()); c.start(); c.create_knowledge_base('demo')
    docs=[write(tmp_path/'network_policy.md','# Security Architecture\nAurora Segment keeps audit logs for 180 days.'), write(tmp_path/'support.txt','Support for Aurora Segment uses Sev-2 tickets.')]
    report=c.ingest_files(docs); assert sum(r.get('chunks',0) for r in report) >= 2
    ans=c.ask('How long are Aurora audit logs kept?', minimum_similarity=0.0)
    assert '180 days' in ans['answer']; assert ans['citations']; assert ans['external_called'] is False
    pkg=c.export_knowledge_base(tmp_path/'demo.zip'); c2=ApplicationController(runtime_dir=tmp_path/'r2', embedding_provider=HashEmbeddingProvider()); c2.start(); c2.import_knowledge_base(pkg)
    ans2=c2.ask('How long are Aurora audit logs kept?', minimum_similarity=0.0)
    assert '180 days' in ans2['answer']

def test_loaders_and_duplicates_and_docx_example(tmp_path):
    c=ApplicationController(runtime_dir=tmp_path, embedding_provider=HashEmbeddingProvider()); c.start(); c.create_knowledge_base('kb')
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
    c=ApplicationController(runtime_dir=tmp_path, embedding_provider=HashEmbeddingProvider()); c.start(); c.create_knowledge_base('kb'); c.ingest_files([write(tmp_path/'p.txt','Aurora contact jane@example.com for help.')])
    fake=FakeExternal(); res=c.ask('Who helps jane@example.com?', mode='External, confidential', minimum_similarity=0.0, external_provider=fake)
    assert fake.called and res['external_called'] and 'jane@example.com' in res['answer']
    assert 'jane@example.com' not in fake.payload[0] and all('jane@example.com' not in t for t in fake.payload[1])

def test_colab_notebook_static():
    nb=json.loads(Path('colab/confidencial_rag_launcher.ipynb').read_text())
    assert all(c.get('outputs',[])==[] for c in nb['cells'] if c['cell_type']=='code')
    assert all(c.get('execution_count') is None for c in nb['cells'] if c['cell_type']=='code')
    src='\n'.join(''.join(c['source']) for c in nb['cells'])
    for needle in ['sys.executable','sys.path.insert','import confidencial_rag','getpass','share=True','auth','GIT_REF','FETCH_HEAD','rev-parse']:
        assert needle in src
    assert 'sk-' not in src


def test_transactional_ingestion_rolls_back_invalid_document(tmp_path):
    controller = ApplicationController(runtime_dir=tmp_path, embedding_provider=HashEmbeddingProvider())
    controller.start()
    controller.create_knowledge_base("rollback")
    good = write(tmp_path / "good.txt", "Aurora rollback baseline evidence.")
    controller.ingest_files([good])
    before_docs = {key: value.to_dict() for key, value in controller.kb.documents.items()}
    before_chunks = {key: value.to_dict() for key, value in controller.kb.chunks.items()}
    before_vectors = list(controller.vector_store.chunk_ids)
    bad = write(tmp_path / "bad.exe", "not supported")
    try:
        controller.ingest_files([write(tmp_path / "second.txt", "valid second"), bad])
        assert False
    except KnowledgeBaseError:
        pass
    assert {key: value.to_dict() for key, value in controller.kb.documents.items()} == before_docs
    assert {key: value.to_dict() for key, value in controller.kb.chunks.items()} == before_chunks
    assert controller.vector_store.chunk_ids == before_vectors


class FailingEmbedding:
    provider_name = "hashing"
    model_name = "sha256-hashing-test-v1"
    dimension = 384

    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        if self.calls > 1:
            raise RuntimeError("synthetic embedding failure")
        return [[1.0] + [0.0] * 383 for _ in texts]


def test_transactional_ingestion_rolls_back_embedding_failure(tmp_path):
    provider = FailingEmbedding()
    controller = ApplicationController(runtime_dir=tmp_path, embedding_provider=provider)
    controller.start()
    controller.create_knowledge_base("rollback_embed")
    controller.ingest_files([write(tmp_path / "first.txt", "baseline")])
    before = controller.kb.manifest()
    try:
        controller.ingest_files([write(tmp_path / "second.txt", "will fail")])
        assert False
    except KnowledgeBaseError:
        pass
    assert controller.kb.manifest()["document_count"] == before["document_count"]
    assert controller.kb.manifest()["chunk_count"] == before["chunk_count"]


def test_single_privacy_session_avoids_external_payload_leakage(tmp_path):
    controller = ApplicationController(runtime_dir=tmp_path, embedding_provider=HashEmbeddingProvider())
    controller.start()
    controller.create_knowledge_base("privacy")
    doc = write(
        tmp_path / "acme_project.txt",
        "AlphaBeta owner jane@example.com and backup jane@example.com coordinate with john@example.com at 10.1.2.3.",
    )
    controller.ingest_files([doc])
    fake = FakeExternal()
    result = controller.ask(
        "Ask jane@example.com about Alpha and AlphaBeta from john@example.com",
        mode="External, confidential",
        minimum_similarity=0.0,
        custom_terms="AlphaBeta\nAlpha",
        external_provider=fake,
    )
    outbound = repr(fake.payload)
    assert "jane@example.com" not in outbound
    assert "john@example.com" not in outbound
    assert "AlphaBeta" not in outbound
    assert "Alpha" not in outbound
    assert "10.1.2.3" not in outbound
    assert result["privacy_report"]["EMAIL"] >= 3
    assert result["privacy_report"]["CUSTOM"] >= 2


def test_pdf_page_metadata_is_structured(tmp_path):
    pytest = __import__("pytest")
    fpdf = pytest.importorskip("fpdf")
    pdf_path = tmp_path / "pages.pdf"
    pdf = fpdf.FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "First page unrelated.")
    pdf.add_page()
    pdf.cell(0, 10, "Second page says Aurora page-aware citation.")
    pdf.output(str(pdf_path))
    controller = ApplicationController(runtime_dir=tmp_path, embedding_provider=HashEmbeddingProvider())
    controller.start()
    controller.create_knowledge_base("pdfpages")
    controller.ingest_files([pdf_path], chunk_size=200, chunk_overlap=0)
    page_numbers = {chunk.page_number for chunk in controller.kb.chunks.values()}
    assert page_numbers == {1, 2}
    answer = controller.ask("Where is page-aware citation?", minimum_similarity=0.0)
    assert any(citation["page_or_section"] == "page 2" for citation in answer["citations"])



@pytest.mark.integration
def test_real_sentence_transformers_export_import_requery(tmp_path):
    provider = SentenceTransformersEmbeddingProvider()
    vectors = provider.embed(["Aurora integration evidence", "unrelated synthetic text"])
    assert len(vectors) == 2
    assert len(vectors[0]) == provider.dimension
    assert provider.provider_name == "sentence_transformers"
    assert provider.model_name == "sentence-transformers/all-MiniLM-L6-v2"

    controller = ApplicationController(runtime_dir=tmp_path / "runtime1", embedding_provider=provider)
    controller.start()
    controller.create_knowledge_base("real_embeddings")
    controller.ingest_files([write(tmp_path / "real.txt", "Aurora integration evidence requires seven day retention.")])
    package = controller.export_knowledge_base(tmp_path / "real_embeddings.zip")
    controller.shutdown()

    fresh_provider = SentenceTransformersEmbeddingProvider()
    fresh_controller = ApplicationController(runtime_dir=tmp_path / "runtime2", embedding_provider=fresh_provider)
    fresh_controller.start()
    fresh_controller.import_knowledge_base(package)
    answer = fresh_controller.ask("What retention does Aurora integration evidence require?", minimum_similarity=0.0)
    assert answer["citations"]
    assert "real.txt" == answer["citations"][0]["filename"]
    fresh_controller.shutdown()



def test_missing_sentence_transformers_raises_clear_error(monkeypatch):
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "sentence_transformers" or name.startswith("sentence_transformers."):
            raise ImportError("synthetic missing dependency")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    provider = SentenceTransformersEmbeddingProvider()
    try:
        provider.embed(["synthetic text"])
        assert False
    except RAGError as exc:
        assert "sentence-transformers is required" in str(exc)


def test_sentence_transformers_model_load_failure_raises_clear_error(monkeypatch):
    class FailingSentenceTransformer:
        def __init__(self, model_name):
            raise RuntimeError(f"cannot load {model_name}")

    class FakeModule:
        SentenceTransformer = FailingSentenceTransformer

    monkeypatch.setitem(sys.modules, "sentence_transformers", FakeModule())
    provider = SentenceTransformersEmbeddingProvider()
    try:
        provider.embed(["synthetic text"])
        assert False
    except RAGError as exc:
        assert "embedding model could not be loaded" in str(exc)


def test_failed_embedding_creates_no_package(tmp_path):
    controller = ApplicationController(runtime_dir=tmp_path, embedding_provider=FailingEmbedding())
    controller.start()
    controller.create_knowledge_base("no_package")
    controller.ingest_files([write(tmp_path / "first.txt", "baseline")])
    package = tmp_path / "no_package.zip"
    try:
        controller.ingest_files([write(tmp_path / "second.txt", "will fail")])
        assert False
    except KnowledgeBaseError:
        pass
    assert not package.exists()


def test_hashing_manifest_never_claims_minilm(tmp_path):
    controller = ApplicationController(runtime_dir=tmp_path, embedding_provider=HashEmbeddingProvider())
    controller.start()
    manifest = controller.create_knowledge_base("hash_manifest")
    assert manifest["embedding_provider"] == "hashing"
    assert manifest["embedding_model"] == "sha256-hashing-test-v1"
    assert manifest["embedding_model"] != "sentence-transformers/all-MiniLM-L6-v2"
    controller.ingest_files([write(tmp_path / "hash.txt", "hashing synthetic evidence")])
    package = controller.export_knowledge_base(tmp_path / "hash_manifest.zip")
    import zipfile

    with zipfile.ZipFile(package) as archive:
        exported_manifest = json.loads(archive.read("manifest.json"))
    assert exported_manifest["embedding_provider"] == "hashing"
    assert exported_manifest["embedding_model"] == "sha256-hashing-test-v1"


def test_import_rejects_provider_model_and_dimension_mismatch(tmp_path):
    controller = ApplicationController(runtime_dir=tmp_path, embedding_provider=HashEmbeddingProvider())
    controller.start()
    controller.create_knowledge_base("compat")
    controller.ingest_files([write(tmp_path / "compat.txt", "compatibility evidence")])
    package = controller.export_knowledge_base(tmp_path / "compat.zip")

    mismatched_provider = HashEmbeddingProvider(model_name="different-hash-model", dimension=384)
    fresh = ApplicationController(runtime_dir=tmp_path / "fresh", embedding_provider=mismatched_provider)
    fresh.start()
    try:
        fresh.import_knowledge_base(package)
        assert False
    except KnowledgeBaseError as exc:
        assert "embedding model is incompatible" in str(exc)

    mismatched_dimension = HashEmbeddingProvider(model_name="sha256-hashing-test-v1", dimension=128)
    fresh_dimension = ApplicationController(runtime_dir=tmp_path / "fresh-dim", embedding_provider=mismatched_dimension)
    fresh_dimension.start()
    try:
        fresh_dimension.import_knowledge_base(package)
        assert False
    except KnowledgeBaseError as exc:
        assert "embedding dimension" in str(exc) or "incompatible" in str(exc)
