"""Design helper for AND-tree detectors on ripple counters (SPEC.md DESIGN RULES).

digits: list of (bit names LSB first, base), e.g. [(['A','B','C','D'],10), (['A2','B2'],4)]
spec:   nested 2-tuples of literal names = AND tree; ('FIN','A') = one gate.
hazards(spec, digits, target) -> counts n where the step n->n+1 (before target) can glitch
    the detector under arbitrary gate delays (leaf groups = literals entering one gate).
best(digits, v) -> (gates, spec) smallest hazard-free detector for first reach of v.
"""
import itertools
def val(state,bits): return sum(state[b]<<i for i,b in enumerate(bits))
def interleave(a,b):
    if not a: yield list(b); return
    if not b: yield list(a); return
    for r in interleave(a[1:],b): yield [a[0]]+r
    for r in interleave(a,b[1:]): yield [b[0]]+r
def inc_events(state,digits,k=0):
    """list of possible event sequences (lists of (bit,val)) for incrementing digit k"""
    if k>=len(digits): return [[]]
    bits,base=digits[k]; v=val(state,bits)
    if base==10 and v==9:
        # 9 -> transient 10 -> clear (B,D in any order); carry starts after first clear
        pre=[(bits[0],0),(bits[1],1)]
        st=dict(state); st[bits[0]]=0; st[bits[1]]=1
        nxt=dict(st); nxt[bits[1]]=0; nxt[bits[3]]=0
        # common CLR: B and D clear together; carry (clocked by D·B falling) follows
        return [pre+[((bits[1],bits[3]),0)]+c for c in inc_events(nxt,digits,k+1)]
    ev=[]; i=0
    while i<len(bits) and state[bits[i]]==1: ev.append((bits[i],0)); i+=1
    if i<len(bits): ev.append((bits[i],1)); return [ev]
    st=dict(state)
    for b,x in ev: st[b]=x
    return [ev+c for c in inc_events(st,digits,k+1)]
def windows(digits,upto):
    allb=[b for bits,_ in digits for b in bits]
    st={b:0 for b in allb}; W=[]
    for n in range(upto):
        seqs=inc_events(st,digits)
        tl=[]
        for s in seqs:
            cur=dict(st); L=[dict(cur)]
            for b,x in s:
                for bb in (b if isinstance(b,tuple) else (b,)): cur[bb]=x
                L.append(dict(cur))
            tl.append(L)
        W.append((n,tl)); st=tl[0][-1]
    return W,st
def groups(spec):
    """leaf groups: literal sets entering the same gate directly"""
    G=[]
    def rec(s):
        if isinstance(s,str): return
        lits=[x for x in s if isinstance(x,str)]
        if lits: G.append(frozenset(lits))
        for x in s:
            if not isinstance(x,str): rec(x)
    if isinstance(spec,str): G.append(frozenset([spec]))
    else: rec(spec)
    return G
def possible(g,timelines,fin=None):
    for L in timelines:
        if 'FIN' in g:
            others=[b for b in g if b!='FIN']
            for i in range(len(L)):
                if fin(L[i]):
                    for j in range(i,len(L)):
                        if all(L[j][b] for b in others): return True
        else:
            for s in L:
                if all(s[b] for b in g): return True
    return False
def hazards(spec,digits,target,fin=None):
    W,_=windows(digits,target)
    bad=[]
    G=groups(spec)
    for n,tl in W:
        if n+1>=target: break   # window ending at target: early detection harmless
        if all(possible(g,tl,fin) for g in G): bad.append(n)
    return bad
def trees(lits):
    """all binary AND trees over literal list (unordered)"""
    lits=list(lits)
    if len(lits)==1: yield lits[0]; return
    first=lits[0]; rest=lits[1:]
    for r in range(0,len(rest)):
        for comb in itertools.combinations(rest,r):
            left=[first]+list(comb); right=[x for x in rest if x not in comb]
            if not right: continue
            for a in trees(left):
                for b in trees(right): yield (a,b)


def bitsof(state): return {b for b,x in state.items() if x}
def states(digits,upto):
    W,last=windows(digits,upto)
    S=[bitsof(tl[0][0]) for n,tl in W]+[bitsof(last)]
    return S,W
def candidates(digits,v,extra=1):
    S,W=states(digits,v)
    target=S[v]; prior=S[:v]
    # transient-inclusive priors: every intermediate state in windows before target
    inter=[bitsof(s) for n,tl in W if n+1<v for L in tl for s in L]
    out=[]
    for k in range(1,len(target)+1):
        for c in itertools.combinations(sorted(target),k):
            if not any(set(c)<=p for p in prior+inter): out.append(list(c))
        if out and k>=len(out[0])+extra: break
    return out,target
def best(digits,v,fin_set=None):
    cands,target=candidates(digits,v)
    sols=[]
    for c in cands:
        for t in trees(c):
            if not hazards(t,digits,v): sols.append((max(1,len(c)-1),t))
    if fin_set:
        fin=lambda s: all(s[b] for b in fin_set)
        ex=sorted(target-set(fin_set))
        for k in range(1,len(ex)+1):
            for c in itertools.combinations(ex,k):
                # FIN·c must be a valid detector of v
                S,W=states(digits,v)
                inter=[bitsof(s) for n,tl in W if n+1<v for L in tl for s in L]
                if any((set(fin_set)|set(c))<=p for p in S[:v]+inter): continue
                for t in trees(['FIN']+list(c)):
                    if not hazards(t,digits,v,fin): sols.append((len(c),t))
    sols.sort(key=lambda x:x[0])
    return sols[0] if sols else None
