# -*- coding: utf-8 -*-
"""
数据库初始化脚本（支持 MySQL 和 SQLite）

- 默认使用 SQLite（文件：backend/herb_management.db）
- 设置环境变量 USE_MYSQL=1 时使用 MySQL

用法：python init_db.py
"""
import hashlib
import os
import time

from db import is_mysql, execute, query, SQLITE_DB_PATH

DB_NAME = "herb_management_system"


# ============ SQLite 建表语句 ============
SQLITE_TABLES = [
    """CREATE TABLE IF NOT EXISTS users (
        username TEXT NOT NULL PRIMARY KEY,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'patient',
        name TEXT NOT NULL,
        phone TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        department TEXT,
        license TEXT,
        gender TEXT,
        age INTEGER,
        idcard TEXT,
        create_time TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS herbs (
        code TEXT NOT NULL PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT,
        origin TEXT,
        storage TEXT,
        unit TEXT,
        price REAL DEFAULT 0,
        quantity INTEGER DEFAULT 0,
        warning_threshold INTEGER DEFAULT 200,
        description TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        updated_at TEXT DEFAULT (datetime('now','localtime'))
    )""",
    """CREATE TABLE IF NOT EXISTS operation_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        herb_code TEXT,
        herb_name TEXT,
        action TEXT NOT NULL,
        changes TEXT,
        operator TEXT,
        operator_name TEXT,
        timestamp INTEGER,
        time_str TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS prescriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prescription_no TEXT NOT NULL UNIQUE,
        patient_name TEXT NOT NULL,
        patient_phone TEXT,
        patient_gender TEXT,
        patient_age INTEGER,
        doctor_username TEXT,
        doctor_name TEXT,
        department TEXT,
        diagnosis TEXT,
        advice TEXT,
        total_amount REAL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'pending',
        audit_remark TEXT,
        auditor TEXT,
        auditor_name TEXT,
        audit_time TEXT,
        dispenser TEXT,
        dispenser_name TEXT,
        dispense_time TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        updated_at TEXT DEFAULT (datetime('now','localtime'))
    )""",
    """CREATE TABLE IF NOT EXISTS prescription_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prescription_id INTEGER NOT NULL,
        herb_code TEXT,
        herb_name TEXT NOT NULL,
        dosage TEXT,
        usage TEXT,
        quantity INTEGER DEFAULT 1,
        price REAL DEFAULT 0,
        subtotal REAL DEFAULT 0
    )""",
    "CREATE INDEX IF NOT EXISTS idx_rx_status ON prescriptions(status)",
    "CREATE INDEX IF NOT EXISTS idx_rx_doctor ON prescriptions(doctor_username)",
    "CREATE INDEX IF NOT EXISTS idx_rx_patient ON prescriptions(patient_name)",
    "CREATE INDEX IF NOT EXISTS idx_item_rx ON prescription_items(prescription_id)",
    # 供应商表
    """CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        contact_person TEXT,
        phone TEXT,
        address TEXT,
        description TEXT,
        status TEXT DEFAULT 'active',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""",
    # 采购单表
    """CREATE TABLE IF NOT EXISTS purchase_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_no TEXT NOT NULL UNIQUE,
        supplier_id INTEGER,
        supplier_name TEXT,
        total_amount REAL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'pending',
        remark TEXT,
        creator TEXT,
        creator_name TEXT,
        auditor TEXT,
        auditor_name TEXT,
        audit_time TEXT,
        in_stock_time TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        updated_at TEXT DEFAULT (datetime('now','localtime'))
    )""",
    # 采购明细表
    """CREATE TABLE IF NOT EXISTS purchase_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        purchase_id INTEGER NOT NULL,
        herb_code TEXT,
        herb_name TEXT NOT NULL,
        quantity INTEGER DEFAULT 0,
        unit TEXT,
        price REAL DEFAULT 0,
        subtotal REAL DEFAULT 0,
        received_quantity INTEGER DEFAULT 0
    )""",
    # 库存流水表
    """CREATE TABLE IF NOT EXISTS stock_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        herb_code TEXT NOT NULL,
        herb_name TEXT NOT NULL,
        type TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        balance_after INTEGER,
        reference_type TEXT,
        reference_id TEXT,
        remark TEXT,
        operator TEXT,
        operator_name TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""",
    "CREATE INDEX IF NOT EXISTS idx_po_status ON purchase_orders(status)",
    "CREATE INDEX IF NOT EXISTS idx_pi_purchase ON purchase_items(purchase_id)",
    "CREATE INDEX IF NOT EXISTS idx_st_herb ON stock_transactions(herb_code)",
    "CREATE INDEX IF NOT EXISTS idx_st_type ON stock_transactions(type)",
    # 药材知识库表
    """CREATE TABLE IF NOT EXISTS herb_knowledge (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        herb_code TEXT,
        herb_name TEXT NOT NULL,
        category TEXT,
        nature TEXT,
        flavor TEXT,
        meridian TEXT,
        effects TEXT,
        indications TEXT,
        dosage TEXT,
        usage TEXT,
        contraindications TEXT,
        compatibility TEXT,
        storage TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""",
    # 方剂库表
    """CREATE TABLE IF NOT EXISTS formulas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT,
        source TEXT,
        composition TEXT,
        effects TEXT,
        indications TEXT,
        usage TEXT,
        contraindications TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""",
    # 对话历史表
    """CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        role TEXT,
        user_message TEXT,
        assistant_reply TEXT,
        intent TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""",
    "CREATE INDEX IF NOT EXISTS idx_hk_name ON herb_knowledge(herb_name)",
    "CREATE INDEX IF NOT EXISTS idx_formula_name ON formulas(name)",
    "CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_history(username)",
]


