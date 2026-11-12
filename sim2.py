# Cozucu v2: gercek POLLEN (delikli PE kabuk) + profilli, kendi pimi uzerinde donen TPU makaralar.
#
# POLLEN (Competition Manual TU08 9.8): ~2.8 in Gopher ResisDent polietilen top, am-5851_yellow.
# AndyMark CAD: 1.8 mm cidar, 26 adet 11.2 mm delik (eksenler shooter hesaplayicisindan).
# Kutle resmi olarak verilmiyor: kabuk hacmi x PE yogunlugu ~= 22 g (tahmin).
#
# Delik temasi: topun temas yonu bir deligin icine dusuyorsa, temas o deligin kenar
# halkasindan (24 nokta) hesaplanir; kucuk makaralar delige gomulebilir.
# TPU makara: CAD'den alinmis fici profili, kendi ekseni etrafinda serbest donus (atalet + pim surtunmesi).
import time
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
from sim import closest_on_tris, StaticMesh, rot, qmul

# ------------------------------------------------------------------ POLLEN
R = 0.03556
WALL = 0.00178
HOLE_A = 0.00559
HOLE_AX = np.array([
    [-0.3685911384, -0.2688750669, 0.8898577252], [0.3582910162, 0.7555613467, -0.5484109764],
    [-0.9465601575, 0.2688750669, -0.1781293538], [-0.6550778972, -0.7555613467, 0.0],
    [-0.5433626321, 0.2688750669, -0.7952755802], [0.0, -1.0, 0.0],
    [0.7952755802, 0.2688750669, -0.5433626321], [-0.8898577252, -0.2688750669, 0.3685911384],
    [0.8898577252, -0.2688750669, -0.3685911384], [0.0, -0.7555613467, 0.6550778972],
    [0.5484109764, 0.7555613467, 0.3582910162], [0.8898577252, -0.2688750669, 0.3685911384],
    [-0.5484109764, 0.7555613467, -0.3582910162], [0.5433626321, 0.2688750669, 0.7952755802],
    [-0.7952755802, 0.2688750669, 0.5433626321], [0.3685911384, -0.2688750669, 0.8898577252],
    [-0.3582910162, 0.7555613467, 0.5484109764], [-0.1781293538, 0.2688750669, 0.9465601575],
    [-0.8898577252, -0.2688750669, -0.3685911384], [0.6550778972, -0.7555613467, 0.0],
    [0.0, -0.7555613467, -0.6550778972], [0.1781293538, 0.2688750669, -0.9465601575],
    [0.9465601575, 0.2688750669, 0.1781293538], [0.3685911384, -0.2688750669, -0.8898577252],
    [0.0, 1.0, 0.0], [-0.3685911384, -0.2688750669, -0.8898577252]])
HOLE_AX /= np.linalg.norm(HOLE_AX, axis=1)[:, None]
COS_A = np.sqrt(1 - (HOLE_A / R) ** 2)
RIM_N = 24
_th = np.linspace(0, 2 * np.pi, RIM_N, endpoint=False)
RIM_C, RIM_S = np.cos(_th), np.sin(_th)

def pollen_mass(rho=950.0):
    Ri = R - WALL
    shell = 4 / 3 * np.pi * (R ** 3 - Ri ** 3)
    holes = len(HOLE_AX) * np.pi * HOLE_A ** 2 * WALL
    return rho * (shell - holes)

P = dict(mass=round(pollen_mass(), 4), stiff=1.0, mu_tpu=0.6, mu_wheel=0.65, mu_hard=0.30,
         mu_floor=0.55, mu_static=1.15, mu_boot=0.65, pin_mu=0.25, pin_r=0.0015, roller_I=2.2e-8, holes=True)

def ball_I(m):
    Ri = R - WALL
    return 0.4 * m * (R ** 5 - Ri ** 5) / (R ** 3 - Ri ** 3)

def qrot(q):
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                     [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                     [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])

