# Sonraki tarama turlari (batch3.py bu dosyadan okur)
from batch3 import suite, SINGLES
import sim3 as S

XM = S.X_MOUTH
G = lambda *zs: [(z, 'G') for z in zs]
# CAD huni seklinin duz (zemine kadar dikey) duvarli parametrik esi
FUN_NEG = [(XM, 0.067), (-0.1325, 0.056), (-0.1175, 0.050), (-0.1025, 0.0442), (-0.0875, 0.0387), (-0.0725, 0.0365)]
FUN_POS = [(XM, 0.074), (-0.1325, 0.0586), (-0.1175, 0.0488), (-0.1025, 0.0434), (-0.0875, 0.0385), (-0.0725, 0.0365)]
SMOOTH = dict(neg=FUN_NEG, pos=FUN_POS)
STRAIGHT = [(XM, 0.0365)]                      # huni yok: kanal hizasinda duz duvar (on yuzu dayama gibi calisir)

DESIGNS = {
    # --- referanslar (1. turun en iyileri, CAD hunisi)
    'A0 GGG-m2 CAD huni': (dict(layout='GGG', mec2=True), None),
    'A1 CTR4-m2 CAD huni': (dict(layout='CTR4', mec2=True), (0.15, 0.30)),
    # --- B: sadece huni baskilari duz duvarli (sekil ayni)
    'B1 GGG-m2 duz huni': (dict(layout='GGG', mec2=True, funnel=SMOOTH), None),
    'B2 CTR4-m2 duz huni': (dict(layout='CTR4', mec2=True, funnel=SMOOTH), (0.15, 0.30)),
    'B3 CAD-m2 duz huni': (dict(layout='CAD', mec2=True, funnel=SMOOTH), (0.15, 0.30)),
    'B4 GGG-m1 duz huni': (dict(layout='GGG', funnel=SMOOTH), None),
    'B5 CAD-m1 duz huni': (dict(layout='CAD', funnel=SMOOTH), (0.15, 0.30)),
    # --- C: tek tarafli agiz: (-) tarafta huni yok, duz duvar + agza kadar mecanum
    'C1 tek tarafli, + CAD huni': (dict(layout=G(-0.012, 0.012, 0.0295, 0.047), mecz=[-0.0765, -0.055, -0.0335, 0.076],
                                        funnel=dict(neg=STRAIGHT)), None),
    'C2 tek tarafli, + duz huni': (dict(layout=G(-0.012, 0.012, 0.0295, 0.047), mecz=[-0.0765, -0.055, -0.0335, 0.076],
                                        funnel=dict(neg=STRAIGHT, pos=FUN_POS)), None),
    'C3 tek tarafli, + ic mecanum yok': (dict(layout=G(-0.012, 0.012, 0.0295, 0.047, 0.0645), mecz=[-0.0765, -0.055, -0.0335],
                                              funnel=dict(neg=STRAIGHT)), None),
    'C4 tek tarafli, 2 ek mecanum': (dict(layout=G(-0.0295, -0.012, 0.012, 0.0295, 0.047), mecz=[-0.0765, -0.055, 0.076],
                                          funnel=dict(neg=STRAIGHT)), None),
    'C5 tek tarafli (+ tarafta)': (dict(layout=G(-0.047, -0.0295, -0.012, 0.012), mecz=[0.0765, 0.055, 0.0335, -0.076],
                                        funnel=dict(pos=STRAIGHT)), None),
}
PAIRS = {'c1': (-0.037, 0.037), 'c2': (0.0, 0.071), 'c3': (0.0, -0.071), 'c4': (0.037, 0.108), 'c5': (-0.037, -0.108),
         'c6': (-0.071, 0.071)}
