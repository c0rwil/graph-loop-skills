#!/usr/bin/env python3
"""Validate source/resources and isolated runtime contracts; no paid inference."""
import ast,json,os,re,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
os.environ['PYTHONDONTWRITEBYTECODE']='1'
ROOT=Path(__file__).resolve().parents[1]

def main():
    sys.path.insert(0,str(ROOT))
    from graph_loop.common import SKILLS
    actual={p.parent.name for p in (ROOT/'skills').glob('*/SKILL.md')}
    assert actual==set(SKILLS) and len(actual)==7
    for name in SKILLS:
        p=ROOT/'skills'/name/'SKILL.md';text=p.read_text();front=text.split('---',2)[1]
        assert re.search(r'^name:\s*'+name+r'\s*$',front,re.M)
        assert re.search(r'^description:\s*\S',front,re.M)
        for target in re.findall(r'\]\(([^)]+)\)',text):
            if '://' not in target:assert (p.parent/target).exists(),(p,target)
    for p in ROOT.rglob('*.py'):
        if '.git' not in p.parts:ast.parse(p.read_text(),filename=str(p))
    for p in [*ROOT.glob('graph_loop/*.py'),ROOT/'README.md',*ROOT.glob('docs/*.md')]:
        assert not re.search(r'/Users/[A-Za-z0-9_-]+|/home/[A-Za-z0-9_-]+',p.read_text()),p
    subprocess.run(['node','--check','adapters/opencode.mjs'],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,check=True)
    print('Seven skills, resource links, no hardcoded private home, Python/JS syntax and isolated contracts passed.')
if __name__=='__main__':main()
