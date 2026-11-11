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


def viterbi(e, cost):
    """Max-score path. e: (T, 3) scores, cost: (3, 3) penalty for moving i -> j.

    Scalar Python on purpose: with 3 states, per-step numpy calls cost more than the arithmetic,
    and this version is ~10x faster while staying dependency-free and bit-for-bit deterministic.
    Ties break toward the lower state index (H, then A, then D), always the same way.
    """
    T = len(e)
    if T == 0:
        return np.empty(0, np.int8)
    c = cost.tolist()
    rows = e.tolist()
    s0, s1, s2 = rows[0]
    back = bytearray(3 * T)
    for t in range(1, T):
        e0, e1, e2 = rows[t]
        best = []
        for j in range(3):
            a, b, d = s0 - c[0][j], s1 - c[1][j], s2 - c[2][j]
            if a >= b and a >= d:
                best.append((a, 0))
            elif b >= d:
                best.append((b, 1))
            else:
                best.append((d, 2))
        k = 3 * t
        back[k], back[k + 1], back[k + 2] = best[0][1], best[1][1], best[2][1]
        s0, s1, s2 = best[0][0] + e0, best[1][0] + e1, best[2][0] + e2
    path = np.empty(T, np.int8)
    cur = 0 if (s0 >= s1 and s0 >= s2) else (1 if s1 >= s2 else 2)
    path[-1] = cur
    for t in range(T - 1, 0, -1):
        cur = back[3 * t + cur]
        path[t - 1] = cur
    return path


def decode(home_lo, dead_lo, cfg, blocks):
    """Labels for every row. blocks = [(start, stop)] half-open row spans that are played;
    rows outside every block get 'X'."""
    labels = np.full(len(home_lo), "X", dtype="<U1")
    cost = transition_costs(cfg)
    e = emissions(home_lo, dead_lo)
    for a, b in blocks:
        labels[a:b] = LABELS[viterbi(e[a:b], cost)]
    return labels
