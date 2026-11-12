# Cozucu v3: robotun TUM genisligi (8 mecanum teker) + tasarim parametreleri + hizli temas.
#
# Tasarim sozlugu (World.set_design):
#   layout : intake milindeki 48 mm tekerlerin dizilimi (LAYOUTS)
#   mec    : 'in' = butun mecanumlar topu ortaya iter, 'cad' = CAD'deki yon (disari)
#   mec2   : True ise +-7.6 cm'ye ek ic mecanum (yerini kaplayan tekerler cikar)
#   ramp   : 'cad' | 'none' | RAMPS anahtari | ramp_tris parametre sozlugu
# Fizik sim2 ile ayni (delikli POLLEN, profilli serbest donen TPU makara, 2B Coulomb).
import numpy as np

def _cross(a, b):
    """np.cross ile ayni islemler, 3'lu vektorlerde numpy ek yuku olmadan."""
    if type(a) is not np.ndarray or a.dtype != np.float64: a = np.asarray(a, dtype=float)
    if type(b) is not np.ndarray or b.dtype != np.float64: b = np.asarray(b, dtype=float)
    if a.shape != (3,) or b.shape != (3,):
        return np.cross(a, b)
    a0, a1, a2 = a.tolist(); b0, b1, b2 = b.tolist()
    return np.array((a1 * b2 - a2 * b1, a2 * b0 - a0 * b2, a0 * b1 - a1 * b0))
import model as M
try:
    import fastk as _fk
    FAST = True
except ImportError:
    FAST = False
from sim import closest_on_tris, StaticMesh, rot, qmul
from sim2 import (R, WALL, HOLE_A, HOLE_AX, COS_A, RIM_N, RIM_C, RIM_S, qrot, cyl_sdf, Profile, ball_I,
                  pollen_mass)

P0 = dict(mass=round(pollen_mass(), 4), stiff=1.0, mu_tpu=0.6, mu_wheel=0.65, mu_boot=0.15, mu_hard=0.30,
          mu_floor=0.55, mu_static=1.15, pin_mu=0.25, pin_r=0.0015, roller_I=2.2e-8, holes=True, stuck_t=0.5,
          c_rr=0.0, mu_back=None)
P = dict(P0)

GECKO = (0.0235, 0.008)       # yaricap, yari genislik
BOOT = (0.0240, 0.004)
LAYOUTS = {
    # CAD: - taraf Bootleg, + taraf Gecko
    'CAD': [(-0.0773, 'B'), (-0.0650, 'B'), (-0.0527, 'B'), (-0.0405, 'B'), (-0.0283, 'B'), (-0.0120, 'G'),
            (0.0120, 'G'), (0.0295, 'G'), (0.0470, 'G'), (0.0645, 'G'), (0.0780, 'B')],
    # hepsi Gecko, simetrik
    'GGG': [(s * z, 'G') for z in (0.0120, 0.0295, 0.0470, 0.0645) for s in (-1, 1)],
    # sadece ortadaki iki teker Gecko, yanlar Bootleg (simetrik)
    'CTR': [(s * 0.0120, 'G') for s in (-1, 1)] +
           [(s * z, 'B') for z in (0.0283, 0.0405, 0.0527, 0.0650, 0.0773) for s in (-1, 1)],
    # ortadaki dort teker Gecko, yanlar Bootleg (simetrik)
    'CTR4': [(s * z, 'G') for z in (0.0120, 0.0295) for s in (-1, 1)] +
            [(s * z, 'B') for z in (0.0445, 0.0567, 0.0690, 0.0813) for s in (-1, 1)],
}
MEC2_Z, MEC2_PHASE, MEC_HALF = 0.076, 30.0, 0.0105

RAMP_TOP, RAMP_BOT, RAMP_XB, RAMP_XF, RAMP_WEDGE = 0.016, 0.007, -0.002, -0.1432, 0.0133
FUN = [(-0.1299, 0.064), (-0.1175, 0.052), (-0.1025, 0.0437), (-0.0875, 0.0385), (-0.0725, 0.0365),
       (RAMP_XB, 0.0365)]                        # huni ic duvarini izleyen dis hat
