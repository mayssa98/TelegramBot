import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  Check,
  ChevronRight,
  Clock3,
  FileCheck2,
  Globe2,
  Headphones,
  Menu,
  MessageCircle,
  Search,
  ShieldCheck,
  ShoppingBag,
  Smartphone,
  Sparkles,
  Upload,
  X,
} from "lucide-react";

const COPY = {
  fr: {
    navCatalog: "Catalogue", navHow: "Comment ça marche", navSupport: "Support",
    eyebrow: "La marketplace digitale tunisienne",
    hero: "Vos services premium, payés simplement en TND.",
    lead: "Une boutique locale, rapide et sécurisée. Choisissez votre service, envoyez votre paiement et suivez sa validation.",
    explore: "Explorer le catalogue", whatsapp: "Parler sur WhatsApp",
    trusted: "Paiement vérifié manuellement", local: "Réservé à la Tunisie", delivery: "Livraison rapide",
    products: "Nos services", productsLead: "Tous les produits disponibles dans le bot, maintenant accessibles en dinars tunisiens.",
    search: "Rechercher un service ou un produit…", all: "Tous", available: "Disponible", unavailable: "Épuisé",
    buy: "Commander", from: "à partir de", how: "Commander en trois étapes",
    step1: "Choisissez", step1Text: "Sélectionnez le service adapté à votre besoin.",
    step2: "Payez", step2Text: "Utilisez D17, Flouci, ISI ou un virement.",
    step3: "Recevez", step3Text: "L’admin vérifie le reçu puis lance la livraison.",
    checkout: "Finaliser la commande", customer: "Vos informations", payment: "Paiement manuel",
    name: "Nom complet", phone: "Téléphone tunisien", email: "E-mail (facultatif)", quantity: "Quantité",
    method: "Méthode de paiement", reference: "Référence de transaction", receipt: "Reçu de paiement",
    receiptHelp: "JPG, PNG ou PDF — 4 Mo maximum", total: "Total", submit: "Envoyer pour vérification",
    sending: "Envoi sécurisé…", success: "Commande envoyée", successText: "Votre paiement attend la vérification de l’administrateur.",
    order: "Commande", close: "Fermer", required: "Veuillez compléter tous les champs obligatoires.",
    footer: "Services numériques pour la Tunisie", rights: "Tous droits réservés.",
  },
  ar: {
    navCatalog: "الخدمات", navHow: "كيفية الطلب", navSupport: "الدعم",
    eyebrow: "السوق الرقمي التونسي",
    hero: "خدماتك المميزة، بالدينار التونسي وبكل سهولة.",
    lead: "متجر محلي سريع وآمن. اختر خدمتك، أرسل الدفع وتابع عملية التحقق.",
    explore: "اكتشف الخدمات", whatsapp: "تواصل عبر واتساب",
    trusted: "تحقق يدوي من الدفع", local: "مخصص لتونس", delivery: "تسليم سريع",
    products: "خدماتنا", productsLead: "كل منتجات البوت متوفرة الآن بالدينار التونسي.",
    search: "ابحث عن خدمة أو منتج…", all: "الكل", available: "متوفر", unavailable: "غير متوفر",
    buy: "اطلب الآن", from: "ابتداءً من", how: "اطلب في ثلاث خطوات",
    step1: "اختر", step1Text: "اختر الخدمة التي تناسب احتياجاتك.",
    step2: "ادفع", step2Text: "استعمل D17 أو Flouci أو ISI أو التحويل.",
    step3: "استلم", step3Text: "يتحقق المسؤول من الوصل ثم يبدأ التسليم.",
    checkout: "إتمام الطلب", customer: "معلوماتك", payment: "الدفع اليدوي",
    name: "الاسم الكامل", phone: "رقم الهاتف التونسي", email: "البريد الإلكتروني (اختياري)", quantity: "الكمية",
    method: "طريقة الدفع", reference: "مرجع العملية", receipt: "وصل الدفع",
    receiptHelp: "JPG أو PNG أو PDF — بحد أقصى 4 ميغابايت", total: "المجموع", submit: "إرسال للتحقق",
    sending: "إرسال آمن…", success: "تم إرسال الطلب", successText: "دفعتك في انتظار تحقق المسؤول.",
    order: "الطلب", close: "إغلاق", required: "يرجى إكمال جميع الحقول المطلوبة.",
    footer: "خدمات رقمية مخصصة لتونس", rights: "جميع الحقوق محفوظة.",
  },
};

function money(value) {
  return `${new Intl.NumberFormat("fr-TN", { minimumFractionDigits: 3, maximumFractionDigits: 3 }).format(Number(value || 0))} TND`;
}

