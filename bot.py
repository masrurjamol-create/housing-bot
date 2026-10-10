"""Housing in Seoul — Telegram bot.
Functions: 1) apply (collect applications)  2) goshiwon search (Kakao Local API)  3) prices / FAQ
Run:  python bot.py
"""
import os
import logging
import requests
from dotenv import load_dotenv
from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup as M, Update
from telegram.request import HTTPXRequest
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler, ContextTypes,
                          ConversationHandler, MessageHandler, filters)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "")
KAKAO_KEY = os.getenv("KAKAO_REST_KEY", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x]
SITE = "housinginseoul.uz"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("hisbot")

# ---------------------------------------------------------------- texts
T = {
    "uz": {
        "welcome": "Salom! Men Housing in Seoul botiman. Koreyada uy/goshiwon topishda yordam beraman.\nNima kerak?",
        "m_apply": "📝 Ariza qoldirish", "m_search": "🔎 Goshiwon qidirish",
        "m_price": "💰 Narxlar", "m_faq": "❓ Savollar", "m_lang": "🌐 Til", "m_contact": "👤 Bog'lanish",
        "price": ("💰 *Xizmat narxlari*\n\nBasic — 50 000 ₩\nStandard — 100 000 ₩\nPremium — 150 000–200 000 ₩\n"
                  "Guruh (2+ kishi) — 20% chegirma\n\nTo'lov: 20% oldindan (qaytarilmaydi), 80% — uy topilgandan keyin.\n"
                  "Xizmat haqi — bizga. Uyning depoziti va oylik ijarasi — to'g'ridan-to'g'ri uy egasiga."),
        "faq": ("❓ *Ko'p so'raladigan savollar*\n\n"
                "*Goshiwon va one-room farqi?*\nGoshiwon — kichik xona, depozit deyarli yo'q (oyiga ~300–450k ₩). "
                "One-room (원룸) — alohida xona, odatda depozit kamida 2 000 000 ₩ (~$1 500) + oylik ijara.\n\n"
                "*Depozit qaytadimi?*\nHa, odatda shartnoma tugagach uy egasi qaytaradi.\n\n"
                "*Shartnomani kim imzolaydi?*\nSiz va uy egasi. Biz yordam beramiz, lekin pul va shartnoma — sizning va uy egasi o'rtasida.\n\n"
                "*Kafolat bormi?*\nXona mavjudligini tekshiramiz, lekin narx va sharoit uy egasiga bog'liq. Imzolashdan oldin o'zingiz ko'ring."),
        "contact": "👤 Masrur: @jamaldinev\n👤 David: @Mangomen8\n🌐 " + SITE,
        "ask_uni": "Qaysi universitetda o'qiysiz? (nomini yozing)",
        "ask_gender": "Jinsingiz?", "boy": "👦 O'g'il", "girl": "👧 Qiz",
        "ask_budget": "Oylik byudjet (₩)? Masalan: 400000",
        "ask_date": "Qachon kelasiz / qachon kerak? (sana yozing)",
        "ask_name": "Ismingiz?",
        "done": "✅ Arizangiz qabul qilindi! Masrur yoki David tez orada siz bilan Telegramda bog'lanadi.",
        "s_uni": "Qaysi universitet yaqinidan qidiray? (nomini yozing, masalan: Kyung Hee University)",
        "s_gender": "Kim uchun?", "s_none": "Hech narsa topilmadi. Boshqa nom bilan urinib ko'ring yoki ariza qoldiring.",
        "s_nokey": "Qidiruv hozir sozlanmagan. Ariza qoldiring — o'zimiz topib beramiz.",
        "s_note": ("\n\n⚠️ Bu ro'yxat xaritadan olingan. Xona bo'shligi, narxi va jinsi (ayollar uchun/yo'q) tasdiqlanmagan — "
                   "telefon qilib so'rang yoki bizga yozing."),
        "cancel": "Bekor qilindi.", "back": "⬅️ Menyu", "km": "m", "found": "📍 {u} atrofida topildi:",
        "no_phone": "telefon yo'q",
    },
    "ru": {
        "welcome": "Привет! Я бот Housing in Seoul. Помогаю найти жильё/госивон в Корее.\nЧто нужно?",
        "m_apply": "📝 Оставить заявку", "m_search": "🔎 Поиск госивонов",
        "m_price": "💰 Цены", "m_faq": "❓ Вопросы", "m_lang": "🌐 Язык", "m_contact": "👤 Связаться",
        "price": ("💰 *Цены на услуги*\n\nBasic — 50 000 ₩\nStandard — 100 000 ₩\nPremium — 150 000–200 000 ₩\n"
                  "Группа (2+ чел.) — скидка 20%\n\nОплата: 20% заранее (не возвращается), 80% — после заселения.\n"
                  "Наша плата — только за услугу. Депозит и аренду вы платите напрямую хозяину."),
        "faq": ("❓ *Частые вопросы*\n\n"
                "*Госивон и ван-рум?*\nГосивон — маленькая комната, почти без депозита (~300–450k ₩/мес). "
                "Ван-рум (원룸) — отдельная комната, депозит обычно от 2 000 000 ₩ (~$1 500) + аренда.\n\n"
                "*Депозит возвращают?*\nОбычно да, по окончании договора.\n\n"
                "*Кто подписывает договор?*\nВы и хозяин. Мы помогаем, деньги и договор — между вами и хозяином.\n\n"
                "*Есть гарантии?*\nМы проверяем наличие комнаты, но цена и условия зависят от хозяина. Посмотрите комнату до подписания."),
        "contact": "👤 Масрур: @jamaldinev\n👤 Давид: @Mangomen8\n🌐 " + SITE,
        "ask_uni": "В каком университете учитесь? (напишите название)",
        "ask_gender": "Ваш пол?", "boy": "👦 Парень", "girl": "👧 Девушка",
        "ask_budget": "Бюджет в месяц (₩)? Например: 400000",
        "ask_date": "Когда приедете / когда нужно жильё? (дата)",
        "ask_name": "Ваше имя?",
        "done": "✅ Заявка принята! Масрур или Давид скоро свяжутся с вами в Telegram.",
        "s_uni": "Рядом с каким университетом искать? (название, напр.: Kyung Hee University)",
        "s_gender": "Для кого?", "s_none": "Ничего не найдено. Попробуйте другое название или оставьте заявку.",
        "s_nokey": "Поиск пока не настроен. Оставьте заявку — найдём сами.",
        "s_note": ("\n\n⚠️ Список взят с карты. Наличие мест, цена и пол (только для женщин или нет) не подтверждены — "
                   "позвоните или напишите нам."),
        "cancel": "Отменено.", "back": "⬅️ Меню", "km": "м", "found": "📍 Найдено рядом с {u}:",
        "no_phone": "нет телефона",
    },
    "en": {
        "welcome": "Hi! I'm the Housing in Seoul bot. I help you find a room/goshiwon in Korea.\nWhat do you need?",
        "m_apply": "📝 Apply", "m_search": "🔎 Search goshiwon",
        "m_price": "💰 Prices", "m_faq": "❓ FAQ", "m_lang": "🌐 Language", "m_contact": "👤 Contact",
        "price": ("💰 *Service prices*\n\nBasic — 50,000 ₩\nStandard — 100,000 ₩\nPremium — 150,000–200,000 ₩\n"
                  "Group (2+ people) — 20% off\n\nPayment: 20% upfront (non-refundable), 80% after placement.\n"
                  "Our fee is for the service only. Deposit and rent go directly to the landlord."),
        "faq": ("❓ *FAQ*\n\n"
                "*Goshiwon vs one-room?*\nGoshiwon — tiny room, almost no deposit (~300–450k ₩/month). "
                "One-room (원룸) — private room, deposit usually from 2,000,000 ₩ (~$1,500) + monthly rent.\n\n"
                "*Is the deposit refundable?*\nUsually yes, when the contract ends.\n\n"
                "*Who signs the contract?*\nYou and the landlord. We help; money and contract are between you and the landlord.\n\n"
                "*Any guarantee?*\nWe check the room is available, but price and conditions depend on the landlord. See the room before signing."),
        "contact": "👤 Masrur: @jamaldinev\n👤 David: @Mangomen8\n🌐 " + SITE,
        "ask_uni": "Which university do you study at? (type the name)",
        "ask_gender": "Your gender?", "boy": "👦 Male", "girl": "👧 Female",
        "ask_budget": "Monthly budget (₩)? e.g. 400000",
        "ask_date": "When do you arrive / need the room? (date)",
        "ask_name": "Your name?",
        "done": "✅ Application received! Masrur or David will contact you on Telegram soon.",
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

ASK_UNI, ASK_GENDER, ASK_BUDGET, ASK_DATE, ASK_NAME = range(5)
S_UNI, S_GENDER = range(5, 7)


def L(ctx) -> dict:
    return T[ctx.user_data.get("lang", "uz")]


def menu(ctx) -> M:
    t = L(ctx)
    return M([
        [B(t["m_apply"], callback_data="apply"), B(t["m_search"], callback_data="search")],
        [B(t["m_price"], callback_data="price"), B(t["m_faq"], callback_data="faq")],
        [B(t["m_contact"], callback_data="contact"), B(t["m_lang"], callback_data="lang")],
    ])


def back_kb(ctx) -> M:
    return M([[B(L(ctx)["back"], callback_data="menu")]])


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if "lang" not in ctx.user_data:
        await update.effective_message.reply_text(
            "Tilni tanlang / Выберите язык / Choose language:",
            reply_markup=M([[B(v, callback_data=f"setlang:{k}")] for k, v in LANGS.items()]))
        return
    await update.effective_message.reply_text(L(ctx)["welcome"], reply_markup=menu(ctx))


async def myid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your chat ID: {update.effective_chat.id}")


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    if d.startswith("setlang:"):
        ctx.user_data["lang"] = d.split(":")[1]
        d = "menu"
    t = L(ctx)
    if d == "menu":
        await q.message.reply_text(t["welcome"], reply_markup=menu(ctx))
    elif d == "lang":
        await q.message.reply_text("🌐", reply_markup=M([[B(v, callback_data=f"setlang:{k}")] for k, v in LANGS.items()]))
    elif d in ("price", "faq", "contact"):
        await q.message.reply_text(t[d], parse_mode="Markdown", reply_markup=back_kb(ctx))


# ---------------------------------------------------------------- apply flow
async def apply_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ctx.user_data["app"] = {}
    await q.message.reply_text(L(ctx)["ask_uni"])
    return ASK_UNI


async def apply_uni(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["app"]["uni"] = update.message.text.strip()
    t = L(ctx)
    await update.message.reply_text(t["ask_gender"], reply_markup=M([[B(t["boy"], callback_data="g:boy"), B(t["girl"], callback_data="g:girl")]]))
    return ASK_GENDER


async def apply_gender(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ctx.user_data["app"]["gender"] = "male" if q.data == "g:boy" else "female"
    await q.message.reply_text(L(ctx)["ask_budget"])
    return ASK_BUDGET


async def apply_budget(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["app"]["budget"] = update.message.text.strip()
    await update.message.reply_text(L(ctx)["ask_date"])
    return ASK_DATE


async def apply_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["app"]["date"] = update.message.text.strip()
    await update.message.reply_text(L(ctx)["ask_name"])
    return ASK_NAME


async def apply_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    a = ctx.user_data["app"]
    a["name"] = update.message.text.strip()
    u = update.effective_user
    handle = f"@{u.username}" if u.username else f"(no username) id={u.id}"
    msg = (f"🆕 New application\n\nName: {a['name']}\nTelegram: {handle}\nUniversity: {a['uni']}\n"
           f"Gender: {a['gender']}\nBudget: {a['budget']}\nArrival: {a['date']}\nLang: {ctx.user_data.get('lang','uz')}")
    sent = 0
    for aid in ADMIN_IDS:
        try:
            await ctx.bot.send_message(aid, msg)
            sent += 1
        except Exception as e:  # admin hasn't pressed /start, etc.
            log.warning("could not notify %s: %s", aid, e)
    log.info("application from %s: %s (admins notified: %d)", handle, a, sent)
    try:  # local backup so no application is ever lost
        with open("applications.log", "a", encoding="utf-8") as f:
            f.write(msg.replace("\n", " | ") + "\n")
    except OSError:
        pass
    await update.message.reply_text(L(ctx)["done"], reply_markup=menu(ctx))
    return ConversationHandler.END


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
        name, places = find_places(ctx.user_data["s_uni"], girl)
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
    await update.effective_message.reply_text(L(ctx)["cancel"], reply_markup=menu(ctx))
    return ConversationHandler.END


def main():
    if not TOKEN:
        raise SystemExit("BOT_TOKEN is missing. Copy .env.example to .env and fill it in.")
    req = HTTPXRequest(connect_timeout=30, read_timeout=30, write_timeout=30, pool_timeout=30)
    upd = HTTPXRequest(connect_timeout=30, read_timeout=40, write_timeout=30, pool_timeout=30)
    app = Application.builder().token(TOKEN).request(req).get_updates_request(upd).build()
    text = filters.TEXT & ~filters.COMMAND
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(apply_start, pattern="^apply$")],
        states={ASK_UNI: [MessageHandler(text, apply_uni)],
                ASK_GENDER: [CallbackQueryHandler(apply_gender, pattern="^g:")],
                ASK_BUDGET: [MessageHandler(text, apply_budget)],
                ASK_DATE: [MessageHandler(text, apply_date)],
                ASK_NAME: [MessageHandler(text, apply_name)]},
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", cancel)], allow_reentry=True))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(search_start, pattern="^search$")],
        states={S_UNI: [MessageHandler(text, search_uni)],
                S_GENDER: [CallbackQueryHandler(search_gender, pattern="^sg:")]},
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", cancel)], allow_reentry=True))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CallbackQueryHandler(on_button))
    log.info("Bot started")
    base = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if base:  # running on Render: webhook mode (wakes up when a message arrives)
        app.run_webhook(listen="0.0.0.0", port=int(os.getenv("PORT", "10000")),
                        url_path=TOKEN, webhook_url=f"{base}/{TOKEN}")
    else:  # running on your computer: polling mode
        app.run_polling(bootstrap_retries=5)


if __name__ == "__main__":
    main()
