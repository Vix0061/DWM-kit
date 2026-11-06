# DWM-SPEC v5 (compact, LLM-oriented; self-contained: read/edit/GENERATE/SIMULATE without any source .dwm)
# Digital Works .dwm = Delphi object graph. LE. f32=IEEE754 float32. coords px, y-down.
# conf: C=confirmed(byte-exact roundtrip of 5 files incl. 1.8MB 4-level nested project; generated circuits run in DW) I=inferred U=unknown(copy verbatim)

## FILE C
file := HEAD obj(TMacro) EOF
HEAD := V(i32 0x0022C4DD) V(01) V* V(00)   # tagged list; length varies (39 or 40 bytes seen); content U -> copy; for new files emit:
04 dd c4 22 00 01 02 01 02 64 06 00 02 01 02 65 06 00 02 01 02 66 06 00 02 02 03 ca 00 02 00 02 02 03 c8 00 02 01 00
parse HEAD as values until the list's closing 00; root starts right after. never assume fixed length.

## V tagged value C
00 null|list_end ; 01 list_begin ; 02 i8 ; 03 i16 ; 04 i32 ; 06 u8len+latin1 ; 08 false ; 09 true
int: ALWAYS shortest of i8/i16/i32 (byte-exact). PT := f32 x,f32 y raw untagged. RAW(4) in text = 00000000 (U).

## SLOT C
slot := 02 0F                         -> nil
      | V(0) V(str classname) body    -> new obj, register class (next idx)
      | V(1) V(int classidx)  body    -> new obj
      | V(2) V(int objid)             -> ref
check 02 0F first. objid: global counter from 0 (root=0), ++ per new obj in stream order, assigned BEFORE body (child may ref parent).
classes don't consume ids. classidx per-file by first appearance; never hardcode.
writer: preorder walk; first encounter=new (full body), later=ref. edit = load graph -> mutate -> reserialize; never patch bytes.

## PRIMITIVE BODIES C   (V tagged, S slot, PT raw8)
TSerializeList : V(01) S* V(00)
TGraphicList   : S(TSerializeList)
TFloatPoint    : PT
TPolygon       : V(0,U) V(1,U) S(list<TFloatPoint>) V(color 0x00BBGGRR)
TPolyline      : V(0) V(1) S(list<TFloatPoint>)
TGraphicText   : TPolygon V(fontsize) V(fontcolor) V(F) V(400) RAW(4) V(str) V(T) V(F)       # polygon = text box
TPin           : TPolygon V(dir) S(TWire|nil)
  dir: 1 in C ; 2 out C ; 3 bidir (switch contacts, tristate out) I ; 0 tag pin / chip VCC-GND I
  square 8x8 (7seg: 4x4) ABS coords; center = avg of 4 pts = connection point; max 1 wire
TMacroPin      : TPin S(TMacroPin partner)   # see MACROS
TWire          : V(color 0|0xC0C0C0,U) V(1) S(list<TFloatPoint>) V(0) S(endA) S(endB)   # ends TPin|TMacroPin|TSolder; pts A->B incl endpoints
TSolder        : PT(pos) S(TWire) S(TWire) S(TWire)                                     # exactly 3 (2 or 4 never seen)

## INVARIANTS C
pin.wire==w <=> w.A==pin||w.B==pin ; w in solder.wires <=> w.A==solder||w.B==solder
connectivity only via TWire/TSolder; visual crossings never connect; net = union-find over wire ends
each canvas: GL[5]==its live solders, GL[6]==its live wires

## DEVICE BODY C
DEV := V(hasShape) [S(list<graphics>) if hasShape] V(b1) V(b2) S(GL<TPin>) [PT(pos) if !hasShape] EXTRA
hasShape=F: standard drawing at pos (= body center). hasShape=T: explicit ABS geometry, no pos (rotated/mirrored gates, displays, tags, macros).
pin geometry always ABS. b1=T on user-clickable devices (I); b2 U.

