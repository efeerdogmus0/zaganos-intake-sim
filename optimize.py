# Funnel Ittirici profil optimizasyonu, iki asama (Optuna TPE). GitHub Actions'ta calisir: her parti eval.yml ile
# 19 makinede degerlendirilir.
#   1. asama: topu kacirmayan duvar (alma orani en yuksek).
#   2. asama: alma orani en iyiden en fazla TOL (1 puan) geride olanlar arasinda topu en hizli alan duvar.
#   Dogrulama: hic gorulmemis sahne/tohumlar; kazanan = en iyi orana TOL icinde olanlardan, hepsinin aldigi toplarda
#   ortalama alma suresi en kisa olan. Sonda kazanan icin video.yml tetiklenir.
import json, os, subprocess, time, collections
import optuna

REPO = os.environ['GITHUB_REPOSITORY']
NB1, NB2, B = int(os.environ.get('NB1', '13')), int(os.environ.get('NB2', '12')), int(os.environ.get('BATCH', '20'))
TOL, TFAIL = float(os.environ.get('TOL', '0.01')), 4.0
# Funnel Ittirici: yan silüet CAD/EnicPleyt ile ayni ve sabit (giris egimi dahil); agiz EnicPleyt hizasinda (83 mm).
# Degisen: her taraf 5 kontrol noktali monoton egri (f1..f5) + duvar egimi (derece).
SPACE = {f'f{i}_{s}': (0.0, 1.0) for s in 'np' for i in range(1, 6)}
SPACE.update(tilt_n=(-30.0, 30.0), tilt_p=(-30.0, 30.0))
WARM = json.load(open('baslangic_hiz.json'))           # onceki optimizasyonun (CAD 7) en iyileri, T394 basta
NSCENE, SEEDS = int(os.environ.get('NSCENE', '100')), os.environ.get('SEEDS', '1 2 3')
REGION = os.environ.get('REGION', 'region2_v8.npz')
SUM = os.environ.get('GITHUB_STEP_SUMMARY', 'ozet.md')

