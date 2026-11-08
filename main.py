"""GUI and isolated local-import worker entry point."""
import argparse,sys,traceback
from paths import data_dir

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir');parser.add_argument('--worker',choices=['scan','import'])
    parser.add_argument('--game');parser.add_argument('--pet-id',type=int);parser.add_argument('--job-log')
    parser.add_argument('--check',action='store_true',help='Save a local startup diagnostic and exit')
    args=parser.parse_args();data=data_dir(args.data_dir)
    if args.worker:
        if args.job_log:sys.stdout=sys.stderr=open(args.job_log,'w',encoding='utf-8',buffering=1)
        try:
            from importer import scan,import_pet
            if args.worker=='scan':scan(args.game,data)
            else:import_pet(args.game,data,args.pet_id)
            return 0
        except Exception:
            traceback.print_exc();return 1
    if sys.stdout is None:sys.stdout=sys.stderr=(data/'runtime.log').open('a',encoding='utf-8',buffering=1)
    from desktop_pet import run
    return run(data,check=args.check)

if __name__=='__main__':sys.exit(main())
