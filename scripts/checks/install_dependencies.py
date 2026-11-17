"""Plan or install local dependencies using saved user consent. Never touches servers."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(SCRIPTS),str(SCRIPTS/'common')]
from local_context import install_policy, state_root
from module.local_validation import capabilities


def install_plan(capability):
    missing = set(capability['missing'])
    skill = SCRIPTS.parent
    commands, manual = [], []
    winget, brew = shutil.which('winget'), shutil.which('brew')
    for item, windows, mac in [('node','OpenJS.NodeJS.LTS','node'),('ffmpeg','Gyan.FFmpeg','ffmpeg')]:
        if item not in missing: continue
        if os.name=='nt' and winget:
            commands.append([winget,'install','--id',windows,'--exact','--silent','--accept-source-agreements','--accept-package-agreements'])
        elif brew:
            commands.append([brew,'install',mac])
        else:
            manual.append({'dependency':item,'action':'安装本机对应工具后重试；已保存意愿，不重复提问。'})
    if 'python-images' in missing:
        commands.append([sys.executable,'-m','pip','install','-r',str(SCRIPTS/'requirements-pack.txt')])
    if 'statistics-packages' in missing:
        commands.append([sys.executable,'-m','pip','install','numpy','Pillow'])
    if 'browser' in missing:
        commands.extend([[sys.executable,'-m','pip','install','-r',str(SCRIPTS/'requirements-capture.txt')],
                         [sys.executable,'-m','playwright','install','chromium']])
    npm = shutil.which('npm')
    if npm:
        if 'preview-packages' in missing:
            commands.append([npm,'--prefix',str(skill/'player-preview'),'ci','--no-audit','--no-fund'])
        if 'builder-packages' in missing and capability.get('shukuRoot'):
            commands.append([npm,'--prefix',str(Path(capability['shukuRoot'])/'tooling/course-build'),'ci','--no-audit','--no-fund'])
    elif 'node' not in missing and ({'preview-packages','builder-packages'} & missing):
        manual.append({'dependency':'npm','action':'检查Node/npm安装目录与PATH，使用实际可执行文件路径；不重复询问安装意愿。'})
    return commands, manual


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',help='Install only when saved preference is allowed; default plan only')
    parser.add_argument('--shuku-root',type=Path)
    parser.add_argument('--media',action='store_true',help='Include FFmpeg only when current course contains audio/video')
    args=parser.parse_args(argv)
    lock=None
    try:
        capability=capabilities(shuku=args.shuku_root or os.environ.get('SHUKU_ROOT'),media=args.media)
        commands,manual=install_plan(capability)
        policy=install_policy()
        result={'status':'plan','commands':commands,'manual':manual,'policy':policy,'configurationMissing':capability['configurationMissing']}
        if args.apply:
            if policy['installation']!='allowed':
                raise ValueError('尚无已保存的安装同意；先读取一次性询问结果并保存用户回答，不能直接安装。')
            lock=state_root()/'install.lock'
            lock.mkdir()
            results=[]
            for index,command in enumerate(commands):
                log=state_root()/f'install-{os.getpid()}-{index}.log'
                with log.open('w',encoding='utf-8') as output:
                    process=subprocess.run(command,stdout=output,stderr=subprocess.STDOUT,timeout=900,check=False)
                results.append({'command':command,'exitCode':process.returncode,'log':str(log)})
                if process.returncode: break
            result.update(status='error' if any(r['exitCode'] for r in results) else 'retry-capabilities',results=results,
                          note='重新探测环境并运行 course.pack；安装失败只报告，不再次询问意愿。新装可执行文件可能需要刷新当前窗口PATH。')
        print(json.dumps(result,ensure_ascii=False))
        return 2 if result['status']=='error' else 0
    except (OSError,ValueError,subprocess.TimeoutExpired) as error:
        print(json.dumps({'status':'error','error':str(error),'nextAction':'检查已有记录和日志，不重复询问用户。'},ensure_ascii=False))
        return 2
    finally:
        # Only remove the lock acquired by this invocation.
        if lock is not None and 'results' in locals(): lock.rmdir()


if __name__=='__main__':raise SystemExit(main())
