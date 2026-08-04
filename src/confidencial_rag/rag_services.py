from __future__ import annotations
import csv, html, io, json, math, os, re, shutil, tempfile, zipfile
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any
from .models import ChunkRecord, DocumentRecord, KnowledgeBase, sha256_bytes, stable_id, utcnow

SUPPORTED={'.txt','.md','.qmd','.html','.htm','.json','.csv','.pdf','.docx'}
class RAGError(RuntimeError): pass
class DocumentLoader:
    def load(self,path:Path, rel:str|None=None)->tuple[str,dict[str,Any],list[str]]:
        ext=path.suffix.lower(); data=path.read_bytes(); warnings=[]; meta={}
        if ext not in SUPPORTED: raise RAGError(f'Unsupported file type: {ext}')
        if ext in {'.txt','.md','.qmd'}: text=data.decode('utf-8',errors='replace')
        elif ext in {'.html','.htm'}: text=re.sub('<[^>]+>',' ',data.decode('utf-8',errors='replace')); text=html.unescape(text)
        elif ext=='.json': text=json.dumps(json.loads(data.decode('utf-8')),indent=2,sort_keys=True)
        elif ext=='.csv':
            rows=list(csv.reader(io.StringIO(data.decode('utf-8',errors='replace')))); text='\n'.join(' | '.join(r) for r in rows)
        elif ext=='.pdf':
            try:
                from pypdf import PdfReader
            except ImportError as e: raise RAGError('PDF support requires pypdf.') from e
            reader=PdfReader(str(path)); meta['page_count']=len(reader.pages); pages=[]
            for i,p in enumerate(reader.pages,1): pages.append(f'\n[Page {i}]\n'+(p.extract_text() or ''))
            text='\n'.join(pages)
            if not text.strip(): warnings.append('No extractable text was found. OCR is not implemented in Version 1.')
        elif ext=='.docx':
            try:
                from docx import Document
                text='\n'.join(p.text for p in Document(str(path)).paragraphs)
            except ImportError:
                import zipfile, xml.etree.ElementTree as ET
                with zipfile.ZipFile(path) as z:
                    root=ET.fromstring(z.read('word/document.xml'))
                text='\n'.join(node.text or '' for node in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'))
        if not text.strip(): warnings.append('Document is empty after text extraction.')
        return text, meta, warnings
class SafeZip:
    def __init__(self,max_files=200,max_total=524288000,max_depth=1): self.max_files=max_files; self.max_total=max_total; self.max_depth=max_depth
    def expand(self,zip_path:Path)->list[Path]:
        out=Path(tempfile.mkdtemp(prefix='confidencial-zip-')); seen=set(); total=0
        try:
            with zipfile.ZipFile(zip_path) as z:
                infos=[i for i in z.infolist() if not i.is_dir()]
                if len(infos)>self.max_files: raise RAGError('ZIP contains too many files.')
                for i in infos:
                    name=i.filename; p=PurePosixPath(name)
                    if name in seen: raise RAGError('ZIP contains duplicate entries.')
                    seen.add(name)
                    if p.is_absolute() or '..' in p.parts or PureWindowsPath(name).drive: raise RAGError('ZIP contains an unsafe path.')
                    if (i.external_attr >> 16) & 0o170000 == 0o120000: raise RAGError('ZIP symlinks are not supported.')
                    if Path(name).suffix.lower()=='.zip' and self.max_depth<=0: raise RAGError('Nested archives exceed safe depth.')
                    if Path(name).suffix.lower() not in SUPPORTED: raise RAGError(f'Unsupported file type in ZIP: {Path(name).suffix.lower()}')
                    total += i.file_size
                    if total>self.max_total: raise RAGError('ZIP uncompressed content is too large.')
                    dest=out / Path(*p.parts); dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(z.read(i))
            return list(out.rglob('*'))
        except Exception:
            shutil.rmtree(out,ignore_errors=True); raise
class RecursiveChunker:
    def __init__(self,chunk_size=1000,chunk_overlap=150):
        if not 100<=chunk_size<=4000 or not 0<=chunk_overlap<chunk_size: raise RAGError('Invalid chunk settings.')
        self.chunk_size=chunk_size; self.chunk_overlap=chunk_overlap
    def chunks(self,doc:DocumentRecord,text:str)->list[ChunkRecord]:
        parts=[]; start=0
        while start < len(text):
            end=min(len(text),start+self.chunk_size); cut=end
            for pat in ['\n#','\n\n','. ',' ']:
                idx=text.rfind(pat,start,end)
                if idx>start+self.chunk_size//2: cut=idx+len(pat); break
            seg=text[start:cut].strip();
            if seg:
                section=None; m=re.search(r'(?m)^#+\s+(.+)$',seg); section=m.group(1) if m else None
                cid=stable_id('chk',doc.document_id,str(len(parts)),sha256_bytes(seg.encode()))
                parts.append(ChunkRecord(cid,doc.document_id,seg,len(parts),None,section,doc.relative_path,start,cut,sha256_bytes(seg.encode())))
            if cut>=len(text): break
            start=max(cut-self.chunk_overlap, start+1)
        return parts
class HashEmbeddingProvider:
    def __init__(self,model_name='hashing-local-v1',dimension=384): self.model_name=model_name; self.dimension=dimension
    def embed(self,texts:list[str])->list[list[float]]:
        rows=[]
        for t in texts:
            row=[0.0]*self.dimension
            for w in re.findall(r'[a-z0-9]+',t.lower()): row[hash(w)%self.dimension]+=1.0
            norm=math.sqrt(sum(x*x for x in row)) or 1.0
            rows.append([x/norm for x in row])
        return rows
class SentenceTransformersEmbeddingProvider(HashEmbeddingProvider):
    def __init__(self,model_name='sentence-transformers/all-MiniLM-L6-v2',batch_size=32):
        self.model_name=model_name; self.batch_size=batch_size; self._model=None; self.dimension=384
    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model=SentenceTransformer(self.model_name); self.dimension=self._model.get_sentence_embedding_dimension()
    def embed(self,texts:list[str])->list[list[float]]:
        self._load(); return [list(map(float, row)) for row in self._model.encode(texts,batch_size=self.batch_size,normalize_embeddings=True)]
class LocalVectorStore:
    def __init__(self): self.vectors=[]; self.chunk_ids=[]
    def add(self,ids,vecs):
        self.vectors.extend([list(map(float,v)) for v in vecs]); self.chunk_ids+=list(ids)
    def remove_document(self,kb,doc_id):
        keep=[i for i,cid in enumerate(self.chunk_ids) if kb.chunks[cid].document_id!=doc_id]; self.vectors=[self.vectors[i] for i in keep]; self.chunk_ids=[self.chunk_ids[i] for i in keep]
    def search(self,q,top_k=5,min_score=0.1):
        if not self.chunk_ids: return []
        q=list(q); scored=[]
        for cid,v in zip(self.chunk_ids,self.vectors): scored.append((cid, sum(a*b for a,b in zip(v,q))))
        scored.sort(key=lambda x:x[1], reverse=True)
        return [(cid,float(score)) for cid,score in scored[:top_k] if float(score)>=min_score]
    def dimension(self): return 0 if not self.vectors else len(self.vectors[0])
    def save(self,path):
        Path(path).mkdir(parents=True,exist_ok=True); (Path(path)/'index.json').write_text(json.dumps({'vectors':self.vectors})); (Path(path)/'metadata.json').write_text(json.dumps({'chunk_ids':self.chunk_ids,'dimension':self.dimension()}))
    @classmethod
    def load(cls,path):
        s=cls(); s.vectors=json.loads((Path(path)/'index.json').read_text())['vectors']; s.chunk_ids=json.loads((Path(path)/'metadata.json').read_text())['chunk_ids']; return s
class PrivacyGateway:
    PATS={'EMAIL':r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b','PHONE':r'\b(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b','IP':r'\b(?:\d{1,3}\.){3}\d{1,3}\b','SSN':r'\b\d{3}-\d{2}-\d{4}\b','CREDIT_CARD':r'\b(?:\d[ -]*?){13,16}\b','API_KEY':r'\b(?:sk-[A-Za-z0-9_-]{12,}|[A-Za-z0-9_-]{24,})\b','UUID':r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b','URL_SECRET':r'https?://\S*(?:token|key|secret|password)=\S+'}
    def sanitize(self,text,custom_terms=None):
        vault={}; counts=Counter(); out=text
        terms=sorted([t.strip() for t in (custom_terms or []) if t.strip()],key=len,reverse=True)
        def tok(cat,val):
            if (cat,val) not in vault: vault[(cat,val)]=f'<{cat}_{sum(1 for k in vault if k[0]==cat)+1:04d}>'
            counts[cat]+=1; return vault[(cat,val)]
        for term in terms: out=re.sub(re.escape(term),lambda m: tok('CUSTOM',m.group(0)),out)
        for cat,pat in self.PATS.items(): out=re.sub(pat,lambda m,c=cat: tok(c,m.group(0)),out)
        rev={v:k[1] for k,v in vault.items()}; return out,rev,dict(counts)
    def restore(self,text,vault):
        for token,val in sorted(vault.items(),key=lambda x:len(x[0]),reverse=True): text=text.replace(token,val)
        return text
class ExtractiveLLM:
    def generate(self,question,results,citations):
        if not results: return 'I could not find sufficient evidence in the indexed documents.'
        lines=['Based on the indexed documents:']
        for n,(chunk,score) in enumerate(results[:3],1): lines.append(f"- {chunk.text[:450].strip()} [{n}]")
        return '\n'.join(lines)
class OpenAIProvider:
    def __init__(self,api_key,model='gpt-4o-mini',base_url=None):
        if not api_key: raise RAGError('An API key is required for external generation.')
        self.api_key=api_key; self.model=model; self.base_url=base_url; self.last_payload=None
    def generate(self,question,results,citations):
        from openai import OpenAI
        client=OpenAI(api_key=self.api_key,base_url=self.base_url)
        context='\n\n'.join(f"[{i+1}] {c.text}" for i,(c,_) in enumerate(results))
        self.last_payload={'question':question,'context':context}
        msg='Answer only from supplied context, preserve placeholder tokens exactly, cite sources.\nContext:\n'+context+'\nQuestion:'+question
        return client.chat.completions.create(model=self.model,messages=[{'role':'user','content':msg}],temperature=0).choices[0].message.content

def save_package(kb,store,path,config=None):
    tmp=Path(tempfile.mkdtemp(prefix='kbpkg-'));
    try:
        (tmp/'vectors').mkdir(); (tmp/'manifest.json').write_text(json.dumps(kb.manifest(),indent=2)); (tmp/'documents.json').write_text(json.dumps([d.to_dict() for d in kb.documents.values()],indent=2));
        (tmp/'chunks.jsonl').write_text('\n'.join(json.dumps(c.to_dict()) for c in kb.chunks.values())+'\n'); (tmp/'configuration.json').write_text(json.dumps(config or {},indent=2)); (tmp/'README.txt').write_text('Confidencial RAG Version 1 package. Not encrypted.'); store.save(tmp/'vectors'); shutil.make_archive(str(Path(path).with_suffix('')),'zip',tmp); return Path(path).with_suffix('.zip')
    finally: shutil.rmtree(tmp,ignore_errors=True)
def load_package(path):
    tmp=Path(tempfile.mkdtemp(prefix='kbimport-'))
    try:
        with zipfile.ZipFile(path) as z:
            seen=set(); total=0
            for i in z.infolist():
                if i.is_dir(): continue
                name=i.filename; p=PurePosixPath(name)
                if name in seen or p.is_absolute() or '..' in p.parts or PureWindowsPath(name).drive:
                    raise RAGError('Unsafe knowledge-base archive path.')
                seen.add(name); total += i.file_size
                if len(seen)>1000 or total>536870912: raise RAGError('Knowledge-base archive exceeds safe limits.')
                dest=tmp/Path(*p.parts); dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(z.read(i))
        man=json.loads((tmp/'manifest.json').read_text());
        if man.get('format')!='confidencial-rag-knowledge-base' or man.get('format_version')!=1: raise RAGError('Unsupported knowledge-base package.')
        kb=KnowledgeBase(man['name'],man['knowledge_base_id'],man['created_at']);
        for d in json.loads((tmp/'documents.json').read_text()): kb.documents[d['document_id']]=DocumentRecord(**d)
        for line in (tmp/'chunks.jsonl').read_text().splitlines():
            if line: c=ChunkRecord(**json.loads(line)); kb.chunks[c.chunk_id]=c
        store=LocalVectorStore.load(tmp/'vectors'); kb.embedding_model=man.get('embedding_model',kb.embedding_model); kb.embedding_dimension=store.dimension(); return kb,store
    finally: shutil.rmtree(tmp,ignore_errors=True)
