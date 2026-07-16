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
        "fr": "✨ *Bienvenue sur {shop}*\n\nDécouvrez une sélection de services numériques premium, soigneusement présentés et régulièrement mis à jour.\n\n⚡ Accès rapide aux offres disponibles\n🛡️ Informations claires et service fiable\n🎯 Assistance dédiée à chaque étape\n\nChoisissez votre espace pour commencer :",
        "en": "✨ *Welcome to {shop}*\n\nDiscover a curated selection of premium digital services, clearly presented and regularly updated.\n\n⚡ Quick access to available offers\n🛡️ Clear information and reliable service\n🎯 Dedicated assistance at every step\n\nChoose where you would like to begin:",
        "ar": "✨ *مرحبًا بك في {shop}*\n\nاكتشف مجموعة مختارة من الخدمات الرقمية المميزة، مع عرض واضح وتحديث مستمر.\n\n⚡ وصول سريع إلى العروض المتاحة\n🛡️ معلومات واضحة وخدمة موثوقة\n🎯 مساعدة مخصصة في كل خطوة\n\nاختر القسم الذي تريد البدء منه:",
    },
    # ---------------- Menu principal ----------------
    "menu_catalog": {"fr": "🛍️ Catalogue", "en": "🛍️ Catalog", "ar": "🛍️ المتجر"},
    "menu_orders": {"fr": "🧾 Mes commandes", "en": "🧾 My orders", "ar": "🧾 طلباتي"},
    "menu_topup": {"fr": "💳 Recharger le solde", "en": "💳 Top Up Balance", "ar": "💳 شحن الرصيد"},
    "menu_lang": {"fr": "🌐 Langue", "en": "🌐 Language", "ar": "🌐 Language"},
    "menu_help": {"fr": "❓ Aide", "en": "❓ Help", "ar": "❓ المساعدة"},
    "menu_admin": {"fr": "🛠️ Admin", "en": "🛠️ Admin", "ar": "🛠️ المشرف"},
    "menu_affiliate": {"fr": "🎁 Affiliation", "en": "🎁 Affiliate", "ar": "🎁 الإحالة"},
    "menu_account": {"fr": "👤 Mon compte", "en": "👤 My account", "ar": "👤 حسابي"},
    "menu_support": {"fr": "🛎️ Support", "en": "🛎️ Support", "ar": "🛎️ Support"},
    "topup_message": {
        "fr": "✍️ *Envoyez le montant souhaité — minimum 1 USDT*\nLe même montant sera ajouté à votre portefeuille.\n\n🟡 *Recharge Binance Pay*\n\nEnvoyez le montant vers notre Binance Pay ID :\n`{binance_id}`\n\n⚠️ *Important*\nAjoutez votre Telegram ID dans le champ Notes / Mémo :\n`{telegram_id}`\n\nAprès le transfert, appuyez sur *Réclamer le transfert* puis envoyez votre TXID.",
        "en": "✍️ *Send any amount — minimum 1 USDT*\nThe same amount will be added to your wallet.\n\n🟡 *Binance Pay Top Up*\n\nSend the amount to our Binance Pay ID:\n`{binance_id}`\n\n⚠️ *Important*\nAdd your Telegram ID in the Notes / Memo field:\n`{telegram_id}`\n\nAfter transferring, tap *Claim Transfer* and send your TXID.",
        "ar": "✍️ *أرسل أي مبلغ — الحد الأدنى 1 USDT*\nسيتم إضافة نفس المبلغ إلى محفظتك.\n\nأرسل المبلغ إلى Binance Pay ID:\n`{binance_id}`\n\n⚠️ أضف معرف تيليغرام في الملاحظات:\n`{telegram_id}`\n\nبعد التحويل اضغط المطالبة بالتحويل وأرسل TXID.",
    },
    "topup_claim": {"fr": "✅ Réclamer le transfert", "en": "✅ Claim Transfer", "ar": "✅ المطالبة بالتحويل"},
    "topup_ask_txid": {
        "fr": "🔎 Envoyez maintenant le *TXID* du transfert. Il sera vérifié avant tout crédit.",
        "en": "🔎 Send the transfer *TXID* now. It will be verified before crediting.",
        "ar": "🔎 أرسل الآن *TXID* للتحقق منه قبل إضافة الرصيد.",
    },
    "topup_success": {
        "fr": "✅ *Recharge confirmée*\n\nMontant ajouté : *{amount} USDT*\nNouveau solde : *{balance} USDT*",
        "en": "✅ *Top up confirmed*\n\nAmount added: *{amount} USDT*\nNew balance: *{balance} USDT*",
        "ar": "✅ *تم شحن الرصيد*\n\nالمبلغ المضاف: *{amount} USDT*\nالرصيد الجديد: *{balance} USDT*",
    },
    "topup_failed": {
        "fr": "⚠️ Recharge non confirmée : {reason}\nVérifiez le TXID puis réessayez.",
        "en": "⚠️ Top up not confirmed: {reason}\nCheck the TXID and try again.",
        "ar": "⚠️ لم يتم تأكيد الشحن: {reason}",
    },
    "wallet_payment_processing": {
        "fr": "💳 *Paiement par portefeuille confirmé*\n\nPréparation de votre livraison…",
        "en": "💳 *Wallet payment confirmed*\n\nPreparing your delivery…",
        "ar": "💳 *تم الدفع بالمحفظة*\n\nجارٍ تجهيز التسليم…",
    },
    "support_admin_contact": {
        "fr": "🛎️ *Support BlackMarket*\n\nPour toute question ou assistance, contactez directement notre administrateur :\n\n👤 {admin}\n\nMerci de préciser votre numéro de commande si votre demande concerne un achat.",
        "en": "🛎️ *BlackMarket Support*\n\nFor questions or assistance, contact our administrator directly:\n\n👤 {admin}\n\nPlease include your order number when your request concerns a purchase.",
        "ar": "🛎️ *دعم BlackMarket*\n\nلأي سؤال أو مساعدة، تواصل مباشرة مع المسؤول:\n\n👤 {admin}\n\nيرجى إرسال رقم الطلب إذا كان طلبك متعلقًا بعملية شراء.",
    },
    "support_prompt": {
        "fr": "🎫 Décrivez votre problème. Vous pourrez continuer la conversation dans ce ticket.",
        "en": "🎫 Describe your issue. You will be able to continue the conversation in this ticket.",
        "ar": "🎫 اشرح مشكلتك. يمكنك متابعة المحادثة داخل هذه التذكرة.",
    },
    "support_choose_category": {
        "fr": "🎫 Choisissez la catégorie de votre demande :",
        "en": "🎫 Choose the category of your request:",
        "ar": "🎫 اختر فئة طلبك:",
    },
    "support_choose_order": {
        "fr": "Sélectionnez la commande concernée, ou choisissez « Aucune » :",
        "en": "Select the related order, or choose “None”:",
        "ar": "اختر الطلب المعني أو اختر «لا يوجد»:",
    },
    "support_no_order": {"fr": "Aucune commande", "en": "No order", "ar": "لا يوجد طلب"},
    "support_category_payment": {"fr": "💳 Paiement", "en": "💳 Payment", "ar": "💳 الدفع"},
    "support_category_delivery": {"fr": "📦 Livraison", "en": "📦 Delivery", "ar": "📦 التسليم"},
    "support_category_invalid_content": {"fr": "⚠️ Code ou compte invalide", "en": "⚠️ Invalid code or account", "ar": "⚠️ رمز أو حساب غير صالح"},
    "support_category_order": {"fr": "🧾 Commande", "en": "🧾 Order", "ar": "🧾 الطلب"},
    "support_category_affiliation": {"fr": "👥 Affiliation", "en": "👥 Affiliate", "ar": "👥 الإحالة"},
    "support_category_other": {"fr": "💬 Autre", "en": "💬 Other", "ar": "💬 أخرى"},
    "support_order_prompt": {
        "fr": "⚠️ Décrivez le problème rencontré avec la commande #{oid}.",
        "en": "⚠️ Describe the problem with order #{oid}.",
        "ar": "⚠️ اشرح المشكلة المتعلقة بالطلب #{oid}.",
    },
    "ticket_created": {
        "fr": "✅ Ticket #{tid} créé. Envoyez simplement un autre message pour compléter la conversation.",
        "en": "✅ Ticket #{tid} created. Send another message to continue the conversation.",
        "ar": "✅ تم إنشاء التذكرة #{tid}. أرسل رسالة أخرى لمتابعة المحادثة.",
    },
    "ticket_message_added": {
        "fr": "✅ Message ajouté au ticket #{tid}.",
        "en": "✅ Message added to ticket #{tid}.",
        "ar": "✅ تمت إضافة الرسالة إلى التذكرة #{tid}.",
    },
    "ticket_unavailable": {
        "fr": "Ce ticket est fermé ou indisponible. Utilisez /support pour en créer un nouveau.",
        "en": "This ticket is closed or unavailable. Use /support to create a new one.",
        "ar": "هذه التذكرة مغلقة أو غير متاحة. استخدم /support لإنشاء تذكرة جديدة.",
    },
    "delivery_confirmed": {
        "fr": "✅ Merci pour votre confirmation. La commande est terminée.",
        "en": "✅ Thank you for confirming. The order is complete.",
        "ar": "✅ شكرًا لتأكيدك. اكتمل الطلب.",
    },
    "terms_text": {
        "fr": "📄 *Conditions d’utilisation*\n\nLes produits numériques sont livrés après confirmation du paiement. Vérifiez l’offre et le réseau de paiement avant de confirmer. Contactez le support en cas de problème.",
        "en": "📄 *Terms of service*\n\nDigital products are delivered after payment confirmation. Verify the offer and payment network before confirming. Contact support if you encounter an issue.",
        "ar": "📄 *شروط الاستخدام*\n\nيتم تسليم المنتجات الرقمية بعد تأكيد الدفع. تحقق من العرض وشبكة الدفع قبل التأكيد. تواصل مع الدعم عند وجود مشكلة.",
    },
    "privacy_text": {
        "fr": "🔐 *Confidentialité*\n\nLa boutique conserve uniquement les données nécessaires aux commandes, paiements, livraisons et tickets. Les secrets d’inventaire sont chiffrés et ne sont pas inscrits dans les journaux.",
        "en": "🔐 *Privacy*\n\nThe store only keeps data required for orders, payments, deliveries and tickets. Inventory secrets are encrypted and are never written to logs.",
        "ar": "🔐 *الخصوصية*\n\nيحتفظ المتجر فقط بالبيانات اللازمة للطلبات والمدفوعات والتسليم والتذاكر. بيانات المخزون السرية مشفرة ولا تُكتب في السجلات.",
    },
    "affiliate_title": {
        "fr": "🎊 *PROGRAMME D'AFFILIATION*\n\n📊 *Vos statistiques*\n💰 Gains : *{earned} USDT*\n💳 Portefeuille : *{balance} USDT*\n👥 Invitations : *{referrals}*\n✅ Membres qualifiés : *{rewarded}*\n⌛ En attente : *{pending}*\n📅 Aujourd'hui : *{today}/{daily_cap}*\n\n🔗 *Votre lien*\n`{link}`\n\n🎯 *Paliers quotidiens*\n• 5 membres qualifiés → *{five_reward} USDT*\n• 10 membres qualifiés → *+{ten_reward} USDT*\n\nUn membre devient qualifié après *{qualify} USDT* d'achats confirmés. Maximum : *{daily_cap} membres par jour*.\n\n⚠️ Auto-parrainage et comptes frauduleux refusés.",
        "en": "🎊 *AFFILIATE PROGRAM*\n\n📊 *Your stats*\n💰 Earned: *{earned} USDT*\n💳 Wallet: *{balance} USDT*\n👥 Invites: *{referrals}*\n✅ Qualified members: *{rewarded}*\n⌛ Pending: *{pending}*\n📅 Today: *{today}/{daily_cap}*\n\n🔗 *Your link*\n`{link}`\n\n🎯 *Daily milestones*\n• 5 qualified members → *{five_reward} USDT*\n• 10 qualified members → *+{ten_reward} USDT*\n\nA member qualifies after *{qualify} USDT* in confirmed purchases. Maximum: *{daily_cap} members per day*.\n\n⚠️ Self-referrals and fake accounts are rejected.",
        "ar": "🎊 *برنامج الإحالة*\n\n💰 الأرباح: *{earned} USDT*\n💳 المحفظة: *{balance} USDT*\n👥 الدعوات: *{referrals}*\n✅ المؤهلون: *{rewarded}*\n📅 اليوم: *{today}/{daily_cap}*\n\n🔗 `{link}`\n\n5 أعضاء مؤهلين = *{five_reward} USDT*\n10 أعضاء مؤهلين = *+{ten_reward} USDT*\n\nيتأهل العضو بعد مشتريات مؤكدة بقيمة *{qualify} USDT*. الحد الأقصى *{daily_cap}* أعضاء يوميًا.",
    },
    "affiliate_copy": {"fr": "🔗 Copier le lien", "en": "🔗 Copy Link", "ar": "🔗 نسخ الرابط"},
    "affiliate_copy_message": {
        "fr": "🔗 *Votre lien de parrainage*\n\n`{link}`\n\nMaintenez le lien pour le copier.",
        "en": "🔗 *Your referral link*\n\n`{link}`\n\nPress and hold the link to copy it.",
        "ar": "🔗 *رابط الإحالة الخاص بك*\n\n`{link}`\n\nاضغط مطولًا لنسخ الرابط.",
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
        "fr": "🛍️ *CATALOGUE {shop}*\n\n🟢 Boutique opérationnelle\n⚡ Livraison rapide ou instantanée\n🛡️ Produits vérifiés et support inclus\n\nChoisissez votre univers :",
        "en": "🛍️ *{shop} CATALOG*\n\n🟢 Store operational\n⚡ Fast or instant delivery\n🛡️ Verified products with support\n\nChoose your category:",
        "ar": "🛍️ *كتالوج {shop}*\n\n🟢 المتجر يعمل\n⚡ تسليم سريع أو فوري\n🛡️ منتجات موثوقة مع الدعم\n\nاختر الفئة:",
    },
    "service_title": {
        "fr": "{emoji} *Choisissez l'offre {name} que vous souhaitez acheter :*",
        "en": "{emoji} *Choose the {name} plan you want to purchase:*",
        "ar": "{emoji} *اختر عرض {name} الذي تريد شراءه:*",
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
        "fr": "{emoji} *{offer}*\n\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\n\n\U0001f4ab *DETAILS DE L'OFFRE*\n\n\U0001f6e1 *Warranty*\n{note}\n\n\U000023f3 *Duration*\n{duration}\n\n\U0001f4e7 *Mail*\n{mail}\n\n\U0001f510 *Access*\n{access}\n\n\U0001f69a *Delivery*\n{delivery}\n\n\U0001f48e *Price*\n*{price} {cur}*\n\n\U0001f4e6 *Stock disponible*\n*{stock} compte(s)*\n\n{description}\n\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\n\U0001f680 _Choisissez Acheter maintenant pour selectionner la quantite._",
        "en": "{emoji} *{offer}*\n\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\n\n\U0001f4ab *OFFER DETAILS*\n\n\U0001f6e1 *Warranty*\n{note}\n\n\U000023f3 *Duration*\n{duration}\n\n\U0001f4e7 *Mail*\n{mail}\n\n\U0001f510 *Access*\n{access}\n\n\U0001f69a *Delivery*\n{delivery}\n\n\U0001f48e *Price*\n*{price} {cur}*\n\n\U0001f4e6 *Available stock*\n*{stock} account(s)*\n\n{description}\n\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\n\U0001f680 _Tap Buy now to select quantity._",
        "ar": "{emoji} *{offer}*\n\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\n\n\U0001f4ab *OFFER DETAILS*\n\n\U0001f6e1 *Warranty*\n{note}\n\n\U000023f3 *Duration*\n{duration}\n\n\U0001f4e7 *Mail*\n{mail}\n\n\U0001f510 *Access*\n{access}\n\n\U0001f69a *Delivery*\n{delivery}\n\n\U0001f48e *Price*\n*{price} {cur}*\n\n\U0001f4e6 *Stock*\n*{stock} account(s)*\n\n{description}\n\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\n\U0001f680 _Tap Buy now to select quantity._",
    },
    "btn_buy": {"fr": "🛒 Acheter maintenant", "en": "🛒 Buy now", "ar": "🛒 اشترِ الآن"},
    "btn_back": {"fr": "⬅️ Retour", "en": "⬅️ Back", "ar": "⬅️ رجوع"},
    "btn_back_services": {
        "fr": "🔶 Services",
        "en": "🔶 Services",
        "ar": "🔶 الخدمات",
    },
    "btn_main_menu": {"fr": "🖤 Retour à BlackMarket", "en": "🖤 Return to BlackMarket", "ar": "🖤 العودة إلى BlackMarket"},
    "btn_refresh": {"fr": "🔄 Actualiser les services", "en": "🔄 Refresh services", "ar": "🔄 تحديث الخدمات"},
    "btn_refresh_short": {"fr": "🔄 Actualiser", "en": "🔄 Refresh", "ar": "🔄 تحديث"},
    "btn_main_menu_short": {"fr": "🏠 Accueil", "en": "🏠 Home", "ar": "🏠 الرئيسية"},
    "btn_cancel_short": {"fr": "✖️ Annuler", "en": "✖️ Cancel", "ar": "✖️ إلغاء"},
    "btn_confirm": {"fr": "✅ Confirmer l'achat", "en": "✅ Confirm purchase", "ar": "✅ تأكيد الشراء"},
    "btn_cancel": {"fr": '\u274c Annuler le paiement', "en": '\u274c Cancel Payment', "ar": '\u274c \u0625\u0644\u063a\u0627\u0621 \u0627\u0644\u062f\u0641\u0639'},
    "btn_copy_binance_id": {"fr": '\U0001f9ed Copier Binance ID', "en": '\U0001f9ed Copy Binance ID', "ar": '\U0001f9ed \u0646\u0633\u062e \u0645\u0639\u0631\u0641 Binance'},
    "btn_copy_amount": {"fr": '\U0001f4a5 Copier le montant exact', "en": '\U0001f4a5 Copy exact amount', "ar": '\U0001f4a5 \u0646\u0633\u062e \u0627\u0644\u0645\u0628\u0644\u063a \u0627\u0644\u0635\u062d\u064a\u062d'},
    "copy_binance_id_msg": {"fr": '\U0001f4cc Binance ID : `{binance_id}`', "en": '\U0001f4cc Binance ID: `{binance_id}`', "ar": '\U0001f4cc \u0645\u0639\u0631\u0641 Binance: `{binance_id}`'},
    "copy_amount_msg": {"fr": '\U0001f4b8 Montant exact : `{total}` *{cur}*', "en": '\U0001f4b8 Exact amount: `{total}` *{cur}*', "ar": '\U0001f4b8 \u0627\u0644\u0645\u0628\u0644\u063a \u0627\u0644\u0635\u062d\u064a\u062d: `{total}` *{cur}*'},
    "btn_continue_payment": {"fr": "💳 Continuer le paiement", "en": "💳 Continue payment", "ar": "💳 متابعة الدفع"},
    "btn_new_order": {"fr": "🆕 Nouvelle commande", "en": "🆕 New order", "ar": "🆕 طلب جديد"},
    "btn_delivery_ok": {"fr": "✅ Tout fonctionne", "en": "✅ Everything works", "ar": "✅ كل شيء يعمل"},
    "btn_delivery_problem": {"fr": "⚠️ Signaler un problème", "en": "⚠️ Report a problem", "ar": "⚠️ الإبلاغ عن مشكلة"},
    "cat_other": {"fr": "📦 Autres services", "en": "📦 Other services", "ar": "📦 خدمات أخرى"},
    # ---------------- Confirmation d'achat ----------------
    "choose_quantity": {
        "fr": "\U0001f9ee *Choisissez la quantit\u00e9*\n\nProduit : *{offer}*\nStock disponible : *{stock}*\nPrix unitaire : *{price} {cur}*\n\nS\u00e9lectionnez le nombre de comptes \u00e0 acheter :",
        "en": "\U0001f9ee *Choose quantity*\n\nProduct: *{offer}*\nAvailable stock: *{stock}*\nUnit price: *{price} {cur}*\n\nSelect how many accounts to buy:",
        "ar": "\U0001f9ee *\u0627\u062e\u062a\u0631 \u0627\u0644\u0643\u0645\u064a\u0629*\n\n\u0627\u0644\u0645\u0646\u062a\u062c: *{offer}*\n\u0627\u0644\u0645\u062e\u0632\u0648\u0646 \u0627\u0644\u0645\u062a\u0627\u062d: *{stock}*\n\u0633\u0639\u0631 \u0627\u0644\u0648\u062d\u062f\u0629: *{price} {cur}*\n\n\u0627\u062e\u062a\u0631 \u0639\u062f\u062f \u0627\u0644\u062d\u0633\u0627\u0628\u0627\u062a \u0627\u0644\u062a\u064a \u062a\u0631\u064a\u062f \u0634\u0631\u0627\u0621\u0647\u0627:",
    },
    "confirm_purchase": {
        "fr": "🧾 *Résumé de votre commande*\n\n{emoji} Service : *{service}*\n📋 Offre : *{offer}*\n💵 Prix unitaire : *{price} {cur}*\n📦 Quantité : *{qty}*\n{discount_line}\n💰 Total : *{total} {cur}*\n\nConfirmez-vous cet achat ?",
        "en": "🧾 *Order summary*\n\n{emoji} Service: *{service}*\n📋 Offer: *{offer}*\n💵 Unit price: *{price} {cur}*\n📦 Quantity: *{qty}*\n{discount_line}\n💰 Total: *{total} {cur}*\n\nDo you confirm this purchase?",
        "ar": "🧾 *ملخص الطلب*\n\n{emoji} الخدمة: *{service}*\n📋 العرض: *{offer}*\n💵 السعر: *{price} {cur}*\n📦 الكمية: *{qty}*\n{discount_line}\n💰 الإجمالي: *{total} {cur}*\n\nهل تؤكد هذا الشراء؟",
    },
    "loyalty_discount_line": {
        "fr": "🏆 Niveau {level} : *-{percent}%* (-{amount} {cur})",
        "en": "🏆 {level} level: *-{percent}%* (-{amount} {cur})",
        "ar": "🏆 مستوى {level}: *-{percent}%* (-{amount} {cur})",
    },
    "profile_card": {
        "fr": "👤 <b>MON PROFIL</b>\n\n🪪 <b>Nom :</b> {name}\n🔗 <b>Utilisateur :</b> {username}\n🆔 <b>Telegram ID :</b> <code>{telegram_id}</code>\n\n💳 <b>Portefeuille :</b> {wallet} USDT\n👥 <b>Total invitations :</b> {invites}\n✅ <b>Invitations qualifiées :</b> {qualified}\n🛍️ <b>Total des achats :</b> {total_buy} USDT\n\n🏆 <b>Niveau :</b> {level}\n🎁 <b>Remise active :</b> {discount}%\n⏳ <b>Expiration :</b> {expires}",
        "en": "👤 <b>MY PROFILE</b>\n\n🪪 <b>Name:</b> {name}\n🔗 <b>Username:</b> {username}\n🆔 <b>Telegram ID:</b> <code>{telegram_id}</code>\n\n💳 <b>Wallet:</b> {wallet} USDT\n👥 <b>Total invites:</b> {invites}\n✅ <b>Qualified invites:</b> {qualified}\n🛍️ <b>Total purchases:</b> {total_buy} USDT\n\n🏆 <b>Level:</b> {level}\n🎁 <b>Active discount:</b> {discount}%\n⏳ <b>Expires:</b> {expires}",
        "ar": "👤 <b>ملفي</b>\n\n🪪 <b>الاسم:</b> {name}\n🆔 <b>معرف تيليغرام:</b> <code>{telegram_id}</code>\n💳 <b>المحفظة:</b> {wallet} USDT\n👥 <b>الدعوات:</b> {invites}\n✅ <b>الدعوات المؤهلة:</b> {qualified}\n🛍️ <b>إجمالي المشتريات:</b> {total_buy} USDT\n🏆 <b>المستوى:</b> {level}\n🎁 <b>الخصم:</b> {discount}%\n⏳ <b>الانتهاء:</b> {expires}",
    },
    "loyalty_activated": {
        "fr": "🏆 *Nouveau niveau {level} !*\n\nVous bénéficiez maintenant de *-{discount}%* sur tous les produits pendant 7 jours.",
        "en": "🏆 *New {level} level!*\n\nYou now receive *-{discount}%* on every product for 7 days.",
        "ar": "🏆 *مستوى جديد {level}!*\n\nتحصل الآن على خصم *{discount}%* على جميع المنتجات لمدة 7 أيام.",
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
        "fr": "\U0001f525\U0001f4b3 *Binance Pay*\n--------------------\n\n\U0001f6cd\ufe0f Produit : *{offer}*\n\U0001f4ab Quantit\xe9 : *{qty}*\n\n\U0001f6a8 *ENVOYEZ EXACTEMENT : {total} {cur}*\n\U0001f9ed Binance ID : `{binance_id}`\n\U0001f4dd Notes / M\xe9mo obligatoire : `{telegram_id}`\n\nLe scanner automatique fonctionne pendant *20 secondes*. Le montant et le m\xe9mo doivent correspondre exactement.\n\nSi le paiement n'est pas d\xe9tect\xe9, appuyez sur *V\xe9rifier le paiement* puis collez votre TXID.\n\n\U0001f3af Commande : *#{oid}*",
        "en": "\U0001f525\U0001f4b3 *Binance Pay*\n--------------------\n\n\U0001f6cd\ufe0f Product: *{offer}*\n\U0001f4ab Quantity: *{qty}*\n\n\U0001f6a8 *SEND EXACTLY: {total} {cur}*\n\U0001f9ed Binance ID: `{binance_id}`\n\U0001f4dd Required Notes / Memo: `{telegram_id}`\n\nThe automatic scanner runs for *20 seconds*. The amount and memo must match exactly.\n\nIf the payment is not detected, tap *Check Payment* and paste your TXID.\n\n\U0001f3af Order: *#{oid}*",
        "ar": "🧾 *تم إنشاء الطلب #{oid}*\n\nالخدمة: *{service}*\nالعرض: *{offer}*\nالكمية: *{qty}*\nالمبلغ الإجمالي: *{total} {cur}*\n\n💳 *الدفع عبر Binance Pay*\n\n1️⃣ أرسل *{total} {cur}* إلى معرّف Binance Pay:\n`{binance_id}`\n\n2️⃣ بعد الدفع، اضغط الزر أدناه وأرسل *رقم معاملة Binance*.",
    },
    "btn_paid": {
        "fr": '\U0001f525 V\xe9rifier le paiement',
        "en": '\U0001f525 Check Payment',
        "ar": '\U0001f525 \u0627\u0644\u062a\u062d\u0642\u0642 \u0645\u0646 \u0627\u0644\u062f\u0641\u0639',
    },
    "ask_txid": {
        "fr": "\u270d\ufe0f Veuillez envoyer l'*ID de transaction Binance* de votre paiement pour la commande #{oid}. Si cela \u00e9choue, contactez le support avec une capture du paiement :",
        "en": "\u270d\ufe0f Please send the *Binance transaction ID* for order #{oid}. If it fails, contact support with a payment screenshot:",
        "ar": "\u270d\ufe0f \u0627\u0644\u0631\u062c\u0627\u0621 \u0625\u0631\u0633\u0627\u0644 *\u0631\u0642\u0645 \u0645\u0639\u0627\u0645\u0644\u0629 Binance* \u0644\u0644\u0637\u0644\u0628 #{oid}. \u0625\u0630\u0627 \u0641\u0634\u0644 \u0627\u0644\u062a\u062d\u0642\u0642\u060c \u062a\u0648\u0627\u0635\u0644 \u0645\u0639 \u0627\u0644\u062f\u0639\u0645 \u0645\u0639 \u0644\u0642\u0637\u0629 \u0634\u0627\u0634\u0629 \u0644\u0644\u062f\u0641\u0639:",
    },
    "auto_check_started": {
        "fr": "\U0001f680 V\u00e9rification automatique lanc\u00e9e pendant *{seconds} secondes*... Le bot cherche un paiement avec le montant exact.",
        "en": "\U0001f680 Automatic verification started for *{seconds} seconds*... The bot is looking for a payment with the exact amount.",
        "ar": "\U0001f680 \u0628\u062f\u0623 \u0627\u0644\u062a\u062d\u0642\u0642 \u0627\u0644\u062a\u0644\u0642\u0627\u0626\u064a \u0644\u0645\u062f\u0629 *{seconds} \u062b\u0627\u0646\u064a\u0629*... \u064a\u0628\u062d\u062b \u0627\u0644\u0628\u0648\u062a \u0639\u0646 \u062f\u0641\u0639\u0629 \u0628\u0627\u0644\u0645\u0628\u0644\u063a \u0627\u0644\u0635\u062d\u064a\u062d.",
    },
    "btn_pay_wallet": {
        "fr": "💳 Payer avec mon solde",
        "en": "💳 Pay with my balance",
        "ar": "💳 الدفع من الرصيد",
    },
    "btn_pay_binance": {
        "fr": "🟡 Payer avec Binance Pay",
        "en": "🟡 Pay with Binance Pay",
        "ar": "🟡 الدفع عبر Binance Pay",
    },
    "onboarding_1": {
        "fr": "✨ *Bienvenue dans l’univers {shop}*\n\nDes services numériques premium, présentés simplement et accessibles en quelques secondes.\n\n`1/3`  Découvrir",
        "en": "✨ *Welcome to the {shop} experience*\n\nPremium digital services, clearly presented and available in seconds.\n\n`1/3`  Discover",
        "ar": "✨ *مرحبًا بك في عالم {shop}*\n\nخدمات رقمية مميزة وواضحة ومتاحة خلال ثوانٍ.\n\n`1/3`  اكتشف",
    },
    "onboarding_2": {
        "fr": "💳 *Paiement simple et sécurisé*\n\n1️⃣ Choisissez votre produit\n2️⃣ Payez le montant exact via Binance Pay\n3️⃣ Le scanner confirme automatiquement\n\n`2/3`  Paiement",
        "en": "💳 *Simple and secure payment*\n\n1️⃣ Choose your product\n2️⃣ Pay the exact amount with Binance Pay\n3️⃣ The scanner confirms automatically\n\n`2/3`  Payment",
        "ar": "💳 *دفع بسيط وآمن*\n\n1️⃣ اختر المنتج\n2️⃣ ادفع المبلغ الدقيق عبر Binance Pay\n3️⃣ يؤكد الماسح الدفع تلقائيًا\n\n`2/3`  الدفع",
    },
    "onboarding_3": {
        "fr": "⚡ *Livraison et accompagnement*\n\n📦 Livraison rapide ou instantanée\n🛡️ Garantie indiquée sur chaque offre\n🎫 Support accessible depuis chaque étape\n\n`3/3`  Vous êtes prêt !",
        "en": "⚡ *Delivery and assistance*\n\n📦 Fast or instant delivery\n🛡️ Warranty shown on every offer\n🎫 Support available at every step\n\n`3/3`  You are ready!",
        "ar": "⚡ *التسليم والمساعدة*\n\n📦 تسليم سريع أو فوري\n🛡️ ضمان واضح لكل عرض\n🎫 الدعم متاح في كل خطوة\n\n`3/3`  أنت جاهز!",
    },
    "onboarding_next": {"fr": "Continuer  ›", "en": "Continue  ›", "ar": "متابعة  ›"},
    "onboarding_start": {"fr": "🚀 Découvrir le catalogue", "en": "🚀 Explore the catalog", "ar": "🚀 اكتشف المتجر"},
    "order_card": {
        "fr": "🧾 *COMMANDE #{oid}*\n\n🛍️ Produit : *{offer}*\n📦 Quantité : *{qty}*\n💎 Total : *{total} {cur}*\n📍 Statut : *{status}*",
        "en": "🧾 *ORDER #{oid}*\n\n🛍️ Product: *{offer}*\n📦 Quantity: *{qty}*\n💎 Total: *{total} {cur}*\n📍 Status: *{status}*",
        "ar": "🧾 *الطلب #{oid}*\n\n🛍️ المنتج: *{offer}*\n📦 الكمية: *{qty}*\n💎 الإجمالي: *{total} {cur}*\n📍 الحالة: *{status}*",
    },
    "rating_prompt": {
        "fr": "⭐ *Votre expérience compte*\n\nComment évaluez-vous cette commande ?",
        "en": "⭐ *Your experience matters*\n\nHow would you rate this order?",
        "ar": "⭐ *تجربتك تهمنا*\n\nكيف تقيّم هذا الطلب؟",
    },
    "rating_thanks": {
        "fr": "💜 Merci ! Votre note de {score}/5 nous aide à améliorer la boutique.",
        "en": "💜 Thank you! Your {score}/5 rating helps us improve the store.",
        "ar": "💜 شكرًا! تقييمك {score}/5 يساعدنا على تحسين المتجر.",
    },
    "payment_scanner": {
        "fr": "💳 *DÉTECTION BINANCE PAY*\n\n`{frame}`\n\n🔎 Signal de paiement en cours d’analyse\n✨ Scanner sécurisé actif\n🧾 Commande *#{oid}*",
        "en": "💳 *BINANCE PAY DETECTION*\n\n`{frame}`\n\n🔎 Analyzing the payment signal\n✨ Secure scanner active\n🧾 Order *#{oid}*",
        "ar": "💳 *فحص BINANCE PAY*\n\n`{frame}`\n\n🔎 جارٍ تحليل إشارة الدفع\n✨ الماسح الآمن نشط\n🧾 الطلب *#{oid}*",
    },
    "payment_scanner_success": {
        "fr": "🟩🟩🟩💎🟩🟩🟩\n\n✅ *PAIEMENT DÉTECTÉ*\n📦 Préparation de la commande *#{oid}*…",
        "en": "🟩🟩🟩💎🟩🟩🟩\n\n✅ *PAYMENT DETECTED*\n📦 Preparing order *#{oid}*…",
        "ar": "🟩🟩🟩💎🟩🟩🟩\n\n✅ *تم اكتشاف الدفع*\n📦 جارٍ تجهيز الطلب *#{oid}*…",
    },
    "payment_scanner_timeout": {
        "fr": "🟧🟧🟧⏳🟧🟧🟧\n\n⚠️ *PAIEMENT NON DÉTECTÉ*\nLa vérification manuelle reste disponible pour la commande *#{oid}*.",
        "en": "🟧🟧🟧⏳🟧🟧🟧\n\n⚠️ *PAYMENT NOT DETECTED*\nManual verification remains available for order *#{oid}*.",
        "ar": "🟧🟧🟧⏳🟧🟧🟧\n\n⚠️ *لم يتم اكتشاف الدفع*\nالتحقق اليدوي متاح للطلب *#{oid}*.",
    },
    "auto_check_timeout": {
        "fr": "\u231b V\u00e9rification automatique termin\u00e9e pour la commande #{oid}.\n\nEnvoyez maintenant l'*ID de transaction Binance* pour v\u00e9rifier manuellement votre paiement.",
        "en": "\u231b Automatic verification ended for order #{oid}.\n\nNow send the *Binance transaction ID* to manually verify your payment.",
        "ar": "\u231b \u0627\u0646\u062a\u0647\u0649 \u0627\u0644\u062a\u062d\u0642\u0642 \u0627\u0644\u062a\u0644\u0642\u0627\u0626\u064a \u0644\u0644\u0637\u0644\u0628 #{oid}.\n\n\u0623\u0631\u0633\u0644 \u0627\u0644\u0622\u0646 *\u0631\u0642\u0645 \u0645\u0639\u0627\u0645\u0644\u0629 Binance* \u0644\u0644\u062a\u062d\u0642\u0642 \u0627\u0644\u064a\u062f\u0648\u064a \u0645\u0646 \u0627\u0644\u062f\u0641\u0639.",
    },
    "payment_contact_admin": {
        "fr": "\U0001f4f8 Si la v\u00e9rification \u00e9choue encore, contactez le support et envoyez une capture du paiement pour la commande #{oid}.",
        "en": "\U0001f4f8 If verification still fails, contact support and send a payment screenshot for order #{oid}.",
        "ar": "\U0001f4f8 \u0625\u0630\u0627 \u0641\u0634\u0644 \u0627\u0644\u062a\u062d\u0642\u0642 \u0645\u0631\u0629 \u0623\u062e\u0631\u0649\u060c \u062a\u0648\u0627\u0635\u0644 \u0645\u0639 \u0627\u0644\u062f\u0639\u0645 \u0648\u0623\u0631\u0633\u0644 \u0644\u0642\u0637\u0629 \u0634\u0627\u0634\u0629 \u0644\u0644\u062f\u0641\u0639 \u0644\u0644\u0637\u0644\u0628 #{oid}.",
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
    "affiliate_payment_progress": {
        "fr": "👥 Un filleul a effectué son premier paiement. Progression : {count}/{target}.",
        "en": "👥 A referral completed their first payment. Progress: {count}/{target}.",
        "ar": "👥 أكمل أحد الإحالات أول دفعة. التقدم: {count}/{target}.",
    },
    "payment_manual_review": {
        "fr": "🔎 Le paiement de la commande #{oid} nécessite une vérification manuelle. Votre TXID est conservé et l’administrateur a été prévenu.",
        "en": "🔎 Payment for order #{oid} requires manual review. Your transaction ID was saved and the administrator was notified.",
        "ar": "🔎 يتطلب دفع الطلب #{oid} مراجعة يدوية. تم حفظ رقم المعاملة وإبلاغ المسؤول.",
    },
    "payment_wrong_amount": {
        "fr": "❌ Le montant reçu ne correspond pas à la commande #{oid}.",
        "en": "❌ The received amount does not match order #{oid}.",
        "ar": "❌ المبلغ المستلم لا يطابق الطلب #{oid}.",
    },
    "payment_wrong_currency": {
        "fr": "❌ La devise reçue ne correspond pas à la commande #{oid}.",
        "en": "❌ The received currency does not match order #{oid}.",
        "ar": "❌ العملة المستلمة لا تطابق الطلب #{oid}.",
    },
    "payment_not_found": {
        "fr": "❌ Transaction introuvable pour la commande #{oid}. Vérifiez le TXID puis réessayez.",
        "en": "❌ Transaction not found for order #{oid}. Check the ID and try again.",
        "ar": "❌ لم يتم العثور على معاملة للطلب #{oid}. تحقق من الرقم وحاول مجددًا.",
    },
    "payment_txid_used": {
        "fr": "❌ Ce TXID a déjà été utilisé pour une autre commande.",
        "en": "❌ This transaction ID has already been used for another order.",
        "ar": "❌ تم استخدام رقم المعاملة هذا لطلب آخر.",
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
    "payment_wrong_memo": {
        "fr": "❌ Le Notes / Mémo ne correspond pas à votre Telegram ID pour la commande #{oid}.",
        "en": "❌ The Notes / Memo does not match your Telegram ID for order #{oid}.",
        "ar": "❌ الملاحظات لا تطابق معرف تيليغرام للطلب #{oid}.",
    },
    "orders_choose_service": {
        "fr": "📋 *Mes commandes*\n\nSélectionnez un service pour consulter vos commandes :",
        "en": "📋 *My Orders*\n\nSelect a service to view your orders:",
        "ar": "📋 *طلباتي*\n\nاختر خدمة لعرض طلباتك:",
    },
    "orders_all": {
        "fr": "📊 Toutes les commandes ({count})",
        "en": "📊 All Orders ({count})",
        "ar": "📊 جميع الطلبات ({count})",
    },
    "orders_all_title": {
        "fr": "Toutes les commandes",
        "en": "All Orders",
        "ar": "جميع الطلبات",
    },
    "orders_file_caption": {
        "fr": "📄 {service} — {count} commande(s)",
        "en": "📄 {service} — {count} order(s)",
        "ar": "📄 {service} — {count} طلب",
    },
    "orders_group_unavailable": {
        "fr": "Cette catégorie n'est plus disponible. Actualisez vos commandes.",
        "en": "This category is no longer available. Refresh your orders.",
        "ar": "هذه الفئة لم تعد متاحة. حدّث قائمة الطلبات.",
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
