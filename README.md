# SctViewer

Viewers for the SCT event format developed by MPIK and TUDO for minimum bias studies.

## Installation

It is recommended to install the app with `pipx`, which automatically generates an isolated environment for the dependencies of the application.
If you don't want to install `pipx`, you can also just use `pip`. Since the app is not general purpose, I don't plan to upload it to PyPI. Therefore you should install directly from GitHub.

```sh
pipx install git+https://github.com/HDembinski/SctViewer.git
```

## Usage

Run the viewer on an SCT file.

```sh
sctviewer /path/to/my/file.sct
```

Supported Keyboard commands:
- Q, ESC: Quit
- Right: Increment event number
- Left: Decrement event number
- H: Restore original zoom setting
- V: Toggle VELO track visibility
- L: Toggle Long track visibility
- G: Toggle Generator track visibility
- D: Toggle generation of debug log in the terminal
