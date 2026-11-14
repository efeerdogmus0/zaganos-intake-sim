# Tasarim taramasi. PYTHONPATH=pylib:. python3.13 batch3.py <tur> <cikti.jsonl> [isci]
# Her is: (tasarim, belirsiz parametreler, test). Sonuclar satir satir yazilir; yarida kalirsa kaldigi yerden surer.
import sys, os, json, time, itertools, random
import numpy as np

W = None
def init():
    global W
    import sim3
    import os
    W = sim3.World(os.environ.get('REGION', 'region2.npz'))

SINGLES = (-0.15, -0.12, -0.09, -0.06, -0.03, 0.0, 0.03, 0.06, 0.09, 0.12, 0.15)
MULTI = {
    'cift': [(-0.30, -0.037, 0), (-0.30, 0.037, 0)],
    'uclu': [(-0.30, -0.08, 0), (-0.30, 0.0, 0), (-0.30, 0.08, 0)],
    'besli': [(-0.30, z, 0) for z in (-0.15, -0.075, 0.0, 0.075, 0.15)],
    'kademeli': [(-0.30, -0.08, 0), (-0.34, 0.0, 0), (-0.38, 0.08, 0)],
}

def suite(did, D, p, seed=1, singles=SINGLES, multi=MULTI, v=0.5, tag=''):
    J = []
    for z in singles:
        J.append(dict(id=f'{did}|{tag}tek{z:+.3f}|s{seed}', did=did, D=D, p=p, test=f'tek{z:+.3f}',
                      balls=[(-0.30, z, 0)], v=v, t_max=2.5, seed=seed))
    for k, b in multi.items():
        J.append(dict(id=f'{did}|{tag}{k}|s{seed}', did=did, D=D, p=p, test=k, balls=b, v=v, t_max=3.5, seed=seed))
    return J

def round1():
    J = []
    for lay, m2, ramp in itertools.product(('CAD', 'GGG', 'CTR', 'CTR4'), (False, True), ('cad', 'w37', 'fun', 'cham', 'vee')):
        D = dict(layout=lay, mec2=m2, ramp=ramp)
        for mb in ((0.15, 0.30) if lay != 'GGG' else (0.15,)):
            J += suite(f"{lay}-{'m2' if m2 else 'm1'}-{ramp}@b{mb}", D, dict(mu_boot=mb))
    # referans: CAD oldugu gibi (mecanum disari)
    for mb in (0.15, 0.30):
        J += suite(f'REF-CADyonu@b{mb}', dict(layout='CAD', mec='cad', ramp='cad'), dict(mu_boot=mb))
    return J

ROUNDS = {'r1': round1}

def run_job(j):
    import sim3
    sim3.P.clear(); sim3.P.update(sim3.P0); sim3.P.update(j['p'])
    W.set_design(j['D'])
    t0 = time.time()
    B, _ = W.run([tuple(b) for b in j['balls']], robot_v=j['v'], intake_only=j.get('io', True), t_max=j['t_max'],
                 seed=j['seed'])
    return dict(id=j['id'], did=j['did'], test=j['test'], D=j['D'], p=j['p'], seed=j['seed'], v=j['v'],
                calc=round(time.time() - t0, 1),
                balls=[dict(z=round(float(b.x0[2]), 4), state=b.state, t=round(float(b.t_end), 3),
                            pos=[round(float(x), 4) for x in b.x],
                            v=None if b.exit_v is None else round(float(np.linalg.norm(b.exit_v)), 2),
                            touch=[k for k, _ in sorted(b.touch.items(), key=lambda kv: -kv[1])[:4]]) for b in B])

JOB_TMO = float(os.environ.get('JOB_TMO', '900'))   # tek is icin duvar saati siniri (s)

