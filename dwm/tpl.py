"""Text templates (SPEC.md ## TEMPLATES) -> new objects; place devices; build new files."""
import re, os, struct
from .model import Obj, enc_int, NEW_HEAD, dump
from .graph import GLs, items

TOK=re.compile(r'\s*(GL\[|\[|\]|\)|P\(([^,]+),([^)]+)\)|@\(([^,]+),([^)]+)\)|X([0-9a-f]{8})|"([^"]*)"|[A-Za-z][A-Za-z0-9]*\(|-?\d+|T\b|F\b|nil)')
def parse(s,ax,ay):
    toks=[]; i=0
    while i<len(s):
        if s[i].isspace(): i+=1; continue
        m=TOK.match(s,i); assert m and m.start()==i or s[i:].strip()=='' ,s[i:i+30]
        toks.append(m); i=m.end()
    pos=[0]; A=[(ax,ay)]
    def nxt(): m=toks[pos[0]]; pos[0]+=1; return m
    def peek(): return toks[pos[0]].group(1).strip()
    def pf(x,y): return struct.pack('<ff',float(x)+A[-1][0],float(y)+A[-1][1])
    def item():
        m=nxt(); g=m.group(1).strip()
        if g=='[' or g=='GL[':
            sl=Obj('TSerializeList'); sl.f=[('t',b'\x01')]
            while peek()!=']': sl.f.append(('o',item()))
            nxt(); sl.f.append(('t',b'\x00'))
            if g=='[': return sl
            gl=Obj('TGraphicList'); gl.f=[('o',sl)]; return gl
        if g.startswith('P('): p=Obj('TFloatPoint'); p.f=[('t',pf(m.group(2),m.group(3)))]; return p
        if g.endswith('('):
            o=Obj(g[:-1]); A.append((0.0,0.0) if o.cls=='TMacroPin' else A[-1])
            while peek()!=')':
                mm=toks[pos[0]]; gg=mm.group(1).strip()
                if gg.startswith('@('): nxt(); o.f.append(('t',pf(mm.group(4),mm.group(5))))
                elif gg.startswith('X'): nxt(); o.f.append(('t',bytes.fromhex(mm.group(6))))
                elif gg.startswith('"'): nxt(); b=mm.group(7).encode('latin1'); o.f.append(('t',b'\x06'+bytes([len(b)])+b))
                elif gg=='T': nxt(); o.f.append(('t',b'\x09'))
                elif gg=='F': nxt(); o.f.append(('t',b'\x08'))
                elif gg=='nil': nxt(); o.f.append(('o',None))
                elif re.fullmatch(r'-?\d+',gg): nxt(); o.f.append(('t',enc_int(int(gg))))
                else: o.f.append(('o',item()))
            nxt(); A.pop(); return o
        raise Exception(g)
    r=item(); assert pos[0]==len(toks); return r


LIST_OF = {'TTagDevice': 2, 'TClockDevice': 3, 'TBitGenerator': 3, 'TInteractiveInput': 3, 'TSupply': 3,
           'TGround': 3, 'TLEDDevice': 4, 'TLEDSegmentDevice': 4, 'TNumericDevice': 4}   # default L1
SPEC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'SPEC.md')


def library(path=SPEC):
    """{name: (anchor, template text)} from the TEMPLATES section of SPEC.md"""
    T = {}
    for line in open(path, encoding='utf-8'):
        m = re.match(r'^(\w+)\s+(pos|pin0|abs)\s*=\s*(.+)$', line.strip())
        if m: T[m.group(1)] = (m.group(2), m.group(3))
    return T


_LIB = None
def make(name, x=0.0, y=0.0):
    """new object from template `name` anchored at (x, y)"""
    global _LIB
    _LIB = _LIB or library()
    return parse(_LIB[name][1], x, y)


def _append(gl, o):
    sl = gl.objs()[0]; sl.f = sl.f[:-1] + [('o', o), sl.f[-1]]


def place(m, name, x, y):
    """create device from template and append it to the right list of canvas m"""
    d = make(name, x, y)
    _append(GLs(m)[LIST_OF.get(name, 1)], d)
    return d


def new_root():
    return make('TMacro', 0, 0)


def new_file_bytes(root): return dump(NEW_HEAD, root)