## DEVICE TABLE C   (EXTRA ; root list ; pins idx:role:dir:offset from pos)
2-in gates T2And T2Nand T2Or T2Nor T2Xor T2Xnor : none ; L1 ; 0:out(+30,0) 1:in(-30,+10) 2:in(-30,-10)
T3AndGate T3OrGate : none ; L1 ; 0:out(+30,0) 1:(-30,+10) 2:(-30,0) 3:(-30,-10)
T4OrGate           : none ; L1 ; 0:out(+30,0) 1:(-30,+15) 2:(-30,+5) 3:(-30,-5) 4:(-30,-15)
TNotGate           : none ; L1 ; 0:out(+30,0) 1:in(-20,0)
TTriState          : none ; L1 ; 0:in(-20,0) 1:out dir3(+20,0) 2:enable(0,+10) ; passes when enable=1 (I)
TJKFlipFlop        : none ; L1 ; 0:Q(+30,-10) 1:Qn(+30,+10) 2:J(-30,-10) 3:CLK(-30,0) 4:CLR(-20,+20) 5:PRE(-10,+20) 6:K(-30,+10)
TDFlipFlop         : none ; L1 ; 0:Q 1:Qn 2:D 3:CLK 4:CLR(I) 5:PRE(I)   (JK layout minus K)
TRSFlipFlop        : none ; L1 ; 0:Q 1:Qn 2:S(I,top) 3:R(I,bottom)
TInteractiveSwitch : V(F) V(2) V(F) U ; L1 ; b1=T ; 0,1 contacts dir3 (0,-15)(0,+15)
TMacro (instance)  : see MACROS ; L1
TGraphicText free label on canvas : L1 (not a device)
TTagDevice         : see MACROS ; L2
TClockDevice       : V(T) V(0) S(TGraphicText "clock") V(F) V(str "01",U) V(color 0x00FF00) ; L3 ; 0:out(+15,0)
TBitGenerator      : same as clock, text "sequence", str "", color 0x0000FF ; L3 ; 0:out(+15,0)
TInteractiveInput  : V(F) V(F) V(F,U state?) V(0,U) ; L3 ; b1=T ; 0:out(0,0)
TSupply            : V(F) V(F) ; L3 ; 0:out(+10,0)   const 1
TGround            : V(F) V(F) ; L3 ; 0:out(0,-10)   const 0
TLEDDevice         : V(F) V(F) V(color 0x0000FF) ; L4 ; 0:in(0,0)
TLEDSegmentDevice  : V(F) V(F) V(color 0x0000FF) V(T,U) ; L4 ; pins 0..6 = seg a..g (C) at (-15..+15 step 5, +50), 4x4
TNumericDevice     : hasShape=T ; V(F) V(F) V(color) V(nbits=4) V(17|18,U) V(0,U) V(color) V(bool,U) ; L4 ; pins 0..3 = bit0(LSB, rightmost)..bit3, step -10

## MACROS C   (root file = TMacro; instances nest to any depth)
TMacro := V(T) S(symbol shape) V(b1) V(b2) S(GL ext pins) V("",U) V(0,U) V(x,U) V(y,U) S(GL)x6
  root: b1,b2=F,T ; ext pins empty ; x,y=F,F ; shape = rect + text "macro"
  instance: b1,b2=F,F ; ext pins = TMacroPin list ; x,y=T,T ; shape = symbol drawn in PARENT canvas (rect, pin names, title)
  6 GLs: L1 logic (gates, FFs, switch, macro instances, free texts) ; L2 tags ; L3 sources ; L4 outputs ; L5 ALL solders ; L6 ALL wires
pin pairing: each macro pin = 2 TMacroPin linked both ways via last field (verified 1886/1886 pairs):
  ext pin   : in instance ext-pin GL ; ABS coords of PARENT canvas ; dir 1 in/2 out/0 power ; takes parent wire
  inner pin : last field of a TTagDevice inside the macro ; coords RELATIVE (±4 around 0,0) ; no wire ; never translated
