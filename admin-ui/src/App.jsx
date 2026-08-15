import { useCallback, useEffect, useMemo, useState } from "react";
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
  Settings,
  ShoppingBag,
  Store,
  Users,
  X,
} from "lucide-react";

const NAV_ITEMS = [
  { id: "overview", label: "Vue d’ensemble", icon: LayoutDashboard, legacy: "/admin" },
  { id: "orders", label: "Commandes", icon: ClipboardList, legacy: "/admin/orders" },
  { id: "catalog", label: "Catalogue", icon: ShoppingBag, legacy: "/admin/catalog" },
  { id: "api-products", label: "Produits API", icon: Cloud, legacy: "/admin/api-products" },
  { id: "inventory", label: "Inventaire", icon: Boxes, legacy: "/admin/inventory" },
  { id: "customers", label: "Clients", icon: Users, legacy: "/admin/customers" },
  { id: "support", label: "Support", icon: Headphones, legacy: "/admin/support" },
  { id: "interactions", label: "Interactions", icon: MessageSquareText, legacy: "/admin/interactions" },
  { id: "activity", label: "Activité", icon: Activity, legacy: "/admin/activity" },
  { id: "settings", label: "Paramètres", icon: Settings, legacy: "/admin/settings" },
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
          <div className="brand-mark"><Store size={22} /></div>
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

function Header({ activePage, alertCount, isRefreshing, onMenu, onRefresh }) {
  const current = NAV_ITEMS.find((item) => item.id === activePage) || NAV_ITEMS[0];
  return (
    <header className="topbar">
      <div className="topbar-title">
        <button className="icon-button menu-button" onClick={onMenu} aria-label="Ouvrir le menu"><Menu size={21} /></button>
        <div><span>Administration</span><h1>{current.label}</h1></div>
      </div>
      <div className="topbar-actions">
        <button className="icon-button" onClick={onRefresh} aria-label="Actualiser">
          <RefreshCw size={19} className={isRefreshing ? "spin" : ""} />
        </button>
        <button className="icon-button notification-button" aria-label={`${alertCount} alertes`}>
          <Bell size={19} />{alertCount > 0 && <span>{Math.min(alertCount, 9)}</span>}
        </button>
        <div className="avatar">AD</div>
      </div>
    </header>
  );
}

function StatCard({ label, value, detail, trend, icon: Icon, tone = "cyan" }) {
  const isPositive = Number(trend) >= 0;
  return (
    <article className="stat-card">
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
    </article>
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

function AlertsPanel({ alerts = [] }) {
  return (
    <section className="panel alerts-panel">
      <div className="panel-heading"><div><span className="eyebrow">À surveiller</span><h2>Alertes actives</h2></div><span className="count-chip">{alerts.length}</span></div>
      <div className="alert-list">
        {alerts.length === 0 ? (
          <div className="healthy-state"><div>✓</div><strong>Tout fonctionne normalement</strong><span>Aucune intervention requise.</span></div>
        ) : alerts.slice(0, 5).map((alert, index) => (
          <div className={`alert-row ${alert.severity || "warning"}`} key={`${alert.type}-${index}`}>
            <AlertTriangle size={18} />
            <div><strong>{alert.severity === "error" ? "Action requise" : "Attention"}</strong><span>{alert.message}</span></div>
          </div>
        ))}
      </div>
      {alerts.length > 5 && <button className="text-button">Voir toutes les alertes <ChevronRight size={16} /></button>}
    </section>
  );
}

function RecentOrders({ orders = [], currency, onOpenLegacy }) {
  return (
    <section className="panel orders-panel">
      <div className="panel-heading">
        <div><span className="eyebrow">Temps réel</span><h2>Commandes récentes</h2></div>
        <button className="text-button" onClick={onOpenLegacy}>Tout afficher <ChevronRight size={16} /></button>
      </div>
      <div className="table-scroll">
        <table>
          <thead><tr><th>Commande</th><th>Client</th><th>Montant</th><th>Statut</th><th>Date</th></tr></thead>
          <tbody>
            {orders.slice(0, 6).map((order) => (
              <tr key={order.id}>
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

function ServicePanel({ services = [], currency }) {
  const ranked = [...services].sort((a, b) => Number(b.total_revenue || 0) - Number(a.total_revenue || 0)).slice(0, 5);
  const max = Math.max(...ranked.map((service) => Number(service.total_revenue || 0)), 1);
  return (
    <section className="panel service-panel">
      <div className="panel-heading"><div><span className="eyebrow">Catalogue</span><h2>Services performants</h2></div><PackageSearch size={20} /></div>
      <div className="service-list">
        {ranked.map((service) => (
          <div className="service-row" key={service.id}>
            <div className="service-avatar">{initials(service.name)}</div>
            <div className="service-info"><strong>{service.name}</strong><span>{service.total_sales || 0} vente(s) · {service.total_stock || 0} en stock</span><div><i style={{ width: `${(Number(service.total_revenue || 0) / max) * 100}%` }} /></div></div>
            <strong>{formatMoney(service.total_revenue, currency)}</strong>
          </div>
        ))}
        {ranked.length === 0 && <div className="empty-cell">Aucun service configuré</div>}
      </div>
    </section>
  );
}

function Overview({ data, onLegacy }) {
  const summary = data.summary || {};
  const currency = data.currency || "USDT";
  return (
    <>
      <div className="welcome-row">
        <div><span className="eyebrow">Centre de contrôle</span><h2>Bonjour, Admin</h2><p>Voici ce qui se passe dans votre boutique aujourd’hui.</p></div>
        <a className="primary-button" href={`https://t.me/${data.bot_username || "blackmarketa_bot"}`} target="_blank" rel="noreferrer">Ouvrir le bot <ChevronRight size={17} /></a>
      </div>

      <div className="stats-grid">
        <StatCard label="Revenu aujourd’hui" value={formatMoney(summary.revenue_today, currency)} detail=" vs hier" trend={summary.revenue_yesterday ? ((summary.revenue_day_delta / summary.revenue_yesterday) * 100).toFixed(1) : 0} icon={CircleDollarSign} tone="cyan" />
        <StatCard label="Commandes" value={summary.orders_today || 0} detail=" aujourd’hui" trend={summary.orders_yesterday ? ((summary.orders_day_delta / summary.orders_yesterday) * 100).toFixed(1) : 0} icon={ShoppingBag} tone="violet" />
        <StatCard label="Nouveaux clients" value={summary.new_users_today || 0} detail=" cette semaine" trend={summary.users_7d_change_pct || 0} icon={Users} tone="green" />
        <StatCard label="Stock disponible" value={summary.available_inventory || 0} detail={`${summary.low_stock_offers || 0} offre(s) faible(s)`} icon={Database} tone="amber" />
      </div>

      <div className="dashboard-grid">
        <RevenueChart data={summary} currency={currency} />
        <AlertsPanel alerts={data.alerts} />
        <RecentOrders orders={data.orders} currency={currency} onOpenLegacy={() => onLegacy("orders")} />
        <ServicePanel services={data.services} currency={currency} />
      </div>
    </>
  );
}

function MigrationPage({ page }) {
  const item = NAV_ITEMS.find((entry) => entry.id === page) || NAV_ITEMS[0];
  const Icon = item.icon;
  return (
    <section className="migration-panel">
      <div className="migration-icon"><Icon size={28} /></div>
      <span className="eyebrow">Migration React en cours</span>
      <h2>{item.label}</h2>
      <p>Cette section reste disponible dans le tableau de bord actuel pendant que nous la reconstruisons dans React.</p>
      <a className="primary-button" href={item.legacy}>Ouvrir la section actuelle <ChevronRight size={17} /></a>
    </section>
  );
}

function LoadingState() {
  return <div className="loading-state"><div className="loader" /><strong>Chargement du centre de contrôle…</strong><span>Connexion sécurisée aux données du bot.</span></div>;
}

function ErrorState({ message, onRetry }) {
  return <div className="loading-state error-state"><AlertTriangle size={32} /><strong>Impossible de charger le dashboard</strong><span>{message}</span><button className="primary-button" onClick={onRetry}>Réessayer</button></div>;
}

export default function App() {
  const initialPage = window.location.pathname.replace(/^\/admin-v2\/?/, "").split("/")[0] || "overview";
  const [activePage, setActivePage] = useState(NAV_ITEMS.some((item) => item.id === initialPage) ? initialPage : "overview");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

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
    const handlePopState = () => {
      const page = window.location.pathname.replace(/^\/admin-v2\/?/, "").split("/")[0] || "overview";
      setActivePage(NAV_ITEMS.some((item) => item.id === page) ? page : "overview");
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const navigate = (page) => {
    setActivePage(page);
    setMobileOpen(false);
    window.history.pushState({}, "", page === "overview" ? "/admin-v2" : `/admin-v2/${page}`);
  };

  const alertCount = useMemo(() => data?.alerts?.length || 0, [data]);

  return (
    <div className="app-shell">
      <Sidebar activePage={activePage} data={data} mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} onNavigate={navigate} />
      <div className="main-shell">
        <Header activePage={activePage} alertCount={alertCount} isRefreshing={refreshing} onMenu={() => setMobileOpen(true)} onRefresh={() => loadData(true)} />
        <main className="content">
          {loading ? <LoadingState /> : error ? <ErrorState message={error} onRetry={() => loadData()} /> : activePage === "overview" ? <Overview data={data} onLegacy={(page) => window.location.assign(NAV_ITEMS.find((item) => item.id === page)?.legacy || "/admin")} /> : <MigrationPage page={activePage} />}
        </main>
      </div>
    </div>
  );
}
