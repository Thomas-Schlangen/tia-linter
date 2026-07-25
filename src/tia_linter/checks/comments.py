"""Prüfpunkte 1-4: Kommentare & Beschreibungen."""

from __future__ import annotations

from typing import Any

from tia_linter.checks._tia_helpers import (
    block_programming_language,
    compile_unit_multilingual_text,
    export_block_xml,
    format_path,
    get_attribute,
    interface_section_members,
    iter_blocks,
    iter_compile_units,
    iter_data_blocks,
    iter_plc_software,
    iter_plc_types,
    iter_tag_tables,
    normalize_member_path,
    read_comment,
    read_title,
    reference_language,
)
from tia_linter.checks.base import BaseCheck
from tia_linter.models import CheckResult
from tia_linter.project_texts import ProjectTextComments


def _all_udt_names(plc_software: Any) -> set[str]:
    """Namen aller PLC-Datentypen (UDTs) der PLC-Software — bewusst
    unabhängig von ``excluded_folders``, siehe ``VariablenKommentarCheck``-
    Docstring ("Neunter Bug"): dient nur der Klassifizierung eines
    Member-Datentyps, nicht der Auswahl, was selbst geprüft wird."""
    return {t.Name for t, _ in iter_plc_types(plc_software)}


def _all_fb_names(plc_software: Any) -> set[str]:
    """Namen aller Funktionsbausteine (FBs) der PLC-Software — bewusst
    unabhängig von ``excluded_folders``/``excluded_blocks``, analog zu
    ``_all_udt_names`` (siehe ``VariablenKommentarCheck``-Docstring,
    "Siebter"/"Neunter Bug")."""
    from Siemens.Engineering.SW.Blocks import FB

    return {block.Name for block, _ in iter_blocks(plc_software) if isinstance(block, FB)}


