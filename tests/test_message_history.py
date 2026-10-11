"""Historique : un message supprimé est décrit par sa nature (dessin, message vocal, message), son auteur et sa date."""


def test_deleted_label(app_module):
    from web.routes_messages import deleted_label
    with app_module.app.test_request_context(headers={"Accept-Language": "fr"}):
        drawing = deleted_label({"kind": "drawing", "signature": "Léa", "created": "2026-10-11 14:05"})
        assert drawing.startswith("Dessin de Léa du ") and "14:05" in drawing and drawing.endswith("supprimé")
        assert deleted_label({"kind": "voice", "signature": "", "created": "2026-10-11 09:30"}).startswith("Message vocal du ")
        assert deleted_label({"title": "Bon anniversaire", "created": "?"}) == "Message « Bon anniversaire » supprimé"
        assert deleted_label(None) == "Message supprimé"
