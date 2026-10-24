# ❓ Frequently Asked Questions (FAQ) - Pimmich

Here is a list of frequently asked questions to help you use and troubleshoot Pimmich.

> This repository is a **personal fork** of [Pimmich](https://github.com/gotenash/pimmich) (purely personal use). The paths
> below (e.g. `Screen > Display`) are those of the new admin interface menu.

---

### General Questions

**Q: What is Pimmich?**

**A:** Pimmich is software that turns a Raspberry Pi into a smart digital photo frame. It can display photos and videos from an [Immich](https://immich.app/) server, Google Drive, Dropbox, OneDrive, an iCloud shared album, a USB drive, a network share (Samba/Windows), a smartphone, WhatsApp, or even through the Telegram messaging app.

**Q: What do I need to use Pimmich?**

**A:** You will need:
- A Raspberry Pi (model 3B+, 4, or 5 recommended) with its power supply.
- An SD card with Raspberry Pi OS Trixie (64-bit) installed.
- A screen.
- An Internet connection (Wi-Fi or Ethernet).

---

### Installation and Configuration

**Q: How do I install Pimmich?**

**A:** The installation is designed to be simple:
1. Clone the GitHub repository: `git clone https://github.com/Sweek-Adam/Pimmich-fork.git pimmich`
2. Go into the folder: `cd pimmich`
3. Make the installation script executable: `chmod +x setup.sh`
4. Run the script with administrator rights: `sudo ./setup.sh`
5. Reboot: `sudo reboot`

The script takes care of installing all dependencies and configuring the system for automatic startup.

**Q: How do I access the admin interface?**

**A:** Once the Raspberry Pi has started, open a web browser on another device (computer, smartphone) connected to the same network and type your Raspberry Pi's IP address, for example `http://192.168.1.25`: you are redirected to `https://`. The certificate is self-signed, so the browser shows a warning the first time. If you don't know the IP, it is shown on the frame's screen at first boot or when no photos are found.

**Q: There are two interfaces: which one should I use?**

**A:** After logging in, the new interface opens (`/app`): it works well on phones and has a dark mode, a search and a guided tour. The old interface is still reachable through the "Classic interface" link at the bottom of the menu; Pimmich remembers your choice. A few settings still only exist in the classic interface: a link on the relevant page leads straight to them.

**Q: I forgot my password for the web interface. How can I reset it?**

**A:** If there is another administrator account, it can reset your password in `System > Accounts`. Otherwise, the easiest way is to re-run part of the installation script:
1. Connect to your Raspberry Pi via SSH.
2. Delete the old credentials file with the command: `sudo rm /boot/firmware/credentials.json`
3. Go to the project folder: `cd pimmich`
4. Re-run the installation script: `sudo ./setup.sh`

The script is designed to be re-run safely. It will detect that the credentials file is missing and create a new one. The new password will be displayed directly in the terminal at the end of the process. Make sure to write it down!

**Q: How do I get an Immich API Token?**

**A:**
1. Log in to your Immich web interface.
2. Go to "Account Settings" (via your profile icon).
3. In the "API Keys" section, click "Generate new API Key".
4. Give it a name (e.g., "Pimmich") and copy the generated key.
5. Paste it in `Photos > Sources`, Immich card.

*Tip:* For better security, create a dedicated Immich user for the frame with access limited to a single shared album.

---

### Features

**Q: How does the Telegram feature work?**

**A:** It allows you and your guests to send photos directly to the frame.
1.  **Create a bot** on Telegram by talking to `@BotFather`. It will give you a **Token**.
2.  **Get your Telegram User ID** by talking to a bot like `@userinfobot`.
3.  Enter these two pieces of information in `Sharing > Telegram`.
4.  You can then create secure, temporary invitation links for your friends and family.

**Q: How can friends and family send photos, messages or drawings?**

**A:** Enable the guest page in `Sharing > Guests`. From the home Wi-Fi, they can send photos, write a message, draw with stickers, record a voice message or react to the photo on screen. A QR code can be shown on the frame to open it. For access from outside the home, a guest link goes through Tailscale (once: `~/pimmich/utils/enable_remote_guests.sh` on the Raspberry Pi). Guest photos go through `Sharing > To review`, except for trusted guests; messages and drawings are then kept in the guestbook.

**Q: What is the "Favorites" section for?**

**A:** By marking a photo as a favorite (using the star icon <i class="fas fa-star"></i> in `Photos > Library`), you increase how often it appears in the slideshow. You can adjust the "boost factor" in `Screen > Display` to make them appear more or less often.

**Q: What is the "Postcard" effect?**

**A:** It's a filter that adds a white border and a space for a caption (if you add one through the interface) to your photos, giving them a postcard look. Photos sent via Telegram use this effect by default for a more personal and warm feel.

**Q: Can the frame show only videos?**

**A:** Yes: on the `Home` page, choose "Videos only". The frame then plays all videos one after another, without photos or special cards; switch back to "Photos and videos" for the usual slideshow.

**Q: Are animated GIFs supported?**

**A:** Yes, from every import: phone, guests, Google Drive and other clouds, Immich, iCloud, Samba, USB stick, e-mail, WhatsApp and Telegram. Telegram sends GIFs as short videos: the frame converts them back to GIFs. A GIF animates as a single photo (the slow zoom is then turned off) and in layouts, where it keeps its place, its tilt and whatever covers it. Layouts that change photo colours (photo booth, film strip, old album) keep the GIF still, on its first frame. So do the Polaroid and Postcard effects.

**Q: How do I show the time, weather, tides or calendar?**

**A:** Everything is in `Screen > Clock & weather`: time and date (font, size, colours, background), weather (OpenWeatherMap key), tides (StormGlass key and harbour coordinates), Google calendar (secret iCal address) and countdowns. Time and weather stay visible on layouts (mosaic, wall...).

**Q: Which voice commands are available?**

**A:** Enable them in `System > Voice control`, then start every command with your wake word, for example: *"next photo"*, *"previous photo"*, *"pause"*, *"play"*, *"duration 15 seconds"*, *"play Vacation"*, *"show postcards"*, *"enable source USB"*, *"sleep mode"*, *"wake up the frame"*, *"shut down the frame"*, *"return to main slideshow"*.

---

### Troubleshooting

**Q: I have a problem, where can I find help?**

**A:** `System > Logs` is the best place to start: each service (web server, slideshow, voice control...) has its own log, with an "Errors only" filter and a "Follow live" mode. `System > Maintenance` also shows the hardware status (temperature, power supply, SD card).

**Q: My screen doesn't turn off completely, the backlight stays on. What can I do?**

**A:** Some screens don't respond properly to the software sleep command (DPMS). First try HDMI-CEC (`Screen > Display`, if your TV supports it). Otherwise, the most reliable solution is a Wi-Fi smart plug that physically cuts the screen's power: enable the "Smart Plug" option in the `Display` tab of the classic interface and enter the URLs to turn your plug on and off. Many plugs (Tasmota, Shelly, Kasa, etc.) can be controlled with simple HTTP requests.

**Q: Videos are not smooth or don't display. What should I do?**

**A:** In `Screen > Display`, try enabling "**Enable hardware video decoding**". It is much more efficient, especially on a Raspberry Pi. If it causes problems (black/blue screen after a video), disable it.

**Q: The frame's IP address changes: how do I find the interface?**

**A:** Type its name instead of its IP address. `https://cadre-photo.local` works from a phone or computer on the same network. `https://cadre-photo.home` goes through an Orange Livebox (the suffix depends on the router, often `.home` or `.lan`). `https://cadre-photo` works from anywhere with Tailscale. Replace `cadre-photo` with the name given to the Raspberry Pi at installation. The exact list is shown in `System > Network`, "Frame address" card. Without `https://`, the browser may run a search instead of opening the page.

**Q: Does Pimmich run on a Raspberry Pi 2, 3, 4 or 5?**

**A:** Yes. Pimmich detects the model and picks a profile (`System > Maintenance`, "Hardware profile" card):
- **Light** (Zero, Pi 1, Pi 2): videos in 720p, one animation per composition, no face detection;
- **Standard** (Pi 3, Pi 4 with 1 GB);
- **Full** (Pi 4 and 5).

The profile never overrides a setting you chose. It suggests "recommended settings", applied only when you click the button. On small models, installation skips OpenCV, which is too heavy for them.

**Q: Can the frame remember several Wi-Fi networks? What if it finds none?**

**A:** Yes: `System > Network`, "Saved networks" card. Add as many networks as you like, even out of range (handy before taking the frame to someone's home), and sort them by preference. With no network at all, the frame still starts and shows the photos it already has. If the time could not be updated for lack of Internet, it ignores the display hours so it does not stay off by mistake. With the "Fallback hotspot" enabled, after 2 minutes it creates its own "Cadre-Pimmich" Wi-Fi: the password and a QR code appear on screen; connect your phone, open `http://10.42.0.1`, then add the local network in `System > Network`.

**Q: The Wi-Fi won't connect, but Ethernet (cable) works. Why?**

**A:** Sometimes, if an Ethernet cable is plugged in, the system gives it priority. In `System > Network`, you can try temporarily disabling the "**Wired Interface (eth0)**" to force the system to use Wi-Fi only.

**Q: How do I update Pimmich?**

**A:** Go to `System > Maintenance` and click "**Start the update**". Pimmich downloads the latest version from GitHub and restarts; if the new version doesn't start, it automatically goes back to the previous one. A button also lets you go back to the previous version manually.

**Q: I changed a setting, but nothing changes on the slideshow.**

**A:** In the new interface, settings are saved automatically and the slideshow restarts by itself a few seconds after a series of changes (except during an import, so as not to interrupt it). If nothing changes, check `System > Logs`; as a last resort, restart the frame from `System > Maintenance`. A setting changed by mistake can be undone from the `Home` page ("Latest actions").

**Q: How do I protect the SD card and back up the frame?**

**A:** `System > Maintenance` creates a full, restorable backup (settings, accounts, messages...) and shows whether wear protection is active. To enable it, run once on the Raspberry Pi `sudo ~/pimmich/utils/enable_sd_protection.sh` then reboot: logs are then written to RAM (log2ram). Add `--zram` to also put swap in compressed memory.

**Q: I flashed the image on a bigger SD card: how do I use all the space?**

**A:** `System > Maintenance`, "SD card file system" card: it shows the partition and card sizes. If some space is unused, the "Extend file system" button prepares the resize, which completes at the next reboot (no data is deleted).
