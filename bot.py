"""WarmNest — Telegram bot.
1) Applications: student answers 7 short questions -> admins get it in Telegram + row in the "Talabalar" sheet
2) Questions: anything a student writes is sent to the admins; an admin answers by REPLYING to that message
3) Packages / FAQ / contacts, gosiwon search (Kakao Local API)
4) Source links: t.me/<bot>?start=site, ?start=ig, ?start=agency_name -> the source is saved with the application
Run:  python bot.py
"""
import asyncio
import logging
import os
import re
import time

import requests
from dotenv import load_dotenv
from telegram import (BotCommand, InlineKeyboardButton as B, InlineKeyboardMarkup as M, KeyboardButton,
                      ReplyKeyboardMarkup, ReplyKeyboardRemove, Update)
from telegram.request import HTTPXRequest
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler, ContextTypes,
                          ConversationHandler, MessageHandler, filters)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "")
KAKAO_KEY = os.getenv("KAKAO_REST_KEY", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x]
SITE = "warmnestkorea.netlify.app"
IG = "instagram.com/warmnestkorea"
# Same Apps Script web app as the website form (writes a row to the "Talabalar" tab). Empty = don't write.
SHEET_URL = os.getenv("SHEET_URL", "https://script.google.com/macros/s/AKfycbx_dBRUJKzBwYzQu-yArOIwgfXNw8mkDgChZRn_oiv0SiP69Hp6fA5H8tnoJ3qirJE9lw/exec")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("warmnest")

