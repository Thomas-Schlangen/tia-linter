"""Prüfpunkte 1-4: Kommentare & Beschreibungen."""

from __future__ import annotations

from typing import Any

from tia_linter.checks._tia_helpers import (
    compile_unit_attribute,
    export_block_xml,
    format_path,
    get_attribute,
    iter_compile_units,
    iter_data_blocks,
    iter_plc_software,
    iter_tag_tables,
    normalize_member_path,
    read_comment,
    reference_language,
)
from tia_linter.checks.base import BaseCheck
from tia_linter.models import CheckResult
from tia_linter.project_texts import ProjectTextComments


class VariablenKommentarCheck(BaseCheck):
    """Prüfpunkt 1: PLC-Tags und DB-Variablen ohne Kommentar.

    ``PlcTag.Comment`` ist wie im Schwesterprojekt ``tia-tag-exporter``
    (dort bereits gelöst, siehe dessen ``extractor.py::_read_comment``) ein
    mehrsprachiges ``MultilingualText``-Objekt statt eines einfachen Strings
    — TIA Portal ist grundsätzlich mehrsprachig (V21-Openness-Referenz,
    Abschnitt "Umgang mit mehrsprachigen Texten", nennt ``PlcTag.Comment``
    explizit als Beispiel). Ein ``GetAttribute("Comment")``-Zugriff darauf
    lieferte nie den tatsächlichen Text, wodurch **jede** Variable als
    unkommentiert gemeldet wurde. Fix: ``read_comment`` liest den Text
    gezielt für die Referenzsprache des Projekts über
    ``Comment.Items.Find(<Language>).Text`` (siehe ``_tia_helpers.py``).

    Beim ersten Testlauf gegen ein echtes Projekt hat sich außerdem gezeigt,
    dass ``db.Interface.Members`` nicht nur die deklarierten Top-Level-Variablen
    liefert, sondern rekursiv jedes einzelne verschachtelte Array-/
    Struct-Element als eigenes Member mit Punkt-/Klammer-Notation im Namen
    (z. B. ``GlobalMan``, ``GlobalMan.GlobalMan[0]``,
    ``GlobalMan.GlobalMan[0].Plus.Ena``, ...) — ein einziger großer Array-DB
    erzeugte dadurch fast 40.000 Einzelbefunde. Ein Kommentar auf dem Array
    selbst reicht aus (nicht jedes Array-Element einzeln); Struct-Felder
    dagegen sind normale, für sich kommentierbare Variablen und werden
    weiterhin einzeln geprüft. Daher wird hier nur übersprungen, was
    irgendwo im Namen einen Array-Index (``[...]``) enthält — reine
    Punkt-Notation ohne Klammer (Struct-Verschachtelung) bleibt geprüft.

    Zweiter, davon unabhängiger Bug (User-Meldung, live an
    ``_Org > DDb > Fieldbus > Alm.4805_15A1`` verifiziert): TIA quotet
    Namenssegmente, die keine gültigen "einfachen" Bezeichner sind (z. B.
    weil sie mit einer Ziffer beginnen) — ``member.Name`` liefert dann z. B.
    ``Alm."4805_15A1"`` statt ``Alm.4805_15A1``. Die ``ViewPath``-Segmente
    aus den Projekttexten sind dagegen unquotiert, wodurch der Lookup nie
    traf, obwohl ein Kommentar hinterlegt war — identisches, bereits im
    Schwesterprojekt ``tia-tag-exporter`` gelöstes Problem. Fix:
    ``normalize_member_path`` vor dem Lookup auf PLC-/DB-/Member-Namen
    anwenden (nur für den Lookup — der im Befund angezeigte Name bleibt
    unverändert die echte, ggf. quotierte TIA-Bezeichnung).
    """

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        exception_prefixes = tuple(self.definition.params.get("ausnahme_prefixe", []))
        language = reference_language(project)

        for plc_software in iter_plc_software(project):
            plc_name = plc_software.Name

            for tag_table in iter_tag_tables(plc_software, self.excluded_folders):
                for tag in tag_table.Tags:
                    tag_name = tag.Name
                    if tag_name.startswith(exception_prefixes):
                        continue
                    comment = read_comment(tag, language)
                    if not comment:
                        results.append(
                            self._make_result(
                                path=format_path(
                                    plc_name, "Variablentabellen", tag_table.Name, tag_name
                                ),
                                description=f"Variable '{tag_name}' hat keinen Kommentar.",
                                value=tag_name,
                            )
                        )

            project_texts = ProjectTextComments.load(project)
            for db, group_path in iter_data_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                db_name = db.Name
                for member in getattr(getattr(db, "Interface", None), "Members", []):
                    member_name = member.Name
                    if "[" in member_name:
                        continue  # Array-Element (auch verschachtelt darunter) — Array selbst reicht
                    if member_name.startswith(exception_prefixes):
                        continue
                    comment = project_texts.get(
                        normalize_member_path(plc_name),
                        normalize_member_path(db_name),
                        normalize_member_path(member_name),
                    )
                    if not comment:
                        results.append(
                            self._make_result(
                                path=format_path(
                                    plc_name, "Datenbaustein", *group_path, db_name, "Member", member_name
                                ),
                                description=f"DB-Variable '{member_name}' hat keinen Kommentar.",
                                value=member_name,
                            )
                        )
        return results


