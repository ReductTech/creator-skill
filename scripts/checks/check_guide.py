"""Check a built Guide entry in an isolated browser; never modifies author source."""
import argparse
import json
from pathlib import Path
import sys

sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'common')]
from _common import resolve_module, emit_result, report_error
from media.capture_slides import browser_session, built_entry


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module',required=True)
    parser.add_argument('--build-output',required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        directory,doc=resolve_module(args.module)
        output=directory/'_scratchpad/screenshots/guide.png'
        output.parent.mkdir(parents=True,exist_ok=True)
        with browser_session(build_output=args.build_output.resolve()) as (context,url):
            page=context.new_page();errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            entry=built_entry(url,doc['id'])
            if not entry:raise ValueError('Current Guide build manifest is unavailable')
            page.goto(entry+'?mode=guide',wait_until='networkidle',timeout=60000)
            page.wait_for_function("document.querySelector('#root')?.children.length>0",timeout=15000)
            text=page.locator('#root').inner_text()
            page.screenshot(path=str(output),full_page=True)
            ids=page.locator('[data-step-id]').evaluate_all('elements=>elements.map(el=>el.dataset.stepId)')
            if not text.strip() and not page.locator('#root canvas,#root svg,#root img').count():
                errors.append('Guide has no visible text or visual content')
            page.close()
        emit_result({'errors':errors,'screenshot':str(output),'guideIds':ids,
                     'coverage':'Guide landing render and runtime errors; scrolling completion and course-specific interactions remain unverified.'},
                    status='failed' if errors else 'passed')
        return 1 if errors else 0
    except (OSError,RuntimeError,ValueError,ImportError) as error:
        return report_error(error)


if __name__=='__main__':raise SystemExit(main())