# ---------------------------------------------------------------- texts
T = {
    "uz": {
        "welcome": "Salom! Men WarmNest botiman 🏠\nJanubiy Koreyadagi birinchi shirin uyingizni topishda yordam beramiz.\nNima kerak?",
        "m_apply": "📝 Ariza qoldirish", "m_search": "🔎 Goshiwon qidirish",
        "m_price": "💰 Paketlar va narxlar", "m_faq": "❓ Savollar", "m_lang": "🌐 Til", "m_contact": "👤 Bog'lanish",
        "price": ("💰 *WarmNest paketlari*\n\n"
                  "*1. Qo'ng'iroq yordami* — 30 000 ₩\nXonani o'zingiz topdingiz, biz egasiga koreyscha qo'ng'iroq qilamiz.\n\n"
                  "*2. Topish + telefonda yo'l ko'rsatish* — 70 000 ₩\n\n"
                  "*3. Topish + birga borish* — 120 000 ₩\n\n"
                  "*4. Aeroport + topish + birga* — 150 000 ₩\nIncheonda kutib olamiz. Metro chiptasini o'zingiz to'laysiz.\n\n"
                  "*5. Depozitsiz xona* — 100 000 ₩ kirish + oylik ijara\nTop universitet yonida 2 do'st bilan 2 xonali uyda. Depozitni biz qo'yamiz. "
                  "Do'stlar bilan kelsangiz, har biriga 80 000 ₩. Joy kam, 1 yillik.\n\n"
                  "👥 2+ kishi birga kelsa, 1–4 paketlarga 20% chegirma.\n\n"
                  "*To'lov:* 20% oldindan (qaytarilmaydi), 80% xona shartnomasi imzolanganda. Har to'lovga kvitansiya.\n"
                  "*Pul qaytadi:* viza rad etilsa yoki 14 kunda mos xona topilmasa (agar 5 ta mos xonani rad etmagan bo'lsangiz).\n"
                  "Depozit va ijara to'g'ridan-to'g'ri uy egasiga to'lanadi (5-paketdan tashqari)."),
        "faq": ("❓ *Ko'p beriladigan savollar*\n\n"
                "*Siz ko'chmas mulk agentligimisiz?*\nYo'q. WarmNest talabalarni qo'llab-quvvatlash xizmati. Qidirish, tarjima va uy egasi bilan gaplashishda yordam beramiz. "
                "Shartnomani egasi yoki litsenziyali agent bilan o'zingiz imzolaysiz (5-paketdan tashqari).\n\n"
                "*Koreyaga kelmasdan oldin to'lasa bo'ladimi?*\nHa. 20% ni uydan to'lang, uchishingizdan oldin qidirishni boshlaymiz.\n\n"
                "*Gosiwon va one-room farqi?*\nGosiwon: oyiga ~300–450 ming ₩, depozit deyarli yo'q, lekin xona 5–7 m². "
                "One-room (원룸): joy ko'proq, depozit odatda kamida 2 000 000 ₩.\n\n"
                "*Qaysi universitetlar?*\nAsosan Seul va atrofi: Kyung Hee, Korea, Hanyang, Sungkyunkwan, Konkuk, Sejong va boshqalar.\n\n"
                "*Ko'chib kirgandan keyin-chi?*\n1 oy bepul yordam: tarjima, egasiga qo'ng'iroq, mayda muammolar.\n\n"
                "*Qaysi tillarda?*\nO'zbek, rus, ingliz va koreys."),
        "contact": "👤 Masrur: @jamaldinev\n👤 David: @Mangomen8\n🌐 " + SITE + "\n📸 " + IG,
        "ask_uni": "Qaysi universitetda o'qiysiz? (nomini yozing)",
        "ask_gender": "Jinsingiz?", "boy": "👦 O'g'il", "girl": "👧 Qiz",
        "ask_budget": "Oylik byudjet (₩)? Masalan: 400000",
        "ask_date": "Qachon kelasiz / qachon kerak? (sana yozing)",
        "ask_name": "Ismingiz?",
        "done": "✅ Arizangiz qabul qilindi! Masrur yoki David 24 soat ichida Telegramda yozadi.",
        "s_uni": "Qaysi universitet yaqinidan qidiray? (nomini yozing, masalan: Kyung Hee University)",
        "s_gender": "Kim uchun?", "s_none": "Hech narsa topilmadi. Boshqa nom bilan urinib ko'ring yoki ariza qoldiring.",
        "s_nokey": "Qidiruv hozir sozlanmagan. Ariza qoldiring — o'zimiz topib beramiz.",
        "s_note": ("\n\n⚠️ Bu ro'yxat xaritadan olingan. Xona bo'shligi, narxi va jinsi (ayollar uchun/yo'q) tasdiqlanmagan — "
                   "telefon qilib so'rang yoki bizga yozing."),
        "cancel": "Bekor qilindi.", "back": "⬅️ Menyu", "km": "m", "found": "📍 {u} atrofida topildi:",
        "no_phone": "telefon yo'q",
    },
    "ru": {
        "welcome": "Привет! Я бот WarmNest 🏠\nПоможем найти ваш первый дом в Южной Корее.\nЧто нужно?",
        "m_apply": "📝 Оставить заявку", "m_search": "🔎 Поиск госивонов",
        "m_price": "💰 Пакеты и цены", "m_faq": "❓ Вопросы", "m_lang": "🌐 Язык", "m_contact": "👤 Связаться",
        "price": ("💰 *Пакеты WarmNest*\n\n"
                  "*1. Помощь по телефону* — 30 000 ₩\nВы нашли комнату, мы звоним хозяину на корейском.\n\n"
                  "*2. Поиск + сопровождение по телефону* — 70 000 ₩\n\n"
                  "*3. Поиск + идём вместе* — 120 000 ₩\n\n"
                  "*4. Аэропорт + поиск + вместе* — 150 000 ₩\nВстречаем в Инчхоне. Билет на метро вы оплачиваете сами.\n\n"
                  "*5. Комната без депозита* — 100 000 ₩ вход + ежемесячная аренда\nДвухкомнатный дом рядом с топ-университетом, с 2 друзьями. Депозит вносим мы. "
                  "С друзьями — по 80 000 ₩ с каждого. Мест мало, на 1 год.\n\n"
                  "👥 Группам от 2 человек скидка 20% на пакеты 1–4.\n\n"
                  "*Оплата:* 20% заранее (не возвращается), 80% при подписании договора. Чек за каждый платёж.\n"
                  "*Возврат:* если отказали в визе или за 14 дней нет подходящей комнаты (если вы не отказались от 5 подходящих).\n"
                  "Депозит и аренда идут напрямую хозяину (кроме пакета 5)."),
        "faq": ("❓ *Частые вопросы*\n\n"
                "*Вы агентство недвижимости?*\nНет. WarmNest — сервис поддержки студентов. Помогаем искать, переводить и общаться с хозяином. "
                "Договор вы подписываете напрямую с хозяином или лицензированным агентом (кроме пакета 5).\n\n"
                "*Можно оплатить до приезда?*\nДа. Оплатите 20% из дома, и мы начнём поиск до вашего вылета.\n\n"
                "*Госивон и ванрум?*\nГосивон: ~300–450 тыс. ₩/мес, почти без депозита, но комната 5–7 м². "
                "Ванрум (원룸): больше места, депозит обычно от 2 000 000 ₩.\n\n"
                "*Какие университеты?*\nВ основном Сеул и окрестности: Кёнхи, Корё, Ханян, Сонгюнгван, Конкук, Седжон и другие.\n\n"
                "*А после заезда?*\nМесяц бесплатной помощи: перевод, звонки хозяину, мелкие вопросы.\n\n"
                "*Языки?*\nУзбекский, русский, английский и корейский."),
        "contact": "👤 Масрур: @jamaldinev\n👤 Давид: @Mangomen8\n🌐 " + SITE + "\n📸 " + IG,
        "ask_uni": "В каком университете учитесь? (напишите название)",
        "ask_gender": "Ваш пол?", "boy": "👦 Парень", "girl": "👧 Девушка",
        "ask_budget": "Бюджет в месяц (₩)? Например: 400000",
        "ask_date": "Когда приедете / когда нужно жильё? (дата)",
        "ask_name": "Ваше имя?",
        "done": "✅ Заявка принята! Масрур или Давид напишут вам в Telegram в течение 24 часов.",
        "s_uni": "Рядом с каким университетом искать? (название, напр.: Kyung Hee University)",
        "s_gender": "Для кого?", "s_none": "Ничего не найдено. Попробуйте другое название или оставьте заявку.",
        "s_nokey": "Поиск пока не настроен. Оставьте заявку — найдём сами.",
        "s_note": ("\n\n⚠️ Список взят с карты. Наличие мест, цена и пол (только для женщин или нет) не подтверждены — "
                   "позвоните или напишите нам."),
        "cancel": "Отменено.", "back": "⬅️ Меню", "km": "м", "found": "📍 Найдено рядом с {u}:",
        "no_phone": "нет телефона",
    },
    "en": {
        "welcome": "Hi! I'm the WarmNest bot 🏠\nYour sweet first home in South Korea.\nWhat do you need?",
        "m_apply": "📝 Apply", "m_search": "🔎 Search goshiwon",
        "m_price": "💰 Packages & prices", "m_faq": "❓ FAQ", "m_lang": "🌐 Language", "m_contact": "👤 Contact",
        "price": ("💰 *WarmNest packages*\n\n"
                  "*1. Call help* — 30,000 ₩\nYou found a room; we call the owner in Korean.\n\n"
                  "*2. Find + phone guidance* — 70,000 ₩\n\n"
                  "*3. Find + go together* — 120,000 ₩\n\n"
                  "*4. Airport + find + go* — 150,000 ₩\nWe meet you at Incheon. You pay your own metro ticket.\n\n"
                  "*5. No-deposit room* — 100,000 ₩ entry + monthly rent\nA two-room home near a top university with 2 friends. We cover the deposit. "
                  "80,000 ₩ entry each when friends come together. Limited places, 1-year stay.\n\n"
                  "👥 Groups of 2+ get 20% off packages 1–4.\n\n"
                  "*Payment:* 20% upfront (non-refundable), 80% when you sign the room contract. A receipt for every payment.\n"
                  "*Refund:* if your visa is refused, or we find nothing in 14 days (unless you turned down 5 matching rooms).\n"
                  "Deposit and rent go directly to the owner (except package 5)."),
        "faq": ("❓ *FAQ*\n\n"
                "*Are you a real estate agency?*\nNo. WarmNest is a student support service. We help you search, translate and talk to the owner. "
                "You sign the contract directly with the owner or a licensed agent (except package 5).\n\n"
                "*Can I pay before I arrive?*\nYes. Pay the 20% from home and we start searching before you fly.\n\n"
                "*Gosiwon vs one-room?*\nGosiwon: ~300–450k ₩/month, little or no deposit, but the room is 5–7 m². "
                "One-room (원룸): more space, deposit usually from 2,000,000 ₩.\n\n"
                "*Which universities?*\nMostly Seoul and nearby: Kyung Hee, Korea University, Hanyang, Sungkyunkwan, Konkuk, Sejong and others.\n\n"
                "*After I move in?*\nOne month of free help: translation, calls to the owner, small problems.\n\n"
                "*Languages?*\nUzbek, Russian, English and Korean."),
        "contact": "👤 Masrur: @jamaldinev\n👤 David: @Mangomen8\n🌐 " + SITE + "\n📸 " + IG,
        "ask_uni": "Which university do you study at? (type the name)",
        "ask_gender": "Your gender?", "boy": "👦 Male", "girl": "👧 Female",
        "ask_budget": "Monthly budget (₩)? e.g. 400000",
        "ask_date": "When do you arrive / need the room? (date)",
        "ask_name": "Your name?",
        "done": "✅ Application received! Masrur or David will write to you on Telegram within 24 hours.",
        "s_uni": "Search near which university? (type the name, e.g. Kyung Hee University)",
        "s_gender": "For whom?", "s_none": "Nothing found. Try another name or submit an application.",
        "s_nokey": "Search isn't set up yet. Submit an application and we'll find it for you.",
        "s_note": ("\n\n⚠️ This list comes from a map. Availability, price and gender policy (women-only or not) are NOT confirmed — "
                   "call them or message us."),
        "cancel": "Cancelled.", "back": "⬅️ Menu", "km": "m", "found": "📍 Found near {u}:",
        "no_phone": "no phone",
    },
}
LANGS = {"uz": "🇺🇿 O'zbekcha", "ru": "🇷🇺 Русский", "en": "🇬🇧 English"}

