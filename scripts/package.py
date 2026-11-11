#!/usr/bin/env python3
"""Reproducible distribution; state/auth/graphs and unrelated skills are excluded."""
import hashlib,zipfile,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DIRS=('graph_loop','adapters','skills','workers','prompts','docs','licenses','tests','scripts','specs','evidence')
FILES=('gl.py','AGENTS.md','README.md','LICENSE','NOTICE','provenance.json','requirements.txt','.gitignore')

def main():
    actual={p.parent.name for p in (ROOT/'skills').glob('*/SKILL.md')}
    assert actual=={'graphify','graph-loop','ponytail','ponytail-review','shunt','bulk-reader','code-writer'}
    files=[ROOT/n for n in FILES]+[p for d in DIRS for p in (ROOT/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
    output=Path(os.environ.get('GRAPH_LOOP_STATE_DIR',str(Path.home()/'.local/state/graph-loop')))/'distributions/graph-loop-skills-2.0.0.zip';output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(files):
            assert not p.is_symlink(),p
            info=zipfile.ZipInfo('graph-loop-skills/'+p.relative_to(ROOT).as_posix(),(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=(p.stat().st_mode&0o777)<<16
            archive.writestr(info,p.read_bytes())
    digest=hashlib.sha256(output.read_bytes()).hexdigest();output.with_suffix('.zip.sha256').write_text(digest+'  '+output.name+'\n');print(output);print(digest)
if __name__=='__main__':main()
