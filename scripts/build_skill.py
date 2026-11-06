"""Build dist/digital-works-dwm.zip (skill + bundled kit) and refresh .claude/skills copy.
run from repo root:  python scripts/build_skill.py"""
import os, zipfile, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = 'digital-works-dwm'
FILES = ['SPEC.md', 'README.md']
DIRS = ['dwm', 'tests', 'examples']


def bundle():
    out = os.path.join(ROOT, 'dist', NAME + '.zip')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(ROOT, 'skill', 'SKILL.md'), NAME + '/SKILL.md')
        for f in FILES: z.write(os.path.join(ROOT, f), NAME + '/' + f)
        for d in DIRS:
            for base, _, names in os.walk(os.path.join(ROOT, d)):
                if '__pycache__' in base: continue
                for n in sorted(names):
                    if n.endswith('.pyc'): continue
                    p = os.path.join(base, n)
                    z.write(p, NAME + '/' + os.path.relpath(p, ROOT).replace(os.sep, '/'))
    return out


def claude_code_copy():
    dst = os.path.join(ROOT, '.claude', 'skills', NAME)
    os.makedirs(dst, exist_ok=True)
    shutil.copy(os.path.join(ROOT, 'skill', 'SKILL.md'), os.path.join(dst, 'SKILL.md'))


if __name__ == '__main__':
    print('built', bundle()); claude_code_copy(); print('updated .claude/skills/' + NAME)