class VariablenKommentarCheck(BaseCheck):
    """Prüfpunkt 1a: PLC-Tags und DB-Variablen ohne Kommentar.

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

    Dritter Bug, mittlerweile durch eine grundsätzlichere Lösung ersetzt
    (siehe "Achter Bug" unten): Ursprünglich wurde hier versucht, den
    geerbten FB-Kommentar eines Instanz-DB-Members per Fallback-Lookup unter
    dem Namen der Quell-FB nachzuschlagen, wenn die Instanz-DB selbst keinen
    eigenen Kommentar hatte. Diese Lösung ist entfallen, siehe unten.

    Achter Bug/Design-Entscheidung (User-Brainstorming): Mit der Einführung
    von Prüfpunkt 1c (siehe "Siebter Bug") entstand echte Redundanz —
    Instanz-DB-Member wurden weiterhin hier geprüft (mit dem oben genannten
    FB-Fallback), *und* an der FB-Definition über Prüfpunkt 1c. Fehlte ein
    FB-Member-Kommentar komplett, entstanden zwei Befunde für dasselbe
    Grundproblem, bei mehrfach instanziierten FBs sogar mehrfach. Ein
    Kommentar auf einem FB-Interface-Member "gehört" konzeptionell zur
    FB-Definition, nicht zur einzelnen Instanz. Fix: Instanz-DBs
    (``db.GetAttribute("InstanceOfName")`` nicht leer) werden hier komplett
    übersprungen — ihre Member werden ausschließlich von Prüfpunkt 1c
    geprüft, der Fallback-Lookup entfällt vollständig. **Tradeoff:** TIA
    erlaubt es, den geerbten FB-Kommentar an einer einzelnen Instanz zu
    überschreiben — ein solcher instanzspezifischer Kommentar wird dadurch
    nicht mehr erkannt, nur der Kommentar an der FB-Definition zählt noch.
    Bewusst in Kauf genommen zugunsten von weniger Redundanz/Rauschen.

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

    Siebter Bug (User-Meldung, live an ``4805PrgManDb > Man4805_27M11``
    verifiziert): Nicht jede verschachtelte Interface-Struktur ist ein UDT
    — ``Man4805_27M11`` hat den ``DataTypeName`` ``"ManStFcPump"``, aber das
    ist der Name eines **Funktionsbausteins (FB)**, keiner PLC-Datentyp.
    ``Man4805_27M11`` ist eine **Multi-Instanz** dieses FB (dieselbe
    ``Interface.Members``-Flachklopfung mit Punktpfaden wie bei DBs/UDTs,
    aber ein technisch anderer Mechanismus) — die UDT-Erkennung fand
    ``"ManStFcPump"`` daher zu Recht nicht in ``udt_names``, wodurch alle
    Items der Multi-Instanz einzeln geprüft wurden. Fix: ``fb_names``
    (analog zu ``udt_names``, aus allen FBs der PLC-Software) wird
    zusätzlich in die Skip-Erkennung einbezogen — ein FB-typisiertes Member
    wird jetzt genauso behandelt wie ein UDT-typisiertes. Die Kommentare der
    FB-Interface-Member selbst (an der FB-Definition, nicht pro
    Verwendungsstelle) prüft der neue Prüfpunkt 1c
    (``kommentare.fb_member_kommentar``, siehe ``FbMemberKommentarCheck``) —
    der FB-Kopfkommentar selbst bleibt weiterhin Sache von Prüfpunkt 2.

    Neunter Bug (User-Meldung, nachdem viele UDTs über ``ausgeschlossene_ordner``
    von der Prüfung ausgenommen wurden — Ordner ``ProjektLib``): ``udt_names``/
    ``fb_names`` wurden bislang mit ``self.excluded_folders`` gefiltert, genau wie
    die eigentliche Iteration der zu prüfenden DBs/UDTs/FBs. Dadurch tauchte ein
    UDT aus einem ausgeschlossenen Ordner nicht mehr in ``udt_names`` auf — ein
    damit typisiertes DB-Member wurde daher nicht mehr als UDT erkannt, wodurch
    entgegen der eigentlichen Absicht wieder in seine (in TIA gar nicht
    einsehbaren) Items hinein geprüft wurde. ``ausgeschlossene_ordner`` soll aber
    nur steuern, was selbst geprüft wird — nicht, welche Datentypen dem Linter
    für die Klassifizierung ("ist das ein UDT/FB?") bekannt sind. Fix:
    ``udt_names``/``fb_names`` werden jetzt unabhängig von ``excluded_folders``/
    ``excluded_blocks`` aus **allen** UDTs/FBs der PLC-Software gebildet.
    """

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        exception_prefixes = tuple(self.definition.params.get("ausnahme_prefixe", []))
        exception_variables = frozenset(self.definition.params.get("ausnahme_variables", []))
        exception_udts = frozenset(self.definition.params.get("ausnahme_udts", []))
        language = reference_language(project)

        for plc_software in iter_plc_software(project):
            results.extend(
                self._check_tags(plc_software, language, exception_prefixes, exception_variables)
            )
            results.extend(
                self._check_db_members(
                    project, plc_software, exception_prefixes, exception_variables, exception_udts
                )
            )
        return results

    def _check_tags(
        self,
        plc_software: Any,
        language: Any,
        exception_prefixes: tuple[str, ...],
        exception_variables: frozenset[str],
    ) -> list[CheckResult]:
        """Prüft alle PLC-Tags (Variablentabellen) der PLC-Software auf Kommentar."""
        results: list[CheckResult] = []
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
                            path=format_path(plc_name, "Variablentabellen", tag_table.Name, tag_name),
                            description=f"Variable '{tag_name}' hat keinen Kommentar.",
                            value=tag_name,
                        )
                    )
        return results

    def _check_db_members(
        self,
        project: Any,
        plc_software: Any,
        exception_prefixes: tuple[str, ...],
        exception_variables: frozenset[str],
        exception_udts: frozenset[str],
    ) -> list[CheckResult]:
        """Prüft alle Global-/Array-DB-Member der PLC-Software auf Kommentar.

        Instanz-DBs werden komplett übersprungen — ihre Member gehören zur
        Interface-Definition der Quell-FB und werden ausschließlich von
        Prüfpunkt 1c geprüft (siehe Klassen-Docstring, "Achter
        Bug/Design-Entscheidung"). ``udt_names``/``fb_names`` (siehe
        ``_all_udt_names``/``_all_fb_names``) dienen hier nur der
        Klassifizierung eines Member-Datentyps, nicht der Auswahl, was selbst
        geprüft wird (siehe Klassen-Docstring, "Neunter Bug").
        """
        results: list[CheckResult] = []
        plc_name = plc_software.Name
        project_texts = ProjectTextComments.load(project)
        udt_names = _all_udt_names(plc_software)
        fb_names = _all_fb_names(plc_software)

        for db, group_path in iter_data_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
            db_name = db.Name
            if get_attribute(db, "InstanceOfName", ""):
                continue
            # Maßnahme 6 (Review-Performance.md, Befund 3.1): statt bei jedem
            # Member per Python-Generator über alle bisherigen skip_prefixes
            # zu iterieren (O(Member × UDT-Member) je DB), wird die exakte
            # Übereinstimmung als O(1)-Set-Lookup und der "...-Unterfeld"-Fall
            # als ein einziger, C-seitig implementierter
            # ``str.startswith(tuple)``-Aufruf geprüft. Beide Strukturen
            # werden nur erweitert, wenn tatsächlich ein neues UDT-/FB-Member
            # erkannt wird (seltener als jede Member-Prüfung selbst).
            skip_prefix_names: set[str] = set()
            skip_prefix_dotted: tuple[str, ...] = ()
            for member in getattr(getattr(db, "Interface", None), "Members", []):
                member_name = member.Name
                if "[" in member_name:
                    continue  # Array-Element (auch verschachtelt darunter) — Array selbst reicht
                if member_name in skip_prefix_names or member_name.startswith(skip_prefix_dotted):
                    continue  # Item innerhalb eines UDT-Members — wird von Prüfpunkt 1b geprüft

                # UDT-Erkennung MUSS vor den Ausnahme-Continues laufen (unten):
                # Sechster Bug (User-Meldung) — ein Member, das per
                # ausnahme_prefixe/ausnahme_variables von der eigenen
                # Kommentarprüfung ausgenommen wird, aber selbst UDT-typisiert
                # ist, wurde nie als Skip-Präfix registriert, weil der jeweilige
                # `continue` schon vorher griff — seine Items blieben dadurch
                # ungeschützt einzeln geprüft (live an
                # LSNTP_ServerDb > lastTimeSet, zusätzlich in ausnahme_variables
                # eingetragen, verifiziert). Die UDT-Erkennung entscheidet daher
                # jetzt unabhängig von diesen Ausnahmen, ob die Items eines
                # Members übersprungen werden — nur ob der Member *selbst* einen
                # Befund bekommt, hängt weiterhin von ausnahme_prefixe/
                # ausnahme_variables ab. DataTypeName quotet UDT-Referenzen
                # unabhängig davon, ob der Name selbst eine Quotierung bräuchte
                # (z. B. '"U_VisBit"' statt 'U_VisBit', live verifiziert) —
                # normalize_member_path() vor dem Abgleich anwenden.
                # fb_names deckt Multi-Instanz-FB-Aufrufe ab (Member-Typ ist
                # der Name eines Funktionsbausteins, nicht eines PLC-Datentyps
                # — siehe "Siebter Bug").
                data_type_name = normalize_member_path(str(get_attribute(member, "DataTypeName", "") or ""))
                if data_type_name in udt_names or data_type_name in exception_udts or data_type_name in fb_names:
                    skip_prefix_names.add(member_name)
                    skip_prefix_dotted = (*skip_prefix_dotted, member_name + ".")

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