# ============ 默认数据 ============
DEFAULT_USERS = [
    {"username": "admin", "password": "123456", "role": "admin", "name": "系统管理员",
     "phone": "13800138000", "status": "active", "department": None, "license": None,
     "gender": None, "age": None, "idcard": None, "create_time": "2026/9/1 00:00:00"},
    {"username": "doctor", "password": "123456", "role": "doctor", "name": "李医生",
     "phone": "13900139000", "status": "active", "department": "中医内科",
     "license": "110101202600001", "gender": None, "age": None, "idcard": None,
     "create_time": "2026/9/1 00:00:00"},
    {"username": "doctor2", "password": "123456", "role": "doctor", "name": "张医生",
     "phone": "13900139001", "status": "active", "department": "中医妇科",
     "license": "110101202600002", "gender": None, "age": None, "idcard": None,
     "create_time": "2026/9/1 00:00:00"},
    {"username": "patient", "password": "123456", "role": "patient", "name": "王病人",
     "phone": "13700137000", "status": "active", "department": None, "license": None,
     "gender": "男", "age": 35, "idcard": "340104199101011234", "create_time": "2026/9/1 00:00:00"},
]

SAMPLE_HERBS = [
    {"code": "HC001", "name": "黄芪", "category": "补气药", "origin": "内蒙古", "storage": "通风干燥",
     "unit": "g", "price": 0.15, "quantity": 5000, "warning_threshold": 500, "description": "补气升阳，固表止汗"},
    {"code": "HC002", "name": "当归", "category": "补血药", "origin": "甘肃", "storage": "阴凉干燥",
     "unit": "g", "price": 0.25, "quantity": 3000, "warning_threshold": 300, "description": "补血活血，调经止痛"},
    {"code": "HC003", "name": "白术", "category": "补气药", "origin": "浙江", "storage": "通风干燥",
     "unit": "g", "price": 0.18, "quantity": 2500, "warning_threshold": 300, "description": "健脾益气，燥湿利水"},
    {"code": "HC004", "name": "茯苓", "category": "利水渗湿药", "origin": "云南", "storage": "通风干燥",
     "unit": "g", "price": 0.12, "quantity": 4000, "warning_threshold": 400, "description": "利水渗湿，健脾宁心"},
    {"code": "HC005", "name": "甘草", "category": "补气药", "origin": "新疆", "storage": "通风干燥",
     "unit": "g", "price": 0.08, "quantity": 6000, "warning_threshold": 500, "description": "补脾益气，清热解毒，调和诸药"},
    {"code": "HC006", "name": "川芎", "category": "活血化瘀药", "origin": "四川", "storage": "阴凉干燥",
     "unit": "g", "price": 0.20, "quantity": 1800, "warning_threshold": 200, "description": "活血行气，祛风止痛"},
    {"code": "HC007", "name": "白芍", "category": "补血药", "origin": "安徽", "storage": "通风干燥",
     "unit": "g", "price": 0.16, "quantity": 2200, "warning_threshold": 250, "description": "养血调经，敛阴止汗"},
    {"code": "HC008", "name": "柴胡", "category": "解表药", "origin": "河北", "storage": "通风干燥",
     "unit": "g", "price": 0.22, "quantity": 1500, "warning_threshold": 200, "description": "和解表里，疏肝升阳"},
    {"code": "HC009", "name": "黄芩", "category": "清热药", "origin": "山西", "storage": "通风干燥",
     "unit": "g", "price": 0.19, "quantity": 1600, "warning_threshold": 200, "description": "清热燥湿，泻火解毒"},
    {"code": "HC010", "name": "党参", "category": "补气药", "origin": "山西", "storage": "通风干燥",
     "unit": "g", "price": 0.30, "quantity": 800, "warning_threshold": 150, "description": "补中益气，健脾益肺"},
]

SAMPLE_SUPPLIERS = [
    {"name": "安徽亳州中药材批发市场", "contact_person": "王经理", "phone": "13800001111",
     "address": "安徽省亳州市中药材交易中心", "description": "华东地区最大中药材批发市场，品种齐全", "status": "active"},
    {"name": "河北安国中药材市场", "contact_person": "李经理", "phone": "13800002222",
     "address": "河北省安国市药城大街", "description": "北方中药材集散地，价格优惠", "status": "active"},
    {"name": "云南三七特产直销", "contact_person": "张经理", "phone": "13800003333",
     "address": "云南省文山州三七交易市场", "description": "云南道地药材直销，三七、天麻等", "status": "active"},
]

