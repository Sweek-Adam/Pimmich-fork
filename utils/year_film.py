"""
Film de l'année : un montage vidéo (MP4, 720p) des plus belles photos de l'année, dans l'ordre, avec un titre, le nom
de chaque mois, un fondu entre les photos et une musique de la bibliothèque du cadre.

Mêmes photos que le livre photo (utils/photo_book.py). Chaque photo devient un court segment vidéo (fondu au noir à
l'entrée et à la sortie), puis les segments sont mis bout à bout sans réencodage et la musique est ajoutée (en
boucle si elle est trop courte, fondu à la fin). Encodage à basse priorité : le cadre reste fluide.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from utils import photo_book as book
from utils.boot_screen import font
from utils.message_renderer import N_

WIDTH, HEIGHT, FPS = 1280, 720, 25
PHOTO_SECONDS, CARD_SECONDS, FADE = 3.5, 2.5, 0.5
MAX_PHOTOS = 60


def _contain(image):
    """Photo entière sur un fond flou de la même photo (rien n'est coupé, même en portrait)."""
    background = image.copy()
    background.thumbnail((WIDTH // 4, HEIGHT // 4))
    background = background.resize((WIDTH, HEIGHT)).filter(ImageFilter.GaussianBlur(18))
    background = Image.blend(background, Image.new("RGB", (WIDTH, HEIGHT)), 0.35)
    photo = image.copy()
    photo.thumbnail((WIDTH, HEIGHT), Image.LANCZOS)
    background.paste(photo, ((WIDTH - photo.width) // 2, (HEIGHT - photo.height) // 2))
    return background


def _card(title, subtitle=""):
    card = Image.new("RGB", (WIDTH, HEIGHT), (18, 16, 24))
    draw = ImageDraw.Draw(card)
    hand = font(130, 400, str(book.HAND)) if book.HAND.exists() else font(100, 800)
    draw.text((WIDTH / 2, HEIGHT * 0.45), title, font=hand, fill=(255, 214, 190), anchor="mm")
    if subtitle:
        draw.text((WIDTH / 2, HEIGHT * 0.66), subtitle, font=font(36, 500), fill=(200, 196, 210), anchor="mm")
    return card


def _segment(ffmpeg, image_path, seconds, out_path, nice):
    vf = f"fade=t=in:st=0:d={FADE},fade=t=out:st={seconds - FADE}:d={FADE},format=yuv420p"
    command = nice + [ffmpeg, "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(FPS), "-t", str(seconds), "-i", str(image_path),
                      "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-r", str(FPS), str(out_path)]
    subprocess.run(command, check=True, capture_output=True, timeout=600)


def build(index, year, out_path, base_dir, music=None, excluded=(), loved=None, favorites=(), title=None, progress=None, translate=None):
    """Écrit le film de l'année ; retourne sa durée en secondes (0 si aucune photo cette année-là)."""
    book._tr[0] = translate or (lambda text: text)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg est introuvable.")
    items = book.select(index, year, excluded, loved, favorites, limit=MAX_PHOTOS)
    if not items:
        return 0
    nice = ["nice", "-n", "19"] if shutil.which("nice") else []
    title = title or book.tr(N_("Notre année"))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out_path.parent) as work:
        work = Path(work)
        slides = [(_card(title, str(year)), CARD_SECONDS + 1)]
        month = None
        for key, when in items:
            if when.month != month:
                month = when.month
                slides.append((_card(book.tr(book.MONTHS[month - 1]).capitalize()), CARD_SECONDS))
            slides.append((key, PHOTO_SECONDS))
        total, duration, segments = len(slides) + 1, 0.0, []
        for n, (slide, seconds) in enumerate(slides):
            if isinstance(slide, str):
                image, _path = book._open(slide, base_dir)
                if image is None:
                    continue
                slide = _contain(image)
            frame = work / f"f{n:04d}.jpg"
            slide.save(frame, "JPEG", quality=92)
            segment = work / f"s{n:04d}.mp4"
            _segment(ffmpeg, frame, seconds, segment, nice)
            frame.unlink()
            segments.append(segment)
            duration += seconds
            if progress:
                progress(n + 1, total)
        (work / "list.txt").write_text("".join(f"file '{s.name}'\n" for s in segments))
        command = nice + [ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(work / "list.txt")]
        if music and Path(music).is_file():
            command += ["-stream_loop", "-1", "-i", str(music), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                        "-af", f"afade=t=out:st={max(0.0, duration - 3)}:d=3", "-shortest"]
        else:
            command += ["-c", "copy"]
        tmp = work / "film.mp4"
        subprocess.run(command + ["-movflags", "+faststart", str(tmp)], check=True, capture_output=True, timeout=1800)
        tmp.replace(out_path)
    if progress:
        progress(total, total)
    return round(duration)
