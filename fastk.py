# Numba cekirdekleri: sim3.World.run icindeki top cozucusu ve mesh temaslarinin adim basi kismi.
# Islemler sim3.py'deki Python surumuyle ayni sirada yazildi; yalniz kucuk vektor ek yuku kalkar.
import numpy as np
import numba as nb


@nb.njit(cache=True, inline='always')
def _cr(a0, a1, a2, b0, b1, b2):
    return a1 * b2 - a2 * b1, a2 * b0 - a0 * b2, a0 * b1 - a1 * b0


@nb.njit(cache=True)
def _nforce(delta, ddot, CD, CF, st, cdamp):
    if delta > CD[-1]:
        v = CF[-1] + (delta - CD[-1]) * 6000
    else:
        v = np.interp(delta, CD, CF)
    f = st * v
    r = f + cdamp * ddot
    return r if r > 0.0 else 0.0


@nb.njit(cache=True)
def solve_ball(bx, bv, bw, X, Q, N, DL, MU, VS, GI, RI, KS, FLOOR,
               gw, ga, gc, gI, gtau, wr, CW, EW, G, m, Ib, rI, mu_s, crr, dt,
               CD, CF, st, cdamp, pin_mu, pin_r, fn):
    """Bir topun bir adimi: normal kuvvet, ivme, 5 tur surtunme impulsu, makara pim surtunmesi.
    bv, bw, gw, gtau, wr, fn yerinde guncellenir; en buyuk normal kuvveti dondurur."""
    nc = X.shape[0]
    a0, a1, a2 = G[0], G[1], G[2]
    peak = 0.0
    for i in range(nc):
        g = GI[i]; ri = RI[i]
        if g < 0:
            s0, s1, s2 = VS[i, 0], VS[i, 1], VS[i, 2]
        else:
            s0, s1, s2 = _cr(gw[g] * ga[g, 0], gw[g] * ga[g, 1], gw[g] * ga[g, 2],
                             Q[i, 0] - gc[g, 0], Q[i, 1] - gc[g, 1], Q[i, 2] - gc[g, 2])
        if ri >= 0:
            e0, e1, e2 = _cr(wr[ri] * EW[ri, 0], wr[ri] * EW[ri, 1], wr[ri] * EW[ri, 2],
                             Q[i, 0] - CW[ri, 0], Q[i, 1] - CW[ri, 1], Q[i, 2] - CW[ri, 2])
            s0 = s0 + e0; s1 = s1 + e1; s2 = s2 + e2
        c0, c1, c2 = _cr(bw[0], bw[1], bw[2], X[i, 0] - bx[0], X[i, 1] - bx[1], X[i, 2] - bx[2])
        v0 = bv[0] + c0 - s0; v1 = bv[1] + c1 - s1; v2 = bv[2] + c2 - s2
        f = KS[i] * _nforce(DL[i], -(v0 * N[i, 0] + v1 * N[i, 1] + v2 * N[i, 2]), CD, CF, st, cdamp)
        fn[i] = f
        a0 += f * N[i, 0] / m; a1 += f * N[i, 1] / m; a2 += f * N[i, 2] / m
        if crr > 0 and FLOOR[i]:
            r0 = bv[0] - VS[i, 0]; r2 = bv[2] - VS[i, 2]
            sp = np.hypot(r0, r2)
            if sp > 1e-3:
                a0 -= crr * f / m * r0 / sp; a2 -= crr * f / m * r2 / sp
        if f > peak:
            peak = f
    bv[0] += a0 * dt; bv[1] += a1 * dt; bv[2] += a2 * dt
    J = np.zeros((nc, 3))
    for it in range(5):
        for i in range(nc):
            if fn[i] <= 0:
                continue
            g = GI[i]; ri = RI[i]
            r0 = X[i, 0] - bx[0]; r1 = X[i, 1] - bx[1]; r2 = X[i, 2] - bx[2]
            if g < 0:
                s0, s1, s2 = VS[i, 0], VS[i, 1], VS[i, 2]
            else:
                s0, s1, s2 = _cr(gw[g] * ga[g, 0], gw[g] * ga[g, 1], gw[g] * ga[g, 2],
                                 Q[i, 0] - gc[g, 0], Q[i, 1] - gc[g, 1], Q[i, 2] - gc[g, 2])
            if ri >= 0:
                e0, e1, e2 = _cr(wr[ri] * EW[ri, 0], wr[ri] * EW[ri, 1], wr[ri] * EW[ri, 2],
                                 Q[i, 0] - CW[ri, 0], Q[i, 1] - CW[ri, 1], Q[i, 2] - CW[ri, 2])
                s0 = s0 + e0; s1 = s1 + e1; s2 = s2 + e2
            c0, c1, c2 = _cr(bw[0], bw[1], bw[2], r0, r1, r2)
            u0 = bv[0] + c0 - s0; u1 = bv[1] + c1 - s1; u2 = bv[2] + c2 - s2
            un = u0 * N[i, 0] + u1 * N[i, 1] + u2 * N[i, 2]
            t0 = u0 - un * N[i, 0]; t1 = u1 - un * N[i, 1]; t2 = u2 - un * N[i, 2]
            s = np.sqrt(t0 * t0 + t1 * t1 + t2 * t2)
            if s < 1e-10:
                continue
            d0 = t0 / s; d1 = t1 / s; d2 = t2 / s
            k0, k1, k2 = _cr(r0, r1, r2, d0, d1, d2)
            K = 1 / m + (k0 * k0 + k1 * k1 + k2 * k2) / Ib
            if g >= 0:
                l0, l1, l2 = _cr(Q[i, 0] - gc[g, 0], Q[i, 1] - gc[g, 1], Q[i, 2] - gc[g, 2], d0, d1, d2)
                lev = l0 * ga[g, 0] + l1 * ga[g, 1] + l2 * ga[g, 2]
                K += lev * lev / gI[g]
            if ri >= 0:
                l0, l1, l2 = _cr(Q[i, 0] - CW[ri, 0], Q[i, 1] - CW[ri, 1], Q[i, 2] - CW[ri, 2], d0, d1, d2)
                levr = l0 * EW[ri, 0] + l1 * EW[ri, 1] + l2 * EW[ri, 2]
                K += levr * levr / rI
            sk = s / K
            j0 = J[i, 0] - d0 * sk; j1 = J[i, 1] - d1 * sk; j2 = J[i, 2] - d2 * sk
            lim = MU[i] * (mu_s if s < 0.02 else 1.0) * fn[i] * dt
            nJ = np.sqrt(j0 * j0 + j1 * j1 + j2 * j2)
            if nJ > lim:
                sc = lim / nJ
                j0 *= sc; j1 *= sc; j2 *= sc
            q0 = j0 - J[i, 0]; q1 = j1 - J[i, 1]; q2 = j2 - J[i, 2]
            J[i, 0] = j0; J[i, 1] = j1; J[i, 2] = j2
            bv[0] += q0 / m; bv[1] += q1 / m; bv[2] += q2 / m
            w0, w1, w2 = _cr(r0, r1, r2, q0, q1, q2)
            bw[0] += w0 / Ib; bw[1] += w1 / Ib; bw[2] += w2 / Ib
            if g >= 0:
                l0, l1, l2 = _cr(Q[i, 0] - gc[g, 0], Q[i, 1] - gc[g, 1], Q[i, 2] - gc[g, 2], -q0, -q1, -q2)
                dL = l0 * ga[g, 0] + l1 * ga[g, 1] + l2 * ga[g, 2]
                gw[g] += dL / gI[g]
                if abs(dL) / dt > gtau[g]:
                    gtau[g] = abs(dL) / dt
            if ri >= 0:
                l0, l1, l2 = _cr(Q[i, 0] - CW[ri, 0], Q[i, 1] - CW[ri, 1], Q[i, 2] - CW[ri, 2], -q0, -q1, -q2)
                wr[ri] += (l0 * EW[ri, 0] + l1 * EW[ri, 1] + l2 * EW[ri, 2]) / rI
    for i in range(nc):
        ri = RI[i]
        if ri >= 0:
            dw = (pin_mu * pin_r * fn[i] + 2e-6) * dt / rI
            if abs(wr[ri]) <= dw:
                wr[ri] = 0.0
            else:
                wr[ri] = wr[ri] - np.sign(wr[ri]) * dw
    return peak


