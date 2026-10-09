"""Schema v1 taxonomy (docs/PROJE_PLANI.md section 4) as data, plus an idempotent loader.

Ids are stable ASCII slugs and never change; names/definitions are the Turkish texts of the plan.
Run against the development database:

    uv run python -m turotel.data.taxonomy
"""

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from turotel.db.models import (
    Action,
    CauseAction,
    CauseFactor,
    Department,
    MainCategory,
    SchemaVersion,
    Subcategory,
    SubcategoryDepartment,
)

VERSION = 1
VERSION_NOTE = "v1: 9 ana / 29 alt kategori, 11 departman, 13 neden faktörü, 13 aksiyon"

# (id, name)
MAIN_CATEGORIES: list[tuple[str, str]] = [
    ("general_experience", "Genel otel deneyimi"),
    ("room_bath", "Oda ve banyo"),
    ("food_beverage", "Yiyecek-içecek"),
    ("service_staff", "Hizmet ve personel"),
    ("reservation_frontdesk", "Rezervasyon ve ön büro"),
    ("facilities_activities", "Tesis ve aktiviteler"),
    ("location_access", "Konum ve ulaşım"),
    ("price_value", "Fiyat ve değer"),
    ("safety", "Güvenlik"),
]

# (id, main_category_id, name, definition)
SUBCATEGORIES: list[tuple[str, str, str, str]] = [
    ("general_satisfaction", "general_experience", "genel memnuniyet",
     "Konu belirtmeden genel olarak memnun ya da memnun olmama ifadesi."),
    ("hotel_quality_expectation", "general_experience", "otel kalitesi/beklentiyi karşılama",
     "Otelin genel kalitesi ve beklentiyi (fotoğraf, yıldız, vaat) karşılayıp karşılamadığı."),
    ("atmosphere_design_noise", "general_experience", "atmosfer-tasarım-gürültü",
     "Otelin havası, mimari/dekorasyon tasarımı ve gürültü düzeyi."),
    ("room_general_size", "room_bath", "oda geneli/büyüklük",
     "Odanın genel durumu, büyüklüğü ve yerleşimi."),
    ("bed_comfort_climate", "room_bath", "yatak-konfor-iklim",
     "Yatak ve yastık konforu, odanın ısı/klima konforu."),
    ("room_cleanliness", "room_bath", "oda temizliği",
     "Odanın temizliği, tekstil ve yatak takımları, günlük oda hazırlığı."),
    ("bathroom_water", "room_bath", "banyo/su",
     "Banyonun durumu ve temizliği, sıcak/soğuk su, basınç, duş."),
    ("room_equipment_maintenance", "room_bath", "oda ekipmanı-bakım-arıza",
     "Oda içi cihaz ve donanım (TV, minibar, kilit, klima cihazı) durumu, bakım ve arızalar."),
    ("food_quality_taste", "food_beverage", "kalite/lezzet",
     "Yemek ve içeceklerin kalitesi, tazeliği ve lezzeti."),
    ("food_variety_choice", "food_beverage", "çeşit/seçenek",
     "Menü çeşitliliği, özel diyet ve çocuk seçenekleri."),
    ("food_service_presentation", "food_beverage", "servis-sunum",
     "Yemek servisi, sunum ve restoran/bar düzeni."),
    ("food_price", "food_beverage", "fiyat",
     "Yiyecek-içecek fiyatları ve paket kapsamındaki değeri."),
    ("staff_attitude", "service_staff", "tutum/nezaket",
     "Personelin davranışı, nezaketi ve misafire yaklaşımı."),
    ("staff_competence", "service_staff", "yetkinlik/sorun çözme",
     "Personelin bilgi ve becerisi, sorunu çözebilmesi."),
    ("staff_speed_waiting", "service_staff", "hız-bekleme",
     "Hizmet hızı, bekleme ve kuyruk süreleri."),
    ("staff_communication", "service_staff", "iletişim/bilgilendirme",
     "Personelin bilgilendirmesi, dil ve iletişim yeterliliği."),
    ("reservation_accuracy", "reservation_frontdesk", "rezervasyon doğruluğu",
     "Yapılan rezervasyonun (oda tipi, tarih, paket) doğru karşılanması."),
    ("checkin_checkout_room_ready", "reservation_frontdesk", "check-in/out ve oda hazırlığı",
     "Giriş/çıkış işlemleri, oda hazır olma durumu ve süreleri."),
    ("payment_invoice_cancel", "reservation_frontdesk", "ödeme-fatura-iptal",
     "Ödeme, fatura, iptal ve iade süreçleri."),
    ("pool_beach", "facilities_activities", "havuz-plaj",
     "Havuz ve plajın durumu, temizliği, şezlong ve kapasitesi."),
    ("spa_sports", "facilities_activities", "spa-spor",
     "Spa, hamam, sauna, masaj ve spor olanakları."),
    ("animation_family_kids", "facilities_activities", "animasyon-aile/çocuk",
     "Animasyon, şovlar, mini club ve aile/çocuk etkinlikleri."),
    ("wifi_technology", "facilities_activities", "Wi-Fi/teknoloji",
     "Wi-Fi ve diğer teknolojik olanakların varlığı ve kalitesi."),
    ("common_area_parking_upkeep", "facilities_activities", "ortak alan-otopark-bakım",
     "Ortak alanlar, otopark ve genel tesis bakım durumu."),
    ("access_transport", "location_access", "erişim/ulaşım",
     "Otele ulaşım, transfer ve çevreye erişim kolaylığı."),
    ("surroundings_view_proximity", "location_access", "çevre/manzara/yakınlık",
     "Çevre, manzara ve plaj/merkez gibi yerlere yakınlık."),
    ("overall_price_performance", "price_value", "genel fiyat-performans",
     "Ödenen paraya karşılık alınan değerin genel değerlendirmesi."),
    ("extra_fees_price_transparency", "price_value", "ek ücret/fiyat şeffaflığı",
     "Sonradan çıkan ücretler, gizli maliyetler ve fiyat açıklığı."),
    ("safety_security", "safety", "kişi/eşya/tesis güvenliği",
     "Kişi, eşya ve tesis güvenliği; güvenlik önlemleri ve olay müdahalesi."),
]

