"""Detailed pipeline reporting and agent handoff; never asks or uploads itself."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from skzip import SERVER_PENDING
from common.submission_policy import issue


def start_report(directories, output):
    return {'status': 'running', 'inputs': [str(Path(p).expanduser().absolute()) for p in directories],
            'output': str(output) if output is not None else None,
            'outputCreated': False, 'serverPending': list(SERVER_PENDING),
            'startedAt': datetime.now(timezone.utc).isoformat(),
            'stages': [], 'issues': {'serious': [], 'warnings': []}, 'coverage': {
                'sourceChecks': False, 'zipIntegrity': False, 'realBuild': False,
                'rendering': False, 'securityReview': False, 'productionUpload': False}}


def record_stage(report, name, started, status, **details):
    report['stages'].append({'name': name, 'status': status,
                            'elapsedSeconds': round(time.monotonic() - started, 3), **details})


def finish_report(report, started, status):
    """Separate upload eligibility from the user's decision to actually upload."""
    serious, warnings = report['issues']['serious'], report['issues']['warnings']
    for group in (serious, warnings):
        for index, item in enumerate(group):
            defaults = issue(item.get('code', item.get('kind', 'SOURCE_CHECK_FAILED')),
                item.get('path', item.get('directory', '')), item.get('message', item.get('reason', '源码检查问题')),
                '严重错误会阻止出包；提醒需由作者决定修复或继续提交。',
                '按文件路径核对元数据、入口和引用，修复后重新运行 course.pack。')
            group[index] = {**defaults, **item}
    report['passedCheckCount'] = report.get('passedCheckCount', 0) + int(report['coverage']['zipIntegrity'])
    report.update(status=status, elapsedSeconds=round(time.monotonic() - started, 3),
                  seriousErrorCount=len(serious), warningCount=len(warnings),
                  warnings=warnings,
                  uploadEligible=bool(report['outputCreated'] and not serious and report['coverage']['zipIntegrity']),
                  uploadAuthorized=False, requiresUserConfirmation=False)
    if status in {'needs-input','needs-setup'}:
        setup = report['dependencySetup']
        report['agentNextAction'] = setup['nextAction']
        report['requiresUserConfirmation'] = setup['policy']['askUser']
        report['userOptions'] = ['allowed','declined'] if setup['policy']['askUser'] else []
        report['userPrompt'] = setup['policy']['question'] or ('依赖安装意愿已保存；补齐授权依赖后重跑，不重复询问。' if status=='needs-setup' else '另一窗口已发起一次性询问，等待保存回答，不重复询问。')
    elif serious:
        report['agentNextAction'] = 'repair-and-repack'
        report['userOptions'] = []
        report['userPrompt'] = '按文件、行号和转换映射修复已授权范围内的问题，再运行 course.pack；仅在取舍不明或缺少条件时询问用户。'
    elif warnings:
        report['agentNextAction'] = 'review-warnings-and-repair-as-authorized'
        report['userOptions'] = []
        report['userPrompt'] = '检查提醒，自动修复任务范围内可确定的问题；媒体听感、动态引用与内容取舍按证据核对。打包不执行上传。'
    else:
        report['agentNextAction'] = 'deliver-package'
        report['userOptions'] = []
        report['userPrompt'] = '交付 ZIP 与简要结果。上传按用户已有授权及目标平台规则执行，打包本身不上传。'
    report['summary'] = {key: report.get(key) for key in (
        'moduleCount', 'rejectedModuleCount', 'files', 'sourceBytes', 'zipBytes',
        'passedCheckCount', 'seriousErrorCount', 'warningCount', 'elapsedSeconds', 'uploadEligible')}
    if report['output'] is None:
        report['reportPath'] = None
        return report
    destination = Path(report['output']).with_suffix('.report.json')
    report['reportPath'] = str(destination)
    report['readableReportPath'] = str(Path(report['output']).with_suffix('.report.md'))
    try:
        with destination.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
    except OSError as error:
        report['reportPath'] = None
        report['reportWriteWarning'] = str(error)
    readable = Path(report['output']).with_suffix('.report.md')
    lines = [f"通过 {report['passedCheckCount']} 项；警告 {len(warnings)} 项；严重错误 {len(serious)} 项。",
             '', '统计范围：逐文件位置检查、逐课件元数据检查，以及最终包完整性检查；不是服务器检查通过数。',
             '', report['userPrompt']]
    for label, items in [('严重错误', serious), ('警告', warnings)]:
        for item in items:
            lines.extend(['', f"## {label} · {item['code']}", '',
                f"文件：{item['path']}" + (f"，行 {item['line']}" if item.get('line') else ''),
                f"问题：{item['message']}", f"影响：{item['impact']}",
                f"修复：{item['repair']}", f"复验：{item['recheck']}"])
    try:
        with readable.open('x', encoding='utf-8') as stream:
            stream.write('\n\n'.join(lines)+'\n')
        report['readableReportPath'] = str(readable)
    except OSError as error:
        report['readableReportWriteWarning'] = str(error)
    return report


def agent_summary(report, limit=20):
    """Bound console output without hiding counts, failures or the full report location."""
    problems = [dict(item, severity=severity) for severity in ('serious', 'warnings')
                for item in report['issues'][severity]]
    compact = {key: report.get(key) for key in (
        'status', 'output', 'outputCreated', 'summary', 'reportPath', 'readableReportPath',
        'coverage', 'serverPending', 'agentNextAction', 'uploadEligible',
        'seriousErrorCount', 'warningCount', 'reportWriteWarning', 'readableReportWriteWarning')}
    compact['issues'] = [{k: item[k] for k in ('severity', 'code', 'path', 'line', 'message',
                          'source', 'target', 'expression', 'repair') if k in item}
                         for item in problems[:limit]]
    compact['remainingIssues'] = max(0, len(problems)-limit)
    compact['media'] = {key: report.get('media', {}).get(key) for key in ('counts', 'savedBytes')}
    compact['references'] = {key: report.get('media', {}).get('references', {}).get(key)
                              for key in ('changedFiles', 'replacements')}
    compact['images'] = {key: report.get('images', {}).get(key) for key in ('counts', 'converted')}
    if 'dependencySetup' in report:
        compact['dependencySetup'] = report['dependencySetup']
    if 'localChecks' in report:
        compact['localChecks'] = {key: report['localChecks'].get(key) for key in ('coverage','evidenceDirectory')}
        compact['localCheckCounts'] = {status:sum(r['status']==status for r in report['localChecks']['checks']) for status in ('passed','failed','unverified','not-applicable')}
    return compact