function App() {
  const initialLang = window.location.pathname.startsWith("/ar") ? "ar" : "fr";
  const [lang, setLang] = useState(initialLang);
  const [data, setData] = useState({ services: [], payment_methods: [], whatsapp: "21626183573" });
  const [loading, setLoading] = useState(true);
  const [menuOpen, setMenuOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [serviceId, setServiceId] = useState("all");
  const [checkout, setCheckout] = useState(null);
  const t = COPY[lang];
  const isAr = lang === "ar";

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = isAr ? "rtl" : "ltr";
    setLoading(true);
    fetch(`/api/storefront/catalog?lang=${lang}`, { cache: "no-store" })
      .then((response) => response.json())
      .then(setData)
      .finally(() => setLoading(false));
  }, [lang, isAr]);

  const products = useMemo(() => data.services.flatMap((service) =>
    service.products.map((product) => ({ ...product, serviceName: service.name }))), [data]);
  const visible = products.filter((product) => {
    const matchesService = serviceId === "all" || product.service_id === Number(serviceId);
    const needle = query.trim().toLowerCase();
    return matchesService && (!needle || `${product.name} ${product.description} ${product.serviceName}`.toLowerCase().includes(needle));
  });
  const whatsappUrl = `https://wa.me/${data.whatsapp || "21626183573"}?text=${encodeURIComponent(isAr ? "السلام عليكم، أحتاج إلى مساعدة بخصوص خدمات الموقع." : "Bonjour, j’ai besoin d’aide concernant les services du site.")}`;
  const changeLang = () => {
    const next = isAr ? "fr" : "ar";
    window.history.replaceState({}, "", `/${next}`);
    setLang(next);
    setServiceId("all");
  };
  const Arrow = isAr ? ArrowLeft : ArrowRight;

  return (
    <div className="site-shell">
      <header className="topbar">
        <a className="logo" href={`/${lang}`}><span>TM</span><div><strong>Trust Market</strong><small>TN</small></div></a>
        <nav className={menuOpen ? "open" : ""}>
          <a href="#catalog" onClick={() => setMenuOpen(false)}>{t.navCatalog}</a>
          <a href="#how" onClick={() => setMenuOpen(false)}>{t.navHow}</a>
          <a href={whatsappUrl} target="_blank" rel="noreferrer">{t.navSupport}</a>
        </nav>
        <div className="nav-actions">
          <button className="lang-button" onClick={changeLang}><Globe2 size={17} />{isAr ? "FR" : "عربي"}</button>
          <button className="menu-button" onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X /> : <Menu />}</button>
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="hero-copy">
            <span className="eyebrow"><Sparkles size={15} />{t.eyebrow}</span>
            <h1>{t.hero}</h1>
            <p>{t.lead}</p>
            <div className="hero-actions">
              <a className="primary" href="#catalog">{t.explore}<Arrow size={18} /></a>
              <a className="secondary" href={whatsappUrl} target="_blank" rel="noreferrer"><MessageCircle size={18} />{t.whatsapp}</a>
            </div>
            <div className="trust-row">
              <span><ShieldCheck />{t.trusted}</span><span><BadgeCheck />{t.local}</span><span><Clock3 />{t.delivery}</span>
            </div>
          </div>
          <div className="hero-visual">
            <div className="orb one" /><div className="orb two" />
            <div className="showcase-card main-card">
              <div className="mini-head"><span className="pulse" />Live catalogue <ShoppingBag size={18} /></div>
              <strong>{products.length || "—"}</strong><small>{isAr ? "منتج رقمي" : "produits numériques"}</small>
              <div className="mini-products">{products.slice(0, 3).map((item) => <span key={item.id}><i>{item.emoji}</i><b>{item.name}</b><em>{money(item.price)}</em></span>)}</div>
            </div>
            <div className="showcase-card float-card"><Smartphone /><span>{isAr ? "دفع محلي" : "Paiement local"}</span><strong>D17 · Flouci</strong></div>
          </div>
        </section>

        <section className="catalog-section" id="catalog">
          <div className="section-heading"><div><span className="eyebrow">Trust Market Selection</span><h2>{t.products}</h2><p>{t.productsLead}</p></div><label className="search-box"><Search /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t.search} /></label></div>
          <div className="category-tabs"><button className={serviceId === "all" ? "active" : ""} onClick={() => setServiceId("all")}>{t.all}</button>{data.services.map((service) => <button className={serviceId === String(service.id) ? "active" : ""} onClick={() => setServiceId(String(service.id))} key={service.id}><span>{service.emoji}</span>{service.name}</button>)}</div>
          <div className="product-grid">
            {loading ? Array.from({ length: 6 }).map((_, index) => <div className="product-card skeleton" key={index} />) : visible.map((product, index) => (
              <article className="product-card" style={{ "--delay": `${index * 45}ms` }} key={product.id}>
                <div className="product-art"><span>{product.emoji}</span><small>{product.serviceName}</small><i className={product.available ? "online" : "offline"}>{product.available ? t.available : t.unavailable}</i></div>
                <div className="product-copy"><h3>{product.name}</h3><p>{product.description || product.warranty || (isAr ? "خدمة رقمية مضمونة" : "Service numérique vérifié")}</p><div className="product-footer"><div><small>{t.from}</small><strong>{money(product.price)}</strong></div><button disabled={!product.available} onClick={() => setCheckout(product)}>{t.buy}<ChevronRight size={17} /></button></div></div>
              </article>
            ))}
          </div>
        </section>

        <section className="how-section" id="how"><div className="section-heading centered"><div><span className="eyebrow">Simple & transparent</span><h2>{t.how}</h2></div></div><div className="steps"><article><span>01</span><ShoppingBag /><h3>{t.step1}</h3><p>{t.step1Text}</p></article><article><span>02</span><FileCheck2 /><h3>{t.step2}</h3><p>{t.step2Text}</p></article><article><span>03</span><Check /><h3>{t.step3}</h3><p>{t.step3Text}</p></article></div></section>
      </main>

      <footer><div className="logo"><span>TM</span><div><strong>Trust Market</strong><small>TN</small></div></div><p>{t.footer}</p><small>© {new Date().getFullYear()} Trust Market TN · {t.rights}</small></footer>
      <a className="whatsapp-float" href={whatsappUrl} target="_blank" rel="noreferrer" aria-label="WhatsApp"><MessageCircle /></a>
      {checkout && <Checkout product={checkout} methods={data.payment_methods} lang={lang} copy={t} whatsapp={data.whatsapp} onClose={() => setCheckout(null)} />}
    </div>
  );
}

