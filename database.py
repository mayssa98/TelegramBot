"""
Couche d'accès aux données (SQLite).
Persiste : utilisateurs, catalogue (services -> offres), commandes.
Le catalogue est entièrement éditable via le panneau admin.
"""
import sqlite3
import threading
import time
import json
import os
from config import DB_PATH

_local = threading.local()
_lock = threading.Lock()


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        _local.conn = conn
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username    TEXT,
            first_name  TEXT,
            lang        TEXT DEFAULT 'fr',
            created_at  INTEGER
        );

        CREATE TABLE IF NOT EXISTS services (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            emoji       TEXT DEFAULT '',
            sort_order  INTEGER DEFAULT 0,
            active      INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS offers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id  INTEGER NOT NULL,
            name        TEXT NOT NULL,
            price       REAL,            -- prix unitaire en USD (NULL = à compléter)
            stock       INTEGER DEFAULT 0,
            note        TEXT DEFAULT '', -- ex: remise gros volume
            active      INTEGER DEFAULT 1,
            FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS orders (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            offer_id      INTEGER,
            service_name  TEXT,
            offer_name    TEXT,
            qty           INTEGER DEFAULT 1,
            unit_price    REAL,
            total_price   REAL,
            status        TEXT DEFAULT 'pending_payment',
            -- statuts: pending_payment, awaiting_verification, paid, delivered, cancelled, rejected
            txid          TEXT DEFAULT '',
            verify_method TEXT DEFAULT '',   -- auto / auto_failed
            delivery_text TEXT DEFAULT '',
            created_at    INTEGER,
            updated_at    INTEGER
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS referrals (
            referred_id INTEGER PRIMARY KEY,
            referrer_id INTEGER NOT NULL,
            created_at  INTEGER NOT NULL,
            CHECK (referred_id <> referrer_id)
        );

        CREATE TABLE IF NOT EXISTS wallets (
            user_id       INTEGER PRIMARY KEY,
            balance_cents INTEGER NOT NULL DEFAULT 0 CHECK (balance_cents >= 0)
        );

        CREATE TABLE IF NOT EXISTS affiliate_rewards (
            referrer_id INTEGER NOT NULL,
            milestone  INTEGER NOT NULL,
            amount_cents INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            PRIMARY KEY (referrer_id, milestone)
        );

        CREATE INDEX IF NOT EXISTS idx_orders_user_created
            ON orders(user_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_txid_unique
            ON orders(txid) WHERE txid <> '';
        """
    )
    conn.commit()
    _seed_catalog(conn)


def _seed_catalog(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM services")
    if cur.fetchone()["c"] > 0:
        return  # déjà initialisé

    # (nom_service, emoji, [ (offre, prix|None, stock, note) ])
    catalog = [
        ("Canva", "🎨", [
            ("Canva Pro 1m", 0.14, 113, ""),
            ("Canva Pro Head 1m", 0.86, 2, ""),
        ]),
        ("Capcut", "🎬", [
            ("Capcut Pro 1m", 2.00, 24, ""),
        ]),
        ("Chatgpt", "🤖", [
            ("Code Reedem Chatgpt GO 3m", 0.06, 14360, ""),
        ]),
        ("Discord Nitro", "🎮", [
            ("Code Reedem Discord Nitro 1m", 0.29, 4, ""),
        ]),
        ("Gemini AI", "✨", [
            ("Gemini Pro 12m [invit]", 1.43, 38, ""),
            ("Gemini Pro 12m [head]", 4.28, 50, ""),
        ]),
        ("Grok AI", "🧠", [
            ("Supergrok 3M Sharing [garantie 25j]", 2.86, 5, "Garantie 25 jours"),
            ("Supergrok 3M Privat", 8.57, 28, "Gros volume >=25 pcs: 5.71$/pc"),
            ("Supergrok 6M Privat", 11.42, 100, "Gros volume: 10.85$/pc"),
            ("Supergrok 12M Privat", 17.14, 108, "Gros volume: 16.57$/pc"),
        ]),
        ("Manus AI", "🚀", [
            ("Manus AI Pro 1m", 3.14, 14, ""),
        ]),
        # --- Services sans prix détaillé : prix=None, à compléter par l'admin ---
        ("Adobe Creative Cloud", "🅰️", [("Offre standard", None, 5, "Prix à définir")]),
        ("Alight Motion", "📲", [("Offre standard", None, 46, "Prix à définir")]),
        ("Base44 AI", "🧩", [("Offre standard", None, 3, "Prix à définir")]),
        ("Duolingo", "🦉", [("Offre standard", None, 3, "Prix à définir")]),
        ("Emergent AI", "🌐", [("Offre standard", None, 1, "Prix à définir")]),
        ("Flux AI", "⚡", [("Offre standard", None, 1, "Prix à définir")]),
        ("Freebeat AI", "🎵", [("Offre standard", None, 19, "Prix à définir")]),
        ("Gamma AI", "📊", [("Offre standard", None, 16, "Prix à définir")]),
        ("Getcontac Premium", "📞", [("Offre standard", None, 3, "Prix à définir")]),
        ("Google Colab", "🐍", [("Offre standard", None, 36, "Prix à définir")]),
        ("Meitu", "📸", [("Offre standard", None, 1, "Prix à définir")]),
        ("Outlook Mail", "📧", [("Offre standard", None, 198, "Prix à définir")]),
        ("Perplexity AI", "🔍", [("Offre standard", None, 3, "Prix à définir")]),
        ("Picsart", "🖼️", [("Offre standard", None, 3, "Prix à définir")]),
        ("Reelshort", "📹", [("Offre standard", None, 1, "Prix à définir")]),
        ("Uncensored AI", "🔓", [("Offre standard", None, 3, "Prix à définir")]),
        ("Viu", "📺", [("Offre standard", None, 38, "Prix à définir")]),
        ("VPN", "🛡️", [("Offre standard", None, 2, "Prix à définir")]),
        ("Weshsop AI", "🛍️", [("Offre standard", None, 14, "Prix à définir")]),
    ]

    order = 0
    for name, emoji, offers in catalog:
        order += 1
        cur.execute(
            "INSERT INTO services (name, emoji, sort_order, active) VALUES (?,?,?,1)",
            (name, emoji, order),
        )
        sid = cur.lastrowid
        for oname, price, stock, note in offers:
            cur.execute(
                "INSERT INTO offers (service_id, name, price, stock, note, active) "
                "VALUES (?,?,?,?,?,1)",
                (sid, oname, price, stock, note),
            )
    conn.commit()


# ---------------- Users ----------------
def upsert_user(telegram_id, username, first_name):
    conn = get_conn()
    with _lock:
        is_new = conn.execute(
            "SELECT 1 FROM users WHERE telegram_id=?", (telegram_id,)
        ).fetchone() is None
        conn.execute(
            "INSERT INTO users (telegram_id, username, first_name, created_at) "
            "VALUES (?,?,?,?) "
            "ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username, "
            "first_name=excluded.first_name",
            (telegram_id, username, first_name, int(time.time())),
        )
        conn.commit()
        return is_new


def get_user_lang(telegram_id):
    row = get_conn().execute(
        "SELECT lang FROM users WHERE telegram_id=?", (telegram_id,)
    ).fetchone()
    return row["lang"] if row and row["lang"] else None


def set_user_lang(telegram_id, lang):
    conn = get_conn()
    with _lock:
        conn.execute("UPDATE users SET lang=? WHERE telegram_id=?", (lang, telegram_id))
        conn.commit()


def register_referral(referred_id, referrer_id, target=10, reward_cents=100):
    """Enregistre un filleul unique et crédite chaque palier atteint."""
    if referred_id == referrer_id or target < 1 or reward_cents < 0:
        return {"accepted": False, "rewarded": False, **affiliate_stats(referrer_id, target)}
    conn = get_conn()
    with _lock:
        try:
            conn.execute("BEGIN IMMEDIATE")
            # Le parrain doit être un utilisateur réel déjà enregistré.
            if not conn.execute("SELECT 1 FROM users WHERE telegram_id=?", (referrer_id,)).fetchone():
                conn.rollback()
                return {"accepted": False, "rewarded": False, **affiliate_stats(referrer_id, target)}
            cur = conn.execute(
                "INSERT OR IGNORE INTO referrals (referred_id, referrer_id, created_at) VALUES (?,?,?)",
                (referred_id, referrer_id, int(time.time())),
            )
            if cur.rowcount != 1:
                conn.rollback()
                return {"accepted": False, "rewarded": False, **affiliate_stats(referrer_id, target)}
            count = conn.execute(
                "SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (referrer_id,)
            ).fetchone()[0]
            milestone = count // target
            rewarded = False
            if milestone and count % target == 0:
                reward = conn.execute(
                    "INSERT OR IGNORE INTO affiliate_rewards "
                    "(referrer_id, milestone, amount_cents, created_at) VALUES (?,?,?,?)",
                    (referrer_id, milestone, reward_cents, int(time.time())),
                )
                if reward.rowcount == 1:
                    conn.execute(
                        "INSERT INTO wallets (user_id, balance_cents) VALUES (?,?) "
                        "ON CONFLICT(user_id) DO UPDATE SET balance_cents=balance_cents+excluded.balance_cents",
                        (referrer_id, reward_cents),
                    )
                    rewarded = True
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {"accepted": True, "rewarded": rewarded, **affiliate_stats(referrer_id, target)}


def affiliate_stats(user_id, target=10):
    conn = get_conn()
    count = conn.execute(
        "SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (user_id,)
    ).fetchone()[0]
    row = conn.execute("SELECT balance_cents FROM wallets WHERE user_id=?", (user_id,)).fetchone()
    return {
        "referrals": count,
        "balance_cents": row[0] if row else 0,
        "progress": count % target,
        "remaining": target - (count % target) if count % target else target,
    }


# ---------------- Catalogue ----------------
def list_services(active_only=True):
    q = "SELECT * FROM services"
    if active_only:
        q += " WHERE active=1"
    q += " ORDER BY sort_order, id"
    return [dict(r) for r in get_conn().execute(q).fetchall()]


def get_service(service_id):
    r = get_conn().execute("SELECT * FROM services WHERE id=?", (service_id,)).fetchone()
    return dict(r) if r else None


def list_offers(service_id, active_only=True):
    q = "SELECT * FROM offers WHERE service_id=?"
    if active_only:
        q += " AND active=1"
    q += " ORDER BY id"
    return [dict(r) for r in get_conn().execute(q, (service_id,)).fetchall()]


def get_offer(offer_id):
    r = get_conn().execute("SELECT * FROM offers WHERE id=?", (offer_id,)).fetchone()
    return dict(r) if r else None


def service_total_stock(service_id):
    r = get_conn().execute(
        "SELECT COALESCE(SUM(stock),0) AS s FROM offers WHERE service_id=? AND active=1",
        (service_id,),
    ).fetchone()
    return r["s"]


def update_offer(offer_id, price=None, stock=None, name=None, note=None, active=None):
    conn = get_conn()
    fields, vals = [], []
    if price is not None:
        fields.append("price=?"); vals.append(price)
    if stock is not None:
        fields.append("stock=?"); vals.append(stock)
    if name is not None:
        fields.append("name=?"); vals.append(name)
    if note is not None:
        fields.append("note=?"); vals.append(note)
    if active is not None:
        fields.append("active=?"); vals.append(active)
    if not fields:
        return
    vals.append(offer_id)
    with _lock:
        conn.execute(f"UPDATE offers SET {', '.join(fields)} WHERE id=?", vals)
        conn.commit()


def add_service(name, emoji=""):
    conn = get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO services (name, emoji, sort_order, active) "
            "VALUES (?,?,(SELECT COALESCE(MAX(sort_order),0)+1 FROM services),1)",
            (name, emoji),
        )
        conn.commit()
        return cur.lastrowid


def update_service(service_id, name=None, emoji=None, active=None):
    conn = get_conn()
    fields, vals = [], []
    for field, value in (("name", name), ("emoji", emoji), ("active", active)):
        if value is not None:
            fields.append(f"{field}=?")
            vals.append(value)
    if not fields:
        return False
    vals.append(service_id)
    with _lock:
        cur = conn.execute(f"UPDATE services SET {', '.join(fields)} WHERE id=?", vals)
        conn.commit()
        return cur.rowcount == 1


def archive_service(service_id):
    """Masque un service et toutes ses offres sans casser l'historique."""
    conn = get_conn()
    with _lock:
        conn.execute("UPDATE services SET active=0 WHERE id=?", (service_id,))
        conn.execute("UPDATE offers SET active=0 WHERE service_id=?", (service_id,))
        conn.commit()


def archive_offer(offer_id):
    return update_offer(offer_id, active=0)


def add_offer(service_id, name, price, stock, note=""):
    conn = get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO offers (service_id, name, price, stock, note, active) "
            "VALUES (?,?,?,?,?,1)",
            (service_id, name, price, stock, note),
        )
        conn.commit()
        return cur.lastrowid


def decrement_stock(offer_id, qty):
    conn = get_conn()
    with _lock:
        conn.execute(
            "UPDATE offers SET stock = MAX(0, stock - ?) WHERE id=?", (qty, offer_id)
        )
        conn.commit()


def mark_order_paid(order_id, verify_method):
    """Valide et déstocke une commande une seule fois, dans une transaction."""
    conn = get_conn()
    with _lock:
        row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not row or row["status"] in ("paid", "delivered"):
            return bool(row)
        if row["status"] not in ("awaiting_verification", "pending_payment"):
            return False
        if row["offer_id"]:
            cur = conn.execute(
                "UPDATE offers SET stock=stock-? WHERE id=? AND stock>=?",
                (row["qty"], row["offer_id"], row["qty"]),
            )
            if cur.rowcount != 1:
                conn.rollback()
                return False
        conn.execute(
            "UPDATE orders SET status='paid', verify_method=?, updated_at=? WHERE id=?",
            (verify_method, int(time.time()), order_id),
        )
        conn.commit()
        return True


# ---------------- Commandes ----------------
def create_order(user_id, offer, qty):
    conn = get_conn()
    now = int(time.time())
    unit = offer["price"] or 0
    total = round(unit * qty, 2)
    svc = get_service(offer["service_id"])
    with _lock:
        cur = conn.execute(
            "INSERT INTO orders (user_id, offer_id, service_name, offer_name, qty, "
            "unit_price, total_price, status, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,'pending_payment',?,?)",
            (user_id, offer["id"], svc["name"] if svc else "", offer["name"], qty,
             unit, total, now, now),
        )
        conn.commit()
        return cur.lastrowid


def get_order(order_id):
    r = get_conn().execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    return dict(r) if r else None


def update_order(order_id, **kwargs):
    if not kwargs:
        return
    conn = get_conn()
    kwargs["updated_at"] = int(time.time())
    allowed = {"status", "txid", "verify_method", "delivery_text", "updated_at"}
    unknown = set(kwargs) - allowed
    if unknown:
        raise ValueError(f"Champs de commande interdits: {sorted(unknown)}")
    fields = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [order_id]
    with _lock:
        conn.execute(f"UPDATE orders SET {fields} WHERE id=?", vals)
        conn.commit()


def list_orders(status=None, limit=30):
    q = "SELECT * FROM orders"
    vals = []
    if status:
        q += " WHERE status=?"
        vals.append(status)
    q += " ORDER BY id DESC LIMIT ?"
    vals.append(limit)
    return [dict(r) for r in get_conn().execute(q, vals).fetchall()]


def list_user_orders(user_id, limit=15):
    return [dict(r) for r in get_conn().execute(
        "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()]


def get_setting(key, default=None):
    r = get_conn().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def set_setting(key, value):
    conn = get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )
        conn.commit()