class UdtKommentarCheck(BaseCheck):
    """Prüfpunkt 1b: PLC-Datentypen (UDTs) ohne Kommentar.

    War in der ursprünglichen Liste der Prüfpunkte kein eigener Punkt —
    ergänzt Prüfpunkt 1a um genau die Items, die dort seit dem "Vierter Bug"
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
    Prüfpunkt 1a übersprungen — ein Kommentar auf dem Array selbst reicht.
    """

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        exception_prefixes = tuple(self.definition.params.get("ausnahme_prefixe", []))
        language = reference_language(project)

        for plc_software in iter_plc_software(project):
            plc_name = plc_software.Name
            project_texts = ProjectTextComments.load(project)
            # udt_names dient hier nur der Klassifizierung verschachtelter Member
            # (ist ein Item selbst wieder UDT-typisiert?), nicht der Auswahl, welche
            # UDTs unten selbst geprüft werden — muss daher wie in
            # VariablenKommentarCheck unabhängig von ausgeschlossene_ordner ALLE
            # UDTs enthalten (siehe "Neunter Bug" dort).
            udt_names = _all_udt_names(plc_software)

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

                # Maßnahme 6 (Review-Performance.md, Befund 3.1) — siehe
                # VariablenKommentarCheck._check_db_members für die Begründung.
                skip_prefix_names: set[str] = set()
                skip_prefix_dotted: tuple[str, ...] = ()
                for member in getattr(getattr(udt, "Interface", None), "Members", []):
                    member_name = member.Name
                    if "[" in member_name:
                        continue  # Array-Element (auch verschachtelt darunter) — Array selbst reicht
                    if member_name in skip_prefix_names or member_name.startswith(skip_prefix_dotted):
                        continue  # Item innerhalb eines verschachtelten UDT-Members — eigener Durchlauf

                    # UDT-Erkennung vor dem exception_prefixe-Continue (analog zum
                    # "Sechster Bug" in VariablenKommentarCheck) — sonst würden die
                    # Items eines per Präfix ausgenommenen, aber selbst
                    # UDT-typisierten Members fälschlich einzeln geprüft, statt als
                    # zum verschachtelten UDT gehörig übersprungen zu werden.
                    # DataTypeName quotet UDT-Referenzen unabhängig davon, ob der
                    # Name selbst eine Quotierung bräuchte (z. B. '"U_VisBit"' statt
                    # 'U_VisBit', live verifiziert) — normalize_member_path() vor
                    # dem Abgleich gegen udt_names anwenden.
                    data_type_name = normalize_member_path(str(get_attribute(member, "DataTypeName", "") or ""))
                    if data_type_name in udt_names:
                        skip_prefix_names.add(member_name)
                        skip_prefix_dotted = (*skip_prefix_dotted, member_name + ".")

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
        return results