def normal_force(delta, ddot, stiff):
    f = stiff * np.interp(delta, M.CURVE_D, M.CURVE_F, right=M.CURVE_F[-1] + (delta - M.CURVE_D[-1]) * 6000)
    c = 2 * 0.22 * np.sqrt(3000.0 * stiff * P['mass'])
    return max(0.0, f + c * ddot)

# ------------------------------------------------------------------ isaretli mesafe fonksiyonlari
def cyl_sdf(X, c, a, rc, h):
    """Dolu silindir: isaretli mesafe, yuzeydeki en yakin nokta, disa normal (X: (k,3))."""
    d = X - c
    t = d @ a
    rv = d - np.outer(t, a)
    rho = np.linalg.norm(rv, axis=1)
    rh = rv / np.maximum(rho, 1e-12)[:, None]
    ds, dc = rho - rc, np.abs(t) - h
    out = (ds > 0) | (dc > 0)
    phi = np.where(out, np.hypot(np.maximum(ds, 0), np.maximum(dc, 0)), np.maximum(ds, dc))
    tc = np.clip(t, -h, h); rr = np.minimum(rho, rc)
    q = c + np.outer(tc, a) + rh * rr[:, None]
    side = ds > dc
    qi = np.where(side[:, None], c + np.outer(t, a) + rh * rc, c + np.outer(np.sign(t) * h, a) + rv)
    q = np.where(out[:, None], q, qi)
    n = np.where(out[:, None], (X - q) / np.maximum(np.linalg.norm(X - q, axis=1), 1e-12)[:, None],
                 np.where(side[:, None], rh, np.outer(np.sign(t), a)))
    return phi, q, n

class Profile:
    """Donel cisim profili (t, r): TPU makaranin CAD'den olculmus fici sekli."""
    def __init__(self, t, r):
        # kapali sinir: uc kapak - profil - uc kapak
        pts = [(t[0], 0.0)] + list(zip(t, r)) + [(t[-1], 0.0)]
        self.P = np.array(pts)
        self.A, self.B = self.P[:-1], self.P[1:]
        self.t, self.r = np.asarray(t), np.asarray(r)

    def sdf(self, X, c, e):
        d = X - c
        tx = d @ e
        rv = d - np.outer(tx, e)
        rho = np.linalg.norm(rv, axis=1)
        rh = rv / np.maximum(rho, 1e-12)[:, None]
        Q = np.stack([tx, rho], 1)                                  # (k,2)
        AB = self.B - self.A                                        # (s,2)
        u = np.clip(((Q[:, None, :] - self.A[None]) * AB[None]).sum(2) / (AB ** 2).sum(1)[None], 0, 1)
        C = self.A[None] + u[..., None] * AB[None]                  # (k,s,2)
        dd = np.linalg.norm(Q[:, None, :] - C, axis=2)
        j = dd.argmin(1)
        cp = C[np.arange(len(X)), j]
        dist = dd[np.arange(len(X)), j]
        inside = (np.abs(tx) <= self.t[-1]) & (rho <= np.interp(tx, self.t, self.r))
        phi = np.where(inside, -dist, dist)
        q = c + np.outer(cp[:, 0], e) + rh * cp[:, 1][:, None]
        n = (X - q) / np.maximum(dist, 1e-12)[:, None]
        n = np.where(inside[:, None], -n, n)
        return phi, q, n

def box_tris(a, b, height, thick):
    """a->b dogrultusunda dikey ince plaka (12 ucgen)."""
    d = b - a; d[1] = 0; L = np.linalg.norm(d); d /= L
    nrm = _cross(d, [0, 1.0, 0]) * thick / 2
    up = np.array([0, height, 0])
    P = [a - nrm, b - nrm, b + nrm, a + nrm]
    V = P + [p + up for p in P]
    F = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6), (0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2),
         (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]
    return [[V[i], V[j], V[k]] for i, j, k in F]

MEC2_Z = 0.076          # ic mecanum merkezi (mevcutlar +-0.097)
MEC2_PHASE = 30.0       # makaralar mevcut tekerlege gore 30 derece kaydirilmis
MEC2_REMOVED = ('48mm Bootleg', '48mm Bootleg_5', '48mm Bootleg_3')

