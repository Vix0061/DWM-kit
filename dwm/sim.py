"""Netlist simulators for flattened .dwm circuits.

UnitSim        : every gate/FF has delay 1 step. Fast; good first check.
RandomDelaySim : every device gets a random delay 1..dmax (transport). This is the
                 model that reproduces real Digital Works glitches. A design is only
                 accepted when it passes many seeds (see SPEC.md TIMING).

Semantics (SPEC.md): JK/D clock on FALLING edge; CLR/PRE active-high async, dominate
clock; unconnected input = 0; tristate passes when enable=1 (else drives 0).
"""
import collections, random
from .graph import pins, Flat

GATES = {'And': all, 'Or': any,
         'Nand': lambda v: not all(v), 'Nor': lambda v: not any(v),
         'Xor': lambda v: sum(v) % 2 == 1, 'Xnor': lambda v: sum(v) % 2 == 0}
FF = ('TJKFlipFlop', 'TDFlipFlop', 'TRSFlipFlop')


def gate_fn(cls):
    if cls[1].isdigit() and cls.endswith('Gate'):
        for k, fn in GATES.items():
            if cls[2:-4] == k: return fn
    return None


def comb(dev, P, rd):
    """combinational output(s) of dev as [(net, value)]; rd(net, dev) reads an input"""
    c = dev.cls
    fn = gate_fn(c)
    if fn: return [(P[0], int(fn([rd(p) for p in P[1:]])))]
    if c == 'TNotGate': return [(P[0], 1 - rd(P[1]))]
    if c == 'TTriState': return [(P[1], rd(P[0]) if rd(P[2]) else 0)]
    if c == 'TSupply': return [(P[0], 1)]
    if c == 'TGround': return [(P[0], 0)]
    return []


def ff_next(dev, P, q, clr, pre, edge, ins):
    c = dev.cls
    if c == 'TRSFlipFlop':
        s, r = ins
        return 1 if s and not r else (0 if r and not s else q)
    if clr: return 0
    if pre: return 1
    if not edge: return q
    if c == 'TDFlipFlop': return ins[0]
    J, K = ins
    return {(0, 0): q, (0, 1): 0, (1, 0): 1, (1, 1): 1 - q}[(J, K)]


def ff_inputs(dev, P):
    """(clk, clr, pre, data nets) per FF type"""
    c = dev.cls
    if c == 'TJKFlipFlop': return P[3], P[4], P[5], (P[2], P[6])
    if c == 'TDFlipFlop': return P[3], P[4], P[5], (P[2],)
    return None, None, None, (P[2], P[3])


class _Base:
    def __init__(self, flat, drive=None):
        self.fl = flat
        self.P = {id(d): [flat.net(p) for p in pins(d)] for d in flat.devs}
        self.ff = [d for d in flat.devs if d.cls in FF]
        self.q = {id(d): 0 for d in self.ff}
        self.drive = dict(drive or {})

    def set(self, net, v): self.drive[net] = v
    def net(self, pin): return self.fl.net(pin)


class UnitSim(_Base):
    def __init__(self, flat, drive=None):
        super().__init__(flat, drive)
        self.v = collections.defaultdict(int); self.prevclk = {}; self.previn = {}
        self.settle(400)

    def step(self):
        v = self.v; nv = collections.defaultdict(int)
        for d in self.fl.devs:
            for n, x in comb(d, self.P[id(d)], lambda p: v[p]): nv[n] = x
        for d in self.ff:
            P = self.P[id(d)]; clk, clr, pre, data = ff_inputs(d, P)
            edge = clk is not None and self.prevclk.get(id(d), 0) == 1 and v[clk] == 0
            ins = self.previn.get(id(d), tuple(0 for _ in data)) if d.cls != 'TRSFlipFlop' else tuple(v[x] for x in data)
            self.q[id(d)] = ff_next(d, P, self.q[id(d)], clr is not None and v[clr], pre is not None and v[pre], edge, ins)
        self.prevclk = {id(d): v[ff_inputs(d, self.P[id(d)])[0]] for d in self.ff if ff_inputs(d, self.P[id(d)])[0] is not None}
        self.previn = {id(d): tuple(v[x] for x in ff_inputs(d, self.P[id(d)])[3]) for d in self.ff}
        for d in self.ff:
            P = self.P[id(d)]; nv[P[0]] = self.q[id(d)]; nv[P[1]] = 1 - self.q[id(d)]
        for n, x in self.drive.items(): nv[n] = x
        nz = lambda dd: {k: x for k, x in dd.items() if x}
        changed = nz(nv) != nz(v); self.v = nv
        return changed

    def settle(self, limit=400):
        quiet = 0
        for _ in range(limit):
            quiet = 0 if self.step() else quiet + 1
            if quiet > 3: return
        raise RuntimeError('circuit does not settle (oscillation?)')

    def pulse(self, clk_net):
        """one full clock cycle: high then low (counters advance on the falling edge)"""
        self.drive[clk_net] = 1; self.settle(); self.drive[clk_net] = 0; self.settle()

    def value(self, pin): return self.v[self.fl.net(pin)]


class RandomDelaySim(_Base):
    def __init__(self, flat, drive=None, seed=0, dmax=3, ffmax=3, hist=8):
        super().__init__(flat, drive)
        rnd = random.Random(seed)
        self.dl = {id(d): rnd.randint(1, ffmax if d.cls in FF else dmax) for d in flat.devs}
        self.H = collections.deque([{}] * hist, maxlen=hist)
        self.pipe = {id(d): collections.deque([0] * hist, maxlen=hist) for d in self.ff}
        self.prevclk = {}; self.v = {}

    def past(self, k, n): return self.H[k - 1].get(n, 0)

    def step(self):
        nv = {}
        for d in self.fl.devs:
            k = self.dl[id(d)]
            for n, x in comb(d, self.P[id(d)], lambda p: self.past(k, p)): nv[n] = x
        for d in self.ff:
            P = self.P[id(d)]; clk, clr, pre, data = ff_inputs(d, P)
            now = self.past(1, clk) if clk is not None else 0
            edge = clk is not None and self.prevclk.get(id(d), 0) == 1 and now == 0
            ins = tuple(self.past(2 if d.cls != 'TRSFlipFlop' else 1, x) for x in data)
            self.q[id(d)] = ff_next(d, P, self.q[id(d)], clr is not None and self.past(1, clr),
                                    pre is not None and self.past(1, pre), edge, ins)
            self.prevclk[id(d)] = now
            self.pipe[id(d)].appendleft(self.q[id(d)])
            out = self.pipe[id(d)][self.dl[id(d)] - 1]
            nv[P[0]] = out; nv[P[1]] = 1 - out
        nv.update(self.drive)
        self.v = nv; self.H.appendleft(nv)

    def run(self, steps):
        for _ in range(steps): self.step()

    def value(self, pin): return self.v.get(self.fl.net(pin), 0)


def run_clocked(sim, clk_net, ticks, half=60, sample=None):
    """drive a square clock on a RandomDelaySim; sample(sim) is called at the end of each period"""
    out = []
    for _ in range(ticks):
        sim.set(clk_net, 1); sim.run(half)
        sim.set(clk_net, 0); sim.run(half)
        if sample: out.append(sample(sim))
    return out