# (id, name, definition = scope rule of section 4.2)
DEPARTMENTS: list[tuple[str, str, str]] = [
    ("front_office", "Ön büro / misafir ilişkileri",
     "Resepsiyon, check-in/out, concierge, misafir iletişimi; şikâyetin iletildiği yer değil, hatayı üreten birim esas."),
    ("housekeeping", "Kat hizmetleri",
     "Oda/ortak alan temizliği, tekstil, buklet, oda hazırlığı; cihaz arızası teknikte."),
    ("food_beverage", "Yiyecek-içecek",
     "Mutfak, restoran, bar, oda servisi; garson/bekleme burada; gizli ücret ticari işlemlerde."),
    ("technical", "Teknik servis / BT",
     "Klima, elektrik, su, asansör, Wi-Fi, cihaz ve yapı bakımı."),
    ("animation", "Animasyon / çocuk aktiviteleri",
     "Şovlar, eğlence, mini club; spor alanının fiziksel durumu rekreasyonda."),
    ("spa_wellness", "Spa & wellness", "Spa, hamam, sauna, masaj."),
    ("pool_beach_recreation", "Havuz-plaj-rekreasyon",
     "Havuz, plaj, şezlong, su sporları; pompa/ısıtma arızası teknikte."),
    ("security", "Güvenlik",
     "Kişi, eşya, erişim, olay müdahalesi; bozuk kasa cihazı teknikte."),
    ("reservations_commercial", "Rezervasyon ve ticari işlemler",
     "Rezervasyon doğruluğu, fiyat koşulu, iptal, iade, ödeme, fatura."),
    ("general_management", "Genel yönetim",
     "Yalnızca politika, konsept veya birden çok birimi açıkça kapsayan şikâyetler."),
    ("unclear", "Belirsiz / kanıt yetersiz",
     "Şikâyet var ama sorumlu birim anlaşılamıyor; sadece \"kötüydü\" diyen yorum buraya."),
]