RAMPS = {
    'cadp': dict(stations=[(RAMP_XF + RAMP_WEDGE, 0.025), (RAMP_XB, 0.025)]),             # CAD'in parametrik esi
    'w37': dict(stations=[(RAMP_XF + RAMP_WEDGE, 0.0365), (RAMP_XB, 0.0365)]),            # kanal genisliginde
    'fun': dict(stations=FUN),                                                           # huni tabaninin tamami
    'cham': dict(stations=[(RAMP_XF + RAMP_WEDGE, 0.025), (RAMP_XB, 0.025)], side=0.030),  # CAD + yan pah
    'vee': dict(stations=FUN, edge=0.006),                                               # huni tabani, V-oluk
}

def ramp_tris(stations, x_front=RAMP_XF, side=0.0, edge=0.0, top=RAMP_TOP, bot=RAMP_BOT):
    """Rampa plakasinin ust/yan yuzeyleri. stations: duz ust yuzeyin dis hatti, [(x, yari genislik)] ya da
    asimetrik [(x, w_eksi, w_arti)]; ilk istasyon on kamanin bittigi yer. side: yan pah genisligi.
    edge: kenarlarin ortaya gore yukseltisi (V-oluk; 0 = duz)."""
    T = []
    def quad(a, b, c, d):
        T.append([a, b, c]); T.append([a, c, d])
    st = [(p[0], p[1], p[1]) if len(p) == 2 else tuple(p) for p in stations]
    x0 = st[0][0]
    for s, k in ((-1, 1), (1, 2)):
        w0 = st[0][k]
        quad((x_front, bot, 0.0), (x_front, bot, s * w0), (x0, top + edge, s * w0), (x0, top, 0.0))       # on kama
        T.append([(x_front, bot, s * w0), (x0, top + edge, s * w0), (x0, bot, s * (w0 + side))])
        for pa, pb in zip(st[:-1], st[1:]):
            xa, wa, xb, wb = pa[0], pa[k], pb[0], pb[k]
            quad((xa, top, 0.0), (xb, top, 0.0), (xb, top + edge, s * wb), (xa, top + edge, s * wa))      # ust
            quad((xa, top + edge, s * wa), (xb, top + edge, s * wb), (xb, bot, s * (wb + side)),
                 (xa, bot, s * (wa + side)))                                                          # yan
    return np.array(T, dtype=np.float64)

X_MOUTH, X_KEEP, Z_PLATE, CHAN = -0.1475, -0.0725, 0.083, 0.0365

def wall_tris(poly, y0=0.006, y1=0.098):
    """poly [(x, z), ...] boyunca dikey duvar yuzeyi."""
    T = []
    for (xa, za), (xb, zb) in zip(poly[:-1], poly[1:]):
        a, b, c, d = (xa, y0, za), (xb, y0, zb), (xb, y1, zb), (xa, y1, za)
        T.append([a, b, c]); T.append([a, c, d])
    return np.array(T, dtype=np.float64)

NY = np.array([0.0, 1.0, 0.0])
ZERO = np.zeros(3)
# topun yana kayarken dayandigi yuzeyler (mu_back verilirse bunlara uygulanir)
BACK = ('TOPİTİLİRKENTUTTURUCU', 'top itilirken tutturucu', 'MiddleOlmayanMiddlespacer', 'Dayama (ek)', 'Huni (-)',
        'Huni (+)', 'EniçPleyt')

def floor_sdf(X):
    q = X.copy(); q[:, 1] = M.FLOOR_Y
    return X[:, 1] - M.FLOOR_Y, q, np.tile(NY, (len(X), 1))

