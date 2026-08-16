import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Archive,
  Ban,
  Boxes,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleDollarSign,
  Clock3,
  ClipboardList,
  Cloud,
  Copy,
  Database,
  Download,
  Edit3,
  Eye,
  Headphones,
  KeyRound,
  MessageSquareText,
  PackagePlus,
  Plus,
  RefreshCw,
  Search,
  Send,
  Settings,
  ShieldCheck,
  ShoppingBag,
  ToggleLeft,
  ToggleRight,
  TrendingUp,
  Trash2,
  UserRound,
  Users,
  X,
} from "lucide-react";

const STATUS_LABELS = {
  pending_payment: "Paiement en attente",
  awaiting_verification: "À vérifier",
  payment_confirmed: "Paiement confirmé",
  preparing_delivery: "Préparation",
  delivered: "Livrée",
  verification_failed: "Échec de vérification",
  manual_review: "Révision manuelle",
  cancelled: "Annulée",
  refunded: "Remboursée",
  expired: "Expirée",
  paid: "Payée",
  open: "Ouvert",
  waiting_admin: "Attente admin",
  waiting_customer: "Attente client",
  resolved: "Résolu",
  closed: "Fermé",
};

const PROVIDERS = [
  ["mailreader", "MailReader"],
  ["shamekh", "Shamekh’s bot"],
  ["kakao", "Kakao Shop"],
  ["vex", "VEX Reseller"],
  ["canboso", "Canboso"],
];

function money(value, currency = "USDT") {
  return `${new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 }).format(Number(value || 0))} ${currency}`;
}

function date(value) {
  if (!value) return "—";
  const parsed =
    typeof value === "number" ? new Date(value * 1000) : new Date(value);
  return Number.isNaN(parsed.getTime())
    ? "—"
    : new Intl.DateTimeFormat("fr-FR", {
        dateStyle: "short",
        timeStyle: "short",
      }).format(parsed);
}