def gh(*a, tries=8):
    for k in range(tries):
        r = subprocess.run(['gh', *a], capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout
        print('gh hata, tekrar:', a[:3], r.stderr[-300:], flush=True); time.sleep(15 * (k + 1))
    raise RuntimeError(r.stderr)

def run_eval(cands, tag, seeds=None, scene_set=42, nscene=None):
    seeds = seeds or SEEDS; nscene = nscene or NSCENE
    if os.environ.get('DRY'):                         # kuru deneme: sahte sonuclar (mantik testi)
        import random
        rows = []
        for c in cands:
            rg = random.Random(hash(c['name']) % 10000)
            for i in range(30):
                rows.append(dict(id=f"{c['name']}|rnd{i:02d}|s{4 if 'dogrulama' in tag else 1}", did=c['name'],
                                 balls=[dict(state='alindi' if rg.random() < 0.95 else 'takildi', t=0.4 + rg.random())
                                        for _ in range(3)]))
        return rows
    for att in range(2):
        t = f"{os.environ.get('GITHUB_RUN_ID', 'yerel')[-6:]}-{tag}" + ('r' if att else '')   # eski kosularla karismasin
        gh('workflow', 'run', 'eval.yml', '-R', REPO, '-f', f'cands={json.dumps(cands)}', '-f', f'tag={t}',
           '-f', f'seeds={seeds}', '-f', f'scene_set={scene_set}', '-f', f'nscene={nscene}', '-f', f'region={REGION}')
        rid = None
        while rid is None:
            time.sleep(10)
            runs = json.loads(gh('run', 'list', '-R', REPO, '-w', 'eval.yml', '-L', '40', '--json', 'databaseId,displayTitle'))
            rid = next((r['databaseId'] for r in runs if r['displayTitle'] == f'eval {t}'), None)
        while json.loads(gh('run', 'view', str(rid), '-R', REPO, '--json', 'status'))['status'] != 'completed':
            time.sleep(20)
        d = f'res/{t}'
        try:
            gh('run', 'download', str(rid), '-R', REPO, '-n', f'eval-{t}', '-D', d, tries=4)
            return [json.loads(l) for l in open(f'{d}/cands.jsonl')]
        except Exception as e:
            print('eval sonucu alinamadi, tekrar:', t, e, flush=True)
    return []

def stats(rows):
    """aday -> dict(ok, n, cap, tcap: alinan toplarin ort. suresi, tpen: kacan = 4 s cezali ort. sure)"""
    a = collections.defaultdict(lambda: dict(ok=0, n=0, ts=0.0, tp=0.0))
    for r in rows:
        for b in r['balls']:
            s = a[r['did']]; s['n'] += 1
            if b['state'] in ('alindi', 'cikti'):
                s['ok'] += 1; s['ts'] += b['t']; s['tp'] += b['t']
            else:
                s['tp'] += TFAIL
    return {k: dict(ok=v['ok'], n=v['n'], cap=v['ok'] / v['n'], tcap=v['ts'] / max(v['ok'], 1), tpen=v['tp'] / v['n'])
            for k, v in a.items()}

def mm(c):
    return ' '.join(f"{k}={v:.0f}" if k.startswith('tilt') else f'{k}={v:.2f}' for k, v in c.items() if k in SPACE)

def out(s):
    with open(SUM, 'a') as f:
        f.write(s)
    print(s, end='', flush=True)

dists = {k: optuna.distributions.FloatDistribution(*v) for k, v in SPACE.items()}
log, ST = [], {}                    # ST: aday adi -> (params, stats)

def batch(study, nb, objective, cons_thr=None, extra=()):
    trials = [study.ask(dists) for _ in range(B)]
    cands = [dict(name=f'T{t.number:03d}{"h" if cons_thr is not None else ""}', **t.params) for t in trials]
    cands += list(extra)
    st = stats(run_eval(cands, f'b{nb:02d}'))
    for t, c in zip(trials, cands):
        s = st.get(c['name'], dict(ok=0, n=1, cap=0.0, tcap=TFAIL, tpen=TFAIL))
        ST[c['name']] = (t.params, s)
        if cons_thr is not None:
            t.set_user_attr('c', cons_thr - s['cap'])
        study.tell(t, objective(s))
        log.append(dict(name=c['name'], asama=2 if cons_thr is not None else 1, **s, **t.params))
    for c in extra:
        if c['name'] in st:
            ST[c['name']] = ({k: v for k, v in c.items() if k in SPACE}, st[c['name']])
            log.append(dict(name=c['name'], asama=0, **st[c['name']]))
    json.dump(log, open('opt_log.json', 'w'), indent=1)
    return st

# ---------------- 1. asama: alma orani
s1 = optuna.create_study(direction='maximize', storage='sqlite:///opt.db', study_name='alma', load_if_exists=True,
                         sampler=optuna.samplers.TPESampler(multivariate=True, seed=0, n_startup_trials=40))
for p in WARM.values():
    s1.enqueue_trial(p)
out('# Funnel Ittirici optimizasyonu (CAD 8)\n\n## 1. asama: topu kacirmayan duvar\n\n'
    '| parti | en iyi | alma | ort. alma suresi |\n|---|---|---|---|\n')
for nb in range(NB1):
    st = batch(s1, nb, lambda s: s['cap'], extra=[dict(name='K00_CAD', cad=True)] if nb == 0 else ())
    if nb == 0 and 'K00_CAD' in st:
        out(f"| CAD (8) oldugu gibi | | {st['K00_CAD']['cap']:.1%} | {st['K00_CAD']['tcap']:.3f} s |\n")
    bt = s1.best_trial; bs = ST[f'T{bt.number:03d}'][1]
    out(f"| {nb} | T{bt.number:03d} | {bt.value:.1%} | {bs['tcap']:.3f} s |\n")

# ---------------- 2. asama: en iyiye TOL icinde olanlar arasinda en hizli
best1 = s1.best_value; thr = best1 - TOL
s2 = optuna.create_study(direction='minimize', storage='sqlite:///opt.db', study_name='hiz', load_if_exists=True,
                         sampler=optuna.samplers.TPESampler(multivariate=True, seed=1, n_startup_trials=10,
                                                            constraints_func=lambda t: [t.user_attrs.get('c', 1.0)]))
for nm, (p, s) in ST.items():                  # 1. asamanin butun sonuclari 2. asamanin gecmisi olur
    if nm == 'K00_CAD' or set(p) != set(SPACE):
        continue
    s2.add_trial(optuna.trial.create_trial(params=p, distributions=dists, value=s['tpen'],
                                           user_attrs={'c': thr - s['cap']}, system_attrs={'constraints': [thr - s['cap']]}))
out(f'\n## 2. asama: alma orani >= {thr:.1%} olanlar arasinda en hizli\n\n'
    '| parti | en hizli uygun | alma | ort. alma suresi | cezali ort. |\n|---|---|---|---|---|\n')
for nb in range(NB1, NB1 + NB2):
    batch(s2, nb, lambda s: s['tpen'], cons_thr=thr)
    feas = [(nm, s) for nm, (p, s) in ST.items() if nm != 'K00_CAD' and s['cap'] >= thr]
    if feas:
        nm, s = min(feas, key=lambda kv: kv[1]['tpen'])
        out(f"| {nb} | {nm} | {s['cap']:.1%} | {s['tcap']:.3f} s | {s['tpen']:.3f} s |\n")

# ---------------- dogrulama: hic gorulmemis sahne seti (777), tohum 4-6
pool = [(nm, p, s) for nm, (p, s) in ST.items() if nm != 'K00_CAD']
top_cap = sorted(pool, key=lambda r: (-r[2]['cap'], r[2]['tpen']))[:8]
top_fast = sorted([r for r in pool if r[2]['cap'] >= thr], key=lambda r: r[2]['tpen'])[:8]
fin = {}
for nm, p, s in top_cap + top_fast:
    fin.setdefault(nm, p)
fin.setdefault('T394_onceki', WARM['T394'])
cands = [dict(name=nm, **p) for nm, p in fin.items()] + [dict(name='K00_CAD', cad=True)]
rows = run_eval(cands, 'dogrulama', seeds='4 5 6', scene_set=777, nscene=NSCENE)
val = stats(rows)
bestv = max(v['cap'] for k, v in val.items() if k != 'K00_CAD')
F = [k for k, v in val.items() if k != 'K00_CAD' and v['cap'] >= bestv - TOL]
# adil hiz karsilastirmasi: F'deki adaylarin HEPSININ aldigi toplarda ortalama sure
bt = collections.defaultdict(dict)
for r in rows:
    for j, b in enumerate(r['balls']):
        if b['state'] in ('alindi', 'cikti'):
            bt[(r['id'].split('|', 1)[1], j)][r['did']] = b['t']
common = [v for v in bt.values() if all(k in v for k in F)]
paired = {k: sum(v[k] for v in common) / max(len(common), 1) for k in F}
win = min(F, key=lambda k: paired[k])
topc = max(F, key=lambda k: (val[k]['cap'], -paired[k]))
rep = []
for c in cands:
    v = val.get(c['name'], dict(ok=0, n=1, cap=0, tcap=TFAIL, tpen=TFAIL))
    rep.append(dict(name=c['name'], **v, esit_kume=c['name'] in F, ortak_sure=paired.get(c['name']),
                    kazanan=c['name'] == win, **{k: x for k, x in c.items() if k in SPACE}))
rep.sort(key=lambda r: (-r['cap'], r['tpen']))
json.dump(dict(kazanan=win, en_yuksek_oran=topc, esik=bestv - TOL, ortak_top=len(common), adaylar=rep),
          open('dogrulama.json', 'w'), indent=1)
out(f'\n## Dogrulama (yeni 100 sahne x tohum 4-6)\n\nEn iyi oran {bestv:.1%}; {bestv - TOL:.1%} ve uzeri "esit" sayildi '
    f'({len(F)} aday). Hiz, bu adaylarin hepsinin aldigi {len(common)} topta karsilastirildi.\n\n'
    '| aday | alma | ort. alma suresi | ortak toplarda sure | cezali ort. | not |\n|---|---|---|---|---|---|\n')
for r in rep:
    out(f"| {r['name']} | {r['cap']:.1%} ({r['ok']}/{r['n']}) | {r['tcap']:.3f} s | "
        f"{'' if r['ortak_sure'] is None else format(r['ortak_sure'], '.3f') + ' s'} | {r['tpen']:.3f} s | "
        f"{'KAZANAN' if r['kazanan'] else ('esit oran' if r['esit_kume'] else '')} |\n")

# ---------------- video: CAD (8) ve kazanan, gerekirse en yuksek oranli aday; dogrulama sahneleri birebir
try:
    sc = collections.defaultdict(dict)
    for r in rows:
        ks = r['id'].split('|')
        tag = f"v{int(ks[1][3:])}s{ks[2][1:]}"
        ok = [b['state'] in ('alindi', 'cikti') for b in r['balls']]
        sc[tag][r['did']] = (sum(ok), len(ok), max([b['t'] for b, o in zip(r['balls'], ok) if o] or [TFAIL]))
    full = lambda d, k: k in d and d[k][0] == d[k][1]
    lose = sorted([t for t, d in sc.items() if full(d, win) and 'K00_CAD' in d and d['K00_CAD'][1] >= 3],
                  key=lambda t: (sc[t]['K00_CAD'][0] - sc[t]['K00_CAD'][1], sc[t][win][2]))[:2]
    scenes = []
    for t in lose:
        scenes += [f'K00_CAD:{t}', f'{win}:{t}']
    vc = [dict(name=win, **fin[win]), dict(name='K00_CAD', cad=True)]
    if topc != win:
        fast = sorted([t for t, d in sc.items() if full(d, win) and full(d, topc) and d[win][1] >= 3],
                      key=lambda t: sc[t][win][2] - sc[t][topc][2])[:1]
        for t in fast:
            scenes += [f'{topc}:{t}', f'{win}:{t}']
        vc.append(dict(name=topc, **fin[topc]))
    vw = next(r for r in rep if r['name'] == win); vk = next(r for r in rep if r['name'] == 'K00_CAD')
    vc.append(dict(name='_ozet', lines=[
        f'Yeni 100 sahne × 3 fizik tohumu = {vw["n"]} top',
        f'{win}: %{vw["cap"] * 100:.1f} alma | ort. alma süresi {vw["tcap"]:.2f} s',
        f'CAD (8) olduğu gibi: %{vk["cap"] * 100:.1f} | ort. {vk["tcap"]:.2f} s',
        f'Kazanan: en iyi orana 1 puan yakın {len(F)} aday içinde en hızlı']))
    if os.environ.get('DRY'):
        raise RuntimeError('kuru deneme: video yok ' + ' '.join(scenes))
    gh('workflow', 'run', 'video.yml', '-R', REPO, '-f', f'scenes={" ".join(scenes)}', '-f', f'region={REGION}',
       '-f', 'assemble=assemble_auto.py', '-f', 'out=ZAGANOS_hiz_optimizasyonu.mp4', '-f', 'chunks=5',
       '-f', 'samples=8', '-f', f'cands={json.dumps(vc)}')
    out(f'\nVideo tetiklendi: {" ".join(scenes)}\n')
except Exception as e:
    out(f'\nVideo tetiklenemedi: {e}\n')
print(json.dumps(rep[:6], indent=1))