def is_mec2_removed(name):
    return name in MEC2_REMOVED or name.startswith('48mm Gecko Wheel - 15A (GB)_4')

# ------------------------------------------------------------------ dunya
class Ball:
    def __init__(self, x, v, q):
        self.x = np.array(x, float); self.v = np.array(v, float)
        self.w = np.zeros(3); self.q = np.array(q, float)
        self.state = 'aktif'; self.t_slow = 0.0; self.t_end = None
        self.exit_v = None; self.peak_f = 0.0; self.touch = {}; self.stuck_at = None
        self.kicked = False; self.hole_hits = 0; self.max_sink = 0.0

class World:
    def __init__(self, region='region.npz'):
        self.groups, tri, part, self.part_names = M.build(region)
        self.mesh = StaticMesh(tri, part)
        self.base = {g.name: g.target for g in self.groups}
        gi = self.groups[0]
        # TPU makara profili (CAD'den, mm -> m)
        tt = np.linspace(-0.01002, 0.01002, 21)
        rr = np.array([4.40, 4.72, 4.96, 5.14, 5.28, 5.41, 5.50, 5.58, 5.65, 5.68, 5.69,
                       5.68, 5.65, 5.58, 5.50, 5.41, 5.28, 5.14, 4.96, 4.72, 4.40]) / 1000
        self.prof = Profile(tt, rr)
        self.rollers0 = [(c0, ax / np.linalg.norm(ax)) for c0, ax, _, _ in gi.rollers]
        self.mirror = False
        self._tri, self._part = tri, part
        self._full_mesh = self.mesh
        self._meshes = {}

    def exclude(self, pattern=None):
        """Tasarim degisikligi denemesi. pattern: 'ad1|ad2' (tam alt dize, Turkce harf duyarli);
        '+flare' eklenirse huni agzina acili yonlendirme plakalari eklenir."""
        if not pattern:
            self.mesh = self._full_mesh; return
        if pattern not in self._meshes:
            names = [p for p in pattern.split('|') if p and p != '+flare']
            bad = np.array([any(p in n for p in names) for n in self.part_names])
            keep = ~bad[self._part]
            tri, part = self._tri[keep], self._part[keep]
            if '+flare' in pattern:
                extra = []
                for sg in (1, -1):
                    extra += box_tris(np.array([-0.215, 0.004, sg * 0.125]), np.array([-0.147, 0.004, sg * 0.0845]),
                                      0.056, 0.003)
                extra = np.array(extra)
                pid = len(self.part_names)
                if 'YONLENDIRME (deneme)' not in self.part_names:
                    self.part_names.append('YONLENDIRME (deneme)')
                pid = self.part_names.index('YONLENDIRME (deneme)')
                tri = np.concatenate([tri, extra]); part = np.concatenate([part, np.full(len(extra), pid, part.dtype)])
            self._meshes[pattern] = StaticMesh(tri, part)
        self.mesh = self._meshes[pattern]

    def set_mec2(self, on):
        """Ikinci (ic) mecanum: mevcutlarin hemen icine, z = +-MEC2_Z; yerini kaplayan tekerlekler cikarilir."""
        gi = self.groups[0]
        if not hasattr(gi, 'cyls0'):
            gi.cyls0 = list(gi.cyls)
        self.mec2 = on
        gi.cyls = [c for c in gi.cyls0 if not (on and is_mec2_removed(c[4]))]

    def roller_set(self):
        out = []
        for c0, ax in self.rollers0:
            out.append((c0, ax * np.array([1, 1, -1]) if self.mirror else ax))
        if getattr(self, 'mec2', False):
            g = self.groups[0]
            Rp = rot(g.a, np.radians(MEC2_PHASE))
            for c0, ax in self.rollers0:
                side = np.sign(c0[2])
                side_c = np.mean([c[2] for c, _ in self.rollers0 if np.sign(c[2]) == side])
                c1 = g.c + Rp @ (c0 - g.c); c1[2] += side * MEC2_Z - side_c
                a1 = Rp @ ax
                out.append((c1, a1 * np.array([1, 1, -1]) if self.mirror else a1))
        return out

    # temas uretimi -------------------------------------------------
    def hole_contact(self, b, Rm, n0, sdf):
        """Temas yonu delikteyse kenar halkasindan temaslar. Donus: [(x_top, q, n, delta)] veya None."""
        d_local = Rm.T @ (-n0)
        k = int(np.argmax(HOLE_AX @ d_local))
        if HOLE_AX[k] @ d_local < COS_A:
            return None
        h = Rm @ HOLE_AX[k]
        u = _cross(h, [1.0, 0, 0]);
        if np.linalg.norm(u) < 0.1:
            u = _cross(h, [0, 1.0, 0])
        u /= np.linalg.norm(u); v = _cross(h, u)
        X = b.x + R * COS_A * h + HOLE_A * (np.outer(RIM_C, u) + np.outer(RIM_S, v))
        phi, q, n = sdf(X)
        pen = -phi
        i = int(np.argmax(pen))
        if pen[i] <= 0:
            return []
        out = [(X[i], q[i], n[i], pen[i])]
        # karsi taraftaki ikinci destek noktasi (makara deligin uzerine oturdugunda)
        opp = [j for j in range(RIM_N) if abs(((j - i + RIM_N // 2) % RIM_N) - RIM_N // 2) >= RIM_N // 4 and pen[j] > 0]
        if opp:
            j = max(opp, key=lambda j: pen[j])
            out.append((X[j], q[j], n[j], pen[j]))
        b.hole_hits += 1
        return out

    def contacts(self, b, gs, fv, others):
        cons = []   # (x_top, q, n, delta, mu, vs, group, roller_idx, label, kshare)
        Rm = qrot(b.q)
        holes = P['holes']
        # zemin
        dfl = b.x[1] - M.FLOOR_Y
        if dfl < R + 0.001:
            n0 = np.array([0, 1.0, 0])
            hc = self.hole_contact(b, Rm, n0, lambda X: (X[:, 1] - M.FLOOR_Y, np.c_[X[:, 0], np.full(len(X), M.FLOOR_Y), X[:, 2]],
                                                          np.tile(n0, (len(X), 1)))) if holes else None
            if hc is None:
                if dfl < R:
                    cons.append((b.x - n0 * R, b.x - n0 * dfl, n0, R - dfl, P['mu_floor'], fv, None, -1, 'zemin', 1.0))
            else:
                for x, q, n, pen in hc:
                    cons.append((x, q, n, pen, P['mu_floor'], fv, None, -1, 'zemin', 1.0 / len(hc)))
        # sabit parcalar (kure duzeyi)
        for q, n, dlt, pid in self.mesh.contacts(b.x):
            cons.append((b.x - n * R, q, n, dlt, P['mu_hard'], np.zeros(3), None, -1, self.part_names[pid], 1.0))
        # donen silindirler ve TPU makaralar
        for gidx, g in enumerate(gs):
            rel = b.x - g.c
            if np.linalg.norm(rel - (rel @ g.a) * g.a) > 0.09 or abs(rel @ g.a) > 0.15:
                continue
            for cc, rc, h, mu, nm in g.cyls:
                sdf = lambda X, cc=cc, rc=rc, h=h: cyl_sdf(X, cc, g.a, rc, h)
                phi, q, n = sdf(b.x[None])
                if phi[0] > R + 0.0005:
                    continue
                hc = self.hole_contact(b, Rm, n[0], sdf) if holes else None
                muw = P['mu_boot'] if 'Bootleg' in nm else P['mu_wheel']
                if hc is None:
                    if phi[0] < R:
                        cons.append((b.x - n[0] * R, q[0], n[0], R - phi[0], muw, None, g, -1, nm, 1.0))
                else:
                    for x, qq, nn, pen in hc:
                        cons.append((x, qq, nn, pen, muw, None, g, -1, nm, 1.0 / len(hc)))
            if gidx == 0:
                Rg = rot(g.a, g.theta)
                for ri, (c0, ax) in enumerate(self.roller_set()):
                    cw = g.c + Rg @ (c0 - g.c); ew = Rg @ ax
                    if np.linalg.norm(b.x - cw) > R + 0.013:
                        continue
                    sdf = lambda X, cw=cw, ew=ew: self.prof.sdf(X, cw, ew)
                    phi, q, n = sdf(b.x[None])
                    if phi[0] > R + 0.0005:
                        continue
                    hc = self.hole_contact(b, Rm, n[0], sdf) if holes else None
                    if hc is None:
                        if phi[0] < R:
                            cons.append((b.x - n[0] * R, q[0], n[0], R - phi[0], P['mu_tpu'], None, g, ri, 'TPU makara', 1.0))
                    else:
                        for x, qq, nn, pen in hc:
                            cons.append((x, qq, nn, pen, P['mu_tpu'], None, g, ri, 'TPU makara', 1.0 / len(hc)))
                            b.max_sink = max(b.max_sink, R - np.linalg.norm(qq - b.x))
        for o in others:
            dv = b.x - o.x; d = np.linalg.norm(dv)
            if d < 2 * R:
                n = dv / d
                cons.append((b.x - n * R, b.x - n * R, n, (2 * R - d) / 2, 0.4, o.v.copy(), None, -1, 'diger top', 1.0))
        return cons

    # surekli calisma ----------------------------------------------
    def run(self, balls, robot_v=0.5, t_max=2.5, dt=1e-4, rec_dt=1 / 600, intake_only=False, seed=0):
        rng = np.random.default_rng(seed)
        m = P['mass']; Ib = ball_I(m)
        B, pending = [], sorted(balls, key=lambda b: b[2])
        gs = self.groups
        for g in gs:
            g.w = g.target; g.theta = 0.0; g.min_w = abs(g.w); g.tau_peak = 0.0
        nroll = len(self.roller_set())
        wr = np.zeros(nroll)                       # makara kendi ekseninde donus hizi
        floor_v = np.array([robot_v, 0, 0], float) if np.isscalar(robot_v) else np.array(robot_v, float)
        rec = {'t': [], 'pos': [], 'quat': [], 'theta': [], 'wr': []}
        t, next_rec = 0.0, 0.0
        while t < t_max:
            while pending and pending[0][2] <= t:
                x, z, _ = pending.pop(0)
                q = rng.normal(size=4); q /= np.linalg.norm(q)
                B.append(Ball([x, R + M.FLOOR_Y, z], floor_v.copy(), q))
            for g in gs:
                g.w += g.motor_torque() / g.I * dt
            active = [b for b in B if b.state == 'aktif']
            if not active and not pending:
                break
            rset = self.roller_set()
            Rg0 = rot(gs[0].a, gs[0].theta)
            for b in active:
                cons = self.contacts(b, gs, floor_v, [o for o in active if o is not b])
                fn = []
                acc = M.G.copy()
                for (x, q, n, dlt, mu, vs, g, ri, lab, ks) in cons:
                    r = x - b.x
                    vsurf = vs if g is None else _cross(g.w * g.a, q - g.c)
                    if ri >= 0:
                        vsurf = vsurf + _cross(wr[ri] * (Rg0 @ rset[ri][1]), q - (gs[0].c + Rg0 @ (rset[ri][0] - gs[0].c)))
                    vrel = b.v + _cross(b.w, r) - vsurf
                    f = ks * normal_force(dlt, -(vrel @ n), P['stiff'])
                    fn.append(f)
                    acc += f * n / m
                    b.peak_f = max(b.peak_f, f)
                    b.touch[lab] = b.touch.get(lab, 0) + 1
                b.v += acc * dt
                # surtunme: 2B Coulomb konisi, PGS; makara donusu ve grup donusu dahil
                J = [np.zeros(3) for _ in cons]
                for it in range(5):
                    for i, (x, q, n, dlt, mu, vs, g, ri, lab, ks) in enumerate(cons):
                        if fn[i] <= 0:
                            continue
                        r = x - b.x
                        vsurf = vs if g is None else _cross(g.w * g.a, q - g.c)
                        if ri >= 0:
                            ew = Rg0 @ rset[ri][1]; cr = gs[0].c + Rg0 @ (rset[ri][0] - gs[0].c)
                            vsurf = vsurf + _cross(wr[ri] * ew, q - cr)
                        u = b.v + _cross(b.w, r) - vsurf
                        ut = u - (u @ n) * n
                        s = np.linalg.norm(ut)
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
                            K += levr * levr / P['roller_I']
                        mu_eff = mu * (P['mu_static'] if s < 0.02 else 1.0)
                        Jnew = J[i] - td * s / K
                        lim = mu_eff * fn[i] * dt
                        nJ = np.linalg.norm(Jnew)
                        if nJ > lim:
                            Jnew *= lim / nJ
                        dJ = Jnew - J[i]; J[i] = Jnew
                        b.v += dJ / m
                        b.w += _cross(r, dJ) / Ib
                        if g is not None:
                            dL = _cross(q - g.c, -dJ) @ g.a
                            g.w += dL / g.I
                            g.tau_peak = max(g.tau_peak, abs(dL) / dt)
                        if ri >= 0:
                            wr[ri] += (_cross(q - cr, -dJ) @ ew) / P['roller_I']
                # makara pim surtunmesi (yuke bagli Coulomb tork)
                for i, (x, q, n, dlt, mu, vs, g, ri, lab, ks) in enumerate(cons):
                    if ri >= 0:
                        tau = P['pin_mu'] * P['pin_r'] * fn[i] + 2e-6
                        dw = tau * dt / P['roller_I']
                        wr[ri] = 0.0 if abs(wr[ri]) <= dw else wr[ri] - np.sign(wr[ri]) * dw
                b.x += b.v * dt
                wn = np.linalg.norm(b.w)
                if wn > 1e-9:
                    hq = np.concatenate([[np.cos(wn * dt / 2)], np.sin(wn * dt / 2) * b.w / wn])
                    b.q = qmul(hq, b.q); b.q /= np.linalg.norm(b.q)
                # durum
                # takilma: robot cercevesinde 0.35 s boyunca 5 mm'den az yer degistirme (titresim dahil)
                if not hasattr(b, 'anchor') or np.linalg.norm(b.x - b.anchor) > 0.005:
                    b.anchor, b.t_anchor = b.x.copy(), t
                elif b.x[0] > -0.26 and t - b.t_anchor > P.get('stuck_t', 0.35):
                    b.state = 'takildi'; b.t_end = t; b.stuck_at = (b.x.copy(), [c[8] for c in cons])
                if b.x[0] < -0.33 and b.v[0] < -0.05:
                    b.kicked = True
                if intake_only and b.x[0] > -0.10 and b.x[1] > R + 0.01:
                    b.state = 'alindi'; b.t_end = t
                elif b.x[1] > 0.36 or (b.x[1] > 0.2 and np.linalg.norm(b.x[[0, 1]] - [0.05, 0.25]) > 0.17):
                    b.state = 'cikti'; b.t_end = t; b.exit_v = b.v.copy()
                elif abs(b.x[2]) > 0.30 or b.x[1] < -0.05 or b.x[0] < -0.9:
                    b.state = 'kacti'; b.t_end = t; b.stuck_at = (b.x.copy(), [])
            # bos makaralar da pim surtunmesiyle yavaslar
            wr *= np.exp(-dt / 0.3)
            for g in gs:
                g.theta += g.w * dt
                g.min_w = min(g.min_w, abs(g.w))
            if t >= next_rec:
                rec['t'].append(t)
                rec['pos'].append([b.x.copy() for b in B]); rec['quat'].append([b.q.copy() for b in B])
                rec['theta'].append([g.theta for g in gs]); rec['wr'].append(wr.copy())
                next_rec += rec_dt
            t += dt
        for b in B:
            if b.state == 'aktif':
                b.state = 'zaman asimi'; b.t_end = t; b.stuck_at = (b.x.copy(), [])
        return B, rec
