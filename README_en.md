# 🖼️ Pimmich – Smart Connected Photo Frame

[![Tests](https://github.com/Sweek-Adam/Pimmich-fork/actions/workflows/tests.yml/badge.svg)](https://github.com/Sweek-Adam/Pimmich-fork/actions/workflows/tests.yml)

Pimmich is a Python application designed to turn a Raspberry Pi into a smart and customizable digital photo frame. It can display photos from multiple sources, be controlled by voice, and much more.

> [!NOTE]
> **This repository is a personal fork** of [Pimmich](https://github.com/gotenash/pimmich), the original project created by Gadgetaulab.
> I took it over for my own photo frame and added **lots of features** (see the list below).
> It is for **purely personal use**: the fork lives its own life, is no longer merged with the original repository
> and is not maintained for other setups. For the official version, head over to the original repository 🙂

<img src="static/pimmich_logo.png" alt="Pimmich Logo" width="300">

<p align="center">
  <a href="https://ko-fi.com/pimmich">
    <img src="https://img.shields.io/badge/Support%20on%20Ko--fi-F16061?logo=kofi&logoColor=white" alt="Support Pimmich on Ko-fi">
  </a>
</p>

---

## 📖 Table of Contents

- 🍴 What this fork adds
- ✨ Main Features
- 🧰 Technologies Used
- 🚀 Installation
- 🔧 Configuration
- 🗣️ Voice Control
- ❓ Troubleshooting (FAQ)
- 🛣️ Roadmap
  - June 2025
  - July 2025
  - August 2025
- 💖 Credits

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
- **Comprehensive Web Interface:** A local configuration page, password-protected and organized into thematic groups and tabs for an intuitive navigation.
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
- **Frontend:** HTML, TailwindCSS, JavaScript
- **Slideshow:** Pygame
- **Image Processing:** Pillow
- **Voice Control:** Picovoice Porcupine (wake word) & Vosk (recognition)
- **Web Server:** NGINX (as a reverse proxy)

---

## 🚀 Installation

### Installation from the Git Repository

#### ✅ Prerequisites

- A Raspberry Pi (model 3B+, 4, or 5 recommended) with Raspberry Pi OS Desktop (64-bit).
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
    This script installs all dependencies, configures the environment, and prepares for automatic startup.
```bash
chmod +x setup.sh
sudo ./setup.sh
```

This script installs system and Python dependencies, sets up the environment, and configures auto-start of the slideshow.

---

### 🔑 Get Your Immich API Token

1. Log into your Immich web interface  
2. Go to **Account Settings**

Click your profile icon (top-right), then choose **Account Settings**.

3. Generate a new API key  
In the **API Key** section, click **Generate new API Key** and give it a name (e.g., `PimmichFrame`).

⚠️ Once the token is shown, **copy it immediately** — you won’t be able to see it again. If lost, you’ll need to generate a new one.

🔒 We recommend creating a dedicated Immich account for the photo frame, with access to a single shared album.

---

### Connect to Pimmich

From a web browser on another device, access:

```
http://<your-raspberry-ip>:5000
```

---

## ⚙️ Configuration Interface

### Slideshow Settings

Here, you can set the display time per photo (minimum ~10s, due to background blur processing for portrait images) and define active hours for the slideshow.

### Photo Import Settings

Choose between importing from an Immich album or a USB stick, and manage downloaded files.

---

## 💖 Credits

- Original project: [Pimmich](https://github.com/gotenash/pimmich) by **Gadgetaulab** — many thanks for this great project! To support it, use [Ko-fi](https://ko-fi.com/pimmich).
- This fork: additions and changes for personal use.