# extra texts for the application, questions and commands
T["uz"].update({
    "m_ask": "💬 Savol berish",
    "ask_name": "Ariza 1 daqiqa oladi. Bekor qilish: /cancel\n\n1/7. Ism familiyangiz?",
    "ask_uni": "2/7. Koreyadagi universitetingiz? (nomini yozing)",
    "ask_gender": "3/7. Jinsingiz?",
    "ask_date": "4/7. Koreyaga qachon kelasiz? (masalan: 2027 fevral. Koreyada bo'lsangiz: hozir)",
    "ask_budget": "5/7. Xona uchun oylik budjet (₩)? Masalan: 400000",
    "ask_pkg": "6/7. Qaysi paket kerak?",
    "pk": ["1. Qo'ng'iroq yordami · 30k", "2. Topish + telefonda · 70k", "3. Topish + birga borish · 120k",
           "4. Aeroport + topish · 150k", "5. Depozitsiz xona"],
    "pk_unsure": "🤔 Hali bilmayman",
    "ask_phone": "7/7. Telefon yoki WhatsApp raqamingiz? Tugmani bosing yoki raqamni yozing.",
    "share": "📱 Raqamimni yuborish", "skip": "O'tkazib yuborish",
    "use_buttons": "Iltimos, yuqoridagi tugmalardan birini bosing 👆",
    "done": "✅ Arizangiz qabul qilindi! Masrur yoki David 24 soat ichida shu yerda yoki Telegramda yozadi.\n\nSavolingiz bo'lsa, shu yerga yozavering.",
    "ask_q": "Savolingizni shu yerga yozing. Masrur yoki David shu chatda javob beradi.",
    "q_ok": "✅ Xabaringiz yuborildi. Tez orada shu yerda javob beramiz.",
    "answer": "💬 WarmNest javobi:",
    "c_start": "Bosh menyu", "c_apply": "Ariza qoldirish", "c_cancel": "Bekor qilish",
})
T["ru"].update({
    "m_ask": "💬 Задать вопрос",
    "ask_name": "Заявка займёт 1 минуту. Отмена: /cancel\n\n1/7. Ваши имя и фамилия?",
    "ask_uni": "2/7. Ваш университет в Корее? (напишите название)",
    "ask_gender": "3/7. Ваш пол?",
    "ask_date": "4/7. Когда приезжаете в Корею? (например: февраль 2027. Если уже в Корее: сейчас)",
    "ask_budget": "5/7. Бюджет на комнату в месяц (₩)? Например: 400000",
    "ask_pkg": "6/7. Какой пакет нужен?",
    "pk": ["1. Помощь по телефону · 30k", "2. Поиск + по телефону · 70k", "3. Поиск + идём вместе · 120k",
           "4. Аэропорт + поиск · 150k", "5. Комната без депозита"],
    "pk_unsure": "🤔 Пока не знаю",
    "ask_phone": "7/7. Ваш телефон или WhatsApp? Нажмите кнопку или напишите номер.",
    "share": "📱 Отправить мой номер", "skip": "Пропустить",
    "use_buttons": "Пожалуйста, нажмите одну из кнопок выше 👆",
    "done": "✅ Заявка принята! Масрур или Давид напишут вам здесь или в Telegram в течение 24 часов.\n\nЕсли есть вопросы, пишите прямо сюда.",
    "ask_q": "Напишите ваш вопрос прямо сюда. Масрур или Давид ответят в этом чате.",
    "q_ok": "✅ Сообщение отправлено. Скоро ответим здесь.",
    "answer": "💬 Ответ WarmNest:",
    "c_start": "Главное меню", "c_apply": "Оставить заявку", "c_cancel": "Отмена",
})
T["en"].update({
    "m_ask": "💬 Ask a question",
    "ask_name": "The application takes 1 minute. To cancel: /cancel\n\n1/7. Your full name?",
    "ask_uni": "2/7. Your university in Korea? (type the name)",
    "ask_gender": "3/7. Your gender?",
    "ask_date": "4/7. When do you arrive in Korea? (e.g. February 2027. Already in Korea: now)",
    "ask_budget": "5/7. Monthly budget for the room (₩)? e.g. 400000",
    "ask_pkg": "6/7. Which package do you need?",
    "pk": ["1. Call help · 30k", "2. Find + phone guidance · 70k", "3. Find + go together · 120k",
           "4. Airport + find + go · 150k", "5. No-deposit room"],
    "pk_unsure": "🤔 Not sure yet",
    "ask_phone": "7/7. Your phone or WhatsApp number? Tap the button or type the number.",
    "share": "📱 Share my number", "skip": "Skip",
    "use_buttons": "Please tap one of the buttons above 👆",
    "done": "✅ Application received! Masrur or David will write to you here or on Telegram within 24 hours.\n\nIf you have questions, just write them here.",
    "ask_q": "Write your question right here. Masrur or David will answer in this chat.",
    "q_ok": "✅ Message sent. We'll answer here soon.",
    "answer": "💬 WarmNest reply:",
    "c_start": "Main menu", "c_apply": "Apply", "c_cancel": "Cancel",
})

