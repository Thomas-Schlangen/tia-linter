"""Prüfpunkte 10-16: Programmstruktur.

Prüfpunkte 11-13 nutzen den ``CrossReferenceService``. Gegen die TIA Portal
V21 Openness-Referenz (Manual 03/2026, Abschnitt "Unter STEP 7 auf Cross
Reference Service zugreifen") verifiziert: der Dienst ist nur auf einzelnen
STEP-7-Objekten verfügbar (OB, FB, FC, DB, Instanz-DB, Globaler DB, Array-DB,
PLC-Variable, PLC-Systemkonstante, PLC-Anwenderdatentyp) — **nicht** auf der
PLC-Software als Ganzes. Entsprechend wird hier pro Tag bzw. pro Baustein
abgefragt, nicht projektweit in einem Aufruf.
"""

from __future__ import annotations

import re
from typing import Any

from tia_linter.checks._tia_helpers import (
    block_programming_language,
    compile_unit_attribute,
    compile_unit_element_count,
    compile_unit_multilingual_text,
    cross_reference_locations,
    cross_reference_referenced_top_level_names,
    export_block_xml,
    format_path,
    interface_section_member_paths,
    iter_blocks,
    iter_compile_units,
    iter_data_blocks,
    iter_plc_software,
    iter_tag_tables,
    local_variable_access_paths,
    normalize_member_path,
    reference_language,
    strip_cross_reference_prefix,
    tag_direction,
    unused_cross_reference_leaf_names,
)
from tia_linter.checks.base import BaseCheck
from tia_linter.models import CheckResult


class LeereNetzwerkeCheck(BaseCheck):
    """Prüfpunkt 10: Netzwerke ohne Inhalt (keine Programmelemente).

    User-Meldung, live an FC ``OrgPrg`` verifiziert: TIA erlaubt gemischte
    Programmiersprachen innerhalb eines Bausteins (siehe Prüfpunkt 15,
    ``GemischteSprachenCheck``) — ein einzelnes Netzwerk kann z. B. SCL sein,
    obwohl der Baustein insgesamt als FBD geführt wird (``OrgPrg``: Netzwerk
    3/8). Der Skip anhand der **Baustein**-``ProgrammingLanguage`` greift in
    diesem Fall nicht; ein SCL-Netzwerk exportiert seinen Inhalt als
    ``<StructuredText>`` statt ``<FlgNet>``/``<Part>``, wurde also von
    ``compile_unit_element_count`` fälschlich als leer (0 Elemente) gezählt.
    Fix: zusätzlicher Skip anhand der **Netzwerk**-eigenen
    ``ProgrammingLanguage``.

    Sechzehnter Bug/Design-Entscheidung (User-Auftrag): Ein leeres Netzwerk
    wird in der Praxis gelegentlich absichtlich verwendet, um mit seinem
    Netzwerktitel eine Art Kapitelüberschrift innerhalb eines Bausteins zu
    setzen (z. B. ``"=== Freigaben ==="``), ohne selbst Logik zu enthalten.
    Neuer Parameter ``ausnahme_titel_regex`` (Standard ``""`` = deaktiviert):
    Ist er gesetzt, wird ein sonst leeres Netzwerk **nicht** gemeldet, wenn
    sein Titel (gelesen wie bei Prüfpunkt 3, ``compile_unit_multilingual_text``)
    auf das konfigurierte Muster passt (``re.match``, wie bei allen anderen
    Regex-Parametern in diesem Projekt). Ein Netzwerk mit Programmelementen
    ist davon unabhängig ohnehin nie betroffen.
    """

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        title_exception_regex = self.definition.params.get("ausnahme_titel_regex", "")
        title_pattern = re.compile(title_exception_regex) if title_exception_regex else None
        culture = str(reference_language(project).Culture) if title_pattern is not None else ""

        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                if block_programming_language(block) in ("SCL", "STL"):
                    continue
                xml_root = export_block_xml(block)
                for index, compile_unit in enumerate(iter_compile_units(xml_root), start=1):
                    if compile_unit_attribute(compile_unit, "ProgrammingLanguage") in ("SCL", "STL"):
                        continue
                    if compile_unit_element_count(compile_unit) == 0:
                        if title_pattern is not None:
                            title = compile_unit_multilingual_text(compile_unit, "Title", culture)
                            if title_pattern.match(title):
                                continue
                        results.append(
                            self._make_result(
                                path=format_path(
                                    plc_software.Name, "Programmbausteine", *group_path, block.Name, f"Netzwerk {index}"
                                ),
                                description="Netzwerk ist leer (keine Programmelemente).",
                            )
                        )
        return results


