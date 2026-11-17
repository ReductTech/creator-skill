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
                  uploadAuthorized=False, requiresUserConfirmation=True)
    if serious:
        report['agentNextAction'] = 'discuss-errors-and-repair-before-repacking'
        report['userOptions'] = ['discuss-and-fix']
        report['userPrompt'] = '发现严重错误，请先与用户确认修复方案；修复并重新打包后，再确认是否上传。'
    elif warnings:
        report['agentNextAction'] = 'offer-repair-and-repack-or-confirm-current-upload'
        report['userOptions'] = ['fix-and-repack', 'upload-current-package']
        report['userPrompt'] = '是否先修复这些提醒再重新打包，还是接受当前状态并上传这个包？'
    else:
        report['agentNextAction'] = 'confirm-upload'
        report['userOptions'] = ['upload-current-package']
        report['userPrompt'] = '源码包已生成，是否确认上传？'
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
