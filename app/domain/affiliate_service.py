"""Service métier pour l'affiliation.

Gère le parrainage avec récompense au premier paiement confirmé
(pas à l'inscription) et empêche l'auto-parrainage.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from pymongo.errors import DuplicateKeyError

import database as db
from config import AFFILIATE_REWARD_CENTS, AFFILIATE_TARGET

log = logging.getLogger(__name__)


def register_referral_link(referred_id: int, referrer_id: int) -> bool:
    """Enregistre le lien de parrainage lors du /start.

    N'accorde PAS la récompense immédiatement — juste l'association.
    La récompense est attribuée au premier paiement du filleul.

    Returns:
        True si le lien a été enregistré, False sinon.
    """
    if referred_id == referrer_id:
        return False

    conn = db.get_conn()

    # Vérifier que le parrain existe
    if not conn.users.find_one({"telegram_id": referrer_id}, {"_id": 1}):
        return False

    try:
        conn.referrals.insert_one({
            "referred_id": referred_id,
            "referrer_id": referrer_id,
            "created_at": int(time.time()),
            "first_payment": False,  # sera True au premier paiement
        })
        log.info("Lien de parrainage enregistré: %d → %d", referrer_id, referred_id)
        return True
    except DuplicateKeyError:
        return False


def on_first_payment(user_id: int) -> dict[str, Any] | None:
    """Appelé après le premier paiement confirmé d'un utilisateur.

    Vérifie si l'utilisateur a un parrain et, si oui, met à jour le compteur.
    Attribue la récompense si le seuil est atteint.

    Returns:
        Dictionnaire avec info parrain si récompense attribuée, None sinon.
    """
    conn = db.get_conn()

    # Chercher un lien de parrainage non encore activé
    referral = conn.referrals.find_one_and_update(
        {"referred_id": user_id, "first_payment": False},
        {"$set": {"first_payment": True, "paid_at": int(time.time())}},
    )
    if not referral:
        return None

    referrer_id = referral["referrer_id"]

    # Compter les filleuls ayant payé
    paid_count = conn.referrals.count_documents({
        "referrer_id": referrer_id,
        "first_payment": True,
    })

    target = AFFILIATE_TARGET
    reward_cents = AFFILIATE_REWARD_CENTS

    # Vérifier si un palier est atteint
    rewarded = False
    if paid_count > 0 and paid_count % target == 0:
        milestone = paid_count // target
        try:
            conn.affiliate_rewards.insert_one({
                "referrer_id": referrer_id,
                "milestone": milestone,
                "amount_cents": reward_cents,
                "created_at": int(time.time()),
            })
            conn.wallets.update_one(
                {"user_id": referrer_id},
                {"$inc": {"balance_cents": reward_cents}},
                upsert=True,
            )
            rewarded = True
            db.audit_event(
                "affiliate.rewarded",
                actor_id=referrer_id,
                details={"milestone": milestone, "amount_cents": reward_cents, "referred_id": user_id},
            )
            log.info("Récompense affiliation: parrain %d, palier %d", referrer_id, milestone)
        except DuplicateKeyError:
            pass

    return {
        "referrer_id": referrer_id,
        "paid_count": paid_count,
        "progress": paid_count % target,
        "remaining": target - (paid_count % target) if paid_count % target else target,
        "rewarded": rewarded,
        "reward_amount": reward_cents / 100 if rewarded else 0,
    }


def get_stats(user_id: int) -> dict[str, Any]:
    """Récupère les statistiques d'affiliation d'un utilisateur."""
    conn = db.get_conn()
    total_referrals = conn.referrals.count_documents({"referrer_id": user_id})
    paid_referrals = conn.referrals.count_documents({
        "referrer_id": user_id,
        "first_payment": True,
    })
    wallet = conn.wallets.find_one({"user_id": user_id})
    balance_cents = wallet.get("balance_cents", 0) if wallet else 0

    target = AFFILIATE_TARGET
    return {
        "referrals": total_referrals,
        "paid_referrals": paid_referrals,
        "balance_cents": balance_cents,
        "progress": paid_referrals % target,
        "remaining": target - (paid_referrals % target) if paid_referrals % target else target,
    }
