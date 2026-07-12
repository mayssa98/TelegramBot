"""Tests unitaires pour le service d'affiliation."""

from __future__ import annotations

import database as db
from app.domain import affiliate_service


def test_register_referral_link_success(mock_mongodb):
    """Vérifie l'enregistrement de lien de parrainage."""
    # Créer les utilisateurs parrain et filleul
    conn = db.get_conn()
    conn.users.insert_one({"telegram_id": 999, "username": "referrer"})
    conn.users.insert_one({"telegram_id": 111, "username": "referred"})

    # Enregistrer le lien
    assert affiliate_service.register_referral_link(referred_id=111, referrer_id=999) is True

    # Vérifier l'enregistrement
    ref = conn.referrals.find_one({"referred_id": 111})
    assert ref is not None
    assert ref["referrer_id"] == 999
    assert ref["first_payment"] is False


def test_register_referral_self_referral(mock_mongodb):
    """Vérifie qu'un utilisateur ne peut pas s'auto-parrainer."""
    conn = db.get_conn()
    conn.users.insert_one({"telegram_id": 111})

    assert affiliate_service.register_referral_link(referred_id=111, referrer_id=111) is False


def test_affiliate_reward_on_first_payment(mock_mongodb):
    """Vérifie qu'un parrain reçoit sa récompense au premier paiement du filleul."""
    conn = db.get_conn()
    conn.users.insert_one({"telegram_id": 999})
    conn.users.insert_one({"telegram_id": 111})

    # Parrainer
    affiliate_service.register_referral_link(referred_id=111, referrer_id=999)

    # Simuler le premier paiement du filleul
    res = affiliate_service.on_first_payment(user_id=111)

    assert res is not None
    assert res["referrer_id"] == 999
    assert res["paid_count"] == 1
    assert res["progress"] == 1

    # Par défaut, le seuil est de 10 filleuls (HP_AFFILIATE_TARGET). Donc pas encore récompensé.
    assert res["rewarded"] is False

    # Simuler 9 autres filleuls qui payent pour le même parrain
    for i in range(2, 11):
        fid = 100 + i
        conn.users.insert_one({"telegram_id": fid})
        affiliate_service.register_referral_link(referred_id=fid, referrer_id=999)
        res = affiliate_service.on_first_payment(user_id=fid)

    # Le 10ème filleul déclenche le seuil de parrainage
    assert res["paid_count"] == 10
    assert res["rewarded"] is True
    assert res["reward_amount"] == 1.0  # 100 centimes = 1.0 USDT

    # Vérifier le solde du parrain
    stats = affiliate_service.get_stats(user_id=999)
    assert stats["balance_cents"] == 100
