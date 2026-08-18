"""
Internationalisation FR / EN / AR.
Usage : t(lang, "key", **kwargs)
"""
import contextlib
import re

CUSTOM_EMOJI_TOKEN_RE = re.compile(r"\[\[TGEMOJI:[0-9A-Za-z_-]+:[0-9a-fA-F]+\]\]")


def without_custom_emoji_tokens(value):
    """Return button/plain text without internal Premium emoji markers."""
    return CUSTOM_EMOJI_TOKEN_RE.sub("", str(value or "")).strip()

TRANSLATIONS = {
    "admin_text_editor_title": {
        "fr": "✏️ *Tous les textes du bot*\n\nChoisissez un texte à modifier. Utilisez les flèches pour parcourir la liste complète.",
        "en": "✏️ *All bot texts*\n\nChoose a text to edit. Use the arrows to browse the complete list.",
        "ar": "✏️ *جميع نصوص البوت*\n\nاختر نصاً لتعديله واستخدم الأسهم لتصفح القائمة.",
    },
    "admin_choose_text_language": {
        "fr": "🌐 Choisissez la langue à modifier pour `{text_key}` :",
        "en": "🌐 Choose the language to edit for `{text_key}`:",
        "ar": "🌐 اختر لغة النص `{text_key}`:",
    },
    "admin_send_new_text": {
        "fr": "✏️ Envoyez le nouveau texte pour `{text_key}` (`{selected_lang}`).\n\nTexte actuel :\n{current}",
        "en": "✏️ Send the new text for `{text_key}` (`{selected_lang}`).\n\nCurrent text:\n{current}",
        "ar": "✏️ أرسل النص الجديد للمفتاح `{text_key}` (`{selected_lang}`).\n\nالنص الحالي:\n{current}",
    },
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
    "channel_join_required": {
        "fr": "🔒 *Accès réservé aux membres*\n\nRejoignez notre canal officiel pour accéder aux offres BlackMarket.\n\n👇 Rejoignez le canal, puis appuyez sur *Vérifier*.",
        "en": "🔒 *MEMBERS-ONLY ACCESS*\n\nJoin our official channel to unlock BlackMarket offers.\n\n👇 Join the channel, then tap *Verify joining*.",
        "ar": "🔒 *وصول خاص بالأعضاء*\n\nانضم إلى قناتنا الرسمية للوصول إلى عروض BlackMarket.\n\n👇 انضم إلى القناة، ثم اضغط على *التحقق*.",
    },
    "btn_join_channel": {"fr": "📢 Join our channel", "en": "📢 Join our channel", "ar": "📢 Join our channel"},
    "btn_join_group": {"fr": "👥 Rejoindre le groupe", "en": "👥 Join our group", "ar": "👥 Join our group"},
    "btn_verify_join": {"fr": "✅ Verify joining", "en": "✅ Verify joining", "ar": "✅ Verify joining"},
    "channel_join_not_verified": {
        "fr": "❌ *Adhésion non détectée*\n\nRejoignez le canal officiel, puis appuyez à nouveau sur *Vérifier*.",
        "en": "❌ *MEMBERSHIP NOT DETECTED*\n\nJoin the official channel, then tap *Verify joining* again.",
        "ar": "❌ *لم يتم اكتشاف العضوية*\n\nانضم إلى القناة الرسمية، ثم اضغط على *التحقق* مرة أخرى.",
    },
    "channel_member_welcome": {
        "fr": "🚀 *WELCOME TO {shop}*\n\nYou are officially inside our premium digital marketplace — verified products, competitive prices and fast delivery are now one tap away.\n\n🎁 *TURN YOUR NETWORK INTO CREDIT*\nShare your personal referral link and earn *2 USDT for every 10 qualified referrals*. A referral qualifies only after they buy from the bot for at least *1 USDT*. Your reward is added automatically to your wallet and can be used to buy any catalog product.\n\n🔗 *Your referral link*\n`{link}`\n\n🏆 *UNLOCK BIGGER DISCOUNTS AS YOU SHOP*\n🥉 *Bronze* — spend 25 USDT → *3% OFF*\n🥈 *Silver* — spend 70 USDT → *6% OFF*\n💎 *Platinum* — spend 200 USDT → *9% OFF*\n👑 *Diamond* — spend 500 USDT → *12% OFF*\n\nEach unlocked discount applies to every product for *3 days*.\n\n🔥 Start exploring today — every purchase brings you closer to a bigger reward.",
        "en": "🚀 *WELCOME TO {shop}*\n\nYou are officially inside our premium digital marketplace — verified products, competitive prices and fast delivery are now one tap away.\n\n🎁 *TURN YOUR NETWORK INTO CREDIT*\nShare your personal referral link and earn *2 USDT for every 10 qualified referrals*. A referral qualifies only after they buy from the bot for at least *1 USDT*. Your reward is added automatically to your wallet and can be used to buy any catalog product.\n\n🔗 *Your referral link*\n`{link}`\n\n🏆 *UNLOCK BIGGER DISCOUNTS AS YOU SHOP*\n🥉 *Bronze* — spend 25 USDT → *3% OFF*\n🥈 *Silver* — spend 70 USDT → *6% OFF*\n💎 *Platinum* — spend 200 USDT → *9% OFF*\n👑 *Diamond* — spend 500 USDT → *12% OFF*\n\nEach unlocked discount applies to every product for *3 days*.\n\n🔥 Start exploring today — every purchase brings you closer to a bigger reward.",
        "ar": "🚀 *WELCOME TO {shop}*\n\nYou are officially inside our premium digital marketplace — verified products, competitive prices and fast delivery are now one tap away.\n\n🎁 *TURN YOUR NETWORK INTO CREDIT*\nShare your personal referral link and earn *2 USDT for every 10 qualified referrals*. A referral qualifies only after they buy from the bot for at least *1 USDT*. Your reward is added automatically to your wallet and can be used to buy any catalog product.\n\n🔗 *Your referral link*\n`{link}`\n\n🏆 *UNLOCK BIGGER DISCOUNTS AS YOU SHOP*\n🥉 *Bronze* — spend 25 USDT → *3% OFF*\n🥈 *Silver* — spend 70 USDT → *6% OFF*\n💎 *Platinum* — spend 200 USDT → *9% OFF*\n👑 *Diamond* — spend 500 USDT → *12% OFF*\n\nEach unlocked discount applies to every product for *3 days*.\n\n🔥 Start exploring today — every purchase brings you closer to a bigger reward.",
    },    # ---------------- Menu principal ----------------
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
        "fr": "✍️ *Envoyez le montant souhaité — minimum 1 USDT*\nLe même montant sera ajouté à votre portefeuille.\n\n🟡 *Binance Pay*\nID : `{binance_id}`\n\n🟠 *Bybit Pay*\nUID : `{bybit_uid}`\n\nAprès le transfert, choisissez ci-dessous le fournisseur utilisé et envoyez le TXID affiché sur votre reçu.",
        "en": "✍️ *Send any amount — minimum 1 USDT*\nThe same amount will be added to your wallet.\n\n🟡 *Binance Pay*\nID: `{binance_id}`\n\n🟠 *Bybit Pay*\nUID: `{bybit_uid}`\n\nAfter transferring, choose the provider used below and send the TXID shown on your receipt.",
        "ar": "✍️ *أرسل أي مبلغ — الحد الأدنى 1 USDT*\nسيتم إضافة نفس المبلغ إلى محفظتك.\n\n🟡 *Binance Pay*\nID: `{binance_id}`\n\n🟠 *Bybit Pay*\nUID: `{bybit_uid}`\n\nبعد التحويل، اختر مزود الدفع المستخدم وأرسل TXID الظاهر في الإيصال.",
    },
    "topup_verify_txid": {"fr": "🟡 Vérifier Binance TXID", "en": "🟡 Verify Binance TXID", "ar": "🟡 Verify Binance TXID"},
    "topup_verify_bybit": {"fr": "🟠 Vérifier Bybit TXID", "en": "🟠 Verify Bybit TXID", "ar": "🟠 Verify Bybit TXID"},
    "topup_bsc": {
        "fr": "🟨 Recharger via USDT BSC",
        "en": "🟨 Top up via USDT BSC",
        "ar": "🟨 Top up via USDT BSC",
    },
    "topup_polygon": {
        "fr": "🟪 Recharger via USDT Polygon",
        "en": "🟪 Top up via USDT Polygon",
        "ar": "🟪 Top up via USDT Polygon",
    },
    "topup_onchain_amount": {
        "fr": "💰 Entrez le montant à ajouter à votre portefeuille via USDT {network} (minimum 1 USDT) :",
        "en": "💰 Enter the amount to add to your wallet via USDT {network} (minimum 1 USDT):",
        "ar": "💰 Enter the amount to add to your wallet via USDT {network} (minimum 1 USDT):",
    },
    "topup_onchain_instructions": {
        "fr": "💳 *RECHARGEMENT USDT — {network}*\n\nEnvoyez exactement *{amount} USDT* à :\n`{address}`\n\n⚠️ Utilisez uniquement le réseau *{network}*.\n{contract_warning}\n\nAprès le transfert, envoyez ici le hash/TXID. Le solde sera crédité après vérification administrative.",
        "en": "💳 *USDT TOP UP — {network}*\n\nSend exactly *{amount} USDT* to:\n`{address}`\n\n⚠️ Use only the *{network}* network.\n{contract_warning}\n\nAfter transferring, send the hash/transaction ID here. Your wallet is credited after administrator verification.",
        "ar": "💳 *USDT TOP UP — {network}*\n\nSend exactly *{amount} USDT* to:\n`{address}`\n\n⚠️ Use only the *{network}* network.\n{contract_warning}\n\nAfter transferring, send the hash/transaction ID here. Your wallet is credited after administrator verification.",
    },
    "topup_onchain_submitted": {
        "fr": "🔎 *Rechargement soumis*\n\nMontant : *{amount} USDT*\nRéseau : *{network}*\nVotre demande attend la vérification administrative. Le solde n’est pas encore crédité.",
        "en": "🔎 *Top up submitted*\n\nAmount: *{amount} USDT*\nNetwork: *{network}*\nYour request is awaiting administrator verification. The balance has not been credited yet.",
        "ar": "🔎 *Top up submitted*\n\nAmount: *{amount} USDT*\nNetwork: *{network}*\nYour request is awaiting administrator verification. The balance has not been credited yet.",
    },
    "topup_onchain_approved": {
        "fr": "✅ *Rechargement confirmé*\n\nMontant ajouté : *{amount} USDT*\nNouveau solde : *{balance} USDT*",
        "en": "✅ *Top up confirmed*\n\nAmount added: *{amount} USDT*\nNew balance: *{balance} USDT*",
        "ar": "✅ *Top up confirmed*\n\nAmount added: *{amount} USDT*\nNew balance: *{balance} USDT*",
    },
    "topup_onchain_rejected": {
        "fr": "❌ Votre rechargement USDT n’a pas été validé. Contactez le support avec votre preuve de paiement.",
        "en": "❌ Your USDT top up was not approved. Contact support with your payment proof.",
        "ar": "❌ Your USDT top up was not approved. Contact support with your payment proof.",
    },
    "topup_home_button": {"fr": "🏠 Home", "en": "🏠 Home", "ar": "🏠 Home"},
    "topup_ask_txid": {
        "fr": "🔎 Envoyez maintenant le *TXID Binance*. Il sera vérifié avant le crédit.",
        "en": "🔎 Send the *Binance TXID* now. It will be verified before crediting.",
        "ar": "🔎 Send the *Binance TXID* now. It will be verified before crediting.",
    },
    "topup_ask_bybit_txid": {
        "fr": "🔎 Envoyez maintenant le *TXID Bybit*. Il sera vérifié avant le crédit.",
        "en": "🔎 Send the *Bybit TXID* now. It will be verified before crediting.",
        "ar": "🔎 Send the *Bybit TXID* now. It will be verified before crediting.",
    },
    "topup_success": {
        "fr": "✅ *Top up confirmed*\n\nAmount added: *{amount} USDT*\nNew balance: *{balance} USDT*",
        "en": "✅ *Top up confirmed*\n\nAmount added: *{amount} USDT*\nNew balance: *{balance} USDT*",
        "ar": "✅ *Top up confirmed*\n\nAmount added: *{amount} USDT*\nNew balance: *{balance} USDT*",
    },
    "topup_already_confirmed": {
        "fr": "✅ *Paiement déjà confirmé*\n\nCette transaction a déjà été vérifiée et créditée. Votre solde n'a pas été crédité une deuxième fois.",
        "en": "✅ *Payment already confirmed*\n\nThis transaction was already verified and credited. Your balance has not been credited again.",
        "ar": "✅ *تم تأكيد الدفع مسبقاً*\n\nتم التحقق من هذه المعاملة وإضافتها إلى الرصيد مسبقاً. لم تتم إضافة الرصيد مرة أخرى.",
    },
    "topup_failed": {
        "fr": "⚠️ *Top up not confirmed*\n\nAutomatic verification is temporarily unavailable. Your balance has not been changed. Try again or use the same TXID later.",
        "en": "⚠️ *Top up not confirmed*\n\nAutomatic verification is temporarily unavailable. Your balance has not been changed. Try again or use the same TXID later.",
        "ar": "⚠️ *Top up not confirmed*\n\nAutomatic verification is temporarily unavailable. Your balance has not been changed. Try again or use the same TXID later.",
    },
    "wallet_payment_processing": {
        "fr": "💳 *Paiement par portefeuille confirmé*\n\nPréparation de votre livraison…",
        "en": "💳 *Wallet payment confirmed*\n\nPreparing your delivery…",
        "ar": "💳 *تم الدفع بالمحفظة*\n\nجارٍ تجهيز التسليم…",
    },
    "support_admin_contact": {
        "fr": "🛎️ <b>Support BlackMarket</b>\n\nPour toute question ou assistance, contactez directement notre administrateur :\n\n👤 {admin}\n\nMerci de préciser votre numéro de commande si votre demande concerne un achat.",
        "en": "🛎️ <b>BlackMarket Support</b>\n\nFor questions or assistance, contact our administrator directly:\n\n👤 {admin}\n\nPlease include your order number when your request concerns a purchase.",
        "ar": "🛎️ <b>دعم BlackMarket</b>\n\nلأي سؤال أو مساعدة، تواصل مباشرة مع المسؤول:\n\n👤 {admin}\n\nيرجى إرسال رقم الطلب إذا كان طلبك متعلقًا بعملية شراء.",
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
        "fr": "🎊 *PROGRAMME D'AFFILIATION*\n\n💰 Gains : *{earned} USDT*\n💳 Portefeuille : *{balance} USDT*\n👥 Filleuls valides : *{referrals}*\n🎯 Progression : *{progress}/10*\n\n🛒 Chaque filleul doit acheter pour au moins *1 USDT* via le bot.\n💵 Invitez *10 filleuls qualifiés* et gagnez *2 USDT*.\n\n🔗 *Votre lien*\n`{link}`\n\n⚠️ Auto-parrainage et faux comptes refusés.",
        "en": "🎊 *AFFILIATE & REWARDS PROGRAM*\n\n📊 *Your affiliate progress*\n💰 Total earned: *{earned} USDT*\n💳 Wallet balance: *{balance} USDT*\n👥 Qualified referrals: *{referrals}*\n🎯 Next reward: *{progress}/10 referrals*\n\n🎁 *How affiliate rewards work*\nShare your personal link. A new, unique user qualifies only after they buy from the bot for at least *1 USDT*. Invite *10 qualified referrals* and *2 USDT* is automatically added to your wallet. You can use this balance to pay for products in the catalog.\n\n🏆 *Purchase discount levels*\n🥉 Bronze — spend *25 USDT*: *3% off*\n🥈 Silver — spend *70 USDT*: *6% off*\n💎 Platinum — spend *200 USDT*: *9% off*\n👑 Diamond — spend *500 USDT*: *12% off*\n\nDiscount levels are based on your cumulative confirmed purchases. Once activated, your discount applies to every product for *3 days*.\n\n🔗 *Your referral link*\n`{link}`\n\n⚠️ Self-referrals, duplicate users and fake accounts are not accepted.",
        "ar": "🎊 *برنامج الإحالة*\n\n💰 الأرباح: *{earned} USDT*\n💳 المحفظة: *{balance} USDT*\n👥 الإحالات الصالحة: *{referrals}*\n🎯 التقدم: *{progress}/10*\n\n🛒 تُحتسب الإحالة بعد شراء ما لا يقل عن *1 USDT* من البوت.\n💵 ادعُ *10 إحالات مؤهلة* واربح *2 USDT*.\n\n🔗 `{link}`\n\n⚠️ الإحالة الذاتية والحسابات الوهمية مرفوضة.",
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
    "channel_affiliate_reward": {
        "fr": "🎉 *AFFILIATE REWARD UNLOCKED!*\n\n🏆 A community member reached *{count} valid referrals*\n💰 *{reward} USDT* was added instantly to their wallet\n\n🔥 Share your referral link, grow the community and unlock your own rewards!",
        "en": "🎉 *AFFILIATE REWARD UNLOCKED!*\n\n🏆 A community member reached *{count} valid referrals*\n💰 *{reward} USDT* was added instantly to their wallet\n\n🔥 Share your referral link, grow the community and unlock your own rewards!",
        "ar": "🎉 *AFFILIATE REWARD UNLOCKED!*\n\n🏆 A community member reached *{count} valid referrals*\n💰 *{reward} USDT* was added instantly to their wallet\n\n🔥 Share your referral link, grow the community and unlock your own rewards!",
    },
    "channel_stock_announcement": {
        "fr": "🚨 *NEW STOCK JUST DROPPED*\n\n{emoji} *{service} — {offer}*\n💎 Price: *{price} {cur}*\n📦 Available now: *{stock} account(s)*\n✨ Freshly restocked: *{added} new account(s)*\n\n⚡ Secure your account before the stock runs out!",
        "en": "🚨 *NEW STOCK JUST DROPPED*\n\n{emoji} *{service} — {offer}*\n💎 Price: *{price} {cur}*\n📦 Available now: *{stock} account(s)*\n✨ Freshly restocked: *{added} new account(s)*\n\n⚡ Secure your account before the stock runs out!",
        "ar": "🚨 *NEW STOCK JUST DROPPED*\n\n{emoji} *{service} — {offer}*\n💎 Price: *{price} {cur}*\n📦 Available now: *{stock} account(s)*\n✨ Freshly restocked: *{added} new account(s)*\n\n⚡ Secure your account before the stock runs out!",
    },
    "flash_sale_announcement": {
        "fr": "⚡ *VENTE FLASH — DURÉE LIMITÉE*\n\n{emoji} *{offer}*\nAncien prix : *{old_price} {cur}*\n🔥 Prix flash : *{price} {cur}*\n\n⌛ Fin dans *{remaining}*\n\nAppuyez ci-dessous pour acheter immédiatement. Livraison automatique.",
        "en": "⚡ *FLASH SALE — LIMITED TIME*\n\n{emoji} *{offer}*\nOld price: *{old_price} {cur}*\n🔥 Flash price: *{price} {cur}*\n\n⌛ Ends in *{remaining}*\n\nTap below to buy instantly. Delivery is automatic.",
        "ar": "⚡ *تخفيض سريع — لفترة محدودة*\n\n{emoji} *{offer}*\nالسعر السابق: *{old_price} {cur}*\n🔥 سعر العرض: *{price} {cur}*\n\n⌛ ينتهي خلال *{remaining}*\n\nاضغط أدناه للشراء فوراً. التسليم تلقائي.",
    },
    "api_flash_sale_announcement": {
        "fr": "🔥 *FLASH SALE — BAISSE DE PRIX API*\n\n{emoji} *{service} — {offer}*\nAncien prix : *{old_price} {cur}*\n⚡ Nouveau prix : *{price} {cur}*\n🎯 Réduction : *{discount}%*\n\nCommandez avant la prochaine variation de prix !",
        "en": "🔥 *FLASH SALE — API PRICE DROP*\n\n{emoji} *{service} — {offer}*\nOld price: *{old_price} {cur}*\n⚡ New price: *{price} {cur}*\n🎯 Discount: *{discount}%*\n\nOrder before the next price change!",
        "ar": "🔥 *FLASH SALE — API PRICE DROP*\n\n{emoji} *{service} — {offer}*\nOld price: *{old_price} {cur}*\n⚡ New price: *{price} {cur}*\n🎯 Discount: *{discount}%*\n\nOrder before the next price change!",
    },
    "offer_stock_announcement": {
        "fr": "📣 *OFFRE DISPONIBLE*\n\n{emoji} *{service} — {offer}*\n💎 Prix actuel : *{price} {cur}*\n📦 Stock disponible : *{stock} compte(s)*\n\n⚡ Commandez directement avant la rupture de stock !",
        "en": "📣 *AVAILABLE OFFER*\n\n{emoji} *{service} — {offer}*\n💎 Current price: *{price} {cur}*\n📦 Available stock: *{stock} account(s)*\n\n⚡ Order directly before it sells out!",
        "ar": "📣 *عرض متاح*\n\n{emoji} *{service} — {offer}*\n💎 السعر الحالي: *{price} {cur}*\n📦 المخزون المتاح: *{stock} حساب*\n\n⚡ اطلب مباشرة قبل نفاد المخزون!",
    },
    "channel_purchase_success": {
        "fr": "🎉 *ANOTHER SUCCESSFUL PURCHASE*\n\n✅ A customer just secured:\n🛍 *{service} — {offer}*\n📦 Quantity: *{qty}*\n💎 Order value: *{total} {cur}*\n🔥 Remaining stock: *{stock} account(s)*\n\nTrusted delivery. Real products. Join the next drop before it sells out!",
        "en": "🎉 *ANOTHER SUCCESSFUL PURCHASE*\n\n✅ A customer just secured:\n🛍 *{service} — {offer}*\n📦 Quantity: *{qty}*\n💎 Order value: *{total} {cur}*\n🔥 Remaining stock: *{stock} account(s)*\n\nTrusted delivery. Real products. Join the next drop before it sells out!",
        "ar": "🎉 *ANOTHER SUCCESSFUL PURCHASE*\n\n✅ A customer just secured:\n🛍 *{service} — {offer}*\n📦 Quantity: *{qty}*\n💎 Order value: *{total} {cur}*\n🔥 Remaining stock: *{stock} account(s)*\n\nTrusted delivery. Real products. Join the next drop before it sells out!",
    },
    "btn_channel_buy_now": {"fr": "🛒 Buy now", "en": "🛒 Buy now", "ar": "🛒 Buy now"},
    "catalog_flat_title": {
        "fr": "*CATALOGUE {shop}*\n\nChoisissez une offre :",
        "en": "*{shop} CATALOG*\n\nChoose an offer:",
        "ar": "*{shop} CATALOG*\n\nChoose an offer:",
    },
    "catalog_title": {
        "fr": "🛍️ *CATALOGUE {shop}*\n\n🟢 Boutique opérationnelle\n⚡ Livraison rapide ou instantanée\n🛡️ Produits vérifiés et support inclus\n\nChoisissez votre univers :",
        "en": "🛍️ *{shop} CATALOG*\n\n🟢 Store operational\n⚡ Fast or instant delivery\n🛡️ Verified products with support\n\nChoose your category:",
        "ar": "🛍️ *كتالوج {shop}*\n\n🟢 المتجر يعمل\n⚡ تسليم سريع أو فوري\n🛡️ منتجات موثوقة مع الدعم\n\nاختر الفئة:",
    },
    "catalog_request_button": {
        "fr": "🔎 Can't find what you need?",
        "en": "🔎 Can't find what you need?",
        "ar": "🔎 Can't find what you need?",
    },
    "catalog_request_prompt": {
        "fr": "✍️ *Tell us what you need*\n\nSend the product or service name and any useful details. Our team will review your request.",
        "en": "✍️ *Tell us what you need*\n\nSend the product or service name and any useful details. Our team will review your request.",
        "ar": "✍️ *Tell us what you need*\n\nSend the product or service name and any useful details. Our team will review your request.",
    },
    "catalog_request_sent": {
        "fr": "✅ *Request sent!*\n\nOur team received your request and will contact you when possible.",
        "en": "✅ *Request sent!*\n\nOur team received your request and will contact you when possible.",
        "ar": "✅ *Request sent!*\n\nOur team received your request and will contact you when possible.",
    },
    "catalog_request_admin": {
        "fr": "🔎 *New catalog request*\n\n👤 Client: {user}\n🆔 Telegram ID: `{user_id}`\n\n📦 *Requested product/service:*\n{request}",
        "en": "🔎 *New catalog request*\n\n👤 Client: {user}\n🆔 Telegram ID: `{user_id}`\n\n📦 *Requested product/service:*\n{request}",
        "ar": "🔎 *New catalog request*\n\n👤 Client: {user}\n🆔 Telegram ID: `{user_id}`\n\n📦 *Requested product/service:*\n{request}",
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
    "preorder_available": {
        "fr": "❌ <b>Rupture de stock</b>\n\nVous pouvez précommander cette offre avec un <b>supplément de 10 %</b>. Livraison sous <b>2 heures maximum</b>.",
        "en": "❌ <b>Out of stock</b>\n\nYou can pre-order this offer with a <b>10% surcharge</b>. Delivery is within <b>2 hours maximum</b>.",
        "ar": "❌ <b>نفد المخزون</b>\n\nيمكنك طلب هذا العرض مسبقاً مع <b>زيادة 10%</b>. التسليم خلال <b>ساعتين كحد أقصى</b>.",
    },
    "catalog_preorder_button": {
        "fr": "⏳ Précommande",
        "en": "⏳ Pre-order",
        "ar": "⏳ طلب مسبق",
    },
    "preorder_catalog_title": {
        "fr": "⏳ *PRÉCOMMANDE*\n\nChoisissez un service en rupture de stock. Les offres sont affichées avec le supplément de *10 %* inclus.\n\n🚚 *Livraison sous 2 heures maximum.*",
        "en": "⏳ *PRE-ORDER*\n\nChoose an out-of-stock service. Offer prices include the *10% surcharge*.\n\n🚚 *Delivery within 2 hours maximum.*",
        "ar": "⏳ *الطلب المسبق*\n\nاختر خدمة نفد مخزونها. تشمل الأسعار المعروضة زيادة *10%*.\n\n🚚 *التسليم خلال ساعتين كحد أقصى.*",
    },
    "preorder_service_title": {
        "fr": "{emoji} *Précommander {name}*\n\nChoisissez une offre en rupture de stock. Le prix affiché inclut déjà le supplément de *10 %*.\n\n🚚 *Livraison sous 2 heures maximum.*",
        "en": "{emoji} *Pre-order {name}*\n\nChoose an out-of-stock offer. The displayed price already includes the *10% surcharge*.\n\n🚚 *Delivery within 2 hours maximum.*",
        "ar": "{emoji} *طلب {name} مسبقاً*\n\nاختر عرضاً نفد مخزونه. السعر المعروض يشمل زيادة *10%*.\n\n🚚 *التسليم خلال ساعتين كحد أقصى.*",
    },
    # ---------------- Détail offre ----------------
    "offer_detail": {
        "fr": "{emoji} *{offer}*\n\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\n\n\U0001f4ab *DETAILS DE L'OFFRE*\n\n\U0001f6e1 *Warranty*\n{note}\n\n\U000023f3 *Duration*\n{duration}\n\n\U0001f4e7 *Mail*\n{mail}\n\n\U0001f510 *Access*\n{access}\n\n\U0001f69a *Delivery*\n{delivery}\n\n\U0001f48e *Price*\n*{price} {cur}*\n\n\U0001f4e6 *Stock disponible*\n*{stock} compte(s)*\n\n{description}\n\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\n\U0001f680 _Choisissez Acheter maintenant pour selectionner la quantite._",
        "en": "{emoji} *{offer}*\n\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\n\n\U0001f4ab *OFFER DETAILS*\n\n\U0001f6e1 *Warranty*\n{note}\n\n\U000023f3 *Duration*\n{duration}\n\n\U0001f4e7 *Mail*\n{mail}\n\n\U0001f510 *Access*\n{access}\n\n\U0001f69a *Delivery*\n{delivery}\n\n\U0001f48e *Price*\n*{price} {cur}*\n\n\U0001f4e6 *Available stock*\n*{stock} account(s)*\n\n{description}\n\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\n\U0001f680 _Tap Buy now to select quantity._",
        "ar": "{emoji} *{offer}*\n\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\n\n\U0001f4ab *OFFER DETAILS*\n\n\U0001f6e1 *Warranty*\n{note}\n\n\U000023f3 *Duration*\n{duration}\n\n\U0001f4e7 *Mail*\n{mail}\n\n\U0001f510 *Access*\n{access}\n\n\U0001f69a *Delivery*\n{delivery}\n\n\U0001f48e *Price*\n*{price} {cur}*\n\n\U0001f4e6 *Stock*\n*{stock} account(s)*\n\n{description}\n\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\U00002728\n\U0001f680 _Tap Buy now to select quantity._",
    },
    "btn_buy": {"fr": "🛒 Acheter maintenant", "en": "🛒 Buy now", "ar": "🛒 اشترِ الآن"},
    "btn_preorder": {"en": "⏳ Pre-order (+10%)"},
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
    "btn_cancel_order": {"fr": "❌ Annuler la commande", "en": "❌ Cancel order", "ar": "❌ إلغاء الطلب"},
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
        "fr": "✏️ *Entrez la quantité à acheter (1-{stock}) :*\n\nProduit : *{offer}*\nStock disponible : *{stock}*\nPrix unitaire : *{price} {cur}*",
        "en": "✏️ *Enter quantity to buy (1-{stock}):*\n\nProduct: *{offer}*\nAvailable stock: *{stock}*\nUnit price: *{price} {cur}*",
        "ar": "✏️ *أدخل الكمية المطلوبة (1-{stock}):*\n\nالمنتج: *{offer}*\nالمخزون المتاح: *{stock}*\nسعر الوحدة: *{price} {cur}*",
    },
    "choose_preorder_quantity": {
        "fr": "⏳ *Précommande (+10 %)*\n\nProduit : *{offer}*\nPrix unitaire avec supplément : *{price} {cur}*\n🚚 Livraison sous *2 heures maximum*.\n\nChoisissez une quantité (1-{max_qty}) :",
        "en": "⏳ *Pre-order (+10%)*\n\nProduct: *{offer}*\nUnit price including surcharge: *{price} {cur}*\n🚚 Delivery within *2 hours maximum*.\n\nChoose a quantity (1-{max_qty}):",
        "ar": "⏳ *طلب مسبق (+10%)*\n\nالمنتج: *{offer}*\nسعر الوحدة بعد الزيادة: *{price} {cur}*\n🚚 التسليم خلال *ساعتين كحد أقصى*.\n\nاختر الكمية (1-{max_qty}):",
    },
    "preorder_quantity_invalid": {
        "en": "⚠️ Invalid quantity. Send a whole number between *1* and *{max_qty}*.",
    },
    "affiliate_referral_success": {
        "fr": "🎉 *Nouveau filleul valide !*\n\nProgression : *{progress}/10*\nEncore *{remaining}* filleul(s) valide(s) pour gagner *2 USDT*.",
        "en": "🎉 *New qualified referral!*\n\nProgress: *{progress}/10*\nOnly *{remaining}* more qualified referral(s) to earn *2 USDT*.",
        "ar": "🎉 *إحالة صالحة جديدة!*\n\nالتقدم: *{progress}/10*\nمتبقي *{remaining}* إحالة صالحة لربح *2 USDT*.",
    },
    "affiliate_ten_success": {
        "fr": "✅ *Objectif atteint !*\n\nVous avez complété *10 filleuls valides*. *2 USDT* ont été ajoutés automatiquement à votre portefeuille.\n\nNouveau solde : *{balance} USDT*.",
        "en": "✅ *Goal completed!*\n\nYou completed *10 valid referrals*. *2 USDT* was automatically added to your wallet.\n\nNew balance: *{balance} USDT*.",
        "ar": "✅ *تم تحقيق الهدف!*\n\nأكملت *10 إحالات صالحة*. تمت إضافة *2 USDT* تلقائيًا إلى محفظتك.\n\nالرصيد الجديد: *{balance} USDT*.",
    },
    "quantity_invalid": {
        "fr": "⚠️ Quantité invalide. Envoyez un nombre entier entre *1* et *{stock}*.",
        "en": "⚠️ Invalid quantity. Send a whole number between *1* and *{stock}*.",
        "ar": "⚠️ كمية غير صالحة. أرسل رقماً صحيحاً بين *1* و *{stock}*.",
    },
    "confirm_purchase": {
        "fr": "🧾 *Résumé de votre commande*\n\n{emoji} Service : *{service}*\n📋 Offre : *{offer}*\n💵 Prix unitaire : *{price} {cur}*\n📦 Quantité : *{qty}*\n{discount_line}\n💰 Total : *{total} {cur}*\n\nConfirmez-vous cet achat ?",
        "en": "🧾 *Order summary*\n\n{emoji} Service: *{service}*\n📋 Offer: *{offer}*\n💵 Unit price: *{price} {cur}*\n📦 Quantity: *{qty}*\n{discount_line}\n💰 Total: *{total} {cur}*\n\nDo you confirm this purchase?",
        "ar": "🧾 *ملخص الطلب*\n\n{emoji} الخدمة: *{service}*\n📋 العرض: *{offer}*\n💵 السعر: *{price} {cur}*\n📦 الكمية: *{qty}*\n{discount_line}\n💰 الإجمالي: *{total} {cur}*\n\nهل تؤكد هذا الشراء؟",
    },
    "preorder_line": {
        "fr": "⏳ Précommande : *supplément de 10 % inclus*\n🚚 Livraison : *2 heures maximum*\n",
        "en": "⏳ Pre-order: *10% surcharge included*\n🚚 Delivery: *2 hours maximum*\n",
        "ar": "⏳ طلب مسبق: *زيادة 10% مشمولة*\n🚚 التسليم: *خلال ساعتين كحد أقصى*\n",
    },
    "loyalty_discount_line": {
        "fr": "🏆 Niveau {level} : *-{percent}%* (-{amount} {cur})",
        "en": "🏆 {level} level: *-{percent}%* (-{amount} {cur})",
        "ar": "🏆 مستوى {level}: *-{percent}%* (-{amount} {cur})",
    },
    "profile_card": {
        "fr": "👤 <b>MON PROFIL</b>\n\n🪪 <b>Nom :</b> {name}\n🔗 <b>Utilisateur :</b> {username}\n🆔 <b>Telegram ID :</b> <code>{telegram_id}</code>\n\n💳 <b>Portefeuille :</b> {wallet} USDT\n👥 <b>Filleuls valides :</b> {invites}\n🛍️ <b>Total des achats :</b> {total_buy} USDT\n\n🏆 <b>Niveau :</b> {level}\n🎁 <b>Remise active :</b> {discount}%\n⏳ <b>Expiration :</b> {expires}",
        "en": "👤 <b>MY PROFILE</b>\n\n🪪 <b>Name:</b> {name}\n🔗 <b>Username:</b> {username}\n🆔 <b>Telegram ID:</b> <code>{telegram_id}</code>\n\n💳 <b>Wallet:</b> {wallet} USDT\n👥 <b>Valid referrals:</b> {invites}\n🛍️ <b>Total purchases:</b> {total_buy} USDT\n\n🏆 <b>Level:</b> {level}\n🎁 <b>Active discount:</b> {discount}%\n⏳ <b>Expires:</b> {expires}",
        "ar": "👤 <b>ملفي</b>\n\n🪪 <b>الاسم:</b> {name}\n🆔 <b>معرف تيليغرام:</b> <code>{telegram_id}</code>\n💳 <b>المحفظة:</b> {wallet} USDT\n👥 <b>الإحالات الصالحة:</b> {invites}\n🛍️ <b>إجمالي المشتريات:</b> {total_buy} USDT\n🏆 <b>المستوى:</b> {level}\n🎁 <b>الخصم:</b> {discount}%\n⏳ <b>الانتهاء:</b> {expires}",
    },
    "loyalty_activated": {
        "fr": "🏆 *Nouveau niveau {level} !*\n\nVous bénéficiez maintenant de *-{discount}%* sur tous les produits pendant 3 jours.",
        "en": "🏆 *New {level} level!*\n\nYou now receive *-{discount}%* on every product for 3 days.",
        "ar": "🏆 *مستوى جديد {level}!*\n\nتحصل الآن على خصم *{discount}%* على جميع المنتجات لمدة 3 أيام.",
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
        "fr": "🔥💳 *Binance Pay*\n--------------------\n\n🛍️ Produit : *{offer}*\n💫 Quantité : *{qty}*\n\n🚨 *ENVOYEZ EXACTEMENT : {total} {cur}*\n🧭 Binance ID : `{binance_id}`\n\nAprès le paiement, appuyez sur *Vérifier avec TXID* et envoyez l'identifiant de transaction ou l'Order ID affiché sur votre reçu Binance.\n\n🎯 Commande : *#{oid}*",
        "en": "🔥💳 *Binance Pay*\n--------------------\n\n🛍️ Product: *{offer}*\n💫 Quantity: *{qty}*\n\n🚨 *SEND EXACTLY: {total} {cur}*\n🧭 Binance ID: `{binance_id}`\n\nAfter paying, tap *Verify with TXID* and send the Transaction ID or Order ID shown on your Binance receipt.\n\n🎯 Order: *#{oid}*",
        "ar": "🧾 *تم إنشاء الطلب #{oid}*\n\nالخدمة: *{service}*\nالعرض: *{offer}*\nالكمية: *{qty}*\nالمبلغ الإجمالي: *{total} {cur}*\n\n💳 *الدفع عبر Binance Pay*\n\n1️⃣ أرسل *{total} {cur}* إلى معرّف Binance Pay:\n`{binance_id}`\n\n2️⃣ بعد الدفع، اضغط الزر أدناه وأرسل *رقم معاملة Binance*.",
    },
    "bybit_order_created": {
        "fr": "🟠💳 *Bybit Pay*\n--------------------\n\n🛍️ Produit : *{offer}*\n💫 Quantité : *{qty}*\n\n🚨 *ENVOYEZ EXACTEMENT : {total} {cur}*\n🧭 UID Bybit : `{bybit_uid}`\n\nAprès le paiement, appuyez sur *Vérifier avec TXID* et envoyez le TXID affiché sur votre reçu Bybit.\n\n🎯 Commande : *#{oid}*",
        "en": "🟠💳 *Bybit Pay*\n--------------------\n\n🛍️ Product: *{offer}*\n💫 Quantity: *{qty}*\n\n🚨 *SEND EXACTLY: {total} {cur}*\n🧭 Bybit UID: `{bybit_uid}`\n\nAfter paying, tap *Verify with TXID* and send the TXID shown on your Bybit receipt.\n\n🎯 Order: *#{oid}*",
        "ar": "🟠💳 *Bybit Pay*\n--------------------\n\n🛍️ Product: *{offer}*\n💫 Quantity: *{qty}*\n\n🚨 *SEND EXACTLY: {total} {cur}*\n🧭 Bybit UID: `{bybit_uid}`\n\nAfter paying, tap *Verify with TXID* and send the TXID shown on your Bybit receipt.\n\n🎯 Order: *#{oid}*",
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
    "ask_bybit_txid": {
        "fr": "✍️ Veuillez envoyer le *TXID Bybit* de votre paiement pour la commande #{oid}. Si cela échoue, contactez le support avec une capture du paiement :",
        "en": "✍️ Please send the *Bybit TXID* for order #{oid}. If it fails, contact support with a payment screenshot:",
        "ar": "✍️ Please send the *Bybit TXID* for order #{oid}. If it fails, contact support with a payment screenshot:",
    },
    "btn_verify_txid": {
        "fr": "🧾 Vérifier avec TXID",
        "en": "🧾 Verify with TXID",
        "ar": "🧾 التحقق باستخدام TXID",
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
    "btn_pay_bybit": {
        "fr": "🟠 Payer avec Bybit Pay",
        "en": "🟠 Pay with Bybit Pay",
        "ar": "🟠 الدفع عبر Bybit Pay",
    },
    "btn_pay_bsc": {
        "fr": "🟨 USDT — BSC (BEP20)",
        "en": "🟨 USDT — BSC (BEP20)",
        "ar": "🟨 USDT — BSC (BEP20)",
    },
    "btn_pay_polygon": {
        "fr": "🟪 USDT — Polygon",
        "en": "🟪 USDT — Polygon",
        "ar": "🟪 USDT — Polygon",
    },
    "btn_submit_chain_txid": {
        "fr": "🧾 Envoyer le TXID",
        "en": "🧾 Submit transaction ID",
        "ar": "🧾 Submit transaction ID",
    },
    "btn_reply_manual_order": {
        "fr": "💬 Répondre à l’administrateur",
        "en": "💬 Reply to administrator",
        "ar": "💬 الرد على المسؤول",
    },
    "manual_order_reply_prompt": {
        "fr": "✍️ Envoyez votre réponse pour la commande #{oid}. Elle sera transmise directement à l’administrateur.",
        "en": "✍️ Send your reply for order #{oid}. It will be forwarded directly to the administrator.",
        "ar": "✍️ أرسل ردك للطلب #{oid}. سيتم إرساله مباشرة إلى المسؤول.",
    },
    "manual_order_reply_sent": {
        "fr": "✅ Votre réponse pour la commande #{oid} a été envoyée à l’administrateur. La conversation reste ouverte jusqu’à la livraison.",
        "en": "✅ Your reply for order #{oid} was sent to the administrator. The conversation remains open until delivery.",
        "ar": "✅ تم إرسال ردك للطلب #{oid} إلى المسؤول. تبقى المحادثة مفتوحة حتى التسليم.",
    },
    "manual_order_conversation_closed": {
        "fr": "Cette conversation est fermée car la commande a déjà été livrée ou n’est plus en attente.",
        "en": "This conversation is closed because the order was already delivered or is no longer pending.",
        "ar": "تم إغلاق هذه المحادثة لأن الطلب تم تسليمه أو لم يعد قيد الانتظار.",
    },
    "onchain_order_created": {
        "fr": "💳 *PAIEMENT USDT — {network}*\n\n🛍️ Produit : *{offer}*\n📦 Quantité : *{qty}*\n🚨 Envoyez exactement : *{total} USDT*\n\n📍 Adresse :\n`{address}`\n\n⚠️ Utilisez uniquement le réseau *{network}*.\n{contract_warning}\nUne transaction envoyée sur un autre réseau peut être définitivement perdue.\n\nCommande : *#{oid}*",
        "en": "💳 *USDT PAYMENT — {network}*\n\n🛍️ Product: *{offer}*\n📦 Quantity: *{qty}*\n🚨 Send exactly: *{total} USDT*\n\n📍 Address:\n`{address}`\n\n⚠️ Use only the *{network}* network.\n{contract_warning}\nA transfer sent through another network may be permanently lost.\n\nOrder: *#{oid}*",
        "ar": "💳 *USDT PAYMENT — {network}*\n\n🛍️ Product: *{offer}*\n📦 Quantity: *{qty}*\n🚨 Send exactly: *{total} USDT*\n\n📍 Address:\n`{address}`\n\n⚠️ Use only the *{network}* network.\n{contract_warning}\nA transfer sent through another network may be permanently lost.\n\nOrder: *#{oid}*",
    },
    "ask_onchain_txid": {
        "fr": "✍️ Envoyez maintenant le hash/TXID de votre transaction USDT {network} pour la commande #{oid}.",
        "en": "✍️ Send the hash/transaction ID of your USDT {network} transfer for order #{oid}.",
        "ar": "✍️ Send the hash/transaction ID of your USDT {network} transfer for order #{oid}.",
    },
    "onchain_payment_submitted": {
        "fr": "🔎 *Transaction enregistrée*\n\nCommande #{oid} — USDT {network}\nVotre paiement attend maintenant la vérification de l’administrateur. La livraison commencera uniquement après confirmation.",
        "en": "🔎 *Transaction submitted*\n\nOrder #{oid} — USDT {network}\nYour payment is now awaiting administrator verification. Delivery starts only after confirmation.",
        "ar": "🔎 *Transaction submitted*\n\nOrder #{oid} — USDT {network}\nYour payment is now awaiting administrator verification. Delivery starts only after confirmation.",
    },
    "onchain_payment_rejected": {
        "fr": "❌ *Paiement non accepté*\n\nLe paiement de la commande #{oid} sur {network} n’a pas été validé par l’administrateur. Vérifiez votre transfert puis soumettez un autre TXID, ou contactez le support.",
        "en": "❌ *Payment rejected*\n\nThe {network} payment for order #{oid} was not approved by the administrator. Check your transfer and submit another TXID, or contact support.",
        "ar": "❌ *Payment rejected*\n\nThe {network} payment for order #{oid} was not approved by the administrator. Check your transfer and submit another TXID, or contact support.",
    },
    "onboarding_1": {
        "fr": "✨ *Bienvenue dans l’univers {shop}*\n\nDes services numériques premium, présentés simplement et accessibles en quelques secondes.\n\n`1/3`  Découvrir",
        "en": "✨ *Welcome to the {shop} experience*\n\nPremium digital services, clearly presented and available in seconds.\n\n`1/3`  Discover",
        "ar": "✨ *مرحبًا بك في عالم {shop}*\n\nخدمات رقمية مميزة وواضحة ومتاحة خلال ثوانٍ.\n\n`1/3`  اكتشف",
    },
    "onboarding_2": {
        "fr": "💳 *Paiement simple et sécurisé*\n\n1️⃣ Choisissez votre produit\n2️⃣ Payez le montant exact via Binance Pay\n3️⃣ Envoyez le TXID de votre reçu\n\n`2/3`  Paiement",
        "en": "💳 *Simple and secure payment*\n\n1️⃣ Choose your product\n2️⃣ Pay the exact amount with Binance Pay\n3️⃣ Send the TXID from your receipt\n\n`2/3`  Payment",
        "ar": "💳 *دفع بسيط وآمن*\n\n1️⃣ اختر المنتج\n2️⃣ ادفع المبلغ الدقيق عبر Binance Pay\n3️⃣ أرسل TXID من الإيصال\n\n`2/3`  الدفع",
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
    "payment_contact_admin": {
        "fr": "\U0001f4f8 Si la v\u00e9rification \u00e9choue encore, contactez le support et envoyez une capture du paiement pour la commande #{oid}.",
        "en": "\U0001f4f8 If verification still fails, contact support and send a payment screenshot for order #{oid}.",
        "ar": "\U0001f4f8 \u0625\u0630\u0627 \u0641\u0634\u0644 \u0627\u0644\u062a\u062d\u0642\u0642 \u0645\u0631\u0629 \u0623\u062e\u0631\u0649\u060c \u062a\u0648\u0627\u0635\u0644 \u0645\u0639 \u0627\u0644\u062f\u0639\u0645 \u0648\u0623\u0631\u0633\u0644 \u0644\u0642\u0637\u0629 \u0634\u0627\u0634\u0629 \u0644\u0644\u062f\u0641\u0639 \u0644\u0644\u0637\u0644\u0628 #{oid}.",
    },
    "verifying": {
        "fr": "🔎 Vérification de votre TXID Binance... Merci de patienter.",
        "en": "🔎 Verifying your Binance TXID... Please wait.",
        "ar": "🔎 جارٍ التحقق من TXID على Binance... الرجاء الانتظار.",
    },
    "codex_payment_confirmed_waiting_number": {
        "fr": "✅ *Paiement confirmé — commande #{oid}*\n\nL'administrateur prépare votre numéro Codex. Vous le recevrez ici.",
        "en": "✅ *Payment confirmed — order #{oid}*\n\nThe administrator is preparing your Codex number. You will receive it here.",
        "ar": "✅ *تم تأكيد الدفع — الطلب #{oid}*\n\nيقوم المسؤول بإعداد رقم Codex الخاص بك. ستستلمه هنا.",
    },
    "codex_number_received": {
        "fr": "📱 *Votre numéro Codex*\n\nCommande : *#{oid}*\nNuméro : `{number}`\n\nAprès avoir vérifié le numéro, appuyez sur *J'accepte* pour demander le code OTP.\n\n⚠️ Vous perdrez la commande si vous n'acceptez pas le numéro dans les *5 minutes* suivant sa réception.",
        "en": "📱 *Your Codex number*\n\nOrder: *#{oid}*\nNumber: `{number}`\n\nAfter checking the number, tap *I agree* to request the OTP code.\n\n⚠️ You will lose the order if you do not accept the number within *5 minutes* of receiving it.",
        "ar": "📱 *رقم Codex الخاص بك*\n\nالطلب: *#{oid}*\nالرقم: `{number}`\n\nبعد التحقق من الرقم، اضغط *أوافق* لطلب رمز OTP.\n\n⚠️ ستفقد الطلب إذا لم تقبل الرقم خلال *5 دقائق* من استلامه.",
    },
    "btn_codex_number_agree": {
        "fr": "J'accepte",
        "en": "I agree",
        "ar": "أوافق",
    },
    "codex_number_agreed": {
        "fr": "✅ *Numéro accepté*\n\nL'administrateur a été averti. Votre code OTP sera envoyé ici.",
        "en": "✅ *Number accepted*\n\nThe administrator has been notified. Your OTP code will be sent here.",
        "ar": "✅ *تم قبول الرقم*\n\nتم إشعار المسؤول. سيتم إرسال رمز OTP هنا.",
    },
    "codex_acceptance_expired": {
        "fr": "⌛ *Délai expiré — commande #{oid}*\n\nVous n'avez pas accepté le numéro Codex dans les 5 minutes. Cette commande est maintenant expirée.",
        "en": "⌛ *Time expired — order #{oid}*\n\nYou did not accept the Codex number within 5 minutes. This order has now expired.",
        "ar": "⌛ *انتهت المهلة — الطلب #{oid}*\n\nلم تقبل رقم Codex خلال 5 دقائق. انتهت صلاحية هذا الطلب الآن.",
    },
    "codex_otp_received": {
        "fr": "🔐 *Code OTP reçu — commande #{oid}*\n\nCode : `{code}`\n\n✅ Votre commande est maintenant terminée.",
        "en": "🔐 *OTP code received — order #{oid}*\n\nCode: `{code}`\n\n✅ Your order is now complete.",
        "ar": "🔐 *تم استلام رمز OTP — الطلب #{oid}*\n\nالرمز: `{code}`\n\n✅ اكتمل طلبك الآن.",
    },
    "otp_ask_service": {
        "fr": "Quel est le service ?",
        "en": "What's the service?",
        "ar": "What's the service?",
    },
    "otp_ask_country": {
        "fr": "Service : *{service}*\n\nQuel est le pays ?",
        "en": "Service: *{service}*\n\nWhat's the country?",
        "ar": "Service: *{service}*\n\nWhat's the country?",
    },
    "otp_redirect_admin": {
        "fr": "*Demande OTP envoyée*\n\nCommande : *#{oid}*\nService : *{service}*\nPays : *{country}*\n\nVotre demande a été transmise. Vous recevrez le code ou la réponse directement dans ce bot.",
        "en": "*OTP request sent*\n\nOrder: *#{oid}*\nService: *{service}*\nCountry: *{country}*\n\nYour request was sent. You will receive the code or reply directly in this bot.",
        "ar": "*تم إرسال طلب OTP*\n\nالطلب: *#{oid}*\nالخدمة: *{service}*\nالبلد: *{country}*\n\nتم إرسال طلبك. ستتلقى الرمز أو الرد مباشرة في هذا البوت.",
    },
    "otp_order_unavailable": {
        "fr": "Cette commande de numéro Codex n'est plus disponible. Utilisez le menu Support si vous avez besoin d'aide.",
        "en": "This Codex number order is no longer available. Use the Support menu if you need help.",
        "ar": "طلب رقم Codex هذا لم يعد متاحاً. استخدم قائمة الدعم إذا كنت بحاجة إلى المساعدة.",
    },
    "verify_ok": {
        "fr": "✅ *Paiement confirmé !* Commande #{oid}\n\nVotre commande est en cours de préparation. Vous recevrez votre produit ici très bientôt. Merci pour votre achat ! 🎉",
        "en": "✅ *Payment confirmed!* Order #{oid}\n\nYour order is being prepared. You'll receive your product here very soon. Thank you for your purchase! 🎉",
        "ar": "✅ *تم تأكيد الدفع!* الطلب #{oid}\n\nيتم تجهيز طلبك. ستستلم منتجك هنا قريباً جداً. شكراً لشرائك! 🎉",
    },
    "verify_failed": {
        "fr": "❌ Paiement non confirmé pour la commande #{oid}. Vérifiez le TXID, le montant et la devise, puis réessayez.",
        "en": "❌ Payment was not confirmed for order #{oid}. Check the TXID, amount and currency, then try again.",
        "ar": "❌ لم يتم تأكيد دفع الطلب #{oid}. تحقق من TXID والمبلغ والعملة ثم حاول مرة أخرى.",
    },
    "affiliate_payment_progress": {
        "fr": "👥 Un filleul a effectué son premier paiement. Progression : {count}/{target}.",
        "en": "👥 A referral bought from the bot for at least 1 USDT. Progress: {count}/{target}.",
        "ar": "👥 أكمل أحد الإحالات أول دفعة. التقدم: {count}/{target}.",
    },
    "affiliate_program_update": {
        "fr": "🎁 *Affiliate program update*\n\nInvitations now count only after the invited user buys from the bot for at least *1 USDT*.\n\nYou still earn *2 USDT* for every *10 qualified referrals*.",
        "en": "🎁 *Affiliate program update*\n\nInvitations now count only after the invited user buys from the bot for at least *1 USDT*.\n\nYou still earn *2 USDT* for every *10 qualified referrals*.",
        "ar": "🎁 *Affiliate program update*\n\nInvitations now count only after the invited user buys from the bot for at least *1 USDT*.\n\nYou still earn *2 USDT* for every *10 qualified referrals*.",
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
        "fr": "ℹ️ *Aide {shop}*\n\n• Parcourez le *Catalogue*, choisissez un service puis une offre.\n• Payez via *Binance Pay* à l'ID indiqué.\n• Envoyez le *TXID ou Order ID* affiché sur votre reçu Binance.\n• Après confirmation, l'équipe vous livre votre produit ici.\n\nBesoin d'aide ? Contactez l'administrateur.",
        "en": "ℹ️ *{shop} Help*\n\n• Browse the *Catalog*, pick a service then an offer.\n• Pay via *Binance Pay* to the shown ID.\n• Send the *TXID or Order ID* shown on your Binance receipt.\n• After confirmation, the team delivers your product here.\n\nNeed help? Contact the administrator.",
        "ar": "ℹ️ *مساعدة {shop}*\n\n• تصفّح *الكتالوج*، اختر خدمة ثم عرضاً.\n• ادفع عبر *Binance Pay* إلى المعرّف الظاهر.\n• أرسل *TXID أو Order ID* الظاهر في إيصال Binance.\n• بعد التأكيد، يقوم الفريق بتسليم منتجك هنا.\n\nتحتاج مساعدة؟ تواصل مع المشرف.",
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
        lang = "en"
    try:
        import database as db
        override = db.get_text_override(key, lang)
    except Exception:
        override = None
    if override is not None and str(override).strip():
        override = without_custom_emoji_tokens(override)
        if kwargs:
            with contextlib.suppress(KeyError, IndexError, ValueError):
                return override.format(**kwargs)
        return override
    entry = TRANSLATIONS.get(key, {})
    text = entry.get(lang) or entry.get("en") or key
    if kwargs:
        with contextlib.suppress(KeyError, IndexError):
            text = text.format(**kwargs)
    return text


def status_label(lang, status):
    return t(lang, f"status_{status}")