# (id, factor_group, name, definition = typical cue). "Kanıt yetersiz" is a status code, not a factor.
CAUSE_FACTORS: list[tuple[str, str, str, str]] = [
    ("staff_capacity", "İnsan", "personel kapasitesi", "Tipik ipucu: \"tek garson vardı\""),
    ("service_execution", "İnsan", "hizmet icrası / yetkinlik", "Tipik ipucu: \"sorunu çözemedi\""),
    ("planning_coordination", "Süreç", "planlama / koordinasyon", "Tipik ipucu: \"üç birim birbirine yönlendirdi\""),
    ("standards_oversight", "Süreç", "standart / denetim zafiyeti", "Tipik ipucu: \"her gün havlu unutuldu\""),
    ("demand_capacity_mismatch", "Kapasite", "talep / kapasite uyumsuzluğu",
     "Tipik ipucu: \"şezlong yetmedi\", \"uzun kuyruk\""),
    ("supply_stock", "Malzeme", "tedarik / stok", "Tipik ipucu: \"içecekler bitti\""),
    ("maintenance_fault", "Teknik", "bakım / arıza", "Tipik ipucu: \"klima bozuktu\""),
    ("design_capacity_limit", "Fiziksel", "tasarım / kapasite kısıtı",
     "Tipik ipucu: \"banyo çok dar\", \"tek asansör\""),
    ("wear_renewal", "Fiziksel", "yıpranma / yenileme ihtiyacı", "Tipik ipucu: \"her yer eski\""),
    ("communication_gap", "İletişim", "bilgilendirme kopukluğu", "Tipik ipucu: \"kimse açıklamadı\""),
    ("policy_promise_mismatch", "Ticari", "politika / vaat uyumsuzluğu",
     "Tipik ipucu: \"fotoğraftaki havuz kapalıydı\""),
    ("external_third_party", "Çevre", "dış etken / üçüncü taraf",
     "Tipik ipucu: hava, belediye altyapısı, acente hatası"),
    ("product_expectation_mismatch", "Uyum", "ürün / beklenti uyuşmazlığı",
     "Tipik ipucu: \"çocuk oteli bana uygun değilmiş\""),
]

# (id, name)
ACTIONS: list[tuple[str, str]] = [
    ("workforce_adjustment", "İş gücü / kaynak ayarlaması"),
    ("training_coaching", "Eğitim, koçluk ve performans takibi"),
    ("shift_workload_planning", "Vardiya ve iş yükü planlama"),
    ("procedure_checklist_audit", "Prosedür, checklist ve denetim revizyonu"),
    ("demand_capacity_control", "Talep ve kapasite kontrolü"),
    ("stock_procurement_supplier", "Stok, satın alma ve tedarikçi yönetimi"),
    ("repair_planned_maintenance", "Arıza giderme ve planlı bakım"),
    ("renewal_equipment_replacement", "Yenileme ve ekipman değişimi"),
    ("physical_layout_capacity_investment", "Fiziksel düzen / kapasite yatırımı"),
    ("guest_information_expectation", "Misafir bilgilendirme ve beklenti yönetimi"),
    ("policy_promise_content_revision", "Politika, vaat ve içerik revizyonu"),
    ("price_value_package_review", "Fiyat–değer / paket gözden geçirme"),
    ("third_party_backup_plan", "Üçüncü taraf yönetimi ve yedek plan"),
]

# Guidance only (not a rule): subcategory -> possible departments, most likely first.
# Drafted from the scope rules of section 4.2 and cross-checked with GPT-6 Astra on 2026-10-07.
SUBCATEGORY_DEPARTMENTS: dict[str, list[str]] = {
    "general_satisfaction": ["unclear", "general_management"],
    "hotel_quality_expectation": ["unclear", "general_management"],
    "atmosphere_design_noise": ["animation", "technical", "general_management"],
    "room_general_size": ["general_management", "unclear", "housekeeping"],
    "bed_comfort_climate": ["housekeeping", "technical"],
    "room_cleanliness": ["housekeeping"],
    "bathroom_water": ["housekeeping", "technical"],
    "room_equipment_maintenance": ["technical", "housekeeping"],
    "food_quality_taste": ["food_beverage"],
    "food_variety_choice": ["food_beverage"],
    "food_service_presentation": ["food_beverage"],
    "food_price": ["food_beverage", "reservations_commercial"],
    "staff_attitude": ["front_office", "food_beverage", "housekeeping"],
    "staff_competence": ["front_office", "technical", "food_beverage"],
    "staff_speed_waiting": ["food_beverage", "front_office"],
    "staff_communication": ["front_office"],
    "reservation_accuracy": ["reservations_commercial"],
    "checkin_checkout_room_ready": ["front_office", "housekeeping"],
    "payment_invoice_cancel": ["reservations_commercial"],
    "pool_beach": ["pool_beach_recreation", "technical"],
    "spa_sports": ["spa_wellness", "pool_beach_recreation", "animation"],
    "animation_family_kids": ["animation"],
    "wifi_technology": ["technical"],
    "common_area_parking_upkeep": ["housekeeping", "technical", "security"],
    "access_transport": ["front_office", "unclear", "general_management"],
    "surroundings_view_proximity": ["unclear", "general_management"],
    "overall_price_performance": ["reservations_commercial", "unclear", "general_management"],
    "extra_fees_price_transparency": ["reservations_commercial", "food_beverage"],
    "safety_security": ["security", "technical"],
}

