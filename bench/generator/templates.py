"""Plantillas clínicas colombianas y constructor determinista con offsets exactos por construcción."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from tapaito.detect.validators import (
    compute_dian_dv,
    validate_celular_co,
    validate_nit_dv,
    validate_radicado_co,
)
from tapaito.schemas import EntityType

GENRES: tuple[str, ...] = (
    "historia_clinica",
    "epicrisis",
    "orden_medica",
    "tutela_salud",
    "seguimiento_paciente",
)

# Bancos separados por split para evitar solapamiento léxico entre dev y test
_DEV_FIRST_NAMES: tuple[str, ...] = (
    "Carlos Alberto",
    "María Fernanda",
    "Juan Sebastián",
    "Diana Marcela",
    "Andrés Felipe",
    "Paula Andrea",
    "Jorge Eliécer",
    "Laura Valentina",
    "Camilo Ernesto",
    "Natalia Sofía",
)

_TEST_FIRST_NAMES: tuple[str, ...] = (
    "Luis Fernando",
    "Claudia Patricia",
    "Diego Alejandro",
    "Carolina Isabel",
    "Óscar Mauricio",
    "Sandra Milena",
    "Héctor Fabián",
    "Juliana Marcela",
    "Germán Darío",
    "Adriana Lucía",
    "Ricardo José",
    "Mónica Alejandra",
)

_DEV_LAST_NAMES: tuple[str, ...] = (
    "Restrepo Gómez",
    "Ospina Jaramillo",
    "Cárdenas Mejía",
    "Betancur Valencia",
    " Montoya Salazar",
    "Giraldo Aristizábal",
    "Patiño Londoño",
    "Castañeda Ríos",
    "Quintero Henao",
    "Velásquez Duque",
)

_TEST_LAST_NAMES: tuple[str, ...] = (
    " Echeverri Zapata",
    "Piedrahita Correa",
    "Arango Botero",
    "Lozano Bermúdez",
    "Morales Tamayo",
    "Sánchez Beltrán",
    "Rincón Villamizar",
    "Parra Castellanos",
    "Vargas Bohórquez",
    "Suárez Peñaloza",
    "Guerrero Alarcón",
    "Mendoza Cubillos",
)

# Nombres compuestos en minúsculas sin etiqueta estándar donde spaCy es_core_news_md falla (Subtipo B - CE3)
_DEV_HARD_LOWERCASE_NAMES: tuple[str, ...] = (
    "luz marina betancur",
    "alba lucia corredor",
    "blanca nieves piedrahita",
    "flor angela camargo",
    "aura stella bocanegra",
    "gloria esperanza pulido",
    "rocio del pilar narvaez",
)

_TEST_HARD_LOWERCASE_NAMES: tuple[str, ...] = (
    "cielo del pilar monroy",
    "ruby estela manrique",
    "estrella del mar angulo",
    "piedad del socorro arenas",
    "nieves del socorro cuellar",
    "fe esperanza dorado",
    "luz marina betancur",
    "alba lucia corredor",
    "blanca nieves piedrahita",
    "flor angela camargo",
    "aura stella bocanegra",
    "gloria esperanza pulido",
)

_DEV_CITIES: tuple[str, ...] = (
    "Medellín",
    "Bogotá",
    "Cali",
    "Barranquilla",
    "Bucaramanga",
    "Pereira",
)

_TEST_CITIES: tuple[str, ...] = (
    "Manizales",
    "Cartagena",
    "Ibagué",
    "Pasto",
    "Villavicencio",
    "Armenia",
    "Popayán",
    "Tunja",
)

_ORGANIZATIONS: tuple[str, ...] = (
    "Fundación Santa Fe",
    "Cruz Roja Colombiana",
    "Asociación Médica Colombiana",
    "Caja de Compensación Familiar",
)

_CIE10_CODES: tuple[str, ...] = ("I10X", "E119", "J189", "N390", "K297", "M545", "J459")

_MEDICATIONS_POS: tuple[tuple[str, str], ...] = (
    ("Losartán", "50 mg cada 12 horas"),
    ("Metformina", "850 mg con el almuerzo"),
    ("Acetaminofén", "500 mg cada 8 horas"),
    ("Enalapril", "20 mg vía oral día"),
    ("Omeprazol", "20 mg en ayunas"),
    ("Atorvastatina", "40 mg en la noche"),
    ("Amoxicilina", "500 mg cada 8 horas por 7 días"),
    ("Salbutamol", "200 mcg inhalados cada 6 horas"),
)

_QUASI_IDENTIFIER_ROLES: tuple[tuple[str, str], ...] = (
    ("quien ejerce como único juez promiscuo municipal de ", "Puerto Carreño"),
    ("actual alcaldesa municipal titular de ", "Mitú"),
    ("quien se desempeña como único notario único del círculo de ", "Inírida"),
    ("actual personero municipal en ejercicio de ", "Leticia"),
    ("quien labora como único registrador delegado en ", "Mocoa"),
    ("actual contralor departamental encargado en ", "Yopal"),
)


@dataclass
class TemplateBuilder:
    """Ensambla texto clínico y registra spans exactos por construcción."""

    chunks: list[str] = field(default_factory=list)
    spans: list[dict[str, Any]] = field(default_factory=list)
    _cursor: int = 0

    def add_text(self, literal: str) -> TemplateBuilder:
        if literal:
            self.chunks.append(literal)
            self._cursor += len(literal)
        return self

    def add_entity(self, entity_type: EntityType, surface: str) -> TemplateBuilder:
        clean_surface = surface.strip()
        if not clean_surface:
            raise ValueError("El texto de la entidad no puede ser vacío.")
        start = self._cursor
        end = start + len(clean_surface)
        self.chunks.append(clean_surface)
        self._cursor = end
        self.spans.append(
            {
                "start": start,
                "end": end,
                "entity_type": entity_type.value,
                "text": clean_surface,
            }
        )
        return self

    def build(self) -> tuple[str, list[dict[str, Any]]]:
        full_text = "".join(self.chunks)
        for sp in self.spans:
            s, e = sp["start"], sp["end"]
            assert full_text[s:e] == sp["text"], (
                f"Inconsistencia de offset: '{full_text[s:e]}' != '{sp['text']}'"
            )
        return full_text, list(self.spans)


def _gen_full_name(rng: random.Random, split: str) -> str:
    first_pool = _DEV_FIRST_NAMES if split == "dev" else _TEST_FIRST_NAMES
    last_pool = _DEV_LAST_NAMES if split == "dev" else _TEST_LAST_NAMES
    first = rng.choice(first_pool).strip()
    last = rng.choice(last_pool).strip()
    return f"{first} {last}"


def _gen_cedula(rng: random.Random, formatted: bool) -> str:
    val = rng.randint(10_100_000, 1_199_999_999)
    if formatted:
        return f"{val:,}".replace(",", ".")
    return str(val)


def _gen_nit_with_valid_dv(rng: random.Random, formatted: bool) -> str:
    base = str(rng.randint(800_100_000, 901_999_999))
    dv = compute_dian_dv(base)
    if formatted:
        dotted = f"{int(base):,}".replace(",", ".")
        return f"{dotted} - {dv}"
    return f"{base}-{dv}"


def _gen_celular(rng: random.Random, formatted: bool) -> str:
    prefix = rng.choice(("300", "301", "310", "311", "312", "315", "316", "320", "321"))
    mid = rng.randint(200, 999)
    end = rng.randint(1000, 9999)
    if formatted:
        style = rng.choice((0, 1))
        if style == 0:
            raw = f"(+57) {prefix}-{mid}-{end}"
        else:
            raw = f"+57 {prefix}.{mid}.{end}"
    else:
        raw = f"{prefix}{mid}{end}"
    assert validate_celular_co(raw)
    return raw


def _gen_radicado(rng: random.Random, formatted: bool) -> str:
    dane = rng.choice(("11001", "05001", "76001", "08001", "68001"))
    corp = rng.choice(("31", "40"))
    esp = rng.choice(("03", "05", "89"))
    desp = f"{rng.randint(1, 45):03d}"
    year = str(rng.randint(2019, 2026))
    consec = f"{rng.randint(10, 9800):05d}"
    rec = rng.choice(("00", "01"))
    if formatted:
        raw = f"{dane}-{corp}-{esp}-{desp}-{year}-{consec}-{rec}"
    else:
        raw = f"{dane}{corp}{esp}{desp}{year}{consec}{rec}"
    assert validate_radicado_co(raw)
    return raw


def _gen_correo(rng: random.Random, name: str, split: str) -> str:
    parts = [
        p.lower()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ñ", "n")
        for p in name.split()
    ]
    domain = rng.choice(("correo.co", "saludpaciente.co", "clinicaejemplo.org.co"))
    num = rng.randint(10, 99) if split == "dev" else rng.randint(100, 999)
    return f"{parts[0]}.{parts[-1]}{num}@{domain}"


def _gen_direccion(rng: random.Random, hard: bool) -> str:
    via = rng.choice(("Calle", "Carrera", "Diagonal", "Transversal", "Avenida"))
    n1 = rng.randint(10, 145)
    letra = rng.choice(("", "A", "B"))
    n2 = rng.randint(10, 95)
    n3 = rng.randint(11, 89)
    base = f"{via} {n1}{letra} # {n2}-{n3}"
    if hard:
        apto = rng.randint(101, 904)
        return f"{base} Apto {apto}"
    return base


def _gen_fecha_nac(rng: random.Random, hard: bool) -> str:
    day = rng.randint(1, 28)
    month_num = rng.randint(1, 12)
    year = rng.randint(1952, 2004)
    if hard:
        months = (
            "enero",
            "febrero",
            "marzo",
            "abril",
            "mayo",
            "junio",
            "julio",
            "agosto",
            "septiembre",
            "octubre",
            "noviembre",
            "diciembre",
        )
        return f"{day} de {months[month_num - 1]} de {year}"
    return f"{day:02d}/{month_num:02d}/{year}"


def _gen_cuenta(rng: random.Random) -> str:
    b1 = rng.randint(100, 999)
    b2 = rng.randint(100000, 999999)
    b3 = rng.randint(10, 99)
    return f"{b1}-{b2}-{b3}"


def build_clinical_case(
    rng: random.Random,
    case_index: int,
    split: str,
    genre: str,
    is_hard_case: bool,
    include_hard_lowercase_name: bool,
    has_quasi_identifier: bool,
) -> dict[str, Any]:
    """Construye un caso sintético completo con etiquetas exactas por construcción."""
    b = TemplateBuilder()

    patient_name = _gen_full_name(rng, split)
    doctor_name = _gen_full_name(rng, split)
    while doctor_name == patient_name:
        doctor_name = _gen_full_name(rng, split)

    cedula = _gen_cedula(rng, formatted=is_hard_case)
    nit = _gen_nit_with_valid_dv(rng, formatted=is_hard_case)
    assert validate_nit_dv(*nit.split("-"))
    celular = _gen_celular(rng, formatted=is_hard_case)
    correo = _gen_correo(rng, patient_name, split)
    direccion = _gen_direccion(rng, hard=is_hard_case)
    city_pool = _DEV_CITIES if split == "dev" else _TEST_CITIES
    city = rng.choice(city_pool)
    org = rng.choice(_ORGANIZATIONS)
    age = rng.randint(24, 82)
    cie10 = rng.choice(_CIE10_CODES)
    med_name, med_dose = rng.choice(_MEDICATIONS_POS)
    cups_code = rng.choice(("890201", "890301", "890701"))
    lote_num = rng.randint(40000000, 89999999)
    invima_num = rng.randint(2019001000, 2024999999)

    if genre == "historia_clinica":
        b.add_text("HISTORIA CLÍNICA DE EVOLUCIÓN. Paciente: ")
        b.add_entity(EntityType.PERSONA, patient_name)
        b.add_text(f", de {age} años, identificado con C.C. ")
        b.add_entity(EntityType.CEDULA, cedula)
        b.add_text(", teléfono celular ")
        b.add_entity(EntityType.CELULAR, celular)
        b.add_text(" y residencia en ")
        b.add_entity(EntityType.DIRECCION, direccion)
        b.add_text(". Asegurador: ")
        b.add_entity(EntityType.ORGANIZACION, org)
        b.add_text(" con código tributario ")
        b.add_entity(EntityType.NIT, nit)
        b.add_text(
            f". Cuadro clínico compatible con diagnóstico CIE-10 {cie10}. "
            f"Se indica manejo ambulatorio con {med_name} {med_dose}."
        )
        if is_hard_case:
            b.add_text(
                f" Se factura interconsulta CUPS {cups_code} y se administra "
                f"ampolla de 1000000 UI intramuscular (Lote {lote_num}, INVIMA {invima_num})."
            )

    elif genre == "epicrisis":
        fecha_nac = _gen_fecha_nac(rng, hard=is_hard_case)
        b.add_text("EPICRISIS DE EGRESO. Paciente: ")
        b.add_entity(EntityType.PERSONA, patient_name)
        b.add_text(", con fecha de nacimiento ")
        b.add_entity(EntityType.FECHA_NAC, fecha_nac)
        b.add_text(f" ({age} años), remitido desde ")
        b.add_entity(EntityType.UBICACION, city)
        b.add_text(". Atendido por Dr. ")
        b.add_entity(EntityType.PERSONA, doctor_name)
        b.add_text(" con documento C.C. ")
        b.add_entity(EntityType.CEDULA, cedula)
        b.add_text(
            f". Egreso con diagnóstico principal CIE-10 {cie10} tras procedimiento "
            f"CUPS {cups_code} sin complicaciones. Continuar {med_name} {med_dose} "
            f"y solución oral 15 ml cada 12 horas."
        )

    elif genre == "orden_medica":
        med2_name, med2_dose = rng.choice(_MEDICATIONS_POS)
        b.add_text("ORDEN MÉDICA AMBULATORIA. Paciente: ")
        b.add_entity(EntityType.PERSONA, patient_name)
        b.add_text(", documento de identificación ")
        b.add_entity(EntityType.CEDULA, cedula)
        b.add_text(", correo electrónico ")
        b.add_entity(EntityType.CORREO, correo)
        b.add_text(" y celular ")
        b.add_entity(EntityType.CELULAR, celular)
        b.add_text(". Entidad pagadora: ")
        b.add_entity(EntityType.ORGANIZACION, org)
        b.add_text(" (registro ")
        b.add_entity(EntityType.NIT, nit)
        b.add_text(
            f"). Diagnóstico CIE-10 {cie10} ({age} años). Prescripción: "
            f"1) {med_name} {med_dose} (Lote {lote_num}); "
            f"2) {med2_name} {med2_dose} (INVIMA {invima_num}, CUPS {cups_code})."
        )

    elif genre == "tutela_salud":
        radicado = _gen_radicado(rng, formatted=is_hard_case)
        b.add_text("SOLICITUD DE CUMPLIMIENTO DE TUTELA EN SALUD. Radicado judicial ")
        b.add_entity(EntityType.RADICADO, radicado)
        b.add_text(". Accionante: Paciente: ")
        b.add_entity(EntityType.PERSONA, patient_name)
        b.add_text(f", de {age} años, portador de la cédula ")
        b.add_entity(EntityType.CEDULA, cedula)
        b.add_text(" y correo de notificación ")
        b.add_entity(EntityType.CORREO, correo)
        b.add_text(". Entidad accionada con registro ")
        b.add_entity(EntityType.NIT, nit)
        b.add_text(
            f". Se ordena entrega inmediata de {med_name} {med_dose} y autorización "
            f"del procedimiento CUPS {cups_code} para patología CIE-10 {cie10}."
        )

    elif genre == "seguimiento_paciente":
        cuenta = _gen_cuenta(rng)
        b.add_text("NOTA DE SEGUIMIENTO Y REEMBOLSO. Paciente: ")
        b.add_entity(EntityType.PERSONA, patient_name)
        b.add_text(f" ({age} años), contacto móvil ")
        b.add_entity(EntityType.CELULAR, celular)
        b.add_text(", entrega domiciliaria en ")
        b.add_entity(EntityType.DIRECCION, direccion)
        b.add_text(" y reembolso autorizado en cuenta de ahorros No. ")
        b.add_entity(EntityType.CUENTA, cuenta)
        b.add_text(
            f". Se verifica adherencia a {med_name} {med_dose} por diagnóstico CIE-10 {cie10}."
        )
    else:
        raise ValueError(f"Género desconocido: {genre}")

    # Subtipo B: Nombre en minúsculas sin etiqueta estándar donde Regex+NER fallan pero Qwen3 recupera (CE3)
    if include_hard_lowercase_name:
        hard_pool = _DEV_HARD_LOWERCASE_NAMES if split == "dev" else _TEST_HARD_LOWERCASE_NAMES
        hard_name = hard_pool[case_index % len(hard_pool)]
        b.add_text(" Se entrega copia autorizada a la ciudadana ")
        b.add_entity(EntityType.PERSONA, hard_name)
        b.add_text(" en admisiones.")

    # Subtipo C: Cuasi-identificador (R6)
    if has_quasi_identifier:
        role_prefix, quasi_city = _QUASI_IDENTIFIER_ROLES[case_index % len(_QUASI_IDENTIFIER_ROLES)]
        b.add_text(f" Nota social: paciente {role_prefix}")
        b.add_entity(EntityType.UBICACION, quasi_city)
        b.add_text(".")

    full_text, spans = b.build()
    return {
        "id": f"{split}_{case_index + 1:03d}",
        "split": split,
        "genre": genre,
        "is_hard_case": is_hard_case,
        "has_quasi_identifier": has_quasi_identifier,
        "text": full_text,
        "spans": spans,
    }
