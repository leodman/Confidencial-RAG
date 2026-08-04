from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any
import hashlib, uuid

def utcnow(): return datetime.now(timezone.utc).isoformat()
def sha256_bytes(b: bytes)->str: return hashlib.sha256(b).hexdigest()
def stable_id(prefix: str, *parts: str)->str: return f"{prefix}_{hashlib.sha256('|'.join(parts).encode()).hexdigest()[:16]}"
@dataclass
class DocumentRecord:
    document_id: str; original_filename: str; relative_path: str; file_type: str; content_hash: str; file_size: int; ingested_at: str; status: str='indexed'; page_count:int|None=None; chunk_count:int=0; warnings:list[str]=field(default_factory=list)
    def to_dict(self): return asdict(self)
@dataclass
class ChunkRecord:
    chunk_id: str; document_id: str; text: str; chunk_index:int; page_number:int|None=None; section:str|None=None; source_path:str=''; character_start:int|None=None; character_end:int|None=None; content_hash:str=''
    def to_dict(self): return asdict(self)
@dataclass
class KnowledgeBase:
    name: str; knowledge_base_id: str=field(default_factory=lambda: str(uuid.uuid4())); created_at: str=field(default_factory=utcnow); updated_at: str=field(default_factory=utcnow); documents: dict[str,DocumentRecord]=field(default_factory=dict); chunks: dict[str,ChunkRecord]=field(default_factory=dict); embedding_model: str='sentence-transformers/all-MiniLM-L6-v2'; embedding_dimension:int=0
    def manifest(self):
        return {'format':'confidencial-rag-knowledge-base','format_version':1,'knowledge_base_id':self.knowledge_base_id,'name':self.name,'created_at':self.created_at,'updated_at':utcnow(),'document_count':len(self.documents),'chunk_count':len(self.chunks),'embedding_model':self.embedding_model,'embedding_dimension':self.embedding_dimension}
