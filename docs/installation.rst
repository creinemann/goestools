.. _installation:

Installation
============

Building goestools requires Linux.

It can be built for x86 and ARM (with NEON).

.. note::

  Other operating systems may be fine as well but have not been
  confirmed to work. If you manage to get goestools to work on macOS,
  Windows, or something else, please reach out and share instructions,
  so they can be added to this page.

Dependencies
------------

System dependencies:

* CMake
* C++14 compiler
* OpenCV 3 or 4 (for image processing in goesproc)
* PROJ (optional, for map overlays)
* zlib (for decompressing EMWIN data)

Bundled dependencies (see vendor directory in repository):

* libcorrect (currently a fork with CMake related fixes)
* libaec
* nanomsg
* json
* tinytoml

Building
--------

These instructions work for Raspberry Pi OS / Raspbian, Debian and Ubuntu.

Install system dependencies:

.. code-block:: text

  sudo apt install -y \
    build-essential \
    cmake \
    git \
    pkg-config \
    libopencv-dev \
    libproj-dev \
    librtlsdr-dev \
    zlib1g-dev

``librtlsdr-dev`` is needed to run goesrecv with an RTL-SDR; add
``libairspy-dev`` for an Airspy. ``libproj-dev`` enables map overlays.
On old Raspbian releases (Buster and earlier) some packages may no
longer download; leave out any you don't need.

Now you can build and install goestools:

.. code-block:: text

  git clone --recursive https://github.com/creinemann/goestools
  cd goestools
  mkdir build
  cd build
  cmake .. -DCMAKE_INSTALL_PREFIX=/usr/local -DCMAKE_BUILD_TYPE=Release
  make -j2
  sudo make install

The goestools executables are now available in /usr/local/bin.

When upgrading, use the same ``CMAKE_INSTALL_PREFIX`` as your existing
install (``which goesrecv``: ``/usr/bin`` means ``/usr``). ``make
install`` installs the example configuration as
``share/goestools/goesproc-goesr.conf.example`` and never overwrites an
existing ``goesproc-goesr.conf``.
