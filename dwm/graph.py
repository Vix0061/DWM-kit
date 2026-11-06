"""Navigation helpers over the object graph + macro flattening into one netlist."""
import struct
from .model import Obj, val


def pts(serial_list):
    return [struct.unpack('<ff', p.f[0][1]) for p in serial_list.objs()]


def items(gl):
    """objects inside a TGraphicList"""
    return gl.objs()[0].objs()


def GLs(m):
    """the TGraphicLists of a device/macro, in field order (macro: [ext pins, L1..L6])"""
    return [x for x in m.objs() if x is not None and x.cls == 'TGraphicList']


def devices(m):
    """L1..L4 of a macro canvas (logic, tags, sources, outputs)"""
    g = GLs(m)
    return [x for gl in g[1:5] for x in items(gl)]


def wires(m): return items(GLs(m)[6])
def solders(m): return items(GLs(m)[5])


def pins(dev):
    if dev.cls == 'TMacro': return items(GLs(dev)[0])
    return items(GLs(dev)[0])


def center(pin):
    P = pts(pin.objs()[0])
    return (sum(x for x, _ in P) / len(P), sum(y for _, y in P) / len(P))


def pin_dir(pin): return val(pin.f[4][1])
def pin_wire(pin): return pin.objs()[1]
def wire_ends(w): return w.objs()[1], w.objs()[2]


def text(g):
    """string of a TGraphicText"""
    return [val(t) for k, t in g.f if k == 't' and t[0] == 6][0]


def tag_label(tag):
    s = tag.objs()[0]
    return text(s.objs()[0]) if s is not None and s.objs() else ''


def macro_title(m):
    T = [text(g) for g in m.objs()[0].objs() if g is not None and g.cls == 'TGraphicText']
    return T[0] if T else ''


def symbol_texts(m):
    return [text(g) for g in m.objs()[0].objs() if g is not None and g.cls == 'TGraphicText']


def ext_pins(m):
    """{tag label: ext TMacroPin} of a macro instance"""
    lab = {id(d.objs()[-1]): tag_label(d) for d in devices(m) if d.cls == 'TTagDevice'}
    return {lab[id(e.objs()[-1])]: e for e in items(GLs(m)[0])}


def pos(dev):
    """device position (only devices without custom shape)"""
    raw = [v for k, v in dev.f if k == 't' and len(v) == 8]
    return struct.unpack('<ff', raw[0]) if raw else None


def walk_macros(root):
    """yield (macro, path) for every canvas, root first"""
    st = [(root, 'root')]; seen = set()
    while st:
        m, p = st.pop()
        if id(m) in seen: continue
        seen.add(id(m)); yield m, p
        for d in devices(m):
            if d.cls == 'TMacro': st.append((d, p + '/' + macro_title(d)))


class Flat:
    """Flatten a macro (and everything nested) into devices + nets.
    net(pin) -> net id. Ext pins of nested macros are joined to their inner tag pins."""

    def __init__(self, m):
        self.uf = {}; self.devs = []; self.tagpin = {}
        self._walk(m)
        for e in items(GLs(m)[0]):          # ext pins of m itself (if instance)
            self._u(e, self.tagpin[id(e.objs()[-1])])

    def _f(self, a):
        self.uf.setdefault(a, a)
        while self.uf[a] != a:
            self.uf[a] = self.uf[self.uf[a]]; a = self.uf[a]
        return a

    def _u(self, a, b): self.uf[self._f(id(a))] = self._f(id(b))

    def _walk(self, m):
        for w in wires(m): self._u(*wire_ends(w))
        for d in devices(m):
            if d.cls == 'TMacro':
                self._walk(d)
                for e in items(GLs(d)[0]): self._u(e, self.tagpin[id(e.objs()[-1])])
            elif d.cls == 'TTagDevice':
                self.tagpin[id(d.objs()[-1])] = pins(d)[0]
            elif d.cls != 'TGraphicText':
                self.devs.append(d)

    def net(self, pin): return self._f(id(pin))


def canvas_nets(m):
    """union-find over ONE canvas (no flattening): returns find(obj)->id"""
    uf = {}
    def f(a):
        uf.setdefault(a, a)
        while uf[a] != a: a = uf[a]
        return a
    for w in wires(m):
        a, b = wire_ends(w); uf[f(id(a))] = f(id(b))
    return lambda o: f(id(o))
