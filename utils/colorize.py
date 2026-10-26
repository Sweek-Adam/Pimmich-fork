"""
Colorisation des vieilles photos noir et blanc : le modèle de Zhang, Isola et Efros (« Colorful Image Colorization »,
2016), lancé par OpenCV sur le Raspberry Pi (quelques secondes par photo, aucun service en ligne).

- Le modèle (129 Mo) est téléchargé une fois, à la demande, puis vérifié par son empreinte SHA-256 : un fichier qui ne
  correspond pas est refusé. Le fichier des couleurs (pts_in_hull.npy) est lu sans « pickle » (aucun code exécuté).
- OpenCV 5 ne lit plus les modèles Caffe : à l'installation, les poids sont lus (petit décodeur protobuf) et le réseau
  est reconstruit au format ONNX (paquet onnx), que lit OpenCV ; le fichier Caffe est ensuite effacé.
- Une photo colorisée est toujours une copie : l'original reste tel quel.
"""
import hashlib
import threading
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_DIR / "cache" / "colorize"
FILES = {
    "deploy.prototxt": (["https://raw.githubusercontent.com/richzhang/colorization/caffe/colorization/models/colorization_deploy_v2.prototxt"],
                        "d16418cef8df4ccd703a55ae0ef3960861d5010418f77c90d0a47689998a7169"),
    "pts_in_hull.npy": (["https://raw.githubusercontent.com/richzhang/colorization/caffe/colorization/resources/pts_in_hull.npy"],
                        "b5dec01315c34f43f1c8c089e84c45ae35d1838d8e77ed0e7ca930f79ffa450e"),
    "colorization_release_v2.caffemodel": (["https://www.dropbox.com/s/dx0qvhhp5hbcx7z/colorization_release_v2.caffemodel?dl=1",
                                            "https://huggingface.co/spaces/BilalSardar/Black-N-White-To-Color/resolve/main/colorization_release_v2.caffemodel"],
                                           "f5af1e602646328c792e1094f9876fe9cd4c09ac46fa886e5708a1abc89137b1"),
}
SMOOTH = 1.6             # lissage des couleurs prédites (en cases de la grille 56 × 56 du modèle)
SATURATION = 1.0         # intensité des couleurs prédites (le lissage suffit à éviter les taches criardes)
MONOCHROME_SPREAD = 4.0  # écart-type des couleurs (Cb, Cr) en dessous duquel une photo est monochrome
INSTALL = {"running": False, "done": 0, "total": 0, "error": None}
_net = [None]
_lock = threading.Lock()


ONNX_NAME = "colorization.onnx"


def installed(model_dir=None):
    return (Path(model_dir or MODEL_DIR) / ONNX_NAME).is_file()


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install(model_dir=None, get=None):
    """Télécharge et vérifie les fichiers du modèle ; ValueError si aucune source ne donne le bon fichier."""
    import requests
    get = get or requests.get
    model_dir = Path(model_dir or MODEL_DIR)
    model_dir.mkdir(parents=True, exist_ok=True)
    INSTALL.update(running=True, done=0, total=sum(1 for _ in FILES), error=None)
    try:
        for name, (urls, expected) in FILES.items():
            target = model_dir / name
            if target.is_file() and _sha256(target) == expected or name.endswith(".caffemodel") and installed(model_dir):
                INSTALL["done"] += 1
                continue
            for url in urls:
                tmp = target.with_suffix(target.suffix + ".part")
                try:
                    with get(url, stream=True, timeout=60) as response:
                        response.raise_for_status()
                        with open(tmp, "wb") as f:
                            for chunk in response.iter_content(1 << 20):
                                f.write(chunk)
                except Exception:
                    tmp.unlink(missing_ok=True)
                    continue
                if _sha256(tmp) == expected:
                    tmp.replace(target)
                    break
                tmp.unlink(missing_ok=True)  # fichier inattendu : refusé
            else:
                raise ValueError(f"{name} : téléchargement impossible ou fichier non conforme.")
            INSTALL["done"] += 1
        build_onnx(model_dir)
        (model_dir / "colorization_release_v2.caffemodel").unlink(missing_ok=True)  # 129 Mo : seul le fichier ONNX sert
    except Exception as e:
        INSTALL["error"] = str(e)[:200]
        raise
    finally:
        INSTALL["running"] = False


