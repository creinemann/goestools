.. _goesproc:

goesproc
--------

Process stream of packets (VCDUs) or list of LRIT files.

Options
=======

================================   ==========================================
``-c``, ``--config=PATH``          Path to configuration file
``-m``, ``--mode [packet|lrit]``   Process stream of VCDU packets
                                   or pre-assembled LRIT files
``--subscribe ADDR``               Address of nanomsg publisher
``-f``, ``--force``                Overwrite existing output files
================================   ==========================================

If mode is set to ``packet``, goesproc reads VCDU packets from the
specified path(s). To process real time data you can either setup a pipe
from the decoder into goesproc (e.g. use /dev/stdin as path argument),
or use ``--subscribe`` to consume packets directly from :ref:`goesrecv`.
To process recorded data you can specify a list of files that contain
VCDU packets in chronological order.

If mode is set to ``lrit``, goesproc finds all LRIT files in the specified
paths and processes them sequentially. You can specify a mix of files
and directories. Directory arguments expand into the files they
contain that match the glob ``*.lrit*``. The complete list of LRIT files
is sorted according to their time stamp header prior to processing it.

Configuration
=============

The configuration file uses TOML_ syntax. You can
find an example configuration (that includes stanzas for every
available handler) in ``./etc/goesproc.conf``.

.. _TOML:
   https://github.com/toml-lang/toml

Handlers
========

Different products use different handlers with different configuration
options. For example, there is an NWS image handler, NWS text handler,
EMWIN handler, GOES N-series handler, GOES R-series handler, Himawari
handler, etc.

**TODO** -- describe configuration options for every handler

Example
=======

For example, with the following configuration file:

.. code-block:: toml

   [[handler]]
   type = "image"
   origin = "goes19"
   regions = [ "fd" ]
   channels = [ "ch13" ]
   directory = "./goes19/fd/ch13"
   filename = "GOES19_{region:short}_{channel:short}_{time:%Y%m%dT%H%M%SZ}"
   format = "jpg"

Subscribing to a running goesrecv on the same machine results in a full
disk image of ABI channel 13 (clean longwave infrared) every 10 minutes:

.. code-block:: shell

   $ goesproc --config example.conf -m packet --subscribe tcp://127.0.0.1:5004
   Writing: ./goes19/fd/ch13/GOES19_FD_CH13_20261123T200020Z.jpg (took 0.912s)
   Writing: ./goes19/fd/ch13/GOES19_FD_CH13_20261123T201020Z.jpg (took 0.905s)
   ...

You can now use these image files however you like. For example, to
produce a GIF from a few consecutive full disk images, you can use the
following ImageMagick_ commands:

.. _ImageMagick: https://www.imagemagick.org/

.. code-block:: shell

   $ mogrify -resize '640x640>' *.jpg
   $ convert -loop 0 -delay 50 *.jpg GOES19_FD_CH13.gif

Sample configuration
====================

.. literalinclude:: ../../etc/goesproc.conf
  :language: toml

.. toctree::
   :maxdepth: 1
