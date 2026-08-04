from __future__ import annotations
import json
from ..controller import ApplicationController, InvalidStateTransition, KnowledgeBaseError
class UIActions:
    def __init__(self, controller: ApplicationController): self.controller=controller
    def status_values(self,msg=''):
        s=self.controller.status(); return (s['state'].upper(),s['active_knowledge_base'] or 'None',s['embedding_model'],s['document_count'],s['chunk_count'],s['vector_count'],s['last_operation'],msg)
    def _run(self,fn,ok):
        try: fn(); return self.status_values('Success: '+ok)
        except (InvalidStateTransition,KnowledgeBaseError,ValueError) as e: return self.status_values('Error: '+str(e))
    def start(self): return self._run(self.controller.start,'System started.')
    def shutdown(self): return self._run(self.controller.shutdown,'System shut down safely.')
    def create(self,name): return self._run(lambda:self.controller.create_knowledge_base(name),'Knowledge base created.')
    def import_kb(self,file): return self._run(lambda:self.controller.import_knowledge_base(getattr(file,'name',file)),'Knowledge base imported.')
    def save(self): return self._run(self.controller.save_knowledge_base,'Knowledge base saved.')
    def export(self):
        try: p=self.controller.export_knowledge_base(); return (*self.status_values('Success: Knowledge base exported.'), str(p))
        except Exception as e: return (*self.status_values('Error: '+str(e)), None)
    def ingest(self,files,zip_file,chunk_size,overlap):
        selected=[]; selected += files or []
        if zip_file: selected.append(zip_file)
        try: report=self.controller.ingest_files(selected,int(chunk_size),int(overlap)); return (*self.status_values('Success: Documents indexed.'), report)
        except Exception as e: return (*self.status_values('Error: '+str(e)), [])
    def chat(self,q,mode,top_k,minsim,terms,key,model,confirm):
        try:
            r=self.controller.ask(q,mode,int(top_k),float(minsim),terms,key,model,bool(confirm))
            return (r['answer'],json.dumps(r['citations'],indent=2),json.dumps(r['evidence'],indent=2),json.dumps(r['privacy_report'],indent=2),r['sanitized_preview'], 'Yes' if r['external_called'] else 'No', *self.status_values('Success: Answer generated.'))
        except Exception as e: return ('','','','{}','', 'No', *self.status_values('Error: '+str(e)))

def build_interface(controller: ApplicationController|None=None):
    import gradio as gr
    actions=UIActions(controller or ApplicationController()); init=actions.status_values('System is off.')
    with gr.Blocks(title='Confidencial RAG') as app:
        gr.Markdown('# Confidencial RAG Version 1\nExperimental local RAG with a fail-closed confidential external mode. Not production security.')
        with gr.Tab('System'):
            state=gr.Textbox(label='System state',value=init[0],interactive=False); kb=gr.Textbox(label='Active knowledge base',value=init[1],interactive=False); model=gr.Textbox(label='Embedding model',value=init[2],interactive=False); docs=gr.Number(label='Documents',value=init[3],interactive=False); chunks=gr.Number(label='Chunks',value=init[4],interactive=False); vectors=gr.Number(label='Vectors',value=init[5],interactive=False); last=gr.Textbox(label='Last operation',value=init[6],interactive=False); status=gr.Textbox(label='Status',value=init[7],interactive=False); gr.Button('Start System',variant='primary').click(actions.start,outputs=[state,kb,model,docs,chunks,vectors,last,status]); gr.Button('Safe Shutdown').click(actions.shutdown,outputs=[state,kb,model,docs,chunks,vectors,last,status])
        outs=[state,kb,model,docs,chunks,vectors,last,status]
        with gr.Tab('Knowledge Base'):
            name=gr.Textbox(label='Knowledge-base name',value='demo_kb'); gr.Button('Create knowledge base').click(actions.create,inputs=name,outputs=outs); import_file=gr.File(label='Upload knowledge-base ZIP'); gr.Button('Import knowledge base').click(actions.import_kb,inputs=import_file,outputs=outs); gr.Button('Save').click(actions.save,outputs=outs); download=gr.File(label='Download exported ZIP'); gr.Button('Export ZIP').click(actions.export,outputs=outs+[download])
        with gr.Tab('Documents'):
            files=gr.File(label='Upload documents',file_count='multiple'); zf=gr.File(label='Upload ZIP'); cs=gr.Slider(100,4000,value=1000,step=50,label='Chunk size'); ov=gr.Slider(0,1000,value=150,step=10,label='Chunk overlap'); table=gr.JSON(label='Document indexing report'); gr.Button('Index uploaded files',variant='primary').click(actions.ingest,inputs=[files,zf,cs,ov],outputs=outs+[table])
        with gr.Tab('Chat'):
            q=gr.Textbox(label='Question'); mode=gr.Radio(['Local only','External, confidential','External, non-confidential test mode'],value='Local only',label='Answer mode'); top=gr.Slider(1,20,value=5,step=1,label='Top K'); ms=gr.Slider(0,1,value=0.1,step=.01,label='Minimum relevance'); terms=gr.Textbox(label='Additional protected terms (one per line)',lines=4); key=gr.Textbox(label='Optional API key',type='password'); emodel=gr.Textbox(label='External model',value='gpt-4o-mini'); confirm=gr.Checkbox(label='I understand non-confidential test mode may send raw text externally.'); ans=gr.Textbox(label='Grounded answer',lines=8); cites=gr.Code(label='Citations'); ev=gr.Code(label='Retrieved evidence'); pr=gr.Code(label='Privacy report'); prev=gr.Textbox(label='Sanitized-request preview (collapsed by default)',lines=6,visible=True); called=gr.Textbox(label='External provider called?',interactive=False); gr.Button('Send',variant='primary').click(actions.chat,inputs=[q,mode,top,ms,terms,key,emodel,confirm],outputs=[ans,cites,ev,pr,prev,called]+outs); gr.Button('Clear chat').click(lambda:('','','','{}','','No'),outputs=[ans,cites,ev,pr,prev,called])
        with gr.Tab('Settings'):
            gr.Markdown('Safe defaults: chunk size 1000, overlap 150, top-k 5, minimum similarity 0.10, local-only answer mode. Upload limits are enforced by controller configuration in Version 1.')
    return app

def launch(*,share=False,username=None,password=None):
    if share and (not username or not password): raise ValueError('A username and password are required when sharing is enabled.')
    return build_interface().launch(share=share,auth=(username,password) if username and password else None)
if __name__=='__main__': launch()