def hole_contact(x, Rm, n0, sdf):
    """Temas yonu bir delige denk geliyorsa temas o deligin kenar halkasindan hesaplanir."""
    d_local = Rm.T @ (-n0)
    k = int(np.argmax(HOLE_AX @ d_local))
    if HOLE_AX[k] @ d_local < COS_A:
        return None
    h = Rm @ HOLE_AX[k]
    u = _cross(h, (1.0, 0.0, 0.0))
    if u @ u < 0.01:
        u = _cross(h, (0.0, 1.0, 0.0))
    u /= np.linalg.norm(u); v = _cross(h, u)
    X = x + R * COS_A * h + HOLE_A * (np.outer(RIM_C, u) + np.outer(RIM_S, v))
    phi, q, n = sdf(X)
    pen = -phi
    i = int(np.argmax(pen))
    if pen[i] <= 0:
        return []
    out = [(X[i], q[i], n[i], pen[i])]
    j0, best = -1, 0.0
    for j in range(RIM_N):
        if pen[j] > best and abs(((j - i + RIM_N // 2) % RIM_N) - RIM_N // 2) >= RIM_N // 4:
            best, j0 = pen[j], j
    if j0 >= 0:
        out.append((X[j0], q[j0], n[j0], pen[j0]))
    return out

def normal_force(delta, ddot):
    st = P['stiff']
    f = st * np.interp(delta, M.CURVE_D, M.CURVE_F, right=M.CURVE_F[-1] + (delta - M.CURVE_D[-1]) * 6000)
    c = 2 * 0.22 * np.sqrt(3000.0 * st * P['mass'])
    return max(0.0, f + c * ddot)

class Mesh(StaticMesh):
    """Sabit ucgen agi; aday ucgenler her top icin ayri onbelleklenir."""
    def __init__(self, tri, part, names, cell=0.015):
        StaticMesh.__init__(self, np.ascontiguousarray(tri, dtype=np.float32), part, cell)
        self.names = names

    def ball_contacts(self, b, margin=0.008):
        p = b.x
        ent = b.mc.get(id(self))
        if ent is None or ((p - ent[0]) ** 2).sum() > (margin * 0.5) ** 2:
            c = self.candidates(p, R + margin)
            t = None
            if len(c):
                t = self.tri[c]
                q = closest_on_tris(p, t[:, 0], t[:, 1], t[:, 2])
                near = ((p - q) ** 2).sum(1) < (R + margin * 0.5 + 2e-4) ** 2
                c = c[near]; t = t[near] if near.any() else None
            ent = (p.copy(), c, t)
            b.mc[id(self)] = ent
        c, t = ent[1], ent[2]
        if t is None:
            return []
        if FAST:
            k, oi, oq, on, od = _fk.mesh_hits(np.asarray(p, np.float64), t, R)
            return [(oq[j].copy(), on[j].copy(), od[j], int(self.part[c[oi[j]]])) for j in range(k)]
        q = closest_on_tris(p, t[:, 0], t[:, 1], t[:, 2])
        dv = p - q
        d = np.sqrt((dv * dv).sum(1))
        idx = np.nonzero(d < R)[0]
        if len(idx) == 0:
            return []
        idx = idx[np.argsort(d[idx])]
        out = []
        for i in idx:
            n = dv[i] / max(d[i], 1e-9)
            if any(n @ o[1] > 0.85 for o in out):
                continue
            out.append((q[i].astype(np.float64), n, R - d[i], int(self.part[c[i]])))
            if len(out) >= 6:
                break
        return out

class Ball:
    def __init__(self, x, v, q):
        self.x = np.array(x, float); self.v = np.array(v, float)
        self.w = np.zeros(3); self.q = np.array(q, float)
        self.x0 = self.x.copy()
        self.state = 'aktif'; self.t_end = None; self.exit_v = None; self.peak_f = 0.0
        self.touch = {}; self.mc = {}
        self.anchor = self.x.copy(); self.t_anchor = 0.0; self.flag = False

class World:
    VAR = ('AltFunnelPrint', 'BootluFunnelİttiricisi', 'GekoluFunnelİttiricisi')   # rampa, huni -, huni +

    def __init__(self, region='region2.npz'):
        self.groups, tri, part, names = M.build(region)
        gi = self.groups[0]
        assert abs(gi.a[2]) > 0.999 and gi.target > 0
        ids = [names.index(n) for n in self.VAR]
        isvar = np.isin(part, ids)
        self.cad_ramp = tri[part == ids[0]]
        self.cad_fun = {-1: tri[part == ids[1]], 1: tri[part == ids[2]]}
        self.base = Mesh(tri[~isvar], part[~isvar], names)
        tt = np.linspace(-0.01002, 0.01002, 21)
        rr = np.array([4.40, 4.72, 4.96, 5.14, 5.28, 5.41, 5.50, 5.58, 5.65, 5.68, 5.69,
                       5.68, 5.65, 5.58, 5.50, 5.41, 5.28, 5.14, 4.96, 4.72, 4.40]) / 1000
        self.prof = Profile(tt, rr)
        rl = sorted(((c0, ax / np.linalg.norm(ax)) for c0, ax, _, _ in gi.rollers), key=lambda r: r[0][2])
        self.cad_wheels = []
        for c0, ax in rl:
            if self.cad_wheels and abs(c0[2] - self.cad_wheels[-1][-1][0][2]) < 0.01:
                self.cad_wheels[-1].append((c0, ax))
            else:
                self.cad_wheels.append([(c0, ax)])
        for g in self.groups[1:]:
            rb = max(np.linalg.norm(cc - g.c) + np.hypot(rc, h) for cc, rc, h, _, _ in g.cyls) + R + 0.002
            g.rb2 = float(rb * rb)
        self.set_design({})

    # ------------------------------------------------------------ tasarim
    def _hand(self, c0, e):
        """+1: makara topu disari iter (intake yonunde donerken)."""
        gi = self.groups[0]
        rel = c0 - gi.c
        return np.sign((_cross((0.0, 0.0, 1.0), rel) @ e) * e[2] * c0[2])

    def set_design(self, D):
        """layout: LAYOUTS anahtari ya da [(z, 'G'|'B')]; mec: 'in'|'cad'; mec2: +-7.6 cm ic mecanum;
        mecz: ek ic mecanum merkezleri; ramp: 'cad'|'none'|RAMPS anahtari|ramp_tris sozlugu;
        funnel: {'neg'|'pos': 'cad' | [(x, yari genislik), ...]} (on kisim parametrik, kanal CAD);
        walls: ek dikey duvarlar [[(x, z), ...], ...]."""
        self.D = dict(D)
        gi = self.groups[0]
        lay = D.get('layout', 'CAD')
        lay = LAYOUTS[lay] if isinstance(lay, str) else [tuple(w) for w in lay]
        mecz = list(D.get('mecz', ())) + ([MEC2_Z, -MEC2_Z] if D.get('mec2') else [])
        def clear(z, k):
            hw = GECKO[1] if k == 'G' else BOOT[1]
            return all(abs(z - m) >= hw + MEC_HALF - 1e-9 for m in mecz)
        self.cyl = [(z, *(GECKO if k == 'G' else BOOT), k) for z, k in lay if clear(z, k)]
        mode = D.get('mec', 'in')
        rol = []
        for wh in self.cad_wheels:
            for c0, e in wh:
                e = e.copy()
                if mode == 'in' and self._hand(c0, e) > 0:
                    e[2] = -e[2]
                rol.append((c0, e))
        for sg in (1, -1):
            src = min((w for w in self.cad_wheels if np.sign(w[0][0][2]) == sg), key=lambda w: abs(w[0][0][2]))
            for i, zc in enumerate(sorted((m for m in mecz if np.sign(m) == sg), key=lambda m: -abs(m))):
                Rp = rot(gi.a, np.radians(MEC2_PHASE if i % 2 == 0 else 0.0))
                for c0, e in src:
                    c1 = gi.c + Rp @ (c0 - gi.c); c1[2] = zc
                    e1 = Rp @ e
                    if self._hand(c1, e1) > 0:                 # ek mecanum her zaman iceri iter
                        e1[2] = -e1[2]
                    rol.append((c1, e1))
        self.rollers = rol
        self.mecz = mecz
        self.RC0 = np.array([c - gi.c for c, _ in rol]); self.RAX = np.array([e for _, e in rol])
        parts, names = [], []
        r = D.get('ramp', 'cad')
        if r != 'none':
            parts.append(self.cad_ramp if r == 'cad' else ramp_tris(**(RAMPS[r] if isinstance(r, str) else r)))
            names.append('Rampa')
        self.ramp_tris = parts[0] if parts else None
        fun = D.get('funnel') or {}
        self.fun_tris = {}
        for sg, key, nm in ((-1, 'neg', 'Huni (-)'), (1, 'pos', 'Huni (+)')):
            spec = fun.get(key, 'cad')
            cad = self.cad_fun[sg]
            if isinstance(spec, str):
                t = cad
            else:
                rear = cad[cad[:, :, 0].min(1) > X_KEEP]
                poly = [(X_MOUTH, sg * Z_PLATE)] + [(x, sg * w) for x, w in spec]
                if poly[-1][0] < X_KEEP:
                    poly.append((X_KEEP, sg * CHAN))
                t = np.concatenate([rear, wall_tris(poly)])
            self.fun_tris[sg] = t
            parts.append(t); names.append(nm)
        self.wall_polys = [list(map(tuple, w)) for w in D.get('walls', ())]
        for w in self.wall_polys:
            parts.append(wall_tris(w, 0.006, 0.064)); names.append('Dayama (ek)')
        tris = np.concatenate(parts)
        pid = np.concatenate([np.full(len(p), i, np.int32) for i, p in enumerate(parts)])
        self.var = Mesh(tris, pid, names)

    # ------------------------------------------------------------ temas
    def _cyl(self, cons, x, Rm, holes, cc, a, rc, h, mu, g, nm):
        sdf = lambda X: cyl_sdf(X, cc, a, rc, h)
        phi, q, n = sdf(x[None])
        if phi[0] > R + 0.0005:
            return
        hc = hole_contact(x, Rm, n[0], sdf) if holes else None
        if hc is None:
            if phi[0] < R:
                cons.append((x - n[0] * R, q[0], n[0], R - phi[0], mu, None, g, -1, nm, 1.0))
        else:
            for X, qq, nn, pen in hc:
                cons.append((X, qq, nn, pen, mu, None, g, -1, nm, 1.0 / len(hc)))

    def contacts(self, b, gs, fv, others, CW, EW):
        cons = []   # (x_top, q, n, delta, mu, vs, grup, makara, etiket, pay)
        x = b.x
        bx, by, bz = float(x[0]), float(x[1]), float(x[2])
        Rm = qrot(b.q); holes = P['holes']
        dfl = by - M.FLOOR_Y
        if dfl < R + 0.001:
            hc = hole_contact(x, Rm, NY, floor_sdf) if holes else None
            if hc is None:
                if dfl < R:
                    cons.append((x - NY * R, x - NY * dfl, NY, R - dfl, P['mu_floor'], fv, None, -1, 'zemin', 1.0))
            else:
                for X, q, n, pen in hc:
                    cons.append((X, q, n, pen, P['mu_floor'], fv, None, -1, 'zemin', 1.0 / len(hc)))
        for mesh in (self.base, self.var):
            if mesh is None:
                continue
            for q, n, dlt, pid in mesh.ball_contacts(b):
                nm = mesh.names[pid]
                mu = P['mu_hard']
                if P['mu_back'] is not None and nm.startswith(BACK):
                    mu = P['mu_back']
                cons.append((x - n * R, q, n, dlt, mu, ZERO, None, -1, nm, 1.0))
        gi = gs[0]
        dx, dy = bx - gi.c[0], by - gi.c[1]
        rho = (dx * dx + dy * dy) ** 0.5
        if rho < 0.0245 + R:
            tz = bz - gi.c[2]
            for zc, rc, h, kind in self.cyl:
                if abs(tz - zc) > h + R or rho > rc + R + 0.0005:
                    continue
                cc = np.array((gi.c[0], gi.c[1], gi.c[2] + zc))
                if kind == 'G':
                    self._cyl(cons, x, Rm, holes, cc, gi.a, rc, h, P['mu_wheel'], gi, 'Gecko 48')
                else:
                    self._cyl(cons, x, Rm, holes, cc, gi.a, rc, h, P['mu_boot'], gi, 'Bootleg 48')
            d2 = ((CW - x) ** 2).sum(1)
            for ri in np.nonzero(d2 < (R + 0.013) ** 2)[0]:
                cw, ew = CW[ri], EW[ri]
                sdf = lambda X, cw=cw, ew=ew: self.prof.sdf(X, cw, ew)
                phi, q, n = sdf(x[None])
                if phi[0] > R + 0.0005:
                    continue
                hc = hole_contact(x, Rm, n[0], sdf) if holes else None
                if hc is None:
                    if phi[0] < R:
                        cons.append((x - n[0] * R, q[0], n[0], R - phi[0], P['mu_tpu'], None, gi, int(ri),
                                     'TPU makara', 1.0))
                else:
                    for X, qq, nn, pen in hc:
                        cons.append((X, qq, nn, pen, P['mu_tpu'], None, gi, int(ri), 'TPU makara', 1.0 / len(hc)))
        for g in gs[1:]:
            c = g.c
            if (bx - c[0]) ** 2 + (by - c[1]) ** 2 + (bz - c[2]) ** 2 > g.rb2:
                continue
            for cc, rc, h, mu, nm in g.cyls:
                self._cyl(cons, x, Rm, holes, cc, g.a, rc, h, P['mu_wheel'], g, nm)
        for o in others:
            dv = x - o.x; d = float(np.sqrt(dv @ dv))
            if d < 2 * R:
                n = dv / d
                cp = x - n * R
                # diger topun temas noktasindaki yuzey hizi (donusu dahil)
                cons.append((cp, cp, n, (2 * R - d) / 2, 0.4, o.v + _cross(o.w, cp - o.x), None, -1, 'diger top', 1.0))
        return cons

    # ------------------------------------------------------------ calistir
    def run(self, balls, robot_v=0.5, t_max=2.5, dt=2e-4, rec_dt=None, intake_only=False, seed=0):
        """balls: [(x, z, t_cikis)]. Donus: (toplar, kayit). Takilan top engel olarak sahnede kalir;
        kalan butun toplar stuck_t boyunca 5 mm'den az hareket ettiyse kosu biter."""
        rng = np.random.default_rng(seed)
        m = P['mass']; Ib = ball_I(m)
        B, pending = [], sorted(balls, key=lambda b: b[2])
        gs = self.groups; gi = gs[0]
        for g in gs:
            g.w = g.target; g.theta = 0.0; g.min_w = abs(g.w); g.tau_peak = 0.0
        wr = np.zeros(len(self.RC0))
        fv = np.array([robot_v, 0, 0], float) if np.isscalar(robot_v) else np.array(robot_v, float)
        rec = {'t': [], 'pos': [], 'quat': [], 'theta': []}
        t, next_rec = 0.0, 0.0
        rI = P['roller_I']; mu_s = P['mu_static']; crr = P['c_rr']
        gidx = {id(g): k for k, g in enumerate(gs)}
        ga = np.array([g.a for g in gs], float); gc = np.array([g.c for g in gs], float)
        gI = np.array([g.I for g in gs], float)
        CD = np.asarray(M.CURVE_D, float); CF = np.asarray(M.CURVE_F, float)
        cdamp = 2 * 0.22 * np.sqrt(3000.0 * P['stiff'] * P['mass'])
        while t < t_max:
            while pending and pending[0][2] <= t:
                x, z, _ = pending.pop(0)
                q = rng.normal(size=4); q /= np.linalg.norm(q)
                b = Ball([x, R + M.FLOOR_Y, z], fv.copy(), q); b.t_anchor = t
                B.append(b)
            for g in gs:
                g.w += g.motor_torque() / g.I * dt
            active = [b for b in B if b.state == 'aktif']
            if not pending and (not active or all(b.flag for b in active)):
                break
            Rg = rot(gi.a, gi.theta)
            gw = np.array([g.w for g in gs], float); gtau = np.array([g.tau_peak for g in gs], float)
            CW = gi.c + self.RC0 @ Rg.T; EW = self.RAX @ Rg.T
            for b in active:
                cons = self.contacts(b, gs, fv, [o for o in active if o is not b], CW, EW)
                nc = len(cons)
                Xc = np.empty((nc, 3)); Qc = np.empty((nc, 3)); Nc = np.empty((nc, 3)); VSc = np.zeros((nc, 3))
                DLc = np.empty(nc); MUc = np.empty(nc); KSc = np.empty(nc)
                GIc = np.full(nc, -1, np.int64); RIc = np.empty(nc, np.int64); FLc = np.zeros(nc, np.bool_)
                for i, (x, q, n, dlt, mu, vs, g, ri, lab, ks) in enumerate(cons):
                    Xc[i] = x; Qc[i] = q; Nc[i] = n; DLc[i] = dlt; MUc[i] = mu; KSc[i] = ks; RIc[i] = ri
                    if g is None:
                        VSc[i] = vs
                    else:
                        GIc[i] = gidx[id(g)]
                    if lab == 'zemin':
                        FLc[i] = True
                    b.touch[lab] = b.touch.get(lab, 0) + 1
                fnc = np.zeros(nc)
                pk = _fk.solve_ball(b.x, b.v, b.w, Xc, Qc, Nc, DLc, MUc, VSc, GIc, RIc, KSc, FLc,
                                    gw, ga, gc, gI, gtau, wr, CW, EW, M.G, m, Ib, rI, mu_s, crr, dt,
                                    CD, CF, P['stiff'], cdamp, P['pin_mu'], P['pin_r'], fnc)
                if pk > b.peak_f:
                    b.peak_f = pk
                for g in gs:
                    g.w = float(gw[gidx[id(g)]])
                b.x += b.v * dt
                wn = float(np.sqrt(b.w @ b.w))
                if wn > 1e-9:
                    hq = np.concatenate([[np.cos(wn * dt / 2)], np.sin(wn * dt / 2) * b.w / wn])
                    b.q = qmul(hq, b.q); b.q /= np.linalg.norm(b.q)
                # durum
                dd = b.x - b.anchor
                if dd @ dd > 2.5e-5:
                    b.anchor = b.x.copy(); b.t_anchor = t; b.flag = False
                elif t - b.t_anchor > P['stuck_t'] and b.x[0] > -0.26:
                    b.flag = True
                if intake_only and b.x[0] > -0.085 and b.x[1] > R + 0.01:
                    b.state = 'alindi'; b.t_end = t
                elif b.x[1] > 0.36 or (b.x[1] > 0.2 and np.hypot(b.x[0] - 0.05, b.x[1] - 0.25) > 0.17):
                    b.state = 'cikti'; b.t_end = t; b.exit_v = b.v.copy()
                elif abs(b.x[2]) > 0.30 or b.x[1] < -0.05 or b.x[0] < -0.9:
                    b.state = 'kacti'; b.t_end = t
            for k_, g in enumerate(gs):
                g.w = float(gw[k_]); g.tau_peak = float(gtau[k_])
            wr *= np.exp(-dt / 0.3)
            for g in gs:
                g.theta += g.w * dt
                if abs(g.w) < g.min_w:
                    g.min_w = abs(g.w)
            if rec_dt is not None and t >= next_rec:
                rec['t'].append(t)
                rec['pos'].append([b.x.copy() for b in B]); rec['quat'].append([b.q.copy() for b in B])
                rec['theta'].append([g.theta for g in gs])
                next_rec += rec_dt
            t += dt
        for b in B:
            if b.state == 'aktif':
                b.state = 'takildi' if b.flag else 'zaman asimi'; b.t_end = t
        return B, rec

    def run_ref(self, balls, robot_v=0.5, t_max=2.5, dt=2e-4, rec_dt=None, intake_only=False, seed=0):
        """balls: [(x, z, t_cikis)]. Donus: (toplar, kayit). Takilan top engel olarak sahnede kalir;
        kalan butun toplar stuck_t boyunca 5 mm'den az hareket ettiyse kosu biter."""
        rng = np.random.default_rng(seed)
        m = P['mass']; Ib = ball_I(m)
        B, pending = [], sorted(balls, key=lambda b: b[2])
        gs = self.groups; gi = gs[0]
        for g in gs:
            g.w = g.target; g.theta = 0.0; g.min_w = abs(g.w); g.tau_peak = 0.0
        wr = np.zeros(len(self.RC0))
        fv = np.array([robot_v, 0, 0], float) if np.isscalar(robot_v) else np.array(robot_v, float)
        rec = {'t': [], 'pos': [], 'quat': [], 'theta': []}
        t, next_rec = 0.0, 0.0
        rI = P['roller_I']; mu_s = P['mu_static']; crr = P['c_rr']
        while t < t_max:
            while pending and pending[0][2] <= t:
                x, z, _ = pending.pop(0)
                q = rng.normal(size=4); q /= np.linalg.norm(q)
                b = Ball([x, R + M.FLOOR_Y, z], fv.copy(), q); b.t_anchor = t
                B.append(b)
            for g in gs:
                g.w += g.motor_torque() / g.I * dt
            active = [b for b in B if b.state == 'aktif']
            if not pending and (not active or all(b.flag for b in active)):
                break
            Rg = rot(gi.a, gi.theta)
            CW = gi.c + self.RC0 @ Rg.T; EW = self.RAX @ Rg.T
            for b in active:
                cons = self.contacts(b, gs, fv, [o for o in active if o is not b], CW, EW)
                fn = []
                acc = M.G.copy()
                for (x, q, n, dlt, mu, vs, g, ri, lab, ks) in cons:
                    vsurf = vs if g is None else _cross(g.w * g.a, q - g.c)
                    if ri >= 0:
                        vsurf = vsurf + _cross(wr[ri] * EW[ri], q - CW[ri])
                    vrel = b.v + _cross(b.w, x - b.x) - vsurf
                    f = ks * normal_force(dlt, -(vrel @ n))
                    fn.append(f)
                    acc += f * n / m
                    if crr > 0 and lab == 'zemin':      # yuvarlanma direnci: zemine gore hareketin tersine
                        vr = b.v - vs
                        sp = float(np.hypot(vr[0], vr[2]))
                        if sp > 1e-3:
                            acc[0] -= crr * f / m * vr[0] / sp; acc[2] -= crr * f / m * vr[2] / sp
                    if f > b.peak_f:
                        b.peak_f = f
                    b.touch[lab] = b.touch.get(lab, 0) + 1
                b.v += acc * dt
                J = [np.zeros(3) for _ in cons]
                for it in range(5):
                    for i, (x, q, n, dlt, mu, vs, g, ri, lab, ks) in enumerate(cons):
                        if fn[i] <= 0:
                            continue
                        r = x - b.x
                        vsurf = vs if g is None else _cross(g.w * g.a, q - g.c)
                        if ri >= 0:
                            ew = EW[ri]; cr = CW[ri]
                            vsurf = vsurf + _cross(wr[ri] * ew, q - cr)
                        u = b.v + _cross(b.w, r) - vsurf
                        ut = u - (u @ n) * n
                        s = float(np.sqrt(ut @ ut))
                        if s < 1e-10:
                            continue
                        td = ut / s
                        rt = _cross(r, td)
                        K = 1 / m + rt @ rt / Ib
                        if g is not None:
                            lev = _cross(q - g.c, td) @ g.a
                            K += lev * lev / g.I
                        if ri >= 0:
                            levr = _cross(q - cr, td) @ ew
                            K += levr * levr / rI
                        Jnew = J[i] - td * (s / K)
                        lim = mu * (mu_s if s < 0.02 else 1.0) * fn[i] * dt
                        nJ = float(np.sqrt(Jnew @ Jnew))
                        if nJ > lim:
                            Jnew *= lim / nJ
                        dJ = Jnew - J[i]; J[i] = Jnew
                        b.v += dJ / m
                        b.w += _cross(r, dJ) / Ib
                        if g is not None:
                            dL = _cross(q - g.c, -dJ) @ g.a
                            g.w += dL / g.I
                            if abs(dL) / dt > g.tau_peak:
                                g.tau_peak = abs(dL) / dt
                        if ri >= 0:
                            wr[ri] += (_cross(q - cr, -dJ) @ ew) / rI
                for i, c in enumerate(cons):
                    ri = c[7]
                    if ri >= 0:                       # makara pim surtunmesi (yuke bagli)
                        dw = (P['pin_mu'] * P['pin_r'] * fn[i] + 2e-6) * dt / rI
                        wr[ri] = 0.0 if abs(wr[ri]) <= dw else wr[ri] - np.sign(wr[ri]) * dw
                b.x += b.v * dt
                wn = float(np.sqrt(b.w @ b.w))
                if wn > 1e-9:
                    hq = np.concatenate([[np.cos(wn * dt / 2)], np.sin(wn * dt / 2) * b.w / wn])
                    b.q = qmul(hq, b.q); b.q /= np.linalg.norm(b.q)
                # durum
                dd = b.x - b.anchor
                if dd @ dd > 2.5e-5:
                    b.anchor = b.x.copy(); b.t_anchor = t; b.flag = False
                elif t - b.t_anchor > P['stuck_t'] and b.x[0] > -0.26:
                    b.flag = True
                if intake_only and b.x[0] > -0.085 and b.x[1] > R + 0.01:
                    b.state = 'alindi'; b.t_end = t
                elif b.x[1] > 0.36 or (b.x[1] > 0.2 and np.hypot(b.x[0] - 0.05, b.x[1] - 0.25) > 0.17):
                    b.state = 'cikti'; b.t_end = t; b.exit_v = b.v.copy()
                elif abs(b.x[2]) > 0.30 or b.x[1] < -0.05 or b.x[0] < -0.9:
                    b.state = 'kacti'; b.t_end = t
            wr *= np.exp(-dt / 0.3)
            for g in gs:
                g.theta += g.w * dt
                if abs(g.w) < g.min_w:
                    g.min_w = abs(g.w)
            if rec_dt is not None and t >= next_rec:
                rec['t'].append(t)
                rec['pos'].append([b.x.copy() for b in B]); rec['quat'].append([b.q.copy() for b in B])
                rec['theta'].append([g.theta for g in gs])
                next_rec += rec_dt
            t += dt
        for b in B:
            if b.state == 'aktif':
                b.state = 'takildi' if b.flag else 'zaman asimi'; b.t_end = t
        return B, rec

def describe(B):
    out = []
    for b in B:
        s = f"z{b.x0[2] * 100:+.1f}:{b.state}"
        if b.exit_v is not None:
            s += f"({np.linalg.norm(b.exit_v):.2f})"
        if b.state in ('takildi', 'zaman asimi', 'kacti'):
            s += f"@({b.x[0]:+.3f},{b.x[1]:.3f},{b.x[2]:+.3f})"
        out.append(s)
    return '  '.join(out)