class UnbenutzteVariablenCheck(BaseCheck):
    """Prüfpunkt 11: PLC-Tags ohne jegliche Referenz im Programm, unbenutzte
    Global-/Array-DB-Variablen, sowie unbenutzte FB-/FC-/OB-Interface-Member
    (nur interne Verwendung im Baustein selbst zählt).

    PLC-Tags: ``cross_reference_locations`` direkt am Tag (bestätigt
    unterstützter Objekttyp) — leer bedeutet unbenutzt.

    Global-/Array-DB-Variablen: ``CrossReferenceFilter.UnusedObjects`` am
    jeweiligen DB abgefragt (DB ist bestätigt unterstützt) — die
    zurückgegebenen ``Sources`` sind die unbenutzten Mitglieder dieses DBs.
    Instanz-DBs sind hiervon **bewusst ausgenommen** (siehe unten).

    Siebzehnter Bug (User-Meldung, live an Instanz-DB ``DB_PrgFieldbusOkDb``
    verifiziert): ``GetCrossReferences(CrossReferenceFilter.UnusedObjects)``
    liefert für eine Instanz-DB nicht ausschließlich echte Member als
    ``Source`` — manchmal liegt genau ein ``Source`` dabei, dessen ``Name``
    identisch zum Namen der DB selbst ist und dessen ``TypeName`` "Instance DB
    of <FB> [...]" lautet (``Path`` zeigt auf den Ordner der DB, nicht auf ein
    verschachteltes Member). Das ist die DB **selbst**, kein Member — der
    ursprüngliche Code behandelte jeden Source blind als DB-Variable, wodurch
    ein nicht existierendes "Member" mit demselben Namen wie die DB gemeldet
    wurde (``... > DB_PrgFieldbusOkDb > Member > DB_PrgFieldbusOkDb``).

    Achtzehnter Bug (User-Meldung, verifiziert anhand des offiziellen
    Beispielcodes der V21-Openness-Referenz, Manual 03/2026, "Querverweise
    für STEP 7 abrufen"): Die ursprüngliche Annahme, jeder ``Source`` in
    ``unused_result.Sources`` sei bereits ein fertiges, unbenutztes Member,
    war falsch — ``Sources`` ist die Wurzel eines Baums, kein flacher
    Treffer. Der Source aus dem "Siebzehnter Bug" (Name == DB-Name) ist
    genau dieser Wurzelknoten; seine ``.Children`` enthalten — rekursiv —
    die tatsächlich unbenutzten Member. Fix: ``unused_cross_reference_leaf_names()``
    (siehe ``_tia_helpers.py``) steigt rekursiv ab und liefert nur echte
    Blattknoten; Array-Elemente werden dabei übersprungen (ein einzelnes
    großes Array-Member lieferte live tausende Einzelindizes als separate
    Blätter, analog zum Array-Skip bei Prüfpunkt 1). Der vom DB-Namen
    führende Pfadanteil wird für eine lesbare Anzeige abgeschnitten
    (``DiagCpu.DNNmode`` statt ``"DB_PrgFieldbusOkDb".DiagCpu.DNNmode``).

    Neunzehnter Bug/Design-Entscheidung (User-Einwand, live verifiziert):
    Die Instanz-DB eines FB ist reiner Speicher ohne eigene Logik — ob ein
    Member "benutzt" ist, entscheidet sich im Code des FB (bzw. am
    Aufrufer), nicht in der DB. ``UnusedObjects`` an der Instanz-DB zählt
    dabei aber **jede** Referenz mit, auch externe Direktzugriffe von außen
    (z. B. ``"Instanz".Member`` aus einem anderen Baustein) — genau solche
    externen Zugriffe sind unerwünscht und werden bereits separat von
    Prüfpunkt 26 (``static_zugriff_extern``) gemeldet. Live an
    ``PlcTimeDb.ot_PlcTime`` und ``01PrgDb.lx_30M1StopGap`` verifiziert:
    beide sind sowohl intern (im eigenen FB) als auch extern referenziert —
    ``UnusedObjects`` kann diese beiden Fälle nicht unterscheiden.

    Versuch, stattdessen direkt am FB/FC/OB abzufragen, scheiterte an einer
    weiteren, live verifizierten Einschränkung: ``GetCrossReferences``
    liefert dort **keinen** Member-Baum (nur einen einzigen Root-Source = der
    Baustein selbst, ``Children`` leer) — der Member-Baum existiert
    nachweislich nur bei DB-Objekten. Und selbst die aggregierten
    ``References``/``Locations`` dieses einen Root-Sources verraten bei
    einem Zugriff auf ein *eigenes* Interface-Member weder über
    ``Location.Name`` noch ``Location.ReferencedAsName`` (beide leer), auf
    welches Member sich die Zeile bezieht — nur bei Referenzen auf fremde,
    benannte Objekte (z. B. eine andere DB) ist ``Location.Name`` gefüllt.

    Fix: FB-/FC-/OB-Interface-Member (Input/Output/InOut/Static/Temp) werden
    jetzt komplett unabhängig von CrossReferenceService/Instanz-DB geprüft —
    stattdessen wird der XML-Export des Bausteins direkt nach eigenen
    lokalen Variablenzugriffen durchsucht (``local_variable_access_paths()``,
    siehe ``_tia_helpers.py``): ``<Access Scope="LocalVariable">`` bzw.
    ``<Instance Scope="LocalVariable">`` (Multiinstanz) — live identisch
    verifiziert für SCL und FBD. Das garantiert strukturell, dass nur
    *interne* Verwendung zählt (externe Zugriffe können in den eigenen
    Netzwerken eines Bausteins gar nicht auftauchen), ohne auf
    CrossReferenceServices projektweite, intern/extern nicht
    unterscheidende Sicht angewiesen zu sein. Instanz-DBs werden von der
    Global-/Array-DB-Schleife oben deshalb jetzt bewusst übersprungen — ihre
    Member werden ausschließlich über die FB-Definition geprüft (unabhängig
    davon, wie viele Instanzen es gibt).

    Vierundzwanzigster Bug/Feature (User-Auftrag, betriebliche Praxis): DB-Member
    vom Typ UDT/Struct werden bei diesem Anwender oft als Ganzes an einen
    anderen Baustein übergeben (z. B. ``MeinFb(duStruct := "MeinDb".MeinStruct)``)
    statt feldweise einzeln zugegriffen. ``CrossReferenceService`` markiert
    dabei typischerweise nur den Struct-Knoten selbst als referenziert —
    einzelne, nicht separat angefasste Unterfelder erschienen bislang
    trotzdem als "unbenutzt" in ``UnusedObjects``, was in der Praxis als
    Fehlalarm-Rauschen empfunden wurde. Neuer Parameter
    ``unterelemente_pruefen`` (Standard ``false``): Ist ein UDT-/Struct-
    typisiertes Top-Level-Member irgendwo referenziert (auf beliebiger
    Tiefe — ``cross_reference_referenced_top_level_names()``, Filter
    ``CrossReferenceFilter.ObjectsWithReferences``), gilt die Variable als
    Ganzes als verwendet und ihre einzelnen (evtl. weiterhin ungenutzten)
    Unterfelder werden **nicht** gemeldet. Ist sie dagegen komplett
    unbenutzt (kein einziges Unterfeld referenziert), werden die
    Unterfelder trotzdem einzeln gemeldet — unabhängig vom Parameter, weil
    in diesem Fall die Detailinformation, welche Felder betroffen sind,
    nicht durch eine pauschale Übergabe abgedeckt sein kann. Bei ``true``
    bleibt es beim bisherigen, feldgranularen Verhalten ohne diese
    Pauschal-Ausnahme. Da ein skalares Member ohnehin nur ein einziges
    Blatt (sich selbst) hat, ist dafür keine UDT/Struct-vs-Skalar-
    Typunterscheidung nötig — das Verhalten reduziert sich für Skalare
    automatisch auf den bisherigen, unveränderten Fall.

    Dieselbe Pauschal-Ausnahme gilt jetzt auch für UDT-/Struct-typisierte
    FB-/FC-/OB-Interface-Member, dort aber neu über den XML-Export gelöst
    (``interface_section_member_paths()``/``local_variable_access_paths()``):
    anders als bei DBs kannte der bisherige XML-Scan nur Top-Level-Member
    (``local_variable_access_names()`` nahm ohnehin nur die erste
    ``Component`` unter ``Symbol`` — Unterfeld-Granularität existierte für
    FB/FC/OB bislang gar nicht). Beide neuen Funktionen lösen die
    verschachtelte ``<Sections>``-Deklaration bzw. verschachtelte
    ``Component``-Zugriffsketten rekursiv bis auf Blattebene auf und sind
    noch **nicht** live an einem echten verschachtelten UDT-/Struct-Zugriff
    verifiziert (siehe Docstrings in ``_tia_helpers.py``).
    """

    _INTERFACE_SECTIONS = ("Input", "Output", "InOut", "Static", "Temp")

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.CrossReference import CrossReferenceFilter, CrossReferenceService
        from Siemens.Engineering.SW.Blocks import FB, FC, OB, InstanceDB

        check_sub_items = bool(self.definition.params.get("unterelemente_pruefen", False))

        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for tag_table in iter_tag_tables(plc_software, self.excluded_folders):
                for tag in tag_table.Tags:
                    if not cross_reference_locations(tag):
                        results.append(
                            self._make_result(
                                path=format_path(plc_software.Name, "Variablentabellen", tag_table.Name, tag.Name),
                                description=f"Variable '{tag.Name}' wird im gesamten Programm nicht verwendet.",
                                value=tag.Name,
                            )
                        )

            for db, group_path in iter_data_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                if isinstance(db, InstanceDB):
                    continue  # geprüft über die FB-Definition weiter unten
                try:
                    service = db.GetService[CrossReferenceService]()
                except Exception:  # noqa: BLE001
                    service = None
                if service is None:
                    continue
                unused_result = service.GetCrossReferences(CrossReferenceFilter.UnusedObjects)
                sources = getattr(unused_result, "Sources", []) or []
                unused_names: list[str] = []
                for raw_name in unused_cross_reference_leaf_names(sources):
                    # Blattnamen sind mit dem DB-Namen als Pfadpräfix
                    # qualifiziert (z. B. '"DB_X".DiagCpu.DNNmode' oder
                    # 'DB_X.DiagCpu.DNNmode') — für eine lesbare Anzeige
                    # abschneiden, analog zum bereits an anderer Stelle
                    # üblichen Member-Pfad-Format.
                    name = normalize_member_path(strip_cross_reference_prefix(raw_name, db.Name))
                    if not name or name == db.Name:
                        continue
                    unused_names.append(name)

                if not check_sub_items and unused_names:
                    # Ist ein Top-Level-Member auf irgendeiner Tiefe
                    # referenziert (z. B. als Ganzes an einen anderen
                    # Baustein übergeben), gilt es als "verwendet" — seine
                    # weiterhin einzeln unbenutzten Unterfelder werden dann
                    # nicht gemeldet (siehe Klassendocstring,
                    # "Vierundzwanzigster Bug/Feature").
                    used_top_level = cross_reference_referenced_top_level_names(db)
                    unused_names = [
                        name for name in unused_names if name.split(".", 1)[0] not in used_top_level
                    ]

                for name in unused_names:
                    results.append(
                        self._make_result(
                            path=format_path(plc_software.Name, "Datenbaustein", *group_path, db.Name, "Member", name),
                            description=f"DB-Variable '{name}' wird im gesamten Programm nicht verwendet.",
                            value=name,
                        )
                    )

            for block, group_path in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                if not isinstance(block, (FB, FC, OB)):
                    continue
                xml_root = export_block_xml(block)
                declared_paths: dict[str, list[str]] = {}
                for section_name in self._INTERFACE_SECTIONS:
                    declared_paths.update(interface_section_member_paths(xml_root, section_name))
                if not declared_paths:
                    continue
                used_paths = local_variable_access_paths(xml_root)

                for member_name, leaf_paths in sorted(declared_paths.items()):
                    if check_sub_items:
                        unused_leaves = [path for path in leaf_paths if path not in used_paths]
                    else:
                        member_used = member_name in used_paths or any(
                            path.startswith(f"{member_name}.") for path in used_paths
                        )
                        unused_leaves = [] if member_used else leaf_paths

                    for leaf_path in unused_leaves:
                        results.append(
                            self._make_result(
                                path=format_path(
                                    plc_software.Name, "Programmbausteine", *group_path, block.Name, "Member", leaf_path
                                ),
                                description=f"Variable '{leaf_path}' wird im Baustein '{block.Name}' nirgends verwendet.",
                                value=leaf_path,
                            )
                        )
        return results