class BausteinBeschreibungCheck(BaseCheck):
    """Prüfpunkt 2: Bausteine ohne (aussagekräftige) Kopfbeschreibung.

    ``PlcBlock.Comment`` ist wie ``PlcTag.Comment`` (siehe
    ``VariablenKommentarCheck``) ein mehrsprachiges ``MultilingualText``-
    Objekt (V21-Openness-Referenz nennt ``PlcBlock`` explizit unter "Mehrsprachige
    Titel und Kommentare") — Lesen über ``read_comment`` statt ``GetAttribute``.
    """

    def run(self, project: Any) -> list[CheckResult]:
        from tia_linter.checks._tia_helpers import iter_blocks

        results: list[CheckResult] = []
        min_length = int(self.definition.params.get("min_laenge", 20))
        language = reference_language(project)

        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                comment = read_comment(block, language)
                if len(comment) < min_length:
                    results.append(
                        self._make_result(
                            path=format_path(plc_software.Name, "Programmbausteine", *group_path, block.Name),
                            description=(
                                f"Baustein '{block.Name}' hat keine oder zu kurze Kopfbeschreibung "
                                f"(mind. {min_length} Zeichen erwartet)."
                            ),
                            value=comment,
                        )
                    )
        return results


class NetzwerkBeschreibungCheck(BaseCheck):
    """Prüfpunkt 3: Netzwerke ohne Titel bzw. mit zu langer Beschreibung."""

    def run(self, project: Any) -> list[CheckResult]:
        from tia_linter.checks._tia_helpers import iter_blocks

        results: list[CheckResult] = []
        max_chars = int(self.definition.params.get("max_zeichen", 80))

        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                if get_attribute(block, "ProgrammingLanguage") in ("SCL", "STL"):
                    continue  # Netzwerk-Titel gibt es nur bei grafischen Sprachen (LAD/FBD/GRAPH)

                xml_root = export_block_xml(block)
                for index, compile_unit in enumerate(iter_compile_units(xml_root), start=1):
                    title = (compile_unit_attribute(compile_unit, "Title") or "").strip()
                    block_path = format_path(
                        plc_software.Name, "Programmbausteine", *group_path, block.Name, f"Netzwerk {index}"
                    )
                    if not title:
                        results.append(
                            self._make_result(path=block_path, description="Netzwerk hat keinen Titel.")
                        )
                    elif len(title) > max_chars:
                        results.append(
                            self._make_result(
                                path=block_path,
                                description=f"Netzwerktitel ist länger als {max_chars} Zeichen.",
                                value=title,
                            )
                        )
        return results


class AenderungshistorieCheck(BaseCheck):
    """Prüfpunkt 4: Bausteinkopf ohne Versionsinfo/Änderungshistorie."""

    def run(self, project: Any) -> list[CheckResult]:
        from tia_linter.checks._tia_helpers import iter_blocks

        results: list[CheckResult] = []

        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                author = str(get_attribute(block, "HeaderAuthor", "") or "").strip()
                version = str(get_attribute(block, "HeaderVersion", "") or "").strip()
                if not author and not version:
                    results.append(
                        self._make_result(
                            path=format_path(plc_software.Name, "Programmbausteine", *group_path, block.Name),
                            description=(
                                f"Baustein '{block.Name}' hat weder Autor noch Version im Bausteinkopf hinterlegt."
                            ),
                        )
                    )
        return results


CHECK_CLASSES = {
    "kommentare.variablen_kommentar": VariablenKommentarCheck,
    "kommentare.baustein_beschreibung": BausteinBeschreibungCheck,
    "kommentare.netzwerk_beschreibung": NetzwerkBeschreibungCheck,
    "kommentare.aenderungshistorie": AenderungshistorieCheck,
}