@nb.njit(cache=True)
def mesh_hits(p, T, R):
    """Onbellekteki ucgenlerde top temaslari: en yakin 6 (birbirine 0.85'ten yakin normaller elenir).
    Donus: (k, sira, q, n, delta)."""
    k = T.shape[0]
    q = np.empty((k, 3), T.dtype)
    for i in range(k):
        A = T[i, 0]; B = T[i, 1]; C = T[i, 2]
        ab0 = B[0] - A[0]; ab1 = B[1] - A[1]; ab2 = B[2] - A[2]
        ac0 = C[0] - A[0]; ac1 = C[1] - A[1]; ac2 = C[2] - A[2]
        ap0 = p[0] - A[0]; ap1 = p[1] - A[1]; ap2 = p[2] - A[2]
        d1 = ab0 * ap0 + ab1 * ap1 + ab2 * ap2; d2 = ac0 * ap0 + ac1 * ap1 + ac2 * ap2
        if d1 <= 0 and d2 <= 0:
            q[i, 0] = A[0]; q[i, 1] = A[1]; q[i, 2] = A[2]; continue
        bp0 = p[0] - B[0]; bp1 = p[1] - B[1]; bp2 = p[2] - B[2]
        d3 = ab0 * bp0 + ab1 * bp1 + ab2 * bp2; d4 = ac0 * bp0 + ac1 * bp1 + ac2 * bp2
        if d3 >= 0 and d4 <= d3:
            q[i, 0] = B[0]; q[i, 1] = B[1]; q[i, 2] = B[2]; continue
        vc = d1 * d4 - d3 * d2
        if vc <= 0 and d1 >= 0 and d3 <= 0:
            v = d1 / (d1 - d3)
            q[i, 0] = A[0] + ab0 * v; q[i, 1] = A[1] + ab1 * v; q[i, 2] = A[2] + ab2 * v; continue
        cp0 = p[0] - C[0]; cp1 = p[1] - C[1]; cp2 = p[2] - C[2]
        d5 = ab0 * cp0 + ab1 * cp1 + ab2 * cp2; d6 = ac0 * cp0 + ac1 * cp1 + ac2 * cp2
        if d6 >= 0 and d5 <= d6:
            q[i, 0] = C[0]; q[i, 1] = C[1]; q[i, 2] = C[2]; continue
        vb = d5 * d2 - d1 * d6
        if vb <= 0 and d2 >= 0 and d6 <= 0:
            w = d2 / (d2 - d6)
            q[i, 0] = A[0] + ac0 * w; q[i, 1] = A[1] + ac1 * w; q[i, 2] = A[2] + ac2 * w; continue
        va = d3 * d6 - d5 * d4
        if va <= 0 and (d4 - d3) >= 0 and (d5 - d6) >= 0:
            w2 = (d4 - d3) / ((d4 - d3) + (d5 - d6))
            q[i, 0] = B[0] + (C[0] - B[0]) * w2; q[i, 1] = B[1] + (C[1] - B[1]) * w2
            q[i, 2] = B[2] + (C[2] - B[2]) * w2; continue
        den = 1.0 / (va + vb + vc)
        v2 = vb * den; w3 = vc * den
        q[i, 0] = A[0] + ab0 * v2 + ac0 * w3; q[i, 1] = A[1] + ab1 * v2 + ac1 * w3
        q[i, 2] = A[2] + ab2 * v2 + ac2 * w3
    dv = np.empty((k, 3)); d = np.empty(k)
    for i in range(k):
        dv[i, 0] = p[0] - q[i, 0]; dv[i, 1] = p[1] - q[i, 1]; dv[i, 2] = p[2] - q[i, 2]
        d[i] = np.sqrt(dv[i, 0] * dv[i, 0] + dv[i, 1] * dv[i, 1] + dv[i, 2] * dv[i, 2])
    idx = np.nonzero(d < R)[0]
    idx = idx[np.argsort(d[idx], kind='mergesort')]
    oi = np.empty(6, np.int64); oq = np.empty((6, 3)); on = np.empty((6, 3)); od = np.empty(6)
    n_out = 0
    for i in idx:
        dd = d[i] if d[i] > 1e-9 else 1e-9
        n0 = dv[i, 0] / dd; n1 = dv[i, 1] / dd; n2 = dv[i, 2] / dd
        skip = False
        for j in range(n_out):
            if n0 * on[j, 0] + n1 * on[j, 1] + n2 * on[j, 2] > 0.85:
                skip = True; break
        if skip:
            continue
        oi[n_out] = i; oq[n_out, 0] = q[i, 0]; oq[n_out, 1] = q[i, 1]; oq[n_out, 2] = q[i, 2]
        on[n_out, 0] = n0; on[n_out, 1] = n1; on[n_out, 2] = n2; od[n_out] = R - d[i]
        n_out += 1
        if n_out >= 6:
            break
    return n_out, oi, oq, on, od


