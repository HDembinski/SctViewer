import numpy as np
from matplotlib.backends.qt_compat import QtWidgets
from matplotlib.backends.backend_qt5agg import (
    FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure
from matplotlib.ticker import NullFormatter
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

    def _setup_axes(self):
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

        self._ax_zy.xaxis.set_major_formatter(NullFormatter())

    def _local_index(self):
        return self._ievent - self._range[0]

    def _draw_vtx(self):
        ax_xy = self._ax_xy
        ax_zx = self._ax_zx
        ax_zy = self._ax_zy
        data = self._data
        i = self._local_index()
        col = "y"
        ax_xy.plot(data["vtx_x"][i], data["vtx_y"][i], "o", ms=10, color=col)
        ax_zx.plot(data["vtx_z"][i], data["vtx_x"][i], "o", ms=10, color=col)
        ax_zy.plot(data["vtx_z"][i], data["vtx_y"][i], "o", ms=10, color=col)

    def _draw_trk(self, is_long):
        alpha = 0.2

        data = self._data
        i = self._local_index()
        ax_xy = self._ax_xy
        ax_zx = self._ax_zx
        ax_zy = self._ax_zy

        trk = "trk" if is_long else "vtrk"
        x = data[f"{trk}_x"][i]
        y = data[f"{trk}_y"][i]
        z = data[f"{trk}_z"][i]
        px = data[f"{trk}_px"][i]
        py = data[f"{trk}_py"][i]
        pz = data[f"{trk}_pz"][i]

        col = "r" if is_long else "b"

        ax_xy.plot(x, y, "o", color=col)
        ax_zx.plot(z, x, "o", color=col)
        ax_zy.plot(z, y, "o", color=col)

        r = (np.where(px > 0, self._xlim[1], self._xlim[0]) - x) / px
        x1 = x + px * r
        y1 = y + py * r

        for x0i, x1i, y0i, y1i in zip(x, x1, y, y1):
            ax_xy.plot([x0i, x1i], [y0i, y1i], "-", color=col, alpha=alpha)

        r = (np.where(pz > 0, self._zlim[1], self._zlim[0]) - z) / pz

        z1 = z + pz * r
        x1 = x + px * r
        y1 = y + py * r

        for z0i, z1i, x0i, x1i, y0i, y1i in zip(z, z1, x, x1, y, y1):
            ax_zx.plot([z0i, z1i], [x0i, x1i], "-", color=col, alpha=alpha)
            ax_zy.plot([z0i, z1i], [y0i, y1i], "-", color=col, alpha=alpha)

    def _update_canvas(self):
        ax_xy = self._ax_xy
        ax_zx = self._ax_zx
        ax_zy = self._ax_zy
        for ax in (ax_xy, ax_zx, ax_zy):
            ax.cla()

        self._setup_axes()
        self._draw_vtx()
        self._draw_trk(True)
        self._draw_trk(False)

        data = self._data
        i = self._local_index()

        self._canvas.figure.suptitle(
            f"Event {self._ievent + 1} / {self._tree.num_entries} "
            f"$n_\\mathrm{{vtx}} = {data['vtx_len'][i]}$ "
            f"$n_\\mathrm{{VELO}} = {data['vtrk_len'][i]}$ "
            f"$n_\\mathrm{{Long}} = {data['trk_len'][i]}$"
        )

        self._canvas.draw()

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
