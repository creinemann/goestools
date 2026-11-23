# goestools

Tools to work with signals and files from GOES satellites.

> **USRadioguy fork** ([usradioguy.com](https://usradioguy.com)) of
> [pietern/goestools](https://github.com/pietern/goestools).
> This is a significant update. Includes updates for GOES 18,19 and Himawari-9
> NOTE: I used AI- Claude to help streamline and check code.
> **See [USRADIOGUY.md](USRADIOGUY.md) for everything that's new**, and
> [the Pi upgrade guide](docs/guides/usradioguy_pi_upgrade.md).
> Builds on current systems (CMake 4, OpenCV 4, PROJ 9, Raspberry Pi
> Buster), fixes map overlays, adds **Himawari-9 false color**, night-side
> LUTs, and a safe `make install`.
> 
> **See [USRADIOGUY.md](USRADIOGUY.md) for everything that's new**, and
> [the Pi upgrade guide](docs/guides/usradioguy_pi_upgrade.md).

![GOES-19 and Himawari-9 false color from Horicon, WI](docs/images/usradioguy_before_after.jpg)

I started writing this to learn about things involved in the GOES
communication pipeline and in the process learn more about space
communication standards. Everything is written in C++ to strike a
balance between usability (no need for yet another hash table in C)
and performance. ~~Eventually it would be nice to run the entire RX
pipeline on a little ARM board.~~ The entire RX pipeline can run on a
Raspberry Pi 3.

## Requirements

System dependencies:

* CMake
* C++14 compiler
* OpenCV 2, 3 or 4 (for image processing in goesproc)
* PROJ (optional, for map overlays)
* zlib (for EMWIN decompression)

Bundled dependencies:

* libcorrect (currently a fork with CMake related fixes)
* libaec

## Build

Install the system dependencies (Raspberry Pi OS / Raspbian, Debian,
Ubuntu):

``` shell
sudo apt install -y git build-essential cmake pkg-config zlib1g-dev \
  libopencv-dev libproj-dev librtlsdr-dev
```

Add `libairspy-dev` if you use an Airspy. On old Raspbian releases
(Buster and earlier) some packages may no longer download; leave out
any you don't need.

Then build and install:

``` shell
git clone --recursive https://github.com/creinemann/goestools
cd goestools
mkdir -p build
cd build
cmake .. -DCMAKE_INSTALL_PREFIX=/usr/local -DCMAKE_BUILD_TYPE=Release
make -j2
sudo make install
```

* **Upgrading?** Use the same prefix as your existing install
  (`which goesrecv` → `/usr/bin` means `-DCMAKE_INSTALL_PREFIX=/usr`),
  otherwise you end up with two copies. `make install` never overwrites
  an existing `share/goestools/goesproc-goesr.conf`.
* Raspberry Pi receivers: see the
  [Pi upgrade guide](docs/guides/usradioguy_pi_upgrade.md).
* Use `make -j2` on a Pi 3 (more parallel jobs can run out of memory).

## Usage

### goesrecv

goesrecv demodulates and decodes the HRIT signal from an RTL-SDR or
Airspy and publishes the packet stream (and live signal statistics) on
the network. It runs on x86 and on ARM (Raspberry Pi; NEON is used
when available). See [etc/goesrecv.conf](etc/goesrecv.conf) for an
example configuration and `goesrecv --help` for options.

The HRIT downlink (1694.1 MHz) is broadcast by **GOES-19** (East,
75.2° W) and **GOES-18** (West, 137.0° W). GOES-18 also relays
**Himawari-9** imagery. Older GOES satellites no longer transmit.

### goeslrit

> If you're interested in post-processed data (images, text files)
> then you can ignore `goeslrit` and only use `goesproc`.

This tool can be used to turn a stream of packets into LRIT files.
LRIT files can then be used by goesproc (or other tools, such as to
generate usable images and text files, or for debugging purposes.

It can either read packets from files to process recorded data, or
subscribe to `goesrecv` process to work with live data.

To make it write LRIT files to disk, you have to specify the category
of files you are interested in. Run `goeslrit --help` for a list of
filtering options. To make it write **ALL** LRIT files it seems, run
`goeslrit` with the `--all` option.

#### Reading packets from files

The files must be specified in chronological order because they are
read in order. Packets for a single LRIT file can span multiple packet
files, so if they are not specified in chronological order some LRIT
files will be dropped. Specifying a file glob in bash expands to an
alphabetically sorted list of file names that match the pattern.

Example with files:

``` shell
$ goeslrit --images /path/to/packets/packets-2018-02-28T*
Reading: /path/to/packets/packets-2018-02-28T00:00:00Z.raw
Writing: OR_ABI-L2-CMIPM1-M3C02_G16_s20180582358300_e20180582358358_c20180582358429.lrit (4004087 bytes)
Writing: OR_ABI-L2-CMIPM2-M3C07_G16_s20180590000000_e20180590000071_c20180590000108.lrit (254551 bytes)
...
```

#### Reading packets from a publisher

If `goesrecv` is running somewhere on your network, `goeslrit` can be
configured to subscribe to its packet publisher to process live data.
This is done with the `--subscribe` argument and it can take any valid
nanomsg address. Often this will be a TCP address
(`tcp://<ip>:<port>`, also see [nn_tcp(7)][nn_tcp]), but if you happen
to run `goesrecv` on the same machine as `goeslrit` you can also use
the IPC transport mechanism (`ipc://path/to/socket`, also see
[nn_ipc(7)][nn_ipc]).

[nn_tcp]: http://nanomsg.org/v1.1.2/nn_tcp.html
[nn_ipc]: http://nanomsg.org/v1.1.2/nn_ipc.html

Example with publisher:

``` shell
$ goeslrit --images --subscribe tcp://1.2.3.4:5005
Writing: OR_ABI-L2-CMIPM1-M3C02_G16_s20180591958303_e20180591958360_c20180591958427.lrit (4004087 bytes)
Writing: OR_ABI-L2-CMIPM2-M3C07_G16_s20180592000003_e20180592000073_c20180592000110.lrit (254551 bytes)
...
```

### goesproc

```
Usage: goesproc [OPTIONS] [path...]
Process stream of packets (VCDUs) or list of LRIT files.

Options:
  -c, --config PATH          Path to configuration file
  -m, --mode [packet|lrit]   Process stream of VCDU packets
                             or pre-assembled LRIT files
      --help                 Show this help

If mode is set to packet, goesproc reads VCDU packets from the
specified path(s). To process real time data you can setup a pipe from
the decoder into goesproc (e.g. use /dev/stdin as path argument).
To process recorded data you can specify a list of files that contain
VCDU packets in chronological order.

If mode is set to lrit, goesproc finds all LRIT files in the specified
paths and processes them sequentially. You can specify a mix of files
and directories. Directory arguments expand into the files they
contain that match the glob '*.lrit*'. The complete list of LRIT files
is sorted according to their time stamp header prior to processing it.
```

An example goesproc configuration file can be found at
[./etc/goesproc.conf](etc/goesproc.conf).

For example, with the following configuration file:

``` toml
[[handler]]
type = "image"
origin = "goes19"
regions = [ "fd" ]
channels = [ "ch13" ]
directory = "./goes19/fd/ch13"
filename = "GOES19_{region:short}_{channel:short}_{time:%Y%m%dT%H%M%SZ}"
format = "jpg"
```

Subscribing to a running goesrecv on the same machine writes a full
disk image of ABI channel 13 every 10 minutes:

``` shell
$ goesproc --config example.conf -m packet --subscribe tcp://127.0.0.1:5004
Writing: ./goes19/fd/ch13/GOES19_FD_CH13_20261123T200020Z.jpg (took 0.912s)
Writing: ./goes19/fd/ch13/GOES19_FD_CH13_20261123T201020Z.jpg (took 0.905s)
...
```

A complete configuration for GOES-18, GOES-19 and Himawari-9 (false
color, enhanced IR, water vapor, EMWIN, NWS text) is installed as
`share/goestools/goesproc-goesr.conf.example`. The configs the
USRadioguy station runs are in
[share/usradioguy/examples](share/usradioguy/examples).

## Resources

Because HRIT is similar to LRIT at a higher baud rate, documentation for
LRIT is also relevant for HRIT. The documents below used to be hosted
by NOAA until ~2020. They're mirrored here for posterity (thanks @gojimmypi;
see https://github.com/pietern/goestools/pull/102).

* [LRIT Receiver Specification](./docs/files/3_LRIT_Receiver-specs.pdf)
* [LRIT Transmitter Specification](./docs/files/4_LRIT_Transmitter-specs.pdf)
* [LRIT Mission Specific Data](./docs/files/5_LRIT_Mission-data.pdf)

Also, these blog series:

* **https://usradioguy.com**: USRadioguy's goestools guides for GOES-18, GOES-19 and Himawari-9 reception on the Raspberry Pi, including setup, configuration, custom color LUTs and processing
* https://web.archive.org/web/20150426214432/http://www.acasper.org/2011/10/24/goes-satellite-decoding/
* http://www.teske.net.br/lucas/2016/10/goes-satellite-hunt-part-1-antenna-system/

### Reed-Solomon

From the LRIT receiver specs:

> The LRIT dissemination service is a Grade-2 service; therefore, the
> transmission of user data will be error controlled using
> Reed-Solomon coding as an outer code. The used Reed-Solomon code is
> (255,223) with an interleaving of I = 4.

Data must be transformed from Berlekamp's dual basis representation to
conventional representation before we can run the Reed-Solomon
algorithm provided by libcorrect.

Please refer to [CCSDS 101.0-B-6][CCSDS101.0-B-6] (Recommendation For
Space Data System Standards: Telemetry Channel Coding) to read more
about the Reed-Solomon specifics for this application, the dual basis
representation, and how to transform data between conventional
representation and dual basis representation.

[CCSDS101.0-B-6]: https://public.ccsds.org/Pubs/101x0b6s.pdf

## Acknowledgments

Thanks to [@lukasteske](https://twitter.com/lucasteske) for building
an open source demodulator and decoder (see [Open Satellite
Project][OSP]). I used his code to verify my antenna system and as
reference to cross check between the LRIT spec and his implementation.

[OSP]: https://github.com/opensatelliteproject