class UnbenutzteBausteineCheck(BaseCheck):
    """Prüfpunkt 11b: FBs/FCs/DBs, die von keiner Stelle aufgerufen/referenziert werden.

    ``cross_reference_locations`` direkt am Baustein (OB/FB/FC/DB sind
    bestätigt unterstützte Objekttypen) — leer bedeutet unbenutzt. OBs werden
    ausgenommen, da sie als Einstiegspunkte vom Betriebssystem und nicht von
    anderem Anwendercode aufgerufen werden.

    Sechsundzwanzigster Bug (User-Einwand, live an 7 bekannt intensiv
    genutzten Global-/Array-DBs verifiziert): ``cross_reference_locations``
    liest nur die ``References``, die direkt am Root-``SourceObject`` des
    abgefragten Objekts hängen. Bei FB/FC/Instanz-DB entspricht das genau
    dem gewünschten Signal, weil ein Aufruf (``CALL``) den Baustein/die
    Instanz-DB selbst als Ziel referenziert — live bestätigt (z. B. FB
    ``PrgFieldbusOk`` 541, FC ``BibVersion`` 0 Root-Referenzen, exakt
    passend zu tatsächlicher Verwendung; Instanz-DBs durchgängig 2
    Root-Referenzen bei genutzten FB-Instanzen). Bei einem **normalen**
    Global-/Array-DB gibt es aber keine "Aufruf"-Semantik — eine Verwendung
    bedeutet dort immer Lesen/Schreiben einzelner Member, was in der
    Openness-Baumstruktur ausschließlich unter ``.Children`` auftaucht, nie
    als direkte ``Reference`` auf das Root-``SourceObject`` der DB selbst.
    ``cross_reference_locations(db)`` lieferte dadurch für **jeden**
    Global-/Array-DB immer 0 Einträge, unabhängig von der tatsächlichen
    Nutzung — live an 7 Stichproben verifiziert (u. a. ``V01St`` mit 17
    tatsächlich benutzten Top-Level-Membern, trotzdem 0 Root-Referenzen).
    Dieser Prüfpunkt hätte dadurch **jeden** Global-/Array-DB im Projekt
    als unbenutzt gemeldet. Fix: Global-/Array-DBs (nicht Instanz-DBs)
    werden stattdessen über ``cross_reference_referenced_top_level_names()``
    geprüft (dieselbe Hilfsfunktion wie bei Prüfpunkt 11) — ein DB gilt als
    verwendet, sobald irgendein Member irgendwo referenziert ist. Live
    verifiziert: 23 → 2 Befunde (alle 21 Global-/Array-DB-Fehlalarme
    verschwunden, die verbleibenden 2 (``BibVersion``, ``LGF_Description``)
    sind echte unbenutzte FCs, z. B. ``BibVersion`` mit 0 Root-Referenzen).

    Siebenundzwanzigster Bug (User-Meldung mit selbst angelegtem Testfall,
    live an Instanz-DB ``01TestOrgPrgDb`` verifiziert — FB ``01OrgPrg`` nie
    per ``CALL`` aufgerufen, aber 2 ihrer Static-Member werden extern in
    ``01Org``/Netzwerk 6 zugegriffen): Jede Instanz-DB trägt in ihren
    Root-``Locations`` unabhängig von echter Verwendung einen permanenten
    Meta-Eintrag mit ``ReferenceType.InstanceType`` (``@<DBName> ▶ Type``),
    der nur die Typbeziehung zur eigenen FB beschreibt, keine echte
    Codestelle — dasselbe Muster, das in Runde 36 bereits bei Prüfpunkt 26
    auf **Member**-Ebene gefiltert wurde (siehe ``libraries.py``,
    ``static_zugriff_extern``), hier aber auf **Root**-Ebene der Instanz-DB
    selbst und bislang ungefiltert. Live verifiziert: ``01TestOrgPrgDb``
    (nie aufgerufen) liefert trotzdem genau 1 Root-Location — exakt dieser
    Meta-Eintrag, kein echter Treffer — wodurch ``cross_reference_locations``
    fälschlich nie leer war. Zum Vergleich liefert eine tatsächlich per
    ``CALL`` verwendete Instanz-DB (``DB_PrgFieldbusOkDb``) 2 Locations: den
    echten Aufruf (``ReferenceType.UsedBy``, ``@OrgPrg ▶ NW12 (Aufruf
    Feldbus Diagnose)``) plus denselben Meta-Eintrag. Fix: Bei Instanz-DBs
    werden ``InstanceType``-Locations vor der Verwendungsprüfung
    herausgefiltert — übrig bleiben nur echte Aufrufstellen.
    """

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.CrossReference import ReferenceType
        from Siemens.Engineering.SW.Blocks import OB, DataBlock, InstanceDB

        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                if isinstance(block, OB):
                    continue
                if isinstance(block, DataBlock) and not isinstance(block, InstanceDB):
                    is_used = bool(cross_reference_referenced_top_level_names(block))
                elif isinstance(block, InstanceDB):
                    locations = cross_reference_locations(block)
                    is_used = any(
                        getattr(loc, "ReferenceType", None) != ReferenceType.InstanceType for loc in locations
                    )
                else:
                    is_used = bool(cross_reference_locations(block))
                if not is_used:
                    if isinstance(block, InstanceDB):
                        description = f"Baustein '{block.Name}' wird an keinem FB verwendet."
                    else:
                        description = f"Baustein '{block.Name}' wird von keiner Stelle im Projekt referenziert."
                    results.append(
                        self._make_result(
                            path=format_path(plc_software.Name, "Programmbausteine", *group_path, block.Name),
                            description=description,
                            value=block.Name,
                        )
                    )
        return results


