"""Turn per-frame evidence into possessions: a 3-state Viterbi over {H, A, D}. Owner: segmenter.

This is where spellF1 is won or lost. Per-frame evidence flickers; the ranking metric counts each
possession once, so every spurious switch costs a whole possession. The switch penalties below
are the main knobs, and must be chosen on the dev set (devset/), never on the public 5 minutes.

States 0=H, 1=A, 2=D. Emission score per frame:
    H: +home/2 - dead/2      A: -home/2 - dead/2      D: +dead/2
(log-odds halves, so a log-odds of 0 is indifferent between all three.)
"""

import numpy as np

H, A, D = 0, 1, 2
LABELS = np.array(["H", "A", "D"])


def emissions(home_lo, dead_lo):
    e = np.empty((len(home_lo), 3))
    e[:, H] = 0.5 * home_lo - 0.5 * dead_lo
    e[:, A] = -0.5 * home_lo - 0.5 * dead_lo
    e[:, D] = 0.5 * dead_lo
    return e


def transition_costs(cfg):
    s = cfg["segment"]
    t = np.zeros((3, 3))
    t[H, A] = t[A, H] = s["cost_team_switch"]
    t[H, D] = t[A, D] = s["cost_to_dead"]
    t[D, H] = t[D, A] = s["cost_from_dead"]
    return t


def viterbi(e, cost, min_dead=1):
    """Max-score path. e: (T, 3) scores, cost: (3, 3) penalty for moving i -> j.

    min_dead: a dead spell must last at least this many frames. Without it the decoder can
    hand the ball from one team to the other through a 1-frame D for cost_to_dead +
    cost_from_dead, which caps the effective team-switch cost and litters the output with
    fake stoppages (real ones under 1 s are ~1% of the dev set's). Implemented as a
    duration chain: entering D at frame s commits frames s..s+K-1 to D (scored with a prefix
    sum of the D emissions); only the "matured" D state can stay or leave. min_dead=1 is the
    plain 3-state Viterbi.

    Scalar Python on purpose: with 3 states, per-step numpy calls cost more than the arithmetic,
    and this stays dependency-free and bit-for-bit deterministic. Ties break toward H, then A,
    then D, always the same way.
    """
    T = len(e)
    if T == 0:
        return np.empty(0, np.int8)
    K = max(1, int(min_dead))
    c = cost.tolist()
    rows = e.tolist()
    ninf = float("-inf")
    eD = [r[2] for r in rows]
    if K > 1:
        P = [0.0] * (T + 1)
        for t in range(T):
            P[t + 1] = P[t] + eD[t]
    # ent[s]: best score just before frame s for a path that enters D at s; ent_src[s]: 0=H,
    # 1=A, 3=path starts in D at frame 0.
    ent = [ninf] * T
    ent_src = bytearray(T)
    ent[0], ent_src[0] = 0.0, 3
    back = bytearray(3 * T)   # per frame: predecessor of H, of A, and for D 2=stay / 4=chain
    s0, s1 = rows[0][0], rows[0][1]
    s2 = rows[0][2] if K == 1 else ninf
    if K == 1:
        back[2] = 4
    for t in range(1, T):
        e0, e1, e2 = rows[t]
        # into H
        a, b, d = s0, s1 - c[1][0], s2 - c[2][0]
        if a >= b and a >= d:
            n0, p0 = a, 0
        elif b >= d:
            n0, p0 = b, 1
        else:
            n0, p0 = d, 2
        # into A
        a, b, d = s0 - c[0][1], s1, s2 - c[2][1]
        if a >= b and a >= d:
            n1, p1 = a, 0
        elif b >= d:
            n1, p1 = b, 1
        else:
            n1, p1 = d, 2
        # entering D at t
        a, b = s0 - c[0][2], s1 - c[1][2]
        if a >= b:
            ent[t], ent_src[t] = a, 0
        else:
            ent[t], ent_src[t] = b, 1
        # matured D at t: stay, or a chain that entered at t-K+1 and just completed
        stay = s2 + e2
        s = t - K + 1
        if s >= 0:
            chain = ent[s] + (e2 if K == 1 else P[t + 1] - P[s])
        else:
            chain = ninf
        if chain >= stay:
            n2, p2 = chain, 4
        else:
            n2, p2 = stay, 2
        k = 3 * t
        back[k], back[k + 1], back[k + 2] = p0, p1, p2
        s0, s1, s2 = n0 + e0, n1 + e1, n2
    path = np.empty(T, np.int8)
    cur = 0 if (s0 >= s1 and s0 >= s2) else (1 if s1 >= s2 else 2)
    t = T - 1
    while t >= 0:
        if cur == 2:
            if back[3 * t + 2] == 2:
                path[t] = 2
                t -= 1
                continue
            s = t - K + 1
            path[s:t + 1] = 2
            src = ent_src[s]
            if src == 3:
                break
            cur, t = src, s - 1
        else:
            path[t] = cur
            if t == 0:
                break
            cur = back[3 * t + cur]
            t -= 1
    return path


def decode(home_lo, dead_lo, cfg, blocks):
    """Labels for every row. blocks = [(start, stop)] half-open row spans that are played;
    rows outside every block get 'X'."""
    labels = np.full(len(home_lo), "X", dtype="<U1")
    cost = transition_costs(cfg)
    e = emissions(home_lo, dead_lo)
    for a, b in blocks:
        labels[a:b] = LABELS[viterbi(e[a:b], cost, cfg["segment"].get("min_dead_frames", 1))]
    return labels
