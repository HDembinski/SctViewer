def main():
    import sys
    from PyQt5 import QtWidgets
    from .mainwindow import MainWindow
    import signal

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Check whether there is already a running QApplication (e.g., if running
    # from an IDE).
    qapp = QtWidgets.QApplication.instance()
    if not qapp:
        qapp = QtWidgets.QApplication(sys.argv)

    if len(qapp.arguments()) != 2:
        raise SystemExit("You need to provide a filename.")

    app = MainWindow(qapp.arguments()[1])
    app.show()
    app.activateWindow()
    app.raise_()
    qapp.exec_()


if __name__ == "__main__":
    main()
