# Bir senaryoyu kayitli kostur (video icin): PYTHONPATH=pylib:. python3.13 record3.py <cikti.npz> <tasarim> <test> [io=1] [tohum]
#   tasarim: REF | IN | C1 | C1L     test: rounds.MULTI2 anahtari | rndNN | tek+0.090
import sys, json
import numpy as np
import sim3 as S, rounds

CAND = {'REF': (rounds.REFS['REF CAD oldugu gibi'][0], dict(c_rr=rounds.RR, mu_boot=0.15)),
        'IN': (rounds.REFS['IN sadece mecanum iceri'][0], dict(c_rr=rounds.RR, mu_boot=0.15)),
        'C1': (rounds.C1, dict(c_rr=rounds.RR)),
        'C1L': (rounds.C1, dict(c_rr=rounds.RR, mu_back=0.12))}

if __name__ == '__main__':
    out, dn, tn = sys.argv[1:4]
    io = (sys.argv[4] != '0') if len(sys.argv) > 4 else True
    D, p = CAND[dn]
    if tn.startswith('rnd'):
        balls = rounds.scenes()[int(tn[3:])]; seed = 100 + int(tn[3:])
    elif tn.startswith('tek'):
        balls = [(-0.30, float(tn[3:]), 0)]; seed = 1
    else:
        balls = rounds.MULTI2[tn]; seed = 1
    if len(sys.argv) > 5:
        seed = int(sys.argv[5])
    W = S.World('region2.npz')
    S.P.clear(); S.P.update(S.P0); S.P.update(p)
    W.set_design(D)
    B, rec = W.run(balls, intake_only=io, t_max=4.0, seed=seed, rec_dt=1 / 600)
    print(dn, tn, S.describe(B), 't_son=%.2f' % max(b.t_end for b in B))
    np.savez_compressed(out, t=np.array(rec['t']), pos=np.array(rec['pos'], dtype=object),
                        quat=np.array(rec['quat'], dtype=object), theta=np.array(rec['theta']),
                        names=np.array([g.name for g in W.groups]), R=S.R, D=json.dumps(D),
                        states=np.array([b.state for b in B]), t_end=np.array([b.t_end for b in B]))