def is_grayscale(image):
    """Vrai pour une photo monochrome : noir et blanc, ou d'une seule teinte (vieux tirage sépia ou jauni).
    Les couleurs (canaux Cb et Cr) varient alors très peu d'un endroit à l'autre de l'image."""
    from PIL import ImageStat
    small = image.convert("RGB").copy()
    small.thumbnail((200, 200))
    _y, cb, cr = ImageStat.Stat(small.convert("YCbCr")).stddev
    return max(cb, cr) < MONOCHROME_SPREAD


# --- Conversion Caffe -> ONNX ---

def _varint(data, i):
    result = shift = 0
    while True:
        byte = data[i]
        i += 1
        result |= (byte & 0x7F) << shift
        shift += 7
        if byte < 0x80:
            return result, i


def _fields(data):
    """Champs d'un message protobuf : (numéro, type, valeur)."""
    i = 0
    while i < len(data):
        key, i = _varint(data, i)
        number, kind = key >> 3, key & 7
        if kind == 0:
            value, i = _varint(data, i)
        elif kind == 2:
            size, i = _varint(data, i)
            value, i = data[i:i + size], i + size
        elif kind == 5:
            value, i = data[i:i + 4], i + 4
        elif kind == 1:
            value, i = data[i:i + 8], i + 8
        else:
            raise ValueError("protobuf : type de champ inattendu")
        yield number, kind, value


def caffe_weights(path):
    """Poids d'un .caffemodel : {nom de couche: [tableaux numpy]} (NetParameter.layer -> LayerParameter.blobs)."""
    import numpy as np
    weights = {}
    for number, _kind, layer in _fields(Path(path).read_bytes()):
        if number != 100:
            continue
        name, blobs = None, []
        for field, _k, value in _fields(layer):
            if field == 1:
                name = value.decode()
            elif field == 7:
                dims, data = [], b""
                for f2, k2, v2 in _fields(value):
                    if f2 == 7:
                        for f3, k3, v3 in _fields(v2):
                            if f3 == 1 and k3 == 2:
                                j = 0
                                while j < len(v3):
                                    dim, j = _varint(v3, j)
                                    dims.append(dim)
                            elif f3 == 1:
                                dims.append(v3)
                    elif f2 == 5 and k2 == 2:
                        data += v2
                blobs.append(np.frombuffer(data, dtype="<f4").reshape(dims or (-1,)))
        if name and blobs:
            weights[name] = blobs
    return weights


def caffe_layers(prototxt):
    """Couches d'un prototxt : [{name, type, bottom, top, num_output, kernel_size, stride, pad, dilation}]."""
    import re
    layers = []
    for block in re.split(r"\blayer\s*\{", Path(prototxt).read_text())[1:]:
        get = lambda key, default=None: (re.search(rf"\b{key}\s*:\s*\"?([\w.]+)\"?", block) or [None, default])[1]  # noqa: E731
        layers.append({"name": get("name"), "type": get("type"), "bottom": get("bottom"), "top": get("top"),
                       **{k: int(get(k, d)) for k, d in (("num_output", 0), ("kernel_size", 1), ("stride", 1), ("pad", 0), ("dilation", 1))}})
    return layers


