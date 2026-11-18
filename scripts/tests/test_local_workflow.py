"""Per-window isolation, once-only consent, and capability-driven dispatch."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from common.local_context import create_context, install_policy
from module.package_course import export_source
from module.local_validation import node_references
from test_delivery import course, snapshot

SCRIPTS=Path(__file__).resolve().parents[1]


def capability(**available):
    base={key:False for key in ('node','typescript','babel','runtime','build','browser','statistics','pillow','pythonAst','ffmpeg')}
    return {'available':{**base,**available},'missing':['node'],'configurationMissing':[],'node':None,'shukuRoot':None}


def test_install_question_once_across_windows_and_decline_persists():
    first=install_policy(missing=['node'],owner='window-a')
    second=install_policy(missing=['ffmpeg'],owner='window-b')
    assert first['askUser'] and not second['askUser']
    assert first['requestId']==second['requestId']
    with pytest.raises(ValueError):install_policy(decision='declined',request_id='wrong')
    install_policy(decision='declined',request_id=first['requestId'])
    assert install_policy(missing=['browser'])['installation']=='declined'
    assert not install_policy(missing=['new-dependency'])['askUser']


def test_concurrent_question_claim_does_not_duplicate(tmp_path):
    command=[sys.executable,'-c',"import sys,json;sys.path.insert(0,sys.argv[1]);from local_context import install_policy;print(json.dumps(install_policy(missing=['node'])))",str(SCRIPTS/'common')]
    def run(_):return subprocess.run(command,env=os.environ.copy(),text=True,capture_output=True)
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run,range(4)))
    documents=[json.loads(r.stdout) for r in results if r.returncode==0]
    assert sum(d['askUser'] for d in documents)==1
    assert install_policy()['installation']=='pending'


def test_two_window_contexts_do_not_change_global_target_or_each_other(tmp_path):
    a=tmp_path/'a';b=tmp_path/'b';a.mkdir();b.mkdir()
    ca=course(a);cb=course(b)
    first=create_context(a,tmp_path/'contexts',module=ca.name)
    second=create_context(b,tmp_path/'contexts',module=cb.name)
    assert first['context']!=second['context']
    for ctx,expected in [(first,ca),(second,cb)]:
        completed=subprocess.run([sys.executable,str(SCRIPTS/'tools.py'),'--context',ctx['context'],'check.outlines'],
            cwd=tmp_path,env=os.environ.copy(),text=True,capture_output=True,check=True)
        assert json.loads(completed.stdout)['modules']==1
        result=export_source([expected],context=Path(ctx['context']),checks='basic')
        assert result['status']=='passed'
    denied=export_source([cb],context=Path(first['context']),checks='basic')
    assert denied['status']=='error' and not denied['outputCreated']
    assert json.loads(Path(first['context']).read_text())['targetRoot']==str(a.resolve())


def test_bound_course_rejects_other_module_in_same_project(tmp_path):
    a=course(tmp_path/'project');b=course(a.parent)
    ctx=create_context(a.parent,tmp_path/'contexts',module=a.name)
    completed=subprocess.run([sys.executable,str(SCRIPTS/'tools.py'),'--context',ctx['context'],'check.outlines','--module='+b.name],
        text=True,capture_output=True)
    assert completed.returncode==2 and 'conflicts' in completed.stdout


def test_concurrent_package_outputs_and_reports_are_unique(tmp_path):
    root=course(tmp_path/'source');before=snapshot(root)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:export_source([root],checks='basic'),range(2)))
    assert all(r['status']=='passed' for r in results)
    assert results[0]['output']!=results[1]['output']
    assert results[0]['reportPath']!=results[1]['reportPath']
    assert snapshot(root)==before


def test_auto_stops_to_ask_then_continues_after_decline(tmp_path,monkeypatch):
    from module import package_course
    root=course(tmp_path/'source')
    monkeypatch.setattr(package_course,'capabilities',lambda **kw:capability())
    first=export_source([root],checks='auto')
    assert first['status']=='needs-input' and first['requiresUserConfirmation']
    second=export_source([root],checks='auto')
    assert second['status']=='needs-input' and not second['requiresUserConfirmation']
    install_policy(decision='declined',request_id=first['dependencySetup']['policy']['requestId'])
    monkeypatch.setattr(package_course,'local_checks',lambda f,*a,**kw:(f,{'issues':[],'checks':[{'check':'node','status':'unverified'}],
                                                                      'coverage':{'localBuild':False,'rendering':False}}))
    final=export_source([root],checks='auto')
    assert final['status']=='passed' and final['localChecks']['checks'][0]['status']=='unverified'


def test_ready_environment_runs_local_checks_and_failure_blocks_zip(tmp_path,monkeypatch):
    from module import package_course
    root=course(tmp_path/'source');cap=capability();cap['missing']=[]
    monkeypatch.setattr(package_course,'capabilities',lambda **kw:cap)
    calls=[]
    def validate(files,*args,**kw):
        calls.append(True)
        return files,{'issues':[{'code':'LOCAL_CHECK_FAILED','path':'typecheck','message':'real error','blocking':True}],
                      'checks':[{'check':'typecheck','status':'failed'}],'coverage':{'localBuild':False,'rendering':False}}
    monkeypatch.setattr(package_course,'local_checks',validate)
    result=export_source([root],checks='auto')
    assert calls and result['status']=='failed' and not Path(result['output']).exists()
    assert not result['dependencySetup']['policy']['askUser']


@pytest.mark.skipif(not __import__('shutil').which('node'),reason='Existing Node required for original planner integration')
def test_node_planner_preserves_original_dynamic_migration_capability(tmp_path):
    import shutil
    root=course(tmp_path/'source');(root/'assets/images').mkdir(parents=True)
    (root/'assets/images/a.webp').write_bytes(b'converted-placeholder')
    (root/'Guide.tsx').write_text('const ids=["a"]; const path=`images/${ids[0]}.png`;')
    prefix='modules/'+root.name
    files={prefix+'/'+p.relative_to(root).as_posix():p for p in root.rglob('*') if p.is_file()}
    result,report=node_references(files,{prefix+'/assets/images/a.png':prefix+'/assets/images/a.webp'},tmp_path/'references',
                                  {'node':shutil.which('node'),'shukuRoot':None})
    assert not [i for i in report['issues'] if i['blocking']],report
    assert '.webp' in result[prefix+'/Guide.tsx'].read_text()
    assert '.png' in (root/'Guide.tsx').read_text()


def test_media_presence_controls_ffmpeg_request(tmp_path,monkeypatch):
    from module import package_course
    root=course(tmp_path/'source');seen=[]
    def probe(**kwargs):
        seen.append(kwargs['media']);return capability()
    monkeypatch.setattr(package_course,'capabilities',probe)
    export_source([root],checks='auto')
    (root/'assets').mkdir();(root/'assets/sound.wma').write_bytes(b'fixture')
    export_source([root],checks='auto')
    assert seen==[False,True]


def test_installer_requires_saved_consent_and_failure_does_not_reask(tmp_path,monkeypatch,capsys):
    from checks import install_dependencies as installer
    monkeypatch.setattr(installer,'capabilities',lambda **kw:capability())
    monkeypatch.setattr(installer,'install_plan',lambda cap:([['fake-installer']],[]))
    assert installer.main(['--apply'])==2
    assert install_policy()['installation']=='unknown'
    request=install_policy(missing=['node'])
    install_policy(decision='allowed',request_id=request['requestId'])
    class Failed:returncode=1
    monkeypatch.setattr(installer.subprocess,'run',lambda *a,**kw:Failed())
    assert installer.main(['--apply'])==2
    policy=install_policy(missing=['node','browser'])
    assert policy['installation']=='allowed' and not policy['askUser']
    assert not (Path(os.environ['CREATOR_SKILL_LOCAL_STATE'])/'install.lock').exists()


def test_bound_context_rejects_cleanup_of_sibling_course(tmp_path):
    a=course(tmp_path/'project');b=course(a.parent)
    scratch=b/'_scratchpad';scratch.mkdir();(scratch/'keep.txt').write_text('keep')
    ctx=create_context(a.parent,tmp_path/'contexts',module=a.name)
    completed=subprocess.run([sys.executable,str(SCRIPTS/'tools.py'),'--context',ctx['context'],'scratchpad.clean',str(b),'--apply'],
        text=True,capture_output=True)
    assert completed.returncode==2 and (scratch/'keep.txt').is_file()


def test_recorded_browser_errors_block_instead_of_becoming_environment_warnings(tmp_path,monkeypatch):
    from module import local_validation
    root=course(tmp_path/'source');prefix='modules/'+root.name
    files={prefix+'/'+p.name:p for p in root.iterdir() if p.is_file()}
    cap=capability(build=True,browser=True);cap['shukuRoot']=str(tmp_path/'shuku')
    def run(command,**kwargs):
        if any('check_guide.py' in str(arg) for arg in command):
            return {'exitCode':2,'result':{'errors':[{'error':'Actual page failed to render'}]},'log':None}
        return {'exitCode':0,'result':{},'log':None}
    monkeypatch.setattr(local_validation,'run_command',run)
    staging=tmp_path/'stage';staging.mkdir()
    _,report=local_validation.local_checks(files,staging,cap,tmp_path/'evidence')
    assert any(i['blocking'] and i['path'].endswith('guide-browser') for i in report['issues'])


def test_standalone_preview_checks_staged_source_without_claiming_a_platform_build(tmp_path, monkeypatch):
    from module import local_validation

    course_module = course(tmp_path / 'source')
    prefix = 'modules/' + course_module.name
    files = {prefix + '/' + file.name: file for file in course_module.iterdir() if file.is_file()}
    capability_with_preview = capability(preview=True, browser=True)
    capability_with_preview['node'] = 'node'
    staging = tmp_path / 'stage'
    staging.mkdir()

    def run(command, **kwargs):
        if any('check_standalone_preview.py' in str(arg) for arg in command):
            project = Path(command[command.index('--project') + 1])
            assert project == staging / 'checked-source'
            assert (project / prefix / 'outlines.json').is_file()
        return {'exitCode': 0, 'result': {}, 'log': None}

    monkeypatch.setattr(local_validation, 'run_command', run)
    _, report = local_validation.local_checks(files, staging, capability_with_preview, tmp_path / 'evidence')
    assert report['coverage'] == {'localBuild': False, 'rendering': False, 'standaloneRendering': True}