@nb.njit(cache=True)
def cyl_sdf(X, c, a, rc, h):
    k = X.shape[0]
    phi = np.empty(k); q = np.empty((k, 3)); n = np.empty((k, 3))
    for i in range(k):
        d0 = X[i, 0] - c[0]; d1 = X[i, 1] - c[1]; d2 = X[i, 2] - c[2]
        t = d0 * a[0] + d1 * a[1] + d2 * a[2]
        r0 = d0 - t * a[0]; r1 = d1 - t * a[1]; r2 = d2 - t * a[2]
        rho = np.sqrt(r0 * r0 + r1 * r1 + r2 * r2)
        rm = rho if rho > 1e-12 else 1e-12
        h0 = r0 / rm; h1 = r1 / rm; h2 = r2 / rm
        ds = rho - rc; dc = abs(t) - h
        out = ds > 0 or dc > 0
        st = np.sign(t)
        if out:
            phi[i] = np.hypot(max(ds, 0.0), max(dc, 0.0))
            tc = min(max(t, -h), h); rr = min(rho, rc)
            q0 = c[0] + tc * a[0] + h0 * rr; q1 = c[1] + tc * a[1] + h1 * rr; q2 = c[2] + tc * a[2] + h2 * rr
            e0 = X[i, 0] - q0; e1 = X[i, 1] - q1; e2 = X[i, 2] - q2
            en = np.sqrt(e0 * e0 + e1 * e1 + e2 * e2)
            en = en if en > 1e-12 else 1e-12
            n[i, 0] = e0 / en; n[i, 1] = e1 / en; n[i, 2] = e2 / en
        else:
            phi[i] = max(ds, dc)
            if ds > dc:
                q0 = c[0] + t * a[0] + h0 * rc; q1 = c[1] + t * a[1] + h1 * rc; q2 = c[2] + t * a[2] + h2 * rc
                n[i, 0] = h0; n[i, 1] = h1; n[i, 2] = h2
            else:
                q0 = c[0] + st * h * a[0] + r0; q1 = c[1] + st * h * a[1] + r1; q2 = c[2] + st * h * a[2] + r2
                n[i, 0] = st * a[0]; n[i, 1] = st * a[1]; n[i, 2] = st * a[2]
        q[i, 0] = q0; q[i, 1] = q1; q[i, 2] = q2
    return phi, q, n