function PageHeader({ eyebrow, title, description, actions }) {
  return (
    <div className="page-heading">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

function ActionButton({
  children,
  icon: Icon,
  secondary = false,
  danger = false,
  ...props
}) {
  return (
    <button
      className={`action-button ${secondary ? "secondary" : ""} ${danger ? "danger" : ""}`}
      {...props}
    >
      {Icon && <Icon size={16} />}
      {children}
    </button>
  );
}

function Modal({ title, children, onClose, wide = false }) {
  return (
    <div className="dialog-backdrop" onMouseDown={onClose}>
      <section
        className={`form-dialog ${wide ? "wide" : ""}`}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <h3>{title}</h3>
          <button onClick={onClose}>
            <X size={19} />
          </button>
        </header>
        <div className="form-dialog-body">{children}</div>
      </section>
    </div>
  );
}

function Field({ label, children, wide = false }) {
  return (
    <label className={`field ${wide ? "wide" : ""}`}>
      <span>{label}</span>
      {children}
    </label>
  );
}

function Empty({
  icon: Icon = Database,
  title = "Aucune donnée",
  text = "Les éléments apparaîtront ici.",
}) {
  return (
    <div className="page-empty">
      <Icon size={28} />
      <strong>{title}</strong>
      <span>{text}</span>
    </div>
  );
}

function FilterBar({
  search,
  setSearch,
  children,
  placeholder = "Rechercher…",
}) {
  return (
    <div className="filter-bar">
      <label>
        <Search size={16} />
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={placeholder}
        />
      </label>
      {children}
    </div>
  );
}

function Pagination({ value, onChange }) {
  if (!value || value.pages <= 1) return null;
  return (
    <div className="pagination">
      <button
        disabled={value.page <= 1}
        onClick={() => onChange(value.page - 1)}
      >
        <ChevronLeft size={16} /> Précédent
      </button>
      <span>
        Page {value.page} sur {value.pages} · {value.total} résultat(s)
      </span>
      <button
        disabled={value.page >= value.pages}
        onClick={() => onChange(value.page + 1)}
      >
        Suivant <ChevronRight size={16} />
      </button>
    </div>
  );
}

function useRemoteList(endpoint, filters) {
  const [result, setResult] = useState({
    items: [],
    page: 1,
    pages: 1,
    total: 0,
  });
  const [loading, setLoading] = useState(true);
  const query = new URLSearchParams(
    Object.entries(filters)
      .filter(([, value]) => value !== "" && value != null)
      .map(([key, value]) => [key, String(value)]),
  ).toString();
  useEffect(() => {
    let active = true;
    setLoading(true);
    fetch(`${endpoint}?${query}`, {
      credentials: "same-origin",
      cache: "no-store",
    })
      .then((response) => {
        if (!response.ok) throw new Error(`Erreur ${response.status}`);
        return response.json();
      })
      .then((payload) => active && setResult(payload))
      .catch(
        () => active && setResult({ items: [], page: 1, pages: 1, total: 0 }),
      )
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [endpoint, query]);
  return [result, loading];
}

function OrderEditor({ order, onAction, onClose, currency }) {
  const [status, setStatus] = useState(order.status || "pending_payment");
  const [note, setNote] = useState(order.admin_note || "");
  const [message, setMessage] = useState("");
  const [delivery, setDelivery] = useState("");
  const submit = async (action, extra = {}) => {
    if (await onAction({ action, order_id: order.id, ...extra })) onClose();
  };
  return (
    <Modal title={`Commande #${order.id}`} onClose={onClose} wide>
      <div className="detail-grid">
        <div>
          <span>Client</span>
          <strong>
            {order.username ? `@${order.username}` : order.user_id}
          </strong>
        </div>
        <div>
          <span>Produit</span>
          <strong>{order.offer_name || order.service_name || "—"}</strong>
        </div>
        <div>
          <span>Montant</span>
          <strong>{money(order.total_price, currency)}</strong>
        </div>
        <div>
          <span>Créée</span>
          <strong>{date(order.created_at)}</strong>
        </div>
      </div>
      <div className="form-grid">
        <Field label="Statut">
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            {Object.entries(STATUS_LABELS)
              .slice(0, 11)
              .map(([value, label]) => (
                <option value={value} key={value}>
                  {label}
                </option>
              ))}
          </select>
        </Field>
        <Field label="Note administrateur">
          <input
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />
        </Field>
        <Field label="Message au client">
          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Message Telegram…"
          />
        </Field>
        <Field label="Contenu de livraison">
          <textarea
            value={delivery}
            onChange={(event) => setDelivery(event.target.value)}
            placeholder="Identifiants ou code…"
          />
        </Field>
      </div>
      <div className="dialog-actions wrap">
        <ActionButton
          icon={Check}
          onClick={() =>
            submit("update_order_admin", { status, admin_note: note })
          }
        >
          Enregistrer
        </ActionButton>
        <ActionButton
          secondary
          icon={Send}
          disabled={!message.trim()}
          onClick={() => submit("message_customer", { message })}
        >
          Envoyer
        </ActionButton>
        <ActionButton
          secondary
          icon={PackagePlus}
          disabled={!delivery.trim()}
          onClick={() =>
            submit("manual_deliver_order", { delivery_text: delivery })
          }
        >
          Livrer
        </ActionButton>
        <ActionButton
          secondary
          icon={RefreshCw}
          onClick={() => submit("reset_order")}
        >
          Réinitialiser
        </ActionButton>
        <ActionButton
          secondary
          icon={Send}
          onClick={() => submit("resend_delivery")}
        >
          Renvoyer
        </ActionButton>
        <ActionButton
          danger
          icon={CircleDollarSign}
          onClick={() =>
            submit("refund_order", {
              reason: note || "Remboursement depuis le dashboard React",
            })
          }
        >
          Rembourser
        </ActionButton>
        <ActionButton
          danger
          icon={X}
          onClick={() =>
            submit("cancel_order", {
              reason: note || "Annulée depuis le dashboard React",
            })
          }
        >
          Annuler
        </ActionButton>
      </div>
    </Modal>
  );
}

function OrdersPage({ data, onAction }) {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState("date");
  const [direction, setDirection] = useState("desc");
  const [selected, setSelected] = useState(null);
  const [result, loading] = useRemoteList("/admin/api/orders", {
    search,
    status,
    page,
    per_page: 25,
    sort,
    direction,
  });
  const analytics = result.analytics || {};
  const daily = analytics.daily || [];
  const chartPoints = useMemo(() => {
    const maximum = Math.max(...daily.map((item) => Number(item.count || 0)), 1);
    return daily.map((item, index) => ({
      ...item,
      x: daily.length <= 1 ? 0 : (index / (daily.length - 1)) * 600,
      y: 142 - (Number(item.count || 0) / maximum) * 112,
    }));
  }, [daily]);
  const statusSegments = useMemo(() => {
    const colors = {
      delivered: "#34d399",
      paid: "#22d3ee",
      payment_confirmed: "#60a5fa",
      cancelled: "#fb7185",
      refunded: "#f97316",
      pending_payment: "#fbbf24",
      manual_review: "#a78bfa",
    };
    return Object.entries(analytics.statuses || {})
      .map(([key, value]) => ({ key, value, color: colors[key] || "#64748b" }))
      .sort((a, b) => b.value - a.value);
  }, [analytics.statuses]);
  const totalStatuses = statusSegments.reduce((sum, item) => sum + item.value, 0);
  let donutCursor = 0;
  const donutBackground = statusSegments.length
    ? `conic-gradient(${statusSegments.map((item) => {
        const start = donutCursor;
        donutCursor += (item.value / totalStatuses) * 100;
        return `${item.color} ${start}% ${donutCursor}%`;
      }).join(", ")})`
    : "conic-gradient(#1c2b3d 0 100%)";
  const toggleSort = (nextSort) => {
    if (sort === nextSort) setDirection((value) => (value === "desc" ? "asc" : "desc"));
    else {
      setSort(nextSort);
      setDirection("desc");
    }
    setPage(1);
  };
  return (
    <>
      <PageHeader
        eyebrow="Ventes"
        title="Commandes"
        description="Suivez les paiements, livraisons et interventions manuelles."
      />
      <section className="order-kpis" aria-label="Statistiques des commandes">
        <article><span className="order-kpi-icon violet"><ClipboardList size={19} /></span><div><small>Total commandes</small><strong>{analytics.total || 0}</strong><em>Volume global</em></div></article>
        <article><span className="order-kpi-icon cyan"><CircleDollarSign size={19} /></span><div><small>Chiffre d'affaires</small><strong>{money(analytics.revenue, data.currency)}</strong><em>Commandes encaissées</em></div></article>
        <article><span className="order-kpi-icon green"><CheckCircle2 size={19} /></span><div><small>Taux de livraison</small><strong>{analytics.success_rate || 0}%</strong><em>{analytics.delivered || 0} livrée(s)</em></div></article>
        <article><span className="order-kpi-icon amber"><Clock3 size={19} /></span><div><small>À traiter</small><strong>{analytics.pending || 0}</strong><em>Action requise</em></div></article>
      </section>
      <section className="order-analytics-grid">
        <article className="data-panel order-trend-card">
          <header><div><span className="eyebrow">Activité</span><h3>Commandes sur 7 jours</h3></div><TrendingUp size={19} /></header>
          <div className="order-line-chart">
            <svg viewBox="0 0 600 160" preserveAspectRatio="none" role="img" aria-label="Courbe des commandes sur 7 jours">
              {[30, 86, 142].map((y) => <line key={y} x1="0" x2="600" y1={y} y2={y} className="order-grid-line" />)}
              {chartPoints.length > 1 && <polygon points={`0,160 ${chartPoints.map((point) => `${point.x},${point.y}`).join(" ")} 600,160`} className="order-area" />}
              {chartPoints.length > 1 && <polyline points={chartPoints.map((point) => `${point.x},${point.y}`).join(" ")} className="order-chart-line" />}
              {chartPoints.map((point) => <circle key={point.date} cx={point.x} cy={point.y} r="4" className="order-chart-dot"><title>{point.count} commande(s)</title></circle>)}
            </svg>
            <div className="order-chart-labels">{daily.map((item) => <span key={item.date}>{new Intl.DateTimeFormat("fr-FR", { weekday: "short" }).format(new Date(`${item.date}T12:00:00`))}</span>)}</div>
          </div>
        </article>
        <article className="data-panel order-status-card">
          <header><div><span className="eyebrow">Répartition</span><h3>Statuts des commandes</h3></div></header>
          <div className="order-status-content">
            <div className="order-donut" style={{ background: donutBackground }}><div><strong>{analytics.total || 0}</strong><span>Total</span></div></div>
            <div className="order-legend">{statusSegments.slice(0, 5).map((item) => <button key={item.key} onClick={() => { setStatus(item.key); setPage(1); }}><i style={{ background: item.color }} /><span>{STATUS_LABELS[item.key] || item.key}</span><strong>{item.value}</strong></button>)}</div>
          </div>
        </article>
      </section>
      <FilterBar
        search={search}
        setSearch={(value) => {
          setSearch(value);
          setPage(1);
        }}
        placeholder="ID, client, produit ou transaction…"
      >
        <select
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(1);
          }}
        >
          <option value="">Tous les statuts</option>
          {Object.entries(STATUS_LABELS)
            .slice(0, 11)
            .map(([value, label]) => (
              <option value={value} key={value}>
                {label}
              </option>
            ))}
        </select>
        <select value={`${sort}-${direction}`} onChange={(event) => { const [nextSort, nextDirection] = event.target.value.split("-"); setSort(nextSort); setDirection(nextDirection); setPage(1); }} aria-label="Trier les commandes">
          <option value="date-desc">Plus récentes</option>
          <option value="date-asc">Plus anciennes</option>
          <option value="amount-desc">Montant décroissant</option>
          <option value="amount-asc">Montant croissant</option>
        </select>
      </FilterBar>
      <section className="data-panel">
        <div className="responsive-table">
          <table>
            <thead>
              <tr>
                <th><button className={`sort-button ${sort === "date" ? "active" : ""}`} onClick={() => toggleSort("date")}>Commande <span>{sort === "date" ? (direction === "desc" ? "↓" : "↑") : "↕"}</span></button></th>
                <th>Client</th>
                <th>Produit</th>
                <th><button className={`sort-button ${sort === "amount" ? "active" : ""}`} onClick={() => toggleSort("amount")}>Montant <span>{sort === "amount" ? (direction === "desc" ? "↓" : "↑") : "↕"}</span></button></th>
                <th>Statut</th>
                <th>Date</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {result.items.map((order) => (
                <tr key={order.id} onClick={() => setSelected(order)}>
                  <td>
                    <strong>#{order.id}</strong>
                  </td>
                  <td>
                    {order.username ? `@${order.username}` : order.user_id}
                  </td>
                  <td>{order.offer_name || order.service_name || "—"}</td>
                  <td>
                    <strong>{money(order.total_price, data.currency)}</strong>
                  </td>
                  <td>
                    <span className={`status ${order.status}`}>
                      {STATUS_LABELS[order.status] || order.status}
                    </span>
                  </td>
                  <td>{date(order.created_at)}</td>
                  <td>
                    <button className="row-action">
                      <Edit3 size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {loading ? (
          <div className="table-loading">Chargement…</div>
        ) : (
          !result.items.length && (
            <Empty icon={ClipboardList} title="Aucune commande" />
          )
        )}
        <Pagination value={result} onChange={setPage} />
      </section>
      {selected && (
        <OrderEditor
          order={selected}
          currency={data.currency}
          onAction={onAction}
          onClose={() => setSelected(null)}
        />
      )}
    </>
  );
}

function OfferForm({ services, offer, onAction, onClose }) {
  const [form, setForm] = useState({
    service_id: offer?.service_id || services[0]?.id || "",
    name: offer?.name || "",
    price: offer?.price ?? "",
    description: offer?.description || "",
    note: offer?.note || "",
    delivery_delay: offer?.delivery_delay || "Instantané après confirmation",
    low_stock_threshold: offer?.low_stock_threshold ?? 5,
    auto_delivery: offer?.auto_delivery !== false,
    initial_inventory: "",
  });
  const set = (key, value) =>
    setForm((current) => ({ ...current, [key]: value }));
  const submit = async (event) => {
    event.preventDefault();
    const action = offer ? "update_offer" : "add_offer";
    const payload = {
      ...form,
      action,
      ...(offer
        ? { offer_id: offer.id, sort_order: offer.sort_order || 0 }
        : {}),
      auto_delivery: form.auto_delivery ? "on" : "",
    };
    if (await onAction(payload)) onClose();
  };
  return (
    <Modal
      title={offer ? "Modifier le produit" : "Nouveau produit"}
      onClose={onClose}
      wide
    >
      <form onSubmit={submit}>
        <div className="form-grid">
          <Field label="Service">
            <select
              value={form.service_id}
              onChange={(event) => set("service_id", event.target.value)}
            >
              {services.map((service) => (
                <option value={service.id} key={service.id}>
                  {service.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Nom">
            <input
              required
              value={form.name}
              onChange={(event) => set("name", event.target.value)}
            />
          </Field>
          <Field label="Prix">
            <input
              required
              min="0"
              step="0.01"
              type="number"
              value={form.price}
              onChange={(event) => set("price", event.target.value)}
            />
          </Field>
          <Field label="Seuil de stock">
            <input
              min="0"
              type="number"
              value={form.low_stock_threshold}
              onChange={(event) =>
                set("low_stock_threshold", event.target.value)
              }
            />
          </Field>
          <Field label="Description" wide>
            <textarea
              value={form.description}
              onChange={(event) => set("description", event.target.value)}
            />
          </Field>
          <Field label="Note / garantie" wide>
            <input
              value={form.note}
              onChange={(event) => set("note", event.target.value)}
            />
          </Field>
          {!offer && (
            <Field label="Stock initial" wide>
              <textarea
                value={form.initial_inventory}
                onChange={(event) =>
                  set("initial_inventory", event.target.value)
                }
                placeholder="#1&#10;Email: …&#10;Password: …"
              />
            </Field>
          )}
          <Field label="Livraison">
            <input
              value={form.delivery_delay}
              onChange={(event) => set("delivery_delay", event.target.value)}
            />
          </Field>
          <Field label="Automatisation">
            <label className="switch">
              <input
                type="checkbox"
                checked={form.auto_delivery}
                onChange={(event) => set("auto_delivery", event.target.checked)}
              />
              <span /> Livraison automatique
            </label>
          </Field>
        </div>
        <div className="dialog-actions">
          <ActionButton secondary onClick={onClose} type="button">
            Annuler
          </ActionButton>
          <ActionButton icon={Check} type="submit">
            Enregistrer
          </ActionButton>
        </div>
      </form>
    </Modal>
  );
}

function CatalogPage({ data, onAction }) {
  const [offer, setOffer] = useState(undefined);
  const [showOffer, setShowOffer] = useState(false);
  const [showService, setShowService] = useState(false);
  const [serviceName, setServiceName] = useState("");
  const [serviceEmoji, setServiceEmoji] = useState("📦");
  const [stockOffer, setStockOffer] = useState(null);
  const [stock, setStock] = useState("");
  const createService = async (event) => {
    event.preventDefault();
    if (
      await onAction({
        action: "add_service",
        name: serviceName,
        emoji: serviceEmoji,
      })
    )
      setShowService(false);
  };
  return (
    <>
      <PageHeader
        eyebrow="Boutique"
        title="Catalogue"
        description="Gérez les catégories, produits, prix et disponibilités."
        actions={
          <>
            <ActionButton
              secondary
              icon={Plus}
              onClick={() => setShowService(true)}
            >
              Service
            </ActionButton>
            <ActionButton
              icon={PackagePlus}
              onClick={() => {
                setOffer(undefined);
                setShowOffer(true);
              }}
            >
              Produit
            </ActionButton>
          </>
        }
      />
      <div className="catalog-react-grid">
        {data.services?.map((service) => (
          <section className="catalog-service" key={service.id}>
            <header>
              <div>
                <span>{service.emoji || "◆"}</span>
                <div>
                  <h3>{service.name}</h3>
                  <small>
                    {service.offer_count || 0} produit(s) ·{" "}
                    {service.total_stock || 0} en stock
                  </small>
                </div>
              </div>
              <button
                onClick={() =>
                  onAction({ action: "toggle_service", service_id: service.id })
                }
              >
                {service.active === 0 ? <ToggleLeft /> : <ToggleRight />}
              </button>
            </header>
            <div>
              {service.offers?.map((item, index) => (
                <article
                  className="offer-card"
                  key={item.id || `${service.id}-${item.name}-${index}`}
                >
                  <div>
                    <strong>{item.name}</strong>
                    <span>
                      {money(item.price, data.currency)} · Stock{" "}
                      {item.stock || 0}
                    </span>
                  </div>
                  <div className="offer-actions">
                    <button
                      title="Ajouter du stock"
                      onClick={() => setStockOffer(item)}
                    >
                      <Boxes size={15} />
                    </button>
                    <button
                      title="Dupliquer"
                      onClick={() =>
                        onAction({
                          action: "duplicate_offer",
                          offer_id: item.id,
                        })
                      }
                    >
                      <Copy size={15} />
                    </button>
                    <button
                      title="Modifier"
                      onClick={() => {
                        setOffer(item);
                        setShowOffer(true);
                      }}
                    >
                      <Edit3 size={15} />
                    </button>
                    <button
                      title="Activer/désactiver"
                      onClick={() =>
                        onAction({ action: "toggle_offer", offer_id: item.id })
                      }
                    >
                      {item.active === 0 ? (
                        <ToggleLeft size={17} />
                      ) : (
                        <ToggleRight size={17} />
                      )}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
      {!data.services?.length && (
        <Empty
          icon={ShoppingBag}
          title="Catalogue vide"
          text="Créez votre premier service puis ajoutez des produits."
        />
      )}
      {showOffer && (
        <OfferForm
          services={data.services || []}
          offer={offer}
          onAction={onAction}
          onClose={() => setShowOffer(false)}
        />
      )}
      {showService && (
        <Modal title="Nouveau service" onClose={() => setShowService(false)}>
          <form onSubmit={createService}>
            <div className="form-grid">
              <Field label="Nom">
                <input
                  required
                  value={serviceName}
                  onChange={(event) => setServiceName(event.target.value)}
                />
              </Field>
              <Field label="Emoji">
                <input
                  value={serviceEmoji}
                  onChange={(event) => setServiceEmoji(event.target.value)}
                />
              </Field>
            </div>
            <div className="dialog-actions">
              <ActionButton type="submit" icon={Plus}>
                Créer
              </ActionButton>
            </div>
          </form>
        </Modal>
      )}
      {stockOffer && (
        <Modal
          title={`Stock · ${stockOffer.name}`}
          onClose={() => setStockOffer(null)}
        >
          <Field label="Éléments à chiffrer">
            <textarea
              value={stock}
              onChange={(event) => setStock(event.target.value)}
              placeholder="#1&#10;Compte: …"
            />
          </Field>
          <div className="dialog-actions">
            <ActionButton
              icon={PackagePlus}
              onClick={async () => {
                if (
                  await onAction({
                    action: "add_inventory",
                    offer_id: stockOffer.id,
                    items: stock,
                  })
                )
                  setStockOffer(null);
              }}
            >
              Ajouter
            </ActionButton>
          </div>
        </Modal>
      )}
    </>
  );
}

function ApiProductsPage({ data, onAction, setToast }) {
  const [provider, setProvider] = useState("mailreader");
  const [catalog, setCatalog] = useState(null);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(null);
  const load = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `/admin/api/reseller-products?provider=${provider}`,
        { credentials: "same-origin", cache: "no-store" },
      );
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "API indisponible");
      setCatalog(payload);
    } catch (error) {
      setCatalog(null);
      setToast({
        type: "error",
        title: "Fournisseur indisponible",
        message: error.message,
      });
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, [provider]);
  return (
    <>
      <PageHeader
        eyebrow="Automatisation"
        title="Produits API"
        description="Connectez les fournisseurs et publiez leurs produits dans votre boutique."
        actions={
          <ActionButton secondary icon={RefreshCw} onClick={load}>
            Synchroniser
          </ActionButton>
        }
      />
      <div className="provider-tabs">
        {PROVIDERS.map(([id, label]) => (
          <button
            className={provider === id ? "active" : ""}
            onClick={() => setProvider(id)}
            key={id}
          >
            <Cloud size={16} />
            {label}
          </button>
        ))}
      </div>
      {catalog && (
        <div className="api-summary">
          <div>
            <span>Fournisseur</span>
            <strong>{catalog.supplier_name || provider}</strong>
          </div>
          <div>
            <span>Solde</span>
            <strong>
              {money(catalog.balance, catalog.currency || "USDT")}
            </strong>
          </div>
          <div>
            <span>Produits publiés</span>
            <strong>{catalog.selected_count || 0}</strong>
          </div>
          <div>
            <span>Produits disponibles</span>
            <strong>{catalog.products?.length || 0}</strong>
          </div>
        </div>
      )}
      <section className="data-panel">
        <div className="product-api-grid">
          {catalog?.products?.map((product) => (
            <article key={product.id}>
              <header>
                <span
                  className={product.stock > 0 ? "api-online" : "api-offline"}
                >
                  {product.stock > 0 ? `${product.stock} en stock` : "Épuisé"}
                </span>
                <button onClick={() => setEditing(product)}>
                  <Edit3 size={15} />
                </button>
              </header>
              <h3>{product.display_name || product.name}</h3>
              <p>{product.description || "Produit fournisseur"}</p>
              <div>
                <span>
                  Achat {money(product.wholesale_price, product.currency)}
                </span>
                <strong>{money(product.retail_price, product.currency)}</strong>
              </div>
            </article>
          ))}
        </div>
        {loading && (
          <div className="table-loading">Connexion au fournisseur…</div>
        )}
        {!loading && !catalog?.products?.length && (
          <Empty
            icon={Cloud}
            title="Aucun produit API"
            text="Vérifiez la configuration de ce fournisseur."
          />
        )}
      </section>
      <BuyerKeys setToast={setToast} />
      {editing && (
        <ApiProductEditor
          product={editing}
          provider={provider}
          services={data.services || []}
          onAction={onAction}
          onClose={() => setEditing(null)}
        />
      )}
    </>
  );
}

function BuyerKeys({ setToast }) {
  const [keys, setKeys] = useState([]);
  const [show, setShow] = useState(false);
  const [userId, setUserId] = useState("");
  const [label, setLabel] = useState("Buyer API");
  const [issued, setIssued] = useState("");
  const load = () =>
    fetch("/admin/api/buyer-keys", {
      credentials: "same-origin",
      cache: "no-store",
    })
      .then((response) => response.json())
      .then((payload) => setKeys(payload.keys || []));
  useEffect(() => {
    load();
  }, []);
  const request = async (body) => {
    const response = await fetch("/admin/api/buyer-keys", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await response.json();
    if (!response.ok) {
      setToast({
        type: "error",
        title: "Clé API",
        message: payload.message || payload.error || "Action refusée",
      });
      return null;
    }
    await load();
    return payload;
  };
  return (
    <section className="data-panel buyer-keys">
      <header>
        <div>
          <span className="eyebrow">Accès revendeurs</span>
          <h3>Clés Buyer API</h3>
        </div>
        <ActionButton icon={KeyRound} onClick={() => setShow(true)}>
          Nouvelle clé
        </ActionButton>
      </header>
      <div className="responsive-table">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Client</th>
              <th>Libellé</th>
              <th>Créée</th>
              <th>Dernière utilisation</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {keys.map((key) => (
              <tr key={key.id}>
                <td>#{key.id}</td>
                <td>{key.user_id}</td>
                <td>{key.label}</td>
                <td>{date(key.created_at)}</td>
                <td>{date(key.last_used_at)}</td>
                <td>
                  <button
                    className="row-action"
                    onClick={() =>
                      request({ action: "revoke", key_id: key.id })
                    }
                  >
                    <Trash2 size={15} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!keys.length && <Empty icon={KeyRound} title="Aucune clé active" />}
      {show && (
        <Modal title="Créer une clé Buyer API" onClose={() => setShow(false)}>
          <div className="form-grid">
            <Field label="Telegram ID">
              <input
                type="number"
                value={userId}
                onChange={(event) => setUserId(event.target.value)}
              />
            </Field>
            <Field label="Libellé">
              <input
                value={label}
                onChange={(event) => setLabel(event.target.value)}
              />
            </Field>
          </div>
          {issued && <pre className="secret-preview">{issued}</pre>}
          <div className="dialog-actions">
            <ActionButton
              icon={KeyRound}
              onClick={async () => {
                const payload = await request({
                  action: "create",
                  user_id: userId,
                  label,
                });
                if (payload)
                  setIssued(
                    payload.key?.secret ||
                      payload.key?.key ||
                      JSON.stringify(payload.key),
                  );
              }}
            >
              Créer
            </ActionButton>
          </div>
        </Modal>
      )}
    </section>
  );
}

function ApiProductEditor({ product, provider, services, onAction, onClose }) {
  const [form, setForm] = useState({
    display_name: product.display_name || product.name,
    retail_price: product.retail_price || "",
    service_id: product.service_id || services[0]?.id || "",
    enabled: Boolean(product.enabled),
    description: product.description || "",
    warranty: product.warranty || "",
    delivery_delay: product.delivery_delay || "Instantané après confirmation",
    low_stock_threshold: product.low_stock_threshold || 5,
  });
  const set = (key, value) =>
    setForm((current) => ({ ...current, [key]: value }));
  return (
    <Modal title={product.name} onClose={onClose} wide>
      <div className="form-grid">
        <Field label="Nom public">
          <input
            value={form.display_name}
            onChange={(event) => set("display_name", event.target.value)}
          />
        </Field>
        <Field label="Prix de vente">
          <input
            type="number"
            step="0.01"
            value={form.retail_price}
            onChange={(event) => set("retail_price", event.target.value)}
          />
        </Field>
        <Field label="Service">
          <select
            value={form.service_id}
            onChange={(event) => set("service_id", event.target.value)}
          >
            {services.map((service) => (
              <option key={service.id} value={service.id}>
                {service.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Publication">
          <label className="switch">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(event) => set("enabled", event.target.checked)}
            />
            <span />
            Visible dans le bot
          </label>
        </Field>
        <Field label="Description" wide>
          <textarea
            value={form.description}
            onChange={(event) => set("description", event.target.value)}
          />
        </Field>
        <Field label="Garantie">
          <input
            value={form.warranty}
            onChange={(event) => set("warranty", event.target.value)}
          />
        </Field>
        <Field label="Délai de livraison">
          <input
            value={form.delivery_delay}
            onChange={(event) => set("delivery_delay", event.target.value)}
          />
        </Field>
      </div>
      <div className="dialog-actions">
        <ActionButton
          icon={Check}
          onClick={async () => {
            if (
              await onAction({
                action: "save_reseller_product",
                provider,
                product_id: product.id,
                ...form,
                enabled: form.enabled ? "1" : "0",
              })
            )
              onClose();
          }}
        >
          Publier
        </ActionButton>
      </div>
    </Modal>
  );
}

function InventoryPage({ data, onAction }) {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [offerId, setOfferId] = useState("");
  const [page, setPage] = useState(1);
  const [revealed, setRevealed] = useState(null);
  const [result, loading] = useRemoteList("/admin/api/inventory", {
    search,
    status,
    offer_id: offerId,
    page,
    per_page: 25,
  });
  const reveal = async (item) => {
    const response = await fetch("/admin", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
      },
      body: new URLSearchParams({
        action: "reveal_inventory",
        inventory_id: item.reference_id,
      }),
    });
    const payload = await response.json();
    if (response.ok) setRevealed({ item, value: payload.value });
  };
  return (
    <>
      <PageHeader
        eyebrow="Livraison"
        title="Inventaire"
        description="Stock chiffré, réservations et livraisons automatiques."
        actions={
          <a
            className="action-button secondary"
            href="/admin/api/inventory-export"
          >
            <Download size={16} />
            Exporter CSV
          </a>
        }
      />
      <FilterBar
        search={search}
        setSearch={(value) => {
          setSearch(value);
          setPage(1);
        }}
        placeholder="Référence masquée…"
      >
        <select
          value={offerId}
          onChange={(event) => {
            setOfferId(event.target.value);
            setPage(1);
          }}
        >
          <option value="">Tous les produits</option>
          {data.services
            ?.flatMap((service) => service.offers || [])
            .map((offer, index) => (
              <option
                value={offer.id}
                key={offer.id || `${offer.name}-${index}`}
              >
                {offer.name}
              </option>
            ))}
        </select>
        <select
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(1);
          }}
        >
          <option value="">Tous les états</option>
          {["available", "reserved", "delivered", "disabled"].map((value) => (
            <option key={value}>{value}</option>
          ))}
        </select>
      </FilterBar>
      <section className="data-panel">
        <div className="responsive-table">
          <table>
            <thead>
              <tr>
                <th>Référence</th>
                <th>Produit</th>
                <th>Aperçu</th>
                <th>État</th>
                <th>Commande</th>
                <th>Date</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {result.items.map((item) => (
                <tr key={item.reference_id}>
                  <td>#{item.reference_id}</td>
                  <td>#{item.offer_id}</td>
                  <td>
                    <code>{item.masked_preview || "••••••"}</code>
                  </td>
                  <td>
                    <span className={`status ${item.status}`}>
                      {item.status}
                    </span>
                  </td>
                  <td>
                    {item.reserved_order_id || item.delivered_order_id || "—"}
                  </td>
                  <td>{date(item.created_at)}</td>
                  <td>
                    <div className="inline-actions">
                      <button title="Révéler" onClick={() => reveal(item)}>
                        <Eye size={15} />
                      </button>
                      <button
                        title="Activer/désactiver"
                        onClick={() =>
                          onAction({
                            action: "toggle_inventory",
                            inventory_id: item.reference_id,
                            disabled: item.status === "disabled" ? "0" : "1",
                          })
                        }
                      >
                        {item.status === "disabled" ? (
                          <ToggleLeft size={16} />
                        ) : (
                          <ToggleRight size={16} />
                        )}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {loading ? (
          <div className="table-loading">Chargement…</div>
        ) : (
          !result.items.length && <Empty icon={Boxes} title="Inventaire vide" />
        )}
        <Pagination value={result} onChange={setPage} />
      </section>
      {revealed && (
        <Modal
          title={`Référence #${revealed.item.reference_id}`}
          onClose={() => setRevealed(null)}
        >
          <pre className="secret-preview">{revealed.value}</pre>
          <div className="dialog-actions">
            <ActionButton
              icon={Copy}
              onClick={() => navigator.clipboard.writeText(revealed.value)}
            >
              Copier
            </ActionButton>
          </div>
        </Modal>
      )}
    </>
  );
}

function CustomerDetail({ customer, onAction, onClose, currency }) {
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  return (
    <Modal
      title={
        customer.username
          ? `@${customer.username}`
          : `Client ${customer.telegram_id}`
      }
      onClose={onClose}
      wide
    >
      <div className="detail-grid">
        <div>
          <span>Telegram ID</span>
          <strong>{customer.telegram_id}</strong>
        </div>
        <div>
          <span>Portefeuille</span>
          <strong>{money(customer.wallet_balance, currency)}</strong>
        </div>
        <div>
          <span>Commandes</span>
          <strong>{customer.order_count || 0}</strong>
        </div>
        <div>
          <span>Total dépensé</span>
          <strong>{money(customer.total_spent, currency)}</strong>
        </div>
      </div>
      <div className="form-grid">
        <Field label="Ajustement du solde">
          <input
            type="number"
            step="0.01"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            placeholder="+10 ou -5"
          />
        </Field>
        <Field label="Motif">
          <input
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </Field>
      </div>
      <div className="dialog-actions wrap">
        <ActionButton
          icon={CircleDollarSign}
          disabled={!amount}
          onClick={() =>
            onAction({
              action: "adjust_user_wallet",
              user_id: customer.telegram_id,
              amount,
              reason,
            })
          }
        >
          Ajuster
        </ActionButton>
        <ActionButton
          danger
          icon={Ban}
          onClick={() =>
            onAction({
              action: "toggle_ban",
              user_id: customer.telegram_id,
              banned: customer.banned ? "0" : "1",
            })
          }
        >
          {customer.banned ? "Débloquer" : "Bloquer"}
        </ActionButton>
      </div>
    </Modal>
  );
}

function CustomersPage({ data, onAction }) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkAmount, setBulkAmount] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [result, loading] = useRemoteList("/admin/api/customers", {
    search,
    page,
    per_page: 25,
  });
  const open = async (user) => {
    const response = await fetch(
      `/admin/api/customers?user_id=${user.telegram_id}`,
      { credentials: "same-origin" },
    );
    if (response.ok) setSelected(await response.json());
  };
  return (
    <>
      <PageHeader
        eyebrow="CRM"
        title="Clients"
        description="Portefeuilles, achats, affiliation et accès au bot."
        actions={
          <ActionButton
            icon={CircleDollarSign}
            onClick={() => setBulkOpen(true)}
          >
            Crédit collectif
          </ActionButton>
        }
      />
      <FilterBar
        search={search}
        setSearch={(value) => {
          setSearch(value);
          setPage(1);
        }}
        placeholder="ID Telegram, username ou prénom…"
      />
      <section className="data-panel">
        <div className="responsive-table">
          <table>
            <thead>
              <tr>
                <th>Client</th>
                <th>Telegram ID</th>
                <th>Portefeuille</th>
                <th>Commandes</th>
                <th>Dépensé</th>
                <th>Affiliés</th>
                <th>Statut</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {result.items.map((user) => (
                <tr key={user.telegram_id} onClick={() => open(user)}>
                  <td>
                    <strong>
                      {user.username
                        ? `@${user.username}`
                        : user.first_name || "Client"}
                    </strong>
                  </td>
                  <td>{user.telegram_id}</td>
                  <td>{money(user.wallet_balance, data.currency)}</td>
                  <td>{user.order_count || 0}</td>
                  <td>{money(user.total_spent, data.currency)}</td>
                  <td>{user.referral_count || 0}</td>
                  <td>
                    <span
                      className={`status ${user.banned ? "cancelled" : "delivered"}`}
                    >
                      {user.banned ? "Bloqué" : "Actif"}
                    </span>
                  </td>
                  <td>
                    <button className="row-action">
                      <UserRound size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {loading ? (
          <div className="table-loading">Chargement…</div>
        ) : (
          !result.items.length && <Empty icon={Users} title="Aucun client" />
        )}
        <Pagination value={result} onChange={setPage} />
      </section>
      {selected && (
        <CustomerDetail
          customer={selected}
          onAction={onAction}
          currency={data.currency}
          onClose={() => setSelected(null)}
        />
      )}
      {bulkOpen && (
        <Modal
          title="Créditer tous les portefeuilles"
          onClose={() => setBulkOpen(false)}
        >
          <div className="warning-box">
            Cette action crédite chaque utilisateur actif. Elle est idempotente
            grâce à un identifiant d’opération unique.
          </div>
          <div className="form-grid">
            <Field label={`Montant (${data.currency})`}>
              <input
                type="number"
                step="0.01"
                value={bulkAmount}
                onChange={(event) => setBulkAmount(event.target.value)}
              />
            </Field>
            <Field label="Confirmation">
              <input
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
                placeholder="CREDIT ALL"
              />
            </Field>
          </div>
          <div className="dialog-actions">
            <ActionButton
              danger
              icon={CircleDollarSign}
              disabled={!bulkAmount || confirmation !== "CREDIT ALL"}
              onClick={async () => {
                if (
                  await onAction({
                    action: "bulk_credit_wallets",
                    amount: bulkAmount,
                    confirmation,
                    operation_id: `react-${Date.now()}`,
                  })
                )
                  setBulkOpen(false);
              }}
            >
              Créditer tous
            </ActionButton>
          </div>
        </Modal>
      )}
    </>
  );
}

function TicketDialog({ ticket, onAction, onClose }) {
  const [messages, setMessages] = useState([]);
  const [reply, setReply] = useState("");
  const load = () =>
    fetch(`/admin/api/ticket-messages?ticket_id=${ticket.id}`, {
      credentials: "same-origin",
      cache: "no-store",
    })
      .then((response) => response.json())
      .then((payload) =>
        setMessages(Array.isArray(payload) ? payload : payload.messages || []),
      );
  useEffect(load, [ticket.id]);
  return (
    <Modal title={`Ticket #${ticket.id}`} onClose={onClose} wide>
      <div className="ticket-thread">
        {messages.map((message, index) => (
          <div
            className={`ticket-message ${message.sender_type === "admin" ? "admin" : ""}`}
            key={message.id || index}
          >
            <strong>
              {message.sender_type === "admin" ? "Admin" : "Client"}
            </strong>
            <p>{message.message || message.content}</p>
            <span>{date(message.created_at)}</span>
          </div>
        ))}
        {!messages.length && (
          <Empty icon={MessageSquareText} title="Conversation vide" />
        )}
      </div>
      <Field label="Réponse">
        <textarea
          value={reply}
          onChange={(event) => setReply(event.target.value)}
          placeholder="Votre réponse…"
        />
      </Field>
      <div className="dialog-actions wrap">
        <ActionButton
          icon={Send}
          disabled={!reply.trim()}
          onClick={async () => {
            if (
              await onAction({
                action: "reply_ticket",
                ticket_id: ticket.id,
                message: reply,
              })
            ) {
              setReply("");
              load();
            }
          }}
        >
          Répondre
        </ActionButton>
        <ActionButton
          secondary
          icon={Archive}
          onClick={async () => {
            if (
              await onAction({ action: "close_ticket", ticket_id: ticket.id })
            )
              onClose();
          }}
        >
          Fermer le ticket
        </ActionButton>
      </div>
    </Modal>
  );
}

function SupportPage({ onAction }) {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [ticket, setTicket] = useState(null);
  const [result, loading] = useRemoteList("/admin/api/tickets", {
    status,
    user_id: search.match(/^\d+$/)?.[0] || "",
    page,
    per_page: 25,
  });
  const items = result.items.filter(
    (item) =>
      !search ||
      `${item.id} ${item.user_id} ${item.category || ""}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <>
      <PageHeader
        eyebrow="Assistance"
        title="Support"
        description="Consultez les conversations et répondez directement aux clients."
      />
      <FilterBar
        search={search}
        setSearch={setSearch}
        placeholder="Ticket ou client…"
      >
        <select
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(1);
          }}
        >
          <option value="">Tous les statuts</option>
          {Object.entries(STATUS_LABELS)
            .slice(11)
            .map(([value, label]) => (
              <option value={value} key={value}>
                {label}
              </option>
            ))}
        </select>
      </FilterBar>
      <section className="data-panel">
        <div className="responsive-table">
          <table>
            <thead>
              <tr>
                <th>Ticket</th>
                <th>Client</th>
                <th>Catégorie</th>
                <th>Statut</th>
                <th>Mis à jour</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} onClick={() => setTicket(item)}>
                  <td>
                    <strong>#{item.id}</strong>
                  </td>
                  <td>{item.user_id}</td>
                  <td>{item.category || "Général"}</td>
                  <td>
                    <span className={`status ${item.status}`}>
                      {STATUS_LABELS[item.status] || item.status}
                    </span>
                  </td>
                  <td>{date(item.updated_at || item.created_at)}</td>
                  <td>
                    <button className="row-action">
                      <MessageSquareText size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {loading ? (
          <div className="table-loading">Chargement…</div>
        ) : (
          !items.length && <Empty icon={Headphones} title="Aucun ticket" />
        )}
        <Pagination value={result} onChange={setPage} />
      </section>
      {ticket && (
        <TicketDialog
          ticket={ticket}
          onAction={onAction}
          onClose={() => setTicket(null)}
        />
      )}
    </>
  );
}

function InteractionsPage({ data }) {
  const analytics = data.interactions || {};
  const summary = analytics.summary || {};
  const [search, setSearch] = useState("");
  const [type, setType] = useState("");
  const events = (analytics.events || []).filter(
    (event) =>
      (!type || event.interaction_type === type) &&
      (!search ||
        `${event.full_name || ""} ${event.username || ""} ${event.user_id || ""} ${event.action || ""} ${event.content || ""}`
          .toLowerCase()
          .includes(search.toLowerCase())),
  );
  const max = Math.max(
    ...(analytics.daily || []).map((point) => point.count),
    1,
  );
  return (
    <>
      <PageHeader
        eyebrow="Analyse"
        title="Interactions"
        description="Messages, commandes et clics enregistrés dans le bot."
      />
      <div className="mini-kpi-grid">
        <div>
          <span>Total</span>
          <strong>{summary.total || 0}</strong>
        </div>
        <div>
          <span>Aujourd’hui</span>
          <strong>{summary.today || 0}</strong>
        </div>
        <div>
          <span>Utilisateurs actifs</span>
          <strong>{summary.active_today || 0}</strong>
        </div>
        <div>
          <span>Clics boutons</span>
          <strong>{summary.button_clicks || 0}</strong>
        </div>
      </div>
      <section className="data-panel analytics-panel">
        <header>
          <h3>Interactions sur 30 jours</h3>
        </header>
        <div className="bar-chart">
          {(analytics.daily || []).map((point) => (
            <div key={point.date} title={`${point.date}: ${point.count}`}>
              <i
                style={{ height: `${Math.max(4, (point.count / max) * 100)}%` }}
              />
              <span>{point.date.slice(8)}</span>
            </div>
          ))}
        </div>
      </section>
      <FilterBar
        search={search}
        setSearch={setSearch}
        placeholder="Utilisateur, message ou action…"
      >
        <select value={type} onChange={(event) => setType(event.target.value)}>
          <option value="">Tous les types</option>
          {["button", "message", "command", "media", "other"].map((value) => (
            <option key={value}>{value}</option>
          ))}
        </select>
      </FilterBar>
      <section className="data-panel">
        <div className="responsive-table">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Utilisateur</th>
                <th>Type</th>
                <th>Action</th>
                <th>Contenu / écran</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event, index) => (
                <tr key={event.id || index}>
                  <td>{date(event.created_at)}</td>
                  <td>
                    <strong>
                      {event.full_name || event.first_name || event.user_id}
                    </strong>
                    <small>
                      {event.username ? `@${event.username}` : event.user_id}
                    </small>
                  </td>
                  <td>
                    <span className="status">{event.interaction_type}</span>
                  </td>
                  <td>
                    <code>{event.action || "—"}</code>
                  </td>
                  <td>{event.content || event.screen || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!events.length && <Empty icon={Activity} title="Aucune interaction" />}
      </section>
    </>
  );
}

function ActivityPage({ data }) {
  const [search, setSearch] = useState("");
  const events = (data.audits || []).filter(
    (item) =>
      !search ||
      `${item.action} ${item.actor_id || ""} ${JSON.stringify(item.details || {})}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <>
      <PageHeader
        eyebrow="Sécurité"
        title="Journal d’activité"
        description="Historique des actions administratives et événements système."
      />
      <FilterBar
        search={search}
        setSearch={setSearch}
        placeholder="Action, acteur ou détail…"
      />
      <section className="data-panel">
        <div className="responsive-table">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Action</th>
                <th>Acteur</th>
                <th>Détails</th>
              </tr>
            </thead>
            <tbody>
              {events.map((item, index) => (
                <tr key={item.id || index}>
                  <td>{date(item.created_at)}</td>
                  <td>
                    <strong>{item.action}</strong>
                  </td>
                  <td>{item.actor_id || item.user_id || "Système"}</td>
                  <td>
                    <code className="audit-details">
                      {typeof item.details === "string"
                        ? item.details
                        : JSON.stringify(item.details || {})}
                    </code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!events.length && <Empty icon={Activity} title="Aucun événement" />}
      </section>
    </>
  );
}

function SettingsPage({ data, onAction, onHealthCheck }) {
  const [form, setForm] = useState({
    shop_name: data.shop_name || "BlackMarket",
    currency: data.currency || "USDT",
    low_stock_threshold: data.low_stock_threshold || 5,
    order_expiry_seconds: data.order_expiry_seconds || 1800,
    payment_recipient: data.payment_recipient || "",
    affiliate_enabled: data.affiliate_enabled !== false,
    affiliate_target: data.affiliate_target || 10,
    affiliate_reward_cents: data.affiliate_reward_cents || 100,
    maintenance_enabled: data.maintenance_enabled === true,
    maintenance_message: data.maintenance_message || "",
    welcome_message: data.welcome_message || "",
    help_message: data.help_message || "",
    terms_message: data.terms_message || "",
    privacy_message: data.privacy_message || "",
    active_languages: data.active_languages || "fr,en,ar",
  });
  const set = (key, value) =>
    setForm((current) => ({ ...current, [key]: value }));
  return (
    <>
      <PageHeader
        eyebrow="Configuration"
        title="Paramètres"
        description="Personnalisez la boutique, le paiement, l’affiliation et les messages."
        actions={
          <>
            <ActionButton
              secondary
              icon={ShieldCheck}
              onClick={() => onHealthCheck("telegram")}
            >
              Telegram
            </ActionButton>
            <ActionButton
              secondary
              icon={Cloud}
              onClick={() => onHealthCheck("binance")}
            >
              Binance
            </ActionButton>
          </>
        }
      />
      <form
        className="settings-layout"
        onSubmit={(event) => {
          event.preventDefault();
          onAction({
            action: "save_settings",
            ...form,
            affiliate_enabled: form.affiliate_enabled ? "on" : "",
            maintenance_enabled: form.maintenance_enabled ? "on" : "",
          });
        }}
      >
        <section className="settings-card">
          <header>
            <Settings size={18} />
            <div>
              <h3>Boutique</h3>
              <p>Identité et règles commerciales.</p>
            </div>
          </header>
          <div className="form-grid">
            <Field label="Nom">
              <input
                value={form.shop_name}
                onChange={(event) => set("shop_name", event.target.value)}
              />
            </Field>
            <Field label="Devise">
              <input
                value={form.currency}
                onChange={(event) => set("currency", event.target.value)}
              />
            </Field>
            <Field label="Seuil stock faible">
              <input
                type="number"
                value={form.low_stock_threshold}
                onChange={(event) =>
                  set("low_stock_threshold", event.target.value)
                }
              />
            </Field>
            <Field label="Expiration commande (secondes)">
              <input
                type="number"
                value={form.order_expiry_seconds}
                onChange={(event) =>
                  set("order_expiry_seconds", event.target.value)
                }
              />
            </Field>
            <Field label="Identifiant de paiement" wide>
              <input
                value={form.payment_recipient}
                onChange={(event) =>
                  set("payment_recipient", event.target.value)
                }
              />
            </Field>
          </div>
        </section>
        <section className="settings-card">
          <header>
            <Users size={18} />
            <div>
              <h3>Affiliation et maintenance</h3>
              <p>Contrôlez les récompenses et la disponibilité.</p>
            </div>
          </header>
          <div className="form-grid">
            <Field label="Affiliation">
              <label className="switch">
                <input
                  type="checkbox"
                  checked={form.affiliate_enabled}
                  onChange={(event) =>
                    set("affiliate_enabled", event.target.checked)
                  }
                />
                <span />
                Activée
              </label>
            </Field>
            <Field label="Objectif">
              <input
                type="number"
                value={form.affiliate_target}
                onChange={(event) =>
                  set("affiliate_target", event.target.value)
                }
              />
            </Field>
            <Field label="Récompense (centimes)">
              <input
                type="number"
                value={form.affiliate_reward_cents}
                onChange={(event) =>
                  set("affiliate_reward_cents", event.target.value)
                }
              />
            </Field>
            <Field label="Maintenance">
              <label className="switch">
                <input
                  type="checkbox"
                  checked={form.maintenance_enabled}
                  onChange={(event) =>
                    set("maintenance_enabled", event.target.checked)
                  }
                />
                <span />
                Activée
              </label>
            </Field>
            <Field label="Message maintenance" wide>
              <textarea
                value={form.maintenance_message}
                onChange={(event) =>
                  set("maintenance_message", event.target.value)
                }
              />
            </Field>
          </div>
        </section>
        <section className="settings-card full">
          <header>
            <MessageSquareText size={18} />
            <div>
              <h3>Contenu du bot</h3>
              <p>Messages personnalisés affichés aux clients.</p>
            </div>
          </header>
          <div className="form-grid">
            <Field label="Accueil">
              <textarea
                value={form.welcome_message}
                onChange={(event) => set("welcome_message", event.target.value)}
              />
            </Field>
            <Field label="Aide">
              <textarea
                value={form.help_message}
                onChange={(event) => set("help_message", event.target.value)}
              />
            </Field>
            <Field label="Conditions">
              <textarea
                value={form.terms_message}
                onChange={(event) => set("terms_message", event.target.value)}
              />
            </Field>
            <Field label="Confidentialité">
              <textarea
                value={form.privacy_message}
                onChange={(event) => set("privacy_message", event.target.value)}
              />
            </Field>
            <Field label="Langues actives" wide>
              <input
                value={form.active_languages}
                onChange={(event) =>
                  set("active_languages", event.target.value)
                }
              />
            </Field>
          </div>
        </section>
        <div className="settings-submit">
          <ActionButton icon={Check} type="submit">
            Enregistrer les paramètres
          </ActionButton>
        </div>
      </form>
    </>
  );
}

export default function AdminPage({
  page,
  data,
  onAction,
  onHealthCheck,
  setToast,
}) {
  const props = { data, onAction, onHealthCheck, setToast };
  if (page === "orders") return <OrdersPage {...props} />;
  if (page === "catalog") return <CatalogPage {...props} />;
  if (page === "api-products") return <ApiProductsPage {...props} />;
  if (page === "inventory") return <InventoryPage {...props} />;
  if (page === "customers") return <CustomersPage {...props} />;
  if (page === "support") return <SupportPage {...props} />;
  if (page === "interactions") return <InteractionsPage {...props} />;
  if (page === "activity") return <ActivityPage {...props} />;
  if (page === "settings") return <SettingsPage {...props} />;
  return null;
}
