# Installe Pimmich « événement » sous Windows 10 / 11 : Python, ffmpeg (vidéos, GIF), mpv (lecture des vidéos), puis
# les bibliothèques de Pimmich dans un environnement à part (.venv). Dans PowerShell, depuis le dossier de Pimmich :
#   powershell -ExecutionPolicy Bypass -File desktop\install_windows.ps1
# Ensuite : double-clic sur « Pimmich evenement.bat ».
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
Write-Host "=== Python et ffmpeg (winget) ==="
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
try { winget install -e --id shinchiro.mpv --accept-package-agreements --accept-source-agreements }
catch { Write-Host "mpv non installé : les vidéos ne seront pas lues (https://mpv.io pour l'installer à la main)." }
Write-Host "=== Bibliothèques de Pimmich (.venv) ==="
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Set-Content -Path "Pimmich evenement.bat" -Value "@echo off`r`ncd /d %~dp0`r`nstart """" .venv\Scripts\pythonw.exe pimmich_event.py" -Encoding ASCII
Write-Host ""
Write-Host "Pimmich est installe. Pour le lancer : double-clic sur 'Pimmich evenement.bat'."
Write-Host "Au premier lancement, Windows demande d'autoriser Python sur le reseau : acceptez (reseaux prives)."