MULTI2 = {k: [(-0.30, z, 0) for z in zs] for k, zs in PAIRS.items()}
MULTI2.update({
    'u1': [(-0.30, z, 0) for z in (-0.08, 0.0, 0.08)],
    'u2': [(-0.30, z, 0) for z in (-0.071, 0.0, 0.071)],
    'b1': [(-0.30, z, 0) for z in (-0.15, -0.075, 0.0, 0.075, 0.15)],
    'b2': [(-0.30, z, 0) for z in (-0.142, -0.071, 0.0, 0.071, 0.142)],
    'k1': [(-0.30, -0.08, 0), (-0.34, 0.0, 0), (-0.38, 0.08, 0)],
})

def round2():
    J = []
    for name, (D, boots) in DESIGNS.items():
        for mb in (boots or (0.15,)):
            did = f'{name}@b{mb}'
            J += suite(did, D, dict(mu_boot=mb), seed=1, multi=MULTI2)
            J += suite(did, D, dict(mu_boot=mb), seed=2, singles=(), multi=MULTI2)
    return J

ROUNDS = {'r2': round2}

# ---------------------------------------------------------------- 3. tur: duzeltilmis top-top surtunmesiyle
# en iyilerin yeniden siralanmasi + kazanan adayin dogrulanmasi
import math, random

REFS = {
    'REF CAD oldugu gibi': (dict(layout='CAD', mec='cad'), (0.15, 0.30)),
    'IN sadece mecanum iceri': (dict(layout='CAD'), (0.15, 0.30)),
}
SENS = {   # ad: (parametre degisikligi, robot hizi)
    'duvar0.15': (dict(mu_hard=0.15), 0.5), 'duvar0.50': (dict(mu_hard=0.50), 0.5),
    'tpu0.40': (dict(mu_tpu=0.40), 0.5), 'tpu0.80': (dict(mu_tpu=0.80), 0.5),
    'zemin0.40': (dict(mu_floor=0.40), 0.5), 'zemin0.70': (dict(mu_floor=0.70), 0.5),
    'sert0.6': (dict(stiff=0.6), 0.5), 'sert3.0': (dict(stiff=3.0), 0.5),
    'top25g': (dict(mass=0.025), 0.5), 'gecko0.45': (dict(mu_wheel=0.45), 0.5),
    'hiz0.25': ({}, 0.25), 'hiz1.0': ({}, 1.0),
    'aci+20': ({}, [0.5 * math.cos(math.radians(20)), 0.0, 0.5 * math.sin(math.radians(20))]),
    'aci-20': ({}, [0.5 * math.cos(math.radians(20)), 0.0, -0.5 * math.sin(math.radians(20))]),
}
MULTI3 = {k: MULTI2[k] for k in ('c1', 'c2', 'c3', 'c6', 'u1', 'u2', 'b1', 'b2', 'k1')}

def scenes(n=60):
    rng = random.Random(42); out = []
    while len(out) < n:
        k = rng.choice((2, 3, 3, 4, 5)); pts = []; tries = 0
        while len(pts) < k and tries < 300:
            tries += 1
            z = rng.uniform(-0.155, 0.155); x = rng.uniform(-0.42, -0.30)
            if all((z - q[1]) ** 2 + (x - q[0]) ** 2 > 0.074 ** 2 for q in pts):
                pts.append((round(x, 4), round(z, 4), 0))
        if len(pts) == k:
            out.append(pts)
    return out

