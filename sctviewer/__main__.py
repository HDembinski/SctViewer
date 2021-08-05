def main():
    import sys
    from PyQt5 import QtWidgets
    from .mainwindow import MainWindow

    # Check whether there is already a running QApplication (e.g., if running
    # from an IDE).
    qapp = QtWidgets.QApplication.instance()
    if not qapp:
        qapp = QtWidgets.QApplication(sys.argv)

    app = MainWindow()
    app.show()
    app.activateWindow()
    app.raise_()
    qapp.exec_()


if __name__ == "__main__":
    main()
