"""Pruebas unitarias y TDD para validadores colombianos y Capa 1 (Regex)."""

from __future__ import annotations

import pytest

from tapaito.detect.regex_layer import detect_regex
from tapaito.detect.validators import (
    compute_dian_dv,
    has_cedula_context,
    validate_celular_co,
    validate_nit_dv,
    validate_radicado_co,
)
from tapaito.schemas import EntityType


class TestDianNitValidators:
    """Pruebas del algoritmo de la DIAN para cálculo y validación de NIT-DV."""

    @pytest.mark.parametrize(
        ("nit_digits", "expected_dv"),
        [
            # NIT públicos empresariales reales (no datos personales, documentados por DIAN)
            ("800197268", 4),  # DIAN
            ("899999068", 1),  # Ecopetrol
            ("890903938", 8),  # Bancolombia
            ("860002964", 4),  # Banco de Bogotá
            # NITs sintéticos de prueba verificados a mano con pesos primos DIAN:
            # 900123456 -> 6*3+5*7+4*13+3*17+2*19+1*23+0*29+0*37+9*41 = 18+35+52+51+38+23+0+0+369 = 586
            # 586 % 11 = 3 -> 11 - 3 = 8
            ("900123456", 8),
            # Caso con residuo 0 o 1
            # 800000001 -> 1*3 + 8*41 = 331; 331 % 11 = 1 -> DV = 1
            ("800000001", 1),
            # 800000005 -> 5*3 + 8*41 = 343; 343 % 11 = 2 -> DV = 9
            ("800000005", 9),
            # 800000013 -> 3*3 + 1*7 + 8*41 = 9+7+328 = 344; 344 % 11 = 3 -> DV = 8
            ("800000013", 8),
            # Residuo 0: 800000008 -> 8*3 + 8*41 = 24+328 = 352; 352 % 11 = 0 -> DV = 0
            ("800000008", 0),
        ],
    )
    def test_compute_dian_dv_valid(self, nit_digits: str, expected_dv: int) -> None:
        assert compute_dian_dv(nit_digits) == expected_dv

    @pytest.mark.parametrize(
        ("nit_raw", "dv"),
        [
            ("800.197.268", "4"),
            ("800197268", "4"),
            ("899.999.068", "1"),
            ("890 903 938", "8"),
            ("900.123.456", "8"),
            ("800000008", "0"),
            ("800000001", "1"),
        ],
    )
    def test_validate_nit_dv_true(self, nit_raw: str, dv: str) -> None:
        assert validate_nit_dv(nit_raw, dv) is True

    @pytest.mark.parametrize(
        ("nit_raw", "dv"),
        [
            ("800.197.268", "5"),  # DV incorrecto (debería ser 4)
            ("899999068", "0"),  # DV incorrecto (debería ser 1)
            ("890903938", "9"),  # DV incorrecto (debería ser 8)
            ("12345", "1"),  # Muy corto (< 8 dígitos)
            ("12345678901", "1"),  # Muy largo (> 10 dígitos)
            ("800197268", "X"),  # DV no numérico
            ("", "4"),
        ],
    )
    def test_validate_nit_dv_false(self, nit_raw: str, dv: str) -> None:
        assert validate_nit_dv(nit_raw, dv) is False


class TestCelularValidator:
    """Pruebas del validador de celulares colombianos."""

    @pytest.mark.parametrize(
        "raw",
        [
            "3001234567",
            "310 456 7890",
            "+57 310 456 7890",
            "(+57) 315-890-1234",
            "57 320 111 2233",
            "314.567.89.01",
            "350-987-6543",
            "+573012223344",
        ],
    )
    def test_validate_celular_co_valid(self, raw: str) -> None:
        assert validate_celular_co(raw) is True

    @pytest.mark.parametrize(
        "raw",
        [
            "3601234567",  # Empieza por 36 (fuera de rango 3[0-5])
            "6012345678",  # Teléfono fijo nacional
            "310456789",  # 9 dígitos
            "31045678901",  # 11 dígitos
            "+58 310 456 7890",  # Prefijo de otro país
            "1234567",  # Fijo local 7 dígitos
            "abc",
        ],
    )
    def test_validate_celular_co_invalid(self, raw: str) -> None:
        assert validate_celular_co(raw) is False


