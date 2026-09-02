
        let dashboardData = {"summary": {}, "alerts": [], "services": []};
        const dashboardWriteToken = "";
        let ordersPagination = { page: 1, pages: 1, total: 0 };
        let inventoryPagination = { page: 1, pages: 1, total: 0 };
        let orderFilterTimer;
        let inventoryFilterTimer;
        let resellerCatalog = null;
        let resellerCatalogLoading = false;
        let apiWorkspaceStep = "overview";
        let selectedApiProductId = null;
        let activeApiProvider = "mailreader";
        let realtimeRequestRunning = false;
        let adminNotifications = loadAdminNotifications();
        let notificationSnapshot = snapshotDashboard(dashboardData);

        // Every dashboard API request must carry the scoped write token. Most
        // browsers preserve Basic Auth for fetch(), but embedded/mobile
        // browsers can omit it on POST requests, which previously caused
        // authenticated offer edits to fail with a misleading 401 response.
        const nativeDashboardFetch = window.fetch.bind(window);
        window.fetch = (input, options = {}) => {
            const requestUrl = new URL(
                typeof input === "string" ? input : input.url,
                window.location.href
            );
            if (
                requestUrl.origin === window.location.origin &&
                requestUrl.pathname.startsWith("/admin")
            ) {
                const headers = new Headers(
                    options.headers || (input instanceof Request ? input.headers : {})
                );
                if (dashboardWriteToken) {
                    headers.set("X-Dashboard-Write-Token", dashboardWriteToken);
                }
                options = {
                    ...options,
                    headers,
                    credentials: "same-origin"
                };
            }
            return nativeDashboardFetch(input, options);
        };

        const ORDER_STATUSES = [
            "pending_payment",
            "awaiting_verification",
            "payment_confirmed",
            "preparing_delivery",
            "delivered",
            "verification_failed",
            "manual_review",
            "cancelled",
            "refunded",
            "expired",
            "paid"
        ];

        // Au chargement de la page
        document.addEventListener("DOMContentLoaded", () => {
            setupTabNavigation();
            refreshUI();
            renderAdminNotifications();
            refreshDashboardData();
            if (document.getElementById("overview")?.classList.contains("active")) {
                loadOverviewSupplier();
            }
            if (document.getElementById("api-products")?.classList.contains("active")) {
                loadApiProducts();
                loadBuyerApiKeys();
            }
        });

        document.addEventListener("click", event => {
            const center = document.querySelector(".notification-center");
            if (center && !center.contains(event.target)) closeNotificationCenter();
        });

        function snapshotDashboard(data) {
            return {
                orders: Number(data?.summary?.orders || 0),
                openTickets: Number(data?.summary?.open_tickets || 0),
                alerts: Array.isArray(data?.alerts) ? data.alerts.length : 0
            };
        }

        function loadAdminNotifications() {
            try { return JSON.parse(localStorage.getItem("admin-notifications-v1") || "[]"); }
            catch (_) { return []; }
        }

        function persistAdminNotifications() {
            localStorage.setItem("admin-notifications-v1", JSON.stringify(adminNotifications.slice(0, 30)));
        }

        function addAdminNotification(title, message, type = "info") {
            const item = { id: Date.now() + Math.random(), title, message, type, createdAt: new Date().toISOString(), unread: true };
            adminNotifications.unshift(item);
            adminNotifications = adminNotifications.slice(0, 30);
            persistAdminNotifications();
            renderAdminNotifications();
            showToast(`${title} · ${message}`, type === "error" ? "error" : "success");
            if ("Notification" in window && Notification.permission === "granted") new Notification(title, { body: message });
        }

        function detectDashboardEvents(previous, current) {
            if (!previous) return;
            const newOrders = current.orders - previous.orders;
            const newTickets = current.openTickets - previous.openTickets;
            if (newOrders > 0) addAdminNotification("Nouvelle commande", `${newOrders} nouvelle${newOrders > 1 ? "s" : ""} commande${newOrders > 1 ? "s" : ""} reçue${newOrders > 1 ? "s" : ""}.`);
            if (newTickets > 0) addAdminNotification("Support", `${newTickets} nouvelle${newTickets > 1 ? "s" : ""} demande${newTickets > 1 ? "s" : ""} à traiter.`);
            if (current.alerts > previous.alerts) addAdminNotification("Alerte système", "Une nouvelle alerte nécessite votre attention.", "error");
        }

        function renderAdminNotifications() {
            const list = document.getElementById("notification-list");
            const badge = document.getElementById("notification-badge");
            if (!list || !badge) return;
            const unread = adminNotifications.filter(item => item.unread).length;
            badge.textContent = unread > 99 ? "99+" : unread;
            badge.classList.toggle("visible", unread > 0);
            list.innerHTML = adminNotifications.length ? adminNotifications.map(item => `<div class="notification-item"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.message)} · ${new Date(item.createdAt).toLocaleString("fr-FR")}</span></div>`).join("") : '<div class="notification-empty">Aucune notification pour le moment.</div>';
            const permissionButton = document.getElementById("browser-notification-button");
            if (permissionButton && "Notification" in window && Notification.permission === "granted") permissionButton.textContent = "Alertes navigateur activées";
        }

        function toggleNotificationCenter(event) {
            event?.stopPropagation();
            const panel = document.getElementById("notification-panel");
            const button = document.getElementById("notification-button");
            const open = !panel.classList.contains("open");
            panel.classList.toggle("open", open);
            button.setAttribute("aria-expanded", String(open));
            if (open) {
                adminNotifications.forEach(item => item.unread = false);
                persistAdminNotifications();
                renderAdminNotifications();
            }
        }

        function closeNotificationCenter() {
            document.getElementById("notification-panel")?.classList.remove("open");
            document.getElementById("notification-button")?.setAttribute("aria-expanded", "false");
        }

        function clearAdminNotifications() {
            adminNotifications = [];
            persistAdminNotifications();
            renderAdminNotifications();
        }

        async function enableBrowserNotifications() {
            if (!("Notification" in window)) return showToast("Ce navigateur ne prend pas en charge les notifications", "error");
            const permission = await Notification.requestPermission();
            renderAdminNotifications();
            showToast(permission === "granted" ? "Alertes navigateur activées" : "Autorisation de notification refusée", permission === "granted" ? "success" : "error");
        }

        function setRealtimeStatus(online) {
            const chip = document.getElementById("realtime-chip");
            const copy = document.getElementById("realtime-copy");
            chip?.classList.toggle("offline", !online);
            if (copy) copy.textContent = online ? "Temps réel actif" : "Connexion interrompue";
        }

        function setupTabNavigation() {
            const buttons = document.querySelectorAll("nav a[data-tab]");
            const panels = document.querySelectorAll(".panel");
            const title = document.getElementById("panel-title");

            function activateTab(btn) {
                const tabId = btn.dataset.tab;
                const panel = document.getElementById(tabId);
                if (!panel) return;

                buttons.forEach(b => b.classList.remove("active"));
                panels.forEach(p => {
                    p.classList.remove("active");
                    p.style.display = "none";
                });
                btn.classList.add("active");
                panel.classList.add("active");
                panel.style.display = "block";
                title.textContent = btn.dataset.title || btn.textContent.trim();
                location.hash = tabId;
                if (tabId === "api-products") {
                    loadApiProducts();
                    loadBuyerApiKeys();
                }
                if (tabId === "overview") loadOverviewSupplier();
                document.querySelector("main").scrollIntoView({ behavior: "smooth", block: "start" });
            }

            buttons.forEach(btn => {
                btn.addEventListener("click", event => {
                    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
                    event.preventDefault();
                    history.pushState(null, "", btn.getAttribute("href"));
                    activateTab(btn);
                });
            });

            window.addEventListener("popstate", () => {
                const tabId = location.pathname.replace("/admin/", "") || "overview";
                const button = document.querySelector(`nav a[data-tab="${tabId}"]`);
                if (button) activateTab(button);
            });

            // Gérer le hash initial
            if (location.hash) {
                const tabId = location.hash.substring(1);
                const button = document.querySelector(`nav a[data-tab="${tabId}"]`);
                if (button) activateTab(button);
            } else if (location.pathname.startsWith("/admin/")) {
                const tabId = location.pathname.replace("/admin/", "");
                const button = document.querySelector(`nav a[data-tab="${tabId}"]`);
                if (button) activateTab(button);
            }
        }

        function navigateToTab(tabId) {
            const button = document.querySelector(`nav a[data-tab="${tabId}"]`);
            if (button) button.click();
        }

        function runGlobalSearch(event) {
            if (event.key !== "Enter") return;
            const value = event.currentTarget.value.trim();
            if (!value) return;
            navigateToTab("orders");
            const orderSearch = document.getElementById("order-search");
            orderSearch.value = value;
            filterOrders();
        }

        document.addEventListener("keydown", event => {
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
                event.preventDefault();
                document.getElementById("global-search")?.focus();
            }
        });

        function openMaintenanceSettings() {
            navigateToTab("settings");
            setTimeout(() => {
                const control = document.getElementById("maintenance-enabled-input");
                control?.focus();
                control?.scrollIntoView({ behavior: "smooth", block: "center" });
            }, 80);
        }

        function openBotBroadcast() {
            const username = dashboardData.bot_username || "blackmarketa_bot";
            window.open(`https://t.me/${encodeURIComponent(username)}`, "_blank", "noopener");
            showToast("Ouvrez le panneau Admin du bot pour créer l’annonce");
        }

        async function syncSupplierCatalog() {
            navigateToTab("api-products");
            await loadApiProducts(true);
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
            document.getElementById("nav-order-count").textContent = dashboardData.summary?.pending_orders || 0;
            document.getElementById("nav-support-count").textContent = dashboardData.summary?.open_tickets || 0;

            // Vue d'ensemble KPI
            renderAlerts();
            renderKPIs();
            renderOverviewOrders();
            updateOverviewSupplier();

            // Tables & catalogue
            renderOrdersTable();
            renderCatalog();
            renderInventory();
            renderInventoryItems();
            renderCustomersTable();
            renderTicketsTable();
            renderInteractions();
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
            const interactions = dashboardData.interactions?.summary || {};
            const apiBalance = resellerCatalog?.balance;
            container.innerHTML = `
                <div class="kpi-grid">
                    <div class="kpi-card">
                        <h3>Chiffre d’affaires · 7 jours</h3>
                        <div class="kpi-value">${Number(s.revenue_7d || 0).toFixed(2)} <small>${currency}</small></div>
                        <div class="kpi-subtext">${Number(s.revenue_7d_change_pct || 0) >= 0 ? "↑" : "↓"} ${Math.abs(Number(s.revenue_7d_change_pct || 0)).toFixed(1)}% par rapport aux 7 jours précédents</div>
                    </div>
                    <div class="kpi-card">
                        <h3>Commandes totales</h3>
                        <div class="kpi-value">${s.orders || 0}</div>
                        <div class="kpi-subtext">${s.paid_orders || 0} payées • ${s.pending_orders || 0} en attente</div>
                    </div>
                    <div class="kpi-card">
                        <h3>Solde fournisseur API</h3>
                        <div class="kpi-value">${apiBalance == null ? "—" : Number(apiBalance).toFixed(2)} <small>USDT</small></div>
                        <div class="kpi-subtext">${dashboardData.reseller?.selected_count || 0} produit(s) sélectionné(s) pour la revente</div>
                    </div>
                    <div class="kpi-card">
                        <h3>Utilisateurs actifs</h3>
                        <div class="kpi-value">${interactions.live_users || 0}</div>
                        <div class="kpi-subtext">${interactions.active_today || 0} actif(s) aujourd’hui • ${s.users || 0} inscrits</div>
                    </div>
                </div>
            `;
        }

        function renderOverviewOrders() {
            const tbody = document.querySelector("#overview-orders-table tbody");
            if (!tbody) return;
            const orders = (dashboardData.orders || []).slice(0, 5);
            if (!orders.length) {
                tbody.innerHTML = '<tr><td colspan="6" class="empty-state">Aucune commande récente.</td></tr>';
                return;
            }
            tbody.innerHTML = orders.map(order => `
                <tr>
                    <td><code>#${escapeHtml(order.id)}</code></td>
                    <td><code>${escapeHtml(order.user_id)}</code></td>
                    <td>${escapeHtml(`${order.service_name || ""} — ${order.offer_name || ""}`)}</td>
                    <td>${Number(order.total_price || 0).toFixed(2)} ${escapeHtml(dashboardData.currency || "USDT")}</td>
                    <td><span class="badge badge-${escapeHtml(order.status || "")}">${escapeHtml(order.status || "—")}</span></td>
                    <td>${formatDateTime(order.created_at)}</td>
                </tr>
            `).join("");
        }

        async function loadOverviewSupplier() {
            if (resellerCatalogLoading) return;
            if (resellerCatalog) {
                updateOverviewSupplier();
                return;
            }
            await loadApiProducts();
        }

        function updateOverviewSupplier() {
            const status = document.getElementById("overview-supplier-status");
            const copy = document.getElementById("overview-supplier-copy");
            const balance = document.getElementById("overview-supplier-balance");
            const meter = document.getElementById("overview-supplier-meter");
            if (!status || !copy || !balance || !meter) return;
            if (!resellerCatalog) {
                const configured = Boolean(dashboardData.reseller?.configured);
                status.textContent = configured ? "VÉRIFICATION…" : "À CONFIGURER";
                status.style.color = configured ? "var(--warning)" : "var(--danger)";
                copy.textContent = configured ? "Connexion au fournisseur…" : "Clé API manquante";
                balance.textContent = "— USDT";
                meter.style.width = "0%";
                return;
            }
            const amount = Number(resellerCatalog.balance || 0);
            status.textContent = "● EN LIGNE";
            status.style.color = "var(--success)";
            copy.textContent = `${resellerCatalog.products?.length || 0} produits synchronisés`;
            balance.textContent = `${amount.toFixed(2)} ${resellerCatalog.currency || "USDT"}`;
            meter.style.width = `${Math.max(6, Math.min(100, amount))}%`;
            renderKPIs();
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
                tbody.innerHTML = '<tr><td colspan="11" class="empty-state">Aucun membre enregistré.</td></tr>';
                return;
            }

            dashboardData.users.forEach(user => {
                const tr = document.createElement("tr");
                const banLabel = user.banned ? "Débannir" : "Bannir";
                const banClass = user.banned ? "btn-primary" : "btn-danger";
                tr.innerHTML = `
                    <td><code>${user.telegram_id}</code></td>
                    <td>${escapeHtml(user.username ? '@' + user.username : '—')}</td>
                    <td>${escapeHtml(user.first_name || user.full_name || '—')}</td>
                    <td><strong>${Number(user.wallet_balance || 0).toFixed(2)} ${escapeHtml(dashboardData.currency)}</strong></td>
                    <td>${user.paid_order_count || 0} / ${user.order_count || 0}</td>
                    <td>${(user.total_spent || user.total_paid || 0).toFixed(2)} ${dashboardData.currency}</td>
                    <td>${user.referral_count || 0}</td>
                    <td>${user.last_active_at ? formatDateTime(user.last_active_at) : 'Jamais'}</td>
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
                                ${offer.description ? `<div style="color:var(--text-muted);font-size:13px;margin-bottom:6px;">${escapeHtml(offer.description)}</div>` : ''}
                                <div class="offer-meta">
                                    <span>💵 Prix : ${offer.price !== null ? offer.price.toFixed(2) : '—'} ${dashboardData.currency}</span>
                                    <span>📦 Stock : ${offer.stock}</span>
                                    <span>📝 Note : ${offer.note || '—'}</span>
                                    <span>Livraison : ${offer.delivery_delay || '-'}</span>
                                </div>
                            </div>
                            <div class="offer-actions">
                                <button class="btn btn-secondary" style="padding:6px 12px; font-size:12px;" onclick="openEditOfferModal(${offer.id})">✏️ Éditer</button>
                                <button class="btn btn-secondary" style="padding:6px 12px; font-size:12px;" onclick="duplicateOffer(${offer.id})">📋 Dupliquer</button>
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

        async function selectApiProvider(provider) {
            activeApiProvider = provider;
            selectedApiProductId = null;
            resellerCatalog = null;
            await loadApiProducts(true, provider);
            if (resellerCatalog) showApiWorkspaceStep("catalog");
        }

        async function loadBuyerApiKeys() {
            const list = document.getElementById("buyer-api-key-list");
            if (!list) return;
            try {
                const response = await fetch("/admin/api/buyer-keys", {
                    credentials: "same-origin",
                    headers: {"Accept": "application/json"},
                });
                const payload = await response.json();
                if (!response.ok || !payload.ok) throw new Error(payload.error || "Chargement impossible");
                const keys = payload.keys || [];
                list.innerHTML = keys.length ? keys.map(item => `
                    <div class="supplier-summary" style="margin-top:8px;">
                        <div class="supplier-stat"><span>Clé</span><strong>${escapeHtml(item.prefix)}••••</strong></div>
                        <div class="supplier-stat"><span>Utilisateur</span><strong>${item.user_id}</strong></div>
                        <div class="supplier-stat"><span>Nom</span><strong>${escapeHtml(item.label || "Buyer API")}</strong></div>
                        <div class="supplier-stat"><span>État</span><strong>${item.active ? "Active" : "Révoquée"}</strong></div>
                        ${item.active ? `<button class="btn btn-danger" onclick="revokeBuyerApiKey(${item.id})">Révoquer</button>` : ""}
                    </div>`).join("") : '<div class="empty-state">Aucune clé Buyer API.</div>';
            } catch (error) {
                list.innerHTML = `<div class="alert alert-error">${escapeHtml(error.message)}</div>`;
            }
        }

        async function createBuyerApiKey() {
            const userId = Number(document.getElementById("buyer-api-user-id").value);
            const label = document.getElementById("buyer-api-label").value.trim();
            if (!Number.isInteger(userId) || userId <= 0) {
                showToast("Telegram user ID invalide", "error");
                return;
            }
            try {
                const response = await fetch("/admin/api/buyer-keys", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json",
                        "X-Dashboard-Write-Token": dashboardWriteToken,
                    },
                    body: JSON.stringify({action: "create", user_id: userId, label}),
                });
                const payload = await response.json();
                if (!response.ok || !payload.ok) throw new Error(payload.error || "Création impossible");
                const output = document.getElementById("buyer-api-created-key");
                output.style.display = "block";
                output.innerHTML = `<strong>Copiez cette clé maintenant :</strong><br><code>${escapeHtml(payload.key.key)}</code>`;
                await loadBuyerApiKeys();
                showToast("Clé Buyer API créée");
            } catch (error) {
                showToast(error.message, "error");
            }
        }

        async function revokeBuyerApiKey(keyId) {
            if (!window.confirm("Révoquer immédiatement cette clé API ?")) return;
            try {
                const response = await fetch("/admin/api/buyer-keys", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json",
                        "X-Dashboard-Write-Token": dashboardWriteToken,
                    },
                    body: JSON.stringify({action: "revoke", key_id: keyId}),
                });
                const payload = await response.json();
                if (!response.ok || !payload.ok) throw new Error(payload.error || "Révocation impossible");
                await loadBuyerApiKeys();
                showToast("Clé révoquée");
            } catch (error) {
                showToast(error.message, "error");
            }
        }

        async function loadApiProducts(force = false, provider = activeApiProvider) {
            if (provider !== activeApiProvider) {
                activeApiProvider = provider;
                resellerCatalog = null;
                selectedApiProductId = null;
            }
            if (resellerCatalogLoading || (resellerCatalog && !force)) {
                if (resellerCatalog) renderApiProducts();
                return;
            }
            resellerCatalogLoading = true;
            const refreshButton = document.getElementById("api-products-refresh");
            if (refreshButton) refreshButton.disabled = true;
            try {
                const response = await fetch(`/admin/api/reseller-products?provider=${encodeURIComponent(activeApiProvider)}`, {
                    headers: { "Accept": "application/json" }
                });
                const result = await response.json();
                if (!response.ok || !result.ok) {
                    throw new Error(result.error || "Connexion fournisseur impossible.");
                }
                resellerCatalog = result;
                renderApiProducts();
                updateOverviewSupplier();
                if (force) showToast(`Catalogue ${result.supplier_name || "API"} actualisé`);
            } catch (error) {
                resellerCatalog = null;
                updateOverviewSupplier();
                document.getElementById("api-supplier-state").innerHTML = `
                    <div class="alert alert-error">
                        <span class="alert-icon">⚠️</span>
                        <span class="alert-message">${escapeHtml(error.message)}</span>
                    </div>`;
                document.getElementById("api-product-list").innerHTML = `
                    <div class="empty-state">
                        Cette API reste indisponible tant que sa clé n’est pas configurée sur le serveur.
                    </div>`;
            } finally {
                resellerCatalogLoading = false;
                if (refreshButton) refreshButton.disabled = false;
            }
        }

        function showApiWorkspaceStep(step, productId = null) {
            if (productId) selectedApiProductId = String(productId);
            apiWorkspaceStep = step;
            document.querySelectorAll(".api-step-button").forEach(button => {
                button.classList.toggle("active", button.dataset.apiStep === step);
            });
            document.querySelectorAll(".api-workspace-page").forEach(page => {
                page.classList.toggle("active", page.id === `api-workspace-${step}`);
            });
            if (step === "editor") renderApiProductEditor();
        }

        function openApiProductEditor(productId) {
            selectedApiProductId = String(productId);
            showApiWorkspaceStep("editor");
        }

        function renderApiProducts() {
            if (!resellerCatalog) return;
            const products = resellerCatalog.products || [];
            activeApiProvider = resellerCatalog.provider || activeApiProvider;
            document.getElementById("api-catalog-title").textContent =
                `Produits & services ${resellerCatalog.supplier_name || "API"}`;
            document.getElementById("api-supplier-state").innerHTML = `
                <div class="supplier-summary">
                    <div class="supplier-stat">
                        <span>Connexion fournisseur</span>
                        <strong><span class="live-dot"></span>Active</strong>
                    </div>
                    <div class="supplier-stat">
                        <span>Solde API</span>
                        <strong>${Number(resellerCatalog.balance || 0).toFixed(2)} ${escapeHtml(resellerCatalog.currency || "USDT")}</strong>
                    </div>
                    <div class="supplier-stat">
                        <span>Produits disponibles</span>
                        <strong>${products.length}</strong>
                    </div>
                    <div class="supplier-stat">
                        <span>Produits publiés</span>
                        <strong>${resellerCatalog.selected_count || 0}</strong>
                    </div>
                </div>`;

            const servicesStrip = document.getElementById("api-services-strip");
            const services = dashboardData.services || [];
            servicesStrip.innerHTML = services.length
                ? services.map(service => `
                    <span class="api-service-chip">${escapeHtml((service.emoji || "📦") + " " + service.name)}</span>
                `).join("")
                : '<span class="last-update">Aucun service créé.</span>';

            const list = document.getElementById("api-product-list");
            if (!products.length) {
                list.innerHTML = `<div class="empty-state">Aucun produit automatique disponible chez ${escapeHtml(resellerCatalog.supplier_name || "ce fournisseur")}.</div>`;
                return;
            }
            list.innerHTML = products.map(product => {
                const wholesale = Number(product.wholesale_price || 0);
                const retail = product.retail_price == null
                    ? Math.ceil((wholesale * 1.30) * 100) / 100
                    : Number(product.retail_price);
                return `
                    <article class="api-product-row ${product.enabled ? "enabled" : ""}"
                             data-enabled="${product.enabled ? "1" : "0"}"
                             data-stock="${Number(product.stock || 0)}"
                             data-search="${escapeHtml((product.name + " " + product.id + " " + (product.service_name || "")).toLowerCase())}">
                        <div>
                            <h3>${escapeHtml(product.name)}</h3>
                            <div class="api-product-id">${escapeHtml(product.id)}</div>
                            <div class="api-statuses" style="margin-top:8px;">
                                ${product.enabled ? '<span class="badge badge-paid">Publié</span>' : '<span class="badge">Brouillon</span>'}
                                ${product.manual_delivery ? '<span class="badge badge-pending">Livraison manuelle</span>' : ''}
                                <span class="badge badge-${product.stock > 0 ? "paid" : "cancelled"}">${Number(product.stock || 0)} stock</span>
                            </div>
                        </div>
                        <div class="api-row-stat">
                            <span>Service</span>
                            <strong>${escapeHtml(product.service_name ? (product.service_emoji || "📦") + " " + product.service_name : "Non assigné")}</strong>
                        </div>
                        <div class="api-row-stat">
                            <span>Grossiste</span>
                            <strong>${wholesale.toFixed(2)} ${escapeHtml(product.currency || "USDT")}</strong>
                        </div>
                        <div class="api-row-stat">
                            <span>Prix client</span>
                            <strong>${retail.toFixed(2)} ${escapeHtml(product.currency || "USDT")}</strong>
                        </div>
                        <button class="btn btn-primary" data-product-id="${escapeHtml(product.id)}"
                                onclick="openApiProductEditor(this.dataset.productId)">Configurer →</button>
                    </article>`;
            }).join("");
            filterApiProducts();
            if (apiWorkspaceStep === "editor") renderApiProductEditor();
        }

        function renderApiProductEditor() {
            const editor = document.getElementById("api-product-editor");
            const product = (resellerCatalog?.products || []).find(
                item => String(item.id) === String(selectedApiProductId)
            );
            if (!product) {
                editor.innerHTML = '<div class="empty-state">Choisissez d’abord un produit dans l’étape 2.</div>';
                return;
            }
            const wholesale = Number(product.wholesale_price || 0);
            const retail = product.retail_price == null
                ? Math.ceil((wholesale * 1.30) * 100) / 100
                : Number(product.retail_price);
            const profit = retail - wholesale;
            const margin = retail > 0 ? (profit / retail) * 100 : 0;
            const services = (dashboardData.services || []).map(service => `
                <option value="${Number(service.id)}" ${Number(product.service_id) === Number(service.id) ? "selected" : ""}>
                    ${escapeHtml((service.emoji || "📦") + " " + service.name)}
                </option>`).join("");
            const previewService = product.service_name
                ? `${product.service_emoji || "📦"} ${product.service_name}`
                : "📦 Choisissez un service";
            editor.innerHTML = `
                <article class="api-product-card ${product.enabled ? "enabled" : ""} ${product.published ? "published" : ""}"
                         data-product-id="${escapeHtml(product.id)}">
                    <div class="api-product-heading">
                        <div>
                            <div class="api-product-id">Configuration du produit</div>
                            <h3>${escapeHtml(product.name)}</h3>
                            <div class="api-product-id">${escapeHtml(product.id)}</div>
                        </div>
                        <div class="api-statuses">
                            ${product.enabled ? '<span class="badge badge-paid">Publié dans le bot</span>' : '<span class="badge">Brouillon</span>'}
                            ${product.manual_delivery ? '<span class="badge badge-pending">Livraison fournisseur manuelle</span>' : ''}
                            <span class="badge badge-${product.stock > 0 ? "paid" : "cancelled"}">${Number(product.stock || 0)} en stock</span>
                        </div>
                    </div>
                    <div class="api-price-grid">
                        <div class="api-price-box">
                            <span>Prix grossiste</span>
                            <strong>${wholesale.toFixed(2)} ${escapeHtml(product.currency || "USDT")}</strong>
                        </div>
                        <div class="api-price-box">
                            <span>Bénéfice par vente</span>
                            <strong class="api-profit ${profit <= 0 ? "loss" : ""}">${profit.toFixed(2)} ${escapeHtml(product.currency || "USDT")} · ${margin.toFixed(1)}%</strong>
                        </div>
                    </div>
                    <div class="api-config-grid">
                        <div class="form-group wide">
                            <label>Service affiché dans le bot</label>
                            <select class="api-service" onchange="toggleApiNewService(this); updateApiPreview(this)">
                                <option value="">Choisir un service…</option>
                                ${services}
                                <option value="__new__">＋ Créer un nouveau service</option>
                            </select>
                        </div>
                        <div class="api-new-service-fields wide">
                            <div class="form-group">
                                <label>Emoji</label>
                                <input class="api-service-emoji" maxlength="12" value="${escapeHtml(product.service_emoji || "📦")}" oninput="updateApiPreview(this)">
                            </div>
                            <div class="form-group">
                                <label>Nom du nouveau service</label>
                                <input class="api-new-service-name" maxlength="80" placeholder="Ex. Comptes Premium" oninput="updateApiPreview(this)">
                            </div>
                        </div>
                        <div class="form-group">
                            <label>Nom visible du produit</label>
                            <input class="api-display-name" maxlength="120" value="${escapeHtml(product.display_name || product.name)}" oninput="updateApiPreview(this)">
                        </div>
                        <div class="form-group">
                            <label>Votre prix client (${escapeHtml(product.currency || "USDT")})</label>
                            <input class="api-retail-price" type="number" min="${(wholesale + 0.01).toFixed(2)}"
                                   step="0.01" value="${retail.toFixed(2)}" oninput="updateApiProfit(this); updateApiPreview(this)">
                        </div>
                        <div class="form-group wide">
                            <label>Description client</label>
                            <textarea class="api-description" maxlength="1000" placeholder="Ce que le client reçoit…">${escapeHtml(product.custom_description || "")}</textarea>
                        </div>
                        <div class="form-group wide">
                            <label>Garantie affichée dans le bot</label>
                            <input class="api-warranty" maxlength="250" value="${escapeHtml(product.warranty || "")}" placeholder="Ex. Remplacement sous 24 heures">
                        </div>
                        <div class="form-group">
                            <label>Délai de livraison</label>
                            <input class="api-delivery-delay" maxlength="120" value="${escapeHtml(product.delivery_delay || "Instantané après confirmation")}">
                        </div>
                        <div class="form-group">
                            <label>Alerte stock bas</label>
                            <input class="api-low-stock" type="number" min="0" value="${Number(product.low_stock_threshold || 0)}">
                        </div>
                        <div class="form-group">
                            <label>Ordre d’affichage</label>
                            <input class="api-sort-order" type="number" min="0" value="${Number(product.sort_order || 0)}">
                        </div>
                        <div class="form-group">
                            <label>Référence fournisseur</label>
                            <input value="${escapeHtml(product.id)}" disabled>
                        </div>
                    </div>
                    <div class="api-product-preview">
                        <small>Aperçu dans le bot</small>
                        <div class="api-preview-service">${escapeHtml(previewService)}</div>
                        <div class="api-preview-line">
                            <span class="api-preview-product">${escapeHtml(product.display_name || product.name)}</span>
                            <span><span class="api-preview-price">${retail.toFixed(2)}</span> ${escapeHtml(product.currency || "USDT")}</span>
                        </div>
                    </div>
                    <div class="api-card-actions">
                        <label class="api-enabled-control">
                            <input class="api-enabled" type="checkbox" ${product.enabled ? "checked" : ""}>
                            Publier et revendre dans le bot
                        </label>
                        <button class="btn btn-primary" onclick="saveApiProduct(this)">Enregistrer & synchroniser</button>
                    </div>
                </article>`;
        }

        function toggleApiNewService(select) {
            select.closest(".api-product-card")
                .querySelector(".api-new-service-fields")
                .classList.toggle("visible", select.value === "__new__");
        }

        function updateApiPreview(input) {
            const card = input.closest(".api-product-card");
            const serviceSelect = card.querySelector(".api-service");
            const newService = serviceSelect.value === "__new__";
            const serviceText = newService
                ? `${card.querySelector(".api-service-emoji").value || "📦"} ${card.querySelector(".api-new-service-name").value || "Nouveau service"}`
                : (serviceSelect.selectedOptions[0]?.textContent.trim() || "📦 Choisissez un service");
            card.querySelector(".api-preview-service").textContent = serviceText;
            card.querySelector(".api-preview-product").textContent =
                card.querySelector(".api-display-name").value || "Produit";
            card.querySelector(".api-preview-price").textContent =
                Number(card.querySelector(".api-retail-price").value || 0).toFixed(2);
        }

        function updateApiProfit(input) {
            const card = input.closest(".api-product-card");
            const product = (resellerCatalog?.products || []).find(
                item => item.id === card.dataset.productId
            );
            if (!product) return;
            const profit = Number(input.value || 0) - Number(product.wholesale_price || 0);
            const output = card.querySelector(".api-profit");
            const retail = Number(input.value || 0);
            const margin = retail > 0 ? (profit / retail) * 100 : 0;
            output.textContent = `${profit.toFixed(2)} ${product.currency || "USDT"} · ${margin.toFixed(1)}%`;
            output.classList.toggle("loss", profit <= 0);
        }

        function filterApiProducts() {
            const search = (document.getElementById("api-product-search")?.value || "").toLowerCase();
            const visibility = document.getElementById("api-product-visibility")?.value || "";
            document.querySelectorAll(".api-product-row").forEach(card => {
                const matchesSearch = (card.dataset.search || "").includes(search);
                const matchesVisibility =
                    !visibility ||
                    (visibility === "enabled" && card.dataset.enabled === "1") ||
                    (visibility === "disabled" && card.dataset.enabled === "0") ||
                    (visibility === "stock" && Number(card.dataset.stock || 0) > 0);
                card.style.display = matchesSearch && matchesVisibility ? "" : "none";
            });
        }

        async function saveApiProduct(button) {
            const card = button.closest(".api-product-card");
            const retailInput = card.querySelector(".api-retail-price");
            const enabled = card.querySelector(".api-enabled").checked;
            const serviceSelect = card.querySelector(".api-service");
            if (!serviceSelect.value) {
                showToast("Choisissez un service pour publier ce produit.", "error");
                return;
            }
            if (serviceSelect.value === "__new__" && !card.querySelector(".api-new-service-name").value.trim()) {
                showToast("Donnez un nom au nouveau service.", "error");
                return;
            }
            const params = new URLSearchParams({
                action: "save_reseller_product",
                provider: activeApiProvider,
                product_id: card.dataset.productId,
                retail_price: retailInput.value,
                enabled: enabled ? "1" : "0",
                service_id: serviceSelect.value === "__new__" ? "" : serviceSelect.value,
                new_service_name: serviceSelect.value === "__new__" ? card.querySelector(".api-new-service-name").value : "",
                service_emoji: card.querySelector(".api-service-emoji").value,
                display_name: card.querySelector(".api-display-name").value,
                description: card.querySelector(".api-description").value,
                warranty: card.querySelector(".api-warranty").value,
                delivery_delay: card.querySelector(".api-delivery-delay").value,
                low_stock_threshold: card.querySelector(".api-low-stock").value,
                sort_order: card.querySelector(".api-sort-order").value
            });
            button.disabled = true;
            try {
                const response = await fetch("/admin", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-Dashboard-Write-Token": dashboardWriteToken
                    },
                    body: params
                });
                const result = await response.json();
                if (!response.ok || !result.ok) throw new Error(result.error || "Enregistrement impossible.");
                resellerCatalog = null;
                await refreshDashboardData(true);
                showToast(enabled ? "Produit publié dans le catalogue du bot" : "Produit enregistré en brouillon");
                await loadApiProducts(true, activeApiProvider);
            } catch (error) {
                showToast(error.message, "error");
            } finally {
                button.disabled = false;
            }
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
                                ${offer.description ? `<div style="color:var(--text-muted);font-size:13px;margin-bottom:6px;">${escapeHtml(offer.description)}</div>` : ''}
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
                list.innerHTML = `<div class="empty-state">Créez d'abord des offres dans le catalogue.</div>`;
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

        function renderInteractions() {
            const data = dashboardData.interactions || {};
            const summary = data.summary || {};
            const kpis = [
                ["Total interactions", summary.total || 0],
                ["Aujourd’hui", summary.today || 0],
                ["Utilisateurs actifs", summary.active_today || 0],
                ['<span class="live-dot"></span>Actifs (5 min)', summary.live_users || 0],
                ["Clics boutons (30 j)", summary.button_clicks || 0],
                ["Messages (30 j)", summary.messages || 0],
            ];
            document.getElementById("interaction-kpis").innerHTML = kpis.map(item =>
                `<div class="interaction-kpi"><span>${item[0]}</span><strong>${item[1]}</strong></div>`
            ).join("");

            const daily = data.daily || [];
            const maxDaily = Math.max(1, ...daily.map(item => item.count || 0));
            document.getElementById("interactions-daily-chart").innerHTML = daily.map(item => {
                const height = Math.max(2, Math.round((item.count || 0) / maxDaily * 145));
                return `<div class="daily-bar-wrap" title="${item.date}: ${item.count}">
                    <span style="font-size:10px">${item.count || ""}</span>
                    <div class="daily-bar" style="height:${height}px"></div>
                    <span class="daily-label">${item.date.slice(5)}</span>
                </div>`;
            }).join("");

            const types = data.types || {};
            const typeEntries = Object.entries(types).sort((a,b) => b[1] - a[1]);
            const maxType = Math.max(1, ...typeEntries.map(item => item[1]));
            document.getElementById("interactions-type-chart").innerHTML = typeEntries.length
                ? typeEntries.map(([type, count]) => `<div class="type-row">
                    <div class="type-row-head"><span>${escapeHtml(type)}</span><strong>${count}</strong></div>
                    <div class="type-track"><div class="type-fill" style="width:${count / maxType * 100}%"></div></div>
                </div>`).join("")
                : '<div class="empty-state">Aucune interaction enregistrée.</div>';

            const serviceClicks = data.service_clicks || {};
            const serviceDays = [...(serviceClicks.daily || [])].reverse();
            const serviceTotal = serviceClicks.total || 0;
            const serviceCount = (serviceClicks.services || []).length;
            document.getElementById("service-clicks-summary").textContent =
                `${serviceTotal} clic${serviceTotal === 1 ? "" : "s"} • ${serviceCount} service${serviceCount === 1 ? "" : "s"}`;
            const maxServiceClicks = Math.max(
                1,
                ...serviceDays.flatMap(day => (day.services || []).map(service => service.count || 0)),
            );
            document.getElementById("service-clicks-daily").innerHTML = serviceDays.length
                ? serviceDays.map(day => {
                    const label = new Date(`${day.date}T00:00:00Z`).toLocaleDateString(
                        "fr-FR", {weekday:"short", day:"2-digit", month:"short", timeZone:"UTC"},
                    );
                    const rows = (day.services || []).map(service => {
                        const width = Math.max(4, Math.round((service.count || 0) / maxServiceClicks * 100));
                        return `<div class="service-click-row" title="${escapeHtml(service.name || "Service")}: ${service.count || 0}">
                            <span class="service-click-name">${escapeHtml(service.name || `Service #${service.service_id}`)}</span>
                            <span class="service-click-track"><span class="service-click-fill" style="display:block;width:${width}%"></span></span>
                            <span class="service-click-count">${service.count || 0}</span>
                        </div>`;
                    }).join("");
                    return `<article class="service-click-day">
                        <div class="service-click-day-head"><strong>${escapeHtml(label)}</strong><span>${day.total || 0} clic${day.total === 1 ? "" : "s"}</span></div>
                        ${rows}
                    </article>`;
                }).join("")
                : '<div class="empty-state">Aucun clic sur un service pendant cette période.</div>';

            const tbody = document.querySelector("#interactions-table tbody");
            const events = data.events || [];
            tbody.innerHTML = events.length ? events.map(event => {
                const content = event.content || event.screen || "";
                const search = [
                    event.full_name, event.first_name, event.username, event.user_id,
                    event.interaction_type, event.action, content
                ].join(" ").toLowerCase();
                const day = new Date((event.created_at || 0) * 1000).toISOString().slice(0,10);
                return `<tr data-search="${escapeHtml(search)}" data-type="${escapeHtml(event.interaction_type || "")}" data-day="${day}">
                    <td>${formatDateTime(event.created_at)}</td>
                    <td>${escapeHtml(event.full_name || event.first_name || "—")}</td>
                    <td>${event.username ? "@" + escapeHtml(event.username) : "—"}</td>
                    <td><code>${event.user_id || "—"}</code></td>
                    <td><span class="badge badge-info">${escapeHtml(event.interaction_type || "other")}</span></td>
                    <td><code>${escapeHtml(event.action || "—")}</code></td>
                    <td class="interaction-content">${escapeHtml(content || "—")}</td>
                </tr>`;
            }).join("") : '<tr><td colspan="7" class="empty-state">Aucune interaction disponible.</td></tr>';
            filterInteractions();
        }

        function filterInteractions() {
            const search = (document.getElementById("interaction-search")?.value || "").toLowerCase();
            const type = document.getElementById("interaction-type")?.value || "";
            const day = document.getElementById("interaction-date")?.value || "";
            document.querySelectorAll("#interactions-table tbody tr").forEach(row => {
                if (!row.dataset.search) return;
                const visible = (!search || row.dataset.search.includes(search))
                    && (!type || row.dataset.type === type)
                    && (!day || row.dataset.day === day);
                row.style.display = visible ? "" : "none";
            });
        }

        function renderAuditTable() {
            const tbody = document.querySelector("#audit-table tbody");
            tbody.innerHTML = "";

            if (!dashboardData.audits || dashboardData.audits.length === 0) {
                tbody.innerHTML = `<tr><td colspan="4" class="empty-state">Aucun événement d'audit disponible.</td></tr>`;
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
        async function checkAndRepairTelegram() {
            const button = document.getElementById("telegram-repair-button");
            const originalText = button.textContent;
            button.disabled = true;
            button.textContent = "Vérification...";
            try {
                const healthResponse = await fetch("/admin/api/telegram-health", {
                    headers: { "Accept": "application/json" }
                });
                const health = await healthResponse.json();
                if (!healthResponse.ok || !health.ok) {
                    showToast(health.message || "Telegram est temporairement indisponible", "error");
                    return;
                }
                if (health.healthy) {
                    showToast(`Webhook Telegram actif · ${health.pending_update_count || 0} mise(s) à jour en attente`);
                    return;
                }
                const reason = health.last_error_message
                    ? `Dernière erreur : ${health.last_error_message}`
                    : "L’URL Telegram ne correspond pas à l’URL stable.";
                if (!confirm(`${reason}

Réparer le webhook maintenant ?`)) return;
                button.textContent = "Réparation...";
                const params = new URLSearchParams({ action: "repair_telegram_webhook" });
                const repairResponse = await fetch("/admin", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-Dashboard-Write-Token": dashboardWriteToken
                    },
                    body: params
                });
                const repair = await repairResponse.json();
                if (!repairResponse.ok || !repair.ok) {
                    showToast(repair.message || "Réparation Telegram impossible", "error");
                    return;
                }
                showToast("Webhook Telegram réparé sur l’URL stable");
            } catch (err) {
                showToast("Impossible de contacter Telegram depuis Railway", "error");
            } finally {
                button.disabled = false;
                button.textContent = originalText;
            }
        }

        async function testBinanceConnection() {
            const button = document.getElementById("binance-test-button");
            const originalText = button.textContent;
            button.disabled = true;
            button.textContent = "Test en cours...";
            try {
                const response = await fetch("/admin/api/binance-health", {
                    headers: { "Accept": "application/json" }
                });
                const result = await response.json();
                if (!response.ok || !result.ok) {
                    showToast(result.message || "Connexion Binance indisponible", "error");
                    return;
                }
                const endpoint = new URL(result.endpoint).hostname;
                showToast(`Binance connecté via ${endpoint} · ${result.transactions_24h} transaction(s) sur 24 h`);
            } catch (err) {
                showToast("Impossible de tester Binance depuis Railway", "error");
            } finally {
                button.disabled = false;
                button.textContent = originalText;
            }
        }

        async function testBybitConnection() {
            const button = document.getElementById("bybit-test-button");
            const originalText = button.textContent;
            button.disabled = true;
            button.textContent = "Test en cours...";
            try {
                const response = await fetch("/admin/api/bybit-health", {
                    headers: { "Accept": "application/json" }
                });
                const result = await response.json();
                if (!response.ok || !result.ok) {
                    showToast(result.message || "Connexion Bybit indisponible", "error");
                    return;
                }
                const endpoint = new URL(result.endpoint).hostname;
                showToast(`Bybit connecté via ${endpoint} · ${result.transactions} transaction(s) récente(s)`);
            } catch (err) {
                showToast("Impossible de tester Bybit depuis Railway", "error");
            } finally {
                button.disabled = false;
                button.textContent = originalText;
            }
        }

        async function refreshDashboardData(silent = false) {
            if (realtimeRequestRunning) return;
            realtimeRequestRunning = true;
            showProgress();
            try {
                const status = document.getElementById("order-filter-status")?.value || "";
                const search = document.getElementById("order-search")?.value || "";
                const query = new URLSearchParams({ page: ordersPagination.page, per_page: 25 });
                if (status) query.set("status", status);
                if (search) query.set("search", search);
                const dateFrom = document.getElementById("order-date-from")?.value || "";
                const dateTo = document.getElementById("order-date-to")?.value || "";
                const sort = document.getElementById("order-sort")?.value || "date";
                if (dateFrom) query.set("date_from", dateFrom);
                if (dateTo) query.set("date_to", dateTo + "T23:59:59");
                query.set("sort", sort);
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
                    const previousSnapshot = notificationSnapshot;
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
                    notificationSnapshot = snapshotDashboard(dashboardData);
                    detectDashboardEvents(previousSnapshot, notificationSnapshot);
                    refreshUI();
                    hideProgress();
                    setRealtimeStatus(true);
                    updateOrdersPagination();
                    updateInventoryPagination();
                    if (!silent) showToast("Données actualisées");
                } else {
                    setRealtimeStatus(false);
                    if (!silent) showToast("Échec de l'actualisation des données", "error");
                }
            } catch (err) {
                setRealtimeStatus(false);
                hideProgress();
                if (!silent) showToast("Erreur réseau lors de l'actualisation", "error");
            } finally {
                realtimeRequestRunning = false;
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

        async function offerAction(action, offerId, confirmation) {
            if (confirmation && !confirm(confirmation)) return;
            const params = new URLSearchParams({ action, offer_id: offerId });
            try {
                const res = await fetch("/admin", {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: params
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || "Action impossible");
                showToast("Offre mise à jour");
                await refreshDashboardData();
            } catch (err) {
                showToast(err.message || "Erreur réseau", "error");
            }
        }

        function toggleOffer(offerId) {
            return offerAction("toggle_offer", offerId);
        }

        function duplicateOffer(offerId) {
            return offerAction("duplicate_offer", offerId, "Dupliquer cette offre sans copier son inventaire ?");
        }

        function openAddOfferModal(serviceId = null) {
            const select = document.getElementById("add-offer-service-id");
            const services = dashboardData.services || [];
            select.innerHTML = services.length
                ? services.map(service => `<option value="${service.id}">${escapeHtml(service.name)}</option>`).join("")
                : '<option value="">Catalogue par defaut</option>';
            if (serviceId !== null) select.value = String(serviceId);
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
                        <div><strong>Portefeuille :</strong> ${Number(customer.wallet_balance || 0).toFixed(2)} ${escapeHtml(dashboardData.currency)}</div>
                        <div><strong>Inscrit le :</strong> ${customer.created_at ? formatDateTime(customer.created_at) : '—'}</div>
                        <div><strong>Dernière activité :</strong> ${customer.last_active_at ? formatDateTime(customer.last_active_at) : 'Jamais'}</div>
                        <div><strong>Interactions :</strong> ${customer.interaction_count || 0}</div>
                        <div><strong>Commandes :</strong> ${customer.order_count || 0}</div>
                        <div><strong>Payées :</strong> ${customer.paid_order_count || 0}</div>
                        <div><strong>Total dépensé :</strong> ${(customer.total_spent || 0).toFixed(2)} ${escapeHtml(dashboardData.currency)}</div>
                        <div><strong>Filleuls :</strong> ${customer.referral_count || 0}</div>
                    </div>
                    <div class="service-card" style="margin:18px 0;">
                        <h4 style="margin-bottom:12px;">Gérer le portefeuille</h4>
                        <form onsubmit="adjustCustomerWallet(event, ${customer.telegram_id})" style="display:grid;grid-template-columns:minmax(140px,180px) 1fr auto;gap:10px;align-items:end;">
                            <div class="form-group" style="margin:0;">
                                <label>Montant (${escapeHtml(dashboardData.currency)})</label>
                                <input name="amount" type="number" step="0.01" min="-10000" max="10000" required placeholder="+10 ou -5">
                            </div>
                            <div class="form-group" style="margin:0;">
                                <label>Motif</label>
                                <input name="reason" maxlength="500" placeholder="Bonus, correction, remboursement...">
                            </div>
                            <button class="btn btn-primary" type="submit">Appliquer</button>
                        </form>
                        <p class="muted" style="margin-top:8px;">Montant positif pour créditer, négatif pour débiter. Le solde ne peut pas devenir négatif.</p>
                    </div>
                    <h4>Commandes récentes</h4><ul>${orders}</ul>
                    <h4>Tickets</h4><ul>${tickets}</ul>`;
                openModal("customer-detail-modal");
            } catch (err) {
                showToast(err.message || "Erreur réseau", "error");
            }
        }

        async function adjustCustomerWallet(event, userId) {
            event.preventDefault();
            const form = event.target;
            const amount = Number(form.elements.amount.value);
            if (!Number.isFinite(amount) || amount === 0 || Math.abs(amount) > 10000) {
                showToast("Saisissez un montant valide entre -10 000 et 10 000", "error");
                return;
            }
            const verb = amount > 0 ? "créditer" : "débiter";
            if (!confirm(`Confirmer : ${verb} ${Math.abs(amount).toFixed(2)} ${dashboardData.currency} pour l'utilisateur ${userId} ?`)) return;
            const params = new URLSearchParams({
                action: "adjust_user_wallet",
                user_id: userId,
                amount: amount.toFixed(2),
                reason: form.elements.reason.value || "",
            });
            try {
                const res = await fetch("/admin", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-Dashboard-Write-Token": dashboardWriteToken,
                    },
                    body: params,
                });
                const payload = await res.json();
                if (!res.ok || !payload.ok) throw new Error(payload.error || "Modification impossible");
                showToast(`Nouveau solde : ${Number(payload.balance).toFixed(2)} ${dashboardData.currency}`);
                closeModal("customer-detail-modal");
                await refreshDashboardData();
            } catch (err) {
                showToast(err.message || "Erreur réseau", "error");
            }
        }

        async function viewOrderDetail(orderId) {
            const order = dashboardData.orders.find(o => o.id === orderId);
            if (!order) return;

            const body = document.getElementById("order-detail-body");
            const statusOptions = ORDER_STATUSES.map(status =>
                `<option value="${status}" ${status === order.status ? "selected" : ""}>${status}</option>`
            ).join("");
            body.innerHTML = `
                <div style="display:flex; flex-direction:column; gap:16px;">
                    <div><strong>ID Commande:</strong> #${order.id}</div>
                    <div><strong>Date:</strong> ${formatDateTime(order.created_at)}</div>
                    <div><strong>Client (Telegram ID):</strong> <code>${order.user_id}</code></div>
                    <div><strong>Produit:</strong> ${escapeHtml(order.service_name || "")} - ${escapeHtml(order.offer_name || "")}</div>
                    <div><strong>Verification:</strong> <code>${escapeHtml(order.verify_method || "-")}</code></div>
                    <form id="order-admin-form" onsubmit="updateOrderAdmin(event, ${order.id})" style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:12px;">
                        <div class="form-group"><label>Statut</label><select name="status">${statusOptions}</select></div>
                        <div class="form-group"><label>TXID</label><input name="txid" value="${escapeHtml(order.txid || "")}" placeholder="Transaction ID"></div>
                        <div class="form-group"><label>Quantite</label><input type="number" min="1" name="qty" value="${order.qty || 1}"></div>
                        <div class="form-group"><label>Prix unitaire</label><input type="number" min="0" step="0.01" name="unit_price" value="${order.unit_price ?? 0}"></div>
                        <div class="form-group"><label>Total</label><input type="number" min="0" step="0.01" name="total_price" value="${order.total_price ?? 0}"></div>
                        <div class="form-group" style="grid-column:1 / -1;"><label>Notes admin</label><textarea name="admin_note" id="order-admin-note" rows="3" placeholder="Notes optionnelles...">${escapeHtml(order.admin_note || "")}</textarea></div>
                        <button class="btn btn-primary" type="submit">Enregistrer la commande</button>
                    </form>
                    <div class="form-group">
                        <label>Livraison manuelle</label>
                        <textarea id="manual-delivery-text" rows="4" placeholder="Contenu a envoyer au client...">${escapeHtml(order.delivery_text || "")}</textarea>
                        <button class="btn btn-primary" style="margin-top:8px;" onclick="manualDeliverOrder(${order.id})">Livrer manuellement</button>
                    </div>
                    <div style="display:flex; flex-wrap:wrap; gap:12px; margin-top:12px;">
                        ${order.status === 'awaiting_verification' || order.status === 'pending_payment' || order.status === 'manual_review' ? `
                            <button class="btn btn-primary" onclick="confirmPaymentManual(${order.id})">Confirmer paiement</button>
                        ` : ''}
                        ${order.status !== 'cancelled' && order.status !== 'refunded' ? `
                            <button class="btn btn-danger" onclick="cancelOrder(${order.id})">Annuler commande</button>
                        ` : ''}
                        ${['awaiting_verification', 'verification_failed', 'manual_review'].includes(order.status) ? `
                            <button class="btn btn-secondary" onclick="orderAction('reset_order', ${order.id})">Remettre en attente</button>
                        ` : ''}
                        ${['paid', 'payment_confirmed', 'preparing_delivery', 'delivered', 'manual_review'].includes(order.status) ? `
                            <button class="btn btn-danger" onclick="orderAction('refund_order', ${order.id}, true)">Rembourser</button>
                        ` : ''}
                        ${order.status === 'delivered' ? `
                            <button class="btn btn-secondary" onclick="orderAction('resend_delivery', ${order.id})">Renvoyer la livraison auto</button>
                        ` : ''}
                        <button class="btn btn-secondary" onclick="messageCustomer(${order.id})">Ecrire au client</button>
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

        async function updateOrderAdmin(event, orderId) {
            event.preventDefault();
            const formData = new FormData(event.target);
            const params = new URLSearchParams();
            params.append("action", "update_order_admin");
            params.append("order_id", orderId);
            for (const pair of formData.entries()) {
                params.append(pair[0], pair[1]);
            }

            try {
                const res = await fetch("/admin", {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: params
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || "Mise a jour impossible");
                showToast("Commande mise a jour");
                closeModal("order-detail-modal");
                await refreshDashboardData();
            } catch (err) {
                showToast(err.message || "Erreur reseau", "error");
            }
        }

        async function manualDeliverOrder(orderId) {
            const content = document.getElementById("manual-delivery-text").value.trim();
            if (!content) {
                showToast("Ajoute le contenu de livraison", "error");
                return;
            }
            if (!confirm("Livrer cette commande et envoyer le contenu au client ?")) return;

            const params = new URLSearchParams({
                action: "manual_deliver_order",
                order_id: orderId,
                delivery_text: content
            });
            try {
                const res = await fetch("/admin", {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: params
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || "Livraison impossible");
                showToast("Commande livree");
                closeModal("order-detail-modal");
                await refreshDashboardData();
            } catch (err) {
                showToast(err.message || "Erreur reseau", "error");
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

        let bulkWalletOperationId = "";

        async function bulkCreditWallets(event) {
            event.preventDefault();
            const form = event.target;
            const amount = Number(document.getElementById("bulk-wallet-amount").value);
            const confirmation = document.getElementById("bulk-wallet-confirmation").value.trim();
            if (!Number.isFinite(amount) || amount < 0.01 || amount > 10000) {
                showToast("Montant invalide (0,01 $ à 10 000 $)", "error");
                return;
            }
            if (confirmation !== "CREDIT ALL") {
                showToast("Saisissez exactement CREDIT ALL", "error");
                return;
            }
            if (!window.confirm(`Ajouter ${amount.toFixed(2)} $ au solde de TOUS les utilisateurs ?`)) {
                return;
            }

            if (!bulkWalletOperationId) {
                const randomPart = window.crypto && window.crypto.randomUUID
                    ? window.crypto.randomUUID().replaceAll("-", "_")
                    : `${Date.now()}_${Math.random().toString(36).slice(2)}`;
                bulkWalletOperationId = `bulk_${randomPart}`;
            }
            const params = new URLSearchParams({
                action: "bulk_credit_wallets",
                amount: amount.toFixed(2),
                confirmation,
                operation_id: bulkWalletOperationId,
            });
            const button = document.getElementById("bulk-wallet-credit-button");
            button.disabled = true;
            button.textContent = "Crédit en cours...";
            try {
                const res = await fetch("/admin", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-Dashboard-Write-Token": dashboardWriteToken,
                    },
                    body: params,
                });
                const payload = await res.json();
                if (!res.ok || !payload.ok) {
                    throw new Error(payload.error || "Le crédit global a échoué");
                }
                showToast(`${payload.credited_count} utilisateur(s) crédité(s) de ${amount.toFixed(2)} $`);
                bulkWalletOperationId = "";
                form.reset();
                await refreshDashboardData();
            } catch (err) {
                showToast(err.message || "Erreur réseau", "error");
            } finally {
                button.disabled = false;
                button.textContent = "Ajouter à tous";
            }
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

        // ═══ PREMIUM ENHANCEMENTS ═══

        // KPI counting animation
        function animateKpiValues() {
            document.querySelectorAll('.kpi-value').forEach(el => {
                const text = el.textContent.trim();
                const match = text.match(/^([\d,.]+)/);
                if (!match) return;
                const raw = match[1].replace(/,/g, '');
                const target = parseFloat(raw);
                if (isNaN(target) || target === 0) return;
                const isDecimal = raw.includes('.');
                const suffix = text.slice(match[0].length);
                el.classList.add('counting');
                const duration = 900;
                const start = performance.now();
                function tick(now) {
                    const elapsed = now - start;
                    const progress = Math.min(elapsed / duration, 1);
                    const eased = 1 - Math.pow(1 - progress, 3);
                    const current = target * eased;
                    el.textContent = (isDecimal ? current.toFixed(2) : Math.round(current)) + suffix;
                    if (progress < 1) requestAnimationFrame(tick);
                    else el.classList.remove('counting');
                }
                requestAnimationFrame(tick);
            });
        }

        // Progress bar control
        function showProgress() {
            const bar = document.getElementById('global-progress');
            const fill = document.getElementById('global-progress-bar');
            if (!bar || !fill) return;
            bar.classList.add('active');
            fill.style.width = '0%';
            setTimeout(() => fill.style.width = '35%', 50);
            setTimeout(() => fill.style.width = '65%', 300);
            setTimeout(() => fill.style.width = '85%', 800);
        }

        function hideProgress() {
            const bar = document.getElementById('global-progress');
            const fill = document.getElementById('global-progress-bar');
            if (!bar || !fill) return;
            fill.style.width = '100%';
            setTimeout(() => {
                bar.classList.remove('active');
                fill.style.width = '0%';
            }, 300);
        }

        // Skeleton loading for KPIs
        function showKpiSkeleton() {
            const container = document.getElementById('kpi-container');
            if (!container) return;
            container.innerHTML = `<div class="kpi-grid">${
                [1,2,3,4].map(() => `<div class="skeleton-kpi skeleton">
                    <div class="skeleton-line w60 skeleton"></div>
                    <div class="skeleton-line lg skeleton"></div>
                    <div class="skeleton-line w80 skeleton"></div>
                </div>`).join('')
            }</div>`;
        }

        // Real-time clock
        function updateClock() {
            const el = document.getElementById('clock-time');
            if (el) el.textContent = new Date().toLocaleTimeString('fr-FR', {hour:'2-digit',minute:'2-digit',second:'2-digit'});
        }
        setInterval(updateClock, 1000);
        updateClock();

        // Scroll-to-top
        const scrollBtn = document.getElementById('scroll-to-top');
        if (scrollBtn) {
            const mainEl = document.querySelector('main');
            (mainEl || window).addEventListener('scroll', () => {
                const scrollY = mainEl ? mainEl.scrollTop : window.scrollY;
                scrollBtn.classList.toggle('visible', scrollY > 400);
            }, {passive: true});
            scrollBtn.addEventListener('click', () => {
                (mainEl || window).scrollTo({top: 0, behavior: 'smooth'});
            });
        }

        // Escape key to close modals
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape') {
                document.querySelectorAll('.modal.active').forEach(m => {
                    m.classList.remove('active');
                });
            }
        });

        // Keyboard shortcuts: Ctrl+1 to Ctrl+9 for tab navigation
        document.addEventListener('keydown', e => {
            if (!e.ctrlKey || e.shiftKey || e.altKey || e.metaKey) return;
            const num = parseInt(e.key);
            if (num >= 1 && num <= 9) {
                const tabs = document.querySelectorAll('nav a[data-tab]');
                if (tabs[num - 1]) {
                    e.preventDefault();
                    tabs[num - 1].click();
                }
            }
        });

        // Button ripple effect
        document.addEventListener('click', e => {
            const btn = e.target.closest('.btn');
            if (!btn) return;
            const rect = btn.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const ripple = document.createElement('span');
            ripple.className = 'ripple-circle';
            ripple.style.cssText = `width:${size}px;height:${size}px;left:${e.clientX - rect.left - size/2}px;top:${e.clientY - rect.top - size/2}px`;
            btn.appendChild(ripple);
            ripple.addEventListener('animationend', () => ripple.remove());
        });

        // Hook into existing refreshDashboardData to show progress
        const _originalRefreshDashboardData = typeof refreshDashboardData === 'function' ? refreshDashboardData : null;
        if (_originalRefreshDashboardData) {
            // We patch the refreshUI function to trigger KPI animation
            const _origRefreshUI = refreshUI;
            refreshUI = function() {
                _origRefreshUI();
                setTimeout(animateKpiValues, 50);
            };
        }

        // Run initial animations after first render
        setTimeout(animateKpiValues, 600);

    