# values the "Talabalar" sheet expects (same as the website form)
PKG_SHEET = ["1. Qo'ng'iroq", "2. Masofaviy", "3. Birga boramiz", "4. Aeroport + xona", "5. Depozitsiz", ""]
COUNTRY_BY_CODE = {"998": "O'zbekiston", "996": "Qirg'iziston", "992": "Tojikiston", "993": "Turkmaniston",
                   "76": "Qozog'iston", "77": "Qozog'iston"}

ASK_NAME, ASK_UNI, ASK_GENDER, ASK_DATE, ASK_BUDGET, ASK_PKG, ASK_PHONE = range(7)
S_UNI, S_GENDER = range(7, 9)
PRIVATE = filters.ChatType.PRIVATE
ID_TAG = re.compile(r"#id(\d+)")


def L(ctx) -> dict:
    return T[ctx.user_data.get("lang", "uz")]


def is_admin(update: Update) -> bool:
    return bool(update.effective_user) and update.effective_user.id in ADMIN_IDS


def who(u) -> str:
    """One line that identifies a student for the admins. #id lets an admin answer by replying."""
    name = " ".join(x for x in (u.first_name, u.last_name) if x) or "?"
    return f"{name} ({'@' + u.username if u.username else 'no username'}) #id{u.id}"