SAMPLE_PURCHASE_ORDERS = [
    {
        "order_no": "PO20260901001", "supplier_id": 1, "supplier_name": "安徽亳州中药材批发市场",
        "status": "completed", "remark": "月度常规采购", "creator": "admin", "creator_name": "系统管理员",
        "auditor": "admin", "auditor_name": "系统管理员", "audit_time": "2026/09/01 09:00:00",
        "in_stock_time": "2026/09/02 14:00:00",
        "items": [
            {"herb_code": "HC001", "herb_name": "黄芪", "quantity": 2000, "unit": "g", "price": 0.12},
            {"herb_code": "HC002", "herb_name": "当归", "quantity": 1500, "unit": "g", "price": 0.20},
            {"herb_code": "HC005", "herb_name": "甘草", "quantity": 3000, "unit": "g", "price": 0.06},
        ],
    },
    {
        "order_no": "PO20260905001", "supplier_id": 2, "supplier_name": "河北安国中药材市场",
        "status": "approved", "remark": "补充库存", "creator": "admin", "creator_name": "系统管理员",
        "auditor": "admin", "auditor_name": "系统管理员", "audit_time": "2026/09/05 10:00:00",
        "items": [
            {"herb_code": "HC003", "herb_name": "白术", "quantity": 1000, "unit": "g", "price": 0.15},
            {"herb_code": "HC004", "herb_name": "茯苓", "quantity": 1500, "unit": "g", "price": 0.10},
        ],
    },
    {
        "order_no": "PO20260910001", "supplier_id": 1, "supplier_name": "安徽亳州中药材批发市场",
        "status": "pending", "remark": "待审核采购单", "creator": "admin", "creator_name": "系统管理员",
        "items": [
            {"herb_code": "HC010", "herb_name": "党参", "quantity": 500, "unit": "g", "price": 0.25},
            {"herb_code": "HC008", "herb_name": "柴胡", "quantity": 800, "unit": "g", "price": 0.18},
        ],
    },
]

SAMPLE_HERB_KNOWLEDGE = [
    {"herb_code": "HC001", "herb_name": "黄芪", "category": "补气药", "nature": "微温", "flavor": "甘",
     "meridian": "脾、肺经", "effects": "补气升阳，固表止汗，利水消肿，生津养血，行滞通痹，托毒排脓，敛疮生肌",
     "indications": "用于气虚乏力，食少便溏，中气下陷，久泻脱肛，便血崩漏，表虚自汗，气虚水肿，内热消渴，血虚萎黄，半身不遂，痹痛麻木，痈疽难溃，久溃不敛",
     "dosage": "9-30g", "usage": "水煎服。蜜炙可增强温补作用",
     "contraindications": "表实邪盛，气滞湿阻，食积停滞，痈疽初起或溃后热毒尚盛等实证，以及阴虚阳亢者，均须禁服",
     "compatibility": "配党参、白术：补气健脾；配当归：补气生血（当归补血汤）；配白术、防风：固表止汗（玉屏风散）"},
    {"herb_code": "HC002", "herb_name": "当归", "category": "补血药", "nature": "温", "flavor": "甘、辛",
     "meridian": "肝、心、脾经", "effects": "补血活血，调经止痛，润肠通便",
     "indications": "用于血虚萎黄，眩晕心悸，月经不调，经闭痛经，虚寒腹痛，风湿痹痛，跌扑损伤，痈疽疮疡，肠燥便秘。酒当归活血通经，用于经闭痛经，风湿痹痛，跌扑损伤",
     "dosage": "6-12g", "usage": "水煎服。生用补血，酒炒活血，炒炭止血",
     "contraindications": "湿盛中满、大便泄泻者忌服",
     "compatibility": "配黄芪：补气生血（当归补血汤）；配川芎、白芍、熟地：养血调经（四物汤）；配桂枝、生姜：温经散寒（当归四逆汤）"},
    {"herb_code": "HC003", "herb_name": "白术", "category": "补气药", "nature": "温", "flavor": "苦、甘",
     "meridian": "脾、胃经", "effects": "健脾益气，燥湿利水，止汗，安胎",
     "indications": "用于脾虚食少，腹胀泄泻，痰饮眩悸，水肿，自汗，胎动不安。土白术健脾，和胃，安胎。用于脾虚食少，泄泻便溏，胎动不安",
     "dosage": "6-12g", "usage": "水煎服。炒用可增强健脾止泻作用",
     "contraindications": "阴虚内热、津液亏耗者不宜使用",
     "compatibility": "配党参、茯苓、甘草：补气健脾（四君子汤）；配茯苓、桂枝：温阳利水（五苓散）；配黄芪、防风：固表止汗（玉屏风散）"},
    {"herb_code": "HC004", "herb_name": "茯苓", "category": "利水渗湿药", "nature": "平", "flavor": "甘、淡",
     "meridian": "心、肺、脾、肾经", "effects": "利水渗湿，健脾，宁心",
     "indications": "用于水肿尿少，痰饮眩悸，脾虚食少，便溏泄泻，心神不安，惊悸失眠",
     "dosage": "10-15g", "usage": "水煎服",
     "contraindications": "虚寒滑精、气虚下陷者慎服",
     "compatibility": "配猪苓、泽泻、白术：利水渗湿（五苓散）；配党参、白术、甘草：健脾益气（四君子汤）；配酸枣仁、远志：宁心安神"},
    {"herb_code": "HC005", "herb_name": "甘草", "category": "补气药", "nature": "平", "flavor": "甘",
     "meridian": "心、肺、脾、胃经", "effects": "补脾益气，清热解毒，祛痰止咳，缓急止痛，调和诸药",
     "indications": "用于脾胃虚弱，倦怠乏力，心悸气短，咳嗽痰多，脘腹、四肢挛急疼痛，痈肿疮毒，缓解药物毒性、烈性",
     "dosage": "2-10g", "usage": "水煎服。生用清热解毒，蜜炙补脾益气",
     "contraindications": "不宜与海藻、京大戟、红大戟、甘遂、芫花同用。湿盛胀满、水肿者不宜用。大剂量久服可导致水钠潴留，引起浮肿",
     "compatibility": "配党参、白术、茯苓：补气健脾（四君子汤）；配桂枝、芍药、生姜：温中补虚（小建中汤）；配桔梗：宣肺祛痰（桔梗汤）"},
    {"herb_code": "HC006", "herb_name": "川芎", "category": "活血化瘀药", "nature": "温", "flavor": "辛",
     "meridian": "肝、胆、心包经", "effects": "活血行气，祛风止痛",
     "indications": "用于胸痹心痛，胸胁刺痛，跌扑肿痛，月经不调，经闭痛经，癥瘕腹痛，头痛，风湿痹痛",
     "dosage": "3-10g", "usage": "水煎服",
     "contraindications": "阴虚火旺，上盛下虚及气弱之人忌服。月经过多、孕妇及出血性疾病慎用",
     "compatibility": "配当归、白芍、熟地：养血活血（四物汤）；配柴胡、香附：疏肝理气，活血止痛；配白芷：祛风止痛（川芎茶调散）"},
    {"herb_code": "HC007", "herb_name": "白芍", "category": "补血药", "nature": "微寒", "flavor": "苦、酸",
     "meridian": "肝、脾经", "effects": "养血调经，敛阴止汗，柔肝止痛，平抑肝阳",
     "indications": "用于血虚萎黄，月经不调，自汗，盗汗，胁痛，腹痛，四肢挛痛，头痛眩晕",
     "dosage": "6-15g", "usage": "水煎服。炒用可减弱寒性，增强养血作用",
     "contraindications": "不宜与藜芦同用。虚寒腹痛泄泻者慎服",
     "compatibility": "配当归、川芎、熟地：养血调经（四物汤）；配甘草：缓急止痛（芍药甘草汤）；配柴胡、当归：疏肝养血（逍遥散）"},
    {"herb_code": "HC008", "herb_name": "柴胡", "category": "解表药", "nature": "微寒", "flavor": "辛、苦",
     "meridian": "肝、胆经", "effects": "疏散退热，疏肝解郁，升举阳气",
     "indications": "用于感冒发热，寒热往来，胸胁胀痛，月经不调，子宫脱垂，脱肛",
     "dosage": "3-10g", "usage": "水煎服。生用解表退热，醋炙疏肝解郁，酒炙升举阳气",
     "contraindications": "肝阳上亢，肝风内动，阴虚火旺及气机上逆者忌用或慎用",
     "compatibility": "配黄芩：和解少阳（小柴胡汤）；配白芍、当归：疏肝养血（逍遥散）；配升麻、黄芪：升阳举陷（补中益气汤）"},
    {"herb_code": "HC009", "herb_name": "黄芩", "category": "清热药", "nature": "寒", "flavor": "苦",
     "meridian": "肺、胆、脾、大肠、小肠经", "effects": "清热燥湿，泻火解毒，止血，安胎",
     "indications": "用于湿温、暑湿，胸闷呕恶，湿热痞满，泻痢，黄疸，肺热咳嗽，高热烦渴，血热吐衄，痈肿疮毒，胎动不安",
     "dosage": "3-10g", "usage": "水煎服。生用清热，炒用安胎，酒炒清上焦热，炒炭止血",
     "contraindications": "脾胃虚寒，无湿热实火者忌服",
     "compatibility": "配柴胡：和解少阳（小柴胡汤）；配黄连、黄柏：泻火解毒（黄连解毒汤）；配白术：清热安胎"},
    {"herb_code": "HC010", "herb_name": "党参", "category": "补气药", "nature": "平", "flavor": "甘",
     "meridian": "脾、肺经", "effects": "健脾益肺，养血生津",
     "indications": "用于脾肺气虚，食少倦怠，咳嗽虚喘，气血不足，面色萎黄，心悸气短，津伤口渴，内热消渴",
     "dosage": "9-30g", "usage": "水煎服",
     "contraindications": "不宜与藜芦同用。实证、热证而正气不虚者不宜使用",
     "compatibility": "配白术、茯苓、甘草：补气健脾（四君子汤）；配黄芪：补气益肺；配当归、熟地：益气养血"},
]

