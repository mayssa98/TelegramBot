"""Rendu HTML/CSS/JS du dashboard administrateur de BlackMarket.

Centralise toute la logique d'affichage du panneau de contrôle avec une
interface moderne, responsive et dynamique (sans rechargement de page).
"""

from __future__ import annotations

import html
import json


def render_dashboard(data: dict) -> str:
    """Génère la page HTML complète du dashboard administrateur."""
    summary = data.get("summary", {})
    alerts = data.get("alerts", [])
    currency = data.get("currency", "USDT")
    shop_name = data.get("shop_name", "BlackMarket")

    # Encodage sécurisé en JSON pour JS
    json_data_str = json.dumps(data, default=str)

    # Alertes HTML
    alerts_html = ""
    if alerts:
        for alert in alerts:
            severity_class = f"alert-{alert.get('severity', 'warning')}"
            alerts_html += f"""
            <div class="alert {severity_class}">
                <span class="alert-icon">⚠️</span>
                <span class="alert-message">{html.escape(alert.get('message', ''))}</span>
            </div>
            """
    else:
        alerts_html = '<div class="empty-state"><p>✅ Aucune alerte active. Tout fonctionne normalement.</p></div>'

    # Vue d'ensemble KPI
    conversion_rate = summary.get("conversion_rate", 0.0)
    kpis_html = f"""
    <div class="kpi-grid">
        <div class="kpi-card">
            <h3>Utilisateurs</h3>
            <div class="kpi-value">{summary.get('users', 0)}</div>
            <div class="kpi-subtext">+{summary.get('new_users_today', 0)} aujourd'hui • {summary.get('users_7d_change_pct', 0):+.1f}% vs 7j précédents</div>
        </div>
        <div class="kpi-card">
            <h3>Commandes</h3>
            <div class="kpi-value">{summary.get('orders', 0)}</div>
            <div class="kpi-subtext">{summary.get('paid_orders', 0)} payées • {summary.get('orders_day_delta', 0):+d} vs hier</div>
        </div>
        <div class="kpi-card">
            <h3>Chiffre d'Affaires</h3>
            <div class="kpi-value">{summary.get('revenue_7d', 0.0):.2f} {currency}</div>
            <div class="kpi-subtext">{summary.get('revenue_7d_change_pct', 0):+.1f}% vs 7j précédents • 30j : {summary.get('revenue_30d', 0.0):.2f} {currency}</div>
        </div>
        <div class="kpi-card">
            <h3>Conversion & Stock</h3>
            <div class="kpi-value">{conversion_rate}%</div>
            <div class="kpi-subtext">{summary.get('available_inventory', 0)} codes dispo • {summary.get('open_tickets', 0)} tickets ouverts</div>
        </div>
    </div>
    """

    # Template HTML brut sans formatage de chaine f-string pour éviter les collisions d'accolades avec JS/CSS
    html_template = """<!doctype html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>__SHOP_NAME__ Control Center</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-main: #07101d;
            --bg-card: #111d2e;
            --bg-nav: #0b1728;
            --border-color: #26364d;
            --text-main: #e8eef8;
            --text-muted: #94a3b8;
            --cyan: #67e8f9;
            --cyan-hover: #22d3ee;
            --btn-primary: #0891b2;
            --btn-secondary: #334155;
            --danger: #ef4444;
            --success: #22c55e;
            --warning: #eab308;
            --info: #3b82f6;
            --purple: #a855f7;
            --pink: #ec4899;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Outfit', system-ui, -apple-system, sans-serif;
            background-color: var(--bg-main);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            overflow-x: hidden;
        }

        /* Navigation latérale desktop */
        aside {
            width: 260px;
            background-color: var(--bg-nav);
            border-right: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            padding: 24px 16px;
            position: fixed;
            height: 100vh;
            z-index: 10;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 32px;
            padding: 0 8px;
        }

        .brand h2 {
            color: var(--cyan);
            font-size: 20px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }

        .brand span {
            font-size: 24px;
        }

        nav {
            display: flex;
            flex-direction: column;
            gap: 8px;
            flex-grow: 1;
        }

        nav button {
            background: transparent;
            border: none;
            color: var(--text-muted);
            padding: 12px 16px;
            border-radius: 8px;
            text-align: left;
            font-family: inherit;
            font-size: 15px;
            font-weight: 500;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 12px;
            transition: all 0.2s ease;
        }

        nav button:hover {
            background-color: rgba(103, 232, 249, 0.05);
            color: var(--text-main);
        }

        nav button.active {
            background-color: var(--btn-primary);
            color: white;
            box-shadow: 0 4px 12px rgba(8, 145, 178, 0.2);
        }

        /* Zone de contenu principal */
        main {
            margin-left: 260px;
            flex-grow: 1;
            padding: 40px;
            max-width: 1400px;
            width: calc(100% - 260px);
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 32px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 20px;
        }

        header h1 {
            font-size: 28px;
            font-weight: 700;
        }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .last-update {
            font-size: 13px;
            color: var(--text-muted);
        }

        .btn {
            padding: 10px 20px;
            border-radius: 8px;
            border: none;
            font-family: inherit;
            font-weight: 600;
            font-size: 14px;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            transition: all 0.2s ease;
            text-decoration: none;
        }

        .btn-primary {
            background-color: var(--btn-primary);
            color: white;
        }

        .btn-primary:hover {
            background-color: var(--cyan-hover);
        }

        .btn-secondary {
            background-color: var(--btn-secondary);
            color: var(--text-main);
            border: 1px solid var(--border-color);
        }

        .btn-secondary:hover {
            background-color: rgba(255, 255, 255, 0.05);
        }

        .btn-danger {
            background-color: var(--danger);
            color: white;
        }

        .btn-danger:hover {
            opacity: 0.9;
        }

        /* Panels */
        .panel {
            display: none;
            animation: fadeIn 0.3s ease-in-out;
        }

        .panel.active {
            display: block;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Grids & Cards */
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 20px;
            margin-bottom: 32px;
        }

        .kpi-card {
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 24px;
            position: relative;
            overflow: hidden;
        }

        .kpi-card::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background-color: var(--cyan);
        }

        .kpi-card h3 {
            font-size: 14px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }

        .kpi-value {
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 8px;
            color: var(--text-main);
        }

        .kpi-subtext {
            font-size: 13px;
            color: var(--text-muted);
        }

        /* Alertes */
        .alerts-section {
            margin-bottom: 32px;
        }

        .alert {
            background-color: rgba(234, 179, 8, 0.1);
            border: 1px solid rgba(234, 179, 8, 0.2);
            border-radius: 8px;
            padding: 14px 18px;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .alert-error {
            background-color: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.2);
        }

        .alert-icon {
            font-size: 18px;
        }

        .alert-message {
            font-size: 14px;
            font-weight: 500;
        }

        /* Tables & Wrappers */
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }

        .table-wrap {
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            overflow: hidden;
            margin-bottom: 24px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }

        th, td {
            padding: 16px 20px;
            border-bottom: 1px solid var(--border-color);
            font-size: 14px;
        }

        th {
            background-color: rgba(255, 255, 255, 0.02);
            font-weight: 600;
            color: var(--text-muted);
            user-select: none;
        }

        tr:last-child td {
            border-bottom: none;
        }

        tr:hover td {
            background-color: rgba(255, 255, 255, 0.01);
        }

        /* Status Badges */
        .badge {
            display: inline-flex;
            align-items: center;
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }

        .badge-pending_payment { background-color: rgba(234, 179, 8, 0.15); color: var(--warning); }
        .badge-awaiting_verification { background-color: rgba(59, 130, 246, 0.15); color: var(--info); }
        .badge-paid, .badge-payment_confirmed { background-color: rgba(34, 197, 94, 0.15); color: var(--success); }
        .badge-delivered { background-color: rgba(168, 85, 247, 0.15); color: var(--purple); }
        .badge-cancelled { background-color: rgba(239, 68, 68, 0.15); color: var(--danger); }
        .badge-expired { background-color: rgba(148, 163, 184, 0.15); color: var(--text-muted); }
        .badge-manual_review { background-color: rgba(249, 115, 22, 0.15); color: #f97316; }
        .badge-refunded { background-color: rgba(236, 72, 153, 0.15); color: var(--pink); }
        .badge-verification_failed { background-color: rgba(239, 68, 68, 0.15); color: var(--danger); }

        /* Forms & Inputs */
        .filters {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            margin-bottom: 20px;
            align-items: center;
        }

        .search-box {
            flex-grow: 1;
            min-width: 240px;
            position: relative;
        }

        .search-box input {
            width: 100%;
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 10px 16px;
            color: var(--text-main);
            font-family: inherit;
            font-size: 14px;
        }

        .search-box input:focus {
            outline: none;
            border-color: var(--btn-primary);
        }

        select, input[type="text"], input[type="number"], textarea {
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 10px 14px;
            color: var(--text-main);
            font-family: inherit;
            font-size: 14px;
        }

        select:focus, input:focus, textarea:focus {
            outline: none;
            border-color: var(--btn-primary);
        }

        /* Modals & Dialogs */
        .modal {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.6);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 100;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s ease;
        }

        .modal.active {
            opacity: 1;
            pointer-events: auto;
        }

        .modal-content {
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            width: 90%;
            max-width: 500px;
            padding: 28px;
            position: relative;
            transform: scale(0.9);
            transition: transform 0.3s ease;
            max-height: 90vh;
            overflow-y: auto;
        }

        .modal.active .modal-content {
            transform: scale(1);
        }

        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }

        .modal-header h3 {
            font-size: 20px;
        }

        .close-btn {
            background: transparent;
            border: none;
            color: var(--text-muted);
            font-size: 24px;
            cursor: pointer;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group label {
            display: block;
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 8px;
            color: var(--text-muted);
        }

        .form-group input, .form-group select, .form-group textarea {
            width: 100%;
        }

        /* Toast Notifications */
        .toast-container {
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 1000;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .toast {
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-left: 4px solid var(--cyan);
            border-radius: 8px;
            padding: 16px 20px;
            color: var(--text-main);
            font-size: 14px;
            font-weight: 500;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
            display: flex;
            align-items: center;
            gap: 12px;
            min-width: 300px;
            max-width: 450px;
            animation: slideIn 0.3s ease-out;
        }

        .toast-error {
            border-left-color: var(--danger);
        }

        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        /* Catalog Layout */
        .catalog-grid {
            display: flex;
            flex-direction: column;
            gap: 24px;
            margin-top: 20px;
        }

        .service-card {
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 24px;
        }

        .service-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 14px;
            margin-bottom: 20px;
        }

        .service-title {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .service-title h3 {
            font-size: 18px;
            font-weight: 600;
        }

        .offers-list {
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .offer-row {
            background-color: rgba(255, 255, 255, 0.01);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 16px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }

        .offer-info {
            flex-grow: 1;
        }

        .offer-name {
            font-weight: 600;
            font-size: 15px;
            margin-bottom: 4px;
        }

        .offer-meta {
            font-size: 13px;
            color: var(--text-muted);
            display: flex;
            gap: 16px;
        }

        .offer-actions {
            display: flex;
            gap: 8px;
        }

        /* Empty state */
        .empty-state {
            text-align: center;
            padding: 40px 20px;
            color: var(--text-muted);
        }

        /* Responsive */
        @media (max-width: 1024px) {
            aside {
                display: none;
            }
            main {
                margin-left: 0;
                width: 100%;
                padding: 24px;
            }
        }

        /* Cryptography / masking values */
        .secret-value {
            font-family: monospace;
            background-color: rgba(255, 255, 255, 0.05);
            padding: 4px 8px;
            border-radius: 4px;
            cursor: pointer;
            user-select: none;
        }

        /* Chat view inside tickets modal */
        .chat-message {
            margin-bottom: 12px;
            padding: 10px 14px;
            border-radius: 8px;
            max-width: 85%;
        }

        .chat-message-client {
            background-color: rgba(59, 130, 246, 0.1);
            border: 1px solid rgba(59, 130, 246, 0.15);
            align-self: flex-start;
            margin-right: auto;
        }

        .chat-message-admin {
            background-color: rgba(8, 145, 178, 0.15);
            border: 1px solid rgba(8, 145, 178, 0.2);
            align-self: flex-end;
            margin-left: auto;
        }

        .chat-time {
            display: block;
            font-size: 10px;
            color: var(--text-muted);
            margin-top: 4px;
            text-align: right;
        }
    </style>
</head>
<body>
    <!-- Barre de navigation latérale -->
    <aside>
        <div class="brand">
            <span>🛡️</span>
            <h2>__SHOP_NAME__</h2>
        </div>
        <nav>
            <button data-tab="overview" class="active">📊 Vue d'ensemble</button>
            <button data-tab="orders">🧾 Commandes</button>
            <button data-tab="catalog">📦 Catalogue</button>
            <button data-tab="inventory">🔐 Inventaire</button>
            <button data-tab="customers">👤 Clients</button>
            <button data-tab="support">🎫 Support</button>
            <button data-tab="activity">📝 Activité</button>
            <button data-tab="settings">⚙️ Paramètres</button>
        </nav>
    </aside>

    <!-- Zone principale -->
    <main>
        <header>
            <div>
                <h1 id="panel-title">Vue d'ensemble</h1>
                <p class="last-update">Dernière mise à jour : <span id="last-update-time">-</span></p>
            </div>
            <div class="header-actions">
                <button class="btn btn-secondary" onclick="refreshDashboardData()">🔄 Actualiser</button>
            </div>
        </header>

        <!-- Toast container -->
        <div class="toast-container" id="toast-container"></div>

        <!-- 1. VUE D'ENSEMBLE -->
        <section id="overview" class="panel active">
            <div class="alerts-section">
                <h2>Alertes système</h2>
                <div style="margin-top:12px;" id="alerts-container">__ALERTS_HTML__</div>
            </div>
            <h2>Statistiques globales</h2>
            <div style="margin-top:12px;" id="kpi-container">__KPIS_HTML__</div>
        </section>

        <!-- 2. GESTION DES COMMANDES -->
        <section id="orders" class="panel">
            <div class="filters">
                <div class="search-box">
                    <input type="text" id="order-search" placeholder="Rechercher par ID, client ou produit..." oninput="filterOrders()">
                </div>
                <select id="order-filter-status" onchange="filterOrders()">
                    <option value="">Tous les statuts</option>
                    <option value="pending_payment">En attente de paiement</option>
                    <option value="awaiting_verification">Vérification en cours</option>
                    <option value="payment_confirmed">Paiement confirmé</option>
                    <option value="preparing_delivery">Préparation</option>
                    <option value="delivered">Livrée</option>
                    <option value="verification_failed">Échec vérification</option>
                    <option value="manual_review">Revue manuelle</option>
                    <option value="cancelled">Annulée</option>
                    <option value="refunded">Remboursée</option>
                    <option value="expired">Expirée</option>
                </select>
            </div>
            <div class="table-wrap">
                <table id="orders-table">
                    <thead>
                        <tr>
                            <th>Commande</th>
                            <th>Date</th>
                            <th>Client</th>
                            <th>Produit</th>
                            <th>Montant</th>
                            <th>Statut</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        <!-- Injecté par JS -->
                    </tbody>
                </table>
            </div>
            <div style="display:flex;justify-content:flex-end;align-items:center;gap:12px;margin-top:16px;">
                <button class="btn btn-secondary" id="orders-prev" onclick="changeOrdersPage(-1)">← Précédent</button>
                <span id="orders-page-label">Page 1</span>
                <button class="btn btn-secondary" id="orders-next" onclick="changeOrdersPage(1)">Suivant →</button>
            </div>
        </section>

        <!-- 3. CATALOGUE -->
        <section id="catalog" class="panel">
            <div class="section-header">
                <h2>Services & Offres</h2>
                <button class="btn btn-primary" onclick="openModal('add-service-modal')">➕ Nouveau service</button>
            </div>
            <div class="catalog-grid" id="catalog-list">
                <!-- Injecté par JS -->
            </div>
        </section>

        <!-- 4. INVENTAIRE -->
        <section id="inventory" class="panel">
            <div class="section-header">
                <h2>Codes & Comptes chiffrés</h2>
                <a class="btn btn-secondary" href="/admin/api/inventory-export">⬇ Export CSV masqué</a>
            </div>
            <div class="catalog-grid" id="inventory-list">
                <!-- Injecté par JS -->
            </div>
            <div class="filters" style="margin-top:24px;">
                <div class="search-box"><input id="inventory-search" placeholder="Rechercher une référence masquée..." oninput="filterInventoryItems()"></div>
                <select id="inventory-filter-status" onchange="filterInventoryItems()">
                    <option value="">Tous les statuts</option>
                    <option value="available">Disponible</option>
                    <option value="reserved">Réservé</option>
                    <option value="delivered">Livré</option>
                    <option value="disabled">Désactivé</option>
                </select>
            </div>
            <div class="table-wrap">
                <table id="inventory-table">
                    <thead><tr><th>Référence</th><th>Offre</th><th>Aperçu masqué</th><th>Statut</th><th>Commande</th><th>Actions</th></tr></thead>
                    <tbody></tbody>
                </table>
            </div>
            <div style="display:flex;justify-content:flex-end;align-items:center;gap:12px;margin-top:16px;">
                <button class="btn btn-secondary" id="inventory-prev" onclick="changeInventoryPage(-1)">← Précédent</button>
                <span id="inventory-page-label">Page 1</span>
                <button class="btn btn-secondary" id="inventory-next" onclick="changeInventoryPage(1)">Suivant →</button>
            </div>
        </section>

        <!-- 5. CLIENTS -->
        <section id="customers" class="panel">
            <div class="filters">
                <div class="search-box">
                    <input type="text" id="customer-search" placeholder="Rechercher par Telegram ID, nom ou prénom..." oninput="filterCustomers()">
                </div>
            </div>
            <div class="table-wrap">
                <table id="customers-table">
                    <thead>
                        <tr>
                            <th>Telegram ID</th>
                            <th>Username</th>
                            <th>Prénom</th>
                            <th>Langue</th>
                            <th>Commandes</th>
                            <th>Total dépensé</th>
                            <th>Statut</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        <!-- Injecté par JS -->
                    </tbody>
                </table>
            </div>
        </section>

        <!-- 6. SUPPORT -->
        <section id="support" class="panel">
            <div class="filters">
                <select id="ticket-filter-status" onchange="filterTickets()">
                    <option value="">Tous les tickets</option>
                    <option value="open">Ouvert</option>
                    <option value="waiting_admin">Attente admin</option>
                    <option value="waiting_customer">Attente client</option>
                    <option value="resolved">Résolu</option>
                    <option value="closed">Fermé</option>
                </select>
            </div>
            <div class="table-wrap">
                <table id="tickets-table">
                    <thead>
                        <tr>
                            <th>Ticket</th>
                            <th>Date</th>
                            <th>Client</th>
                            <th>Catégorie</th>
                            <th>Statut</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        <!-- Injecté par JS -->
                    </tbody>
                </table>
            </div>
        </section>

        <!-- 7. ACTIVITE -->
        <section id="activity" class="panel">
            <h2>Journal d'audit système</h2>
            <div class="table-wrap" style="margin-top:20px;">
                <table id="audit-table">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Action</th>
                            <th>Acteur</th>
                            <th>Détails</th>
                        </tr>
                    </thead>
                    <tbody>
                        <!-- Injecté par JS -->
                    </tbody>
                </table>
            </div>
        </section>

        <!-- 8. CONFIGURATION -->
        <section id="settings" class="panel">
            <h2>Paramètres de la boutique</h2>
            <div class="table-wrap" style="margin-top:20px; padding:28px;">
                <form id="settings-form" onsubmit="saveSettings(event)">
                    <div class="form-group">
                        <label for="shop-name-input">Nom de la boutique</label>
                        <input type="text" id="shop-name-input" name="shop_name" required>
                    </div>
                    <div class="form-group">
                        <label for="currency-input">Devise de la boutique</label>
                        <input type="text" id="currency-input" name="currency" required>
                    </div>
                    <div class="form-group">
                        <label for="low-stock-input">Seuil global de stock faible</label>
                        <input type="number" id="low-stock-input" name="low_stock_threshold" min="1" required>
                    </div>
                    <div class="form-group">
                        <label for="expiry-input">Délai d'expiration des commandes (secondes)</label>
                        <input type="number" id="expiry-input" name="order_expiry_seconds" min="300" required>
                    </div>
                    <div class="form-group">
                        <label for="payment-recipient-input">Identifiant de paiement</label>
                        <input type="text" id="payment-recipient-input" name="payment_recipient">
                    </div>
                    <div class="form-group">
                        <label><input type="checkbox" id="affiliate-enabled-input" name="affiliate_enabled"> Affiliation active</label>
                    </div>
                    <div class="form-group">
                        <label for="affiliate-target-input">Objectif d'affiliation</label>
                        <input type="number" id="affiliate-target-input" name="affiliate_target" min="1">
                    </div>
                    <div class="form-group">
                        <label for="affiliate-reward-input">Récompense d'affiliation (centimes)</label>
                        <input type="number" id="affiliate-reward-input" name="affiliate_reward_cents" min="0">
                    </div>
                    <div class="form-group">
                        <label><input type="checkbox" id="maintenance-enabled-input" name="maintenance_enabled"> Mode maintenance</label>
                    </div>
                    <div class="form-group">
                        <label for="maintenance-message-input">Message de maintenance</label>
                        <textarea id="maintenance-message-input" name="maintenance_message" maxlength="500"></textarea>
                    </div>
                    <div class="form-group"><label>Message d'accueil personnalisé</label><textarea id="welcome-message-input" name="welcome_message"></textarea></div>
                    <div class="form-group"><label>Message d'aide personnalisé</label><textarea id="help-message-input" name="help_message"></textarea></div>
                    <div class="form-group"><label>Conditions</label><textarea id="terms-message-input" name="terms_message"></textarea></div>
                    <div class="form-group"><label>Confidentialité</label><textarea id="privacy-message-input" name="privacy_message"></textarea></div>
                    <div class="form-group"><label>Langues actives (fr,en,ar)</label><input id="active-languages-input" name="active_languages" value="fr,en,ar"></div>
                    <button class="btn btn-primary" type="submit">💾 Enregistrer la configuration</button>
                </form>
            </div>
        </section>
    </main>

    <!-- MODALS -->
    <!-- 1. Ajouter Service -->
    <div class="modal" id="add-service-modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>Ajouter un service</h3>
                <button class="close-btn" onclick="closeModal('add-service-modal')">&times;</button>
            </div>
            <form onsubmit="handleFormSubmit(event, 'add_service')">
                <div class="form-group">
                    <label>Nom du service</label>
                    <input type="text" name="name" required>
                </div>
                <div class="form-group">
                    <label>Emoji</label>
                    <input type="text" name="emoji" placeholder="📦" maxlength="4">
                </div>
                <button class="btn btn-primary" type="submit">Créer</button>
            </form>
        </div>
    </div>

    <!-- 2. Ajouter Offre -->
    <div class="modal" id="add-offer-modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>Ajouter une offre</h3>
                <button class="close-btn" onclick="closeModal('add-offer-modal')">&times;</button>
            </div>
            <form onsubmit="handleFormSubmit(event, 'add_offer')">
                <input type="hidden" name="service_id" id="add-offer-service-id">
                <div class="form-group">
                    <label>Nom de l'offre</label>
                    <input type="text" name="name" required>
                </div>
                <div class="form-group">
                    <label>Prix</label>
                    <input type="number" name="price" step="0.01" min="0" required>
                </div>
                <div class="form-group">
                    <label>Stock affiché (si non géré par codes)</label>
                    <input type="number" name="stock" value="0" min="0">
                </div>
                <div class="form-group">
                    <label>Note / Description</label>
                    <textarea name="note"></textarea>
                </div>
                <div class="form-group"><label>Description détaillée</label><textarea name="description"></textarea></div>
                <div class="form-group"><label>Délai de livraison</label><input name="delivery_delay" value="Instantané après confirmation"></div>
                <div class="form-group"><label>Seuil de stock faible</label><input type="number" name="low_stock_threshold" value="5" min="0"></div>
                <div class="form-group"><label><input type="checkbox" name="auto_delivery" checked> Livraison automatique</label></div>
                <button class="btn btn-primary" type="submit">Créer l'offre</button>
            </form>
        </div>
    </div>

    <div class="modal" id="edit-offer-modal">
        <div class="modal-content">
            <div class="modal-header"><h3>Modifier l'offre</h3><button class="close-btn" onclick="closeModal('edit-offer-modal')">&times;</button></div>
            <form onsubmit="handleFormSubmit(event, 'update_offer')">
                <input type="hidden" name="offer_id" id="edit-offer-id">
                <div class="form-group"><label>Nom</label><input name="name" id="edit-offer-name" required></div>
                <div class="form-group"><label>Description</label><textarea name="description" id="edit-offer-description"></textarea></div>
                <div class="form-group"><label>Note</label><textarea name="note" id="edit-offer-note"></textarea></div>
                <div class="form-group"><label>Prix</label><input type="number" step="0.01" min="0" name="price" id="edit-offer-price" required></div>
                <div class="form-group"><label>Stock affiché</label><input type="number" min="0" name="stock" id="edit-offer-stock" required></div>
                <div class="form-group"><label>Ordre</label><input type="number" min="0" name="sort_order" id="edit-offer-sort"></div>
                <div class="form-group"><label>Délai de livraison</label><input name="delivery_delay" id="edit-offer-delay"></div>
                <div class="form-group"><label>Seuil de stock faible</label><input type="number" min="0" name="low_stock_threshold" id="edit-offer-threshold"></div>
                <div class="form-group"><label><input type="checkbox" name="auto_delivery" id="edit-offer-auto"> Livraison automatique</label></div>
                <button class="btn btn-primary" type="submit">Enregistrer</button>
            </form>
        </div>
    </div>

    <!-- 3. Ajouter Inventaire -->
    <div class="modal" id="add-inventory-modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>Ajouter du stock chiffré</h3>
                <button class="close-btn" onclick="closeModal('add-inventory-modal')">&times;</button>
            </div>
            <form onsubmit="handleFormSubmit(event, 'add_inventory')">
                <input type="hidden" name="offer_id" id="add-inventory-offer-id">
                <div class="form-group">
                    <label>Contenus à chiffrer (un par ligne)</label>
                    <textarea name="items" placeholder="code1&#10;compte:passe2" required style="min-height: 150px;"></textarea>
                </div>
                <button class="btn btn-primary" type="submit">🔒 Chiffrer & Ajouter</button>
            </form>
        </div>
    </div>

    <!-- 4. Fiche Commande -->
    <div class="modal" id="order-detail-modal">
        <div class="modal-content" style="max-width:600px;">
            <div class="modal-header">
                <h3>Détail de la commande</h3>
                <button class="close-btn" onclick="closeModal('order-detail-modal')">&times;</button>
            </div>
            <div id="order-detail-body">
                <!-- Injecté par JS -->
            </div>
        </div>
    </div>

    <!-- 5. Ticket Conversation -->
    <div class="modal" id="customer-detail-modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>Fiche client</h3>
                <button class="close-btn" onclick="closeModal('customer-detail-modal')">&times;</button>
            </div>
            <div id="customer-detail-body"></div>
        </div>
    </div>

    <div class="modal" id="ticket-modal">
        <div class="modal-content" style="max-width:700px;">
            <div class="modal-header">
                <h3>Ticket #<span id="ticket-title-id"></span></h3>
                <button class="close-btn" onclick="closeModal('ticket-modal')">&times;</button>
            </div>
            <div id="ticket-chat-area" style="max-height: 350px; overflow-y: auto; margin-bottom: 20px; padding: 10px; background: rgba(0,0,0,0.2); border-radius: 8px; display: flex; flex-direction: column;">
                <!-- Injecté par JS -->
            </div>
            <form onsubmit="replyToTicket(event)">
                <input type="hidden" id="ticket-reply-id">
                <div class="form-group">
                    <textarea id="ticket-reply-message" placeholder="Votre réponse au client..." required style="min-height: 80px;"></textarea>
                </div>
                <button class="btn btn-primary" type="submit">✉️ Répondre & Transmettre</button>
            </form>
        </div>
    </div>

    <!-- INJECTION DES DONNEES DANS LE SCRIPT -->
    <script>
        let dashboardData = __JSON_DATA__;
        let ordersPagination = { page: 1, pages: 1, total: 0 };
        let inventoryPagination = { page: 1, pages: 1, total: 0 };
        let orderFilterTimer;
        let inventoryFilterTimer;

        // Au chargement de la page
        document.addEventListener("DOMContentLoaded", () => {
            setupTabNavigation();
            refreshUI();
            refreshDashboardData();
        });

        function setupTabNavigation() {
            const buttons = document.querySelectorAll("nav button");
            const panels = document.querySelectorAll(".panel");
            const title = document.getElementById("panel-title");

            buttons.forEach(btn => {
                btn.addEventListener("click", () => {
                    buttons.forEach(b => b.classList.remove("active"));
                    panels.forEach(p => p.classList.remove("active"));

                    btn.classList.add("active");
                    const tabId = btn.dataset.tab;
                    document.getElementById(tabId).classList.add("active");
                    title.textContent = btn.textContent.substring(3); // Enlever l'émoji
                    location.hash = tabId;
                });
            });

            // Gérer le hash initial
            if (location.hash) {
                const tabId = location.hash.substring(1);
                const button = document.querySelector(`nav button[data-tab="${tabId}"]`);
                if (button) button.click();
            }
        }

        function showToast(message, type = "success") {
            const container = document.getElementById("toast-container");
            const toast = document.createElement("div");
            toast.className = `toast toast-${type}`;
            toast.innerHTML = `<span>${type === 'success' ? '✅' : '⚠️'}</span> <span>${message}</span>`;
            container.appendChild(toast);
            setTimeout(() => toast.remove(), 4000);
        }

        function openModal(id) {
            document.getElementById(id).classList.add("active");
        }

        function closeModal(id) {
            document.getElementById(id).classList.remove("active");
        }

        function formatDateTime(unixTimestamp) {
            if (!unixTimestamp) return "-";
            const date = new Date(unixTimestamp * 1000);
            return date.toLocaleString('fr-FR');
        }

        function refreshUI() {
            document.getElementById("last-update-time").textContent = new Date().toLocaleTimeString();

            // Vue d'ensemble KPI
            renderAlerts();
            renderKPIs();

            // Tables & catalogue
            renderOrdersTable();
            renderCatalog();
            renderInventory();
            renderInventoryItems();
            renderCustomersTable();
            renderTicketsTable();
            renderAuditTable();
            fillSettingsForm();
        }

        function renderAlerts() {
            const container = document.getElementById("alerts-container");
            if (!dashboardData.alerts || dashboardData.alerts.length === 0) {
                container.innerHTML = '<div class="empty-state"><p>✅ Aucune alerte active. Tout fonctionne normalement.</p></div>';
                return;
            }
            container.innerHTML = dashboardData.alerts.map(alert => `
                <div class="alert alert-${alert.severity || 'warning'}">
                    <span class="alert-icon">⚠️</span>
                    <span class="alert-message">${alert.message}</span>
                </div>
            `).join("");
        }

        function renderKPIs() {
            const container = document.getElementById("kpi-container");
            const s = dashboardData.summary || {};
            const currency = dashboardData.currency || "USDT";
            container.innerHTML = `
                <div class="kpi-grid">
                    <div class="kpi-card">
                        <h3>Utilisateurs</h3>
                        <div class="kpi-value">${s.users || 0}</div>
                        <div class="kpi-subtext">+${s.new_users_today || 0} aujourd'hui • +${s.new_users_7d || 0} sur 7j</div>
                    </div>
                    <div class="kpi-card">
                        <h3>Commandes</h3>
                        <div class="kpi-value">${s.orders || 0}</div>
                        <div class="kpi-subtext">${s.paid_orders || 0} payées • ${s.pending_orders || 0} en attente</div>
                    </div>
                    <div class="kpi-card">
                        <h3>Chiffre d'Affaires</h3>
                        <div class="kpi-value">${(s.revenue_7d || 0).toFixed(2)} ${currency}</div>
                        <div class="kpi-subtext">Aujourd'hui : ${(s.revenue_today || 0).toFixed(2)} ${currency} • 30j : ${(s.revenue_30d || 0).toFixed(2)} ${currency}</div>
                    </div>
                    <div class="kpi-card">
                        <h3>Conversion & Stock</h3>
                        <div class="kpi-value">${s.conversion_rate || 0}%</div>
                        <div class="kpi-subtext">${s.available_inventory || 0} codes dispo • ${s.open_tickets || 0} tickets ouverts</div>
                    </div>
                </div>
            `;
        }

        function renderOrdersTable() {
            const tbody = document.querySelector("#orders-table tbody");
            tbody.innerHTML = "";

            if (!dashboardData.orders || dashboardData.orders.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="empty-state">Aucune commande disponible.</td></tr>';
                return;
            }

            dashboardData.orders.forEach(order => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td>#${order.id}</td>
                    <td>${formatDateTime(order.created_at)}</td>
                    <td><code>${order.user_id}</code></td>
                    <td>${order.service_name} — ${order.offer_name}</td>
                    <td>${order.total_price.toFixed(2)} ${dashboardData.currency}</td>
                    <td><span class="badge badge-${order.status}">${order.status}</span></td>
                    <td><button class="btn btn-secondary" style="padding:6px 12px; font-size:12px;" onclick="viewOrderDetail(${order.id})">🔍 Détails</button></td>
                `;
                tbody.appendChild(tr);
            });
        }

        function renderCustomersTable() {
            const tbody = document.querySelector("#customers-table tbody");
            tbody.innerHTML = "";

            if (!dashboardData.users || dashboardData.users.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" class="empty-state">Aucun client enregistré.</td></tr>';
                return;
            }

            dashboardData.users.forEach(user => {
                const tr = document.createElement("tr");
                const banLabel = user.banned ? "Débannir" : "Bannir";
                const banClass = user.banned ? "btn-primary" : "btn-danger";
                tr.innerHTML = `
                    <td><code>${user.telegram_id}</code></td>
                    <td>@${user.username || '—'}</td>
                    <td>${user.first_name || '—'}</td>
                    <td>${user.lang || 'fr'}</td>
                    <td>${user.order_count || 0}</td>
                    <td>${(user.total_spent || user.total_paid || 0).toFixed(2)} ${dashboardData.currency}</td>
                    <td><span class="badge badge-${user.banned ? 'cancelled' : 'paid'}">${user.banned ? 'Banni' : 'Actif'}</span></td>
                    <td>
                        <button class="btn btn-secondary" style="padding:6px 12px;font-size:12px;" onclick="viewCustomer(${user.telegram_id})">🔍 Profil</button>
                        <button class="btn ${banClass}" style="padding:6px 12px;font-size:12px;" onclick="toggleBanUser(${user.telegram_id}, ${user.banned ? 0 : 1})">${banLabel}</button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }

        function renderCatalog() {
            const list = document.getElementById("catalog-list");
            list.innerHTML = "";

            if (!dashboardData.services || dashboardData.services.length === 0) {
                list.innerHTML = '<div class="empty-state">Aucun service créé.</div>';
                return;
            }

            dashboardData.services.forEach(service => {
                const card = document.createElement("div");
                card.className = "service-card";
                card.innerHTML = `
                    <div class="service-header">
                        <div class="service-title">
                            <span style="font-size:24px;">${service.emoji}</span>
                            <h3>${service.name}</h3>
                        </div>
                        <div style="display:flex; gap:8px;">
                            <button class="btn btn-secondary" onclick="openAddOfferModal(${service.id})">➕ Offre</button>
                            <button class="btn btn-secondary" onclick="toggleService(${service.id}, ${service.active})">${service.active ? '⏸ Désactiver' : '▶️ Activer'}</button>
                        </div>
                    </div>
                    <div class="offers-list" id="offers-for-service-${service.id}"></div>
                `;
                list.appendChild(card);

                const offersListContainer = card.querySelector(`#offers-for-service-${service.id}`);

                if (service.offers && service.offers.length > 0) {
                    service.offers.forEach(offer => {
                        const row = document.createElement("div");
                        row.className = "offer-row";
                        row.innerHTML = `
                            <div class="offer-info">
                                <div class="offer-name">${offer.name}</div>
                                <div class="offer-meta">
                                    <span>💵 Prix : ${offer.price !== null ? offer.price.toFixed(2) : '—'} ${dashboardData.currency}</span>
                                    <span>📦 Stock : ${offer.stock}</span>
                                    <span>📝 Note : ${offer.note || '—'}</span>
                                </div>
                            </div>
                            <div class="offer-actions">
                                <button class="btn btn-secondary" style="padding:6px 12px; font-size:12px;" onclick="openEditOfferModal(${offer.id})">✏️ Éditer</button>
                                <button class="btn btn-secondary" style="padding:6px 12px; font-size:12px;" onclick="toggleOffer(${offer.id}, ${offer.active})">${offer.active ? '⏸' : '▶️'}</button>
                            </div>
                        `;
                        offersListContainer.appendChild(row);
                    });
                } else {
                    offersListContainer.innerHTML = '<div style="color:var(--text-muted); font-size:13px; text-align:center;">Aucune offre pour ce service.</div>';
                }
            });
        }

        function renderInventory() {
            const list = document.getElementById("inventory-list");
            list.innerHTML = "";

            let hasOffers = false;
            dashboardData.services.forEach(service => {
                if (service.offers && service.offers.length > 0) {
                    hasOffers = true;
                    const card = document.createElement("div");
                    card.className = "service-card";
                    card.innerHTML = `
                        <div class="service-header">
                            <div class="service-title">
                                <span style="font-size:24px;">${service.emoji}</span>
                                <h3>${service.name}</h3>
                            </div>
                        </div>
                        <div class="offers-list" id="inv-offers-for-service-${service.id}"></div>
                    `;
                    list.appendChild(card);

                    const offersListContainer = card.querySelector(`#inv-offers-for-service-${service.id}`);
                    service.offers.forEach(offer => {
                        const row = document.createElement("div");
                        row.className = "offer-row";
                        row.innerHTML = `
                            <div class="offer-info">
                                <div class="offer-name">${offer.name}</div>
                                <div class="offer-meta">
                                    <span>📦 Dispo : ${offer.stock}</span>
                                </div>
                            </div>
                            <div class="offer-actions">
                                <button class="btn btn-primary" style="padding:6px 12px; font-size:12px;" onclick="openAddInventoryModal(${offer.id})">🔐 Ajouter des codes</button>
                            </div>
                        `;
                        offersListContainer.appendChild(row);
                    });
                }
            });

            if (!hasOffers) {
                list.innerHTML = '<div class="empty-state">Créez d\'abord des offres dans le catalogue.</div>';
            }
        }

        function renderInventoryItems() {
            const tbody = document.querySelector("#inventory-table tbody");
            tbody.innerHTML = "";
            const items = dashboardData.inventory || [];
            if (!items.length) {
                tbody.innerHTML = '<tr><td colspan="6" class="empty-state">Aucune référence pour ces filtres.</td></tr>';
                return;
            }
            items.forEach(item => {
                const tr = document.createElement("tr");
                const linkedOrder = item.reserved_order_id || item.delivered_order_id || "—";
                const canToggle = ["available", "disabled"].includes(item.status);
                tr.innerHTML = `
                    <td><code>#${item.reference_id}</code></td>
                    <td>#${item.offer_id}</td>
                    <td><code>${escapeHtml(item.masked_preview || "***")}</code></td>
                    <td><span class="badge badge-${escapeHtml(item.status)}">${escapeHtml(item.status)}</span></td>
                    <td>${linkedOrder === "—" ? linkedOrder : "#" + linkedOrder}</td>
                    <td>
                        <button class="btn btn-secondary" style="padding:6px 10px" onclick="revealInventory(${item.reference_id}, this)">👁 Révéler</button>
                        ${canToggle ? `<button class="btn ${item.status === 'disabled' ? 'btn-primary' : 'btn-danger'}" style="padding:6px 10px" onclick="toggleInventory(${item.reference_id}, ${item.status === 'disabled' ? 0 : 1})">${item.status === 'disabled' ? 'Activer' : 'Désactiver'}</button>` : ''}
                    </td>`;
                tbody.appendChild(tr);
            });
        }

        function filterInventoryItems() {
            clearTimeout(inventoryFilterTimer);
            inventoryPagination.page = 1;
            inventoryFilterTimer = setTimeout(refreshDashboardData, 250);
        }

        async function changeInventoryPage(delta) {
            const next = Math.max(1, Math.min(inventoryPagination.pages || 1, inventoryPagination.page + delta));
            if (next === inventoryPagination.page) return;
            inventoryPagination.page = next;
            await refreshDashboardData();
        }

        function updateInventoryPagination() {
            const pages = inventoryPagination.pages || 1;
            document.getElementById("inventory-page-label").textContent = `Page ${inventoryPagination.page} / ${pages} (${inventoryPagination.total || 0})`;
            document.getElementById("inventory-prev").disabled = inventoryPagination.page <= 1;
            document.getElementById("inventory-next").disabled = inventoryPagination.page >= pages;
        }

        async function revealInventory(itemId, button) {
            if (!confirm("Afficher temporairement le contenu complet de cette référence ?")) return;
            const params = new URLSearchParams({ action: "reveal_inventory", inventory_id: itemId });
            try {
                const res = await fetch("/admin", {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: params
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || "Révélation impossible");
                const original = button.textContent;
                button.textContent = data.value;
                button.disabled = true;
                setTimeout(() => { button.textContent = original; button.disabled = false; }, 15000);
            } catch (err) {
                showToast(err.message || "Erreur réseau", "error");
            }
        }

        async function toggleInventory(itemId, disabled) {
            if (!confirm("Confirmer le changement d'état de cette référence ?")) return;
            const params = new URLSearchParams({ action: "toggle_inventory", inventory_id: itemId, disabled });
            try {
                const res = await fetch("/admin", {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: params
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || "Action impossible");
                showToast("Inventaire mis à jour");
                await refreshDashboardData();
            } catch (err) {
                showToast(err.message || "Erreur réseau", "error");
            }
        }

        function renderTicketsTable() {
            const tbody = document.querySelector("#tickets-table tbody");
            tbody.innerHTML = "";

            if (!dashboardData.tickets || dashboardData.tickets.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="empty-state">Aucun ticket support.</td></tr>';
                return;
            }

            dashboardData.tickets.forEach(ticket => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td>#${ticket.id}</td>
                    <td>${formatDateTime(ticket.created_at)}</td>
                    <td><code>${ticket.user_id}</code></td>
                    <td>${ticket.category || 'Général'}</td>
                    <td><span class="badge badge-${ticket.status}">${ticket.status}</span></td>
                    <td>
                        <button class="btn btn-secondary" style="padding:6px 12px; font-size:12px;" onclick="viewTicket(${ticket.id})">💬 Ouvrir</button>
                        ${ticket.status !== 'closed' ? `<button class="btn btn-danger" style="padding:6px 12px; font-size:12px;" onclick="closeTicket(${ticket.id})">Fermer</button>` : ''}
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }

        function renderAuditTable() {
            const tbody = document.querySelector("#audit-table tbody");
            tbody.innerHTML = "";

            if (!dashboardData.audits || dashboardData.audits.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" class="empty-state">Aucun événement d\'audit disponible.</td></tr>';
                return;
            }

            dashboardData.audits.forEach(audit => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td>${formatDateTime(audit.created_at)}</td>
                    <td><code>${audit.action}</code></td>
                    <td>${audit.actor_id || 'système'}</td>
                    <td><code>${JSON.stringify(audit.details || {})}</code></td>
                `;
                tbody.appendChild(tr);
            });
        }

        function fillSettingsForm() {
            document.getElementById("shop-name-input").value = dashboardData.shop_name || "BlackMarket";
            document.getElementById("currency-input").value = dashboardData.currency || "USDT";
            document.getElementById("low-stock-input").value = dashboardData.low_stock_threshold || 5;
            document.getElementById("expiry-input").value = dashboardData.order_expiry_seconds || 1800;
            document.getElementById("payment-recipient-input").value = dashboardData.payment_recipient || "";
            document.getElementById("affiliate-enabled-input").checked = dashboardData.affiliate_enabled !== false;
            document.getElementById("affiliate-target-input").value = dashboardData.affiliate_target || 10;
            document.getElementById("affiliate-reward-input").value = dashboardData.affiliate_reward_cents || 100;
            document.getElementById("maintenance-enabled-input").checked = dashboardData.maintenance_enabled === true;
            document.getElementById("maintenance-message-input").value = dashboardData.maintenance_message || "";
            document.getElementById("welcome-message-input").value = dashboardData.welcome_message || "";
            document.getElementById("help-message-input").value = dashboardData.help_message || "";
            document.getElementById("terms-message-input").value = dashboardData.terms_message || "";
            document.getElementById("privacy-message-input").value = dashboardData.privacy_message || "";
            document.getElementById("active-languages-input").value = dashboardData.active_languages || "fr,en,ar";
        }

        // Actions Ajax
        async function refreshDashboardData() {
            try {
                const status = document.getElementById("order-filter-status")?.value || "";
                const search = document.getElementById("order-search")?.value || "";
                const query = new URLSearchParams({ page: ordersPagination.page, per_page: 25 });
                if (status) query.set("status", status);
                if (search) query.set("search", search);
                const inventoryQuery = new URLSearchParams({ page: inventoryPagination.page, per_page: 25 });
                const inventoryStatus = document.getElementById("inventory-filter-status")?.value || "";
                const inventorySearch = document.getElementById("inventory-search")?.value || "";
                if (inventoryStatus) inventoryQuery.set("status", inventoryStatus);
                if (inventorySearch) inventoryQuery.set("search", inventorySearch);
                const [res, ordersRes, customersRes, ticketsRes, inventoryRes] = await Promise.all([
                    fetch("/admin/api/data"),
                    fetch("/admin/api/orders?" + query.toString()),
                    fetch("/admin/api/customers?per_page=100"),
                    fetch("/admin/api/tickets?per_page=100"),
                    fetch("/admin/api/inventory?" + inventoryQuery.toString())
                ]);
                if (res.ok && ordersRes.ok && customersRes.ok && ticketsRes.ok && inventoryRes.ok) {
                    dashboardData = await res.json();
                    const orderData = await ordersRes.json();
                    const customerData = await customersRes.json();
                    const ticketData = await ticketsRes.json();
                    const inventoryData = await inventoryRes.json();
                    dashboardData.orders = orderData.items;
                    dashboardData.users = customerData.items;
                    dashboardData.tickets = ticketData.items;
                    dashboardData.inventory = inventoryData.items;
                    inventoryPagination = inventoryData;
                    ordersPagination = orderData;
                    refreshUI();
                    updateOrdersPagination();
                    updateInventoryPagination();
                    showToast("Données actualisées");
                } else {
                    showToast("Échec de l'actualisation des données", "error");
                }
            } catch (err) {
                showToast("Erreur réseau lors de l'actualisation", "error");
            }
        }

        async function changeOrdersPage(delta) {
            const next = Math.max(1, Math.min(ordersPagination.pages || 1, ordersPagination.page + delta));
            if (next === ordersPagination.page) return;
            ordersPagination.page = next;
            await refreshDashboardData();
        }

        function updateOrdersPagination() {
            const pages = ordersPagination.pages || 1;
            document.getElementById("orders-page-label").textContent = `Page ${ordersPagination.page} / ${pages} (${ordersPagination.total || 0})`;
            document.getElementById("orders-prev").disabled = ordersPagination.page <= 1;
            document.getElementById("orders-next").disabled = ordersPagination.page >= pages;
        }

        async function handleFormSubmit(event, action) {
            event.preventDefault();
            const form = event.target;
            const formData = new FormData(form);
            const params = new URLSearchParams();
            params.append("action", action);
            for (const pair of formData.entries()) {
                params.append(pair[0], pair[1]);
            }

            try {
                const res = await fetch("/admin", {
                    method: "POST",
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: params
                });
                if (res.ok) {
                    showToast("Opération réussie");
                    closeModal(form.closest('.modal').id);
                    form.reset();
                    await refreshDashboardData();
                } else {
                    const err = await res.json();
                    showToast(err.error || "Erreur de traitement", "error");
                }
            } catch (err) {
                showToast("Erreur réseau", "error");
            }
        }

        async function toggleBanUser(userId, banned) {
            if (!confirm(`Voulez-vous vraiment ${banned ? 'bannir' : 'débannir'} l'utilisateur ${userId} ?`)) return;
            const params = new URLSearchParams();
            params.append("action", "toggle_ban");
            params.append("user_id", userId);
            params.append("banned", banned);

            try {
                const res = await fetch("/admin", {
                    method: "POST",
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: params
                });
                if (res.ok) {
                    showToast("Statut utilisateur mis à jour");
                    await refreshDashboardData();
                }
            } catch (err) {
                showToast("Erreur réseau", "error");
            }
        }

        async function toggleService(serviceId, active) {
            const params = new URLSearchParams();
            params.append("action", "toggle_service");
            params.append("service_id", serviceId);

            try {
                const res = await fetch("/admin", {
                    method: "POST",
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: params
                });
                if (res.ok) {
                    showToast("Statut service mis à jour");
                    await refreshDashboardData();
                }
            } catch (err) {
                showToast("Erreur réseau", "error");
            }
        }

        function openAddOfferModal(serviceId) {
            document.getElementById("add-offer-service-id").value = serviceId;
            openModal("add-offer-modal");
        }

        function openEditOfferModal(offerId) {
            const offer = (dashboardData.services || [])
                .flatMap(service => service.offers || [])
                .find(item => item.id === offerId);
            if (!offer) {
                showToast("Offre introuvable", "error");
                return;
            }
            document.getElementById("edit-offer-id").value = offer.id;
            document.getElementById("edit-offer-name").value = offer.name || "";
            document.getElementById("edit-offer-description").value = offer.description || "";
            document.getElementById("edit-offer-note").value = offer.note || "";
            document.getElementById("edit-offer-price").value = offer.price ?? 0;
            document.getElementById("edit-offer-stock").value = offer.stock ?? 0;
            document.getElementById("edit-offer-sort").value = offer.sort_order ?? 0;
            document.getElementById("edit-offer-delay").value = offer.delivery_delay || "";
            document.getElementById("edit-offer-threshold").value = offer.low_stock_threshold ?? 5;
            document.getElementById("edit-offer-auto").checked = offer.auto_delivery !== false;
            openModal("edit-offer-modal");
        }

        function openAddInventoryModal(offerId) {
            document.getElementById("add-inventory-offer-id").value = offerId;
            openModal("add-inventory-modal");
        }

        function escapeHtml(value) {
            const node = document.createElement("div");
            node.textContent = value == null ? "" : String(value);
            return node.innerHTML;
        }

        async function viewCustomer(userId) {
            try {
                const res = await fetch(`/admin/api/customers?user_id=${userId}`);
                const customer = await res.json();
                if (!res.ok) throw new Error(customer.error || "Client introuvable");
                const orders = (customer.orders || []).map(order =>
                    `<li>#${order.id} — ${escapeHtml(order.offer_name || '')} — ${escapeHtml(order.status || '')}</li>`
                ).join("") || "<li>Aucune commande</li>";
                const tickets = (customer.tickets || []).map(ticket =>
                    `<li>#${ticket.id} — ${escapeHtml(ticket.category || 'other')} — ${escapeHtml(ticket.status || '')}</li>`
                ).join("") || "<li>Aucun ticket</li>";
                document.getElementById("customer-detail-body").innerHTML = `
                    <div class="detail-grid">
                        <div><strong>Telegram ID :</strong> <code>${customer.telegram_id}</code></div>
                        <div><strong>Username :</strong> ${escapeHtml(customer.username ? '@' + customer.username : '—')}</div>
                        <div><strong>Prénom :</strong> ${escapeHtml(customer.first_name || '—')}</div>
                        <div><strong>Langue :</strong> ${escapeHtml(customer.lang || 'fr')}</div>
                        <div><strong>Commandes :</strong> ${customer.order_count || 0}</div>
                        <div><strong>Payées :</strong> ${customer.paid_order_count || 0}</div>
                        <div><strong>Total dépensé :</strong> ${(customer.total_spent || 0).toFixed(2)} ${escapeHtml(dashboardData.currency)}</div>
                        <div><strong>Filleuls :</strong> ${customer.referral_count || 0}</div>
                    </div>
                    <h4>Commandes récentes</h4><ul>${orders}</ul>
                    <h4>Tickets</h4><ul>${tickets}</ul>`;
                openModal("customer-detail-modal");
            } catch (err) {
                showToast(err.message || "Erreur réseau", "error");
            }
        }

        async function viewOrderDetail(orderId) {
            const order = dashboardData.orders.find(o => o.id === orderId);
            if (!order) return;

            const body = document.getElementById("order-detail-body");
            body.innerHTML = `
                <div style="display:flex; flex-direction:column; gap:16px;">
                    <div><strong>ID Commande:</strong> #${order.id}</div>
                    <div><strong>Date:</strong> ${formatDateTime(order.created_at)}</div>
                    <div><strong>Client (Telegram ID):</strong> <code>${order.user_id}</code></div>
                    <div><strong>Produit:</strong> ${order.service_name} — ${order.offer_name}</div>
                    <div><strong>Total:</strong> ${order.total_price.toFixed(2)} ${dashboardData.currency}</div>
                    <div><strong>Statut:</strong> <span class="badge badge-${order.status}">${order.status}</span></div>
                    <div><strong>Identifiant Transaction (TXID):</strong> <code>${order.txid || '—'}</code></div>
                    <div><strong>Méthode de vérification:</strong> <code>${order.verify_method || '—'}</code></div>
                    <div><strong>Notes Administrateur:</strong> <textarea style="width:100%; margin-top:8px;" id="order-admin-note" rows="3" placeholder="Notes optionnelles...">${order.admin_note || ''}</textarea></div>
                    <div style="display:flex; gap:12px; margin-top:12px;">
                        ${order.status === 'awaiting_verification' || order.status === 'pending_payment' || order.status === 'manual_review' ? `
                            <button class="btn btn-primary" onclick="confirmPaymentManual(${order.id})">✅ Confirmer paiement</button>
                        ` : ''}
                        ${order.status !== 'cancelled' && order.status !== 'refunded' ? `
                            <button class="btn btn-danger" onclick="cancelOrder(${order.id})">❌ Annuler commande</button>
                        ` : ''}
                        ${['awaiting_verification', 'verification_failed', 'manual_review'].includes(order.status) ? `
                            <button class="btn btn-secondary" onclick="orderAction('reset_order', ${order.id})">↩️ Remettre en attente</button>
                        ` : ''}
                        ${['paid', 'payment_confirmed', 'preparing_delivery', 'delivered', 'manual_review'].includes(order.status) ? `
                            <button class="btn btn-danger" onclick="orderAction('refund_order', ${order.id}, true)">💸 Rembourser</button>
                        ` : ''}
                        ${order.status === 'delivered' ? `
                            <button class="btn btn-secondary" onclick="orderAction('resend_delivery', ${order.id})">📨 Renvoyer la livraison</button>
                        ` : ''}
                        <button class="btn btn-secondary" onclick="messageCustomer(${order.id})">💬 Écrire au client</button>
                        <button class="btn btn-secondary" onclick="saveOrderNote(${order.id})">💾 Enregistrer Notes</button>
                    </div>
                </div>
            `;
            openModal("order-detail-modal");
        }

        async function confirmPaymentManual(orderId) {
            if (!confirm("Confirmer manuellement le paiement de cette commande ?")) return;
            const params = new URLSearchParams();
            params.append("action", "confirm_payment");
            params.append("order_id", orderId);

            try {
                const res = await fetch("/admin", {
                    method: "POST",
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: params
                });
                if (res.ok) {
                    showToast("Paiement validé");
                    closeModal("order-detail-modal");
                    await refreshDashboardData();
                }
            } catch (err) {
                showToast("Erreur réseau", "error");
            }
        }

        async function cancelOrder(orderId) {
            const reason = prompt("Raison de l'annulation :");
            if (reason === null) return;
            const params = new URLSearchParams();
            params.append("action", "cancel_order");
            params.append("order_id", orderId);
            params.append("reason", reason);

            try {
                const res = await fetch("/admin", {
                    method: "POST",
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: params
                });
                if (res.ok) {
                    showToast("Commande annulée");
                    closeModal("order-detail-modal");
                    await refreshDashboardData();
                }
            } catch (err) {
                showToast("Erreur réseau", "error");
            }
        }

        async function orderAction(action, orderId, askReason = false) {
            if (!confirm("Confirmer cette action sur la commande #" + orderId + " ?")) return;
            const params = new URLSearchParams({ action, order_id: orderId });
            if (askReason) params.append("reason", prompt("Motif (optionnel) :") || "");
            try {
                const res = await fetch("/admin", {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: params
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || "Action impossible");
                showToast("Action effectuée avec succès");
                closeModal("order-detail-modal");
                await refreshDashboardData();
            } catch (err) {
                showToast(err.message || "Erreur réseau", "error");
            }
        }

        async function messageCustomer(orderId) {
            const message = prompt("Message à envoyer au client :");
            if (!message) return;
            const params = new URLSearchParams({ action: "message_customer", order_id: orderId, message });
            try {
                const res = await fetch("/admin", {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: params
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || "Envoi impossible");
                showToast("Message envoyé au client");
            } catch (err) {
                showToast(err.message || "Erreur réseau", "error");
            }
        }

        async function saveOrderNote(orderId) {
            const note = document.getElementById("order-admin-note").value;
            const params = new URLSearchParams();
            params.append("action", "save_order_note");
            params.append("order_id", orderId);
            params.append("note", note);

            try {
                const res = await fetch("/admin", {
                    method: "POST",
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: params
                });
                if (res.ok) {
                    showToast("Notes enregistrées");
                    closeModal("order-detail-modal");
                    await refreshDashboardData();
                }
            } catch (err) {
                showToast("Erreur réseau", "error");
            }
        }

        async function viewTicket(ticketId) {
            const ticket = dashboardData.tickets.find(t => t.id === ticketId);
            if (!ticket) return;

            document.getElementById("ticket-title-id").textContent = ticket.id;
            document.getElementById("ticket-reply-id").value = ticket.id;
            document.getElementById("ticket-reply-message").value = "";

            try {
                const res = await fetch(`/admin/api/ticket-messages?ticket_id=${ticketId}`);
                if (res.ok) {
                    const messages = await res.json();
                    const area = document.getElementById("ticket-chat-area");
                    area.innerHTML = messages.map(msg => `
                        <div class="chat-message chat-message-${msg.sender_type}">
                            <div>${msg.content}</div>
                            <span class="chat-time">${formatDateTime(msg.created_at)}</span>
                        </div>
                    `).join("");
                    openModal("ticket-modal");
                    area.scrollTop = area.scrollHeight;
                }
            } catch (err) {
                showToast("Échec de récupération de la discussion", "error");
            }
        }

        async function replyToTicket(event) {
            event.preventDefault();
            const ticketId = document.getElementById("ticket-reply-id").value;
            const message = document.getElementById("ticket-reply-message").value;

            const params = new URLSearchParams();
            params.append("action", "reply_ticket");
            params.append("ticket_id", ticketId);
            params.append("message", message);

            try {
                const res = await fetch("/admin", {
                    method: "POST",
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: params
                });
                if (res.ok) {
                    showToast("Réponse transmise");
                    closeModal("ticket-modal");
                    await refreshDashboardData();
                }
            } catch (err) {
                showToast("Erreur réseau", "error");
            }
        }

        async function closeTicket(ticketId) {
            if (!confirm("Marquer ce ticket comme résolu et le fermer ?")) return;
            const params = new URLSearchParams();
            params.append("action", "close_ticket");
            params.append("ticket_id", ticketId);

            try {
                const res = await fetch("/admin", {
                    method: "POST",
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: params
                });
                if (res.ok) {
                    showToast("Ticket fermé");
                    await refreshDashboardData();
                }
            } catch (err) {
                showToast("Erreur réseau", "error");
            }
        }

        async function saveSettings(event) {
            event.preventDefault();
            const form = event.target;
            const formData = new FormData(form);
            const params = new URLSearchParams();
            params.append("action", "save_settings");
            for (const pair of formData.entries()) {
                params.append(pair[0], pair[1]);
            }

            try {
                const res = await fetch("/admin", {
                    method: "POST",
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: params
                });
                if (res.ok) {
                    showToast("Configuration enregistrée avec succès");
                    await refreshDashboardData();
                }
            } catch (err) {
                showToast("Erreur réseau lors de l'enregistrement", "error");
            }
        }

        // Recherche et filtres serveur avec temporisation pour éviter une requête par frappe.
        function filterOrders() {
            clearTimeout(orderFilterTimer);
            ordersPagination.page = 1;
            orderFilterTimer = setTimeout(refreshDashboardData, 250);
        }

        function filterCustomers() {
            const query = document.getElementById("customer-search").value.toLowerCase();
            const rows = document.querySelectorAll("#customers-table tbody tr");

            rows.forEach(row => {
                if (row.cells.length < 3) return;
                const text = row.innerText.toLowerCase();
                row.style.display = text.includes(query) ? "" : "none";
            });
        }

        function filterTickets() {
            const status = document.getElementById("ticket-filter-status").value;
            const rows = document.querySelectorAll("#tickets-table tbody tr");

            rows.forEach(row => {
                if (row.cells.length < 5) return;
                const badge = row.querySelector(".badge").textContent;
                row.style.display = (!status || badge === status) ? "" : "none";
            });
        }
    </script>
</body>
</html>
"""

    # Remplacements de chaînes simples pour éviter les syntax errors f-string
    return (
        html_template.replace("__SHOP_NAME__", html.escape(shop_name))
        .replace("__ALERTS_HTML__", alerts_html)
        .replace("__KPIS_HTML__", kpis_html)
        .replace("__JSON_DATA__", json_data_str)
    )