def build_onnx(model_dir=None):
    """Reconstruit le réseau de colorisation au format ONNX (lisible par OpenCV 5) à partir des fichiers Caffe."""
    import numpy as np
    import onnx
    from onnx import TensorProto, helper, numpy_helper
    model_dir = Path(model_dir or MODEL_DIR)
    weights = caffe_weights(model_dir / "colorization_release_v2.caffemodel")
    pts = np.load(model_dir / "pts_in_hull.npy", allow_pickle=False).transpose().reshape(2, 313, 1, 1).astype("float32")
    nodes, inits, current = [], [], {"data_l": "data_l"}

    def init(name, array):
        inits.append(numpy_helper.from_array(np.ascontiguousarray(array, dtype="float32"), name))
        return name

    for n, layer in enumerate(caffe_layers(model_dir / "deploy.prototxt")):
        kind, name = layer["type"], layer["name"]
        if kind in ("Input", "Silence"):
            continue
        source, out = current[layer["bottom"]], f"{layer['top']}_{n}"
        k, s, p, d = layer["kernel_size"], layer["stride"], layer["pad"], layer["dilation"]
        if kind in ("Convolution", "Deconvolution"):
            blobs = [pts] if name == "class8_ab" else weights[name]
            inputs = [source, init(f"{name}_W", blobs[0])] + ([init(f"{name}_B", blobs[1])] if len(blobs) > 1 else [])
            nodes.append(helper.make_node("Conv" if kind == "Convolution" else "ConvTranspose", inputs, [out], kernel_shape=[k, k],
                                          strides=[s, s], pads=[p, p, p, p], dilations=[d, d]))
        elif kind == "ReLU":
            nodes.append(helper.make_node("Relu", [source], [out]))
        elif kind == "BatchNorm":
            mean, var, factor = weights[name]
            factor = float(factor.reshape(-1)[0]) or 1.0
            channels = mean.size
            nodes.append(helper.make_node("BatchNormalization", [source, init(f"{name}_s", np.ones(channels)), init(f"{name}_b", np.zeros(channels)),
                                                                 init(f"{name}_m", mean / factor), init(f"{name}_v", var / factor)],
                                          [out], epsilon=1e-5))
        elif kind == "Scale":  # conv8_313_rh : facteur constant 2,606 (le « recuit » des probabilités de couleur)
            nodes.append(helper.make_node("Mul", [source, init(f"{name}_k", np.array([2.606]))], [out]))
        elif kind == "Softmax":
            nodes.append(helper.make_node("Softmax", [source], [out], axis=1))
        else:
            raise ValueError(f"Couche inattendue : {kind}")
        current[layer["top"]] = out
    graph = helper.make_graph(nodes, "colorisation", [helper.make_tensor_value_info("data_l", TensorProto.FLOAT, [1, 1, 224, 224])],
                              [helper.make_tensor_value_info(current["class8_ab"], TensorProto.FLOAT, [1, 2, 56, 56])], initializer=inits)
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    tmp = model_dir / (ONNX_NAME + ".part")
    onnx.save(model, str(tmp))
    tmp.replace(model_dir / ONNX_NAME)


def _load_net(model_dir):
    import cv2
    return cv2.dnn.readNetFromONNX(str(Path(model_dir) / ONNX_NAME))


def colorize(image, model_dir=None):
    """Photo noir et blanc (PIL) -> photo colorisée (PIL, même taille). La luminosité d'origine est gardée telle quelle."""
    import cv2
    import numpy as np
    from PIL import Image
    with _lock:
        if _net[0] is None or model_dir:
            _net[0] = _load_net(model_dir or MODEL_DIR)
        net = _net[0]
        bgr = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR).astype("float32") / 255.0
        lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
        small = cv2.split(cv2.resize(lab, (224, 224)))[0] - 50
        net.setInput(cv2.dnn.blobFromImage(small))
        ab = net.forward()[0, :, :, :].transpose((1, 2, 0))
        # Couleurs lissées avant d'être agrandies (le modèle laisse des taches vives isolées)
        ab = cv2.GaussianBlur(ab, (0, 0), SMOOTH) * SATURATION
        ab = cv2.resize(ab, (bgr.shape[1], bgr.shape[0]), interpolation=cv2.INTER_CUBIC)
        out = cv2.cvtColor(np.concatenate((cv2.split(lab)[0][:, :, np.newaxis], ab), axis=2), cv2.COLOR_LAB2BGR)
        out = (np.clip(out, 0, 1) * 255).astype("uint8")
    return Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))
