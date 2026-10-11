"""Dates de la famille (anniversaires, mariages, naissances) : elles déclenchent les dispositions de ces moments-là."""
from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from utils import occasions


def _view(item):
    return {"kind": item["kind"], "name": item["name"], "date": item["date"].isoformat(), "years": item.get("years")}


@app.route('/api/family_dates', methods=['GET'])
@login_required
def family_dates_api():
    config = load_config()
    return jsonify({"success": True, "dates": [_view(d) for d in occasions.family_dates(config)],
                    "upcoming": [_view(d) for d in occasions.upcoming(config)],
                    "active": [o["theme"] for o in occasions.active(config)], "country": occasions.country(config)})


@app.route('/api/family_dates', methods=['POST'])
@login_required
def family_dates_save_api():
    data = request.get_json(silent=True) or {}
    items = data.get("dates")
    if not isinstance(items, list):
        return jsonify({"success": False, "message": _("Liste invalide.")}), 400
    clean = occasions.family_dates({"family_dates": [i for i in items if isinstance(i, dict)][:200]})
    config = dict(load_config())
    config["family_dates"] = [{"kind": d["kind"], "name": d["name"], "date": d["date"].isoformat()} for d in clean]
    save_config(config)
    return jsonify({"success": True, "message": _("%(count)s date(s) enregistrée(s).", count=len(clean))})
