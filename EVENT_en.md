# Pimmich "event": the photo frame on a computer

For a wedding, a birthday or a party, Pimmich runs on a laptop (Mac or Windows). The slideshow is shown full screen
on the screen of your choice: the laptop itself, a TV or a projector. Guests scan the QR code on screen and send their
photos from their phone. Each photo appears right away, full screen with the guest's name, then on the "Party wall".
Family games (Games menu) work too.

## Installation (once)

Get Pimmich (**Code > Download ZIP** on GitHub, or `git clone`), then, from its folder:

- **Mac**: install [Homebrew](https://brew.sh), then run `bash desktop/install_mac.sh` in the Terminal.
  The script installs Python, ffmpeg and mpv, then Pimmich's libraries.
- **Windows 10 / 11**: in PowerShell, run `powershell -ExecutionPolicy Bypass -File desktop\install_windows.ps1`.
  The script installs Python, ffmpeg and mpv with `winget`, then Pimmich's libraries.
  The Windows edition hasn't been tried for real yet: please report any issue.

## Launching

Double-click **"Pimmich événement.command"** (Mac) or **"Pimmich evenement.bat"** (Windows). A window offers the
following settings:

| Setting | Purpose |
|---|---|
| Party name, duration | Turns on party mode: large QR code, guests' photos shown right away, Party wall |
| Slideshow screen | The laptop, or the connected screen / projector; full screen or in a window |
| Dropped photos | Folder where guests' photos arrive (external drive, synced folder...) |
| Prepared photos | Folder for the display-ready versions (can differ from the dropped photos) |
| Port | Address given to guests: `http://<computer address>:8080` |
| Admin password | First launch only (`admin` account) |

Click **Launch**. The browser opens the admin interface, and the slideshow starts on the chosen screen. Closing the
window stops everything. From the command line: `python pimmich_event.py --no-gui --name "Wedding" --display 1`
(see `--help`, and `--list-displays` for the list of screens).

Keyboard, on the slideshow:
- **→**: next photo;
- **←**: previous photo;
- **space**: pause;
- **Esc**: minimise the window.

## The network on the day

Guests' phones and the computer must be on the **same Wi-Fi network**.
- Hotel or venue Wi-Fi networks often isolate devices from each other: guests then can't reach the computer. In that
  case, use a small travel router, or a phone's hotspot.
- On first launch, macOS or Windows ask to allow Python to receive connections: accept. On Windows, choose
  "private networks".

## After the party

The photos are in the "Dropped photos" folder, in the `fete_YYYYMMDD` subfolder. Copy it wherever you like: it is the
party album. The admin interface can also back everything up (`System > Maintenance`).

## What doesn't apply on a computer

Raspberry Pi features are hidden: Wi-Fi and fallback hotspot, physical button, rotation sensor, drives to mount,
screen sleep, voice control, automatic system updates.