TTagDevice := DEV(hasShape=T: [TGraphicText label = pin number/name]) b1=F b2=T GL[TPin dir0 color 0xEEFAFF] V(a, mostly 0,U) V(b = ext dir) S(inner TMacroPin)
signal path outside->inside: ext pin -> partner inner pin -> its tag -> tag's TPin -> inner wires
move instance in parent: shift symbol shape pts + ext pin pts only (inner canvas untouched)

## SIMULATION SEMANTICS
JK toggles on CLK FALLING edge (ripple Q->CLK counts up) C ; CLR active-high async, dominates clock (edge during clear ignored) C ; PRE active-high I
unconnected input = 0 C ; tristate passes when enable=1 C ; supply=1 ground=0 ; interactive input red=1 C
macros are transparent: flatten (ext pin <-> partner inner pin <-> tag TPin) before simulating C
TIMING C(observed): DW delays are NOT uniform per gate depth. design as if every gate/FF has an arbitrary positive delay.
  verify model: transport delay, each device random 1..3 steps, clock half-period >=60 steps, >=24 seeds; must match designed sequence on all seeds.
  unit-delay or zero-delay sims MISS real DW failures (seen: reset glitch passed unit-delay, failed in DW and in random-delay).

## DESIGN RULES (ripple counters, AND-tree detectors) C
ripple step order: lower bits fall first, then the next bit rises (caused by that fall). MOD10 digit 9->0: A fall, B rise (=10 transient), D·B -> CLR B,D, then D·B falls -> clocks next digit.
hazard: AND of literals glitches if one input falls and another rises in the same step and they reach the root by different paths.
R1 a falling bit and the rising bit it causes must enter the SAME gate directly (causality then orders them). never pad/delay one with AND(x,Vcc) chains or depth-balancing.
R2 use the MINIMAL literal set: smallest subset of target's 1-bits that no earlier state (incl. transients like units=10) contains.
R3 if R1 is impossible with 2-input gates (needs 3 changing bits together), factor: reset(v+1) = AND(FIN(v), x) as ONE gate, x = bit that turns on at v+1; FIN changes only after x's partner fell.
R4 stable bits (other digits not changing in that step) may enter anywhere.
R5 gate signals that must not glitch (clock gating, next-stage clock N=CK·FIN) with CK: transitions happen right after the falling edge while CK=0, so CK masks them.
R6 async CLR is the dangerous consumer: a glitch on a reset detector clears the counter. check every reset detector with R1-R3.
R7 stop detection must settle within half a clock period; long carry chains (x9->x0 with tens ripple) are slowest -> slow clock if a stage overshoots.
calendar month pattern C: units MOD10 (A,B,C,D) + tens MOD4 (A2,B2) [+T2 JK clocked by B2 for 40]; FIN=AND(target bits); freeze: AND(FIN,Cl)->tristate(en=Vcc)->NOT->AND(P)->AND(CK)=gated clock; N=AND(CK,FIN) -> next stage CK; cycle reset = AND(bits of v+1) OR R -> CLR.

## CHIP MACROS I
student files wrap gates in 74xx-style macros (title "AND"/"OR"/"Not", 2 gates each, VCC/GND pins unconnected inside). unused gate = all its ext pins without wire -> free for reuse. flatten through them for netlists.

## TPL — template grammar C
line := Name anchor "=" obj ; anchor: pos (device pos) | pin0 (center of pin 0) | abs (0,0)
obj  := Class "(" field* ")"   -> new obj; fields in byte order
field:= int -> V shortest | T | F | "text" | X<8hex> -> RAW(4) | @(dx,dy) -> raw PT = anchor+d | nil | obj | list | GL list
list := "[" (obj | P(dx,dy))* "]"   -> new TSerializeList ; P -> new TFloatPoint at anchor+d
inside TMacroPin(...) of a tag: coords NOT offset. all objects new (no refs). connect a pin = replace its last nil with the TWire.
new wire: TWire(0 1 [P(x0,y0)..P(xn,yn)] 0 endA endB) ABS ; new solder: TSolder(@(x,y) w1 w2 w3)