class FbMemberKommentarCheck(BaseCheck):
    """Prüfpunkt 1c: Interface-Member von Funktionsbausteinen (FBs) ohne Kommentar.

    War in der ursprünglichen Liste der Prüfpunkte kein eigener Punkt — ergänzt
    Prüfpunkt 1a um die Lücke, die durch dessen "Siebter Bug"-Fix entstanden ist
    (siehe ``VariablenKommentarCheck``): Multi-Instanz-FB-Aufrufe (z. B.
    ``Man4805_27M11`` vom Typ ``ManStFcPump``) werden dort seitdem wie
    UDT-typisierte Member behandelt — ihre Items werden nicht mehr einzeln
    geprüft. Anders als bei UDTs gab es dafür aber keinen eigenen Prüfpunkt,
    der diese Items stattdessen erfasst; dieser Prüfpunkt schließt die Lücke.

    Deckt seit dem "Achter Bug/Design-Entscheidung" in ``VariablenKommentarCheck``
    zusätzlich **alle Instanz-DB-Member** ab, nicht nur verschachtelte
    Multi-Instanzen innerhalb einer DB: Prüfpunkt 1a prüfte dort ursprünglich
    jedes Instanz-DB-Member einzeln (mit Fallback auf den FB-Kommentar), was
    zu doppelten Befunden für dasselbe Grundproblem führte (einer an der
    Instanz, einer an der FB-Definition). Instanz-DBs werden bei Prüfpunkt 1a
    daher komplett übersprungen — dieser Prüfpunkt ist jetzt die alleinige
    Quelle für Kommentar-Befunde zu FB-Interface-Membern, unabhängig davon,
    ob der FB als eigenständige Instanz-DB oder als verschachtelte
    Multi-Instanz verwendet wird. **Tradeoff:** ein an einer einzelnen
    Instanz-DB überschriebener, abweichender Kommentar wird dadurch nicht
    mehr erkannt — nur der Kommentar an der FB-Definition zählt.

    Geprüft werden **nur** die Kommentare der Interface-Member eines FB (an
    der FB-Definition selbst, nicht pro Verwendungsstelle/Instanz) — der
    Kopfkommentar des FB als Ganzes ist bereits Sache von Prüfpunkt 2
    (``kommentare.baustein_beschreibung``) und wird hier nicht erneut geprüft.

    **Live-Befund während der Implementierung:** Anders als bei
    ``DataBlock.Interface.Members`` (Prüfpunkt 1a) und ``PlcType.Interface.Members``
    (Prüfpunkt 1b) liefert ``PlcBlock.Interface.Members`` direkt auf einem FB
    **immer eine leere Liste** — verifiziert an allen 127 FBs des
    Salzmaschine-Projekts, unabhängig von Know-how-Schutz (keiner der FBs war
    geschützt). Dieselbe Einschränkung, die bereits ``styleguide.static_zugriff_extern``/
    ``styleguide.output_mehrfach_beschrieben`` dazu gezwungen hat, Interface-
    Member-Namen stattdessen aus dem XML-Export zu lesen (siehe
    ``interface_section_members`` in ``_tia_helpers.py``, Abschnitte "Static"
    bzw. "Output" der Interface-Sections). Dieser Prüfpunkt verwendet denselben
    Mechanismus für alle vier "echten" Interface-Sections eines FB (``Input``,
    ``Output``, ``InOut``, ``Static`` — ``Temp`` bewusst ausgenommen, da
    Temp-Variablen zwischen Aufrufen nicht persistieren und in der Praxis nicht
    einzeln kommentiert werden).

    Zehnter Bug (User-Meldung, live an ``01OrgPrg > lu_RcpReq``/``iou_ReqRcp``
    verifiziert): Die ursprüngliche Annahme, der XML-Export liefere pro Section
    nur die direkt deklarierten Member ohne rekursive Auflösung, war falsch für
    Multi-Instanz-Member (Member, deren eigener Datentyp ein FB/UDT mit eigenem
    Interface ist): Deren verschachteltes Sub-Interface trägt im Export
    ebenfalls eine ``<Section Name="...">`` mit demselben Namen wie die
    äußeren Sections — der Fix dafür sitzt direkt in
    ``interface_section_members`` (``_tia_helpers.py``), das jetzt beim
    Abstieg nicht mehr in ``<Member>``-Elemente hinein rekursiert. Dieser
    Prüfpunkt selbst brauchte dadurch keine Änderung, nur die zuvor falsche
    Annahme in diesem Docstring ist hiermit korrigiert: Mit dem Fix stimmt sie
    jetzt tatsächlich — jedes Ergebnis ist ein einzelnes, direkt deklariertes
    Interface-Member, keine Array-/UDT-Skip-Logik nötig.
    """

    _INTERFACE_SECTIONS = ("Input", "Output", "InOut", "Static")

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.SW.Blocks import FB

        results: list[CheckResult] = []
        exception_prefixes = tuple(self.definition.params.get("ausnahme_prefixe", []))

        for plc_software in iter_plc_software(project):
            plc_name = plc_software.Name
            project_texts = ProjectTextComments.load(project)

            for block, group_path in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                if not isinstance(block, FB):
                    continue
                fb_name = block.Name

                xml_root = export_block_xml(block, plc_software)
                member_names: set[str] = set()
                for section_name in self._INTERFACE_SECTIONS:
                    member_names |= interface_section_members(xml_root, section_name)

                for member_name in sorted(member_names):
                    if member_name.startswith(exception_prefixes):
                        continue
                    comment = project_texts.get(
                        normalize_member_path(plc_name),
                        normalize_member_path(fb_name),
                        normalize_member_path(member_name),
                    )
                    if not comment:
                        results.append(
                            self._make_result(
                                path=format_path(
                                    plc_name, "Programmbausteine", *group_path, fb_name, "Member", member_name
                                ),
                                description=f"FB-Variable '{member_name}' hat keinen Kommentar.",
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

    Elfter Bug/Design-Entscheidung (User-Meldung): Eine Kopfbeschreibung ist
    bei Datenbausteinen in der Praxis unüblich — anders als bei FB/FC/OB, wo
    sie den Zweck des Codes beschreibt, hat ein DB meist nur Daten ohne
    eigene "Funktion" zu beschreiben. Neuer Parameter ``check_db`` (Standard
    ``false``): Ist er ``false``, werden Datenbausteine (Global-, Instanz-
    und Array-DB) von dieser Prüfung komplett ausgenommen — FB/FC/OB bleiben
    unverändert geprüft. Steht er auf ``true``, werden auch DBs wie bisher
    geprüft.

    Zwölfter Bug (User-Meldung, live an FC ``40Org`` verifiziert): Der Titel
    "Mehrsprachige Titel und Kommentare" der V21-Openness-Referenz hätte es
    verraten — ``PlcBlock`` hat **zwei** unabhängige mehrsprachige Attribute,
    ``Title`` und ``Comment``, beide im Bausteinkopf des TIA-UI sichtbar,
    aber getrennt gepflegt. Diese Prüfung las bislang nur ``Comment`` — bei
    ``40Org`` war ``Comment`` für jede Sprache leer, obwohl ``Title`` die
    eigentliche, sichtbare Kopfbeschreibung "Organisation Störungen
    Allgemein" trug, wodurch der Baustein fälschlich als unbeschrieben
    gemeldet wurde. Fix: Es zählt jetzt das längere der beiden Felder
    (``Title``/``Comment``) — je nachdem, welches Feld in der Praxis für die
    Kopfbeschreibung genutzt wird.
    """

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.SW.Blocks import DataBlock

        results: list[CheckResult] = []
        min_length = int(self.definition.params.get("min_laenge", 20))
        check_db = bool(self.definition.params.get("check_db", False))
        language = reference_language(project)

        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                if not check_db and isinstance(block, DataBlock):
                    continue
                comment = read_comment(block, language)
                title = read_title(block, language)
                description_text = comment if len(comment) >= len(title) else title
                if len(description_text) < min_length:
                    results.append(
                        self._make_result(
                            path=format_path(plc_software.Name, "Programmbausteine", *group_path, block.Name),
                            description=(
                                f"Baustein '{block.Name}' hat keine oder zu kurze Kopfbeschreibung "
                                f"(mind. {min_length} Zeichen erwartet)."
                            ),
                            value=description_text,
                        )
                    )
        return results


class NetzwerkBeschreibungCheck(BaseCheck):
    """Prüfpunkt 3: Netzwerke ohne Titel bzw. mit zu langer Beschreibung.

    Dreizehnter Bug (User-Meldung: "fast alle Warnungen sind falsch"): Anders
    als einfache Attribute wie ``ProgrammingLanguage`` liegt der Netzwerktitel
    im XML-Export nicht in der ``AttributeList`` eines ``CompileUnit``,
    sondern als eigene, mehrsprachige ``MultilingualText``-Komposition im
    ``ObjectList`` — strukturell identisch zu ``PlcBlock.Title``/``.Comment``
    (siehe ``BausteinBeschreibungCheck``/"Zwölfter Bug"), nur eben als XML
    statt als Openness-Objekt gelesen. ``compile_unit_attribute(compile_unit,
    "Title")`` suchte bislang ausschließlich in der ``AttributeList`` und
    lieferte dadurch **immer** ``None``, unabhängig davon, ob ein Titel
    gepflegt war — fast jedes Netzwerk wurde daher fälschlich als "kein
    Titel" gemeldet. Fix: ``compile_unit_multilingual_text()`` liest den
    Titel gezielt für die Kultur der Projekt-Referenzsprache
    (``reference_language(project).Culture``, z. B. ``"de-DE"``) aus dem
    ``ObjectList``.
    """

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        max_chars = int(self.definition.params.get("max_zeichen", 80))
        # .Culture liefert ein System.Globalization.CultureInfo-.NET-Objekt,
        # kein System.String — str(...) für den Vergleich gegen die aus dem
        # XML gelesenen (reinen Text-)Kultur-Codes wie "de-DE" nötig, sonst
        # matcht compile_unit_multilingual_text() nie (live verifiziert:
        # ohne str() lieferte der Vergleich immer "" statt des echten Titels).
        culture = str(reference_language(project).Culture)

        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                if block_programming_language(block) in ("SCL", "STL"):
                    continue  # Netzwerk-Titel gibt es nur bei grafischen Sprachen (LAD/FBD/GRAPH)

                xml_root = export_block_xml(block, plc_software)
                for index, compile_unit in enumerate(iter_compile_units(xml_root), start=1):
                    title = compile_unit_multilingual_text(compile_unit, "Title", culture)
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
    """Prüfpunkt 4: Bausteinkopf ohne Versionsinfo/Änderungshistorie.

    Vierzehnter Bug (User-Meldung, live an FB ``01OrgPrg`` verifiziert, dort
    absichtlich weder Autor noch Version gesetzt): ``GetAttribute("HeaderVersion")``
    liefert kein ``System.String``, sondern ein ``System.Version``-.NET-Objekt,
    dessen ``ToString()`` bei einer nicht gesetzten Version ``"0.0.0.0"``
    ergibt (.NET-Standardwert des parameterlosen ``Version()``-Konstruktors) —
    ein nicht-leerer String, wodurch die Version fälschlich als "vorhanden"
    galt und praktisch **jeder** Baustein den Prüfpunkt bestand, unabhängig
    vom tatsächlichen Inhalt. Live an allen 288 Bausteinen des
    Salzmaschine-Projekts bestätigt: 234 tragen exakt ``"0.0.0.0"`` (nie
    gesetzt), echte Versionen sehen dagegen wie ``"0.1"``, ``"1.0"``,
    ``"2.1"`` aus — im TIA-UI besteht das Versionsfeld im Bausteinkopf aus
    genau zwei Zahlenfeldern, ein vierteiliger Wert wie ``"0.0.0.0"`` lässt
    sich dort gar nicht eingeben. Fix: ``"0.0.0.0"`` wird wie ein leerer
    Wert behandelt.

    Fünfzehnter Bug/Design-Entscheidung (User-Meldung, analog zu Prüfpunkt 2
    "Elfter Bug/Design-Entscheidung"): Instanz-Datenbausteine pflegen keine
    eigene Änderungshistorie — Autor/Version "gehören" konzeptionell zur
    FB-Definition, nicht zur einzelnen Instanz. Neuer Parameter ``check_idb``
    (Standard ``false``): Ist er ``false``, werden Instanz-DBs
    (``db.GetAttribute("InstanceOfName")`` nicht leer) von dieser Prüfung
    ausgenommen — Global-/Array-DBs sowie FB/FC/OB bleiben davon unberührt
    und werden weiterhin normal geprüft. Anders als bei Prüfpunkt 2s
    ``check_db`` betrifft dieser Parameter also gezielt nur Instanz-DBs,
    nicht alle Datenbausteine.
    """

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        # .NET-Standardwert von System.Version bei nicht gesetzter Version —
        # siehe Klassen-Docstring, "Vierzehnter Bug".
        unset_version = "0.0.0.0"
        check_idb = bool(self.definition.params.get("check_idb", False))

        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                if not check_idb and get_attribute(block, "InstanceOfName", ""):
                    continue
                author = str(get_attribute(block, "HeaderAuthor", "") or "").strip()
                version = str(get_attribute(block, "HeaderVersion", "") or "").strip()
                if version == unset_version:
                    version = ""
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
    "kommentare.fb_member_kommentar": FbMemberKommentarCheck,
    "kommentare.baustein_beschreibung": BausteinBeschreibungCheck,
    "kommentare.netzwerk_beschreibung": NetzwerkBeschreibungCheck,
    "kommentare.aenderungshistorie": AenderungshistorieCheck,
}