def menu(ctx) -> M:
    t = L(ctx)
    return M([
        [B(t["m_apply"], callback_data="apply")],
        [B(t["m_price"], callback_data="price"), B(t["m_faq"], callback_data="faq")],
        [B(t["m_ask"], callback_data="ask"), B(t["m_search"], callback_data="search")],
        [B(t["m_contact"], callback_data="contact"), B(t["m_lang"], callback_data="lang")],
    ])


def back_kb(ctx) -> M:
    t = L(ctx)
    return M([[B(t["m_apply"], callback_data="apply")], [B(t["back"], callback_data="menu")]])


def lang_kb() -> M:
    return M([[B(v, callback_data=f"setlang:{k}")] for k, v in LANGS.items()])


async def notify_admins(ctx, text: str, skip: int = 0, **kw) -> int:
    sent = 0
    for aid in ADMIN_IDS:
        if aid == skip:
            continue
        try:
            await ctx.bot.send_message(aid, text, **kw)
            sent += 1
        except Exception as e:  # admin hasn't pressed /start, etc.
            log.warning("could not notify %s: %s", aid, e)
    return sent


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.args and "src" not in ctx.user_data:  # t.me/<bot>?start=site -> source "site"
        ctx.user_data["src"] = re.sub(r"[^\w-]", "", ctx.args[0])[:40]
    if "lang" not in ctx.user_data:
        await update.effective_message.reply_text(
            "Tilni tanlang / Выберите язык / Choose language:", reply_markup=lang_kb())
        return
    await update.effective_message.reply_text(L(ctx)["welcome"], reply_markup=menu(ctx))


