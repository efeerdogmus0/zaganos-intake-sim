# Funnel Ittirici profil optimizasyonu (Optuna TPE). GitHub Actions'ta calisir: her parti eval.yml ile 19 makinede
# degerlendirilir. Sonda en iyiler hic gorulmemis sahne/tohumlarla dogrulanir.
import json, os, subprocess, time, collections
import optuna

REPO = os.environ['GITHUB_REPOSITORY']
NB, B = int(os.environ.get('NBATCH', '15')), int(os.environ.get('BATCH', '20'))
# Funnel Ittirici: yan silüet CAD/EnicPleyt ile ayni ve sabit (giris egimi dahil); agiz EnicPleyt hizasinda (83 mm).
# Degisen: her taraf 5 kontrol noktali monoton egri (f1..f5: o noktada kalan daralmanin orani) + duvar egimi (derece).
SPACE = {f'f{i}_{s}': (0.0, 1.0) for s in 'np' for i in range(1, 6)}
SPACE.update(tilt_n=(-30.0, 30.0), tilt_p=(-30.0, 30.0))
BASE = json.load(open('baslangic_adaylari.json'))      # CADfit, T253fit, K14fit, Konikfit
NSCENE, SEEDS = int(os.environ.get('NSCENE', '100')), os.environ.get('SEEDS', '1 2 3')
REGION = os.environ.get('REGION', 'region2_v7.npz')
sym = lambda b: {f'{k}_{s}': v for k, v in b.items() for s in 'np'}
SUM = os.environ.get('GITHUB_STEP_SUMMARY', 'ozet.md')

def gh(*a, tries=8):
    for k in range(tries):
        r = subprocess.run(['gh', *a], capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout
        print('gh hata, tekrar:', a[:3], r.stderr[-300:], flush=True); time.sleep(15 * (k + 1))
    raise RuntimeError(r.stderr)

def evaluate(cands, tag, seeds=None, scene_set=42, nscene=None):
    seeds = seeds or SEEDS; nscene = nscene or NSCENE
    gh('workflow', 'run', 'eval.yml', '-R', REPO, '-f', f'cands={json.dumps(cands)}', '-f', f'tag={tag}',
       '-f', f'seeds={seeds}', '-f', f'scene_set={scene_set}', '-f', f'nscene={nscene}', '-f', f'region={REGION}')
    rid = None
    while rid is None:
        time.sleep(10)
        runs = json.loads(gh('run', 'list', '-R', REPO, '-w', 'eval.yml', '-L', '40', '--json', 'databaseId,displayTitle'))
        rid = next((r['databaseId'] for r in runs if r['displayTitle'] == f'eval {tag}'), None)
    while json.loads(gh('run', 'view', str(rid), '-R', REPO, '--json', 'status'))['status'] != 'completed':
        time.sleep(20)
    d = f'res/{tag}'
    gh('run', 'download', str(rid), '-R', REPO, '-n', f'eval-{tag}', '-D', d)
    ok, tot = collections.Counter(), collections.Counter()
    for l in open(f'{d}/cands.jsonl'):
        r = json.loads(l)
        for b in r['balls']:
            tot[r['did']] += 1; ok[r['did']] += b['state'] in ('alindi', 'cikti')
    return {k: (ok[k], tot[k]) for k in tot}

def mm(c):
    return ' '.join(f"{k}={v:.0f}" if k.startswith('tilt') else f'{k}={v:.2f}' for k, v in c.items() if k in SPACE)

study = optuna.create_study(direction='maximize', storage='sqlite:///opt.db', study_name='funnel', load_if_exists=True,
                            sampler=optuna.samplers.TPESampler(multivariate=True, seed=0, n_startup_trials=60))
for b in BASE.values():
    study.enqueue_trial(b)
dists = {k: optuna.distributions.FloatDistribution(*v) for k, v in SPACE.items()}
log = []
with open(SUM, 'a') as f:
    f.write('# Funnel Ittirici optimizasyonu\n\n| parti | en iyi | oran |\n|---|---|---|\n')
for nb in range(NB):
    trials = [study.ask(dists) for _ in range(B)]
    cands = [dict(name=f'T{t.number:03d}', **t.params) for t in trials]
    if nb == 0:
        cands.append(dict(name='K00_CAD', cad=True))
    res = evaluate(cands, f'b{nb:02d}')
    for t in trials:
        o, n = res[f'T{t.number:03d}']; study.tell(t, o / n)
        log.append(dict(trial=t.number, score=o / n, ok=o, n=n, **t.params))
    if 'K00_CAD' in res:
        o, n = res['K00_CAD']; log.append(dict(trial='K00_CAD', score=o / n, ok=o, n=n))
    json.dump(log, open('opt_log.json', 'w'), indent=1)
    bt = study.best_trial
    with open(SUM, 'a') as f:
        f.write(f'| {nb} | T{bt.number:03d} {mm(bt.params)} | {bt.value:.1%} |\n')
    print('parti', nb, 'en iyi', bt.number, round(bt.value, 4), flush=True)

# dogrulama: hic gorulmemis sahne seti (777) ve 3 yeni tohum; ilk 6 + referanslar
done = [t for t in study.trials if t.value is not None]
top = sorted(done, key=lambda t: -t.value)[:8]
cands = [dict(name=f'T{t.number:03d}', **t.params) for t in top]
cands += [dict(name='CADfit', **BASE['CADfit']), dict(name='T253fit', **BASE['T253fit']), dict(name='K00_CAD', cad=True)]
val = evaluate(cands, 'dogrulama', seeds='4 5 6', scene_set=777, nscene=NSCENE)
rep = []
for c in cands:
    o, n = val[c['name']]
    tr = next((t.value for t in top if f'T{t.number:03d}' == c['name']), None)
    rep.append(dict(name=c['name'], val=o / n, ok=o, n=n, train=tr, **{k: v for k, v in c.items() if k in SPACE}))
rep.sort(key=lambda r: -r['val'])
json.dump(rep, open('dogrulama.json', 'w'), indent=1)
with open(SUM, 'a') as f:
    f.write('\n## Dogrulama (yeni sahneler, tohum 4-6)\n\n| aday | dogrulama | egitim | profil |\n|---|---|---|---|\n')
    for r in rep:
        f.write(f"| {r['name']} | {r['val']:.1%} ({r['ok']}/{r['n']}) | {'' if r['train'] is None else format(r['train'], '.1%')} | {mm(r)} |\n")
print(json.dumps(rep, indent=1))