## TEMPLATES C
TMacro abs = TMacro(T [TPolygon(0 1 [P(-20,-10) P(20,-10) P(20,10) P(-20,10)] 16777215) TGraphicText(0 1 [P(-13,-5) P(-13,5) P(13,5) P(13,-5)] 16777215 7 0 F 400 X00000000 "macro" T F)] F T GL[] "" 0 F F GL[] GL[] GL[] GL[] GL[] GL[])
T2OrGate pos = T2OrGate(F F F GL[TPin(0 1 [P(34,4) P(34,-4) P(26,-4) P(26,4)] 16777215 2 nil) TPin(0 1 [P(-26,14) P(-26,6) P(-34,6) P(-34,14)] 16777215 1 nil) TPin(0 1 [P(-26,-6) P(-26,-14) P(-34,-14) P(-34,-6)] 16777215 1 nil)] @(0,0))
T2NorGate pos = T2NorGate(F F F GL[TPin(0 1 [P(34,4) P(34,-4) P(26,-4) P(26,4)] 16777215 2 nil) TPin(0 1 [P(-26,14) P(-26,6) P(-34,6) P(-34,14)] 16777215 1 nil) TPin(0 1 [P(-26,-6) P(-26,-14) P(-34,-14) P(-34,-6)] 16777215 1 nil)] @(0,0))
T2XorGate pos = T2XorGate(F F F GL[TPin(0 1 [P(34,4) P(34,-4) P(26,-4) P(26,4)] 16777215 2 nil) TPin(0 1 [P(-26,14) P(-26,6) P(-34,6) P(-34,14)] 16777215 1 nil) TPin(0 1 [P(-26,-6) P(-26,-14) P(-34,-14) P(-34,-6)] 16777215 1 nil)] @(0,0))
T2XnorGate pos = T2XnorGate(F F F GL[TPin(0 1 [P(34,4) P(34,-4) P(26,-4) P(26,4)] 16777215 2 nil) TPin(0 1 [P(-26,14) P(-26,6) P(-34,6) P(-34,14)] 16777215 1 nil) TPin(0 1 [P(-26,-6) P(-26,-14) P(-34,-14) P(-34,-6)] 16777215 1 nil)] @(0,0))
TNotGate pos = TNotGate(F F F GL[TPin(0 1 [P(34,4) P(34,-4) P(26,-4) P(26,4)] 16777215 2 nil) TPin(0 1 [P(-16,4) P(-16,-4) P(-24,-4) P(-24,4)] 16777215 1 nil)] @(0,0))
T2AndGate pos = T2AndGate(F F F GL[TPin(0 1 [P(34,4) P(34,-4) P(26,-4) P(26,4)] 16777215 2 nil) TPin(0 1 [P(-26,14) P(-26,6) P(-34,6) P(-34,14)] 16777215 1 nil) TPin(0 1 [P(-26,-6) P(-26,-14) P(-34,-14) P(-34,-6)] 16777215 1 nil)] @(0,0))
T2NandGate pos = T2NandGate(F F F GL[TPin(0 1 [P(34,4) P(34,-4) P(26,-4) P(26,4)] 16777215 2 nil) TPin(0 1 [P(-26,14) P(-26,6) P(-34,6) P(-34,14)] 16777215 1 nil) TPin(0 1 [P(-26,-6) P(-26,-14) P(-34,-14) P(-34,-6)] 16777215 1 nil)] @(0,0))
T3AndGate pos = T3AndGate(F F F GL[TPin(0 1 [P(34,4) P(34,-4) P(26,-4) P(26,4)] 16777215 2 nil) TPin(0 1 [P(-26,14) P(-26,6) P(-34,6) P(-34,14)] 16777215 1 nil) TPin(0 1 [P(-26,4) P(-26,-4) P(-34,-4) P(-34,4)] 16777215 1 nil) TPin(0 1 [P(-26,-6) P(-26,-14) P(-34,-14) P(-34,-6)] 16777215 1 nil)] @(0,0))
T3OrGate pos = T3OrGate(F F F GL[TPin(0 1 [P(34,4) P(34,-4) P(26,-4) P(26,4)] 16777215 2 nil) TPin(0 1 [P(-26,14) P(-26,6) P(-34,6) P(-34,14)] 16777215 1 nil) TPin(0 1 [P(-26,4) P(-26,-4) P(-34,-4) P(-34,4)] 16777215 1 nil) TPin(0 1 [P(-26,-6) P(-26,-14) P(-34,-14) P(-34,-6)] 16777215 1 nil)] @(0,0))
T4OrGate pos = T4OrGate(F F F GL[TPin(0 1 [P(34,4) P(34,-4) P(26,-4) P(26,4)] 16777215 2 nil) TPin(0 1 [P(-26,19) P(-26,11) P(-34,11) P(-34,19)] 16777215 1 nil) TPin(0 1 [P(-26,9) P(-26,1) P(-34,1) P(-34,9)] 16777215 1 nil) TPin(0 1 [P(-26,-1) P(-26,-9) P(-34,-9) P(-34,-1)] 16777215 1 nil) TPin(0 1 [P(-26,-11) P(-26,-19) P(-34,-19) P(-34,-11)] 16777215 1 nil)] @(0,0))
TTriState pos = TTriState(F F F GL[TPin(0 1 [P(-16,4) P(-16,-4) P(-24,-4) P(-24,4)] 16777215 1 nil) TPin(0 1 [P(24,4) P(24,-4) P(16,-4) P(16,4)] 16777215 3 nil) TPin(0 1 [P(4,14) P(4,6) P(-4,6) P(-4,14)] 16777215 1 nil)] @(0,0))
TRSFlipFlop pos = TRSFlipFlop(F F F GL[TPin(0 1 [P(34,-6) P(34,-14) P(26,-14) P(26,-6)] 16777215 2 nil) TPin(0 1 [P(34,14) P(34,6) P(26,6) P(26,14)] 16777215 2 nil) TPin(0 1 [P(-26,-6) P(-26,-14) P(-34,-14) P(-34,-6)] 16777215 1 nil) TPin(0 1 [P(-26,14) P(-26,6) P(-34,6) P(-34,14)] 16777215 1 nil)] @(0,0))
TJKFlipFlop pos = TJKFlipFlop(F F F GL[TPin(0 1 [P(34,-6) P(34,-14) P(26,-14) P(26,-6)] 16777215 2 nil) TPin(0 1 [P(34,14) P(34,6) P(26,6) P(26,14)] 16777215 2 nil) TPin(0 1 [P(-26,-6) P(-26,-14) P(-34,-14) P(-34,-6)] 16777215 1 nil) TPin(0 1 [P(-26,4) P(-26,-4) P(-34,-4) P(-34,4)] 16777215 1 nil) TPin(0 1 [P(-16,24) P(-16,16) P(-24,16) P(-24,24)] 16777215 1 nil) TPin(0 1 [P(-6,24) P(-6,16) P(-14,16) P(-14,24)] 16777215 1 nil) TPin(0 1 [P(-26,14) P(-26,6) P(-34,6) P(-34,14)] 16777215 1 nil)] @(0,0))
TDFlipFlop pos = TDFlipFlop(F F F GL[TPin(0 1 [P(34,-6) P(34,-14) P(26,-14) P(26,-6)] 16777215 2 nil) TPin(0 1 [P(34,14) P(34,6) P(26,6) P(26,14)] 16777215 2 nil) TPin(0 1 [P(-26,-6) P(-26,-14) P(-34,-14) P(-34,-6)] 16777215 1 nil) TPin(0 1 [P(-26,4) P(-26,-4) P(-34,-4) P(-34,4)] 16777215 1 nil) TPin(0 1 [P(-16,24) P(-16,16) P(-24,16) P(-24,24)] 16777215 1 nil) TPin(0 1 [P(-6,24) P(-6,16) P(-14,16) P(-14,24)] 16777215 1 nil)] @(0,0))
TInteractiveSwitch pos = TInteractiveSwitch(F T F GL[TPin(0 1 [P(4,-11) P(4,-19) P(-4,-19) P(-4,-11)] 16777215 3 nil) TPin(0 1 [P(4,19) P(4,11) P(-4,11) P(-4,19)] 16777215 3 nil)] @(0,0) F 2 F)
TTagDevice pin0 = TTagDevice(T [TGraphicText(0 1 [P(-12,0) P(-12,0) P(-12,0) P(-12,0)] 16777215 7 0 F 400 X00000000 "" T F)] F T GL[TPin(0 1 [P(4,4) P(4,-4) P(-4,-4) P(-4,4)] 15661823 0 nil)] 0 0 TMacroPin(0 1 [P(4,4) P(4,-4) P(-4,-4) P(-4,4)] 16777215 0 nil nil))
TBitGenerator pos = TBitGenerator(F F F GL[TPin(0 1 [P(19,4) P(19,-4) P(11,-4) P(11,4)] 16777215 2 nil)] @(0,0) T 0 TGraphicText(0 1 [P(-44,-5) P(-44,5) P(-4,5) P(-4,-5)] 16777215 7 0 F 400 X00000000 "sequence" T F) F "" 255)
TClockDevice pos = TClockDevice(F F F GL[TPin(0 1 [P(19,4) P(19,-4) P(11,-4) P(11,4)] 16777215 2 nil)] @(0,0) T 0 TGraphicText(0 1 [P(-26,-5) P(-26,5) P(-4,5) P(-4,-5)] 16777215 7 0 F 400 X00000000 "clock" T F) F "01" 65280)
TInteractiveInput pos = TInteractiveInput(F T F GL[TPin(0 1 [P(4,4) P(4,-4) P(-4,-4) P(-4,4)] 16777215 2 nil)] @(0,0) F F F 0)
TGround pos = TGround(F F F GL[TPin(0 1 [P(4,-6) P(4,-14) P(-4,-14) P(-4,-6)] 16777215 2 nil)] @(0,0) F F)
TSupply pos = TSupply(F F F GL[TPin(0 1 [P(14,4) P(14,-4) P(6,-4) P(6,4)] 16777215 2 nil)] @(0,0) F F)
TLEDDevice pos = TLEDDevice(F F F GL[TPin(0 1 [P(4,4) P(4,-4) P(-4,-4) P(-4,4)] 16777215 1 nil)] @(0,0) F F 255)
TLEDSegmentDevice pos = TLEDSegmentDevice(F F F GL[TPin(0 1 [P(-13,52) P(-13,48) P(-17,48) P(-17,52)] 16777215 1 nil) TPin(0 1 [P(-8,52) P(-8,48) P(-12,48) P(-12,52)] 16777215 1 nil) TPin(0 1 [P(-3,52) P(-3,48) P(-7,48) P(-7,52)] 16777215 1 nil) TPin(0 1 [P(2,52) P(2,48) P(-2,48) P(-2,52)] 16777215 1 nil) TPin(0 1 [P(7,52) P(7,48) P(3,48) P(3,52)] 16777215 1 nil) TPin(0 1 [P(12,52) P(12,48) P(8,48) P(8,52)] 16777215 1 nil) TPin(0 1 [P(17,52) P(17,48) P(13,48) P(13,52)] 16777215 1 nil)] @(0,0) F F 255 T)
TNumericDevice pin0 = TNumericDevice(T [TPolygon(0 1 [P(-35,5) P(5,5) P(5,20) P(-35,20) P(-35,5)] 0) TGraphicText(0 1 [P(-3,6) P(-3,21) P(3,21) P(3,6)] 16777215 10 8421504 F 400 X00000000 "0" T F) TGraphicText(0 1 [P(-13,6) P(-13,21) P(-7,21) P(-7,6)] 16777215 10 8421504 F 400 X00000000 "0" T F) TGraphicText(0 1 [P(-23,6) P(-23,21) P(-17,21) P(-17,6)] 16777215 10 8421504 F 400 X00000000 "0" T F) TGraphicText(0 1 [P(-33,6) P(-33,21) P(-27,21) P(-27,6)] 16777215 10 8421504 F 400 X00000000 "0" T F) TPolyline(0 1 [P(0,0) P(0,5)]) TPolyline(0 1 [P(-10,0) P(-10,5)]) TPolyline(0 1 [P(-20,0) P(-20,5)]) TPolyline(0 1 [P(-30,0) P(-30,5)])] F F GL[TPin(0 1 [P(4,4) P(4,-4) P(-4,-4) P(-4,4)] 16777215 1 nil) TPin(0 1 [P(-6,4) P(-6,-4) P(-14,-4) P(-14,4)] 16777215 1 nil) TPin(0 1 [P(-16,4) P(-16,-4) P(-24,-4) P(-24,4)] 16777215 1 nil) TPin(0 1 [P(-26,4) P(-26,-4) P(-34,-4) P(-34,4)] 16777215 1 nil)] F F 16777215 4 17 0 8421504 F)