async def myid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your chat ID: {update.effective_chat.id}")


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    if d.startswith("setlang:"):
        ctx.user_data["lang"] = d.split(":")[1] if d.split(":")[1] in T else "uz"
        d = "menu"
    t = L(ctx)
    if d == "menu":
        await q.message.reply_text(t["welcome"], reply_markup=menu(ctx))
    elif d == "lang":
        await q.message.reply_text("🌐", reply_markup=lang_kb())
    elif d == "ask":
        await q.message.reply_text(t["ask_q"])
    elif d in ("price", "faq", "contact"):
        await q.message.reply_text(t[d], parse_mode="Markdown", reply_markup=back_kb(ctx),
                                   disable_web_page_preview=True)


# ---------------------------------------------------------------- apply flow
async def apply_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
    ctx.user_data["app"] = {}
    await update.effective_message.reply_text(L(ctx)["ask_name"])
    return ASK_NAME


async def apply_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["app"]["name"] = update.message.text.strip()[:100]
    await update.message.reply_text(L(ctx)["ask_uni"])
    return ASK_UNI


async def apply_uni(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["app"]["uni"] = update.message.text.strip()[:100]
    t = L(ctx)
    await update.message.reply_text(t["ask_gender"], reply_markup=M(
        [[B(t["boy"], callback_data="g:boy"), B(t["girl"], callback_data="g:girl")]]))
    return ASK_GENDER


async def apply_gender(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ctx.user_data["app"]["gender"] = "Erkak" if q.data == "g:boy" else "Ayol"
    await q.message.reply_text(L(ctx)["ask_date"])
    return ASK_DATE


async def apply_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["app"]["date"] = update.message.text.strip()[:60]
    await update.message.reply_text(L(ctx)["ask_budget"])
    return ASK_BUDGET


async def apply_budget(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["app"]["budget"] = update.message.text.strip()[:60]
    t = L(ctx)
    rows = [[B(name, callback_data=f"pk:{i}")] for i, name in enumerate(t["pk"])]
    rows.append([B(t["pk_unsure"], callback_data="pk:5")])
    await update.message.reply_text(t["ask_pkg"], reply_markup=M(rows))
    return ASK_PKG


async def apply_pkg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    i = int(q.data.split(":")[1])
    ctx.user_data["app"]["pkg"] = PKG_SHEET[i] if 0 <= i < len(PKG_SHEET) else ""
    t = L(ctx)
    await q.message.reply_text(t["ask_phone"], reply_markup=ReplyKeyboardMarkup(
        [[KeyboardButton(t["share"], request_contact=True)], [KeyboardButton(t["skip"])]],
        resize_keyboard=True, one_time_keyboard=True))
    return ASK_PHONE


async def use_buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(L(ctx)["use_buttons"])


def save_to_sheet(data: dict) -> bool:
    """Sends the application to the same Apps Script as the website form."""
    if not SHEET_URL:
        return False
    r = requests.post(SHEET_URL, data=data, timeout=25)
    return r.ok and "ok" in r.text[:20].lower()


async def apply_phone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    a, t, m, u = ctx.user_data.get("app", {}), L(ctx), update.message, update.effective_user
    if m.contact:
        phone = "+" + m.contact.phone_number.lstrip("+")
    elif (m.text or "").strip() == t["skip"]:
        phone = ""
    else:
        phone = (m.text or "").strip()[:30]
    digits = re.sub(r"\D", "", phone)
    country = next((c for code, c in COUNTRY_BY_CODE.items() if digits.startswith(code)), "")
    src = ctx.user_data.get("src", "")
    lang = ctx.user_data.get("lang", "uz")

    msg = (f"🆕 Yangi ariza (bot)\n\n👤 {a.get('name','')}\n🎓 {a.get('uni','')}\n⚧ {a.get('gender','')}\n"
           f"📅 Kelish: {a.get('date','')}\n💰 Budjet: {a.get('budget','')}\n📦 Paket: {a.get('pkg') or 'bilmaydi'}\n"
           f"📱 {phone or 'raqam bermadi'}\n🌐 Til: {lang}" + (f"\n🔗 Manba: {src}" if src else "") +
           f"\n\nTelegram: {who(u)}")

    note = "; ".join(x for x in (f"Tel: {phone}" if phone and u.username else "",
                                  f"Manba: {src}" if src else "", f"TG id {u.id}") if x)
    row = {"name": a.get("name", ""), "contact": f"@{u.username}" if u.username else (phone or f"TG id {u.id}"),
           "gender": a.get("gender", ""), "country": country, "university": a.get("uni", ""),
           "arrival": a.get("date", ""), "budget": a.get("budget", ""), "package": a.get("pkg", ""),
           "lang": f"Telegram bot, {lang}", "message": note}
    try:
        saved = await asyncio.to_thread(save_to_sheet, row)
    except Exception as e:
        log.error("sheet error: %s", e)
        saved = False
    msg += "\n\n" + ("✅ Jadvalga yozildi (Talabalar)" if saved else "⚠️ JADVALGA YOZILMADI, qo'lda kiriting!")
    msg += "\n↩️ Javob berish: shu xabarga Reply qiling."
    kb = M([[B("✍️ Chatni ochish", url=f"https://t.me/{u.username}" if u.username else f"tg://user?id={u.id}")]])
    sent = await notify_admins(ctx, msg, reply_markup=kb)
    log.info("application %s | sheet=%s | admins=%d", row, saved, sent)

    await m.reply_text(t["done"], reply_markup=ReplyKeyboardRemove())
    await m.reply_text(t["welcome"], reply_markup=menu(ctx))
    ctx.user_data.pop("app", None)
    return ConversationHandler.END


# ---------------------------------------------------------------- questions: student <-> admins
async def relay(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    m, u = update.effective_message, update.effective_user
    if is_admin(update):
        ref = m.reply_to_message
        found = ID_TAG.search((ref.text or ref.caption or "") if ref else "")
        if not found:
            await m.reply_text("Talabaga javob berish uchun uning xabariga (#id bor xabarga) Reply qiling.\n"
                               "Botni talaba sifatida sinash: /start")
            return
        uid = int(found.group(1))
        student_lang = ctx.application.user_data.get(uid, {}).get("lang", "uz")
        try:
            if m.text:
                await ctx.bot.send_message(uid, f"{T[student_lang]['answer']}\n\n{m.text}")
            else:
                await ctx.bot.copy_message(uid, m.chat_id, m.message_id)
            await m.reply_text("✅ Talabaga yuborildi.")
            await notify_admins(ctx, f"↪️ {u.first_name} javob berdi (#id{uid}):\n{m.text or '[fayl]'}", skip=u.id)
        except Exception as e:
            await m.reply_text(f"⚠️ Yuborilmadi: {e}")
        return

    head = f"❓ Savol: {who(u)}"
    if ctx.user_data.get("src"):
        head += f"\n🔗 Manba: {ctx.user_data['src']}"
    hint = "\n\n↩️ Javob berish: shu xabarga Reply qiling."
    if m.text:
        await notify_admins(ctx, f"{head}\n\n{m.text[:3500]}{hint}")
    else:  # photo, voice, file...
        for aid in ADMIN_IDS:
            try:
                await ctx.bot.copy_message(aid, m.chat_id, m.message_id)
                await ctx.bot.send_message(aid, f"⬆️ {head}{hint}")
            except Exception as e:
                log.warning("could not forward to %s: %s", aid, e)
    if time.time() - ctx.user_data.get("ack", 0) > 600:  # don't repeat "we got it" on every message
        ctx.user_data["ack"] = time.time()
        await m.reply_text(L(ctx)["q_ok"])


# ---------------------------------------------------------------- search flow
async def search_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(L(ctx)["s_uni"])
    return S_UNI


async def search_uni(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["s_uni"] = update.message.text.strip()
    t = L(ctx)
    await update.message.reply_text(t["s_gender"], reply_markup=M([[B(t["boy"], callback_data="sg:boy"), B(t["girl"], callback_data="sg:girl")]]))
    return S_GENDER


def kakao(path: str, **params):
    r = requests.get("https://dapi.kakao.com/v2/local/search/" + path, params=params,
                     headers={"Authorization": f"KakaoAK {KAKAO_KEY}"}, timeout=10)
    r.raise_for_status()
    return r.json().get("documents", [])


def find_places(uni: str, girl: bool):
    campus = kakao("keyword.json", query=uni, size=1)
    if not campus:
        return None, []
    c = campus[0]
    queries = ["여성 고시원", "고시원"] if girl else ["고시원"]
    seen, out = set(), []
    for qy in queries:
        for page in (1, 2):
            docs = kakao("keyword.json", query=qy, x=c["x"], y=c["y"], radius=3000, sort="distance", size=15, page=page)
            for d in docs:
                if d["id"] not in seen:
                    seen.add(d["id"])
                    out.append(d)
    out.sort(key=lambda d: int(d.get("distance") or 99999))
    return c["place_name"], out[:12]


async def search_gender(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    t = L(ctx)
    if not KAKAO_KEY:
        await q.message.reply_text(t["s_nokey"], reply_markup=menu(ctx))
        return ConversationHandler.END
    girl = q.data == "sg:girl"
    try:
        name, places = await asyncio.to_thread(find_places, ctx.user_data.get("s_uni", ""), girl)
    except Exception as e:
        log.error("kakao error: %s", e)
        await q.message.reply_text(t["s_none"], reply_markup=menu(ctx))
        return ConversationHandler.END
    if not places:
        await q.message.reply_text(t["s_none"], reply_markup=menu(ctx))
        return ConversationHandler.END
    lines = [t["found"].format(u=name), ""]
    for i, p in enumerate(places, 1):
        addr = p.get("road_address_name") or p.get("address_name", "")
        lines.append(f"{i}. {p['place_name']} — {p.get('distance','?')} {t['km']}\n   {addr}\n   📞 {p.get('phone') or t['no_phone']}\n   {p.get('place_url','')}")
    await q.message.reply_text("\n".join(lines)[:3800] + t["s_note"], disable_web_page_preview=True, reply_markup=menu(ctx))
    return ConversationHandler.END


async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.pop("app", None)
    await update.effective_message.reply_text(L(ctx)["cancel"], reply_markup=ReplyKeyboardRemove())
    await update.effective_message.reply_text(L(ctx)["welcome"], reply_markup=menu(ctx))
    return ConversationHandler.END


async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    log.error("error while handling update", exc_info=ctx.error)


async def post_init(app: Application):
    """Shows the / command list in Telegram, in the student's language."""
    for code in ("uz", "ru", "en"):
        t = T[code]
        cmds = [BotCommand("start", t["c_start"]), BotCommand("apply", t["c_apply"]), BotCommand("cancel", t["c_cancel"])]
        try:
            await app.bot.set_my_commands(cmds, language_code=code)
            if code == "en":
                await app.bot.set_my_commands(cmds)  # default for all other languages
        except Exception as e:
            log.warning("could not set commands: %s", e)


def build(token: str) -> Application:
    req = HTTPXRequest(connect_timeout=30, read_timeout=30, write_timeout=30, pool_timeout=30)
    upd = HTTPXRequest(connect_timeout=30, read_timeout=40, write_timeout=30, pool_timeout=30)
    app = Application.builder().token(token).request(req).get_updates_request(upd).post_init(post_init).build()
    text = filters.TEXT & ~filters.COMMAND
    stop = [CommandHandler("cancel", cancel), CommandHandler("start", cancel)]
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(apply_start, pattern="^apply$"), CommandHandler("apply", apply_start)],
        states={ASK_NAME: [MessageHandler(text, apply_name)],
                ASK_UNI: [MessageHandler(text, apply_uni)],
                ASK_GENDER: [CallbackQueryHandler(apply_gender, pattern="^g:"), MessageHandler(text, use_buttons)],
                ASK_DATE: [MessageHandler(text, apply_date)],
                ASK_BUDGET: [MessageHandler(text, apply_budget)],
                ASK_PKG: [CallbackQueryHandler(apply_pkg, pattern="^pk:"), MessageHandler(text, use_buttons)],
                ASK_PHONE: [MessageHandler(filters.CONTACT | text, apply_phone)]},
        fallbacks=stop, allow_reentry=True))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(search_start, pattern="^search$")],
        states={S_UNI: [MessageHandler(text, search_uni)],
                S_GENDER: [CallbackQueryHandler(search_gender, pattern="^sg:"), MessageHandler(text, use_buttons)]},
        fallbacks=stop, allow_reentry=True))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(PRIVATE & ~filters.COMMAND & ~filters.StatusUpdate.ALL, relay))
    app.add_error_handler(on_error)
    return app


def main():
    if not TOKEN:
        raise SystemExit("BOT_TOKEN is missing. Copy .env.example to .env and fill it in.")
    app = build(TOKEN)
    log.info("Bot started")
    base = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if base:  # running on Render: webhook mode (wakes up when a message arrives)
        app.run_webhook(listen="0.0.0.0", port=int(os.getenv("PORT", "10000")),
                        url_path=TOKEN, webhook_url=f"{base}/{TOKEN}")
    else:  # running on your computer: polling mode
        app.run_polling(bootstrap_retries=5)


if __name__ == "__main__":
    main()