function Checkout({ product, methods, lang, copy: t, whatsapp, onClose }) {
  const [form, setForm] = useState({ name: "", phone: "", email: "", quantity: 1, payment_method: methods[0]?.id || "d17", transaction_reference: "" });
  const [proof, setProof] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(null);
  const total = product.price * Number(form.quantity || 1);
  const submit = async (event) => {
    event.preventDefault(); setError("");
    if (!proof) { setError(t.required); return; }
    setBusy(true);
    try {
      const data = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = reject; reader.readAsDataURL(proof); });
      const response = await fetch("/api/storefront/orders", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...form, offer_id: product.id, proof: { name: proof.name, type: proof.type, data } }) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Erreur");
      localStorage.setItem(`bm-order-${payload.order_id}`, payload.tracking_token);
      setSuccess(payload);
    } catch (requestError) { setError(requestError.message); } finally { setBusy(false); }
  };
  const supportUrl = success ? `https://wa.me/${whatsapp}?text=${encodeURIComponent(lang === "ar" ? `السلام عليكم، أحتاج إلى مساعدة بخصوص الطلب رقم #${success.order_id}.` : `Bonjour, j’ai besoin d’aide concernant la commande #${success.order_id}.`)}` : "";
  return <div className="modal-backdrop" onMouseDown={onClose}><section className="checkout-modal" onMouseDown={(event) => event.stopPropagation()}><header><div><span>{product.serviceName}</span><h2>{success ? t.success : t.checkout}</h2></div><button onClick={onClose}><X /></button></header>{success ? <div className="success-state"><span><Check /></span><h3>{t.order} #{success.order_id}</h3><p>{t.successText}</p><strong>{money(success.total)}</strong><a href={supportUrl} target="_blank" rel="noreferrer"><MessageCircle />WhatsApp</a><button onClick={onClose}>{t.close}</button></div> : <form onSubmit={submit}><div className="checkout-product"><span>{product.emoji}</span><div><strong>{product.name}</strong><small>{product.serviceName}</small></div><b>{money(total)}</b></div><h3>{t.customer}</h3><div className="form-grid"><label><span>{t.name}</span><input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label><label><span>{t.phone}</span><input required inputMode="tel" placeholder="+216 20 000 000" value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} /></label><label><span>{t.email}</span><input type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label><label><span>{t.quantity}</span><input type="number" min="1" max="10" value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} /></label></div><h3>{t.payment}</h3><div className="payment-methods">{methods.map((method) => <button type="button" className={form.payment_method === method.id ? "active" : ""} onClick={() => setForm({ ...form, payment_method: method.id })} key={method.id}>{method.label}</button>)}</div><label className="full-field"><span>{t.reference}</span><input required value={form.transaction_reference} onChange={(event) => setForm({ ...form, transaction_reference: event.target.value })} /></label><label className={`upload-field ${proof ? "ready" : ""}`}><Upload /><strong>{proof ? proof.name : t.receipt}</strong><small>{t.receiptHelp}</small><input required type="file" accept="image/jpeg,image/png,application/pdf" onChange={(event) => setProof(event.target.files?.[0] || null)} /></label>{error && <div className="form-error">{error}</div>}<div className="checkout-submit"><div><small>{t.total}</small><strong>{money(total)}</strong></div><button disabled={busy}>{busy ? t.sending : t.submit}<ArrowRight /></button></div></form>}</section></div>;
}

export default App;
