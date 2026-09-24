"""Check a supplied self-contained case: python -m refcert check CASE.json."""
import argparse,json,sys
from pathlib import Path
from .checker import verify,Rejected

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['check']);parser.add_argument('case',type=Path)
    args=parser.parse_args()
    try:
        if args.case.stat().st_size>8*1024**2:raise Rejected('case file exceeds 8 MiB input limit')
        data=json.loads(args.case.read_text(encoding='utf-8'))
        verdict=verify(data['program'],data['certificate'],data['budget_cells'])
    except (OSError,ValueError,TypeError,KeyError,IndexError) as error:
        print(json.dumps({'accepted':False,'reason':str(error)}));return 2
    print(json.dumps({'accepted':True,**verdict},indent=2));return 0
if __name__=='__main__':sys.exit(main())
