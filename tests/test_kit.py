"""run: python -m tests.test_kit   (from the repo root)"""
import os, sys
sys.setrecursionlimit(100000)
from dwm import model, tpl, graph, edit, sim, check
HERE = os.path.dirname(os.path.abspath(__file__)); EX = os.path.join(HERE, '..', 'examples', 'general_components.dwm')


def t1_roundtrip():
    d = open(EX, 'rb').read()
    assert check.roundtrip(d)


def t2_templates_rebuild_components():
    """SPEC T2: root + every template at its anchor == general_components.dwm byte-exact"""
    L = {1: [('T2OrGate', 370, 165), ('T2NorGate', 370, 225), ('T2XorGate', 480, 160), ('T2XnorGate', 480, 215),
             ('TNotGate', 570, 160), ('T2AndGate', 700, 160), ('T2NandGate', 700, 210), ('TRSFlipFlop', 815, 150),
             ('TJKFlipFlop', 820, 210), ('TDFlipFlop', 950, 150), ('TInteractiveSwitch', 1170, 235)],
         2: [('TTagDevice', 970, 240)],
         3: [('TBitGenerator', 1110, 175), ('TClockDevice', 1085, 235), ('TInteractiveInput', 1175, 170),
             ('TGround', 1240, 230), ('TSupply', 1245, 170)],
         4: [('TLEDDevice', 1315, 175), ('TLEDSegmentDevice', 1535, 215), ('TNumericDevice', 1335, 220)]}
    root = tpl.new_root()
    for li, devs in L.items():
        for name, x, y in devs:
            tpl._append(graph.GLs(root)[li], tpl.make(name, x, y))
    want = open(EX, 'rb').read()
    head = model.load(want)[0]
    assert model.dump(head, root) == want


def t3_build_and_simulate_counter():
    """generate a 2-bit ripple counter (clock -> JK0 -> JK1), check it, simulate it"""
    root = tpl.new_root(); cv = edit.Canvas(root)
    clk = tpl.place(root, 'TClockDevice', 100, 100)
    vcc = tpl.place(root, 'TSupply', 100, 200)
    j0 = tpl.place(root, 'TJKFlipFlop', 250, 100)
    j1 = tpl.place(root, 'TJKFlipFlop', 400, 100)
    P0, P1 = graph.pins(j0), graph.pins(j1)
    edit.connect(cv, P0[3], graph.pins(clk)[0])            # CLK0 <- clock
    edit.connect(cv, P1[3], P0[0])                         # CLK1 <- Q0
    for p in (P0[2], P0[6], P1[2], P1[6]):                 # J,K <- Vcc
        edit.connect(cv, p, graph.pins(vcc)[0])
    data = tpl.new_file_bytes(root)
    h, r2, _ = model.load(data)
    assert check.roundtrip(data) and not check.invariants(r2), check.invariants(r2)
    g = check.geometry(r2); assert not g.get('end off pin') and not g.get('diagonal segment'), g
    assert not check.undriven(r2)
    fl = graph.Flat(r2)
    d = [x for x in fl.devs if x.cls == 'TJKFlipFlop']; c = [x for x in fl.devs if x.cls == 'TClockDevice'][0]
    cn = fl.net(graph.pins(c)[0])
    read = lambda s: s.value(graph.pins(d[0])[0]) + 2 * s.value(graph.pins(d[1])[0])
    u = sim.UnitSim(fl, {cn: 0}); seq = []
    for _ in range(6): u.pulse(cn); seq.append(read(u))
    assert seq == [1, 2, 3, 0, 1, 2], seq
    for seed in range(5):
        s = sim.RandomDelaySim(fl, {cn: 0}, seed=seed)
        assert sim.run_clocked(s, cn, 6, sample=read) == [1, 2, 3, 0, 1, 2]


def t4_hazard_rules():
    from dwm import hazard as H
    M = [('A B C D'.split(), 10), ('A2 B2'.split(), 4)]
    assert H.hazards(('FIN', 'A'), M, 37, lambda s: s['B'] and s['C'] and s['A2'] and s['B2']) == []
    assert H.hazards(((('B', 'C'), ('A2', 'B2')), 'A'), M, 37)      # depth-padded version glitches


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('t') and name[1].isdigit():
            fn(); print('ok', name)
