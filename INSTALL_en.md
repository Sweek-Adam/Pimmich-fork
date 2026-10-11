# 🖼️ Installing Pimmich on a fresh Raspberry Pi

> [!NOTE]
> **This repository is a personal fork** of [Pimmich](https://github.com/gotenash/pimmich), the original project created by Gadgetaulab.
> It is for **purely personal use**: this guide is provided **as is**, with no warranty and no support.
> It describes what the scripts in this repository do at the time of writing.

This guide starts from a blank SD card and ends with a photo frame that starts on its own. It assumes you are comfortable with a terminal, but not that you know the project.

🇫🇷 Version française : [INSTALL.md](INSTALL.md)

---

## 📖 Table of Contents

- [🧰 Recommended hardware](#-recommended-hardware)
- [💾 Prepare the SD card](#-prepare-the-sd-card)
- [🔌 First boot and SSH connection](#-first-boot-and-ssh-connection)
- [🚀 Install Pimmich](#-install-pimmich)
- [🔑 First login](#-first-login)
- [🔧 Basic configuration](#-basic-configuration)
- [🧩 Options](#-options)
  - [SD card protection (log2ram, zram)](#sd-card-protection-log2ram-zram)
  - [HTTPS certificate](#https-certificate)
  - [Tailscale: remote guest link and warning-free HTTPS](#tailscale-remote-guest-link-and-warning-free-https)
  - [Google Drive, Dropbox, OneDrive (rclone)](#google-drive-dropbox-onedrive-rclone)
  - [Voice control (Picovoice)](#voice-control-picovoice)
  - [Spotify, AirPlay and Bluetooth](#spotify-airplay-and-bluetooth)
  - [TV: HDMI-CEC](#tv-hdmi-cec)
  - [Automatic orientation (accelerometer)](#automatic-orientation-accelerometer)
  - [Physical button (GPIO)](#physical-button-gpio)
- [🔄 Updates and backup](#-updates-and-backup)
- [🩺 Quick troubleshooting](#-quick-troubleshooting)
- [❓ Going further](#-going-further)

---

## 🧰 Recommended hardware

| Item | Advice |
|---|---|
| **Raspberry Pi** | Model **3B+, 4 or 5** (the ones recommended by the README). A Pi 4 or 5 copes better with videos, layouts and voice control. |
| **Power supply** | The official power supply, or one with the same rating: **Pi 5**: 5.1 V / 5 A (USB-C, 27 W); **Pi 4**: 5.1 V / 3 A (USB-C, 15 W); **Pi 3B+**: 5.1 V / 2.5 A (micro-USB). These are the values Pimmich shows in `System > Maintenance > Hardware`, which also reports an insufficient power supply. |
| **SD card** | **32 GB minimum**, class **A1 or A2**. Go bigger if you keep many photos and videos on the card (a USB drive or a NAS can also hold them). |
| **Screen** | An HDMI monitor or a TV. The Pi 4 and 5 have **micro-HDMI** ports: you need a micro-HDMI → HDMI cable or adapter. |
| **Network** | Wi-Fi or Ethernet, with Internet access during the installation. |
| *Option*: **I2C accelerometer** | MPU-6050, ADXL345 or LIS3DH (a few euros), so the screen rotates on its own when you turn the frame. See [Automatic orientation](#automatic-orientation-accelerometer). |
| *Option*: **USB microphone** | For voice control. See [Voice control](#voice-control-picovoice). |
| *Option*: **sound** | Sound goes out through HDMI (screen or TV speakers) or through the 3.5 mm jack (Pi 3B+ and Pi 4; the Pi 5 has none). |

---

## 💾 Prepare the SD card

1. On a computer, install **Raspberry Pi Imager** (<https://www.raspberrypi.com/software/>) and start it.
2. Choose your Raspberry Pi model, then the **Raspberry Pi OS (64-bit)** system: the **desktop** version based on **Debian 13 "Trixie"**, which is the version recommended by the README.
   > The *Lite* version (no desktop) is not the recommended one. The `System > Maintenance > Switch back to Raspberry Pi OS (desktop)` button also needs the desktop to work.
3. Choose the SD card.
4. Fill in the **customisation settings**. Depending on the Imager version, they appear in a wizard or behind an "Edit settings" button:
   - **Hostname**: for example `cadre`. The Pi will then be reachable as `cadre.local`, and this name will be included in the HTTPS certificate created during installation.
   - **Username and password**: your choice (see the box below). This password is the one for the Linux account (SSH and `sudo`), not the Pimmich interface password.
   - **Wi-Fi**: network name (SSID), password and country.
   - **Time zone and keyboard**. The time zone will be set again by `setup.sh` anyway (see [what setup.sh does](#3-what-setupsh-does)).
   - **SSH**: enable it, with a password or a public key.
5. Write the card, then insert it into the Raspberry Pi.

> [!IMPORTANT]
> **Username and folder: what the scripts expect**
> - **The username is up to you**: no script requires `pi`.
> - `setup.sh` finds your user with the `logname` command. Run it from **your normal session** (preferably over SSH), prefixed with `sudo`, but **not** from a root shell (`sudo su`, `sudo -i`) nor logged in directly as root: otherwise everything would be configured for root.
> - This user is given ownership of the data folders (`static`, `logs`, `cache`, `config`) and the targeted `sudo` rights (`/etc/sudoers.d/pimmich-auth`). Its home folder is also where `~/.bash_profile` and `~/.config/sway/config` are written, which start the frame at boot.
> - `setup.sh` enables automatic console login (through `raspi-config`). Install Pimmich with **the account created in Imager** (the first account on the system), so that the session opened automatically at boot is the one where the frame is configured.
> - **Folder**: clone the repository into **`~/pimmich`**. The scripts work from any folder, but the commands shown by the interface and by the FAQ assume `~/pimmich`. Above all, the full path of `start_pimmich.sh` is written into the Sway configuration at installation time: **do not move the folder afterwards**.

---

## 🔌 First boot and SSH connection

1. Connect the screen (and the network cable if you use one), then the power supply. The first boot takes a few minutes, because Raspberry Pi OS finishes its setup and may reboot once on its own. The desktop eventually appears.
2. From your computer, connect over SSH with the username and hostname chosen in Imager:
   ```bash
   ssh username@cadre.local
   ```
   If the name `cadre.local` cannot be found, use the Pi's IP address: your router's interface shows it, or run `hostname -I` in a terminal on the Pi.
3. **Update the system.** `setup.sh` only refreshes the package list (`apt update`): it does not upgrade the packages already installed.
   ```bash
   sudo apt update
   sudo apt full-upgrade -y
   sudo reboot
   ```
4. Reconnect over SSH once the Pi has rebooted.

---

## 🚀 Install Pimmich

### 1. Get the code

Clone the repository **without `sudo`**, so the files belong to your user:

```bash
cd ~
git clone https://github.com/Sweek-Adam/Pimmich-fork.git pimmich
cd pimmich
```

`git` is normally already present on Raspberry Pi OS. If it is missing, install it with `sudo apt install -y git`.

### 2. Run the installation script

First check that `logname` prints your username, since that is what `setup.sh` uses:

```bash
logname
```

Then start the installation:

```bash
chmod +x setup.sh
sudo ./setup.sh
```

- **No questions are asked**: the script takes no input and has no options. Its messages are in French.
- **Duration**: expect roughly **20 to 45 minutes**. This is an estimate: it mostly depends on the Pi model, the SD card and the Internet speed. The longest parts are installing the Python libraries and downloading the speech recognition models.
- **Internet is needed throughout the installation.** If the script stops on an error (network outage, for example), simply run `sudo ./setup.sh` again. It is designed to be run again: steps already done are detected and skipped.

> [!WARNING]
> **Write down the password shown at step 8/12.** A box headed "NOTEZ CES IDENTIFIANTS, ILS NE SERONT PLUS AFFICHÉS" ("write down these credentials, they will not be shown again") shows the user (`admin`) and a random 12-character password. **This is the only time the password is shown in clear.** If you lose it, see [First login](#-first-login) to generate a new one.

### 3. What setup.sh does

| Step | What happens |
|---|---|
| 1/12 | `apt update` (package list). |
| 2/12 | Installs system packages: `sway`, `xterm`, `python3`, `python3-venv`, `python3-pip`, `libjpeg-dev`, `libopenjp2-7-dev`, `libtiff-dev`, `libopenblas-dev`, `ffmpeg`, `git`, `cifs-utils`, `smbclient`, `network-manager`, `jq`, `mpv`, `gettext`, `portaudio19-dev` (or `libportaudio-dev` as a fallback), `unzip`, `libheif-dev`. Then enables the `fr_FR.UTF-8` locale, so dates can be displayed in French. |
| 3/12 | Installs `python3-rpi.gpio`. Disables Wi-Fi power saving (file `/etc/NetworkManager/conf.d/99-disable-wifi-powersave.conf`), which causes dropouts, then restarts NetworkManager. |
| 4/12 | Detects the time zone from the public IP address (`ip-api.com` service) and applies it with `timedatectl`, or sets UTC if detection fails. **This replaces the time zone chosen in Imager.** |
| 5/12 | Installs **nginx**, removes its default site and runs `utils/enable_https.sh`. That script creates a self-signed certificate valid for 10 years in `/etc/ssl/pimmich/`, for the hostname, `name.local` and the current IP addresses. It also writes the site `/etc/nginx/sites-available/pimmich`: HTTP (port 80) redirects to HTTPS (port 443), except the guest upload page, which also stays reachable over HTTP. Pimmich itself only listens locally (`127.0.0.1:5000`). |
| 6/12 | Creates the Python environment `venv/` in the project folder and installs `requirements.txt`, `qrcode` and `python-telegram-bot` into it. **On Pi 3 and later**, it adds `pillow-heif` (iPhone HEIC photos), the voice control libraries (Vosk, Porcupine…), Porcupine's French language model, the sound `static/sounds/ding.wav` and the French and English Vosk models (`models/` folder). On Pi 1, Pi 2 and Zero, this voice part is skipped. |
| 7/12 | Creates `logs/`, `cache/`, `static/photos/`, `static/prepared/`, `static/pending_uploads/` and `config/`, then gives them to your user. |
| 8/12 | If `/boot/firmware/credentials.json` does not exist yet, creates the **`admin`** administrator account with a random password (shown once). Also creates the rule `/etc/sudoers.d/pimmich-auth`, which allows without a password only: writing that file, `reboot`, `shutdown`, `nmcli`, `raspi-config`, `mount`, `umount` and `timedatectl`. |
| 9/12 | Sets boot to **console with automatic login** (`raspi-config nonint do_boot_behaviour B2`). The desktop is no longer shown. |
| 10/12 | Adds to `~/.bash_profile` the start of **Sway** on console `tty1`. |
| 11/12 | Adds to `~/.config/sway/config` the line `exec_always --no-startup-id <folder>/start_pimmich.sh`, plus rules that show videos (`mpv`) and the slideshow full screen. |
| 12/12 | Done: "Redémarrez pour lancer automatiquement Sway + Pimmich." ("Reboot to start Sway + Pimmich automatically.") |

> [!NOTE]
> There is **no systemd service** for Pimmich. At boot, the automatic login on `tty1` starts Sway, which starts `start_pimmich.sh`, which starts the application (`app.py`). `start_pimmich.sh` restarts the application if it stops and writes everything to `logs/pimmich.log`.

### 4. Reboot

```bash
sudo reboot
```

At boot, the console logs in on its own, then Sway and Pimmich start. During display hours (**7 am – 10 pm by default**), the frame shows the logo, "Aucune photo trouvée." ("No photo found."), the address `Configurez sur : http://<IP>` and a **QR code**. These screen messages are always in French. Outside display hours, the screen stays black, and that is normal.

---

## 🔑 First login

1. On a phone or computer connected to the same network, **scan the QR code**, or type the displayed address (`http://<IP>`) or `http://cadre.local`. nginx automatically redirects you to **`https://`**.
2. The certificate is **self-signed**: the browser shows a warning the first time. Accept it once on each device ("Advanced" then "Proceed", depending on the browser). For a warning-free address, see [Tailscale](#tailscale-remote-guest-link-and-warning-free-https).
3. Log in with the user **`admin`** and the password written down at step 8/12.

> [!NOTE]
> **About `/boot/firmware/credentials.json`.** This file is on the boot partition, the one you see when you plug the SD card into a computer; that is why the frame's screen mentions "credentials.json à la racine de la SD" ("at the root of the SD card"). It contains the username, but the password is only stored **as a hash** (`password_hash`), next to the session secret key. **So the password cannot be read back from it.**
> ```bash
> sudo cat /boot/firmware/credentials.json
> ```
> This command shows the whole file: do not share it, it contains the session secret key. To see only the username, use `jq` (installed by `setup.sh`):
> ```bash
> sudo jq -r .username /boot/firmware/credentials.json
> ```

**Password lost or not written down?** If another administrator account exists, it can reset your password in `System > Accounts`. Otherwise, regenerate the credentials file: a new password is shown once in the terminal. This is the command Pimmich itself suggests in its logs.

```bash
cd ~/pimmich
sudo venv/bin/python utils/create_initial_user.py --output /boot/firmware/credentials.json
```

The [FAQ](FAQ_en.md) offers another method: delete the file with `sudo rm /boot/firmware/credentials.json`, then run `sudo ./setup.sh` again.

4. **Change the password right away**: `System > Accounts`, "My account" card, "New password" and "Confirm password" fields, then "Change password".
5. **The interfaces.** After logging in, the **new interface** (`/app`) opens. Its menu has five sections (Home, Photos, Screen, Sharing, System); it is phone-friendly and offers a search and a guided tour. The **classic interface** (`/configure`) is still reachable through the "Classic interface" link at the bottom of the menu, and the choice is remembered in the browser. All settings are available in the new interface. The interface language follows the browser's (French, English, Spanish, German or Japanese).

---

## 🔧 Basic configuration

The **Home** page shows a "**Getting started**" checklist that tracks your progress: choose a photo source, import photos, set display hours, choose a mood, invite family, secure the connection (HTTPS, already done by `setup.sh`) and enable automatic backup. The "**Frame status**" card reports problems, with a link to the page to fix. In the new interface, settings are saved automatically, and the slideshow restarts on its own after a series of changes.

### 1. Add a source: `Photos > Sources`

- **Immich**: enter the server URL (for example `http://192.168.1.YY:2283`), the access token (see [Get your Immich API token](README_en.md#-get-your-immich-api-token)) and the technical name of the album. You can enable automatic updates and choose their interval.
- **Samba / Windows share**: enter the server, the share name, and if needed a path, a username and a password. The "Test the Samba connection" button checks access.
- **Google Drive, other clouds, iCloud shared albums, photos by e-mail**: follow each card's wizard. Google Drive and the other clouds are detailed [below](#google-drive-dropbox-onedrive-rclone).
- Finally, tick the source in "**Sources to display in the slideshow**". By default, only Immich is ticked.

### 2. Import: `Photos > Import`

- "Importing photos" card: the "Import from Immich", "Import from Samba", "Import from Google Drive" and "Import from USB drive" buttons start an import. For the USB drive, plug it into the Pi first. Progress is shown during the import, then while the photos are prepared to the screen size; the slideshow then restarts.
- "**Import from Smartphone**" opens the upload page from the phone's browser.
- "**Import a WhatsApp chat**" accepts the `.zip` exported from WhatsApp.
- Photos received through **Telegram** (`Sharing > Telegram`) are imported automatically.

### 3. Set display hours: `Screen > Display`

- "**Weekly Hours (Mon-Fri)**" and "**Weekend hours (Sat-Sun)**" cards: on and off times. By default, the frame displays from 7 am to 10 pm.
- "**Evening and night**" card: lower brightness in the evening and, outside display hours, screen off or night clock.
- The same page also sets the display duration, transitions and videos (sound, audio output, hardware decoding), as well as the TV (HDMI-CEC).

### 4. Everything else

- **`Screen > Clock & weather`**: time, date, weather (OpenWeatherMap key), tides, Google calendar and countdowns.
- **`Screen > Layouts`**: mosaic, wall, magazine… and how often they appear.
- **`Sharing > Guests`**: QR code and upload page for relatives on the same Wi-Fi (photos, messages, drawings, voice messages, reactions). Guest photos go through `Sharing > To review`.
- **`System > Network`**: Wi-Fi and wired interface.
- **`System > Accounts`**: accounts for family members.

---

## 🧩 Options

Each option below is optional and is set up once, over SSH on the Pi. The scripts live in `~/pimmich/utils/`.

### SD card protection (log2ram, zram)

```bash
sudo ~/pimmich/utils/enable_sd_protection.sh
sudo reboot
```

- Installs **log2ram** from its author's repository (adds the `packages.azlux.fr` source to apt). System logs (`/var/log`) and Pimmich logs (`~/pimmich/logs`) are then written to RAM (128 MB), and copied to the card once a day and at shutdown.
- Limits the size and retention of `journald` logs (40 MB, 2 weeks).

With the **`--zram`** option, the swap file on the card is also replaced by compressed swap in RAM. The script uses `rpi-swap` if present, otherwise `zram-tools`. Swap lines in `/etc/fstab` are commented out, with a backup in `/etc/fstab.bak`.

```bash
sudo ~/pimmich/utils/enable_sd_protection.sh --zram
sudo reboot
```

To check that protection is active: `System > Maintenance`, "SD card file system" card, "Wear protection" section.

### HTTPS certificate

`setup.sh` has already run `utils/enable_https.sh`: the interface uses HTTPS right after installation. If the frame's **hostname** or **IP address** changes, recreate the certificate so it covers the new address:

```bash
sudo ~/pimmich/utils/enable_https.sh --renew
```

Without `--renew`, the script keeps the existing certificate and only rewrites the nginx configuration. This is useful if **Frame status** shows the "Unencrypted connection" alert.

### Tailscale: remote guest link and warning-free HTTPS

Tailscale is **not** installed by `setup.sh`.

1. Install Tailscale by following <https://tailscale.com/download/linux>, then connect the frame to your account:
   ```bash
   sudo tailscale up
   ```
2. Run the preparation script once. There is no need to prefix it with `sudo`: it asks for the password itself when needed.
   ```bash
   ~/pimmich/utils/enable_remote_guests.sh
   ```
   It creates a local nginx entry (`127.0.0.1:8088`) that lets **only** the guest upload page through. It also allows Pimmich's account to control Tailscale (`tailscale set --operator`), so the interface can turn publishing on and off.
3. **Guest link from outside**: `Sharing > Guests`, "Away from home" card, then "Allow uploads from outside". The first time, Tailscale may ask you to allow Funnel ("Allow Funnel on Tailscale" button). Then use "Share the link"; "Change the link" makes the old one unusable. The admin interface and your photos are never published, and guest photos still go through "To review".
4. **Warning-free HTTPS administration**: `System > Maintenance`, "HTTPS without warnings (Tailscale)" card, then "Enable HTTPS access via Tailscale". The admin interface becomes reachable at an `https://…ts.net:8443` address, with a real certificate, **only from your devices connected to Tailscale**: it is never published on the Internet. If Tailscale asks, first allow HTTPS certificates on your account ("Allow on Tailscale" button).

### Google Drive, Dropbox, OneDrive (rclone)

`rclone` is **not** installed by `setup.sh`.

**Google Drive** offers two methods, chosen in `Photos > Sources`, Google Drive card, "Connection method" setting:

- **Google service account** (no rclone): create a service account in the Google Cloud console, with the Google Drive API enabled. Download its JSON key and paste it into the card. Then share your photo folders with the service account's e-mail address.
- **rclone**: install rclone on the Pi, for example with the Debian package (`sudo apt install rclone`) or following <https://rclone.org>. Then create a Google Drive "remote" **with your usual user, without `sudo`**, since Pimmich reads the rclone configuration of the account it runs under:
  ```bash
  rclone config
  ```
  On a frame without a browser, the rclone wizard offers to finish the authorisation from a computer. In the Google Drive card, then choose the remote, click "Show my Google Drive folders" and tick the folders to display.

**Other clouds** (Dropbox, OneDrive, pCloud…): "Other clouds" card, then "Add an account". On a computer with a browser, install rclone and run the command shown, for example `rclone authorize "dropbox"`. Then paste the text shown between braces into the card. Pimmich then creates the rclone account on the frame, which requires **rclone to be installed on the Pi as well**.

The **automatic backup to Google Drive** (`System > Maintenance`) also goes through an rclone connection.

### Voice control (Picovoice)

**Prerequisites**: a USB microphone and a Pi 3 or newer. On these models, `setup.sh` has already installed Vosk, Porcupine and the language models. A **Picovoice access key** (AccessKey) is required: the current code demands it in every case, even when the "Vosk" engine is selected in the interface.

1. Create a free account on the **Picovoice Console** and copy your AccessKey.
2. **Wake word**: the repository already ships `voice_models/cadre-magique_raspberry-pi.ppn` ("Cadre Magique", in French). To use your own, or for English, create a wake word in the console's *Porcupine* section and download it for the **Raspberry Pi** platform. Rename it to `cadre-magique_raspberry-pi.ppn` (French) or `magic-frame_raspberry-pi_en.ppn` (English), then copy it into `~/pimmich/voice_models/`, for example from your computer:
   ```bash
   scp magic-frame_raspberry-pi_en.ppn username@cadre.local:~/pimmich/voice_models/
   ```
   If the bundled file is rejected with your key (see the logs), generate your own as above.
   > The French file is part of the repository. An update from the interface (which runs `git reset --hard`) therefore resets it to the repository version: keep a copy of yours.
3. In `System > Voice control`, set:
   - the recognition language;
   - the Picovoice access key;
   - the microphone ("Audio input (microphone)");
   - test with "Diagnostic Audio", then "Start the diagnosis".

   Finally, turn on "Enable voice control".
4. The available commands are listed in the [README](README_en.md#️-voice-control). If something goes wrong, check `System > Logs`, where the `voice_control.py` logs appear.

### Spotify, AirPlay and Bluetooth

This script turns the frame into a **Spotify Connect** speaker (Premium account), an **AirPlay** receiver and a **Bluetooth** speaker. Run it once from the account that runs Pimmich, **without `sudo`**: it asks for the password itself to install packages.

```bash
~/pimmich/utils/enable_music_receivers.sh
```

The script:
- installs `librespot` (through the raspotify package, downloaded from `dtcooper.github.io`), `shairport-sync`, `playerctl`, `rfkill`, `python3-dbus` and `python3-gi`;
- configures Bluetooth as a speaker;
- creates and enables the user services `pimmich-spotify`, `pimmich-airplay`, `pimmich-airplay-meta`, `pimmich-bluetooth` and `pimmich-bt-mpris`;
- enables `loginctl enable-linger`, so these services start with the frame.

The frame then appears as "**Cadre photo**". The `Screen > Sound` page, "The frame as a speaker" card, shows the status of each service and lets you pair a Bluetooth phone ("Pair a phone" button, for 3 minutes). It also lets you connect Spotify to control it from the interface.

To check a service, for example: `systemctl --user status pimmich-spotify`.

### TV: HDMI-CEC

In `Screen > Display`, "Television" card, enable "**Control the TV via HDMI-CEC**": the TV switches on to the frame's input when it wakes up, and goes to standby with it. Also enable HDMI-CEC in the TV's settings (Anynet+, Bravia Sync, SimpLink…).

Pimmich uses the `cec-ctl` command (package `v4l-utils`) and the `/dev/cec0` device. If `command -v cec-ctl` returns nothing, install the package:

```bash
sudo apt install v4l-utils
```

### Automatic orientation (accelerometer)

1. Connect an I2C accelerometer (MPU-6050, ADXL345 or LIS3DH) to the Pi's **SDA, SCL, 3.3 V and GND** pins, and fix it to the back of the frame.
2. Enable I2C: `sudo raspi-config`, menu *Interface Options › I2C*.
3. In `Screen > Display`, "Screen" card, set "Frame orientation" to "Automatic (orientation sensor)". The "Screen resolution" card then shows the sensor status. Then record the positions: stand the frame in landscape and click "The frame is in landscape", then stand it in portrait and click "The frame is in portrait".

The I2C library (`smbus2`) is already installed through `requirements.txt`.

### Physical button (GPIO)

The slideshow code can handle a sleep button (GPIO 23 by default, wired to ground). But no page of the current interface lets you enable it, so this option is not covered by this guide.

---

## 🔄 Updates and backup

### Update from the interface (recommended)

`System > Maintenance`, "**Application update**" card: it shows the installed version and the available changes. Click "**Start the update**", then follow the progress page. The `update_script.sh` script:

1. backs up `config/`, then runs `git fetch` and `git reset --hard origin/main`: **any local change to the repository's files is lost**, but `config/` is restored;
2. updates the Python dependencies. If this fails, a warning is shown and the details are in `logs/update_pip.log`;
3. restarts Pimmich, without rebooting the Pi.

**Automatic rollback**: if the new version crashes 3 times in a row within 90 seconds of starting, `start_pimmich.sh` goes back to the previous version on its own. The new version is confirmed after about 2 minutes of normal operation. The "**Go back to the previous version**" button also lets you roll back by hand.

### Update over SSH (`git pull`)

```bash
cd ~/pimmich
git pull
sudo reboot
```

If `requirements.txt` has changed, also update the Python dependencies before rebooting, as `update_script.sh` does. `setup.sh` gives the `venv/` environment to your user: no `sudo` needed. (On an installation made before this fix, `venv/` may belong to root: take it back once with `sudo chown -R "$USER:$USER" venv`.)

```bash
venv/bin/pip install -r requirements.txt
```

Instead of `sudo reboot`, you can also use `System > Maintenance > Reboot Application Web`. Node.js is not needed: the new interface ships already built in `static/app/`.

### Full backup

`System > Maintenance`, "**Full backup**" card:

- "**Without photos**", then "**Download**": you get a `.zip` file containing the settings (`config/` folder), accounts, playlists, messages, drawings and voice messages, guestbook, captions, reactions, music and history. "Restore this file" applies it again, on this frame or on a new installation. **Keep this file safe**: `config/` contains your access keys and tokens (Immich, weather…).
- "**With photos, on a USB drive or NAS**": first add a storage device in the "Photo storage" card.
- "**Automatic backup to Google Drive**": settings only, without photos, through an rclone connection.

Two things are **not** in the backup: the `admin` password (`/boot/firmware/credentials.json`, outside the project folder) and the Spotify credentials (`~/.config/pimmich`). After restoring on a new installation, log in with that new installation's `admin` password.

---

## 🩺 Quick troubleshooting

### Where to find the logs

- **`System > Logs`**: the log named "Pimmich (Serveur Web & Supervisor)" is `logs/pimmich.log` and covers the web application, the slideshow and the start script. The voice control logs also appear if they exist. The page offers an "Errors only" filter and "Follow live".
- **`System > Maintenance`**, "Hardware" card: temperature, power supply (reports undervoltage) and SD card errors.
- **Over SSH**:
  ```bash
  tail -f ~/pimmich/logs/pimmich.log
  ```
  Other useful files: `~/pimmich/logs/update_pip.log` (dependencies during an update) and `/tmp/mpv_pimmich.log` (video player, cleared at reboot). With log2ram, `logs/` lives in RAM but stays at the same path.

### Restart Pimmich

Pimmich has no systemd service: Sway starts it through `start_pimmich.sh`, which restarts it if it stops.

- **From the interface**: `System > Maintenance`, "System control" card. "Reboot Application Web" restarts only the application; "Restart the system" reboots the Pi.
- **Over SSH**: the simplest is `sudo reboot`. You can also stop the application: `start_pimmich.sh` restarts it about 5 seconds later.
  ```bash
  pkill -f "python3 -u app.py"
  ```
- **nginx**: `sudo nginx -t` checks its configuration, and `sudo systemctl restart nginx` restarts it. While Pimmich restarts, nginx shows a waiting page instead of a 502 error.

### Black screen

- **Display hours**: outside the hours set in `Screen > Display` (7 am – 10 pm by default), the screen is off, or shows the night clock if you chose it. The Home page says "The frame is asleep" and offers "Turn the frame on".
- **Sway does not start** (you see a text console or a login prompt): check that automatic login uses the account that installed Pimmich (`sudo raspi-config`, menu *System Options*). Also check that the start lines are present:
  ```bash
  grep -n "exec sway" ~/.bash_profile
  grep -n "start_pimmich" ~/.config/sway/config
  ```
- **Resolution**: at startup, Pimmich forces the saved resolution (1920 × 1080 by default). If your screen does not support it, change it in `Screen > Display`, "Screen resolution" card ("Show the screen's resolutions", then "Apply").
- **Black or blue screen after a video**: untick "Activate hardware video decoding" in `Screen > Display`, "Videos" card.
- **Power supply**: if `System > Maintenance > Hardware` reports a weak power supply, replace it (see the [recommended hardware](#-recommended-hardware)).
- **The screen does not fully turn off at night**: see the [FAQ](FAQ_en.md) (HDMI-CEC or smart plug).

### No HDMI sound

- In `Screen > Display`, "Videos" card, check "Enable sound for videos", the "Sound output" (Automatic or HDMI) and the volume. Also check the screen's or TV's volume.
- If the screen or TV was off when the Pi booted, HDMI sound can disappear. Pimmich checks every 5 minutes and repairs it on its own as soon as the screen responds; otherwise, reboot the Pi with the screen on.
- For the jack output, choose "Jack 3.5mm (headphone)" (not available on Pi 5).

### Wi-Fi

- **`System > Network`**: the page shows the connection status, the network and the IP address. The "Wi-Fi Configuration" card (country, SSID, password) switches networks, which can cut the connection to the frame for a minute. The list of nearby networks is there too.
- Wi-Fi power saving, which causes dropouts, is already disabled by `setup.sh`.
- If an Ethernet cable is plugged in, it takes priority: temporarily disable the "Wired Interface (eth0)" to force Wi-Fi.
- If the frame's IP address changes, use `https://cadre.local` instead, and remember to [renew the certificate](#https-certificate).

### Other cases

- **"Too many login attempts"**: after several wrong passwords, login is blocked for a few minutes. Wait, then try again.
- **Wrong time**: fix the time zone, for example `sudo timedatectl set-timezone Europe/Paris`.
- **Back to the Raspberry Pi OS desktop**: `System > Maintenance > Switch back to Raspberry Pi OS (desktop)`. To return to photo frame mode afterwards, double-click the **"Revenir au cadre Pimmich"** ("Back to the Pimmich frame") shortcut on the desktop or in the applications menu: it asks for confirmation, then restarts the Pi in frame mode. Over SSH: `~/pimmich/utils/switch_to_pimmich.sh --yes`. While the desktop is shown, the admin interface stays reachable (without the slideshow): `System > Maintenance` shows the current mode and also offers "Switch back to Pimmich (photo frame)".

---

## ❓ Going further

- **FAQ**: [FAQ_en.md](FAQ_en.md) (in French: [FAQ.md](FAQ.md)), for Wi-Fi, display, videos, guests, Telegram, updates…
- **README**: [README_en.md](README_en.md), for features, voice commands and the Immich token.