## OPS C
place(dev): TPL at anchor ; append to its L1..L4
connect(pA,pB): new wire, orthogonal pts center(pA)..center(pB) ; set both pin.wire ; append L6
rail(net of n pins): sort taps by x ; solders at taps 2..n-1 ; wires e1->S2, Si->Si+1, Si->ei (stub), Sn-1->en ; L5,L6
tap(w:A->B at P, dst): S@P ; wires A->S, S->B, S->dst (arrive perpendicular) ; replace w in A,B ; dst.wire=S->dst ; rm w
del_device(d): rm from list ; rm its wires (far pins.wire=nil) ; solder left 2 wires -> merge ; <2 -> rm + cascade ; fix L5,L6
merge(S; wa:X-S, wb:S-Y): wire X->Y, pts = pts(wa toward S)+pts(wb from S)[1:], drop collinear/backtrack ; replace refs in X,Y ; rm wa,wb,S
add_macro_pin(m): ext TMacroPin on symbol edge (parent ABS, dir) + TTagDevice inside (label, b=dir) ; link both ways ; symbol text label ; wire both sides
move(dev): shift pos (if any) + all pin/shape pts ; reroute attached wires (rigid groups: move internal wires too)
routing hygiene: no wire over chip/display body ; no collinear overlap between nets ; never through another net's pin/vertex ; many crossings -> channel routing (own track per net)

