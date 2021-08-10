import numpy as np
from matplotlib.backends.qt_compat import QtWidgets, QtCore
from matplotlib.backends.backend_qt5agg import (
    FigureCanvas,
    NavigationToolbar2QT as NavigationToolbarBase,
)
from matplotlib.figure import Figure
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
import uproot
import awkward  # noqa
import warnings
import particle


def pid_to_name(pid):
    try:
        name = particle.Particle.from_pdgid(pid).name
    except particle.InvalidParticle:
        name = f"Unknown({pid})"
    return name


LONG_LIVED_PIDs = set(particle.Particle.findall(lambda p: p.ctau > 1))
# particle 0.15.1 uses None for ctau of neutrinos, add neutrinos by hand for now
for p in particle.Particle.findall(lambda p: "nu" in p.name):
    LONG_LIVED_PIDs.add(p.pdgid)

# categories of long-lived particles
PID = {
    "pi": (particle.literals.pi_plus.pdgid,),
    "K": (particle.literals.K_plus.pdgid,),
    "p": (particle.literals.proton.pdgid, 1000010010),
    "n": (particle.literals.neutron.pdgid, 1000000010),
    "e": (particle.literals.e_minus.pdgid,),
    "mu": (particle.literals.mu_minus.pdgid,),
    "gamma": (particle.literals.gamma.pdgid,),
    "strange_neutral": (
        particle.literals.K_S_0.pdgid,
        particle.literals.K_L_0.pdgid,
        particle.literals.Lambda.pdgid,
        particle.literals.Xi_0.pdgid,
    ),
    "strange_charged": (
        particle.literals.Sigma_minus.pdgid,
        particle.literals.Sigma_plus.pdgid,
        particle.literals.Xi_minus.pdgid,
        particle.literals.Omega_minus.pdgid,
    ),
}

COLOR = {
    "pi": "darkorange",
    "K": "steelblue",
    "p": "k",
    "n": "k",
    "e": "gold",
    "gamma": "gold",
    "mu": "forestgreen",
    "strange_neutral": "teal",
    "strange_charged": "teal",
    "nuclei": "k",
    "other": "fuchsia",
}


class NavigationToolbar(NavigationToolbarBase):
    toolitems = [
        t
        for t in NavigationToolbarBase.toolitems
        if t[0] in ("Home", "Pan", "Zoom", "Save")
    ]


class PointCollection:
    def __init__(self, ax, color, zorder):
        self._pts = Line2D(
            [], [], marker="o", ls="", mec=color, color="none", ms=10, zorder=zorder
        )
        ax.add_artist(self._pts)

    def update(self, a, b):
        self._pts.set_data(a, b)


class TrackCollection:
    def __init__(self, ax, color, alpha, zorder, linestyle):
        self._lines = LineCollection(
            [], colors=color, alpha=alpha, zorder=zorder, linestyles=linestyle
        )
        self._pts = Line2D(
            [],
            [],
            marker=".",
            ls="",
            mfc=color,
            mec="none",
            zorder=zorder,
        )
        ax.add_collection(self._lines)
        ax.add_artist(self._pts)

    def update(self, a0, b0, a1, b1):
        self._lines.set_segments(
            [[(a0i, b0i), (a1i, b1i)] for (a0i, b0i, a1i, b1i) in zip(a0, b0, a1, b1)]
        )
        self._pts.set_data(a0, b0)