class EingaengeGelesenCheck(BaseCheck):
    """Prüfpunkt 12: Eingangs-Tags, die im Programm nie gelesen werden."""

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.CrossReference import Access

        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for tag_table in iter_tag_tables(plc_software, self.excluded_folders):
                for tag in tag_table.Tags:
                    if tag_direction(tag) != "I":
                        continue
                    locations = cross_reference_locations(tag)
                    has_read = any(getattr(loc, "Access", None) == Access.Read for loc in locations)
                    if not has_read:
                        results.append(
                            self._make_result(
                                path=format_path(plc_software.Name, "Variablentabellen", tag_table.Name, tag.Name),
                                description=f"Eingang '{tag.Name}' wird im Programm nie gelesen.",
                                value=tag.Name,
                            )
                        )
        return results


class EingaengeNichtBeschriebenCheck(BaseCheck):
    """Prüfpunkt 12b: Eingangs-Tags dürfen im Programm nicht beschrieben werden.

    Ergänzung zu Prüfpunkt 12 (liest nur, ob ein Eingang gelesen wird) — war
    in der ursprünglichen Prüfpunkte-Liste kein eigener Punkt, ist aber eine
    der grundlegendsten SPS-Programmierregeln: Eingänge werden jeden Zyklus
    vom Prozessabbild aus der Hardware überschrieben, ein Schreibzugriff aus
    dem Anwenderprogramm wird beim nächsten Zyklus also ohnehin wieder
    verworfen — er täuscht daher bestenfalls einen Wert vor, der real nie
    ankommt, und deutet meist auf eine Verwechslung mit einem Merker hin.
    """

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.CrossReference import Access

        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for tag_table in iter_tag_tables(plc_software, self.excluded_folders):
                for tag in tag_table.Tags:
                    if tag_direction(tag) != "I":
                        continue
                    locations = cross_reference_locations(tag)
                    write_count = sum(1 for loc in locations if getattr(loc, "Access", None) == Access.Write)
                    if write_count > 0:
                        results.append(
                            self._make_result(
                                path=format_path(plc_software.Name, "Variablentabellen", tag_table.Name, tag.Name),
                                description=(
                                    f"Eingang '{tag.Name}' wird im Programm an {write_count} Stelle(n) "
                                    "beschrieben — Eingänge dürfen nicht beschrieben werden."
                                ),
                                value=str(write_count),
                            )
                        )
        return results


