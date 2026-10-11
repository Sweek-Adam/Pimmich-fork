# Modèles

- `face_detection_yunet_2023mar.onnx` : détecteur de visages YuNet (OpenCV Zoo, licence MIT,
  https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet). Sert au recadrage
  intelligent qui garde les visages entiers (`utils/faces.py`).

# Cartes

- `world_countries.json` : contours des pays, Natural Earth 1:50m (domaine public, https://www.naturalearthdata.com/),
  coordonnées arrondies à 0,01° et noms des pays en fr/en/es/de/ja. Fond de carte hors ligne de la carte des voyages
  (administration) et des cartes dessinées sur le cadre (`utils/trips.py`, `utils/trip_map.py`).
