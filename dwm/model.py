"""Lossless reader/writer for Digital Works .dwm files (Delphi TWriter object stream).

load(bytes) -> (head, root, reader) ; dump(head, root) -> bytes
Every object keeps its fields in byte order: ('t', raw tagged bytes) or ('o', Obj|None).
Editing = mutate the object graph, then dump. Never patch bytes.
"""
import struct

NIL = b'\x02\x0f'


class Obj:
    def __init__(self, cls):
        self.cls = cls
        self.f = []          # [('t', bytes) | ('o', Obj|None)]

    def __repr__(self):
        return '<%s %x>' % (self.cls, id(self) & 0xffff)

    def objs(self):
        return [x for k, x in self.f if k == 'o']


def val(tb):
    """decode one tagged value"""
    t = tb[0]
    if t == 2: return struct.unpack('<b', tb[1:])[0]
    if t == 3: return struct.unpack('<h', tb[1:])[0]
    if t == 4: return struct.unpack('<i', tb[1:])[0]
    if t == 6: return tb[2:].decode('latin1')
    return {0: 'NULL', 1: 'LIST', 8: False, 9: True}[t]


def enc_int(v):
    """shortest i8/i16/i32 encoding (required for byte-exact output)"""
    if -128 <= v < 128: return b'\x02' + struct.pack('<b', v)
    if -32768 <= v < 32768: return b'\x03' + struct.pack('<h', v)
    return b'\x04' + struct.pack('<i', v)


def enc_str(s):
    b = s.encode('latin1')
    return b'\x06' + bytes([len(b)]) + b


class Reader:
    def __init__(self, d):
        self.d = d; self.i = 0; self.classes = []; self.objs = []; self.cur = None

    def tok(self):
        st = self.i; t = self.d[self.i]; self.i += 1
        n = {0: 0, 1: 0, 2: 1, 3: 2, 4: 4, 8: 0, 9: 0}.get(t)
        if t == 6: n = 1 + self.d[self.i]
        if n is None: raise ValueError('bad tag %x @%d' % (t, st))
        self.i += n
        return self.d[st:self.i]

    def V(self):
        tb = self.tok(); self.cur.f.append(('t', tb)); return val(tb)

    def R(self, n):
        b = self.d[self.i:self.i + n]; self.i += n; self.cur.f.append(('t', b)); return b

    def S(self):
        o = self.readobj(); self.cur.f.append(('o', o)); return o

    def readobj(self):
        if self.d[self.i:self.i + 2] == NIL:
            self.i += 2; return None
        st = self.i
        mode = val(self.tok())
        if mode == 2: return self.objs[val(self.tok())]
        if mode == 0:
            c = val(self.tok()); self.classes.append(c)
        elif mode == 1:
            c = self.classes[val(self.tok())]
        else:
            raise ValueError('bad slot mode %r @%d' % (mode, st))
        o = Obj(c); o.at = st; self.objs.append(o)   # id assigned before body
        prev, self.cur = self.cur, o
        body = getattr(self, 'b_' + c, None)
        if body is None: raise ValueError('unknown class %s @%d (add a schema)' % (c, st))
        body()
        self.cur = prev
        return o

    # ---- schemas (see SPEC.md)
    def b_TSerializeList(self):
        assert self.V() == 'LIST'
        while self.d[self.i] != 0: self.S()
        self.V()
    def b_TFloatPoint(self): self.R(8)
    def b_TPolygon(self): self.V(); self.V(); self.S(); self.V()
    def b_TPolyline(self): self.V(); self.V(); self.S()
    def b_TGraphicText(self):
        self.b_TPolygon(); self.V(); self.V(); self.V(); self.V(); self.R(4); self.V(); self.V(); self.V()
    def b_TGraphicList(self): self.S()
    def b_TWire(self): self.V(); self.V(); self.S(); self.V(); self.S(); self.S()
    def b_TSolder(self): self.R(8); self.S(); self.S(); self.S()
    def b_TPin(self): self.b_TPolygon(); self.V(); self.S()
    def b_TMacroPin(self): self.b_TPin(); self.S()
    def dev(self):
        has_shape = self.V()
        if has_shape is True: self.S()
        self.V(); self.V(); self.S()
        if has_shape is not True: self.R(8)
    def b_TClockDevice(self): self.dev(); self.V(); self.V(); self.S(); self.V(); self.V(); self.V()
    b_TBitGenerator = b_TClockDevice
    def b_TSupply(self): self.dev(); self.V(); self.V()
    b_TGround = b_TSupply
    def b_TNumericDevice(self): self.dev(); [self.V() for _ in range(8)]
    def b_TInteractiveSwitch(self): self.dev(); self.V(); self.V(); self.V()
    def b_TTagDevice(self): self.dev(); self.V(); self.V(); self.S()
    def b_TInteractiveInput(self): self.dev(); [self.V() for _ in range(4)]
    def b_TLEDDevice(self): self.dev(); self.V(); self.V(); self.V()
    def b_TLEDSegmentDevice(self): self.dev(); [self.V() for _ in range(4)]
    def b_TMacro(self):
        self.dev(); self.V(); self.V(); self.V(); self.V()
        for _ in range(6): self.S()


# plain devices: DEV body only
for _c in ['T2AndGate', 'T2OrGate', 'T2NorGate', 'T2XorGate', 'T2XnorGate', 'T2NandGate', 'TNotGate',
           'T3AndGate', 'T3OrGate', 'T4OrGate', 'TTriState', 'TJKFlipFlop', 'TDFlipFlop', 'TRSFlipFlop']:
    setattr(Reader, 'b_' + _c, Reader.dev)


def load(d):
    r = Reader(d); r.cur = Obj('HEAD')
    r.V(); assert r.V() == 'LIST'
    while d[r.i] != 0: r.V()
    r.V(); hl = r.i
    r.cur = Obj('ROOT'); root = r.readobj()
    assert r.i == len(d), (r.i, len(d))
    return d[:hl], root, r


class Writer:
    def __init__(self):
        self.out = bytearray(); self.ids = {}; self.classes = []

    def obj(self, o):
        if o is None: self.out += NIL; return
        if id(o) in self.ids: self.out += enc_int(2) + enc_int(self.ids[id(o)]); return
        self.ids[id(o)] = len(self.ids)
        if o.cls in self.classes:
            self.out += enc_int(1) + enc_int(self.classes.index(o.cls))
        else:
            self.classes.append(o.cls); self.out += enc_int(0) + enc_str(o.cls)
        for k, x in o.f:
            if k == 't': self.out += x
            else: self.obj(x)


def dump(head, root):
    w = Writer(); w.out += head; w.obj(root); return bytes(w.out)


# header for brand-new files (content unknown, copied from DW output)
NEW_HEAD = bytes.fromhex('04 dd c4 22 00 01 02 01 02 64 06 00 02 01 02 65 06 00 02 01 02 66 06 00 '
                         '02 02 03 ca 00 02 00 02 02 03 c8 00 02 01 00')


def read(path):
    with open(path, 'rb') as fh: return load(fh.read())


def write(path, head, root):
    with open(path, 'wb') as fh: fh.write(dump(head, root))
