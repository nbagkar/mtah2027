"""Fingerprint the dev set and the pipeline's labels on it, to compare machines.

    python scripts/dev_fingerprint.py      # after `make dev` has built devdata/

Prints one sha256 over every dev copy's tracking arrays and one over every predicted label
array. Two machines that print the same pair run the pipeline identically on the same inputs.
Dev set only (Metrica's public games); never reads competition data.
"""

import hashlib
import os
import platform
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from possession import pipeline  # noqa: E402
from scripts.score_dev import dev_games, load_npz  # noqa: E402


def main():
    cfg = pipeline.load_config()
    h_in, h_out, n = hashlib.sha256(), hashlib.sha256(), 0
    for game, gt, blocks, variants in dev_games():
        h_in.update("".join(gt).encode())
        for name, path in sorted(variants):
            trk = load_npz(path)
            for a in (trk.px, trk.py, trk.bx, trk.by):
                h_in.update(np.ascontiguousarray(a).tobytes())
            labels = pipeline.predict(trk, cfg, blocks)
            one = hashlib.sha256("".join(labels).encode()).hexdigest()
            h_out.update(one.encode())
            print("{} {:<14} labels {}".format(game, name, one[:16]), flush=True)
            n += 1
    print("machine  {} {} numpy {}".format(platform.system(), platform.machine(), np.__version__))
    print("copies   {}".format(n))
    print("inputs   sha256 {}".format(h_in.hexdigest()))
    print("labels   sha256 {}".format(h_out.hexdigest()))


if __name__ == "__main__":
    main()