class AusgaengeMehrfachSchreibenCheck(BaseCheck):
    """Prüfpunkt 13: Ausgangs-Tags, die an mehreren Stellen beschrieben werden."""

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.CrossReference import Access

        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for tag_table in iter_tag_tables(plc_software, self.excluded_folders):
                for tag in tag_table.Tags:
                    if tag_direction(tag) != "Q":
                        continue
                    locations = cross_reference_locations(tag)
                    write_count = sum(1 for loc in locations if getattr(loc, "Access", None) == Access.Write)
                    if write_count > 1:
                        results.append(
                            self._make_result(
                                path=format_path(plc_software.Name, "Variablentabellen", tag_table.Name, tag.Name),
                                description=f"Ausgang '{tag.Name}' wird an {write_count} Stellen beschrieben.",
                                value=str(write_count),
                            )
                        )
        return results


class AwlCodeCheck(BaseCheck):
    """Prüfpunkt 14: Bausteine, die noch in AWL/STL programmiert sind.

    Ein Baustein, dessen Grundsprache KOP/FUP ist, kann trotzdem einzelne
    Netzwerke enthalten, die (z. B. per Copy&Paste) in AWL umgeschaltet
    wurden — ``block.ProgrammingLanguage`` bleibt dabei auf der
    Grundsprache stehen und meldet nichts. Prüfpunkt 15
    (``GemischteSprachenCheck``) erkennt genau diesen Fall bereits über den
    XML-Export je ``CompileUnit``; dieselbe Abfrage wird hier wiederverwendet,
    um auch einzelne AWL-Netzwerke innerhalb eines sonst nicht-AWL-Bausteins
    zu melden.
    """

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                block_language = block_programming_language(block)
                if block_language == "STL":
                    results.append(
                        self._make_result(
                            path=format_path(plc_software.Name, "Programmbausteine", *group_path, block.Name),
                            description=f"Baustein '{block.Name}' ist in AWL (STL) programmiert.",
                        )
                    )
                    continue
                if block_language == "SCL":
                    continue
                xml_root = export_block_xml(block)
                for index, compile_unit in enumerate(iter_compile_units(xml_root), start=1):
                    if compile_unit_attribute(compile_unit, "ProgrammingLanguage") == "STL":
                        results.append(
                            self._make_result(
                                path=format_path(
                                    plc_software.Name, "Programmbausteine", *group_path, block.Name, f"Netzwerk {index}"
                                ),
                                description=f"Netzwerk {index} in Baustein '{block.Name}' ist in AWL (STL) programmiert.",
                            )
                        )
        return results


