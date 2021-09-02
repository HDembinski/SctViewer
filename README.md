# SctViewer

Viewers for the SCT event format developed by MPIK and TUDO for minimum bias studies.

Supported: Windows, OSX, Linux

## Installation

It is recommended to install the app with `pipx`, which automatically generates an isolated environment for the dependencies of the application.
If you don't want to install `pipx`, you can also just use `pip`. Since the app is not general purpose, I don't plan to upload it to PyPI. Therefore you should install directly from GitHub.

```sh
pipx install git+https://github.com/HDembinski/SctViewer.git
```

This requires that you have `git` installed. Please install `git` following the usual steps for your platform.

### Installation on Windows

Installation on Windows is a bit more complicated.

- Type `python` in the Windows command prompt. If Python is not installed, it will direct you to the Microsoft store to download it.
- Type `git` in the Windows Command Prompt to see if it is installed. If it is not installed, [you need to install it](https://git-scm.com/downloads)
- Go back to the command prompt and run
```sh
python -m pip install --upgrade pip
python -m pip install git+https://github.com/HDembinski/SctViewer.git
```

## Usage

Run the viewer on an SCT file.

```sh
sctviewer /path/to/my/file.sct
```
if `sctviewer` is in your PATH, otherwise
```sh
python -m sctviewer /path/to/my/file.sct
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

## Developer info

Similar project https://twiki.cern.ch/twiki/bin/view/LHCb/LHCbEventDisplay

- JavaScript and WebGL
- Requires conversion of LHCb format to JSON format
- https://gitlab.cern.ch/bcouturi/gltfexporter
- https://github.com/andrewpap22/root_cern-To_gltf-Exporter
- https://gitlab.cern.ch/lhcb/geometryvalidation/-/tree/master/gdml_export
