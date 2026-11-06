"""Grid A* router (5 px grid) for one canvas: orthogonal wires that avoid device bodies,
other pins, and collinear overlap with existing wires."""
import heapq, struct
from .graph import devices, pins, center, pts, wires, GLs, items
from .model import val

G = 5
DIRS = {'R': (1, 0), 'L': (-1, 0), 'D': (0, 1), 'U': (0, -1)}


def g(v): return int(round(v / G))


def rect_of(d):
    """bounding box of a device body (macro: its symbol polygon; else pins + pos)"""
    if d.cls == 'TMacro':
        P = [p for s in d.objs()[0].objs() if s is not None and s.cls == 'TPolygon' for p in pts(s.objs()[0])]
    else:
        P = [center(p) for p in pins(d)]
        if val(d.f[0][1]) is not True:
            P.append(struct.unpack('<ff', [v for k, v in d.f if k == 't' and len(v) == 8][0]))
    if not P: return None
    xs = [p[0] for p in P]; ys = [p[1] for p in P]
    return (min(xs), min(ys), max(xs), max(ys))


class Grid:
    def __init__(self, m):
        self.m = m
        self.rects = [r for r in (rect_of(d) for d in devices(m) if d.cls not in ('TGraphicText', 'TTagDevice')) if r]
        self.occH = set(); self.occV = set(); self.nodes = set(); self.pinc = set()
        xs, ys = [], []
        for w in wires(m):
            P = pts(w.objs()[0])
            for i in range(len(P) - 1): self._mark(P[i], P[i + 1])
            for p in P: self.nodes.add((g(p[0]), g(p[1]))); xs.append(p[0]); ys.append(p[1])
        for d in devices(m):
            if d.cls == 'TGraphicText': continue
            for p in pins(d):
                c = center(p); self.pinc.add((g(c[0]), g(c[1]))); xs.append(c[0]); ys.append(c[1])
        for r in self.rects: xs += [r[0], r[2]]; ys += [r[1], r[3]]
        xs = xs or [0]; ys = ys or [0]
        self.bx = (g(min(xs)) - 12, g(max(xs)) + 12); self.by = (g(min(ys)) - 12, g(max(ys)) + 12)

    def _mark(self, a, b):
        (ax, ay), (bx, by) = (g(a[0]), g(a[1])), (g(b[0]), g(b[1]))
        if ay == by:
            for x in range(min(ax, bx), max(ax, bx) + 1): self.occH.add((x, ay))
        elif ax == bx:
            for y in range(min(ay, by), max(ay, by) + 1): self.occV.add((ax, y))

    def blocked(self, c):
        x, y = c[0] * G, c[1] * G
        return any(r[0] - 2 <= x <= r[2] + 2 and r[1] - 2 <= y <= r[3] + 2 for r in self.rects)

    def outward(self, pc):
        """direction that leaves the body owning pin center pc"""
        x, y = pc; best = None
        for r in self.rects:
            if r[0] - 6 <= x <= r[2] + 6 and r[1] - 6 <= y <= r[3] + 6:
                d = {'L': abs(x - r[0]), 'R': abs(x - r[2]), 'U': abs(y - r[1]), 'D': abs(y - r[3])}
                k = min(d, key=d.get)
                if best is None or d[k] < best[0]: best = (d[k], k)
        return best[1] if best else None

    def route(self, src, targets, first_dir=None, limit=1500000):
        """src: point; targets: {cell: allowed arrival dirs}. returns list of points or None"""
        sc = (g(src[0]), g(src[1]))
        pq = [(0, 0, sc, dn, None) for dn in DIRS if not first_dir or dn == first_dir]
        best = {}; prev = {}; cnt = 0
        tl = list(targets)[:50]
        while pq:
            _, cost, c, dn, par = heapq.heappop(pq)
            key = (c, dn)
            if key in best: continue
            best[key] = cost; prev[key] = par
            if c in targets and c != sc and dn in targets[c]:
                path = []; k = key
                while k: path.append(k[0]); k = prev[k]
                return [(x * G, y * G) for x, y in path[::-1]]
            cnt += 1
            if cnt > limit: break
            for nd, (dx, dy) in DIRS.items():
                if c == sc and nd != dn: continue
                if DIRS[nd][0] == -DIRS[dn][0] and DIRS[nd][1] == -DIRS[dn][1]: continue
                n = (c[0] + dx, c[1] + dy)
                if not (self.bx[0] <= n[0] <= self.bx[1] and self.by[0] <= n[1] <= self.by[1]): continue
                tgt = n in targets
                if self.blocked(n) and not tgt: continue
                horiz = dy == 0; pen = 0
                if not tgt:
                    if n in self.pinc: continue
                    if (horiz and n in self.occH) or (not horiz and n in self.occV): pen += 40
                    if n in self.nodes: pen += 25
                cross = 3 if (horiz and n in self.occV) or (not horiz and n in self.occH) else 0
                nc = cost + 1 + pen + cross + (4 if nd != dn else 0)
                h = min(abs(n[0] - t[0]) + abs(n[1] - t[1]) for t in tl)
                heapq.heappush(pq, (nc + h, nc, n, nd, key))
        return None


def simplify(P):
    R = [P[0]]
    for i in range(1, len(P) - 1):
        a, b, c = R[-1], P[i], P[i + 1]
        if (a[0] == b[0] == c[0]) or (a[1] == b[1] == c[1]): continue
        R.append(b)
    R.append(P[-1]); return R


def snap_ends(path, src, dst):
    """grid path -> path whose first/last runs pass exactly through src/dst (stays orthogonal)"""
    P = [list(p) for p in path]
    def fix(P, pt):
        if len(P) >= 2:
            c = 0 if P[0][0] == P[1][0] else 1      # coordinate shared by the first run
            k = 1
            while k < len(P) and P[k][c] == P[0][c]: k += 1
            for i in range(k): P[i][c] = pt[c]
        P[0] = [pt[0], pt[1]]
        return P
    P = fix(P, src)
    P = fix(P[::-1], dst)[::-1]
    return [tuple(p) for p in P]