class TestRadicadoValidator:
    """Pruebas del validador de radicados judiciales de 23 dígitos."""

    @pytest.mark.parametrize(
        "raw",
        [
            "11001310300120240012300",
            "11001-31-03-001-2024-00123-00",
            "05001 31 05 002 2019 00456 01",
            "76001-40-03-010-1998-01020-00",
        ],
    )
    def test_validate_radicado_co_valid(self, raw: str) -> None:
        assert validate_radicado_co(raw) is True

    @pytest.mark.parametrize(
        "raw",
        [
            "11001-31-03-001-9999-00123-00",  # Año 9999 inválido
            "11001-31-03-001-1850-00123-00",  # Año 1850 inválido (< 1990)
            "1100131030012024001230",  # 22 dígitos
            "110013103001202400123000",  # 24 dígitos
            "110013103001202400123AA",  # Letras
        ],
    )
    def test_validate_radicado_co_invalid(self, raw: str) -> None:
        assert validate_radicado_co(raw) is False


class TestCedulaContextValidator:
    """Pruebas de contexto positivo y negativo para cédulas colombianas."""

    @pytest.mark.parametrize(
        ("text", "target"),
        [
            ("Paciente con CC 1032456789 que ingresa por urgencias.", "1032456789"),
            ("Identificación: 79456123 de Bogotá.", "79456123"),
            ("Cédula de ciudadanía No. 52.345.678 expedida en Cali.", "52.345.678"),
            ("Portador del documento 1098765432 presenta fiebre.", "1098765432"),
            # Formato explícito con puntos de miles válido sin palabra clave inmediata
            ("El señor 1.032.456.789 asistió al control.", "1.032.456.789"),
            ("Registrado bajo 79.456.123 en admisiones.", "79.456.123"),
        ],
    )
    def test_has_cedula_context_positive(self, text: str, target: str) -> None:
        start = text.index(target)
        end = start + len(target)
        assert has_cedula_context(text, start, end) is True

    @pytest.mark.parametrize(
        ("text", "target"),
        [
            ("Se ordena procedimiento CUPS 890201 prioritario.", "890201"),
            ("Vacuna aplicada del Lote 12345678 sin reacción.", "12345678"),
            ("Registro INVIMA 2021012345 vigente.", "2021012345"),
            ("Suministrar Acetaminofén 1000000 ui intramuscular.", "1000000"),
            ("Solución salina 1500000 ml en 24 horas.", "1500000"),
            ("Orden # 98765432 de laboratorio clínico.", "98765432"),
            ("Número sin contexto ni puntos 12345678 en la nota.", "12345678"),
        ],
    )
    def test_has_cedula_context_negative(self, text: str, target: str) -> None:
        start = text.index(target)
        end = start + len(target)
        assert has_cedula_context(text, start, end) is False


