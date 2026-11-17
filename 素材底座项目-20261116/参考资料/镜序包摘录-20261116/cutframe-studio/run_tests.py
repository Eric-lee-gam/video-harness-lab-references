# -*- coding: utf-8 -*-
"""所有自动化检查均使用临时台账，避免触碰正在运行的工程。"""
import os,json,tempfile,unittest,sys
from pathlib import Path
base=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='cutframe-test-') as folder:
    state=Path(folder);cfg=json.loads((base.parent/'local/cutframe/config.json').read_text('utf-8-sig'))
    cfg['output']=str(state/'outputs');cfg['roots']={};(state/'config.json').write_text(json.dumps(cfg),'utf-8')
    os.environ['CUTFRAME_STATE']=folder
    sys.path.insert(0,str(base))
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(base),pattern='test_*.py'))
    sys.exit(not result.wasSuccessful())
