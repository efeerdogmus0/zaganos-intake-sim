# Robot CAD'inden fizik modeli: sabit ucgen geometri + motorla donen tekerlek gruplari.
# Koordinatlar: CAD (metre), y yukari, robot onu -x. Zemin y = 0.
#
# Varsayimlar (olculmedi; shooter hesaplayicisindaki "current" preset ile ayni):
#   top 71.1 mm / 25 g, ici bos kabuk (I = 2/3 m R^2), kuvvet-ezilme egrisi 12 N @ 4 mm ...
#   intake 1150 RPM motor 25T->20T, feeder 32 mm gecko ayni yuzey hizi (3.61 m/s),
#   flywheel 96 mm @ 1450 RPM, sushi hood 1" @ 1450 x 3.75 RPM.
import re
import numpy as np

BALL_R = 0.071 / 2 + 0.0000  # 2.8 in = 71.12 mm
BALL_R = 0.03556
BALL_M = 0.025
BALL_I = 2.0 / 3.0 * BALL_M * BALL_R ** 2
FLOOR_Y = 0.0
G = np.array([0.0, -9.80665, 0.0])

# Top ezilme kuvveti (N) - ezilme (m); preset forceCurve
CURVE_D = np.array([0.0, 0.004, 0.008, 0.012, 0.030])
CURVE_F = np.array([0.0, 12.0, 24.0, 40.0, 130.0])

MU_WHEEL = 0.65      # gecko / sushi / rhino / TPU
MU_HARD = 0.30       # baski, aluminyum, polikarbon
MU_FLOOR = 0.55      # sahadaki kopuk zemin

RPM = 2 * np.pi / 60

def rpm_presets():
    return {
        'intake': 1150 * 25 / 20,
        'feeder': 1150 * 30 / 16,
        'flywheel': 1450.0,
        'sushi': 1450.0 * 3.75,
    }

ROT_PAT = re.compile(r'Gecko|Bootleg|Roller_TPU|Rhino|Sushi|HoodTeker|TekerSağ|TekerSol')

def pca_axis(v):
    c = v.mean(0)
    w, vec = np.linalg.eigh(np.cov((v - c).T))
    return c, vec[:, -1]

def cyl_fit(v, c0, a, pct=99.5):
    """Eksen (c0,a) etrafinda parcayi silindir olarak ozetle: merkez, yaricap, yari genislik."""
    t = (v - c0) @ a
    rad = np.linalg.norm((v - c0) - np.outer(t, a), axis=1)
    t0, t1 = t.min(), t.max()
    return c0 + a * (t0 + t1) / 2, float(np.percentile(rad, pct)), float((t1 - t0) / 2)

class Group:
    """Ayni milde donen parcalar. Temas yuzeyleri: silindirler ve serbest makaralar."""
    def __init__(self, name, center, axis, rpm, sign, inertia, tau_stall, w_free):
        self.name, self.c, self.a = name, np.asarray(center, float), np.asarray(axis, float) / np.linalg.norm(axis)
        if self.a[2] < 0:
            self.a = -self.a
        self.target = sign * rpm * RPM
        self.w = self.target
        self.theta = 0.0
        self.I = inertia
        self.tau_stall, self.w_free = tau_stall, w_free
        self.cyls = []      # (merkez, yaricap, yari genislik, mu, ad)
        self.rollers = []   # serbest TPU makaralar: (merkez0, eksen0, yaricap, yari uzunluk)
        self.tau_load = 0.0
        self.parts = []     # gorsellestirmede bu grupla donen CAD parcalari
        self.min_w = abs(self.w)

    def motor_torque(self):
        # hiz kontrollu motor: hedefe ulasmak icin gereken tork, motor egrisiyle sinirli
        sgn = np.sign(self.target) if self.target else 1.0
        w_dir = self.w * sgn
        avail = self.tau_stall * max(0.0, 1.0 - w_dir / self.w_free)
        want = (abs(self.target) - w_dir) * self.I / 0.004
        return sgn * float(np.clip(want, -self.tau_stall, avail))

