"""Pure Python entry: python simulate.py [--scene scene.py] [--open-report]."""
import argparse
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'/'Agamemnon.Optics'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene',type=Path,default=ROOT/'src'/'Agamemnon.Optics'/'scene_example.py')
    parser.add_argument('--parameters',type=Path,help='Optional JSON overrides; ordinary use edits PARAMETERS in scene.py')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--open-report',action='store_true')
    parser.add_argument('--test',action='store_true')
    args=parser.parse_args()
    if args.test:
        suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_optics*.py')
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    from run_bpm import main as run
    forwarded=['--scene',str(args.scene)]
    if args.parameters: forwarded+=['--config',str(args.parameters)]
    if args.output: forwarded+=['--output',str(args.output)]
    if args.open_report: forwarded+=['--open-report']
    return run(forwarded)


if __name__=='__main__':
    import json
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    try: sys.exit(main())
    except (ValueError,TypeError,KeyError,IndexError,OSError,ImportError,SyntaxError,AttributeError) as error:
        print(json.dumps(dict(status='error',error=str(error)),ensure_ascii=False),file=sys.stderr)
        sys.exit(1)
