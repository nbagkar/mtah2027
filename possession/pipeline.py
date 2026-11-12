"""Tracking + config -> one label per row. The single entry point every script uses."""

import copy
import json
import os
import sys

import numpy as np

from . import deadball, features, possessor, segment

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR = os.path.join(ROOT, "vendor", "mtah")


def load_config(path=None, overrides=None):
    path = path or os.path.join(ROOT, "configs", "default.json")
    with open(path) as fh:
        cfg = json.load(fh)
    return with_overrides(cfg, overrides or {})


def predict(trk, cfg, blocks, return_parts=False):
    feat = features.compute(trk, cfg, blocks=blocks)
    home = possessor.home_logodds(feat, cfg)
    dead = deadball.dead_logodds(feat, cfg)
    labels = segment.decode(home, dead, cfg, blocks)
    if return_parts:
        return labels, {"features": feat, "home_logodds": home, "dead_logodds": dead}
    return labels


def scorer():
    """The official metric library, imported from the pinned challenge repo."""
    sys.path.insert(0, os.path.join(VENDOR, "evaluation"))
    import possession_metrics as pm  # noqa: E402
    return pm


def score(gt_labels, pred_labels):
    pm = scorer()
    r = pm.evaluate(pm.label_codes(list(gt_labels)), pm.label_codes(list(pred_labels)))
    keep = ("spell_f1_mean", "macro_f1", "n_gt_spells", "n_pred_spells",
            "alive_dead_f1", "team_acc_gt_alive")
    return {k: r[k] for k in keep}


def with_overrides(cfg, overrides):
    cfg = copy.deepcopy(cfg)
    for dotted, value in overrides.items():
        node = cfg
        *head, last = dotted.split(".")
        for k in head:
            node = node[k]
        node[last] = value
    return cfg


def blocks_from_gt(gt_labels):
    """Half-open spans where labels are not X -- for dev games, where we hold the GT."""
    graded = (np.asarray(gt_labels) != "X").astype(np.int8)
    edges = np.diff(np.concatenate(([0], graded, [0])))
    return list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)))