SAMPLE_FORMULAS = [
    {"name": "四君子汤", "category": "补益剂", "source": "《太平惠民和剂局方》",
     "composition": "党参9g、白术9g、茯苓9g、炙甘草6g",
     "effects": "益气健脾",
     "indications": "脾胃气虚证。面色萎白，语声低微，气短乏力，食少便溏，舌淡苔白，脉虚弱",
     "usage": "水煎服，每日一剂，分两次温服",
     "contraindications": "阴虚内热者慎用"},
    {"name": "四物汤", "category": "补益剂", "source": "《仙授理伤续断秘方》",
     "composition": "当归9g、川芎6g、白芍9g、熟地黄12g",
     "effects": "补血调血",
     "indications": "营血虚滞证。心悸失眠，头晕目眩，面色无华，妇人月经不调，量少或经闭不行，脐腹作痛，舌淡，脉细弦或细涩",
     "usage": "水煎服，每日一剂",
     "contraindications": "阴虚发热，血崩气脱之证不宜使用"},
    {"name": "当归补血汤", "category": "补益剂", "source": "《内外伤辨惑论》",
     "composition": "黄芪30g、当归6g",
     "effects": "补气生血",
     "indications": "血虚阳浮发热证。肌热面红，烦渴欲饮，脉洪大而虚，重按无力。亦治妇人经期、产后血虚发热头痛；或疮疡溃后，久不愈合者",
     "usage": "水煎服，每日一剂",
     "contraindications": "阴虚潮热者慎用"},
    {"name": "玉屏风散", "category": "补益剂", "source": "《医方类聚》",
     "composition": "黄芪30g、白术60g、防风30g",
     "effects": "益气固表止汗",
     "indications": "表虚自汗。汗出恶风，面色㿠白，舌淡苔薄白，脉浮虚。亦治虚人腠理不固，易感风邪",
     "usage": "研末，每日两次，每次6-9g，温开水送服；亦可水煎服",
     "contraindications": "阴虚盗汗者忌用"},
    {"name": "逍遥散", "category": "和解剂", "source": "《太平惠民和剂局方》",
     "composition": "柴胡9g、当归9g、白芍9g、白术9g、茯苓9g、炙甘草6g、薄荷3g、生姜3片",
     "effects": "疏肝解郁，养血健脾",
     "indications": "肝郁血虚脾弱证。两胁作痛，头痛目眩，口燥咽干，神疲食少，或月经不调，乳房胀痛，脉弦而虚",
     "usage": "水煎服，每日一剂",
     "contraindications": "肝肾阴虚，气滞不运所致的胁肋疼痛，胸腹胀满者慎用"},
    {"name": "小柴胡汤", "category": "和解剂", "source": "《伤寒论》",
     "composition": "柴胡12g、黄芩9g、人参6g、炙甘草5g、半夏9g、生姜9g、大枣4枚",
     "effects": "和解少阳",
     "indications": "伤寒少阳证。往来寒热，胸胁苦满，默默不欲饮食，心烦喜呕，口苦，咽干，目眩，舌苔薄白，脉弦者",
     "usage": "水煎服，每日一剂，分两次温服",
     "contraindications": "阴虚血少者忌用"},
    {"name": "五苓散", "category": "祛湿剂", "source": "《伤寒论》",
     "composition": "猪苓9g、泽泻15g、白术9g、茯苓9g、桂枝6g",
     "effects": "利水渗湿，温阳化气",
     "indications": "膀胱气化不利之蓄水证。小便不利，头痛微热，烦渴欲饮，甚则水入即吐；或脐下动悸，吐涎沫而头目眩晕；或短气而咳；或水肿、泄泻。舌苔白，脉浮或浮数",
     "usage": "研末，每日三次，每次6-9g，多饮暖水，取微汗；亦可水煎服",
     "contraindications": "湿热者忌用，阴虚津少者慎用"},
    {"name": "补中益气汤", "category": "补益剂", "source": "《内外伤辨惑论》",
     "composition": "黄芪18g、炙甘草9g、人参6g、当归3g、橘皮6g、升麻6g、柴胡6g、白术9g",
     "effects": "补中益气，升阳举陷",
     "indications": "脾虚气陷证。饮食减少，体倦肢软，少气懒言，面色萎黄，大便稀溏，舌淡，脉虚；以及脱肛、子宫脱垂、久泻久痢，崩漏等",
     "usage": "水煎服，每日一剂，分两次温服",
     "contraindications": "阴虚发热及内热炽盛者忌用"},
]