class TestDetectRegexLayer:
    """Pruebas integrales de detect_regex(text) y verificación de invariantes de Span."""

    def _assert_spans_invariant(self, text: str, spans: list) -> None:
        for s in spans:
            assert text[s.start : s.end] == s.text, (
                f"Desajuste de offset para {s.entity_type}: "
                f"text[{s.start}:{s.end}]={text[s.start:s.end]!r} != {s.text!r}"
            )
            assert s.source == "regex"

    def test_detect_nit_valid_and_reject_invalid_dv(self) -> None:
        text = (
            "IPS Clínica Sintética con NIT 800.197.268-4 y proveedor 890903938-8. "
            "No confundir con código interno 800.197.268-9 que tiene DV inválido."
        )
        spans = detect_regex(text)
        self._assert_spans_invariant(text, spans)
        nit_spans = [s for s in spans if s.entity_type == EntityType.NIT]
        nit_texts = [s.text for s in nit_spans]
        assert any("800.197.268-4" in t for t in nit_texts)
        assert any("890903938-8" in t for t in nit_texts)
        assert not any("800.197.268-9" in t for t in nit_texts)

    def test_detect_celular_variants(self) -> None:
        text = (
            "Contactar al +57 310 456 7890 o al (+57) 315-890-1234 o al 3001234567. "
            "No tomar fijo 6012345678 ni 3601234567."
        )
        spans = detect_regex(text)
        self._assert_spans_invariant(text, spans)
        cel_texts = [s.text for s in spans if s.entity_type == EntityType.CELULAR]
        assert "+57 310 456 7890" in cel_texts
        assert "(+57) 315-890-1234" in cel_texts
        assert "3001234567" in cel_texts
        assert "6012345678" not in cel_texts
        assert "3601234567" not in cel_texts

    def test_detect_radicado_and_prevent_subspan_collisions(self) -> None:
        text = (
            "Tutela de salud con radicado 11001-31-03-001-2024-00123-00 y "
            "proceso anexo 05001310500220210045600. "
            "Falso radicado con año inválido: 11001-31-03-001-9999-00123-00."
        )
        spans = detect_regex(text)
        self._assert_spans_invariant(text, spans)
        rad_texts = [s.text for s in spans if s.entity_type == EntityType.RADICADO]
        assert "11001-31-03-001-2024-00123-00" in rad_texts
        assert "05001310500220210045600" in rad_texts
        assert "11001-31-03-001-9999-00123-00" not in rad_texts
        # Asegurar que ningún sub-segmento del radicado continuo se detectó como celular o cédula
        rad_span = next(s for s in spans if s.text == "05001310500220210045600")
        for s in spans:
            if s != rad_span:
                assert not (s.start >= rad_span.start and s.end <= rad_span.end)

    def test_detect_cedula_vs_clinical_codes(self) -> None:
        text = (
            "Paciente identificado con CC 1.032.456.789 y documento: 79456123. "
            "Se realiza CUPS 890201, Lote 12345678, CIE-10 J00, "
            "Acetaminofén 1000 mg cada 8 horas."
        )
        spans = detect_regex(text)
        self._assert_spans_invariant(text, spans)
        ced_texts = [s.text for s in spans if s.entity_type == EntityType.CEDULA]
        assert "1.032.456.789" in ced_texts
        assert "79456123" in ced_texts
        assert "890201" not in ced_texts
        assert "12345678" not in ced_texts
        assert "1000" not in ced_texts

    def test_detect_correo_direccion_fechanac_cuenta(self) -> None:
        text = (
            "Correo: paciente.sintetico24@clinica-ejemplo.co. "
            "Reside en Calle 45 # 12-34 y trabaja en Cra. 7 No. 32 - 16 Apto 402 "
            "o Diagonal 115A # 70B - 20 o Vereda El Rosal Km 4. "
            "Fecha de nacimiento: 14/05/1985 (nacido el 1985-05-14). "
            "Reembolso a cuenta de ahorros 240-123456-78."
        )
        spans = detect_regex(text)
        self._assert_spans_invariant(text, spans)

        by_type: dict[EntityType, list[str]] = {}
        for s in spans:
            by_type.setdefault(s.entity_type, []).append(s.text)

        assert "paciente.sintetico24@clinica-ejemplo.co" in by_type.get(EntityType.CORREO, [])
        direcciones = by_type.get(EntityType.DIRECCION, [])
        assert any("Calle 45 # 12-34" in d for d in direcciones)
        assert any("Cra. 7 No. 32 - 16" in d for d in direcciones)
        assert any("Diagonal 115A # 70B - 20" in d for d in direcciones)
        assert any("Vereda El Rosal Km 4" in d for d in direcciones)

        fechas = by_type.get(EntityType.FECHA_NAC, [])
        assert "14/05/1985" in fechas
        assert "1985-05-14" in fechas

        cuentas = by_type.get(EntityType.CUENTA, [])
        assert "240-123456-78" in cuentas