def fail_rec(j, why):
    """Coken / takilan is: toplari 'hata' (alinmadi) say, kosuyu durdurma."""
    return dict(id=j['id'], did=j['did'], test=j['test'], D=j['D'], p=j['p'], seed=j['seed'], v=j['v'], calc=None,
                err=why, balls=[dict(z=round(float(b[1]), 4), state='hata', t=None, pos=None, v=None, touch=[])
                                for b in j['balls']])

def _kill(ex):
    for pr in list(getattr(ex, '_processes', {}).values()):
        try:
            pr.kill()
        except Exception:
            pass
    ex.shutdown(wait=False, cancel_futures=True)

def run_all(J, nproc, fh, t0):
    """Pool yerine: olen isciyi fark eder (BrokenProcessPool), takilan isi zaman asimiyla keser.
    Cokme aninda ucustaki isler supheli listesine gider; onlar sonda tek tek, ayri iscide denenir."""
    from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
    from concurrent.futures.process import BrokenProcessPool
    queue, suspect, ndone, N = list(J), [], 0, len(J)
    def emit(r):
        nonlocal ndone
        fh.write(json.dumps(r, ensure_ascii=False) + '\n'); fh.flush(); ndone += 1
        if ndone % 25 == 0 or ndone == N:
            print(f'[{ndone}/{N}] {time.time() - t0:.0f} s', flush=True)
    while queue:
        ex = ProcessPoolExecutor(nproc, initializer=init); fly = {}
        try:
            while queue or fly:
                while queue and len(fly) < nproc:
                    j = queue.pop(); fly[ex.submit(run_job, j)] = (j, time.time())
                dn, _ = wait(fly, timeout=10, return_when=FIRST_COMPLETED)
                for f in dn:
                    j, _ = fly[f]
                    if isinstance(f.exception(), BrokenProcessPool):
                        raise f.exception()
                    del fly[f]
                    emit(f.result() if f.exception() is None else fail_rec(j, repr(f.exception())[:200]))
                late = [f for f, (j, ts) in fly.items() if time.time() - ts > JOB_TMO]
                if late:
                    raise TimeoutError
        except (BrokenProcessPool, TimeoutError) as e:
            print('isci kaybi/zaman asimi:', type(e).__name__, len(fly), 'is supheli', flush=True)
            for f, (j, _) in fly.items():
                if f.done() and f.exception() is None:
                    emit(f.result())
                else:
                    suspect.append(j)
            _kill(ex); continue
        ex.shutdown()
    for j in suspect:                      # tek basina, ayri iscide son deneme
        ex = ProcessPoolExecutor(1, initializer=init)
        f = ex.submit(run_job, j)
        try:
            emit(f.result(timeout=JOB_TMO)); ex.shutdown()
        except Exception as e:
            print('HATA', j['id'], type(e).__name__, flush=True)
            emit(fail_rec(j, type(e).__name__)); _kill(ex)

if __name__ == '__main__':
    rnd, out = sys.argv[1], sys.argv[2]
    nproc = int(sys.argv[3]) if len(sys.argv) > 3 else os.cpu_count()
    if rnd not in ROUNDS:
        import rounds                      # sonraki turlar ayri dosyada tanimlanir
        ROUNDS.update(rounds.ROUNDS)
    J = ROUNDS[rnd]()
    done = set()
    if os.path.exists(out):
        done = {json.loads(l)['id'] for l in open(out) if l.strip()}
    J = [j for j in J if j['id'] not in done]
    sh = os.environ.get('SHARD')          # 'i/n': is listesinin sadece i. parcasi (GitHub Actions icin)
    if sh:
        i, n = map(int, sh.split('/'))
        J = sorted(J, key=lambda j: j['id'])[i::n]
    random.Random(0).shuffle(J)
    print(len(J), 'is,', len(done), 'onceden bitmis', flush=True)
    t0 = time.time()
    with open(out, 'a') as fh:
        run_all(J, nproc, fh, t0)
    print('bitti', round(time.time() - t0), 's', flush=True)
