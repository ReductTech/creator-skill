"""Optional installed Shuku computation; help never imports models or the platform."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'common'))
from _common import project_path,report_error
TOOLS=('gradcam-face','gradcam-celebrity','gradcam-pretrained','emnist-train')

def build_parser():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tool',choices=TOOLS)
    parser.add_argument('--config',type=Path)
    parser.add_argument('--asset-root',type=Path,help='Exported assets, grouped under the stable course UUID')
    parser.add_argument('--data-root',type=Path,help='Dataset root (EMNIST uses its emnist subdirectory)')
    parser.add_argument('--model-root',type=Path)
    parser.add_argument('--plan',action='store_true',help='Show paths and dependencies without downloading, training or writing')
    parser.add_argument('--epochs',type=int,default=10)
    parser.add_argument('--batch-size',type=int,default=128)
    parser.add_argument('--learning-rate',type=float,default=1e-3)
    parser.add_argument('--num-workers',type=int,default=0)
    return parser

def main(argv=None):
    parser=build_parser()
    args=parser.parse_args(argv)
    if args.asset_root is None:
        parser.error('Pass --asset-root inside targetRoot; installed platform defaults cannot override the independent target')
    try:
        assets=project_path(args.asset_root)
        forwarded=list(sys.argv[1:] if argv is None else argv)
        for option in ('--asset-root','--config','--data-root','--model-root'):
            for index,value in enumerate(forwarded):
                if value == option:
                    forwarded[index+1]=str(assets if option=='--asset-root' else project_path(forwarded[index+1],external=True))
                elif value.startswith(option+'='):
                    forwarded[index]=option+'='+str(assets if option=='--asset-root' else project_path(value.split('=',1)[1],external=True))
        from shuku_compute.tools.__main__ import main as compute_main
        return compute_main(forwarded)
    except ImportError:
        return report_error(ValueError('Install the Shuku backend[authoring-compute] package to use this optional tool'))
    except (OSError,ValueError) as error:
        return report_error(error)

if __name__=='__main__':raise SystemExit(main())
