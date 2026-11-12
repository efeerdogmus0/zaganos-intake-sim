# Top yolu fizik cozucusu: tek/birden cok top, gercek CAD ucgenleri, motorlu tekerlekler.
#
# Temas: top uyumlu (ezilme egrisi + sonum), surtunme hiz duzeyinde Coulomb (PGS),
# serbest TPU makaralar sadece eksenleri boyunca surtunme uygular.
# Zemin robot cercevesinde hareket eder (robot ileri giderken zemin +x yonunde akar).
import time
import numpy as np
import model as M

R = M.BALL_R
STIFF = 1.0

# ------------------------------------------------------------------ geometri yardimcilari
def closest_on_tris(p, A, B, C):
    """p noktasinin her ucgene en yakin noktasi (Ericson, vektorlu)."""
    ab, ac, ap = B - A, C - A, p - A
    d1 = np.einsum('ij,ij->i', ab, ap); d2 = np.einsum('ij,ij->i', ac, ap)
    bp = p - B
    d3 = np.einsum('ij,ij->i', ab, bp); d4 = np.einsum('ij,ij->i', ac, bp)
    cp = p - C
    d5 = np.einsum('ij,ij->i', ab, cp); d6 = np.einsum('ij,ij->i', ac, cp)
    vc = d1 * d4 - d3 * d2; vb = d5 * d2 - d1 * d6; va = d3 * d6 - d5 * d4
    out = np.empty_like(A)
    done = np.zeros(len(A), bool)

    def put(mask, val):
        nonlocal done
        m = mask & ~done
        if m.any():
            out[m] = val[m] if val.ndim == 2 else val
            done |= m
    with np.errstate(divide='ignore', invalid='ignore'):
        put((d1 <= 0) & (d2 <= 0), A)
        put((d3 >= 0) & (d4 <= d3), B)
        v = d1 / (d1 - d3)
        put((vc <= 0) & (d1 >= 0) & (d3 <= 0), A + ab * v[:, None])
        put((d6 >= 0) & (d5 <= d6), C)
        w = d2 / (d2 - d6)
        put((vb <= 0) & (d2 >= 0) & (d6 <= 0), A + ac * w[:, None])
        w2 = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        put((va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0), B + (C - B) * w2[:, None])
        den = 1.0 / (va + vb + vc)
        v2 = vb * den; w3 = vc * den
        put(np.ones(len(A), bool), A + ab * v2[:, None] + ac * w3[:, None])
    return out