class MainWindow(QtWidgets.QMainWindow):

    _range = None
    _tree = None
    _canvas = None
    _data = None
    _debug = False

    def __init__(self, filename):
        super().__init__()

        f = uproot.open(filename)

        # file can contain trees with different names, sct or ana, and also may
        # have several versions, sct;4 and sct;5 for instance
        keys = set(k.split(";")[0] for k in f.keys())
        if len(keys) != 1:
            raise SystemExit("Error: files contains more than one tree")

        self._tree = f[next(iter(keys))]

        self._main = QtWidgets.QWidget()
        self._main.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setCentralWidget(self._main)

        self._fig = Figure(figsize=(12, 4.5))
        self._ax = {
            "xy": self._fig.add_axes([0.08, 0.1, 0.35, 0.74]),
            "zx": self._fig.add_axes([0.52, 0.1, 0.45, 0.35]),
        }
        self._ax["zy"] = self._fig.add_axes(
            [0.52, 0.49, 0.45, 0.35], sharex=self._ax["zx"], sharey=self._ax["xy"]
        )

        self._canvas = FigureCanvas(self._fig)
        self._navigation = NavigationToolbar(self._canvas, self)
        self.addToolBar(self._navigation)

        self._velo_visible = QtWidgets.QPushButton("VELO tracks")
        self._long_visible = QtWidgets.QPushButton("Long tracks")
        self._generator_visible = QtWidgets.QPushButton("Generator tracks")
        for button in (self._velo_visible, self._long_visible, self._generator_visible):
            button.setCheckable(True)
            button.setChecked(True)
            button.clicked.connect(self._process_event)

        b = QtWidgets.QPushButton("Backward")
        f = QtWidgets.QPushButton("Forward")
        s = QtWidgets.QSpinBox()
        b.clicked.connect(self._backward)
        f.clicked.connect(self._forward)
        s.setRange(1, self._tree.num_entries)
        s.setSingleStep(10)
        s.valueChanged.connect(self._jump)
        self._spinbox = s

        layout = QtWidgets.QVBoxLayout(self._main)
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self._velo_visible)
        button_layout.addWidget(self._long_visible)
        button_layout.addWidget(self._generator_visible)
        layout.addLayout(button_layout)
        layout.addWidget(self._canvas)
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(b)
        button_layout.addWidget(f)
        button_layout.addWidget(s)
        layout.addLayout(button_layout)

        self._update_data()
        self._init_canvas()
        self._process_event()

    def _update_data(self):
        tree = self._tree
        ievent = self._spinbox.value() - 1
        self._range = max(0, ievent - 50), min(ievent + 50, tree.num_entries)
        self._data = tree.arrays(
            filter_name=[
                "vtx_len",
                "vtx_[xyz]",
                "trk_len",
                "trk_[xyz]",
                "trk_p[xyz]",
                "vtrk_len",
                "vtrk_[xyz]",
                "vtrk_p[xyz]",
                "mc_vtx_len",
                "mc_trk_len",
                "mc_trk_[xyz]",
                "mc_trk_p[xyz]",
                "mc_trk_imot",
                "mc_trk_pid",
            ],
            entry_start=self._range[0],
            entry_stop=self._range[1],
        )

    def _get(self, *args):
        d = self._data
        i = self._spinbox.value() - 1 - self._range[0]
        if len(args) == 1:
            return np.asarray(d[args[0]][i])
        return (np.asarray(d[arg][i]) for arg in args)

    def _init_canvas(self):
        d = self._data

        def r(d, s, delta, sym):
            xmin = []
            xmax = []
            for src in (f"vtx_{s}", f"trk_{s}", f"vtrk_{s}"):
                try:
                    x = d[src]
                    xmin.append(np.min(x))
                    xmax.append(np.max(x))
                except ValueError:
                    warnings.warn(f"Branch {src} not found")
                    continue
            xmin = min(xmin)
            xmax = max(xmax)
            if sym:
                xmax = max(-xmin, xmax)
                return -xmax, xmax
            return xmin, xmax

        self._lim = {
            "x": r(d, "x", 1, True),
            "y": r(d, "y", 1, True),
            "z": r(d, "z", 10, False),
        }

        for (dim0, dim1), ax in self._ax.items():
            ax.set_xlim(*self._lim[dim0])
            ax.set_ylim(*self._lim[dim1])
            ax.set_xlabel(f"{dim0} / mm")
            ax.set_ylabel(f"{dim1} / mm")

        self._ax["zy"].xaxis.set_visible(False)

        for ax in self._ax.values():
            obj = {"vtx": PointCollection(ax, "r", 4)}
            handles = []
            alpha = 0.3
            for type, col, zorder in (
                ("vtrk", "r", 2),
                ("trk", "b", 3),
            ):
                neutral = type.endswith("neutral") or type in ("n", "gamma")
                obj[type] = TrackCollection(ax, col, alpha, zorder, "-")
                handles.append(Line2D([], [], color=col))
            zorder = 1
            for i, type in enumerate(PID):
                neutral = type.endswith("neutral") or type in ("n", "gamma")
                linestyle = ":" if neutral else "-"
                col = COLOR[type]
                obj[type] = TrackCollection(ax, col, alpha, zorder, linestyle)
                handles.append(Line2D([], [], color=col, linestyle=linestyle))
            for type, linestyle in (("nuclei", "--"), ("other", "-.")):
                col = COLOR[type]
                obj[type] = TrackCollection(ax, col, alpha, zorder, linestyle)
                handles.append(Line2D([], [], color=col, linestyle=linestyle))
            ax._obj = obj

        labels = ["Long track", "VELO track"] + list(PID) + ["nuclei", "other"]
        self._fig.legend(
            handles,
            labels,
            loc=(0.15, 0.85),
            ncol=7,
            frameon=False,
            fontsize="small",
            handlelength=3,
        )

    def _process_event(self):
        self._update_vtx()
        self._update_trk()
        self._update_gen()

        title = [f"Event {self._spinbox.value()} / {self._tree.num_entries}"]

        try:
            n = self._get("vtx_len")
            title.append(f"$n_\\mathrm{{vtx}} = {n}$")
        except ValueError:
            warnings.warn("Branch vtx_len not found")

        try:
            n = self._get("vtrk_len")
            title.append(f"$n_\\mathrm{{VELO}} = {n}$")
        except ValueError:
            warnings.warn("Branch vtrk_len not found")

        try:
            n = self._get("trk_len")
            title.append(f"$n_\\mathrm{{Long}} = {n}$")
        except ValueError:
            warnings.warn("Branch trk_len not found")

        try:
            n = self._get("mc_trk_len")
            title.append(f"$n_\\mathrm{{gen}} = {n}$")
        except ValueError:
            warnings.warn("Branch mc_trk_len not found")

        try:
            n = self._get("mc_vtx_len")
            title.append(f"$n_\\mathrm{{pv,gen}} = {n}$")
        except ValueError:
            warnings.warn("Branch mc_vtx_len not found")

        self._canvas.figure.suptitle("    ".join(title), fontsize="medium")
        self._canvas.draw()

        self._run_debug()

    def _update_vtx(self):
        x, y, z = self._get("vtx_x", "vtx_y", "vtx_z")
        r = {"x": x, "y": y, "z": z}
        for (dim0, dim1), ax in self._ax.items():
            ax._obj["vtx"].update(r[dim0], r[dim1])

    def _update_trk(self):
        for trk, button in (
            ("trk", self._long_visible),
            ("vtrk", self._velo_visible),
        ):
            if button.isChecked():
                try:
                    x, y, z, px, py, pz = self._get(
                        f"{trk}_x",
                        f"{trk}_y",
                        f"{trk}_z",
                        f"{trk}_px",
                        f"{trk}_py",
                        f"{trk}_pz",
                    )
                except ValueError:
                    warnings.warn(f"Branches {trk}_[xyz] or {trk}_p[xyz] not found")
                    continue
            else:
                x, y, z, px, py, pz = np.empty((6, 0))

            r = {"x": x, "y": y, "z": z}
            p = {"x": px, "y": py, "z": pz}
            for (dim0, dim1), ax in self._ax.items():
                a0 = r[dim0]
                b0 = r[dim1]
                pa = p[dim0]
                pb = p[dim1]
                lim = self._lim[dim0]
                s = np.zeros_like(a0)
                with np.errstate(invalid="ignore", divide="ignore"):
                    s[pa > 0] = ((lim[1] - a0) / pa)[pa > 0]
                    s[pa < 0] = ((lim[0] - a0) / pa)[pa < 0]
                a1 = a0 + pa * s
                b1 = b0 + pb * s
                ax._obj[trk].update(a0, b0, a1, b1)

    def _update_gen(self):
        if not self._generator_visible.isChecked():
            for ax in self._ax.values():
                for pid in PID:
                    ax._obj[pid].update([], [], [], [])
                for type in ("nuclei", "other"):
                    ax._obj[type].update([], [], [], [])
            return
        try:
            x, y, z, px, py, pz, pid, imot = self._get(
                "mc_trk_x",
                "mc_trk_y",
                "mc_trk_z",
                "mc_trk_px",
                "mc_trk_py",
                "mc_trk_pz",
                "mc_trk_pid",
                "mc_trk_imot",
            )
        except ValueError:
            warnings.warn(
                "Some branches of mc_trk_[xyz], mc_trk_p[xyz], "
                "mc_trk_imot, mc_trk_pid not found"
            )
            return

        end_vertex_x = np.where(px > 0, np.inf, -np.inf)
        end_vertex_y = np.where(py > 0, np.inf, -np.inf)
        end_vertex_z = np.where(pz > 0, np.inf, -np.inf)
        daughters = {}
        for i, imoti in enumerate(imot):
            if imoti != -1:
                daughters[imoti] = i
        for imoti, i in daughters.items():
            end_vertex_x[imoti] = x[i]
            end_vertex_y[imoti] = y[i]
            end_vertex_z[imoti] = z[i]

        types = []
        m_all = False
        for type, pids in PID.items():
            m = False
            for pidi in pids:
                m |= np.abs(pid) == pidi
            m_all |= m
            r = {"x": x[m], "y": y[m], "z": z[m]}
            p = {"x": px[m], "y": py[m], "z": pz[m]}
            re = {"x": end_vertex_x[m], "y": end_vertex_y[m], "z": end_vertex_z[m]}
            types.append((type, r, p, re))
        m = np.fromiter((particle.PDGID(pidi).is_nucleus for pidi in pid), bool)
        m[m_all] = False  # protons and neutrons have been drawn already
        m_all |= m
        r = {"x": x[m], "y": y[m], "z": z[m]}
        p = {"x": px[m], "y": py[m], "z": pz[m]}
        re = {"x": end_vertex_x[m], "y": end_vertex_y[m], "z": end_vertex_z[m]}
        types.append(("nuclei", r, p, re))
        m = ~m_all
        r = {"x": x[m], "y": y[m], "z": z[m]}
        p = {"x": px[m], "y": py[m], "z": pz[m]}
        re = {"x": end_vertex_x[m], "y": end_vertex_y[m], "z": end_vertex_z[m]}
        types.append(("other", r, p, re))

        for (type, r, p, re) in types:
            for (dim0, dim1), ax in self._ax.items():
                lim = self._lim[dim0]
                a0 = r[dim0]
                b0 = r[dim1]
                pa = p[dim0]
                pb = p[dim1]
                ea = re[dim0]
                eb = re[dim1]
                s = np.zeros_like(a0)
                for limi, m in zip(lim, (pa < 0, pa > 0)):
                    s[m] = (limi - a0)[m] / pa[m]
                a1 = a0 + pa * s
                b1 = b0 + pb * s
                for m, fn in zip(((pa > 0), (pa < 0)), (np.minimum, np.maximum)):
                    a1[m] = fn(ea, a1)[m]
                for m, fn in zip(((pb > 0), (pb < 0)), (np.minimum, np.maximum)):
                    b1[m] = fn(eb, b1)[m]
                m = s != 0
                ax._obj[type].update(a0[m], b0[m], a1[m], b1[m])

    def _run_debug(self):
        if not self._debug:
            return

        try:
            pid, imot, px, py, pz = self._get(
                "mc_trk_pid", "mc_trk_imot", "mc_trk_px", "mc_trk_py", "mc_trk_pz"
            )
        except ValueError:
            warnings.warn(
                "Some branches of mc_trk_p[xyz], mc_trk_pid, mc_trk_imot not found"
            )
            return

        has_daughters = set()
        for i, imoti in enumerate(imot):
            if imoti != -1:
                has_daughters.add(imoti)

        no_daughters_but_short_lived = []
        zero_momentum = []
        for i, (pidi, xi, yi, zi) in enumerate(zip(pid, px, py, pz)):
            if xi == 0 or yi == 0 or zi == 0:
                name = pid_to_name(pidi)
                zero_momentum.append((i, name, xi, yi, zi))
            if i in has_daughters:
                continue
            if pidi in LONG_LIVED_PIDs:
                continue
            if particle.PDGID(pidi).is_nucleus:
                continue
            name = pid_to_name(pidi)
            no_daughters_but_short_lived.append((i, name))

        print(f"Debug log for event {self._spinbox.value()}")
        if no_daughters_but_short_lived:
            print("  Particles without daughters which are not long-lived")
            for i, name in no_daughters_but_short_lived:
                print(f"    {i} {name}")

        if zero_momentum:
            print("  Particles with zero momentum in x or y or z")
            for i, name, x, y, z in zero_momentum:
                print(f"    {i} {name} ({x}, {y}, {z})")

    def _backward(self):
        self._spinbox.setValue(self._spinbox.value() - 1)

    def _forward(self):
        self._spinbox.setValue(self._spinbox.value() + 1)

    def _jump(self, value):
        ievent = self._spinbox.value() - 1
        if ievent < self._range[0] or ievent >= self._range[1]:
            self._update_data()
        self._process_event()

    def keyPressEvent(self, event):
        key = event.key()
        Qt = QtCore.Qt
        if key in (Qt.Key_Q, Qt.Key_Escape):
            self.close()
            return
        if key == Qt.Key_Right:
            self._forward()
            return
        if key == Qt.Key_Left:
            self._backward()
            return
        if key == Qt.Key_H:
            self._navigation.home()
            return
        if key == Qt.Key_G:
            self._generator_visible.click()
            return
        if key == Qt.Key_L:
            self._long_visible.click()
            return
        if key == Qt.Key_V:
            self._velo_visible.click()
            return
        if key == Qt.Key_B:
            self._tree.show()
            return
        if key == Qt.Key_D:
            self._debug = not self._debug
            self._run_debug()
            return
