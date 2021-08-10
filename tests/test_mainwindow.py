from sctviewer.mainwindow import MainWindow
from PyQt5 import QtWidgets
import pytest
from pathlib import Path

test_file = Path.home() / "Extern/Data/sct/00058786_00000001_5.sct.root"


@pytest.mark.skipif(not test_file.exists(), reason="data file missing")
def test_MainWindow(capsys):
    qapp = QtWidgets.QApplication.instance()
    if not qapp:
        qapp = QtWidgets.QApplication([])  # noqa
    mw = MainWindow(test_file)
    mw._debug = True
    for i in range(10):
        mw._forward()

    out, err = capsys.readouterr()
    assert "Debug log for event 1" in out
    assert "Debug log for event 10" in out