class GemischteSprachenCheck(BaseCheck):
    """Prüfpunkt 15: Innerhalb eines Bausteins werden mehrere Sprachen gemischt.

    Neuer Parameter `scl_in_fup_ignorieren` (User-Auftrag, betriebliche Praxis;
    Standard `true`): SCL-Netzwerke innerhalb eines ansonsten in FUP (TIA-XML-
    Wert ``"FBD"``) programmierten Bausteins sind bei diesem Anwender weit
    verbreitet und gelten nicht als Problem. Ist die Baustein-Grundsprache FUP
    und die gefundene Sprachmischung genau {FUP, SCL}, wird der Baustein bei
    `true` nicht gemeldet. Jede andere Kombination (z. B. KOP+SCL, FUP+AWL,
    oder mehr als zwei Sprachen) bleibt unabhängig vom Parameter gemeldet. Bei
    `false` bleibt das bisherige Verhalten (jede Mischung wird gemeldet)
    erhalten.
    """

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        ignore_scl_in_fup = bool(self.definition.params.get("scl_in_fup_ignorieren", True))

        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                block_language = block_programming_language(block)
                if block_language in ("SCL", "STL"):
                    continue
                xml_root = export_block_xml(block)
                languages = {
                    compile_unit_attribute(cu, "ProgrammingLanguage")
                    for cu in iter_compile_units(xml_root)
                }
                languages.discard(None)
                if len(languages) <= 1:
                    continue
                if ignore_scl_in_fup and block_language == "FBD" and languages == {"FBD", "SCL"}:
                    continue
                results.append(
                    self._make_result(
                        path=format_path(plc_software.Name, "Programmbausteine", *group_path, block.Name),
                        description=f"Baustein '{block.Name}' mischt mehrere Sprachen: {', '.join(sorted(languages))}.",
                        value=", ".join(sorted(languages)),
                    )
                )
        return results


