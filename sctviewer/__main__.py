def main():
    import sys
    from PyQt5 import QtWidgets
    import signal

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Check whether there is already a running QApplication (e.g., if running
    # from an IDE).
    qapp = QtWidgets.QApplication.instance()
    if not qapp:
        qapp = QtWidgets.QApplication(sys.argv)

    if len(qapp.arguments()) != 2:
        raise SystemExit("You need to provide a filename.")

    # importing this takes a long time so we only do it after checking arguments
    from .mainwindow import MainWindow

    app = MainWindow(qapp.arguments()[1])
    app.show()
    app.activateWindow()
    app.raise_()
    qapp.exec_()


main()
