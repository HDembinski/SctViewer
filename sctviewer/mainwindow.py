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

    def update(self, x, y):
        self._pts.set_data(x, y)


class TrackCollection:
    def __init__(self, ax, color, alpha, zorder):
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

    def update(self, x0, y0, x1, y1):
        self._lines.set_segments(
            [[(x0i, y0i), (x1i, y1i)] for (x0i, y0i, x1i, y1i) in zip(x0, y0, x1, y1)]
        )
        self._pts.set_data(x0, y0)


class MainWindow(QtWidgets.QMainWindow):

    _range = None
    _tree = None
    _canvas = None
    _data = None
    _xlim = None
    _ylim = None
    _Zlim = None

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

        fig = Figure(figsize=(12, 4.5))
        self._ax_xy = fig.add_axes([0.08, 0.1, 0.35, 0.82])
        self._ax_zx = fig.add_axes([0.52, 0.1, 0.45, 0.39])
        self._ax_zy = fig.add_axes(
            [0.52, 0.53, 0.45, 0.39], sharex=self._ax_zx, sharey=self._ax_xy
        )

        self._canvas = FigureCanvas(fig)
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
                "mc_trk_len",
                "mc_trk_[xyz]",
                "mc_trk_p[xyz]",
            ],
            entry_start=self._range[0],
            entry_stop=self._range[1],
        )

    def _get(self, *args):
        d = self._data
        i = self._spinbox.value() - 1 - self._range[0]
        if len(args) == 1:
            return d[args[0]][i]
        return (d[arg][i] for arg in args)

    def _init_canvas(self):
        ax_xy = self._ax_xy
        ax_zx = self._ax_zx
        ax_zy = self._ax_zy

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
                    continue
            xmin = min(xmin)
            xmax = max(xmax)
            if sym:
                xmax = max(-xmin, xmax)
                return -xmax, xmax
            return xmin, xmax

        self._xlim = r(d, "x", 1, True)
        self._ylim = r(d, "y", 1, True)
        self._zlim = r(d, "z", 10, False)

        ax_xy.set_xlim(*self._xlim)
        ax_xy.set_ylim(*self._ylim)
        ax_zx.set_xlim(*self._zlim)
        ax_zx.set_ylim(*self._xlim)
        ax_zy.set_xlim(*self._zlim)
        ax_zy.set_ylim(*self._ylim)

        ax_xy.set_xlabel("x / mm")
        ax_xy.set_ylabel("y / mm")
        ax_zx.set_xlabel("z / mm")
        ax_zx.set_ylabel("x / mm")
        ax_zy.set_ylabel("y / mm")

        self._ax_zy.xaxis.set_visible(False)

        for ax in (ax_xy, ax_zx, ax_zy):
            obj = {"vtx": PointCollection(ax, "r", 4)}
            for trk, col, zorder in (
                ("trk", "r", 3),
                ("vtrk", "b", 2),
                ("mc_trk", "g", 1),
            ):
                alpha = 0.2
                obj[trk] = TrackCollection(ax, col, alpha, zorder)
            ax._obj = obj

    def _update_canvas(self):
        self._update_vtx()
        self._update_trk()

        title = [f"Event {self._spinbox.value()} / {self._tree.num_entries}"]

        try:
            n = self._get("vtx_len")
            title.append(f"$n_\\mathrm{{vtx}} = {n}$")
        except ValueError:
            pass

        try:
            n = self._get("vtrk_len")
            title.append(f"$n_\\mathrm{{VELO}} = {n}$")
        except ValueError:
            pass

        try:
            n = self._get("trk_len")
            title.append(f"$n_\\mathrm{{Long}} = {n}$")
        except ValueError:
            pass

        try:
            n = self._get("mc_trk_len")
            title.append(f"$n_\\mathrm{{gen}} = {n}$")
        except ValueError:
            pass

        self._canvas.figure.suptitle("    ".join(title))
        self._canvas.draw()

    def _update_vtx(self):
        x, y, z = self._get("vtx_x", "vtx_y", "vtx_z")
        for ax, a, b in ((self._ax_xy, x, y), (self._ax_zx, z, x), (self._ax_zy, z, y)):
            ax._obj["vtx"].update(a, b)

    def _update_trk(self):
        for trk, button in (
            ("trk", self._long_visible),
            ("vtrk", self._velo_visible),
            ("mc_trk", self._generator_visible),
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
                    continue
            else:
                x, y, z, px, py, pz = np.empty((6, 0))

            for ax, a, b, pa, pb, lim in (
                (self._ax_xy, x, y, px, py, self._xlim),
                (self._ax_zx, z, x, pz, px, self._zlim),
                (self._ax_zy, z, y, pz, py, self._zlim),
            ):
                pa = np.array(pa)
                a = np.array(a)
                r = np.zeros_like(a)
                with np.errstate(invalid="ignore", divide="ignore"):
                    r[pa > 0] = ((lim[1] - a) / pa)[pa > 0]
                    r[pa < 0] = ((lim[0] - a) / pa)[pa < 0]

                a1 = a + pa * r
                b1 = b + pb * r

                ax._obj[trk].update(a, b, a1, b1)

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