class StaticMesh:
    def __init__(self, tri, part, cell=0.015):
        self.tri, self.part, self.cell = tri, part, cell
        self.bmin, self.bmax = tri.min(1), tri.max(1)
        lo = np.floor(self.bmin / cell).astype(np.int64)
        hi = np.floor(self.bmax / cell).astype(np.int64)
        self.off = lo.min(0) - 2
        self.dim = hi.max(0) - self.off + 3
        n = hi - lo + 1
        cnt = n.prod(1)
        ids = np.repeat(np.arange(len(tri)), cnt)
        k = np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)
        nx, ny = n[ids, 0], n[ids, 1]
        ix = lo[ids, 0] + k % nx
        iy = lo[ids, 1] + (k // nx) % ny
        iz = lo[ids, 2] + k // (nx * ny)
        keys = self._key(ix, iy, iz)
        order = np.argsort(keys, kind='stable')
        self.keys, self.ids = keys[order], ids[order]
        self.cache_p, self.cache = None, None

    def _key(self, ix, iy, iz):
        return ((ix - self.off[0]) * self.dim[1] + (iy - self.off[1])) * self.dim[2] + (iz - self.off[2])

    def candidates(self, p, rad):
        lo = np.floor((p - rad) / self.cell).astype(np.int64)
        hi = np.floor((p + rad) / self.cell).astype(np.int64)
        gx, gy, gz = np.meshgrid(*[np.arange(lo[i], hi[i] + 1) for i in range(3)], indexing='ij')
        q = self._key(gx.ravel(), gy.ravel(), gz.ravel())
        a = np.searchsorted(self.keys, q, 'left'); b = np.searchsorted(self.keys, q, 'right')
        sel = [self.ids[i:j] for i, j in zip(a, b) if j > i]
        if not sel:
            return np.zeros(0, np.int64)
        c = np.unique(np.concatenate(sel))
        ok = ((self.bmin[c] <= p + rad) & (self.bmax[c] >= p - rad)).all(1)
        return c[ok]

    def contacts(self, p, margin=0.008):
        if self.cache_p is None or np.linalg.norm(p - self.cache_p) > margin * 0.5:
            self.cache = self.candidates(p, R + margin); self.cache_p = p.copy()
        c = self.cache
        if len(c) == 0:
            return []
        t = self.tri[c]
        q = closest_on_tris(p, t[:, 0], t[:, 1], t[:, 2])
        dv = p - q
        d = np.linalg.norm(dv, axis=1)
        hit = d < R
        if not hit.any():
            return []
        idx = np.nonzero(hit)[0]
        idx = idx[np.argsort(d[idx])]
        out = []
        for i in idx:
            n = dv[i] / max(d[i], 1e-9)
            if any(n @ o[1] > 0.85 for o in out):
                continue
            out.append((q[i], n, R - d[i], int(self.part[c[i]])))
            if len(out) >= 6:
                break
        return out

def rot(axis, ang):
    a = axis / np.linalg.norm(axis)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(ang) * K + (1 - np.cos(ang)) * K @ K

def cyl_contact(p, c, a, rc, h):
    """Dolu silindire (merkez c, eksen a, yaricap rc, yari genislik h) en yakin nokta ve normal."""
    rp = p - c
    t = rp @ a
    rv = rp - t * a
    rho = np.linalg.norm(rv)
    rh = rv / rho if rho > 1e-9 else np.array([1.0, 0, 0])
    if abs(t) <= h and rho >= rc:
        q = c + t * a + rc * rh; n = rh; d = rho - rc
    elif rho <= rc and abs(t) > h:
        q = c + np.sign(t) * h * a + rv; n = np.sign(t) * a; d = abs(t) - h
    elif abs(t) > h and rho > rc:
        q = c + np.sign(t) * h * a + rc * rh
        dv = p - q; d = np.linalg.norm(dv); n = dv / d
    else:  # merkez silindirin icinde
        if rc - rho < h - abs(t):
            q = c + t * a + rc * rh; n = rh; d = -(rc - rho)
        else:
            q = c + np.sign(t) * h * a + rv; n = np.sign(t) * a; d = -(h - abs(t))
    return q, n, d

def seg_contact(p, c, a, r, h):
    t = np.clip((p - c) @ a, -h, h)
    s = c + t * a
    dv = p - s; d = np.linalg.norm(dv)
    n = dv / max(d, 1e-9)
    return s + n * r, n, d - r

# ------------------------------------------------------------------ cozucu
class Ball:
    def __init__(self, x, v):
        self.x = np.array(x, float); self.v = np.array(v, float)
        self.w = np.zeros(3); self.q = np.array([1.0, 0, 0, 0])
        self.state = 'aktif'; self.t_slow = 0.0; self.t_end = None
        self.exit_v = None; self.peak_f = 0.0; self.touch = {}
        self.stuck_at = None
        self.kicked = False
        self.x0 = self.x.copy()

def qmul(a, b):
    w1, x1, y1, z1 = a; w2, x2, y2, z2 = b
    return np.array([w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                     w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2])

def normal_force(delta, ddot):
    f = STIFF * np.interp(delta, M.CURVE_D, M.CURVE_F, right=M.CURVE_F[-1] + (delta - M.CURVE_D[-1]) * 6000)
    k = 3000.0 * STIFF
    c = 2 * 0.22 * np.sqrt(k * M.BALL_M)          # carpma ~0.5 geri sekme
    return max(0.0, f + c * ddot)

class World:
    def __init__(self, region='region.npz', speeds=None):
        self.groups, tri, part, self.part_names = M.build(region)
        self.mesh = StaticMesh(tri, part)
        self.base = {g.name: (g.c.copy(), g.target) for g in self.groups}
        if speeds:
            self.set_speeds(speeds)

    def set_speeds(self, scale):
        for g in self.groups:
            s = scale.get(g.name, scale.get(g.name.rstrip('0123456789_'), 1.0))
            for key in ('intake', 'Feeder', 'flywheel', 'sushi'):
                if g.name.startswith(key):
                    s = scale.get(key, s)
            g.target = self.base[g.name][1] * s
            g.w = g.target; g.theta = 0.0; g.min_w = abs(g.w)

    def run(self, balls, robot_v=0.5, robot_stop=None, t_max=2.5, dt=1e-4, rec_dt=1 / 600, log=False):
        """balls: [(x, z, t_spawn)] zemin uzerinde. Donus: her top icin sonuc + kayit."""
        B = []
        pending = sorted(balls, key=lambda b: b[2])
        rec = {'t': [], 'pos': [], 'quat': [], 'theta': [], 'w': []}
        t, next_rec = 0.0, 0.0
        gs = self.groups
        for g in gs:
            g.w = g.target; g.theta = 0.0; g.min_w = abs(g.w); g.tau_peak = 0.0
        floor_v = np.array([robot_v, 0, 0], float) if np.isscalar(robot_v) else np.array(robot_v, float)
        t0 = time.time()
        while t < t_max:
            while pending and pending[0][2] <= t:
                x, z, _ = pending.pop(0)
                B.append(Ball([x, R + M.FLOOR_Y, z], floor_v.copy()))
            fv = floor_v if (robot_stop is None or t < robot_stop) else np.zeros(3)
            # motorlar
            for g in gs:
                g.w += g.motor_torque() / g.I * dt
            active = [b for b in B if b.state == 'aktif']
            if not active and not pending:
                break
            for b in active:
                cons = []   # (q, n, delta, mu, surface_v, group, roller_axis, label)
                # zemin
                dfl = b.x[1] - M.FLOOR_Y
                if dfl < R:
                    cons.append((b.x - np.array([0, dfl, 0]), np.array([0, 1.0, 0]), R - dfl, M.MU_FLOOR,
                                 fv, None, None, 'zemin'))
                for q, n, dlt, pid in self.mesh.contacts(b.x):
                    cons.append((q, n, dlt, M.MU_HARD, np.zeros(3), None, None, self.part_names[pid]))
                for g in gs:
                    rel = b.x - g.c
                    if np.linalg.norm(rel - (rel @ g.a) * g.a) > 0.09 or abs(rel @ g.a) > 0.15:
                        continue
                    wv = g.w * g.a
                    for cc, rc, h, mu, nm in g.cyls:
                        q, n, d = cyl_contact(b.x, cc, g.a, rc, h)
                        if d < R:
                            cons.append((q, n, R - d, mu, np.cross(wv, q - g.c), g, None, nm))
                    if g.rollers:
                        Rm = rot(g.a, g.theta)
                        for c0, ax, rr, hh in g.rollers:
                            cw = g.c + Rm @ (c0 - g.c); aw = Rm @ ax
                            q, n, d = seg_contact(b.x, cw, aw, rr, hh)
                            if d < R:
                                cons.append((q, n, R - d, M.MU_WHEEL, np.cross(wv, q - g.c), g, aw, 'TPU makara'))
                for o in B:
                    if o is b or o.state != 'aktif':
                        continue
                    dv = b.x - o.x; d = np.linalg.norm(dv)
                    if d < 2 * R:
                        n = dv / d
                        cons.append((b.x - n * R, n, (2 * R - d) / 2, 0.4, o.v + np.cross(o.w, -n * R) * 0, None, None, 'diger top'))
                # normal kuvvetler
                fn = []
                acc = M.G.copy()
                for q, n, dlt, mu, vs, g, ax, lab in cons:
                    r = q - b.x
                    vrel = b.v + np.cross(b.w, r) - vs
                    f = normal_force(dlt, -(vrel @ n))
                    fn.append(f)
                    acc += f * n / M.BALL_M
                    b.peak_f = max(b.peak_f, f)
                    b.touch[lab] = b.touch.get(lab, 0) + 1
                b.v += acc * dt
                # surtunme (PGS)
                J = [np.zeros(3) for _ in cons]
                for it in range(4):
                    for i, (q, n, dlt, mu, vs, g, ax, lab) in enumerate(cons):
                        if fn[i] <= 0:
                            continue
                        r = q - b.x
                        vs_now = np.cross(g.w * g.a, q - g.c) if g is not None else vs
                        u = b.v + np.cross(b.w, r) - vs_now
                        ut = u - (u @ n) * n
                        if ax is not None:
                            e = ax - (ax @ n) * n
                            ne = np.linalg.norm(e)
                            if ne < 1e-6:
                                continue
                            e /= ne
                            ut = (ut @ e) * e
                        s = np.linalg.norm(ut)
                        if s < 1e-9:
                            continue
                        tdir = ut / s
                        K = 1 / M.BALL_M + R * R / M.BALL_I
                        if g is not None:
                            lev = np.cross(q - g.c, tdir) @ g.a
                            K += lev * lev / g.I
                        jn = -tdir * s / K
                        Jnew = J[i] + jn
                        lim = mu * fn[i] * dt
                        nJ = np.linalg.norm(Jnew)
                        if nJ > lim:
                            Jnew *= lim / nJ
                        dJ = Jnew - J[i]; J[i] = Jnew
                        b.v += dJ / M.BALL_M
                        b.w += np.cross(r, dJ) / M.BALL_I
                        if g is not None:
                            dL = np.cross(q - g.c, -dJ) @ g.a
                            g.w += dL / g.I
                            g.tau_peak = max(g.tau_peak, abs(dL) / dt)
                # entegrasyon
                b.x += b.v * dt
                wn = np.linalg.norm(b.w)
                if wn > 1e-9:
                    hq = np.concatenate([[np.cos(wn * dt / 2)], np.sin(wn * dt / 2) * b.w / wn])
                    b.q = qmul(hq, b.q); b.q /= np.linalg.norm(b.q)
                # durum
                sp = np.linalg.norm(b.v)            # robot cercevesinde hiz
                if b.x[0] > -0.26 and sp < 0.03:
                    b.t_slow += dt
                    if b.t_slow > 0.4:
                        b.state = 'takildi'; b.t_end = t
                        b.stuck_at = (b.x.copy(), [c[7] for c in cons])
                else:
                    b.t_slow = 0.0
                if b.x[0] < -0.33 and b.v[0] < -0.05:
                    b.kicked = True                 # one geri tepildi; robot ilerledikce tekrar gelebilir
                if b.x[1] > 0.36 or (b.x[1] > 0.2 and np.linalg.norm(b.x[[0, 1]] - [0.05, 0.25]) > 0.17):
                    b.state = 'cikti'; b.t_end = t; b.exit_v = b.v.copy()
                elif abs(b.x[2]) > 0.30 or b.x[1] < -0.05 or b.x[0] < -0.9:
                    b.state = 'kacti'; b.t_end = t; b.stuck_at = (b.x.copy(), [])
            for g in gs:
                g.theta += g.w * dt
                g.min_w = min(g.min_w, abs(g.w))
            if t >= next_rec:
                rec['t'].append(t)
                rec['pos'].append([b.x.copy() for b in B]); rec['quat'].append([b.q.copy() for b in B])
                rec['theta'].append([g.theta for g in gs]); rec['w'].append([g.w for g in gs])
                next_rec += rec_dt
            t += dt
        for b in B:
            if b.state == 'aktif':
                b.state = 'zaman asimi'; b.t_end = t; b.stuck_at = (b.x.copy(), [])
        if log:
            print(f'  {t:.2f} s simulasyon, {time.time() - t0:.1f} s hesap')
        return B, rec

def summary(b, gs=None):
    s = f'{b.state:11s} t={b.t_end:.3f}s  tepe kuvvet={b.peak_f:5.1f} N'
    if b.exit_v is not None:
        s += f'  cikis hizi={np.linalg.norm(b.exit_v):.2f} m/s  yon={np.round(b.exit_v / np.linalg.norm(b.exit_v), 2)}'
    if b.stuck_at is not None:
        s += f'  yer={np.round(b.stuck_at[0], 3)}  temas={sorted(set(b.stuck_at[1]))[:5]}'
    return s

if __name__ == '__main__':
    import sys
    W = World(sys.argv[1] if len(sys.argv) > 1 else 'region.npz')
    B, rec = W.run([(-0.30, 0.0, 0.0)], robot_v=0.5, log=True)
    for b in B:
        print(summary(b))
    for g in W.groups:
        print(f'  {g.name:18s} hedef {g.target / M.RPM:7.0f} rpm  en dusuk {g.min_w / M.RPM:7.0f} rpm  tepe yuk {g.tau_peak:.3f} Nm')
    np.savez('traj_single.npz', t=np.array(rec['t']), pos=np.array([p[0] for p in rec['pos']]), stride=20)
    print('en cok temas:', sorted(B[0].touch.items(), key=lambda kv: -kv[1])[:12])
