"""Editing primitives that keep the SPEC invariants (pin.wire, solder wires, L5/L6 lists)."""
import struct
from .model import Obj
from .graph import GLs, items, pts, center, wire_ends
from . import router as RT

DEFAULT_WIRE = [('t', b'\x02\x00'), ('t', b'\x02\x01'), None, ('t', b'\x02\x00')]


class Canvas:
    """one macro canvas: owns its L5 (solders) and L6 (wires)"""
    def __init__(self, m):
        self.m = m; g = GLs(m); self.solGL = g[5]; self.wireGL = g[6]

    def _set(self, gl, objs): gl.objs()[0].f = [('t', b'\x01')] + [('o', o) for o in objs] + [('t', b'\x00')]
    def wires(self): return items(self.wireGL)
    def solders(self): return items(self.solGL)

    def add(self, o):
        if o.cls == 'TWire': self._set(self.wireGL, self.wires() + [o])
        else: self._set(self.solGL, self.solders() + [o])

    def rm(self, o):
        if o.cls == 'TWire': self._set(self.wireGL, [w for w in self.wires() if w is not o])
        else: self._set(self.solGL, [s for s in self.solders() if s is not o])


def point(x, y):
    o = Obj('TFloatPoint'); o.f = [('t', struct.pack('<ff', x, y))]; return o


def mkwire(A, B, P, like=None):
    """new TWire A->B through points P (duplicates and collinear points removed)"""
    f = like.f if like is not None else DEFAULT_WIRE
    Q = [P[0]] + [p for i, p in enumerate(P[1:]) if p != P[i]]
    R = [Q[0]]
    for i in range(1, len(Q) - 1):
        a, b, c = R[-1], Q[i], Q[i + 1]
        if not ((a[0] == b[0] == c[0]) or (a[1] == b[1] == c[1])): R.append(b)
    R.append(Q[-1])
    w = Obj('TWire'); sl = Obj('TSerializeList')
    sl.f = [('t', b'\x01')] + [('o', point(*p)) for p in R] + [('t', b'\x00')]
    w.f = [f[0], f[1], ('o', sl), f[3], ('o', A), ('o', B)]
    return w


def wire_pts(w): return pts(w.f[2][1])
def set_pin_wire(p, w): p.f[5] = ('o', w)
def solder_pos(s): return struct.unpack('<ff', s.f[0][1])


def _replace_ref(o, old, new):
    o.f = [(k, (new if (k == 'o' and x is old) else x)) for k, x in o.f]


def disconnect(cv, pin):
    """remove the wire on pin; a solder left with 2 wires is merged into one wire"""
    w = pin.objs()[1]
    if w is None: return
    a, b = wire_ends(w); other = b if a is pin else a
    set_pin_wire(pin, None); cv.rm(w)
    if other.cls in ('TPin', 'TMacroPin'): set_pin_wire(other, None); return
    S = other; live = [x for x in S.objs() if x is not w]
    assert len(live) == 2
    wa, wb = live
    A = [e for e in wire_ends(wa) if e is not S][0]; B = [e for e in wire_ends(wb) if e is not S][0]
    Pa = wire_pts(wa); Pa = Pa if wire_ends(wa)[1] is S else Pa[::-1]
    Pb = wire_pts(wb); Pb = Pb if wire_ends(wb)[0] is S else Pb[::-1]
    nw = mkwire(A, B, Pa + Pb[1:], wa)
    for e, old in ((A, wa), (B, wb)):
        if e.cls == 'TSolder': _replace_ref(e, old, nw)
        else: set_pin_wire(e, nw)
    cv.rm(wa); cv.rm(wb); cv.rm(S); cv.add(nw)


def connect_pins(cv, p1, p2):
    """route a new wire p1 -> p2 (L-shape fallback if the router finds nothing)"""
    grid = RT.Grid(cv.m)
    c1, c2 = center(p1), center(p2)
    o2 = grid.outward(c2); opp = {'L': 'R', 'R': 'L', 'U': 'D', 'D': 'U'}
    tg = {(RT.g(c2[0]), RT.g(c2[1])): {opp[o2]} if o2 else set('LRUD')}
    grid.pinc.discard((RT.g(c2[0]), RT.g(c2[1])))
    path = grid.route(c1, tg, grid.outward(c1))
    if path is None:
        path = [c1, (c1[0], (c1[1] + c2[1]) / 2), (c2[0], (c1[1] + c2[1]) / 2), c2]
    else:
        path = RT.simplify(RT.snap_ends(path, c1, c2))
    w = mkwire(p1, p2, path); set_pin_wire(p1, w); set_pin_wire(p2, w); cv.add(w)
    return w


def _seg_cells(w):
    P = wire_pts(w); out = {}
    for i in range(len(P) - 1):
        (x0, y0), (x1, y1) = P[i], P[i + 1]
        if x0 == x1:
            lo, hi = sorted((y0, y1))
            for y in range(RT.g(lo) + 1, RT.g(hi)): out[(RT.g(x0), y)] = (i, {'L', 'R'})
        elif y0 == y1:
            lo, hi = sorted((x0, x1))
            for x in range(RT.g(lo) + 1, RT.g(hi)): out[(x, RT.g(y0))] = (i, {'U', 'D'})
    return out


def connect_to_net(cv, pin, net_wires):
    """tap the nearest reachable segment of net_wires with a new solder and wire it to pin"""
    grid = RT.Grid(cv.m); tg = {}; owner = {}
    for w in net_wires:
        for c, (i, dirs) in _seg_cells(w).items():
            if c in grid.nodes: continue
            tg[c] = dirs; owner[c] = (w, i)
    pc = center(pin)
    path = grid.route(pc, tg, grid.outward(pc)) if tg else None
    if path is None: raise RuntimeError('no route from pin to net (add space or route by hand)')
    w, i = owner[(RT.g(path[-1][0]), RT.g(path[-1][1]))]
    P = wire_pts(w); A, B = wire_ends(w)
    (x0, y0), (x1, y1) = P[i], P[i + 1]
    tx, ty = (x0, path[-1][1]) if x0 == x1 else (path[-1][0], y0)
    path = RT.simplify(RT.snap_ends(path, pc, (tx, ty)))
    S = Obj('TSolder')
    wa = mkwire(A, S, P[:i + 1] + [(tx, ty)], w); wb = mkwire(S, B, [(tx, ty)] + P[i + 1:], w)
    wc = mkwire(S, pin, path[::-1], w)
    S.f = [('t', struct.pack('<ff', tx, ty)), ('o', wa), ('o', wb), ('o', wc)]
    for e, nw in ((A, wa), (B, wb)):
        if e.cls == 'TSolder': _replace_ref(e, w, nw)
        else: set_pin_wire(e, nw)
    set_pin_wire(pin, wc)
    cv.rm(w); cv.add(wa); cv.add(wb); cv.add(wc); cv.add(S)
    return S


def connect(cv, pin, target):
    """connect pin to target pin: direct wire if target is free, else tap target's net"""
    if target.objs()[1] is None: return connect_pins(cv, pin, target)
    from .graph import canvas_nets
    f = canvas_nets(cv.m); n = f(target)
    return connect_to_net(cv, pin, [w for w in cv.wires() if f(wire_ends(w)[0]) == n])
