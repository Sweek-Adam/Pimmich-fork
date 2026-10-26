# 📘 Photo frame user manual

This manual explains, step by step, how to use the frame day to day. It is meant for the whole family: no technical
knowledge needed. To install the frame, see [INSTALL_en.md](INSTALL_en.md); for specific questions, the
[FAQ](FAQ_en.md).

*Version française : [MANUEL.md](MANUEL.md).* Menu names below are those of the English interface.

---

## 📖 Contents

1. [Open the frame's interface](#1-open-the-frames-interface)
2. [Add photos](#2-add-photos)
3. [Find and organise photos](#3-find-and-organise-photos)
4. [What the screen shows](#4-what-the-screen-shows)
5. [Control the frame without a phone](#5-control-the-frame-without-a-phone)
6. [Guests, parties and games](#6-guests-parties-and-games)
7. [Staying close: messages, hearts, twin frames](#7-staying-close-messages-hearts-twin-frames)
8. [Making keepsakes: book, calendar, film](#8-making-keepsakes-book-calendar-film)
9. [Emails from the frame](#9-emails-from-the-frame)
10. [Upkeep, backups and notifications](#10-upkeep-backups-and-notifications)
11. [Turning on, off, restarting](#11-turning-on-off-restarting)
12. [Privacy: what leaves the house](#12-privacy-what-leaves-the-house)

---

## 1. Open the frame's interface

On a phone or computer connected to the **home Wi-Fi**, open a browser and type:

- **`cadre-photo.local`** (or `cadre-photo.home` on some routers), or the frame's IP address;
- from outside, the frame's **Tailscale** address if it has been set up.

The first time, the browser warns about an "unsafe" certificate: that's expected (the frame makes its own
certificate), accept it. Sign in with your account. Each family member can have one (**System › Accounts**).

The menu groups pages in six sections: **Home**, **Photos**, **Screen**, **Sharing**, **Games**, **System**.
**Home › What's new** lists the latest features.

> 💡 Add the interface to your phone's home screen (Share › "Add to Home Screen"): it then opens like an app.

## 2. Add photos

### From your phone
- **Photos › Import**: pick photos and videos on the phone, they go to the frame.
- **Guests** (no account) use the guest page: QR code shown on the frame, or the `…/upload` link. Their photos wait for
  your approval in **Sharing › To approve** (except during a party, or for trusted guests).
- Also: **Telegram**, **email** (the frame checks its own mailbox), **WhatsApp**, and direct sharing from Android.

### From your online libraries
**Photos › Sources**: Google Drive, Immich, Dropbox, OneDrive, iCloud shared albums, network share (NAS), USB stick.
The frame syncs by itself; the small "Preparing" pill only appears when there is something new.

### Old paper photos: the scanner
**Photos › Import › Scan a paper photo**

1. Lay the print on a **dark table**, well lit, without glare.
2. Tap "Photograph a print" and take the picture with your phone.
3. The frame finds the edges, **straightens** the photo and **revives** faded colours. Rotate it if needed.
4. "Add to the frame": it joins the "Scanned paper photos" source.

### Colourising black-and-white photos
**Photos › Import › Colourising black-and-white photos**

- The first time, tap **"Install colourisation"** (129 MB, downloaded once).
- Then, in the **Library**, open a black-and-white (or sepia) photo and tap **"Colourise"**: a colour copy joins the
  slideshow ("Colourised photos" source). The original is never changed.
- Optionally, scanned black-and-white prints are colourised automatically (the original is kept aside).

Colours are soft and plausible, computed on the frame (nothing goes to the internet).

### Media preparation
Each photo is "prepared" to the screen size; videos are re-encoded (big ones at night).
**Photos › Media preparation** shows the state of every media file:
- **To prepare**: a "Prepare" button catches up a file that was left out;
- **Failed** (damaged, unreadable file): the bin 🗑 deletes it, or "Delete the N failed" for a whole source.

## 3. Find and organise photos

**Photos › Library**: every photo, with search by text (place, caption, name), date, source, person (with Immich),
and "by content" ("beach", "dog"… with Immich).

When you open a photo, you can:
- write a **caption** (and choose its style), make it a **favourite** ⭐;
- **"Tell this photo's story"** 🎤: record the story behind the photo (up to 90 s). The frame plays this **voice
  memory** when the photo is on screen;
- see the **comments** left by guests (and delete them);
- **"Colourise"** a black-and-white photo;
- adopt a **suggested caption** ✨ (see below).

### Automatically suggested captions
**Screen › Captions › Automatically suggested captions**: every night, the frame suggests a short description and
keywords (beach, snow, birthday…). They're used by the search, and one click adopts them. Two ways:
- **Immich**: keywords, free (photos coming from Immich);
- **Claude**: a real sentence for each photo. A reduced copy of the photo is sent to Anthropic (about 0.7 cents per
  photo, on your Anthropic account). **Off by default.**

A handwritten caption is never replaced.

### Playlists, favourites, map
- **Playlists**: a selection of photos to loop (with music if you like).
- **Favourites**: your favourite photos, shown more often.
- **Map**: photos on a world map, grouped by trip.

## 4. What the screen shows

### The slideshow
**Screen › Display** sets the essentials: on/off hours (weekdays, weekend), time per photo, transitions, sources shown.

- **Pan/Zoom effect**: the photo moves gently while it's shown. **Ken Burns** slowly zooms towards **faces** (the
  "slide" movement goes from one edge to the other).
- **Forgotten photos**: those never (or rarely) shown come back more often.
- **Long videos**: the frame only shows the **liveliest part** (20 s by default); the full video stays in the library.
- **Automatically improve dark or dull photos** (**Screen › Layouts**): a light touch-up of the displayed copy, never
  the original; coloured party lighting is kept as it is.

### Special slides
- **On this day**: photos taken on this date in previous years.
- **This week**: the family calendar and countdowns.
- **Your week on the frame**: on Sunday evening, the week's new photos, who sent them, messages and hearts.
- **Layouts** (Screen › Layouts): mosaics, walls, postcards, seasonal and birthday themes.

### Clock, weather, night
**Screen › Clock & weather**: clock, animated weather, calendar. In the evening the brightness goes down; at night a
discreet clock can replace the black screen.

### The boot screen
When it starts, the frame shows "Your photo frame is starting" in one of four styles (picked at random), with its
features and the upload QR code, then goes to the first photo without a black screen.

### Cast to a TV (Chromecast)
**Screen › Display › Cast to a TV**: "Find TVs", pick the TV, then **"Cast the slideshow"** or **"Cast the film"**
(the film of the year, once "played on the frame"). "Stop" returns the TV to its home screen.

## 5. Control the frame without a phone

### The TV remote (HDMI-CEC)
If the frame is plugged into a TV (with HDMI-CEC enabled in the TV settings: Anynet+, Bravia Sync, SimpLink…) and the
TV is on the frame's input:

| Key | Action |
|---|---|
| ▶ / ◀ (or channel + / −) | next / previous photo |
| OK, play, pause | pause / resume |
| ▲ or **red** key | ❤️ on the photo shown |
| **blue** key | "thinking of you" to the family's other frames |
| Stop, Back | put the frame to sleep |
| any key (frame asleep) | wake up |

Setting: **Screen › Display › Television**.

### The motion sensor
A small infrared sensor (HC-SR501, a few euros) plugged into the Raspberry Pi: the screen **turns off** when nobody has
walked past the frame for a few minutes, and **turns back on** as soon as someone comes into the room. Wiring and
setting: **Screen › Display › Motion sensor** (the card shows the last motion seen, handy to check the wiring).

### The physical button
A button plugged into the Raspberry Pi: one press puts the frame to sleep, another wakes it up
(**Screen › Display › Physical button**).

### Grandparents mode
**Sharing › Guests › Grandparents mode**: a **very simple page with very big buttons**, for the phone of someone who
doesn't like apps:

1. Type the name ("Hello Grandma!") and tap "Create the link".
2. Scan the **QR code** with their phone (on the home Wi-Fi), then add the page to the home screen.
3. They see the photo on screen and can: go to the next one, pause, send a ❤️, **write a note** or **say it out loud**,
   send "thinking of you" to the other frames, turn the frame on or off.

No password; the page only works on the home Wi-Fi. "Change the link" makes the old one useless.

## 6. Guests, parties and games

### The guest page
The QR code shown in a corner of the frame leads to the guest page: send **photos**, a **message**, a **drawing**, a
**voice message**, sign the **guestbook**, and, on the photo currently shown, send a **reaction** (❤️ 😂 😮 👏) or a
**few words** 💬 that appear straight away as a banner on the frame.

### Party mode
**Sharing › Guests › Party mode**: party name, duration, then "Start". A big QR code stays on screen; guests' photos
appear **straight away**, full screen with their name, then in the "Party wall". At the end, the usual slideshow comes
back and the party album stays in the sources.

- **Wi-Fi QR code**: tick "Also show the home Wi-Fi QR code": guests join with one scan (the password is read from the
  Raspberry Pi when shown, never saved).
- **Photo booth**: see below.

### The photo booth
**Sharing › Guests › Photo booth**: during a party, guests **print** the photo shown on the frame on a Wi-Fi printer at
home.

1. "Find printers", then tap yours.
2. Choose the **paper**: 4×6 photo, or A4 (large photo).
3. "Test print" to check.
4. Tick "Open the photo booth during parties" and set the **prints per guest**. Optionally, every photo received can
   be printed automatically (with a cap for the party).

Each print has a white margin, the party name and the date, like a real photo booth. Guests get a "🖨️ Print the photo
on screen" button on their page.

### The frame wall
**Sharing › Guests › Frame wall**: place several frames side by side; together they show **one big photo**, split
across the screens and changed at the same moment on all of them. Choose the frames and their left-to-right order, the
gap between screens (bezels), the time per photo, then "Start the wall". The other frames must first be added in
"Family frames" (see § 7).

### Games
**Games › Family games**: eleven games played from phones ("Where and when?", "Who is it?", bingo, timeline…). The
frame shows the game and its rules next to the QR code.

## 7. Staying close: messages, hearts, twin frames

### Messages
**Photos › Messages**: a note shown full screen on the frame, with a style. It can be **scheduled** (on a birthday) or
**recurring** (every Monday…). Guests can also send them from the guest page.

### Family frames
**Sharing › Guests › Family frames**: control the family's other frames from here (at Grandma's, at the chalet…): see
their current photo, turn them on, send them photos or a message.

1. On the other frame: "Pairing code" › "Create a code".
2. Here: its address (Tailscale or local network) and that code.

Then, for each frame:
- **💞 "Thinking of you"**: hearts fly up on its screen, with "Grandma is thinking of you";
- **automatic sharing** (checkboxes, off by default): new photos received and messages written here also go to that
  frame. Only new items are sent; what comes from the other frame never comes back (no loop); Google Drive or Immich
  photos are not copied.

## 8. Making keepsakes: book, calendar, film

Everything is at the bottom of **Photos › Library**.

### The photo book of the year
Pick the year, "Create the book": a **print-ready PDF** (landscape A4) with a cover, the best photos month by month
(most loved and favourites first, no blurry photos or screenshots), then "the year in numbers". A few minutes on a
Raspberry Pi; then "Download".

### The photo calendar
"Create the calendar" (next year by default): one month per page, **portrait A4**, with a nice photo taken that month in
a previous year and the grid of days showing **family birthdays**, Mother's and Father's Day.

### The film of the year
Pick some music, "Make the film": a short film of the best photos, with a title, months, fades and music (about ten
minutes of editing). Then: "Watch", "Download", or **"Play on the frame"** (it joins the slideshow, and can be cast to a
Chromecast TV).

## 9. Emails from the frame

The frame sends emails from **its own mailbox**, the same one used to receive photos (**Photos › Sources › Photos
received by email**). Recipients don't see each other's addresses.

- **Photo of the day** (**Sharing › Guests**): for loved ones without a frame, one photo a day at the chosen time (an
  "on this day" memory if possible). Never the same photo within two months.
- **Monthly report** (**Sharing › Guests**): on the 1st of the month, photos received and from whom, views, hearts and
  the most loved photos.

Both are **off by default**; "Send now" lets you try.

## 10. Upkeep, backups and notifications

### Notifications (System › Notifications)
On your phone (ntfy app): guests' photos, sync errors, frame problems, finished imports, daily summary… and **upcoming
birthdays** (three days before, to prepare a note or a voice message, then on the day).

### Backups (System › Maintenance)
- **Full backup**: settings, accounts, messages, playlists… to download, or **with the photos** on a USB drive or NAS.
- **Automatically every week**: tick the box, choose the drive, the day and how many backups to keep. It runs at
  night; free space is checked first; a notification warns you if it fails.
- **Restore**: one click on a backup.

### Updates
**System › Maintenance**: one-click update (with automatic roll-back if something goes wrong).

## 11. Turning on, off, restarting

- The frame turns on and off by itself at the chosen hours (**Screen › Display**).
- The interface's **Home** page puts it to sleep, wakes it up, skips a photo.
- Heavy work (big videos, automatic captions, the weekly backup) is done **at night**, screen off.

## 12. Privacy: what leaves the house

By default **nothing leaves the house** apart from the syncs you set up (Google Drive, Immich…). These features send
data outside and are **all off by default**:

| Feature | What leaves | Where |
|---|---|---|
| Guests outside the house (Tailscale Funnel) | the guest page becomes reachable with a secret link | internet |
| Photo of the day, monthly report | one or a few photos | the chosen email addresses |
| Automatic sharing between frames | new photos and messages | the chosen family frames |
| Captions suggested by Claude | a reduced copy of each photo | Anthropic |
| Notifications | short texts | the ntfy service |

Colourisation, the scanner, the photo book, the film and face detection all run **on the frame**.