class MaxNetzwerkElementeCheck(BaseCheck):
    """Prüfpunkt 16: Netzwerke mit mehr Elementen als der Schwellenwert."""

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        max_elements = int(self.definition.params.get("max_elemente", 50))

        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                if block_programming_language(block) in ("SCL", "STL"):
                    continue
                xml_root = export_block_xml(block)
                for index, compile_unit in enumerate(iter_compile_units(xml_root), start=1):
                    count = compile_unit_element_count(compile_unit)
                    if count > max_elements:
                        results.append(
                            self._make_result(
                                path=format_path(
                                    plc_software.Name, "Programmbausteine", *group_path, block.Name, f"Netzwerk {index}"
                                ),
                                description=f"Netzwerk hat {count} Elemente (Schwellenwert: {max_elements}).",
                                value=str(count),
                            )
                        )
        return results


CHECK_CLASSES = {
    "programmstruktur.leere_netzwerke": LeereNetzwerkeCheck,
    "programmstruktur.unbenutzte_variablen": UnbenutzteVariablenCheck,
    "programmstruktur.unbenutzte_bausteine": UnbenutzteBausteineCheck,
    "programmstruktur.eingaenge_gelesen": EingaengeGelesenCheck,
    "programmstruktur.eingaenge_nicht_beschrieben": EingaengeNichtBeschriebenCheck,
    "programmstruktur.ausgaenge_mehrfach_schreiben": AusgaengeMehrfachSchreibenCheck,
    "programmstruktur.awl_code": AwlCodeCheck,
    "programmstruktur.gemischte_sprachen": GemischteSprachenCheck,
    "programmstruktur.max_netzwerk_elemente": MaxNetzwerkElementeCheck,
}
