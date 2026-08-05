import pytest
from confidencial_rag.controller import ApplicationController, InvalidStateTransition, KnowledgeBaseError
from confidencial_rag.state import SystemState

def test_normal_lifecycle(tmp_path):
    c=ApplicationController(runtime_dir=tmp_path); assert c.start() is SystemState.EMPTY; m=c.create_knowledge_base('synthetic-test-kb'); assert m['document_count']==0; assert c.state is SystemState.READY; assert c.shutdown() is SystemState.OFF
@pytest.mark.parametrize('operation',['create','save','ask'])
def test_operations_blocked_while_off(tmp_path,operation):
    c=ApplicationController(runtime_dir=tmp_path)
    with pytest.raises(InvalidStateTransition):
        if operation=='create': c.create_knowledge_base('kb')
        elif operation=='save': c.save_knowledge_base()
        else: c.ask('hello')
def test_invalid_name_cannot_escape_runtime_directory(tmp_path):
    c=ApplicationController(runtime_dir=tmp_path); c.start()
    with pytest.raises(KnowledgeBaseError): c.create_knowledge_base('../secret')
def test_chat_requires_index(tmp_path):
    c=ApplicationController(runtime_dir=tmp_path); c.start(); c.create_knowledge_base('kb')
    with pytest.raises(KnowledgeBaseError): c.ask('What is indexed?')
