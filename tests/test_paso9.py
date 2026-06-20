from pathlib import Path

from expediente_scout.openclaw.router import construir_plan_desde_mensaje


ALLOWLIST = {"+5491100000000"}


def test_openclaw_archivos_de_configuracion_existen():
    for ruta in [
        "openclaw/AGENTS.md",
        "openclaw/TOOLS.md",
        "openclaw/SOUL.md",
        "openclaw/COMMANDS.md",
        "openclaw/prompts/analisis_gpt.md",
        "openclaw/examples/allowlist.example.txt",
    ]:
        assert Path(ruta).exists(), ruta


def test_remitente_no_autorizado_se_rechaza():
    plan = construir_plan_desde_mensaje(
        "+5491199999999",
        "Expediente: estado pjn 12345/2024",
        ALLOWLIST,
    )
    assert plan.autorizado is False
    assert plan.comandos_shell == []
    assert "no autorizado" in plan.motivo.lower()


def test_estado_autorizado_mapea_a_cli_scout():
    plan = construir_plan_desde_mensaje(
        "+5491100000000",
        "Expediente: estado pjn 12345/2024",
        ALLOWLIST,
    )
    assert plan.autorizado is True
    assert plan.requiere_gpt is False
    assert plan.comandos_shell == [
        "scout estado --root . --jurisdiccion pjn --numero 12345 --anio 2024"
    ]


def test_informe_autorizado_requiere_gpt_y_validador():
    plan = construir_plan_desde_mensaje(
        "+5491100000000",
        "Expediente: informe pjn 12345/2024",
        ALLOWLIST,
    )
    joined = "\n".join(plan.comandos_shell)
    assert plan.autorizado is True
    assert plan.requiere_gpt is True
    assert "scout capturar" in joined
    assert "scout normalizar" in joined
    assert "scout curar" in joined
    assert "GPT_ANALISIS_JSON=" in joined
    assert "scout validar-analisis" in joined
    assert "scout reportar" in joined


def test_prompt_gpt_exige_json_fuentes_y_no_determinable():
    texto = Path("openclaw/prompts/analisis_gpt.md").read_text(encoding="utf-8")
    assert "JSON" in texto
    assert "fuentes" in texto
    assert "No inventar IDs" in texto
    assert "no_determinable" in texto
    assert "scout validar-analisis" in texto