def round3():
    J = []
    top = {k: DESIGNS[k] for k in ('C1 tek tarafli, + CAD huni', 'C4 tek tarafli, 2 ek mecanum', 'B1 GGG-m2 duz huni',
                                   'A0 GGG-m2 CAD huni')}
    top.update(REFS)
    for name, (D, boots) in top.items():                      # (a) ayni 35 testlik takim
        for mb in (boots or (0.15,)):
            did = f'{name}@b{mb}'
            J += suite(did, D, dict(mu_boot=mb), seed=1, multi=MULTI2)
            J += suite(did, D, dict(mu_boot=mb), seed=2, singles=(), multi=MULTI2)
    SC = scenes()
    for name in ('C1 tek tarafli, + CAD huni', 'C4 tek tarafli, 2 ek mecanum', 'B1 GGG-m2 duz huni',
                 'IN sadece mecanum iceri', 'REF CAD oldugu gibi'):   # (b) rastgele sahneler
        D = top[name][0]
        for i, balls in enumerate(SC):
            J.append(dict(id=f'{name}@b0.15|rnd{i:02d}', did=f'{name}@b0.15', D=D, p=dict(mu_boot=0.15), test=f'rnd{i:02d}',
                          balls=balls, v=0.5, t_max=4.0, seed=100 + i))
    for name in ('C1 tek tarafli, + CAD huni', 'C4 tek tarafli, 2 ek mecanum'):
        D = top[name][0]
        for sn, (p, v) in SENS.items():                       # (c) belirsiz degerlere duyarlilik
            J += suite(f'{name}~{sn}@b0.15', D, dict(p), seed=1, multi=MULTI3, v=v)
        full = suite(f'{name}~tamyol@b0.15', D, {}, seed=1, multi=MULTI3)   # (d) shooter cikisina kadar
        for j in full:
            j['io'] = False
        J += full
    return J

ROUNDS['r3'] = round3


# ---------------------------------------------------------------- 4. tur: yuvarlanma direnci (0.03) eklendi;
# kazanan aday + kaygan dayama duvari secenegi + referanslar; kisaltilmis duyarlilik
C1 = DESIGNS['C1 tek tarafli, + CAD huni'][0]
RR = 0.03
SENS4 = {
    'tpu0.40': (dict(mu_tpu=0.40), 0.5), 'tpu0.80': (dict(mu_tpu=0.80), 0.5), 'duvar0.50': (dict(mu_hard=0.50), 0.5),
    'sert3.0': (dict(stiff=3.0), 0.5), 'gecko0.45': (dict(mu_wheel=0.45), 0.5), 'top25g': (dict(mass=0.025), 0.5),
    'hiz0.25': ({}, 0.25), 'hiz1.0': ({}, 1.0), 'rr0': (dict(c_rr=0.0), 0.5), 'rr0.06': (dict(c_rr=0.06), 0.5),
}
MULTI4 = {k: MULTI2[k] for k in ('c1', 'u1', 'b1', 'k1')}

def round4():
    J = []
    SC = scenes()
    cand = {'C1 tek tarafli agiz': (C1, dict(c_rr=RR)),
            'C1L tek tarafli agiz + kaygan dayama': (C1, dict(c_rr=RR, mu_back=0.12)),
            'IN sadece mecanum iceri': (REFS['IN sadece mecanum iceri'][0], dict(c_rr=RR, mu_boot=0.15)),
            'REF CAD oldugu gibi': (REFS['REF CAD oldugu gibi'][0], dict(c_rr=RR, mu_boot=0.15))}
    for name, (D, p) in cand.items():
        did = f'{name}@b0.15'
        J += suite(did, D, p, seed=1, multi=MULTI2)
        J += suite(did, D, p, seed=2, singles=(), multi=MULTI2)
        for i, balls in enumerate(SC):
            J.append(dict(id=f'{did}|rnd{i:02d}', did=did, D=D, p=p, test=f'rnd{i:02d}', balls=balls, v=0.5, t_max=4.0,
                          seed=100 + i))
    for name in ('C1 tek tarafli agiz', 'C1L tek tarafli agiz + kaygan dayama'):
        D, p0 = cand[name]
        for sn, (p, v) in SENS4.items():
            pp = dict(p0); pp.update(p)
            J += suite(f'{name}~{sn}@b0.15', D, pp, seed=1, singles=(-0.15, -0.09, 0.0, 0.09, 0.15), multi=MULTI4, v=v)
        full = suite(f'{name}~tamyol@b0.15', D, dict(p0), seed=1, multi=MULTI3)
        for j in full:
            j['io'] = False
        J += full
    return J

ROUNDS['r4'] = round4