SAMPLE_PRESCRIPTIONS = [
    {
        "prescription_no": "RX20260901001",
        "patient_name": "王病人", "patient_phone": "13700137000", "patient_gender": "男", "patient_age": 35,
        "doctor_username": "doctor", "doctor_name": "李医生", "department": "中医内科",
        "diagnosis": "气血两虚证", "advice": "水煎服，每日一剂，分两次温服",
        "status": "approved", "audit_remark": "处方合理，同意", "auditor": "admin", "auditor_name": "系统管理员",
        "audit_time": "2026/09/01 10:30:00",
        "items": [
            {"herb_code": "HC001", "herb_name": "黄芪", "dosage": "30g", "usage": "水煎", "quantity": 7, "price": 0.15},
            {"herb_code": "HC002", "herb_name": "当归", "dosage": "15g", "usage": "水煎", "quantity": 7, "price": 0.25},
            {"herb_code": "HC003", "herb_name": "白术", "dosage": "15g", "usage": "水煎", "quantity": 7, "price": 0.18},
            {"herb_code": "HC005", "herb_name": "甘草", "dosage": "6g", "usage": "水煎", "quantity": 7, "price": 0.08},
        ],
    },
    {
        "prescription_no": "RX20260902001",
        "patient_name": "李华", "patient_phone": "13600136000", "patient_gender": "女", "patient_age": 28,
        "doctor_username": "doctor2", "doctor_name": "张医生", "department": "中医妇科",
        "diagnosis": "月经不调，血虚血瘀", "advice": "水煎服，经前一周开始服用",
        "status": "dispensed", "audit_remark": "同意", "auditor": "admin", "auditor_name": "系统管理员",
        "audit_time": "2026/09/02 14:00:00",
        "dispenser": "admin", "dispenser_name": "系统管理员", "dispense_time": "2026/09/02 15:30:00",
        "items": [
            {"herb_code": "HC002", "herb_name": "当归", "dosage": "20g", "usage": "水煎", "quantity": 5, "price": 0.25},
            {"herb_code": "HC006", "herb_name": "川芎", "dosage": "10g", "usage": "水煎", "quantity": 5, "price": 0.20},
            {"herb_code": "HC007", "herb_name": "白芍", "dosage": "15g", "usage": "水煎", "quantity": 5, "price": 0.16},
            {"herb_code": "HC005", "herb_name": "甘草", "dosage": "6g", "usage": "水煎", "quantity": 5, "price": 0.08},
        ],
    },
    {
        "prescription_no": "RX20260903001",
        "patient_name": "赵强", "patient_phone": "13500135000", "patient_gender": "男", "patient_age": 45,
        "doctor_username": "doctor", "doctor_name": "李医生", "department": "中医内科",
        "diagnosis": "脾虚湿盛证", "advice": "水煎服，每日一剂，忌食生冷油腻",
        "status": "pending",
        "items": [
            {"herb_code": "HC003", "herb_name": "白术", "dosage": "20g", "usage": "水煎", "quantity": 7, "price": 0.18},
            {"herb_code": "HC004", "herb_name": "茯苓", "dosage": "20g", "usage": "水煎", "quantity": 7, "price": 0.12},
            {"herb_code": "HC001", "herb_name": "黄芪", "dosage": "25g", "usage": "水煎", "quantity": 7, "price": 0.15},
            {"herb_code": "HC010", "herb_name": "党参", "dosage": "15g", "usage": "水煎", "quantity": 7, "price": 0.30},
            {"herb_code": "HC005", "herb_name": "甘草", "dosage": "6g", "usage": "水煎", "quantity": 7, "price": 0.08},
        ],
    },
    {
        "prescription_no": "RX20260904001",
        "patient_name": "孙丽", "patient_phone": "13400134000", "patient_gender": "女", "patient_age": 52,
        "doctor_username": "doctor2", "doctor_name": "张医生", "department": "中医妇科",
        "diagnosis": "更年期综合征，肝肾阴虚", "advice": "水煎服，每日一剂",
        "status": "rejected", "audit_remark": "剂量偏大，请调整后重新提交", "auditor": "admin", "auditor_name": "系统管理员",
        "audit_time": "2026/09/04 09:00:00",
        "items": [
            {"herb_code": "HC008", "herb_name": "柴胡", "dosage": "12g", "usage": "水煎", "quantity": 7, "price": 0.22},
            {"herb_code": "HC009", "herb_name": "黄芩", "dosage": "10g", "usage": "水煎", "quantity": 7, "price": 0.19},
            {"herb_code": "HC007", "herb_name": "白芍", "dosage": "15g", "usage": "水煎", "quantity": 7, "price": 0.16},
            {"herb_code": "HC005", "herb_name": "甘草", "dosage": "6g", "usage": "水煎", "quantity": 7, "price": 0.08},
        ],
    },
]