def build(region_path):
    d = np.load(region_path, allow_pickle=True)
    names = list(d['names']); verts = list(d['verts']); faces = list(d['faces'])
    by = {n: (v.astype(np.float64), f) for n, v, f in zip(names, verts, faces)}

    def shaft(name):
        v = by[name][0]
        c, a = pca_axis(v)
        return c, a

    P = rpm_presets()
    # motor modelleri (goBILDA Yellowjacket katalog degerleri, kontrol edilmeli)
    tau_1150, w_1150 = 0.775, 1150 * RPM
    tau_6000, w_6000 = 0.144, 6000 * RPM
    groups = []
    used = set()

    # --- intake mili
    c, a = shaft('IntakeShaft')
    gi = Group('intake', c, a, P['intake'], +1, 4e-5, tau_1150 * 20 / 25, w_1150 * 25 / 20)
    groups.append(gi)
    # --- feeder milleri (ust sira) ve agiz milleri
    feeders = [('FeederShaft_2', +1), ('FeederShaft', +1), ('FeederShaft_3', +1), ('FeederShaft_1', +1),
               ('FeederShaftAğız', +1), ('FeederShaftAğız_1', -1)]
    gf = {}
    for nm, sgn in feeders:
        c, a = shaft(nm)
        g = Group(nm, c, a, P['feeder'], sgn, 1.5e-5, tau_1150 * 16 / 30, w_1150 * 30 / 16)
        groups.append(g); gf[nm] = g
    # --- shooter
    c, a = shaft('ShooterShaft')
    gs = Group('flywheel', c, a, P['flywheel'], -1, 2.5e-4, 2 * tau_6000 * 2.42 * 0.7, w_6000 / 2.42)
    groups.append(gs)

    def nearest_group(v, cands, maxd=0.03):
        cen = v.mean(0)
        best, bd = None, maxd
        for g in cands:
            r = cen - g.c
            dist = np.linalg.norm(r - (r @ g.a) * g.a)
            if dist < bd:
                best, bd = g, dist
        return best

    sushi = []
    for n, (v, f) in by.items():
        if not ROT_PAT.search(n):
            continue
        if 'Sushi' in n:
            sushi.append((n, v))
            used.add(n)
            continue
        if re.search(r'HoodTeker|TekerSağ|TekerSol', n):
            used.add(n); gs.parts.append(n)   # flywheel ici gobek parcalari: tekerlek silindirinin icinde
            continue
        if 'Rhino' in n:
            cc, r, h = cyl_fit(v, gs.c, gs.a)
            gs.cyls.append((cc, r, h, MU_WHEEL, n)); used.add(n); gs.parts.append(n); continue
        if 'Roller_TPU' in n:
            g = nearest_group(v, [gi], 0.04)
            if g is None:
                continue
            c0, ax = pca_axis(v)
            t = (v - c0) @ ax
            rad = np.linalg.norm((v - c0) - np.outer(t, ax), axis=1)
            g.rollers.append((c0, ax, float(np.percentile(rad, 99)), float((t.max() - t.min()) / 2)))
            used.add(n); g.parts.append(n); continue
        g = nearest_group(v, groups[:-1], 0.012)
        if g is None:
            continue
        g.parts.append(n)
        if len(f) < 1000:               # gecko gobek parcasi, tekerlek icinde
            used.add(n); continue
        cc, r, h = cyl_fit(v, g.c, g.a)
        g.cyls.append((cc, r, h, MU_WHEEL, n)); used.add(n)

    # sushi hood makaralari: shooter miline paralel, her biri kendi grubunda.
    # Her makara iki agdan olusur (govde + gobek); eksene gore genis yaricapli olan govdedir.
    body = {}
    for n, v in sushi:
        base = re.sub(r'_[0-9a-f]{6}$', '', n)
        r = cyl_fit(v, v.mean(0), gs.a)[1]
        if base not in body or r > body[base][2]:
            body[base] = (n, v, r)
    sushi = sorted(((n, v) for n, v, _ in body.values()), key=lambda s: s[1].mean(0)[1])
    pairs = []
    for n, v in sushi:
        cen = v.mean(0)
        for p in pairs:
            if abs(p[0][1] - cen[1]) < 0.01:
                p[1].append((n, v)); break
        else:
            pairs.append([cen, [(n, v)]])
    for i, (cen, items) in enumerate(pairs):
        allv = np.vstack([v for _, v in items])
        g = Group(f'sushi{i + 1}', allv.mean(0), gs.a, P['sushi'], +1, 6e-6,
                  2 * tau_6000 * 2.42 * 0.7 / 3.75, w_6000 / 2.42 * 3.75)
        for n, v in items:
            cc, r, h = cyl_fit(v, v.mean(0), gs.a)
            g.cyls.append((cc, r, h, MU_WHEEL, n))
        groups.append(g)
    sg = [g for g in groups if g.name.startswith('sushi')]
    for n, (v, f) in by.items():
        if 'Sushi' in n:
            min(sg, key=lambda g: abs(g.c[1] - v.mean(0)[1])).parts.append(n)

    # intake milinin tekerlek zarfi icinde kalan her sey (mil, gobek, makara cekirdegi, tasiyici,
    # ara parca) mille birlikte doner; top bunlara tekerlek/makara yuzeyinden once ulasamaz
    for n, (v, f) in by.items():
        if n in used:
            continue
        rel = v - gi.c
        t = rel @ gi.a
        if np.linalg.norm(rel - np.outer(t, gi.a), axis=1).max() < 0.0245 and np.abs(t).max() < 0.21:
            used.add(n); gi.parts.append(n)

    # --- sabit ucgenler
    tri, tri_part, part_names = [], [], []
    for n, (v, f) in by.items():
        if n in used:
            continue
        pid = len(part_names); part_names.append(n)
        tri.append(v[f]); tri_part.append(np.full(len(f), pid, np.int32))
    tri = np.concatenate(tri); tri_part = np.concatenate(tri_part)
    return groups, tri, tri_part, part_names

if __name__ == '__main__':
    import sys
    groups, tri, tp, pn = build(sys.argv[1])
    print('sabit ucgen', len(tri), 'parca', len(pn))
    for g in groups:
        print(f'{g.name:18s} c={np.round(g.c, 4)} a={np.round(g.a, 3)} hedef={g.target / RPM:7.0f} rpm  '
              f'silindir={len(g.cyls)} makara={len(g.rollers)}')
        for cc, r, h, mu, n in g.cyls:
            print(f'      {n[:40]:40s} r={r * 1000:5.1f} mm  gen={2 * h * 1000:5.1f} mm  c={np.round(cc, 4)}')
        for c0, ax, r, h in g.rollers:
            print(f'      TPU makara c={np.round(c0, 4)} eksen={np.round(ax, 2)} r={r * 1000:4.1f} uz={2 * h * 1000:4.1f}')
