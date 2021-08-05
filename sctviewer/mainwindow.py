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


class MainWindow(QtWidgets.QMainWindow):

    _ievent = 0
    _range = None
    _tree = None
    _canvas = None
    _data = None
    _xlim = None
    _ylim = None
    _Zlim = None

    def __init__(self, filename):
        super().__init__()
        self._main = QtWidgets.QWidget()
        self._main.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setCentralWidget(self._main)
        layout = QtWidgets.QVBoxLayout(self._main)

        fig = Figure(figsize=(12, 4.5))
        self._canvas = FigureCanvas(fig)
        layout.addWidget(self._canvas)
        self._navigation = NavigationToolbar(self._canvas, self)
        self.addToolBar(self._navigation)

        self._ax_xy = fig.add_axes([0.08, 0.1, 0.35, 0.82])
        self._ax_zx = fig.add_axes([0.52, 0.1, 0.45, 0.39])
        self._ax_zy = fig.add_axes(
            [0.52, 0.53, 0.45, 0.39], sharex=self._ax_zx, sharey=self._ax_xy
        )

        f = uproot.open(filename)
        self._tree = f["ana"]

        b = QtWidgets.QPushButton("Backward")
        f = QtWidgets.QPushButton("Forward")
        s = QtWidgets.QSpinBox()

        b.clicked.connect(self._backward)
        f.clicked.connect(self._forward)
        s.setRange(1, self._tree.num_entries)
        s.setSingleStep(10)
        s.valueChanged.connect(self._jump)
        self._spinbox = s

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
        ievent = self._ievent
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
                "mc_trk_[xyz]",
                "mc_trk_p[xyz]",
            ],
            entry_start=self._range[0],
            entry_stop=self._range[1],
        )

    def _get(self, *args):
        d = self._data
        i = self._ievent - self._range[0]
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

        alpha = 0.2
        for ax in (ax_xy, ax_zx, ax_zy):
            obj = {"vtx": Line2D([], [], marker="o", ls="", color="r")}
            for trk, col in (("trk", "r"), ("vtrk", "b"), ("mc_trk", "g")):
                obj[trk + "_pts"] = Line2D(
                    [], [], marker=".", ls="", color=col, mec="none", alpha=alpha
                )
                obj[trk] = LineCollection([], colors=col, alpha=alpha)
            ax.add_artist(obj["trk"])
            ax.add_artist(obj["trk_pts"])
            ax.add_artist(obj["vtrk_pts"])
            ax.add_artist(obj["mc_trk_pts"])
            ax.add_collection(obj["trk"])
            ax.add_collection(obj["vtrk"])
            ax.add_collection(obj["mc_trk"])
            ax._obj = obj

    def _update_canvas(self):
        self._update_vtx()
        self._update_trk()

        title = [f"Event {self._ievent + 1} / {self._tree.num_entries}"]

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

        self._canvas.figure.suptitle("    ".join(title))
        self._canvas.draw()

    def _update_vtx(self):
        x, y, z = self._get("vtx_x", "vtx_y", "vtx_z")
        for ax, a, b in ((self._ax_xy, x, y), (self._ax_zx, z, x), (self._ax_zy, z, y)):
            ax._obj["vtx"].set_data(a, b)

    def _update_trk(self):
        for trk in ("trk", "vtrk", "mc_trk"):
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

            for ax, a, b, pa, pb, lim in (
                (self._ax_xy, x, y, px, py, self._xlim),
                (self._ax_zx, z, x, pz, px, self._zlim),
                (self._ax_zy, z, y, pz, py, self._zlim),
            ):
                r = (np.where(pa > 0, lim[1], lim[0]) - a) / pa
                a1 = a + pa * r
                b1 = b + pb * r

                ax._obj[trk].set_segments(
                    [[(ai, bi), (a1i, b1i)] for (ai, bi, a1i, b1i) in zip(a, b, a1, b1)]
                )
                ax._obj[trk + "_pts"].set_data(a, b)

    def _backward(self):
        self._spinbox.setValue(self._ievent)

    def _forward(self):
        self._spinbox.setValue(self._ievent + 2)

    def _jump(self, value):
        self._ievent = value - 1
        if self._ievent < self._range[0] or self._ievent >= self._range[1]:
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
