from __future__ import annotations
import re, tempfile, shutil
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any
from .models import DocumentRecord, KnowledgeBase, sha256_bytes, stable_id, utcnow
from .rag_services import DocumentLoader, ExtractiveLLM, HashEmbeddingProvider, LocalVectorStore, OpenAIProvider, PrivacyGateway, RAGError, RecursiveChunker, SafeZip, load_package, save_package
from .state import SystemState
class InvalidStateTransition(RuntimeError): pass
class KnowledgeBaseError(RuntimeError): pass
@dataclass
class ApplicationController:
    state:SystemState=SystemState.OFF; runtime_dir:Path|None=None; embedding_provider:Any|None=None
    active_knowledge_base:str|None=None; kb:KnowledgeBase|None=None; vector_store:LocalVectorStore=field(default_factory=LocalVectorStore); last_operation:str='Idle'; warnings:list[str]=field(default_factory=list); exported_path:Path|None=None; _lock:RLock=field(default_factory=RLock,init=False,repr=False)
    def __post_init__(self):
        self.runtime_dir=Path(self.runtime_dir or tempfile.mkdtemp(prefix='confidencial-rag-')); self.runtime_dir.mkdir(parents=True,exist_ok=True)
        self.embedding_provider=self.embedding_provider or HashEmbeddingProvider('sentence-transformers/all-MiniLM-L6-v2')
    def start(self):
        with self._lock: self._require(SystemState.OFF); self.state=SystemState.STARTING; self.state=SystemState.EMPTY; self.last_operation='System started'; return self.state
    def create_knowledge_base(self,name):
        with self._lock:
            self._require_any(SystemState.EMPTY,SystemState.READY); clean=self._validate_name(name); self.kb=KnowledgeBase(clean, embedding_model=self.embedding_provider.model_name); self.vector_store=LocalVectorStore(); self.active_knowledge_base=clean; self.state=SystemState.READY; self.last_operation='Knowledge base created'; return self.kb.manifest()
    def load_knowledge_base(self,name): return self.create_knowledge_base(name)
    def ingest_files(self,files,chunk_size=1000,chunk_overlap=150):
        with self._lock:
            self._require(SystemState.READY); assert self.kb; self.state=SystemState.INGESTING; loader=DocumentLoader(); zip_safe=SafeZip(); paths=[]; tempdirs=[]; report=[]
            try:
                for f in files or []:
                    p=Path(f if isinstance(f,(str,Path)) else getattr(f,'name',f));
                    if p.suffix.lower()=='.zip':
                        expanded=zip_safe.expand(p); paths += [x for x in expanded if x.is_file()]; tempdirs.append(expanded[0].parents[len(expanded[0].parents)-1] if expanded else None)
                    else: paths.append(p)
                chunker=RecursiveChunker(chunk_size,chunk_overlap); self.state=SystemState.INDEXING
                for p in paths:
                    data=p.read_bytes(); h=sha256_bytes(data)
                    if any(d.content_hash==h for d in self.kb.documents.values()): report.append({'file':p.name,'status':'duplicate','warning':'Already indexed'}); continue
                    text,meta,warns=loader.load(p,p.name); doc_id=stable_id('doc',h,p.name); doc=DocumentRecord(doc_id,p.name,p.name,p.suffix.lower(),h,len(data),utcnow(),'indexed',meta.get('page_count'),0,warns)
                    chunks=chunker.chunks(doc,text); doc.chunk_count=len(chunks); self.kb.documents[doc_id]=doc
                    for c in chunks: self.kb.chunks[c.chunk_id]=c
                    if chunks:
                        vecs=self.embedding_provider.embed([c.text for c in chunks]); self.vector_store.add([c.chunk_id for c in chunks],vecs); self.kb.embedding_dimension=self.vector_store.dimension()
                    report.append({'file':p.name,'status':doc.status,'chunks':doc.chunk_count,'warnings':'; '.join(warns)})
                self.state=SystemState.READY; self.last_operation=f'Indexed {len(report)} file(s)'; return report
            except Exception as e:
                self.state=SystemState.READY; raise KnowledgeBaseError(str(e)) from None
    def ask(self,question,mode='Local only',top_k=5,minimum_similarity=0.1,custom_terms='',api_key='',model='gpt-4o-mini',confirm_non_confidential=False,external_provider=None):
        with self._lock:
            self._require(SystemState.READY); assert self.kb
            if not self.kb.chunks or not self.vector_store.chunk_ids: raise KnowledgeBaseError('Chat requires an indexed knowledge base.')
            if not question.strip(): raise KnowledgeBaseError('Enter a question before sending.')
            self.state=SystemState.CHATTING; qv=self.embedding_provider.embed([question])[0]; hits=self.vector_store.search(qv,int(top_k),float(minimum_similarity)); results=[(self.kb.chunks[cid],score) for cid,score in hits]
            citations=[{'number':i+1,'filename':self.kb.documents[c.document_id].original_filename,'page_or_section':c.section or (f'page {c.page_number}' if c.page_number else ''),'score':score,'chunk_id':c.chunk_id,'excerpt':c.text[:500]} for i,(c,score) in enumerate(results)]
            external_called=False; privacy_report={}; preview=''
            try:
                if not results: answer='I could not find sufficient evidence in the indexed documents.'
                elif mode=='Local only': answer=ExtractiveLLM().generate(question,results,citations)
                elif mode=='External, confidential':
                    gateway=PrivacyGateway(); terms=custom_terms.splitlines(); sq,vq,rq=gateway.sanitize(question,terms); sanitized=[]; vault=dict(vq); privacy_report=rq
                    for c,s in results:
                        st,vc,rc=gateway.sanitize(c.text,terms); vault.update(vc); privacy_report={k:privacy_report.get(k,0)+rc.get(k,0) for k in set(privacy_report)|set(rc)}; sanitized.append((type(c)(**{**c.to_dict(),'text':st}),s))
                    preview='Question:\n'+sq+'\n\nContext:\n'+'\n---\n'.join(c.text for c,_ in sanitized); provider=external_provider or OpenAIProvider(api_key,model); answer=gateway.restore(provider.generate(sq,sanitized,citations),vault); external_called=True
                else:
                    if not confirm_non_confidential: raise KnowledgeBaseError('Non-confidential external test mode requires explicit confirmation.')
                    provider=external_provider or OpenAIProvider(api_key,model); answer=provider.generate(question,results,citations); external_called=True
                self.state=SystemState.READY; self.last_operation='Answered question'; return {'answer':answer,'citations':citations,'evidence':citations,'privacy_report':privacy_report,'sanitized_preview':preview,'external_called':external_called}
            except Exception as e:
                self.state=SystemState.READY; raise KnowledgeBaseError(str(e)) from None
    def save_knowledge_base(self):
        self._require(SystemState.READY); p=self.runtime_dir/(self.kb.name+'.zip'); return self.export_knowledge_base(p)
    def export_knowledge_base(self,path=None):
        with self._lock:
            self._require(SystemState.READY); self.state=SystemState.EXPORTING; self.exported_path=save_package(self.kb,self.vector_store,path or (self.runtime_dir/(self.kb.name+'.zip')),{'secrets_persisted':False}); self.state=SystemState.READY; self.last_operation='Knowledge base exported'; return self.exported_path
    def import_knowledge_base(self,path):
        with self._lock:
            self._require_any(SystemState.EMPTY,SystemState.READY); prev=(self.kb,self.vector_store,self.active_knowledge_base); self.state=SystemState.IMPORTING
            try: self.kb,self.vector_store=load_package(path); self.active_knowledge_base=self.kb.name; self.state=SystemState.READY; self.last_operation='Knowledge base imported'; return self.kb.manifest()
            except Exception as e: self.kb,self.vector_store,self.active_knowledge_base=prev; self.state=SystemState.READY if prev[0] else SystemState.EMPTY; raise KnowledgeBaseError(str(e)) from None
    def remove_document(self,document_id):
        self._require(SystemState.READY); self.vector_store.remove_document(self.kb,document_id); [self.kb.chunks.pop(cid) for cid,c in list(self.kb.chunks.items()) if c.document_id==document_id]; self.kb.documents.pop(document_id,None); return True
    def status(self):
        return {'state':self.state.value,'active_knowledge_base':self.active_knowledge_base,'embedding_model':self.embedding_provider.model_name,'document_count':len(self.kb.documents) if self.kb else 0,'chunk_count':len(self.kb.chunks) if self.kb else 0,'vector_count':len(self.vector_store.chunk_ids),'last_operation':self.last_operation,'warnings':self.warnings,'exported_path':str(self.exported_path) if self.exported_path else None}
    def shutdown(self):
        self.state=SystemState.SHUTTING_DOWN; self.active_knowledge_base=None; self.kb=None; self.vector_store=LocalVectorStore(); self.state=SystemState.OFF; self.last_operation='Safe shutdown'; return self.state
    def _require(self,s):
        if self.state is not s: raise InvalidStateTransition(f'Operation requires state {s}; current state is {self.state}.')
    def _require_any(self,*ss):
        if self.state not in ss: raise InvalidStateTransition(f'Operation requires one of {ss}; current state is {self.state}.')
    def _validate_name(self,n):
        n=n.strip();
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}',n): raise KnowledgeBaseError('Use 1-64 letters, numbers, hyphens, or underscores; start with a letter or number.')
        return n
