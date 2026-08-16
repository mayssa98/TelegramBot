import { useCallback, useEffect, useMemo, useState } from "react";
import AdminPage from "./AdminPages";
import {
  Activity,
  AlertTriangle,
  Bell,
  Boxes,
  ChevronRight,
  CircleDollarSign,
  ClipboardList,
  Cloud,
  Database,
  Headphones,
  LayoutDashboard,
  Menu,
  MessageSquareText,
  PackageSearch,
  RefreshCw,
  Search,
  ShieldCheck,
  Settings,
  ShoppingBag,
  Users,
  Wrench,
  X,
} from "lucide-react";

const NAV_ITEMS = [
  { id: "overview", label: "Vue d’ensemble", icon: LayoutDashboard },
  { id: "orders", label: "Commandes", icon: ClipboardList },
  { id: "catalog", label: "Catalogue", icon: ShoppingBag },
  { id: "api-products", label: "Produits API", icon: Cloud },
  { id: "inventory", label: "Inventaire", icon: Boxes },
  { id: "customers", label: "Clients", icon: Users },
  { id: "support", label: "Support", icon: Headphones },
  { id: "interactions", label: "Interactions", icon: MessageSquareText },
  { id: "activity", label: "Activité", icon: Activity },
  { id: "settings", label: "Paramètres", icon: Settings },
];

const STATUS_LABELS = {
  pending_payment: "Paiement en attente",
  awaiting_verification: "À vérifier",
  manual_review: "Révision manuelle",
  paid: "Payée",
  payment_confirmed: "Confirmée",
  delivered: "Livrée",
  cancelled: "Annulée",
};

function formatMoney(value, currency = "USDT") {
  return `${new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 }).format(Number(value || 0))} ${currency}`;
}

function formatDate(value) {
  if (!value) return "—";
  const date = typeof value === "number" ? new Date(value * 1000) : new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : new Intl.DateTimeFormat("fr-FR", { dateStyle: "short", timeStyle: "short" }).format(date);
}

