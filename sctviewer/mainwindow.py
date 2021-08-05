import numpy as np
from matplotlib.backends.qt_compat import QtWidgets
from matplotlib.backends.backend_qt5agg import (
    FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
import uproot
import awkward  # noqa


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
        self.setCentralWidget(self._main)
        layout = QtWidgets.QVBoxLayout(self._main)

        fig = Figure(figsize=(12, 4.5))
        self._canvas = FigureCanvas(fig)
        layout.addWidget(self._canvas)
        self.addToolBar(NavigationToolbar(self._canvas, self))

        self._ax_xy = fig.add_axes([0.08, 0.1, 0.35, 0.82])
        self._ax_zx = fig.add_axes([0.52, 0.1, 0.45, 0.39])
        self._ax_zy = fig.add_axes(
            [0.52, 0.53, 0.45, 0.39], sharex=self._ax_zx, sharey=self._ax_xy
        )

        f = uproot.open(filename)
        self._tree = f["ana"]

        button_layout = QtWidgets.QHBoxLayout()

        b = QtWidgets.QPushButton("Backward")
        b.clicked.connect(self._backward)
        button_layout.addWidget(b)

        b = QtWidgets.QPushButton("Forward")
        b.clicked.connect(self._forward)
        button_layout.addWidget(b)

        layout.addLayout(button_layout)

        self._update_data()
        self._init_canvas()
        self._update_canvas()

    def _update_data(self):
        tree = self._tree
        ievent = self._ievent
        self._range = max(0, ievent - 50), min(ievent + 100, tree.num_entries)
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
        if self._xlim is None:
            d = self._data

            def r(d, s, delta):
                s = f"vtx_{s}", f"trk_{s}", f"vtrk_{s}"
                return (
                    min(np.min(d[si]) for si in s) - delta,
                    max(np.max(d[si]) for si in s) + delta,
                )

            self._xlim = r(d, "x", 1)
            self._ylim = r(d, "y", 1)
            self._zlim = r(d, "z", 10)

    def _get(self, *args):
        d = self._data
        i = self._ievent - self._range[0]
        return (d[arg][i] for arg in args)

    def _init_canvas(self):
        ax_xy = self._ax_xy
        ax_zx = self._ax_zx
        ax_zy = self._ax_zy

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
            ax._vtx = Line2D([], [], marker="o", ls="", color="r")
            ax._trk = LineCollection([], colors="r", alpha=alpha)
            ax._vtrk = LineCollection([], colors="b", alpha=alpha)
            ax._mc_trk = LineCollection([], colors="g", alpha=alpha)
            ax.add_artist(ax._vtx)
            ax.add_collection(ax._trk)
            ax.add_collection(ax._vtrk)
            ax.add_collection(ax._mc_trk)

    def _update_canvas(self):
        self._update_vtx()
        self._update_trk()

        n_vtx, n_velo, n_long = self._get("vtx_len", "vtrk_len", "trk_len")
        self._canvas.figure.suptitle(
            f"Event {self._ievent + 1} / {self._tree.num_entries}    "
            f"$n_\\mathrm{{vtx}} = {n_vtx}$    "
            f"$n_\\mathrm{{VELO}} = {n_velo}$    "
            f"$n_\\mathrm{{Long}} = {n_long}$"
        )

        self._canvas.draw()

    def _update_vtx(self):
        x, y, z = self._get("vtx_x", "vtx_y", "vtx_z")
        for ax, a, b in ((self._ax_xy, x, y), (self._ax_zx, z, x), (self._ax_zy, z, y)):
            ax._vtx.set_data(a, b)

    def _update_trk(self):
        for trk in ("trk", "vtrk", "mc_trk"):
            if trk == "mc_trk":
                continue
            x, y, z, px, py, pz = self._get(
                f"{trk}_x",
                f"{trk}_y",
                f"{trk}_z",
                f"{trk}_px",
                f"{trk}_py",
                f"{trk}_pz",
            )

            for ax, a, b, pa, pb, lim in (
                (self._ax_xy, x, y, px, py, self._xlim),
                (self._ax_zx, z, x, pz, px, self._zlim),
                (self._ax_zy, z, y, pz, py, self._zlim),
            ):
                r = (np.where(pa > 0, lim[1], lim[0]) - a) / pa
                a1 = a + pa * r
                b1 = b + pb * r

                getattr(ax, f"_{trk}").set_segments(
                    [[(ai, bi), (a1i, b1i)] for (ai, bi, a1i, b1i) in zip(a, b, a1, b1)]
                )

    def _forward(self):
        if self._ievent == self._tree.num_entries - 1:
            return
        self._ievent += 1
        if self._ievent >= self._range[1]:
            self._update_data()
        self._update_canvas()

    def _backward(self):
        if self._ievent == 0:
            return
        self._ievent -= 1
        if self._ievent < self._range[0]:
            self._update_data()
        self._update_canvas()
