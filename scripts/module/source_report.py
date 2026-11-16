"""Detailed pipeline reporting and agent handoff; never asks or uploads itself."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from skzip import SERVER_PENDING


def start_report(directories, output):
    return {'status': 'running', 'inputs': [str(Path(p).expanduser().absolute()) for p in directories],
            'output': str(output) if output is not None else None,
            'outputCreated': False, 'serverPending': list(SERVER_PENDING),
            'startedAt': datetime.now(timezone.utc).isoformat(),
            'stages': [], 'issues': {'serious': [], 'warnings': []}, 'coverage': {
                'sourceChecks': False, 'skzipIntegrity': False, 'realBuild': False,
                'rendering': False, 'securityReview': False, 'productionUpload': False}}


def record_stage(report, name, started, status, **details):
    report['stages'].append({'name': name, 'status': status,
                            'elapsedSeconds': round(time.monotonic() - started, 3), **details})


def finish_report(report, started, status):
    """Separate upload eligibility from the user's decision to actually upload."""
    serious, warnings = report['issues']['serious'], report['issues']['warnings']
    report.update(status=status, elapsedSeconds=round(time.monotonic() - started, 3),
                  seriousErrorCount=len(serious), warningCount=len(warnings),
                  warnings=warnings,
                  uploadEligible=bool(report['outputCreated'] and not serious and report['coverage']['skzipIntegrity']),
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
        'seriousErrorCount', 'warningCount', 'elapsedSeconds', 'uploadEligible')}
    if report['output'] is None:
        report['reportPath'] = None
        return report
    destination = Path(report['output']).with_suffix('.report.json')
    report['reportPath'] = str(destination)
    try:
        with destination.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
    except OSError as error:
        report['reportPath'] = None
        report['reportWriteWarning'] = str(error)
    return report