function initials(value = "BM") {
  return value
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function Sidebar({ activePage, data, mobileOpen, onClose, onNavigate }) {
  const pendingOrders = data?.summary?.pending_orders || 0;
  const openTickets = data?.summary?.open_tickets || 0;

  return (
    <>
      <button
        className={`sidebar-backdrop ${mobileOpen ? "is-open" : ""}`}
        aria-label="Fermer le menu"
        onClick={onClose}
      />
      <aside className={`sidebar ${mobileOpen ? "is-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark">{initials(data?.shop_name || "BlackMarket")}</div>
          <div><strong>{data?.shop_name || "BlackMarket"}</strong><span>Control Center</span></div>
          <button className="icon-button mobile-only" onClick={onClose} aria-label="Fermer"><X size={20} /></button>
        </div>

        <nav className="nav-list" aria-label="Navigation principale">
          <span className="nav-heading">Espace de travail</span>
          {NAV_ITEMS.map(({ id, label, icon: Icon }) => {
            const count = id === "orders" ? pendingOrders : id === "support" ? openTickets : 0;
            return (
              <button
                key={id}
                className={`nav-item ${activePage === id ? "active" : ""}`}
                onClick={() => onNavigate(id)}
              >
                <Icon size={19} strokeWidth={1.8} />
                <span>{label}</span>
                {count > 0 && <small>{count}</small>}
              </button>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="connection-dot" />
          <div><strong>Bot connecté</strong><span>@{data?.bot_username || "blackmarketa_bot"}</span></div>
        </div>
      </aside>
    </>
  );
}

function Header({ activePage, alertCount, busyAction, isRefreshing, onMenu, onNotifications, onRefresh, onRepairTelegram, onSearch, onTestBinance }) {
  const current = NAV_ITEMS.find((item) => item.id === activePage) || NAV_ITEMS[0];
  return (
    <header className="topbar">
      <div className="topbar-title">
        <button className="icon-button menu-button" onClick={onMenu} aria-label="Ouvrir le menu"><Menu size={21} /></button>
        <div><span>Administration</span><h1>{current.label}</h1></div>
      </div>
      <button className="global-search-trigger" onClick={onSearch}>
        <Search size={17} />
        <span>Rechercher commandes, produits ou clients…</span>
        <kbd>Ctrl K</kbd>
      </button>
      <div className="topbar-actions">
        <button className="header-action" onClick={onRepairTelegram} disabled={Boolean(busyAction)}>
          <Wrench size={16} className={busyAction === "telegram" ? "spin" : ""} /><span>Réparer Telegram</span>
        </button>
        <button className="header-action" onClick={onTestBinance} disabled={Boolean(busyAction)}>
          <ShieldCheck size={16} className={busyAction === "binance" ? "spin" : ""} /><span>Tester Binance</span>
        </button>
        <button className="icon-button" onClick={onRefresh} aria-label="Actualiser" title="Actualiser les données">
          <RefreshCw size={19} className={isRefreshing ? "spin" : ""} />
        </button>
        <button className="icon-button notification-button" onClick={onNotifications} aria-label={`${alertCount} alertes`}>
          <Bell size={19} />{alertCount > 0 && <span>{Math.min(alertCount, 9)}</span>}
        </button>
        <div className="avatar">AD</div>
      </div>
    </header>
  );
}

function StatCard({ label, value, detail, trend, icon: Icon, onClick, tone = "cyan" }) {
  const isPositive = Number(trend) >= 0;
  return (
    <button className="stat-card" onClick={onClick}>
      <div className={`stat-icon ${tone}`}><Icon size={21} /></div>
      <div className="stat-copy">
        <span>{label}</span>
        <strong>{value}</strong>
        <small>
          {trend !== undefined && trend !== null && (
            <b className={isPositive ? "positive" : "negative"}>{isPositive ? "+" : ""}{trend}%</b>
          )}
          {detail}
        </small>
      </div>
      <ChevronRight className="stat-arrow" size={17} />
    </button>
  );
}

function RevenueChart({ data, currency }) {
  const today = Number(data?.revenue_today || 0);
  const week = Number(data?.revenue_7d || 0);
  const month = Number(data?.revenue_30d || 0);
  const values = [week * 0.08, week * 0.11, week * 0.09, week * 0.19, week * 0.14, week * 0.17, today || week * 0.22];
  const max = Math.max(...values, 1);
  const points = values.map((value, index) => `${index * 100},${116 - (value / max) * 92}`).join(" ");

  return (
    <section className="panel revenue-panel">
      <div className="panel-heading">
        <div><span className="eyebrow">Performance</span><h2>Chiffre d’affaires</h2></div>
        <div className="chart-total"><span>30 derniers jours</span><strong>{formatMoney(month, currency)}</strong></div>
      </div>
      <div className="chart-wrap" aria-label="Aperçu du chiffre d’affaires sur sept jours">
        <svg viewBox="0 0 600 140" role="img" preserveAspectRatio="none">
          <defs>
            <linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#22d3ee" stopOpacity=".3" />
              <stop offset="100%" stopColor="#22d3ee" stopOpacity="0" />
            </linearGradient>
          </defs>
          {[24, 54, 84, 114].map((y) => <line key={y} x1="0" x2="600" y1={y} y2={y} className="grid-line" />)}
          <polygon points={`0,140 ${points} 600,140`} fill="url(#chartFill)" />
          <polyline points={points} fill="none" className="chart-line" />
        </svg>
        <div className="chart-labels"><span>Lun</span><span>Mar</span><span>Mer</span><span>Jeu</span><span>Ven</span><span>Sam</span><span>Aujourd’hui</span></div>
      </div>
      <div className="chart-summary">
        <div><span>Aujourd’hui</span><strong>{formatMoney(today, currency)}</strong></div>
        <div><span>7 jours</span><strong>{formatMoney(week, currency)}</strong></div>
        <div><span>Conversion</span><strong>{Number(data?.conversion_rate || 0).toFixed(1)}%</strong></div>
      </div>
    </section>
  );
}

function AlertsPanel({ alerts = [], onSelect }) {
  return (
    <section className="panel alerts-panel">
      <div className="panel-heading"><div><span className="eyebrow">À surveiller</span><h2>Alertes actives</h2></div><span className="count-chip">{alerts.length}</span></div>
      <div className="alert-list">
        {alerts.length === 0 ? (
          <div className="healthy-state"><div>✓</div><strong>Tout fonctionne normalement</strong><span>Aucune intervention requise.</span></div>
        ) : alerts.slice(0, 5).map((alert, index) => (
          <button className={`alert-row ${alert.severity || "warning"}`} key={`${alert.type}-${index}`} onClick={() => onSelect(alert)}>
            <AlertTriangle size={18} />
            <div><strong>{alert.severity === "error" ? "Action requise" : "Attention"}</strong><span>{alert.message}</span></div>
            <ChevronRight size={16} />
          </button>
        ))}
      </div>
      {alerts.length > 5 && <button className="text-button">Voir toutes les alertes <ChevronRight size={16} /></button>}
    </section>
  );
}

function RecentOrders({ orders = [], currency, onOpenLegacy, onSelectOrder }) {
  return (
    <section className="panel orders-panel">
      <div className="panel-heading">
        <div><span className="eyebrow">Activité récente</span><h2>Commandes récentes</h2></div>
        <button className="text-button" onClick={onOpenLegacy}>Tout afficher <ChevronRight size={16} /></button>
      </div>
      <div className="table-scroll">
        <table>
          <thead><tr><th>Commande</th><th>Client</th><th>Montant</th><th>Statut</th><th>Date</th></tr></thead>
          <tbody>
            {orders.slice(0, 6).map((order) => (
              <tr key={order.id} onClick={() => onSelectOrder(order)} tabIndex="0" onKeyDown={(event) => event.key === "Enter" && onSelectOrder(order)}>
                <td><strong>#{order.id}</strong><span>{order.offer_name || order.service_name || "Commande"}</span></td>
                <td>{order.username ? `@${order.username}` : order.user_id || "—"}</td>
                <td><strong>{formatMoney(order.total_price, currency)}</strong></td>
                <td><span className={`status ${order.status || "pending"}`}>{STATUS_LABELS[order.status] || order.status || "—"}</span></td>
                <td>{formatDate(order.created_at)}</td>
              </tr>
            ))}
            {orders.length === 0 && <tr><td colSpan="5" className="empty-cell">Aucune commande récente</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ServicePanel({ services = [], currency, onSelect }) {
  const ranked = [...services].sort((a, b) => Number(b.total_revenue || 0) - Number(a.total_revenue || 0)).slice(0, 5);
  const max = Math.max(...ranked.map((service) => Number(service.total_revenue || 0)), 1);
  return (
    <section className="panel service-panel">
      <div className="panel-heading"><div><span className="eyebrow">Catalogue</span><h2>Services performants</h2></div><PackageSearch size={20} /></div>
      <div className="service-list">
        {ranked.map((service) => (
          <button className="service-row" key={service.id} onClick={() => onSelect(service)}>
            <div className="service-avatar">{initials(service.name)}</div>
            <div className="service-info"><strong>{service.name}</strong><span>{service.total_sales || 0} vente(s) · {service.total_stock || 0} en stock</span><div><i style={{ width: `${(Number(service.total_revenue || 0) / max) * 100}%` }} /></div></div>
            <strong>{formatMoney(service.total_revenue, currency)}</strong>
            <ChevronRight size={15} />
          </button>
        ))}
        {ranked.length === 0 && <div className="empty-cell">Aucun service configuré</div>}
      </div>
    </section>
  );
}

function Overview({ data, onNavigate, onOpenBot }) {
  const summary = data.summary || {};
  const currency = data.currency || "USDT";
  return (
    <>
      <div className="welcome-row">
        <div><span className="eyebrow">Centre de contrôle</span><h2>Bonjour, Admin</h2><p>Voici ce qui se passe dans votre boutique aujourd’hui.</p></div>
        <button className="primary-button" onClick={onOpenBot}>Ouvrir le bot <ChevronRight size={17} /></button>
      </div>

      <div className="stats-grid">
        <StatCard label="Revenu aujourd’hui" value={formatMoney(summary.revenue_today, currency)} detail=" vs hier" trend={summary.revenue_yesterday ? ((summary.revenue_day_delta / summary.revenue_yesterday) * 100).toFixed(1) : 0} icon={CircleDollarSign} onClick={() => onNavigate("orders")} tone="cyan" />
        <StatCard label="Commandes" value={summary.orders_today || 0} detail=" aujourd’hui" trend={summary.orders_yesterday ? ((summary.orders_day_delta / summary.orders_yesterday) * 100).toFixed(1) : 0} icon={ShoppingBag} onClick={() => onNavigate("orders")} tone="violet" />
        <StatCard label="Nouveaux clients" value={summary.new_users_today || 0} detail=" cette semaine" trend={summary.users_7d_change_pct || 0} icon={Users} onClick={() => onNavigate("customers")} tone="green" />
        <StatCard label="Stock disponible" value={summary.available_inventory || 0} detail={`${summary.low_stock_offers || 0} offre(s) faible(s)`} icon={Database} onClick={() => onNavigate("inventory")} tone="amber" />
      </div>

      <div className="dashboard-grid">
        <RevenueChart data={summary} currency={currency} />
        <AlertsPanel alerts={data.alerts} onSelect={(alert) => onNavigate(alert.type?.includes("stock") ? "inventory" : alert.type?.includes("ticket") ? "support" : "orders")} />
        <RecentOrders orders={data.orders} currency={currency} onOpenLegacy={() => onNavigate("orders")} onSelectOrder={() => onNavigate("orders")} />
        <ServicePanel services={data.services} currency={currency} onSelect={() => onNavigate("catalog")} />
      </div>
    </>
  );
}

function SearchDialog({ data, onClose, onNavigate }) {
  const [query, setQuery] = useState("");
  const normalized = query.trim().toLowerCase();
  const results = useMemo(() => {
    if (!normalized) return [];
    const orders = (data.orders || []).filter((item) => `${item.id} ${item.user_id} ${item.username || ""} ${item.offer_name || ""}`.toLowerCase().includes(normalized)).slice(0, 4).map((item) => ({ id: `order-${item.id}`, title: `Commande #${item.id}`, detail: item.offer_name || `Client ${item.user_id}`, page: "orders", icon: ClipboardList }));
    const customers = (data.users || []).filter((item) => `${item.telegram_id || item.user_id || ""} ${item.username || ""} ${item.first_name || ""} ${item.last_name || ""}`.toLowerCase().includes(normalized)).slice(0, 4).map((item) => ({ id: `customer-${item.telegram_id || item.user_id}`, title: item.username ? `@${item.username}` : `Client ${item.telegram_id || item.user_id}`, detail: [item.first_name, item.last_name].filter(Boolean).join(" ") || "Client Telegram", page: "customers", icon: Users }));
    const services = (data.services || []).filter((item) => `${item.name || ""} ${(item.offers || []).map((offer) => offer.name).join(" ")}`.toLowerCase().includes(normalized)).slice(0, 4).map((item) => ({ id: `service-${item.id}`, title: item.name, detail: `${item.offer_count || 0} offre(s)`, page: "catalog", icon: ShoppingBag }));
    return [...orders, ...customers, ...services].slice(0, 8);
  }, [data, normalized]);

  useEffect(() => {
    const closeOnEscape = (event) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return (
    <div className="dialog-backdrop" onMouseDown={onClose}>
      <section className="search-dialog" role="dialog" aria-modal="true" aria-label="Recherche globale" onMouseDown={(event) => event.stopPropagation()}>
        <div className="search-dialog-input"><Search size={20} /><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Commande, produit, client…" /><button onClick={onClose}><X size={18} /></button></div>
        <div className="search-results">
          {!normalized && <div className="search-empty"><Search size={25} /><strong>Recherche globale</strong><span>Saisissez un identifiant, un nom ou un produit.</span></div>}
          {normalized && results.length === 0 && <div className="search-empty"><strong>Aucun résultat</strong><span>Essayez un autre terme de recherche.</span></div>}
          {results.map(({ id, title, detail, page, icon: Icon }) => (
            <button key={id} onClick={() => { onNavigate(page); onClose(); }}><span><Icon size={17} /></span><div><strong>{title}</strong><small>{detail}</small></div><ChevronRight size={16} /></button>
          ))}
        </div>
        <footer><span>↵ ouvrir</span><span>Échap fermer</span></footer>
      </section>
    </div>
  );
}

function NotificationsDrawer({ alerts = [], onClose, onNavigate }) {
  return (
    <div className="drawer-backdrop" onMouseDown={onClose}>
      <aside className="notifications-drawer" onMouseDown={(event) => event.stopPropagation()}>
        <header><div><span className="eyebrow">Centre d’alertes</span><h2>Notifications</h2></div><button className="icon-button" onClick={onClose}><X size={18} /></button></header>
        <div className="drawer-alerts">
          {alerts.length === 0 ? <div className="search-empty"><strong>Aucune alerte</strong><span>Votre boutique fonctionne normalement.</span></div> : alerts.map((alert, index) => (
            <button key={`${alert.type}-${index}`} onClick={() => { onNavigate(alert.type?.includes("stock") ? "inventory" : alert.type?.includes("ticket") ? "support" : "orders"); onClose(); }} className={alert.severity || "warning"}>
              <span><AlertTriangle size={17} /></span><div><strong>{alert.severity === "error" ? "Action requise" : "Attention"}</strong><small>{alert.message}</small></div><ChevronRight size={16} />
            </button>
          ))}
        </div>
      </aside>
    </div>
  );
}

function Toast({ toast, onClose }) {
  useEffect(() => {
    if (!toast) return undefined;
    const timeout = window.setTimeout(onClose, 4500);
    return () => window.clearTimeout(timeout);
  }, [toast, onClose]);
  if (!toast) return null;
  return <div className={`toast ${toast.type || "success"}`}><span>{toast.type === "error" ? "!" : "✓"}</span><div><strong>{toast.title}</strong><small>{toast.message}</small></div><button onClick={onClose}><X size={15} /></button></div>;
}

function LoadingState() {
  return <div className="loading-state"><div className="loader" /><strong>Chargement du centre de contrôle…</strong><span>Connexion sécurisée aux données du bot.</span></div>;
}

function ErrorState({ message, onRetry }) {
  return <div className="loading-state error-state"><AlertTriangle size={32} /><strong>Impossible de charger le dashboard</strong><span>{message}</span><button className="primary-button" onClick={onRetry}>Réessayer</button></div>;
}

export default function App() {
  const routePage = () => window.location.pathname.replace(/^\/admin(?:-v2)?\/?/, "").split("/")[0] || "overview";
  const initialPage = routePage();
  const [activePage, setActivePage] = useState(NAV_ITEMS.some((item) => item.id === initialPage) ? initialPage : "overview");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [busyAction, setBusyAction] = useState("");
  const [toast, setToast] = useState(null);
  const [actionVersion, setActionVersion] = useState(0);

  const loadData = useCallback(async (background = false) => {
    background ? setRefreshing(true) : setLoading(true);
    setError("");
    try {
      const response = await fetch("/admin/api/data", { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) throw new Error(response.status === 401 ? "Authentification administrateur requise." : `Erreur serveur (${response.status}).`);
      setData(await response.json());
    } catch (requestError) {
      setError(requestError.message || "Une erreur inattendue est survenue.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);
  useEffect(() => {
    const openSearch = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearchOpen(true);
      }
    };
    window.addEventListener("keydown", openSearch);
    return () => window.removeEventListener("keydown", openSearch);
  }, []);
  useEffect(() => {
    const handlePopState = () => {
      const page = routePage();
      setActivePage(NAV_ITEMS.some((item) => item.id === page) ? page : "overview");
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const navigate = (page) => {
    setActivePage(page);
    setMobileOpen(false);
    window.history.pushState({}, "", page === "overview" ? "/admin" : `/admin/${page}`);
  };

  const adminAction = async (params) => {
    try {
      const response = await fetch("/admin", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
        body: new URLSearchParams(Object.entries(params).map(([key, value]) => [key, value == null ? "" : String(value)])),
      });
      const payload = await response.json();
      if (!response.ok || payload.ok === false) throw new Error(payload.message || payload.error || "Action refusée.");
      setToast({ title: "Action enregistrée", message: payload.message || "Les modifications ont été appliquées." });
      await loadData(true);
      setActionVersion((value) => value + 1);
      return payload;
    } catch (actionError) {
      setToast({ type: "error", title: "Action impossible", message: actionError.message });
      return null;
    }
  };

  const runHealthCheck = async (type) => {
    setBusyAction(type);
    try {
      if (type === "telegram") {
        const response = await fetch("/admin", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
          body: new URLSearchParams({ action: "repair_telegram_webhook" }),
        });
        const payload = await response.json();
        if (!response.ok || payload.ok === false) throw new Error(payload.message || payload.error || "Réparation refusée.");
        setToast({ title: "Telegram réparé", message: payload.message || "Le webhook est correctement configuré." });
      } else {
        const response = await fetch("/admin/api/binance-health", { credentials: "same-origin", cache: "no-store" });
        const payload = await response.json();
        if (!response.ok || payload.ok === false) throw new Error(payload.message || payload.error || "Connexion Binance indisponible.");
        setToast({ title: "Binance opérationnel", message: payload.message || "La connexion API fonctionne correctement." });
      }
    } catch (actionError) {
      setToast({ type: "error", title: type === "telegram" ? "Échec Telegram" : "Échec Binance", message: actionError.message });
    } finally {
      setBusyAction("");
    }
  };

  const alertCount = useMemo(() => data?.alerts?.length || 0, [data]);

  return (
    <div className="app-shell">
      <Sidebar activePage={activePage} data={data} mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} onNavigate={navigate} />
      <div className="main-shell">
        <Header activePage={activePage} alertCount={alertCount} busyAction={busyAction} isRefreshing={refreshing} onMenu={() => setMobileOpen(true)} onNotifications={() => setNotificationsOpen(true)} onRefresh={() => loadData(true)} onRepairTelegram={() => runHealthCheck("telegram")} onSearch={() => setSearchOpen(true)} onTestBinance={() => runHealthCheck("binance")} />
        <main className="content">
          {loading ? <LoadingState /> : error ? <ErrorState message={error} onRetry={() => loadData()} /> : activePage === "overview" ? <Overview data={data} onNavigate={navigate} onOpenBot={() => window.open(`https://t.me/${data.bot_username || "blackmarketa_bot"}`, "_blank", "noopener,noreferrer")} /> : <AdminPage key={`${activePage}-${actionVersion}`} page={activePage} data={data} onAction={adminAction} onHealthCheck={runHealthCheck} setToast={setToast} />}
        </main>
      </div>
      {searchOpen && data && <SearchDialog data={data} onClose={() => setSearchOpen(false)} onNavigate={navigate} />}
      {notificationsOpen && <NotificationsDrawer alerts={data?.alerts || []} onClose={() => setNotificationsOpen(false)} onNavigate={navigate} />}
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
