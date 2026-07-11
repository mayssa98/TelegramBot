"""Constantes et enums centralisés pour HEAVENPREM."""

from enum import StrEnum


class OrderStatus(StrEnum):
    """Statuts possibles d'une commande."""

    PENDING_PAYMENT = "pending_payment"
    AWAITING_VERIFICATION = "awaiting_verification"
    PAYMENT_CONFIRMED = "payment_confirmed"
    PREPARING_DELIVERY = "preparing_delivery"
    DELIVERED = "delivered"
    VERIFICATION_FAILED = "verification_failed"
    MANUAL_REVIEW = "manual_review"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    EXPIRED = "expired"

    # Alias historique — conservé pour compatibilité avec les commandes existantes.
    PAID = "paid"


class InventoryStatus(StrEnum):
    """Statuts possibles d'un élément d'inventaire."""

    AVAILABLE = "available"
    RESERVED = "reserved"
    DELIVERED = "delivered"
    DISABLED = "disabled"

    # Alias historique.
    SOLD = "sold"


class TicketStatus(StrEnum):
    """Statuts possibles d'un ticket support."""

    OPEN = "open"
    WAITING_ADMIN = "waiting_admin"
    WAITING_CUSTOMER = "waiting_customer"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketCategory(StrEnum):
    """Catégories de tickets support."""

    PAYMENT = "payment"
    DELIVERY = "delivery"
    INVALID_CONTENT = "invalid_content"
    ORDER = "order"
    AFFILIATION = "affiliation"
    OTHER = "other"


class TicketPriority(StrEnum):
    """Niveaux de priorité des tickets."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


# Statuts considérés comme « payés » (pour les requêtes d'agrégation).
PAID_STATUSES = frozenset({
    OrderStatus.PAID,
    OrderStatus.PAYMENT_CONFIRMED,
    OrderStatus.DELIVERED,
})

# Statuts terminaux (plus aucune action possible).
TERMINAL_STATUSES = frozenset({
    OrderStatus.DELIVERED,
    OrderStatus.CANCELLED,
    OrderStatus.REFUNDED,
    OrderStatus.EXPIRED,
})
