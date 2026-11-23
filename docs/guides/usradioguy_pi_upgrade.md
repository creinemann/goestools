# Upgrading a Raspberry Pi receiver to the USRadioguy goestools

This guide upgrades a working goestools receiver on a Raspberry Pi. It
was written for, and used on, two Raspbian 10 "Buster" Pis that start
goestools from `/etc/rc.local` inside `screen` sessions, and connect to
the PC with PuTTY. Systemd setups are covered at the end.

**Downtime:** the old version keeps receiving during the build (about
12 minutes on a Pi 4 class board). The switch-over in step 8 takes a
few seconds.

Throughout this guide:
* **Paste:** copy a block from here and **right-click** in PuTTY to paste it.
* **Ctrl-C** stops a running command.
* **Leave a screen session running:** press **Ctrl-A**, then **D**.
* **Before connecting:** in PuTTY, set *Connection → Seconds between
  keepalives* to `30`.

---

## 0. Copy your new config to the Pi (Command Prompt on the PC)
Skip this if you're keeping your current `goesproc-goesr.conf`.
```bat
cd %USERPROFILE%\Downloads
pscp my-new-goesproc-goesr.conf pi@PI-ADDRESS:/home/pi/FIXED_goesproc-goesr.conf
```
If `pscp` isn't found, try `"C:\Program Files\PuTTY\pscp.exe"`, or
copy the file with WinSCP.

## 1. Connect
Open PuTTY, connect to the Pi, and log in as `pi`.

## 2. Look around
```bash
cat /etc/os-release | head -2
cmake --version | head -1
df -h ~ | tail -1
which goesrecv goesproc
grep -A3 -i goes /etc/rc.local
ps aux | grep -E "goesrecv|goesproc" | grep -v grep
grep -E "^\s*source" ~/goesrecv.conf
```
Write down:
* **cmake version:** it must be **3.10 or newer**.
* **Free space:** you need about **1 GB**.
* **Install prefix:** `/usr/bin/goesrecv` means the prefix is `/usr`;
  `/usr/local/bin/goesrecv` means `/usr/local`.
* **The exact command lines** goesrecv and goesproc run with (from
  `ps`). You need them in step 8.
* **Radio source:** `rtlsdr` or `airspy`.

The rest of this guide assumes prefix `/usr` and a live config at
`/usr/share/goestools/goesproc-goesr.conf`. Adjust both if yours differ.

## 3. Back up
```bash
BK=~/goestools-backup-$(date +%F); mkdir -p $BK
cp /usr/bin/goes* $BK/
sudo cp /usr/share/goestools/goesproc-goesr.conf $BK/goesproc-goesr.conf.LIVE
cp ~/goesrecv.conf $BK/
sudo cp -r /usr/share/goestools $BK/share
ls -l $BK
```

## 4. Build tools
```bash
sudo apt install -y git build-essential cmake pkg-config zlib1g-dev libopencv-dev libproj-dev librtlsdr-dev
```
Add `libairspy-dev` only if your source is `airspy`.

**On Buster,** the old Raspbian download server no longer has every
package. For example, `libairspy-dev` gives "404 Not Found". If your
earlier goestools build already installed the tools above, they'll all
report "already the newest version" and you can carry on. Leave out
`apt update` and any package you don't need.

## 5. Download
```bash
cd ~
git clone --recursive https://github.com/creinemann/goestools goestools-usradioguy
cd goestools-usradioguy
git submodule status        # none of the lines should start with "-"
```

## 6. Build (in the background, safe from PuTTY disconnects)
```bash
cd ~/goestools-usradioguy
mkdir -p build && cd build
cmake .. -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_BUILD_TYPE=Release
nohup make -j2 > ~/build.log 2>&1 &
tail -f ~/build.log
```
* `Unable to find libairspy` is fine for RTL-SDR users.
* Ctrl-C only stops the `tail`; the build keeps going.

When the log reaches `[100%] Built target goesproc`, check:
```bash
ls -l src/goesrecv/goesrecv src/goesproc/goesproc
grep -i " error" ~/build.log | head
```

## 7. Install (the old version keeps receiving)
```bash
cd ~/goestools-usradioguy/build
sudo make install
sudo cp ~/FIXED_goesproc-goesr.conf /usr/share/goestools/goesproc-goesr.conf   # only if you did step 0
ls /usr/share/goestools/ /usr/share/goestools/usradioguy/
```
`make install` puts the example config next to yours as
`goesproc-goesr.conf.example`. It never replaces your
`goesproc-goesr.conf`.

## 8. Switch to the new programs
For receivers started from `rc.local` in `screen`, use the command
lines you noted in step 2:
```bash
screen -S goesproc -X quit
screen -S goesrecv -X quit
sleep 3
screen -dmS goesrecv /usr/bin/goesrecv -v -i 1 -c /home/pi/goesrecv.conf
sleep 5
screen -dmS goesproc /usr/bin/goesproc -c /usr/share/goestools/goesproc-goesr.conf -m packet --subscribe tcp://127.0.0.1:5004 --out /home/pi/goes
```
**Don't also start the systemd services** if your Pi uses `rc.local`.
Two copies of goesrecv fight over the SDR: the second one aborts with
`signal=ABRT`. If `goesrecv.service` and `goesproc.service` exist but are
`disabled`, you can make sure nothing ever starts them with
`sudo systemctl mask goesrecv goesproc`.

## 9. Check
```bash
sleep 5
ps aux | grep -E "goesrecv|goesproc" | grep -v grep   # one of each, owned by pi
goesproc --version
screen -ls
```
Then:
* Look at the signal with `screen -r goesrecv` (Ctrl-A, D to leave), or
  in your monitoring.
* Confirm new images arrive.

`rc.local` already starts `/usr/bin/goesrecv` and `/usr/bin/goesproc`, so
a reboot brings up the new version with nothing else to change.

---

## Rollback
```bash
screen -S goesproc -X quit; screen -S goesrecv -X quit; sleep 3
BK=~/goestools-backup-YYYY-MM-DD
sudo cp $BK/goes* /usr/bin/
sudo cp $BK/goesproc-goesr.conf.LIVE /usr/share/goestools/goesproc-goesr.conf
# then restart them with the same two screen -dmS lines as step 8
```

## Systemd instead of rc.local
If `systemctl is-enabled goesrecv` says `enabled`, your Pi uses systemd.
Replace step 8 with:
```bash
sudo systemctl restart goesrecv
sleep 5
sudo systemctl restart goesproc
systemctl status goesrecv goesproc --no-pager
```