def sha256_pwd(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def main():
    print("=" * 50)
    print("  本草智管平台 - 数据库初始化")
    print(f"  数据库模式: {'MySQL' if is_mysql() else 'SQLite（默认，即开即用）'}")
    if not is_mysql():
        print(f"  数据库文件: {SQLITE_DB_PATH}")
    print("=" * 50)

    if is_mysql():
        _init_mysql()
    else:
        _init_sqlite()

    print("\n数据库初始化完成！")
    print("默认账号：")
    print("  admin / 123456 （管理员，可审核/发药/用户管理）")
    print("  doctor / 123456 （医生，可开处方）")
    print("  doctor2 / 123456（医生，可开处方）")
    print("  patient / 123456（病人，只读）")


def _init_sqlite():
    print("[1/8] 创建数据表 ...")
    for sql in SQLITE_TABLES:
        execute(sql)
    print("  12张表 + 13个索引 创建完成")

    print("[2/8] 写入默认账号 ...")
    for u in DEFAULT_USERS:
        existing = query("SELECT username FROM users WHERE username = ?", (u["username"],), one=True)
        if existing:
            execute("""UPDATE users SET password=?, role=?, name=?, phone=?, status=?,
                       department=?, license=?, gender=?, age=?, idcard=?, create_time=?
                       WHERE username=?""",
                    (sha256_pwd(u["password"]), u["role"], u["name"], u["phone"], u["status"],
                     u["department"], u["license"], u["gender"], u["age"], u["idcard"],
                     u["create_time"], u["username"]))
        else:
            execute("""INSERT INTO users (username,password,role,name,phone,status,department,license,gender,age,idcard,create_time)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (u["username"], sha256_pwd(u["password"]), u["role"], u["name"], u["phone"],
                     u["status"], u["department"], u["license"], u["gender"], u["age"],
                     u["idcard"], u["create_time"]))
    print(f"  {len(DEFAULT_USERS)} 个账号就绪")

    print("[3/8] 写入示例药材 ...")
    for h in SAMPLE_HERBS:
        existing = query("SELECT code FROM herbs WHERE code = ?", (h["code"],), one=True)
        if existing:
            execute("""UPDATE herbs SET name=?, category=?, origin=?, storage=?, unit=?,
                       price=?, quantity=?, warning_threshold=?, description=? WHERE code=?""",
                    (h["name"], h["category"], h["origin"], h["storage"], h["unit"],
                     h["price"], h["quantity"], h["warning_threshold"], h["description"], h["code"]))
        else:
            execute("""INSERT INTO herbs (code,name,category,origin,storage,unit,price,quantity,warning_threshold,description)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (h["code"], h["name"], h["category"], h["origin"], h["storage"], h["unit"],
                     h["price"], h["quantity"], h["warning_threshold"], h["description"]))
    print(f"  {len(SAMPLE_HERBS)} 种药材就绪")

    print("[4/8] 写入示例供应商 ...")
    for s in SAMPLE_SUPPLIERS:
        existing = query("SELECT id FROM suppliers WHERE name = ?", (s["name"],), one=True)
        if not existing:
            execute("""INSERT INTO suppliers (name,contact_person,phone,address,description,status)
                       VALUES (?,?,?,?,?,?)""",
                    (s["name"], s["contact_person"], s["phone"], s["address"], s["description"], s["status"]))
    print(f"  {len(SAMPLE_SUPPLIERS)} 个供应商就绪")

    print("[5/8] 写入示例采购单 ...")
    count = 0
    for p in SAMPLE_PURCHASE_ORDERS:
        existing = query("SELECT id FROM purchase_orders WHERE order_no = ?", (p["order_no"],), one=True)
        if existing:
            continue
        total = sum(item["quantity"] * item["price"] for item in p["items"])
        _, po_id = execute("""INSERT INTO purchase_orders
            (order_no,supplier_id,supplier_name,total_amount,status,remark,creator,creator_name,
             auditor,auditor_name,audit_time,in_stock_time)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (p["order_no"], p["supplier_id"], p["supplier_name"], round(total, 2), p["status"],
             p.get("remark"), p.get("creator"), p.get("creator_name"), p.get("auditor"),
             p.get("auditor_name"), p.get("audit_time"), p.get("in_stock_time")))
        for item in p["items"]:
            subtotal = round(item["quantity"] * item["price"], 2)
            received = item["quantity"] if p["status"] == "completed" else 0
            execute("""INSERT INTO purchase_items
                (purchase_id,herb_code,herb_name,quantity,unit,price,subtotal,received_quantity)
                VALUES (?,?,?,?,?,?,?,?)""",
                (po_id, item["herb_code"], item["herb_name"], item["quantity"],
                 item["unit"], item["price"], subtotal, received))
        count += 1
    print(f"  {count} 张采购单就绪")

    print("[6/8] 写入示例处方 ...")
    count = 0
    for p in SAMPLE_PRESCRIPTIONS:
        existing = query("SELECT id FROM prescriptions WHERE prescription_no = ?", (p["prescription_no"],), one=True)
        if existing:
            continue
        total = sum(float(str(item["dosage"]).replace("g", "")) * item["quantity"] * item["price"] for item in p["items"])
        _, rx_id = execute("""INSERT INTO prescriptions
            (prescription_no,patient_name,patient_phone,patient_gender,patient_age,
             doctor_username,doctor_name,department,diagnosis,advice,total_amount,
             status,audit_remark,auditor,auditor_name,audit_time,dispenser,dispenser_name,dispense_time)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (p["prescription_no"], p["patient_name"], p["patient_phone"], p["patient_gender"], p["patient_age"],
             p["doctor_username"], p["doctor_name"], p["department"], p["diagnosis"], p["advice"], round(total, 2),
             p["status"], p.get("audit_remark"), p.get("auditor"), p.get("auditor_name"), p.get("audit_time"),
             p.get("dispenser"), p.get("dispenser_name"), p.get("dispense_time")))
        for item in p["items"]:
            dosage_val = float(str(item["dosage"]).replace("g", ""))
            subtotal = round(dosage_val * item["quantity"] * item["price"], 2)
            execute("""INSERT INTO prescription_items
                (prescription_id,herb_code,herb_name,dosage,usage,quantity,price,subtotal)
                VALUES (?,?,?,?,?,?,?,?)""",
                (rx_id, item["herb_code"], item["herb_name"], item["dosage"],
                 item["usage"], item["quantity"], item["price"], subtotal))
        count += 1
    print(f"  {count} 张处方就绪")

    print("[7/8] 写入药材知识库 ...")
    count = 0
    for k in SAMPLE_HERB_KNOWLEDGE:
        existing = query("SELECT id FROM herb_knowledge WHERE herb_code = ?", (k["herb_code"],), one=True)
        if existing:
            continue
        execute("""INSERT INTO herb_knowledge
            (herb_code,herb_name,category,nature,flavor,meridian,effects,indications,
             dosage,usage,contraindications,compatibility)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (k["herb_code"], k["herb_name"], k["category"], k["nature"], k["flavor"],
             k["meridian"], k["effects"], k["indications"], k["dosage"], k["usage"],
             k["contraindications"], k["compatibility"]))
        count += 1
    print(f"  {count} 条药材知识就绪")

    print("[8/8] 写入方剂库 ...")
    count = 0
    for f in SAMPLE_FORMULAS:
        existing = query("SELECT id FROM formulas WHERE name = ?", (f["name"],), one=True)
        if existing:
            continue
        execute("""INSERT INTO formulas
            (name,category,source,composition,effects,indications,usage,contraindications)
            VALUES (?,?,?,?,?,?,?,?)""",
            (f["name"], f["category"], f["source"], f["composition"], f["effects"],
             f["indications"], f["usage"], f["contraindications"]))
        count += 1
    print(f"  {count} 首方剂就绪")


def _init_mysql():
    """MySQL 模式初始化（兼容 Railway MySQL 环境变量）"""
    import pymysql
    import urllib.parse
    # 优先用 MYSQL_URL 解析（Railway MySQL 自动提供）
    mysql_url = os.environ.get("MYSQL_URL") or os.environ.get("MYSQL_PUBLIC_URL")
    if mysql_url:
        parsed = urllib.parse.urlparse(mysql_url)
        conn_cfg = {
            "host": parsed.hostname,
            "port": parsed.port or 3306,
            "user": parsed.username,
            "password": parsed.password,
            "charset": "utf8mb4",
        }
        db_name = parsed.path.lstrip("/") or DB_NAME
    else:
        conn_cfg = {
            "host": os.environ.get("DB_HOST") or os.environ.get("MYSQLHOST") or "127.0.0.1",
            "port": int(os.environ.get("DB_PORT") or os.environ.get("MYSQLPORT") or "3306"),
            "user": os.environ.get("DB_USER") or os.environ.get("MYSQLUSER") or "root",
            "password": os.environ.get("DB_PASSWORD") or os.environ.get("MYSQLPASSWORD") or "",
            "charset": "utf8mb4",
        }
        db_name = DB_NAME or os.environ.get("MYSQLDATABASE") or "bencao_zhiguan"
    conn = pymysql.connect(**conn_cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS {db_name} DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            cur.execute(f"USE {db_name}")
            # 建表（MySQL 语法）
            mysql_tables = [
                """CREATE TABLE IF NOT EXISTS users (
                    username VARCHAR(50) NOT NULL PRIMARY KEY, password VARCHAR(64) NOT NULL,
                    role VARCHAR(20) NOT NULL DEFAULT 'patient', name VARCHAR(50) NOT NULL,
                    phone VARCHAR(30), status VARCHAR(20) NOT NULL DEFAULT 'active',
                    department VARCHAR(50), license VARCHAR(50), gender VARCHAR(10),
                    age INT, idcard VARCHAR(30), create_time VARCHAR(50)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
                """CREATE TABLE IF NOT EXISTS herbs (
                    code VARCHAR(50) NOT NULL PRIMARY KEY, name VARCHAR(50) NOT NULL,
                    category VARCHAR(50), origin VARCHAR(100), storage VARCHAR(100),
                    unit VARCHAR(20), price DECIMAL(10,2), quantity INT DEFAULT 0,
                    warning_threshold INT DEFAULT 200, description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
                """CREATE TABLE IF NOT EXISTS operation_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY, herb_code VARCHAR(50), herb_name VARCHAR(50),
                    action VARCHAR(20) NOT NULL, changes JSON, operator VARCHAR(50), operator_name VARCHAR(50),
                    timestamp BIGINT, time_str VARCHAR(50)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
                """CREATE TABLE IF NOT EXISTS prescriptions (
                    id INT AUTO_INCREMENT PRIMARY KEY, prescription_no VARCHAR(50) NOT NULL UNIQUE,
                    patient_name VARCHAR(50) NOT NULL, patient_phone VARCHAR(30), patient_gender VARCHAR(10),
                    patient_age INT, doctor_username VARCHAR(50), doctor_name VARCHAR(50), department VARCHAR(50),
                    diagnosis TEXT, advice TEXT, total_amount DECIMAL(10,2) DEFAULT 0,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending', audit_remark TEXT, auditor VARCHAR(50),
                    auditor_name VARCHAR(50), audit_time VARCHAR(50), dispenser VARCHAR(50),
                    dispenser_name VARCHAR(50), dispense_time VARCHAR(50),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_status (status), INDEX idx_doctor (doctor_username), INDEX idx_patient (patient_name)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
                """CREATE TABLE IF NOT EXISTS prescription_items (
                    id INT AUTO_INCREMENT PRIMARY KEY, prescription_id INT NOT NULL,
                    herb_code VARCHAR(50), herb_name VARCHAR(50) NOT NULL, dosage VARCHAR(30),
                    `usage` VARCHAR(100), quantity INT DEFAULT 1, price DECIMAL(10,2) DEFAULT 0,
                    subtotal DECIMAL(10,2) DEFAULT 0, INDEX idx_prescription (prescription_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            ]
            for sql in mysql_tables:
                cur.execute(sql)
            print("  5张表创建完成")

            # 写入默认数据（复用 SQLite 的数据，用 MySQL 语法）
            print("[2/4] 写入默认账号 ...")
            for u in DEFAULT_USERS:
                cur.execute("""INSERT INTO users (username,password,role,name,phone,status,department,license,gender,age,idcard,create_time)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE password=VALUES(password), role=VALUES(role), name=VALUES(name)""",
                    (u["username"], sha256_pwd(u["password"]), u["role"], u["name"], u["phone"],
                     u["status"], u["department"], u["license"], u["gender"], u["age"], u["idcard"], u["create_time"]))

            print("[3/4] 写入示例药材 ...")
            for h in SAMPLE_HERBS:
                cur.execute("""INSERT INTO herbs (code,name,category,origin,storage,unit,price,quantity,warning_threshold,description)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE name=VALUES(name), quantity=VALUES(quantity)""",
                    (h["code"], h["name"], h["category"], h["origin"], h["storage"], h["unit"],
                     h["price"], h["quantity"], h["warning_threshold"], h["description"]))

            print("[4/4] 写入示例处方 ...")
            for p in SAMPLE_PRESCRIPTIONS:
                cur.execute("SELECT id FROM prescriptions WHERE prescription_no=%s", (p["prescription_no"],))
                if cur.fetchone():
                    continue
                total = sum(float(str(item["dosage"]).replace("g", "")) * item["quantity"] * item["price"] for item in p["items"])
                cur.execute("""INSERT INTO prescriptions
                    (prescription_no,patient_name,patient_phone,patient_gender,patient_age,
                     doctor_username,doctor_name,department,diagnosis,advice,total_amount,
                     status,audit_remark,auditor,auditor_name,audit_time,dispenser,dispenser_name,dispense_time)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (p["prescription_no"], p["patient_name"], p["patient_phone"], p["patient_gender"], p["patient_age"],
                     p["doctor_username"], p["doctor_name"], p["department"], p["diagnosis"], p["advice"], round(total, 2),
                     p["status"], p.get("audit_remark"), p.get("auditor"), p.get("auditor_name"), p.get("audit_time"),
                     p.get("dispenser"), p.get("dispenser_name"), p.get("dispense_time")))
                rx_id = cur.lastrowid
                for item in p["items"]:
                    dosage_val = float(str(item["dosage"]).replace("g", ""))
                    subtotal = round(dosage_val * item["quantity"] * item["price"], 2)
                    cur.execute("""INSERT INTO prescription_items
                        (prescription_id,herb_code,herb_name,dosage,usage,quantity,price,subtotal)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (rx_id, item["herb_code"], item["herb_name"], item["dosage"],
                         item["usage"], item["quantity"], item["price"], subtotal))
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
