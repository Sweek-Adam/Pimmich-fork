# 🖼️ Pimmich – Smart Connected Photo Frame

[![Tests](https://github.com/Sweek-Adam/Pimmich-fork/actions/workflows/tests.yml/badge.svg)](https://github.com/Sweek-Adam/Pimmich-fork/actions/workflows/tests.yml)

Pimmich is a Python application designed to turn a Raspberry Pi into a smart and customizable digital photo frame. It can display photos from multiple sources, be controlled by voice, and much more.

> [!NOTE]
> **This repository is a personal fork** of [Pimmich](https://github.com/gotenash/pimmich), the original project created by Gadgetaulab.
> I took it over for my own photo frame and added **lots of features** (see the list below).
> It is for **purely personal use**: the fork lives its own life, is no longer merged with the original repository
> and is not maintained for other setups. For the official version, head over to the original repository 🙂

<img src="static/pimmich_logo.png" alt="Pimmich Logo" width="300">

---

## 📖 Table of Contents

- [🍴 What this fork adds](#-what-this-fork-adds)
- [✨ Main Features](#-main-features)
- [🧰 Technologies Used](#-technologies-used)
- [🚀 Installation](#-installation)
- [🔧 Configuration](#-configuration)
- [🗣️ Voice Control](#️-voice-control)
- [❓ Troubleshooting (FAQ)](#-troubleshooting-faq)
- [🔑 Get your Immich API token](#-get-your-immich-api-token)
- [🕰️ Original project history](#️-original-project-history)
- [📜 Licenses](#-licenses)
- [💖 Credits](#-credits)

---

## 🍴 What this fork adds

On top of everything the original Pimmich offers, this fork adds in particular:

#### 🖥️ New admin interface
- Fully rebuilt interface (Vue 3), phone-friendly, **dark mode**, search, shortcuts to every section, guided tour.
- Settings history with undo, drag and drop on the home page, statistics, searchable library (date, source, person).
- Per-family-member accounts (own uploads and playlists), multi-frame administration.

#### 📸 Photos & sources
- Google Drive, Dropbox, OneDrive (rclone), iCloud shared albums, WhatsApp import, direct sharing from Android.
- Automatic filtering (blurry, dark, duplicate photos, screenshots), people recognised via Immich, face-aware cropping.
- Smart albums, "On this day", automatic place captions, Snapchat-style captions on photos and videos.
- Several storage locations (USB disk, NAS) and automatic screen rotation.
- **World travel map**: photos grouped by place and period, trip stories shown on the frame.

#### 🖼️ Display
- Layouts (mosaic, wall, magazine…) prepared ahead of time, family layouts (birthdays with name and age, holidays…).
- **Videos only** mode, chaining without a loading screen.
- Fully customisable clock (font, size, colours, background), animated weather, sun and moon, quote of the day.
- Family calendar (Google Calendar), countdowns, adjustable display frequencies, evening dimming and night clock.
- New transitions, synced to the music beat, and seasonal moods (Halloween, Christmas, Easter…).

#### 💌 Messages & guests
- Scheduled or recurring messages, **drawings** with stickers, **voice messages**, reactions and a **guestbook**.
- Guest link reachable from outside (Tailscale) and automatically approved trusted guests.

#### 🎵 Music
- Spotify (player, jukebox with big cover, **karaoke** with synced lyrics), internet radios and podcasts.
- Bluetooth, AirPlay, sleep timer, music by time of day, volume lowered during videos and voice messages.

#### 🏠 Smart home & reliability
- Home Assistant (MQTT), HDMI-CEC, Wi-Fi presence detection, notifications (ntfy).
- One-click update with rollback, watchdog that restarts a frozen slideshow, log rotation.
- SD card protection (log2ram, zram), full restorable backup, HTTPS access via Tailscale.
- Automated tests and continuous integration.

---

## ✨ Main Features

Pimmich is packed with features to provide a complete and customizable experience:

#### 🖼️ **Display & Slideshow**
- **Multi-source:** Display photos from Immich, a network share (Samba/Windows), a USB drive, a smartphone, or via Telegram.
- **Advanced Customization:** Set display duration, active hours, transitions (fade, slide), and enable a "Pan & Zoom" motion effect.
- **Creative Filters:** Apply filters to your photos (Black & White, Sepia, Vintage) and unique effects like **Polaroid** or **Postcard**.
- **Format Handling:** Smart support for portrait photos (blurred background) and videos (with sound and optional hardware acceleration).

#### ⚙️ **Interface & Control**
- **Comprehensive Web Interface:** A local, password-protected admin interface with a menu by section (Home, Photos, Screen, Sharing, System), also usable on a phone.
- **Voice Control:** Control your frame with voice commands like *"Magic Frame, next photo"* or *"Magic Frame, play Vacation playlist"*.
- **Content Management:**
    - **Playlists:** Create virtual albums, reorder photos with drag-and-drop, and launch themed slideshows with a dynamic title screen (photo jumble on a corkboard background).
    - **Favorites:** Mark your favorite photos to make them appear more often.
    - **Captions:** Add custom text to your photos and postcards.

#### 🌐 **Connectivity & Interactions**
- **Telegram:** Allow friends and family to send photos to the frame via a Telegram bot, with a secure and temporary invitation system.
- **Wi-Fi & Network:** Configure Wi-Fi, scan for networks, and manage network interfaces directly from the interface.
- **Smartphone Upload:** Import photos directly from your phone's browser.

#### 🛠️ **Maintenance & Monitoring**
- **Easy Updates:** Update Pimmich with a single click from the interface.
- **Backup & Restore:** Back up and restore your entire configuration.
- **System Monitoring:** Track real-time temperature, CPU, RAM, and disk usage with history graphs.
- **Detailed Logs:** Access logs for each service (web server, slideshow, voice control) for easy troubleshooting.

---

## 🧰 Technologies Used

- **Backend:** Python, Flask
- **Admin interface:** Vue 3, Vite, TypeScript (built into `static/app/`: the Raspberry Pi does not need Node); the classic interface (Jinja, TailwindCSS) is still available
- **Slideshow:** Pygame (pygame-ce)
- **Videos, music and voice messages:** mpv, PipeWire
- **Image Processing:** Pillow, NumPy, OpenCV (YuNet face detection)
- **Cloud sync:** rclone (Google Drive, Dropbox, OneDrive)
- **Remote access:** Tailscale (guest link, HTTPS)
- **Voice Control:** Picovoice Porcupine (wake word) & Vosk (recognition)
- **Web Server:** NGINX (as a reverse proxy, HTTPS)
- **Tests:** pytest, Playwright, GitHub Actions continuous integration

---

## 🚀 Installation

### Installation from the Git Repository

#### ✅ Prerequisites

- A Raspberry Pi (model 3B+, 4, or 5 recommended) with **Raspberry Pi OS Trixie (Debian 13)** Desktop (64-bit) — **recommended version**.
- An SD card, a power supply, a screen.
- An Internet connection.

#### 📝 Installation Steps

1.  **Clone the repository**
    Open a terminal on your Raspberry Pi and run:
    ```bash
    git clone https://github.com/Sweek-Adam/Pimmich-fork.git pimmich
    cd pimmich
    ```

2.  **Run the installation script**
    This script installs all system and Python dependencies, configures the environment, and sets up automatic startup.
    ```bash
    chmod +x setup.sh
    sudo ./setup.sh
    ```

3.  **Reboot**
    Once the script is done, reboot so that all services start properly.
    ```bash
    sudo reboot
    ```

---

## 🔧 Configuration

### 1. First Login

- After rebooting, the frame shows a QR code and the Raspberry Pi's IP address.
- Scan the QR code or open a browser on another device on the same network and type the IP address (e.g. `http://192.168.1.XX`): you are redirected to `https://`. The certificate is self-signed, so the browser shows a warning the first time (for an address without a warning, see `System > Maintenance > HTTPS without warnings (Tailscale)`).
- The initial password is randomly generated during installation and stored in `/boot/firmware/credentials.json`. It is strongly recommended to change it in the interface (`System > Accounts`).
- After logging in, the new interface opens (`/app`). The classic one is still reachable from the menu ("Classic interface") and the choice is remembered.

### 2. Sources

Everything happens in `Photos > Sources`:
- **Immich:** you need your **server URL** (e.g. `http://192.168.1.YY:2283`), an **API token** (see [Get your Immich API token](#-get-your-immich-api-token)) and the **album name**.
- **Google Drive, Dropbox, OneDrive, iCloud:** follow each card's wizard.
- **Samba / Windows share:** fill in your network share details.
- **USB, smartphone, WhatsApp:** use `Photos > Import`.

### 3. Customization

Explore the menu sections to customize your frame:
- **Screen > Display:** durations, active hours, transitions, effects, videos-only mode...
- **Screen > Clock & weather:** clock, date, weather, tides, calendar and countdowns.
- **Screen > Layouts:** layouts (mosaic, wall, magazine...) and how often they appear.
- **Photos > Sources:** tick the sources you want in the slideshow.
- **Sharing > Guests:** open the guest page (photos, messages, drawings, voice messages, guestbook).

---

## 🗣️ Voice Control

Pimmich supports voice control in **French** and **English**.

To use a custom wake word ("Magic Frame"...), a manual step is required:
1.  Create a free account on the Picovoice Console.
2.  In the "Porcupine" section, create your custom wake word.
3.  Download the model for the **Raspberry Pi** platform.
4.  Rename the downloaded `.ppn` file (e.g. `magic-frame_raspberry-pi_en.ppn`).
5.  Put this file in the `voice_models` folder at the root of the Pimmich project.
6.  In Pimmich, go to `System > Voice control`, choose the language, enter your Picovoice "Access Key" and enable the service.

### Available Commands

Start every command with the wake word, then say for example:
- *"next photo"*, *"previous photo"*, *"pause"*, *"play"*
- *"duration 15 seconds"*
- *"play Vacation"* (starts a playlist), *"show postcards"*
- *"enable source USB"*, *"disable source Samba"*
- *"sleep mode"*, *"wake up the frame"*, *"shut down the frame"*, *"return to main slideshow"*

---

## ❓ Troubleshooting (FAQ)

For questions or problems, see the **Frequently Asked Questions ([FAQ_en.md](FAQ_en.md))**: solutions to common issues (Wi-Fi, display, etc.) and tips to get the most out of Pimmich.

---

## 🔑 Get your Immich API token

1. Log into your Immich web interface.
2. Click your profile icon (top-right), then choose **Account Settings**.
3. In the **API Keys** section, click **Generate new API Key** and give it a name (e.g., `PimmichFrame`).

⚠️ Once the token is shown, **copy it immediately** — you won't be able to see it again. If lost, you'll need to generate a new one. Never share it publicly: it gives full access to your Immich albums.

🔒 We recommend creating a dedicated Immich account for the photo frame, with access to a single shared album.

---

## 🕰️ Original project history

The version history of the original [Pimmich](https://github.com/gotenash/pimmich) project (Gadgetaulab), before this fork, is kept in the French [README.md](README.md#️-historique-du-projet-dorigine). What this fork adds is described in [🍴 What this fork adds](#-what-this-fork-adds).

---

## 📜 Licenses

- **Pimmich** is released under the **MIT** license (see [LICENSE](LICENSE)): © 2025 gotenash for the original project, © 2026 Sweek-Adam for this fork's changes. The original license notice is kept.
- Third-party components shipped with the project keep their own license, whose text is provided next to each of them:
    - Font Awesome Free (icons CC BY 4.0, fonts SIL OFL 1.1, code MIT): `static/vendor/fontawesome/LICENSE.txt`
    - Leaflet (BSD-2-Clause), Chart.js, GLightbox, SortableJS, Tailwind CSS (MIT): `static/vendor/*/LICENSE*`
    - Vue and Vue Router (MIT): notices kept in the built files of `static/app/`
    - Caveat and Patrick Hand fonts (SIL OFL 1.1), Permanent Marker and Special Elite (Apache 2.0): `static/fonts/LICENSE-*.txt`
    - Natural Earth country outlines (public domain) and OpenCV Zoo's YuNet face detector (MIT): see `resources/README.md`
- The `System > Maintenance > About` page of the interface shows these credits and licenses.

---

## 💖 Credits

- Original project: [Pimmich](https://github.com/gotenash/pimmich) by **Gotenash** and **Shenron**, made at the [Gadgetaulab](https://www.gadgetaulab.fr) — many thanks for this great project!
- This fork: additions and changes for personal use.

<p align="center">
  <a href="https://ko-fi.com/pimmich">
    <img src="https://img.shields.io/badge/Support%20on%20Ko--fi-F16061?logo=kofi&logoColor=white" alt="Support Pimmich (original project) on Ko-fi">
  </a>
</p>
