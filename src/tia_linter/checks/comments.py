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
    iter_plc_types,
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

    Dritter Bug (User-Meldung, live gegen das Salzmaschine-Projekt
    verifiziert — z. B. Instanz-DB ``LSNTP_ServerDb``: 40 von 136 Membern
    betroffen): Ein Interface-Member einer Instanz-DB ohne eigenen,
    überschriebenen Kommentar erbt seinen Kommentar vom entsprechenden
    Member der Quell-FB (TIA-GUI-Verhalten: der geerbte Kommentar wird in
    der Instanz-DB angezeigt, bis er dort explizit überschrieben wird — dann
    gilt der Instanz-DB-eigene Kommentar). In den Projekttexten liegt der
    geerbte Kommentar unter dem ``ViewPath`` der **Quell-FB**, nicht der
    Instanz-DB — ein reiner Lookup unter dem Instanz-DB-Namen findet ihn
    daher nie. Fix: Schlägt der Lookup unter dem Instanz-DB-Namen fehl,
    wird zusätzlich unter dem Namen der Quell-FB nachgeschlagen
    (``db.GetAttribute("InstanceOfName")``, dieselbe Auflösung wie in
    ``bibliotheken.verwaiste_instanz_dbs``) — bewusst nur als Fallback
    *nach* dem eigenen Lookup, damit ein tatsächlich überschriebener
    Instanz-DB-Kommentar weiterhin Vorrang hat.

    Vierter Bug (User-Meldung): Viele Warnungen stammten von Membern, deren
    Datentyp selbst ein PLC-Datentyp (UDT) ist — jedes einzelne Item *im*
    UDT wurde hier zusätzlich zum UDT-Member selbst einzeln bemängelt.
    Analog zum bereits gelösten Array-Fall (s. o.): Ein Kommentar auf dem
    UDT-Member selbst reicht aus, die enthaltenen Items werden ab Version
    dieses Fixes von diesem Prüfpunkt nicht mehr einzeln erfasst — sie
    werden stattdessen vom neuen Prüfpunkt 1b (``kommentare.udt_kommentar``,
    siehe ``UdtKommentarCheck``) geprüft, der gezielt für PLC-Datentypen
    zuständig ist. Erkennung: Für jedes Member wird dessen ``DataTypeName``
    gegen die Namen aller UDTs der PLC-Software abgeglichen (``iter_plc_types``)
    — trifft das zu, werden alle nachfolgenden Member, deren Name mit
    ``"<dieser Membername>."`` beginnt, übersprungen (das UDT-Member selbst
    bleibt geprüft). Verschachtelte, aber nicht UDT-typisierte Structs
    (anonyme ``Struct``) bleiben wie bisher einzeln geprüft.

    Zusätzlich zu ``ausnahme_prefixe`` (Präfix-Abgleich) erlaubt
    ``ausnahme_variables`` das gezielte Ausnehmen einzelner Variablen anhand
    ihres vollständigen Namens (exakte Übereinstimmung, keine Teilstring-
    oder Präfix-Logik) — sowohl für PLC-Tags als auch für DB-Member (dort
    inkl. eines eventuellen Punktpfads, z. B. ``"Alm.Station_1"``).

    Fünfter Bug (User-Meldung): Manche System-Datentypen (u. a. bestimmte
    Siemens-Bibliothekstypen) sind in TIA Portal selbst nirgends sichtbar
    als PLC-Datentyp definiert — sie tauchen also nie in ``iter_plc_types()``
    auf und werden daher nicht automatisch als "UDT-Skip" erkannt (siehe
    "Vierter Bug"). Da es für solche Typen keine Möglichkeit gibt, ihr
    Inneres zu prüfen (weder hier noch über Prüfpunkt 1b, das ebenfalls nur
    im Projekt sichtbare UDTs findet), erlaubt ``ausnahme_udts`` das manuelle
    Ergänzen solcher Datentypnamen — bewusst nicht ``ausnahme_system_udts``
    genannt, damit Anwender darüber später auch eigene, sichtbare UDTs aus
    anderen Gründen ausnehmen können. Wirkt wie ein zusätzlicher, manuell
    gepflegter Eintrag in ``udt_names`` (siehe unten) — nur das UDT-typisierte
    Member selbst bleibt geprüft, seine (in TIA ohnehin nicht einsehbaren)
    Items werden übersprungen.
    """

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        exception_prefixes = tuple(self.definition.params.get("ausnahme_prefixe", []))
        exception_variables = frozenset(self.definition.params.get("ausnahme_variables", []))
        exception_udts = frozenset(self.definition.params.get("ausnahme_udts", []))
        language = reference_language(project)

        for plc_software in iter_plc_software(project):
            plc_name = plc_software.Name

            for tag_table in iter_tag_tables(plc_software, self.excluded_folders):
                for tag in tag_table.Tags:
                    tag_name = tag.Name
                    if tag_name.startswith(exception_prefixes):
                        continue
                    if tag_name in exception_variables:
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
            udt_names = {t.Name for t, _ in iter_plc_types(plc_software, self.excluded_folders)}

            for db, group_path in iter_data_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                db_name = db.Name
                instance_of = str(get_attribute(db, "InstanceOfName", "") or "")
                skip_prefixes: list[str] = []
                for member in getattr(getattr(db, "Interface", None), "Members", []):
                    member_name = member.Name
                    if "[" in member_name:
                        continue  # Array-Element (auch verschachtelt darunter) — Array selbst reicht
                    if any(
                        member_name == prefix or member_name.startswith(prefix + ".")
                        for prefix in skip_prefixes
                    ):
                        continue  # Item innerhalb eines UDT-Members — wird von Prüfpunkt 1b geprüft
                    if member_name.startswith(exception_prefixes):
                        continue
                    if member_name in exception_variables:
                        continue
                    norm_member = normalize_member_path(member_name)
                    comment = project_texts.get(
                        normalize_member_path(plc_name),
                        normalize_member_path(db_name),
                        norm_member,
                    )
                    if not comment and instance_of:
                        # Instanz-DB-Member ohne eigenen Kommentar erbt ihn von der
                        # Quell-FB — siehe Klassen-Docstring, "Dritter Bug".
                        comment = project_texts.get(
                            normalize_member_path(plc_name),
                            normalize_member_path(instance_of),
                            norm_member,
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

                    # DataTypeName quotet UDT-Referenzen unabhängig davon, ob der
                    # Name selbst eine Quotierung bräuchte (z. B. '"U_VisBit"' statt
                    # 'U_VisBit', live verifiziert) — normalize_member_path() vor
                    # dem Abgleich gegen udt_names/exception_udts anwenden.
                    data_type_name = normalize_member_path(str(get_attribute(member, "DataTypeName", "") or ""))
                    if data_type_name in udt_names or data_type_name in exception_udts:
                        skip_prefixes.append(member_name)
        return results


class UdtKommentarCheck(BaseCheck):
    """Prüfpunkt 1b: PLC-Datentypen (UDTs) ohne Kommentar.

    War in der ursprünglichen Liste der Prüfpunkte kein eigener Punkt —
    ergänzt Prüfpunkt 1 um genau die Items, die dort seit dem "Vierter Bug"
    genannten Fix bewusst nicht mehr geprüft werden (Items *innerhalb* eines
    UDT-typisierten Members). Geprüft werden zwei unabhängige Dinge:

    1. Der Kommentar des UDT selbst (``PlcType.Comment``) — genau wie
       ``PlcBlock.Comment`` ein mehrsprachiges ``MultilingualText``-Objekt
       (V21-Openness-Referenz nennt ``PlcType`` explizit unter "Mehrsprachige
       Titel und Kommentare"), gelesen über ``read_comment`` — live gegen
       das Salzmaschine-Projekt verifiziert (UDT ``U_SpMani``: identischer
       Text über ``read_comment`` und über die Projekttexte gefunden).
    2. Die Kommentare aller Items *innerhalb* des UDT (``PlcType.Interface.Members``)
       — wie bei DB-Membern hat ``Interface.Member`` kein eigenes
       ``Comment``-Attribut, der Kommentar kommt über dieselbe zentrale
       Projekttexte-Verwaltung (``project_texts.py``) wie bei DB-Membern;
       der generische ViewPath-Parser dort (``{Projekt}\\{PLC}\\...\\{Baustein}\\{Member}``)
       erfasst UDT-Member-Kommentare bereits transparent mit, unabhängig
       davon, ob "Baustein" ein DB oder eine UDT ist — live verifiziert
       (``PLC-Datentypen\\DataTypes\\BibAlpma\\U_VisBit\\Ena`` landet mit
       demselben Mechanismus im selben Lookup-Dict wie ein DB-Member).

    Ist ein Item selbst wieder ein UDT-typisiertes Member, wird ab dort
    bewusst nicht weiter in die Tiefe geprüft — dieses verschachtelte UDT
    wird unabhängig davon geprüft, wenn die äußere Schleife bei ihm
    ankommt (jede UDT wird einmal für sich betrachtet, nicht rekursiv über
    ihre Verwendungsstellen). Array-Elemente (``[...]``) werden wie bei
    Prüfpunkt 1 übersprungen — ein Kommentar auf dem Array selbst reicht.
    """

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        exception_prefixes = tuple(self.definition.params.get("ausnahme_prefixe", []))
        language = reference_language(project)

        for plc_software in iter_plc_software(project):
            plc_name = plc_software.Name
            project_texts = ProjectTextComments.load(project)
            udt_names = {t.Name for t, _ in iter_plc_types(plc_software, self.excluded_folders)}

            for udt, group_path in iter_plc_types(plc_software, self.excluded_folders):
                udt_name = udt.Name
                if not udt_name.startswith(exception_prefixes):
                    comment = read_comment(udt, language)
                    if not comment:
                        results.append(
                            self._make_result(
                                path=format_path(plc_name, "PLC-Datentypen", *group_path, udt_name),
                                description=f"PLC-Datentyp '{udt_name}' hat keinen Kommentar.",
                                value=udt_name,
                            )
                        )

                skip_prefixes: list[str] = []
                for member in getattr(getattr(udt, "Interface", None), "Members", []):
                    member_name = member.Name
                    if "[" in member_name:
                        continue  # Array-Element (auch verschachtelt darunter) — Array selbst reicht
                    if any(
                        member_name == prefix or member_name.startswith(prefix + ".")
                        for prefix in skip_prefixes
                    ):
                        continue  # Item innerhalb eines verschachtelten UDT-Members — eigener Durchlauf
                    if member_name.startswith(exception_prefixes):
                        continue

                    norm_member = normalize_member_path(member_name)
                    comment = project_texts.get(
                        normalize_member_path(plc_name),
                        normalize_member_path(udt_name),
                        norm_member,
                    )
                    if not comment:
                        results.append(
                            self._make_result(
                                path=format_path(
                                    plc_name, "PLC-Datentypen", *group_path, udt_name, "Member", member_name
                                ),
                                description=f"UDT-Variable '{member_name}' hat keinen Kommentar.",
                                value=member_name,
                            )
                        )

                    # DataTypeName quotet UDT-Referenzen unabhängig davon, ob der
                    # Name selbst eine Quotierung bräuchte (z. B. '"U_VisBit"' statt
                    # 'U_VisBit', live verifiziert) — normalize_member_path() vor
                    # dem Abgleich gegen udt_names anwenden.
                    data_type_name = normalize_member_path(str(get_attribute(member, "DataTypeName", "") or ""))
                    if data_type_name in udt_names:
                        skip_prefixes.append(member_name)
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
    "kommentare.udt_kommentar": UdtKommentarCheck,
    "kommentare.baustein_beschreibung": BausteinBeschreibungCheck,
    "kommentare.netzwerk_beschreibung": NetzwerkBeschreibungCheck,
    "kommentare.aenderungshistorie": AenderungshistorieCheck,
}
