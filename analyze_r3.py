# 3. tur ozeti: python3 analyze_r3.py r3.jsonl
import sys, json, collections
R = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
OK = ('alindi', 'cikti')
by = collections.defaultdict(list)
for r in R:
    by[r['did']].append(r)
def tally(rs, pred):
    g = n = out = 0
    for r in rs:
        if pred(r):
            g += sum(b['state'] in OK for b in r['balls']); n += len(r['balls'])
            out += sum(b['state'] == 'kacti' for b in r['balls'])
    return g, n, out
print(f'{len(R)} kosu')
print('--- ana takim (11 tek + 24 coklu kosu) ve 60 rastgele sahne')
print(f"{'tasarim':44s} {'tek':>7s} {'coklu':>8s} {'rastgele':>10s} {'disari':>6s}")
for did in sorted(by):
    if '~' in did: continue
    rs = by[did]
    s = tally(rs, lambda r: r['test'].startswith('tek')); m = tally(rs, lambda r: not r['test'].startswith(('tek', 'rnd')))
    q = tally(rs, lambda r: r['test'].startswith('rnd'))
    print(f"{did:44s} {s[0]:3d}/{s[1]:<3d} {m[0]:4d}/{m[1]:<3d} {q[0]:5d}/{q[1]:<4d} {s[2]+m[2]+q[2]:6d}")
print('--- duyarlilik (11 tek + 9 coklu kosu), sadece eksik olanlar')
for did in sorted(by):
    if '~' not in did: continue
    rs = by[did]
    s = tally(rs, lambda r: r['test'].startswith('tek')); m = tally(rs, lambda r: not r['test'].startswith('tek'))
    bad = [f"{r['test']}:" + ','.join(f"z{b['z']*100:+.0f}{'!' if b['state']=='kacti' else ''}" for b in r['balls'] if b['state'] not in OK) for r in sorted(rs, key=lambda r: r['test']) if any(b['state'] not in OK for b in r['balls'])]
    vs = [b['v'] for r in rs for b in r['balls'] if b.get('v')]
    extra = f" cikis {min(vs):.2f}-{max(vs):.2f} m/s" if vs else ''
    print(f"{did:44s} tek {s[0]}/{s[1]} coklu {m[0]}/{m[1]}{extra}  {' '.join(bad)}")
