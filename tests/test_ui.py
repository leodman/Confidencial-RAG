from confidencial_rag.controller import ApplicationController
from confidencial_rag.ui.gradio_app import UIActions, build_interface

def test_ui_actions_do_not_echo_api_key(tmp_path):
    c=ApplicationController(runtime_dir=tmp_path); a=UIActions(c); a.start(); a.create('kb')
    out=a.chat('q','External, non-confidential test mode',5,0.1,'','SECRETKEY','model',False)
    assert 'SECRETKEY' not in repr(out)
def test_build_interface_without_launching_server():
    try:
        import gradio  # noqa: F401
    except ModuleNotFoundError:
        return
    app=build_interface(ApplicationController())
    assert app is not None