## TESTS
T1 write(read(f))==f byte-exact
T2 root + every template at these anchors -> general_components.dwm byte-exact (6111 B), list order as given, L5,L6 empty:
   L1 T2OrGate(370,165) T2NorGate(370,225) T2XorGate(480,160) T2XnorGate(480,215) TNotGate(570,160) T2AndGate(700,160) T2NandGate(700,210) TRSFlipFlop(815,150) TJKFlipFlop(820,210) TDFlipFlop(950,150) TInteractiveSwitch(1170,235)
   L2 TTagDevice(970,240)
   L3 TBitGenerator(1110,175) TClockDevice(1085,235) TInteractiveInput(1175,170) TGround(1240,230) TSupply(1245,170)
   L4 TLEDDevice(1315,175) TLEDSegmentDevice(1535,215) TNumericDevice(1335,220)
T3 INVARIANTS after every edit
T4 netlist simulation (SIMULATION SEMANTICS) reproduces designed behavior, unit-delay AND random-delay (TIMING) both pass
T5 no net with loads and no driver ; no wire over a chip body ; no collinear overlap between nets
T6 every edit keeps T1-T5; fix one stage, retest all stages (a fix can expose the next stage)

## GAPS U
not seen: T flip-flop, NAND/NOR/XOR with 3-4 inputs, generated rotated devices
unknown: HEAD meaning, b2, tag field a, switch/input state, clock "01"/freq storage, numeric 17|18 + last bool, 7seg last bool
method: save same circuit twice changing one property, diff
