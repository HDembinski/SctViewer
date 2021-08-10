from sctviewer.mainwindow import PID
import numpy as np
from particle import Particle

all_pids = np.array(sum(PID.values(), start=()))


def test_positive():
    for pid in all_pids:
        assert pid > 0, f"{pid} -> {Particle.from_pdgid(pid).name}"


def test_long_lived():

    # skip gluon, ID 21
    all_long_lived = set(
        abs(p.pdgid)
        for p in Particle.findall(lambda p: p.ctau > 1)
        if abs(p.pdgid) != 21
    )

    assert set(all_pids) == all_long_lived
