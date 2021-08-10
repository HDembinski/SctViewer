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

PID = {
    "pi": 211,
    "K": 321,
    "p": 2212,
    "n": 2112,
    "e": 11,
    "mu": 13,
    "gamma": 22,
    "strange_neutral": (
        130,
        310,
        3122,
        3322,
    ),
    "strange_charged": (3312, 3334, 3112),
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
        self._lines = LineCollection([], colors=color, alpha=alpha, zorder=zorder)
        self._pts = Line2D(
            [],
            [],
            marker=".",
            ls="",
            color=color,
            mec="none",
            alpha=alpha,
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
            button.clicked.connect(self._update_canvas)

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
        self._update_canvas()

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
            for type, col, zorder in (
                ("trk", "k", 3),
                ("vtrk", "0.5", 2),
            ):
                alpha = 0.2
                neutral = type.endswith("neutral") or type in ("n", "gamma")
                obj[type] = TrackCollection(
                    ax, col, alpha, zorder, "--" if neutral else "-"
                )
            for i, type in enumerate(PID):
                alpha = 0.2
                col = f"C{i}"
                zorder = 1
                neutral = type.endswith("neutral") or type in ("n", "gamma")
                obj[type] = TrackCollection(
                    ax, col, alpha, zorder, "--" if neutral else "-"
                )
            ax._obj = obj

        handles = [Line2D([], [], color="k"), Line2D([], [], color="0.5")]
        labels = ["Long track", "VELO track"]

        for i, label in enumerate(PID):
            handles.append(Line2D([], [], color=f"C{i}"))
            labels.append(label)

        self._fig.legend(
            handles, labels, loc=(0.15, 0.85), ncol=6, frameon=False, fontsize="small"
        )

    def _update_canvas(self):
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
        for type, pid_or_pids in PID.items():
            if isinstance(pid_or_pids, int):
                m = np.abs(pid) == pid_or_pids
            else:
                m = True
                for pidi in pid_or_pids:
                    m |= np.abs(pid) == pidi
            r = {"x": x[m], "y": y[m], "z": z[m]}
            p = {"x": px[m], "y": py[m], "z": pz[m]}
            for (dim0, dim1), ax in self._ax.items():
                lim = self._lim[dim0]
                a0 = r[dim0]
                b0 = r[dim1]
                pa = p[dim0]
                pb = p[dim1]
                s = np.zeros_like(a0)
                with np.errstate(invalid="ignore", divide="ignore"):
                    s[pa > 0] = ((lim[1] - a0) / pa)[pa > 0]
                    s[pa < 0] = ((lim[0] - a0) / pa)[pa < 0]
                a1 = a0 + pa * s
                b1 = b0 + pb * s
                ax._obj[type].update(a0, b0, a1, b1)

    def _backward(self):
        self._spinbox.setValue(self._spinbox.value() - 1)

    def _forward(self):
        self._spinbox.setValue(self._spinbox.value() + 1)

    def _jump(self, value):
        ievent = self._spinbox.value() - 1
        if ievent < self._range[0] or ievent >= self._range[1]:
            self._update_data()
        self._update_canvas()

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
