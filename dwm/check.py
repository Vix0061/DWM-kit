"""Structural checks (SPEC.md TESTS T1, T3, T5).  CLI: python -m dwm.check file.dwm [...]"""
import sys, collections
from .model import load, dump
from .graph import walk_macros, wires, solders, devices, pins, center, wire_ends, pin_dir, GLs, items, pts
from .edit import wire_pts, solder_pos
from .router import rect_of


def roundtrip(data):
    h, r, _ = load(data); return dump(h, r) == data


def invariants(root):
    """pin<->wire and solder<->wire back-references; every wire/solder listed on its canvas"""
    bad = []
    for m, path in walk_macros(root):
        W = set(map(id, wires(m)))
        for w in wires(m):
            for e in wire_ends(w):
                if e is None: bad.append((path, 'wire end nil')); continue
                if e.cls == 'TSolder':
                    if w not in e.objs(): bad.append((path, 'solder misses wire'))
                elif e.objs()[1] is not w: bad.append((path, 'pin.wire mismatch'))
        for s in solders(m):
            ws = s.objs()
            if len(ws) != 3 or len(set(map(id, ws))) != 3: bad.append((path, 'solder needs 3 distinct wires'))
            if any(id(w) not in W for w in ws): bad.append((path, 'solder wire not in canvas list'))
    return bad


def geometry(root):
    """wire ends at pin centers / solder positions; orthogonal; not over macro chip bodies"""
    bad = collections.Counter()
    for m, path in walk_macros(root):
        chips = [rect_of(d) for d in devices(m) if d.cls == 'TMacro']
        for w in wires(m):
            P = wire_pts(w)
            for e, pt in zip(wire_ends(w), (P[0], P[-1])):
                c = solder_pos(e) if e.cls == 'TSolder' else center(e)
                if abs(c[0] - pt[0]) > .6 or abs(c[1] - pt[1]) > .6: bad['end off pin'] += 1
            for a, b in zip(P, P[1:]):
                if a[0] != b[0] and a[1] != b[1]: bad['diagonal segment'] += 1
                for r in chips:
                    if r and _hits(a, b, r): bad['wire over chip'] += 1
    return dict(bad)


def _hits(a, b, R, m=2):
    x0, y0, x1, y1 = R[0] + m, R[1] + m, R[2] - m, R[3] - m
    if x0 >= x1 or y0 >= y1: return False
    if a[0] == b[0]: return x0 < a[0] < x1 and max(min(a[1], b[1]), y0) < min(max(a[1], b[1]), y1)
    if a[1] == b[1]: return y0 < a[1] < y1 and max(min(a[0], b[0]), x0) < min(max(a[0], b[0]), x1)
    return False


def undriven(root):
    """flattened nets that have loads but no driver (usually a broken connection)"""
    from .graph import Flat
    fl = Flat(root); drv = set(); load_ = collections.Counter()
    for d in fl.devs:
        P = pins(d)
        for i, p in enumerate(P):
            n = fl.net(p); dr = pin_dir(p)
            if d.cls == 'TTriState': dr = 2 if i == 1 else 1
            if dr in (2, 3): drv.add(n)
            elif dr == 1 and p.objs()[1] is not None: load_[n] += 1
    return [n for n in load_ if n not in drv]


def report(path):
    data = open(path, 'rb').read()
    h, root, _ = load(data)
    out = {'roundtrip': roundtrip(data), 'invariants': invariants(root)[:10],
           'geometry': geometry(root), 'undriven_nets': len(undriven(root))}
    return out


if __name__ == '__main__':
    for f in sys.argv[1:]:
        print(f, report(f))
