"""
Internationalisation FR / EN / AR.
Usage : t(lang, "key", **kwargs)
"""
import contextlib

TRANSLATIONS = {
    # ---------------- Démarrage / langue ----------------
    "choose_lang": {
        "fr": "🌍 Bienvenue ! Choisissez votre langue :",
        "en": "🌍 Welcome! Please choose your language:",
        "ar": "🌍 مرحباً! الرجاء اختيار لغتك:",
    },
    "lang_set": {
        "fr": "✅ Langue définie : Français",
        "en": "✅ Language set: English",
        "ar": "✅ تم تعيين اللغة: العربية",
    },
    "welcome": {
        "fr": "👋 Bienvenue sur *{shop}* !\n\nVotre boutique de services numériques premium à prix imbattables. Paiement rapide via Binance Pay et livraison assurée.\n\nUtilisez le menu ci-dessous :",
        "en": "👋 Welcome to *{shop}*!\n\nYour premium digital services store at unbeatable prices. Fast payment via Binance Pay and guaranteed delivery.\n\nUse the menu below:",
        "ar": "👋 مرحباً بك في *{shop}*!\n\nمتجرك للخدمات الرقمية المميزة بأسعار لا تُقاوم. دفع سريع عبر Binance Pay وتسليم مضمون.\n\nاستخدم القائمة أدناه:",
    },
    # ---------------- Menu principal ----------------
    "menu_catalog": {"fr": "🛍️ Catalogue", "en": "🛍️ Catalog", "ar": "🛍️ الكتالوج"},
    "menu_orders": {"fr": "📦 Mes commandes", "en": "📦 My orders", "ar": "📦 طلباتي"},
    "menu_lang": {"fr": "🌍 Langue", "en": "🌍 Language", "ar": "🌍 اللغة"},
    "menu_help": {"fr": "ℹ️ Aide", "en": "ℹ️ Help", "ar": "ℹ️ مساعدة"},
    "menu_admin": {"fr": "🛠️ Admin", "en": "🛠️ Admin", "ar": "🛠️ المشرف"},
    "menu_affiliate": {"fr": "💸 Mon affiliation", "en": "💸 My affiliate", "ar": "💸 الإحالات"},
    "menu_account": {"fr": "👤 Mon compte", "en": "👤 My account", "ar": "👤 حسابي"},
    "affiliate_title": {
        "fr": "💸 *Programme d'affiliation*\n\n👥 Filleuls : *{count}*\n🎯 Progression : *{progress}/{target}*\n💰 Solde : *{balance}$*\n\nInvitez {target} nouvelles personnes avec votre lien et recevez *{reward}$*. Chaque personne ne peut compter qu'une fois.\n\n🔗 Votre lien :\n`{link}`",
        "en": "💸 *Affiliate program*\n\n👥 Referrals: *{count}*\n🎯 Progress: *{progress}/{target}*\n💰 Balance: *{balance}$*\n\nInvite {target} new people with your link and receive *{reward}$*. Each person counts only once.\n\n🔗 Your link:\n`{link}`",
        "ar": "💸 *برنامج الإحالة*\n\n👥 الإحالات: *{count}*\n🎯 التقدم: *{progress}/{target}*\n💰 الرصيد: *{balance}$*\n\nادعُ {target} أشخاص جدد واربح *{reward}$*.\n\n🔗 رابطك:\n`{link}`",
    },
    "affiliate_share": {"fr": "📤 Partager mon lien", "en": "📤 Share my link", "ar": "📤 مشاركة الرابط"},
    "affiliate_open": {"fr": "🔗 Ouvrir le lien", "en": "🔗 Open link", "ar": "🔗 فتح الرابط"},
    "affiliate_rewarded": {
        "fr": "🎉 Bravo ! Vous avez atteint {count} filleuls. *{reward}$* ont été ajoutés à votre solde.",
        "en": "🎉 Congratulations! You reached {count} referrals. *{reward}$* was added to your balance.",
        "ar": "🎉 مبروك! وصلت إلى {count} إحالات. تمت إضافة *{reward}$* إلى رصيدك.",
    },
    # ---------------- Catalogue ----------------
    "catalog_title": {
        "fr": "🛍️ *Catalogue {shop}*\n\nChoisissez un service :",
        "en": "🛍️ *{shop} Catalog*\n\nChoose a service:",
        "ar": "🛍️ *كتالوج {shop}*\n\nاختر خدمة:",
    },
    "service_title": {
        "fr": "{emoji} *{name}*\n\nChoisissez une offre :",
        "en": "{emoji} *{name}*\n\nChoose an offer:",
        "ar": "{emoji} *{name}*\n\nاختر عرضاً:",
    },
    "stock_label": {"fr": "stock", "en": "stock", "ar": "المخزون"},
    "no_offers": {
        "fr": "Aucune offre disponible pour ce service pour le moment.",
        "en": "No offers available for this service right now.",
        "ar": "لا توجد عروض متاحة لهذه الخدمة حالياً.",
    },
    "price_tbd": {
        "fr": "Prix à venir",
        "en": "Price coming soon",
        "ar": "السعر قريباً",
    },
    "out_of_stock": {
        "fr": "❌ Rupture de stock",
        "en": "❌ Out of stock",
        "ar": "❌ نفذ المخزون",
    },
    # ---------------- Détail offre ----------------
    "offer_detail": {
        "fr": "{emoji} *{service}*\n\n📋 Offre : *{offer}*\n💵 Prix : *{price} {cur}*\n📦 Stock : *{stock}*\n{note}",
        "en": "{emoji} *{service}*\n\n📋 Offer: *{offer}*\n💵 Price: *{price} {cur}*\n📦 Stock: *{stock}*\n{note}",
        "ar": "{emoji} *{service}*\n\n📋 العرض: *{offer}*\n💵 السعر: *{price} {cur}*\n📦 المخزون: *{stock}*\n{note}",
    },
    "btn_buy": {"fr": "🛒 Acheter maintenant", "en": "🛒 Buy now", "ar": "🛒 اشترِ الآن"},
    "btn_back": {"fr": "⬅️ Retour", "en": "⬅️ Back", "ar": "⬅️ رجوع"},
    "btn_back_services": {
        "fr": "⬅️ Retour aux services",
        "en": "⬅️ Back to services",
        "ar": "⬅️ العودة إلى الخدمات",
    },
    "btn_main_menu": {"fr": "🖤 Retour à BlackMarket", "en": "🖤 Return to BlackMarket", "ar": "🖤 العودة إلى BlackMarket"},
    "btn_refresh": {"fr": "🔄 Actualiser les services", "en": "🔄 Refresh services", "ar": "🔄 تحديث الخدمات"},
    "btn_confirm": {"fr": "✅ Confirmer l'achat", "en": "✅ Confirm purchase", "ar": "✅ تأكيد الشراء"},
    "btn_cancel": {"fr": "❌ Annuler", "en": "❌ Cancel", "ar": "❌ إلغاء"},
    "btn_continue_payment": {"fr": "💳 Continuer le paiement", "en": "💳 Continue payment", "ar": "💳 متابعة الدفع"},
    "btn_new_order": {"fr": "🆕 Nouvelle commande", "en": "🆕 New order", "ar": "🆕 طلب جديد"},
    "btn_delivery_ok": {"fr": "✅ Tout fonctionne", "en": "✅ Everything works", "ar": "✅ كل شيء يعمل"},
    "btn_delivery_problem": {"fr": "⚠️ Signaler un problème", "en": "⚠️ Report a problem", "ar": "⚠️ الإبلاغ عن مشكلة"},
    "cat_other": {"fr": "📦 Autres services", "en": "📦 Other services", "ar": "📦 خدمات أخرى"},
    # ---------------- Confirmation d'achat ----------------
    "confirm_purchase": {
        "fr": "🧾 *Résumé de votre commande*\n\n{emoji} Service : *{service}*\n📋 Offre : *{offer}*\n💵 Prix unitaire : *{price} {cur}*\n📦 Quantité : *{qty}*\n💰 Total : *{total} {cur}*\n\nConfirmez-vous cet achat ?",
        "en": "🧾 *Order summary*\n\n{emoji} Service: *{service}*\n📋 Offer: *{offer}*\n💵 Unit price: *{price} {cur}*\n📦 Quantity: *{qty}*\n💰 Total: *{total} {cur}*\n\nDo you confirm this purchase?",
        "ar": "🧾 *ملخص الطلب*\n\n{emoji} الخدمة: *{service}*\n📋 العرض: *{offer}*\n💵 السعر: *{price} {cur}*\n📦 الكمية: *{qty}*\n💰 الإجمالي: *{total} {cur}*\n\nهل تؤكد هذا الشراء؟",
    },
    "duplicate_order": {
        "fr": "⚠️ *Commande existante détectée*\n\nVous avez déjà une commande #{oid} en attente pour *{offer}* ({total} {cur}).\n\nQue souhaitez-vous faire ?",
        "en": "⚠️ *Existing order detected*\n\nYou already have a pending order #{oid} for *{offer}* ({total} {cur}).\n\nWhat would you like to do?",
        "ar": "⚠️ *تم اكتشاف طلب موجود*\n\nلديك بالفعل طلب #{oid} معلق لـ *{offer}* ({total} {cur}).\n\nماذا تريد أن تفعل؟",
    },
    "already_paid": {
        "fr": "ℹ️ La commande #{oid} a déjà été payée.",
        "en": "ℹ️ Order #{oid} has already been paid.",
        "ar": "ℹ️ الطلب #{oid} تم دفعه بالفعل.",
    },
    # ---------------- Paiement ----------------
    "order_created": {
        "fr": "🧾 *Commande #{oid} créée*\n\nService : *{service}*\nOffre : *{offer}*\nQuantité : *{qty}*\nMontant total : *{total} {cur}*\n\n💳 *Paiement via Binance Pay*\n\n1️⃣ Envoyez *{total} {cur}* à l'ID Binance Pay :\n`{binance_id}`\n\n2️⃣ Après le paiement, appuyez sur le bouton ci-dessous et envoyez l'*ID de transaction Binance*.",
        "en": "🧾 *Order #{oid} created*\n\nService: *{service}*\nOffer: *{offer}*\nQuantity: *{qty}*\nTotal amount: *{total} {cur}*\n\n💳 *Payment via Binance Pay*\n\n1️⃣ Send *{total} {cur}* to Binance Pay ID:\n`{binance_id}`\n\n2️⃣ After payment, tap the button below and send the *Binance transaction ID*.",
        "ar": "🧾 *تم إنشاء الطلب #{oid}*\n\nالخدمة: *{service}*\nالعرض: *{offer}*\nالكمية: *{qty}*\nالمبلغ الإجمالي: *{total} {cur}*\n\n💳 *الدفع عبر Binance Pay*\n\n1️⃣ أرسل *{total} {cur}* إلى معرّف Binance Pay:\n`{binance_id}`\n\n2️⃣ بعد الدفع، اضغط الزر أدناه وأرسل *رقم معاملة Binance*.",
    },
    "btn_paid": {
        "fr": "✅ J'ai payé — saisir l'ID de transaction",
        "en": "✅ I have paid — enter transaction ID",
        "ar": "✅ لقد دفعت — أدخل رقم المعاملة",
    },
    "ask_txid": {
        "fr": "✍️ Veuillez envoyer l'*ID de transaction Binance* de votre paiement pour la commande #{oid} :",
        "en": "✍️ Please send the *Binance transaction ID* of your payment for order #{oid}:",
        "ar": "✍️ الرجاء إرسال *رقم معاملة Binance* الخاص بدفعتك للطلب #{oid}:",
    },
    "verifying": {
        "fr": "🔎 Vérification automatique de votre paiement en cours... Merci de patienter quelques instants.",
        "en": "🔎 Automatically verifying your payment... Please wait a moment.",
        "ar": "🔎 جارٍ التحقق التلقائي من دفعتك... الرجاء الانتظار قليلاً.",
    },
    "verify_ok": {
        "fr": "✅ *Paiement confirmé !* Commande #{oid}\n\nVotre commande est en cours de préparation. Vous recevrez votre produit ici très bientôt. Merci pour votre achat ! 🎉",
        "en": "✅ *Payment confirmed!* Order #{oid}\n\nYour order is being prepared. You'll receive your product here very soon. Thank you for your purchase! 🎉",
        "ar": "✅ *تم تأكيد الدفع!* الطلب #{oid}\n\nيتم تجهيز طلبك. ستستلم منتجك هنا قريباً جداً. شكراً لشرائك! 🎉",
    },
    "verify_failed": {
        "fr": "❌ Paiement non confirmé automatiquement pour la commande #{oid}. Vérifiez le TXID, le montant et la devise, puis appuyez de nouveau sur *J'ai payé* pour réessayer.",
        "en": "❌ Payment was not automatically confirmed for order #{oid}. Check the TXID, amount and currency, then tap *I have paid* again to retry.",
        "ar": "❌ لم يتم تأكيد دفع الطلب #{oid} تلقائياً. تحقق من رقم المعاملة والمبلغ والعملة ثم حاول مرة أخرى.",
    },
    "txid_too_short": {
        "fr": "⚠️ Cet ID de transaction semble invalide. Veuillez vérifier et renvoyer l'ID de transaction Binance.",
        "en": "⚠️ This transaction ID looks invalid. Please check and resend the Binance transaction ID.",
        "ar": "⚠️ يبدو رقم المعاملة غير صالح. الرجاء التحقق وإعادة إرسال رقم معاملة Binance.",
    },
    # ---------------- Commandes ----------------
    "my_orders_title": {
        "fr": "📦 *Vos commandes*",
        "en": "📦 *Your orders*",
        "ar": "📦 *طلباتك*",
    },
    "no_orders": {
        "fr": "Vous n'avez aucune commande pour le moment.",
        "en": "You have no orders yet.",
        "ar": "ليس لديك أي طلبات حتى الآن.",
    },
    "order_line": {
        "fr": "#{oid} • {offer} • {total} {cur} • {status}",
        "en": "#{oid} • {offer} • {total} {cur} • {status}",
        "ar": "#{oid} • {offer} • {total} {cur} • {status}",
    },
    # statuts lisibles
    "status_pending_payment": {"fr": "💳 En attente de paiement", "en": "💳 Awaiting payment", "ar": "💳 بانتظار الدفع"},
    "status_awaiting_verification": {"fr": "🔎 Vérification en cours", "en": "🔎 Under verification", "ar": "🔎 قيد التحقق"},
    "status_paid": {"fr": "✅ Payée (préparation)", "en": "✅ Paid (preparing)", "ar": "✅ مدفوعة (قيد التجهيز)"},
    "status_payment_confirmed": {"fr": "✅ Paiement confirmé", "en": "✅ Payment confirmed", "ar": "✅ تم تأكيد الدفع"},
    "status_preparing_delivery": {"fr": "📦 Préparation en cours", "en": "📦 Preparing delivery", "ar": "📦 قيد التجهيز"},
    "status_delivered": {"fr": "🎁 Livrée", "en": "🎁 Delivered", "ar": "🎁 تم التسليم"},
    "status_cancelled": {"fr": "❌ Annulée", "en": "❌ Cancelled", "ar": "❌ ملغاة"},
    "status_rejected": {"fr": "🚫 Refusée", "en": "🚫 Rejected", "ar": "🚫 مرفوضة"},
    "status_manual_review": {"fr": "🔍 Vérification manuelle", "en": "🔍 Manual review", "ar": "🔍 مراجعة يدوية"},
    "status_expired": {"fr": "⏰ Expirée", "en": "⏰ Expired", "ar": "⏰ منتهية الصلاحية"},
    "status_refunded": {"fr": "💸 Remboursée", "en": "💸 Refunded", "ar": "💸 تم الاسترداد"},
    "status_verification_failed": {"fr": "❌ Échec de vérification", "en": "❌ Verification failed", "ar": "❌ فشل التحقق"},
    # ---------------- Livraison ----------------
    "delivery_received": {
        "fr": "🎁 *Votre commande #{oid} est livrée !*\n\nService : *{service}* — {offer}\n\n{content}\n\nMerci pour votre confiance ! 💜",
        "en": "🎁 *Your order #{oid} has been delivered!*\n\nService: *{service}* — {offer}\n\n{content}\n\nThank you for your trust! 💜",
        "ar": "🎁 *تم تسليم طلبك #{oid}!*\n\nالخدمة: *{service}* — {offer}\n\n{content}\n\nشكراً لثقتك! 💜",
    },
    # ---------------- Aide ----------------
    "help_text": {
        "fr": "ℹ️ *Aide {shop}*\n\n• Parcourez le *Catalogue*, choisissez un service puis une offre.\n• Payez via *Binance Pay* à l'ID indiqué.\n• Envoyez votre *ID de transaction* : le paiement est vérifié automatiquement.\n• Après confirmation, l'équipe vous livre votre produit ici.\n\nBesoin d'aide ? Contactez l'administrateur.",
        "en": "ℹ️ *{shop} Help*\n\n• Browse the *Catalog*, pick a service then an offer.\n• Pay via *Binance Pay* to the shown ID.\n• Send your *transaction ID*: payment is verified automatically.\n• After confirmation, the team delivers your product here.\n\nNeed help? Contact the administrator.",
        "ar": "ℹ️ *مساعدة {shop}*\n\n• تصفّح *الكتالوج*، اختر خدمة ثم عرضاً.\n• ادفع عبر *Binance Pay* إلى المعرّف الظاهر.\n• أرسل *رقم المعاملة*: يتم التحقق من الدفع تلقائياً.\n• بعد التأكيد، يقوم الفريق بتسليم منتجك هنا.\n\nتحتاج مساعدة؟ تواصل مع المشرف.",
    },
    "cancelled_msg": {
        "fr": "❌ Opération annulée.",
        "en": "❌ Operation cancelled.",
        "ar": "❌ تم إلغاء العملية.",
    },
    "not_for_you": {
        "fr": "Cette action ne vous est pas destinée.",
        "en": "This action is not for you.",
        "ar": "هذا الإجراء ليس لك.",
    },
}


def t(lang, key, **kwargs):
    if lang not in ("fr", "en", "ar"):
        lang = "fr"
    entry = TRANSLATIONS.get(key, {})
    text = entry.get(lang) or entry.get("fr") or key
    if kwargs:
        with contextlib.suppress(KeyError, IndexError):
            text = text.format(**kwargs)
    return text


def status_label(lang, status):
    return t(lang, f"status_{status}")