# action id -> typical cause factors (the "Tipik neden faktörleri" column of section 4.2)
ACTION_CAUSES: dict[str, list[str]] = {
    "workforce_adjustment": ["staff_capacity", "demand_capacity_mismatch"],
    "training_coaching": ["service_execution"],
    "shift_workload_planning": ["planning_coordination", "staff_capacity"],
    "procedure_checklist_audit": ["standards_oversight", "planning_coordination"],
    "demand_capacity_control": ["demand_capacity_mismatch"],
    "stock_procurement_supplier": ["supply_stock", "external_third_party"],
    "repair_planned_maintenance": ["maintenance_fault", "wear_renewal"],
    "renewal_equipment_replacement": ["wear_renewal"],
    "physical_layout_capacity_investment": ["design_capacity_limit"],
    "guest_information_expectation": ["communication_gap", "product_expectation_mismatch"],
    "policy_promise_content_revision": ["policy_promise_mismatch", "product_expectation_mismatch"],
    "price_value_package_review": ["policy_promise_mismatch", "product_expectation_mismatch"],
    "third_party_backup_plan": ["external_third_party", "supply_stock"],
}


@dataclass(frozen=True)
class LoadResult:
    """Rows newly inserted per table; all zeros means the version was already loaded."""

    inserted: dict[str, int]

    @property
    def changed(self) -> bool:
        return any(self.inserted.values())


def _insert_missing(session: Session, model, rows: list[dict], key: list[str]) -> int:
    """Insert rows whose primary key is absent; existing rows are never touched."""
    stmt = (
        insert(model)
        .values(rows)
        .on_conflict_do_nothing(index_elements=key)
        .returning(*(getattr(model, k) for k in key))
    )
    return len(session.execute(stmt).all())


def load_taxonomy(session: Session) -> LoadResult:
    """Load schema v1. Safe to run repeatedly; the caller commits."""
    inserted: dict[str, int] = {}
    version_stmt = (
        insert(SchemaVersion)
        .values(version=VERSION, frozen_at=func.now(), note=VERSION_NOTE)
        .on_conflict_do_nothing(index_elements=["version"])
        .returning(SchemaVersion.version)
    )
    inserted["schema_versions"] = len(session.execute(version_stmt).all())

    def base(**extra) -> dict:
        return {"introduced_in": VERSION, "retired_in": None, **extra}

    inserted["main_categories"] = _insert_missing(
        session, MainCategory, [base(id=i, name=n) for i, n in MAIN_CATEGORIES], ["id"]
    )
    inserted["subcategories"] = _insert_missing(
        session,
        Subcategory,
        [base(id=i, main_category_id=m, name=n, definition=d) for i, m, n, d in SUBCATEGORIES],
        ["id"],
    )
    inserted["departments"] = _insert_missing(
        session, Department, [base(id=i, name=n, definition=d) for i, n, d in DEPARTMENTS], ["id"]
    )
    inserted["cause_factors"] = _insert_missing(
        session,
        CauseFactor,
        [base(id=i, factor_group=g, name=n, definition=d) for i, g, n, d in CAUSE_FACTORS],
        ["id"],
    )
    inserted["actions"] = _insert_missing(session, Action, [base(id=i, name=n) for i, n in ACTIONS], ["id"])
    inserted["subcategory_departments"] = _insert_missing(
        session,
        SubcategoryDepartment,
        [base(subcategory_id=s, department_id=d) for s, deps in SUBCATEGORY_DEPARTMENTS.items() for d in deps],
        ["subcategory_id", "department_id"],
    )
    inserted["cause_actions"] = _insert_missing(
        session,
        CauseAction,
        [base(cause_factor_id=c, action_id=a) for a, causes in ACTION_CAUSES.items() for c in causes],
        ["cause_factor_id", "action_id"],
    )
    return LoadResult(inserted)


def main() -> int:
    from turotel.db.session import make_session_factory

    with make_session_factory()() as session:
        result = load_taxonomy(session)
        session.commit()
    print("inserted:", result.inserted if result.changed else "nothing (already loaded)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