@nb.njit(cache=True)
def prof_sdf(X, c, e, PA, PB, pt, pr):
    k = X.shape[0]; ns = PA.shape[0]
    phi = np.empty(k); q = np.empty((k, 3)); n = np.empty((k, 3))
    for i in range(k):
        d0 = X[i, 0] - c[0]; d1 = X[i, 1] - c[1]; d2 = X[i, 2] - c[2]
        tx = d0 * e[0] + d1 * e[1] + d2 * e[2]
        r0 = d0 - tx * e[0]; r1 = d1 - tx * e[1]; r2 = d2 - tx * e[2]
        rho = np.sqrt(r0 * r0 + r1 * r1 + r2 * r2)
        rm = rho if rho > 1e-12 else 1e-12
        h0 = r0 / rm; h1 = r1 / rm; h2 = r2 / rm
        best = np.inf; c0 = 0.0; c1 = 0.0
        for s in range(ns):
            ab0 = PB[s, 0] - PA[s, 0]; ab1 = PB[s, 1] - PA[s, 1]
            u = ((tx - PA[s, 0]) * ab0 + (rho - PA[s, 1]) * ab1) / (ab0 * ab0 + ab1 * ab1)
            u = min(max(u, 0.0), 1.0)
            x0 = PA[s, 0] + u * ab0; x1 = PA[s, 1] + u * ab1
            dd = np.hypot(tx - x0, rho - x1)
            if dd < best:
                best = dd; c0 = x0; c1 = x1
        inside = abs(tx) <= pt[-1] and rho <= np.interp(tx, pt, pr)
        q0 = c[0] + c0 * e[0] + h0 * c1; q1 = c[1] + c0 * e[1] + h1 * c1; q2 = c[2] + c0 * e[2] + h2 * c1
        bm = best if best > 1e-12 else 1e-12
        sg = -1.0 if inside else 1.0
        phi[i] = sg * best
        q[i, 0] = q0; q[i, 1] = q1; q[i, 2] = q2
        n[i, 0] = sg * (X[i, 0] - q0) / bm; n[i, 1] = sg * (X[i, 1] - q1) / bm; n[i, 2] = sg * (X[i, 2] - q2) / bm
    return phi, q, n
