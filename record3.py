# Bir senaryoyu kayitli kostur (video icin): PYTHONPATH=pylib:. python3.13 record3.py <cikti.npz> <tasarim> <test> [io=1] [tohum]
#   tasarim: REF | IN | C1 | C1L     test: rounds.MULTI2 anahtari | rndNN | tek+0.090
import sys, json
import numpy as np
import sim3 as S, rounds

CAND = {'REF': (rounds.REFS['REF CAD oldugu gibi'][0], dict(c_rr=rounds.RR, mu_boot=0.15)),
        'IN': (rounds.REFS['IN sadece mecanum iceri'][0], dict(c_rr=rounds.RR, mu_boot=0.15)),
        'C1': (rounds.C1, dict(c_rr=rounds.RR)),
        'C1L': (rounds.C1, dict(c_rr=rounds.RR, mu_back=0.12)),
        'NEW': (rounds.NATIVE, dict(c_rr=rounds.RR, mu_boot=0.15))}

if __name__ == '__main__':
    out, dn, tn = sys.argv[1:4]
    io = (sys.argv[4] != '0') if len(sys.argv) > 4 else True
    import os
    cj = json.loads(os.environ.get('CANDS') or '[]')     # optimizasyon adaylari (T253 vb.) ve K00_CAD
    if any(c['name'] == dn for c in cj):
        c = next(c for c in cj if c['name'] == dn)
        D = rounds.cand_design(c); p = dict(rounds.PHYS_MED)
    elif dn in CAND:
        D, p = CAND[dn]
    else:                                   # rounds.KANAL / KANAL2 tasarimi, ad on eki ile (orn. K14)
        allk = dict(rounds.KANAL); allk.update(getattr(rounds, 'KANAL2', {}))
        name = next(k for k in allk if k.split(' ')[0] == dn)
        D = dict(rounds.NATIVE); D.update(allk[name]); p = dict(c_rr=rounds.RR, mu_boot=0.15)
    rv = 0.5
    if tn.startswith('v') and 's' in tn[1:]:    # dogrulama sahnesi birebir: v55s5 = scenes(100, 777)[55], tohum 5, ayni fizik/hiz
        i_, sd_ = map(int, tn[1:].split('s'))
        balls = rounds.scenes(100, 777)[i_]; seed = 777 * 1000 + 100 * sd_ + i_
        p, rv = rounds.dr_params(sd_ * 100003 + 777, i_)
    elif tn.startswith('rnd'):
        balls = rounds.scenes()[int(tn[3:])]; seed = 100 + int(tn[3:])
    elif tn.startswith('tek'):
        balls = [(-0.30, float(tn[3:]), 0)]; seed = 1
    else:
        balls = rounds.MULTI2[tn]; seed = 1
    if len(sys.argv) > 5:
        seed = int(sys.argv[5])
    import os
    W = S.World(os.environ.get('REGION', 'region2.npz'))
    S.P.clear(); S.P.update(S.P0); S.P.update(p)
    W.set_design(D)
    B, rec = W.run(balls, robot_v=rv, intake_only=io, t_max=4.0, seed=seed, rec_dt=1 / 600)
    print(dn, tn, S.describe(B), 't_son=%.2f' % max(b.t_end for b in B))
    if os.environ.get('SONUC_OUT'):                       # videodaki sonuc yazisi icin
        ok = sum(b.state in ('alindi', 'cikti') for b in B)
        ts = [b.t_end for b in B if b.state in ('alindi', 'cikti')]
        open(os.environ['SONUC_OUT'], 'w').write(f'{ok}/{len(B)} alındı' + ('' if ok == len(B) else
                                                 f' ({len(B) - ok} top kaldı)') +
                                                 (f' | son top {max(ts):.2f} s' if ts else ''))
    np.savez_compressed(out, t=np.array(rec['t']), pos=np.array(rec['pos'], dtype=object),
                        quat=np.array(rec['quat'], dtype=object), theta=np.array(rec['theta']),
                        names=np.array([g.name for g in W.groups]), R=S.R, D=json.dumps(D),
                        states=np.array([b.state for b in B]), region=os.environ.get('REGION', 'region2.npz'), t_end=np.array([b.t_end for b in B]))
