"""Interne Hilfsfunktionen zum Traversieren eines TIA-Openness-Projekts.

Wird von allen ``checks/*.py``-Modulen verwendet — die Projekt-Objektstruktur
ist über die Kategorien hinweg identisch (PLC-Software-Container finden, alle
Bausteine/Tag-Tabellen rekursiv durchlaufen, Pfade einheitlich formatieren).
"""

from __future__ import annotations

import logging
import tempfile
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Iterator

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

logger = logging.getLogger(__name__)


def format_path(*parts: str) -> str:
    """Baut einen Befund-Pfad im projektweit einheitlichen Format
    ``Teil1 > Teil2 > ...`` (siehe README, Abschnitt "Pfad-Format")."""
    return " > ".join(str(p) for p in parts if p)


def leaf_messages(messages: Any) -> list[Any]:
    """Flacht einen rekursiv verschachtelten ``Messages``-Baum auf die
    Blattmeldungen ab.

    Sowohl ``UpdateCheckResultMessage`` (Prüfpunkt 22, Bibliotheks-Update-
    Check) als auch ``CompilerResultMessage`` (Prüfpunkt 21, Kompilierfehler)
    liefern laut V21-Openness-Referenz keine flache Meldungsliste, sondern
    rekursiv verschachtelte ``Messages`` — nur die Blattmeldungen (kein
    eigenes ``Messages``) sind die tatsächlich anzuzeigenden Einzelbefunde."""
    leaves: list[Any] = []
    for message in messages or []:
        children = list(getattr(message, "Messages", []) or [])
        if children:
            leaves.extend(leaf_messages(children))
        else:
            leaves.append(message)
    return leaves


def iter_plc_software(project: Any) -> Iterator[Any]:
    """Liefert alle PLC-Software-Container (``PlcSoftware``) des Projekts."""
    from Siemens.Engineering.HW.Features import SoftwareContainer
    from Siemens.Engineering.SW import PlcSoftware

    for device in project.Devices:
        for device_item in device.DeviceItems:
            container = device_item.GetService[SoftwareContainer]()
            if container is not None and isinstance(container.Software, PlcSoftware):
                yield container.Software


def iter_plc_targets(project: Any) -> Iterator[tuple[Any, Any, Any]]:
    """Liefert ``(plc_software, device_item, device)``-Tripel — ``device_item``
    ist das Hardware-Objekt (CPU), das die jeweilige PLC-Software hostet, für
    Hardware-/Safety-/Zertifikats-Prüfungen, die am ``DeviceItem`` statt an
    der Software ansetzen (``GetService[SafetyAdministration]()`` u. Ä.).
    ``device`` ist die umgebende ``Device``-Station (aus ``project.Devices``,
    korrekt typisiert) — wird zusätzlich mitgeliefert, weil
    ``device_item.Parent`` beim ersten Testlauf gegen ein echtes Projekt nur
    ein generisches ``IEngineeringObject`` ohne ``.DeviceItems``-Zugriff
    geliefert hat (bekannte Openness-Einschränkung: Navigations-Properties
    liefern oft nur die Basisschnittstelle statt des konkreten Typs)."""
    from Siemens.Engineering.HW.Features import SoftwareContainer
    from Siemens.Engineering.SW import PlcSoftware

    for device in project.Devices:
        for device_item in device.DeviceItems:
            container = device_item.GetService[SoftwareContainer]()
            if container is not None and isinstance(container.Software, PlcSoftware):
                yield container.Software, device_item, device


_ET200SP_BUS_ADAPTER_POSITION = 127


def count_additional_hardware_modules(device: Any) -> int:
    """Zählt die zusätzlich zur CPU konfigurierten Hardware-Module eines
    ``Device`` (für Prüfpunkt 17, ``hardware.hardware_vorhanden``).

    ``device.DeviceItems`` enthält daneben immer strukturelle Elemente, die
    TIA selbst anlegt und die kein echtes I/O-Modul darstellen: den
    Baugruppenträger (``Rack_0``) sowie — bei ET200SP-Stationen — genau ein
    Busadapter/Schnittstellenmodul (belegt konstant Positionsnummer 127,
    unabhängig vom konkreten Adaptertyp) und genau ein
    Server-/Abschlussmodul (belegt immer die höchste "normale" Positionsnummer,
    da es physisch das letzte Modul im Baugruppenträger sein muss). Ohne
    Herausrechnen dieser drei Elementarten kann ``module_count`` bei einer
    ET200SP-Station selbst ganz ohne zusätzliche I/O-Module nie unter 2-3
    fallen — Prüfpunkt 17 hätte dadurch nie anschlagen können (live
    verifiziert an einem eigens angelegten CPU-only-Testprojekt ohne jede
    I/O-Hardware, siehe review_fortschritt.md Runde 44)."""
    from Siemens.Engineering.HW.Features import SoftwareContainer
    from Siemens.Engineering.SW import PlcSoftware

    is_et200sp = False
    candidates: list[tuple[int, Any]] = []
    for index, device_item in enumerate(device.DeviceItems):
        type_identifier = str(get_attribute(device_item, "TypeIdentifier", "") or "")
        if type_identifier.startswith("System:Rack"):
            if "ET200SP" in type_identifier:
                is_et200sp = True
            continue

        container = device_item.GetService[SoftwareContainer]()
        if container is not None and isinstance(container.Software, PlcSoftware):
            continue  # CPU selbst

        position = get_attribute(device_item, "PositionNumber", None)
        if position == _ET200SP_BUS_ADAPTER_POSITION:
            continue  # Busadapter/Schnittstellenmodul: fester ET200SP-Sonderslot

        candidates.append((position if isinstance(position, int) else index, device_item))

    if is_et200sp and candidates:
        # Höchste "normale" Positionsnummer ist bei ET200SP immer das
        # zwingende Server-/Abschlussmodul, kein optionales I/O-Modul.
        candidates.sort(key=lambda item: item[0])
        candidates.pop()

    return len(candidates)


def _normalize_excluded(excluded_folders: Iterable[str]) -> frozenset[str]:
    """Normalisiert Ordnernamen für den Vergleich ohne Berücksichtigung von
    Groß-/Kleinschreibung (siehe ``ausgeschlossene_ordner`` in der Config)."""
    return frozenset(name.casefold() for name in excluded_folders)


def iter_blocks(
    plc_software: Any,
    excluded_folders: Iterable[str] = (),
    excluded_blocks: Iterable[str] = (),
) -> Iterator[tuple[Any, list[str]]]:
    """Durchläuft rekursiv alle Bausteine (FB/FC/OB/DB) einer PLC-Software und
    liefert je Baustein ein Tupel ``(block, gruppenpfad)``. ``gruppenpfad``
    sind die Namen der durchlaufenen Ordner/Gruppen (ohne den Baustein selbst,
    ohne den PLC-Namen) — für die Root-Ebene eine leere Liste.

    ``excluded_folders`` — Ordnernamen (aus ``ausgeschlossene_ordner`` in der
    Config), deren Inhalt inklusive aller Unterordner komplett übersprungen
    wird: Sobald eine Gruppe passt, wird gar nicht erst in sie hinabgestiegen,
    wodurch auch verschachtelte Unterordner automatisch ausgeschlossen sind.

    ``excluded_blocks`` — Bausteinnamen (aus ``ausgeschlossene_bausteine`` in
    der Config), die unabhängig davon, in welchem Ordner sie liegen, komplett
    übersprungen werden — der Baustein taucht dann in keinem einzigen
    Prüfpunkt mehr auf (weder Namens- noch Inhaltsprüfung), da alle
    Check-Module ausschließlich über diese Funktion (bzw. ``iter_data_blocks``)
    an Bausteine gelangen.
    """
    excluded_group_names = _normalize_excluded(excluded_folders)
    excluded_block_names = _normalize_excluded(excluded_blocks)

    def _walk(block_group: Any, path: list[str]) -> Iterator[tuple[Any, list[str]]]:
        for block in block_group.Blocks:
            if block.Name.casefold() in excluded_block_names:
                continue
            yield block, path
        for subgroup in getattr(block_group, "Groups", []):
            if subgroup.Name.casefold() in excluded_group_names:
                continue
            yield from _walk(subgroup, [*path, subgroup.Name])

    yield from _walk(plc_software.BlockGroup, [])


def iter_data_blocks(
    plc_software: Any,
    excluded_folders: Iterable[str] = (),
    excluded_blocks: Iterable[str] = (),
) -> Iterator[tuple[Any, list[str]]]:
    """Wie ``iter_blocks``, aber nur Datenbausteine (Global-DB, Instanz-DB,
    Array-DB) — Openness kennt keine gemeinsame Klasse ``DB``, alle drei
    leiten von ``Siemens.Engineering.SW.Blocks.DataBlock`` ab."""
    from Siemens.Engineering.SW.Blocks import DataBlock

    for block, path in iter_blocks(plc_software, excluded_folders, excluded_blocks):
        if isinstance(block, DataBlock):
            yield block, path


def iter_tag_tables(plc_software: Any, excluded_folders: Iterable[str] = ()) -> Iterator[Any]:
    """Durchläuft rekursiv alle Variablentabellen einer PLC-Software (inkl.
    Untergruppen). ``excluded_folders`` wirkt wie bei ``iter_blocks``."""
    excluded = _normalize_excluded(excluded_folders)

    def _walk(tag_table_group: Any) -> Iterator[Any]:
        for tag_table in tag_table_group.TagTables:
            yield tag_table
        for subgroup in getattr(tag_table_group, "Groups", []):
            if subgroup.Name.casefold() in excluded:
                continue
            yield from _walk(subgroup)

    yield from _walk(plc_software.TagTableGroup)


def iter_plc_types(
    plc_software: Any, excluded_folders: Iterable[str] = ()
) -> Iterator[tuple[Any, list[str]]]:
    """Durchläuft rekursiv alle PLC-Datentypen (UDTs) einer PLC-Software und
    liefert je UDT ein Tupel ``(plc_type, gruppenpfad)`` — analog zu
    ``iter_blocks``/``iter_tag_tables``. ``excluded_folders`` wirkt wie dort.

    Openness-Referenz (Manual 03/2026, "Auf PLC-Datentypen und
    Datentypgruppen zugreifen"): ``plc_software.TypeGroup`` (``PlcTypeSystemGroup``)
    mit ``.Types`` (``PlcTypeComposition``, UDTs auf dieser Ebene) und
    ``.Groups`` (``PlcTypeUserGroupComposition``, Unterordner, rekursiv mit
    denselben zwei Eigenschaften) — strukturell identisch zu
    ``BlockGroup``/``TagTableGroup``.
    """
    excluded = _normalize_excluded(excluded_folders)

    def _walk(type_group: Any, path: list[str]) -> Iterator[tuple[Any, list[str]]]:
        for plc_type in type_group.Types:
            yield plc_type, path
        for subgroup in getattr(type_group, "Groups", []):
            if subgroup.Name.casefold() in excluded:
                continue
            yield from _walk(subgroup, [*path, subgroup.Name])

    yield from _walk(plc_software.TypeGroup, [])


def tag_direction(tag: Any) -> str | None:
    """Liefert ``'I'``/``'Q'`` je nach logischer Adresse des Tags (z. B.
    ``%I0.0``/``%Q4.1``), oder ``None`` wenn das Tag keine feste Adresse hat
    (z. B. rein interne Merker ohne Peripherie-Bezug)."""
    address = str(get_attribute(tag, "LogicalAddress", "") or "").lstrip("%")
    if address[:1] in ("I", "Q"):
        return address[0]
    return None


def get_attribute(obj: Any, name: str, default: Any = None) -> Any:
    """``GetAttribute`` mit Fallback — manche Openness-Objekte werfen bei
    einem auf diesem Objekttyp nicht vorhandenen Attributnamen eine
    .NET-Exception statt ``None`` zurückzugeben."""
    try:
        value = obj.GetAttribute(name)
    except Exception:  # noqa: BLE001 — .NET-Exception, Typ variiert je nach Attribut/TIA-Version
        logger.debug("GetAttribute('%s') nicht verfügbar, verwende Standardwert.", name, exc_info=True)
        return default
    return default if value is None else value


def block_programming_language(block: Any) -> str | None:
    """Liefert die Baustein-Grundsprache (``GetAttribute("ProgrammingLanguage")``)
    als reinen Python-String (``"FBD"``, ``"SCL"``, ``"STL"``, ...), oder
    ``None`` wenn nicht ermittelbar.

    Achtundzwanzigster Bug (live an Baustein ``OrgPrg`` verifiziert):
    ``GetAttribute("ProgrammingLanguage")`` liefert kein
    ``System.String``, sondern ein
    ``Siemens.Engineering.SW.Blocks.ProgrammingLanguage``-.NET-Enum-Objekt
    (``repr`` zeigt ``<ProgrammingLanguage.FBD: 3>``) — ein Vergleich wie
    ``get_attribute(block, "ProgrammingLanguage") == "STL"`` oder
    ``in ("SCL", "STL")`` ist dadurch **immer** ``False``, unabhängig von
    der tatsächlichen Sprache. Live bestätigt: ``str(...)`` liefert
    zuverlässig den reinen Namen (``"FBD"``, ``"SCL"``, ``"DB"``, ...),
    identisch zu den bereits als Text vorliegenden Netzwerk-eigenen
    ``ProgrammingLanguage``-Werten aus dem XML-Export
    (``compile_unit_attribute``). Dasselbe Muster (.NET-Objekt statt
    ``System.String`` an einer Stelle, die einen reinen Text erwartet) trat
    bereits bei ``reference_language(project).Culture`` auf (siehe
    ``comments.py``, ``SprachenKonsistentCheck``) — dort schon korrekt mit
    ``str(...)`` behoben, hier aber lange unbemerkt, weil in diesem Projekt
    (Salzmaschine) offenbar nie ein Baustein existierte, dessen Grundsprache
    tatsächlich SCL oder STL ist (die betroffenen Skips liefen dadurch immer
    ins Leere, ohne dass es auffiel) — betraf u. a. Prüfpunkt 10, 14, 15, 16
    und den Kommentar-Check ``SprachenKonsistentCheck``.
    """
    value = get_attribute(block, "ProgrammingLanguage")
    return None if value is None else str(value)


def reference_language(project: Any) -> Any:
    """Liefert die Referenzsprache des Projekts (``Siemens.Engineering.Language``).

    Dieselbe Sprache, die bereits an anderer Stelle als "die maßgebliche
    Projektsprache" verwendet wird (Prüfpunkt 24 ``SprachenKonsistentCheck``,
    Projekttexte-Export in ``project_texts.py``) — hier als ``Language``-Objekt
    statt nur dessen ``Culture``, weil ``MultilingualTextItemComposition.Find``
    (siehe ``multilingual_text``) ein ``Language``-Objekt erwartet, keine
    ``CultureInfo``."""
    return project.LanguageSettings.ReferenceLanguage


def multilingual_text(value: Any, language: Any) -> str:
    """Liest den Text eines ``Siemens.Engineering.MultilingualText``-Objekts
    für eine bestimmte Sprache.

    TIA Portal ist grundsätzlich mehrsprachig: viele ``Comment``-/``Title``-
    Attribute (u. a. ``PlcTag.Comment``, ``PlcBlock.Comment``/``.Title`` — laut
    V21-Openness-Referenz, Abschnitt "Umgang mit mehrsprachigen Texten",
    explizit als Beispiele genannt) liefern kein ``System.String``, sondern ein
    ``MultilingualText``-Objekt mit einem ``MultilingualTextItem`` pro Sprache.
    Der Text für eine bestimmte Sprache ist nur über
    ``multilingualText.Items.Find(<Language>).Text`` erreichbar — ein
    ``GetAttribute("Comment")``- oder naiver ``str(...)``-Zugriff auf das
    ``MultilingualText``-Objekt selbst liefert **nicht** den Text der
    gewünschten Sprache (das war der ursprüngliche Bug: jede Variable wurde
    als unkommentiert gemeldet, weil so nie ein echter Text gefunden wurde —
    identisch zu einem bereits im Schwesterprojekt ``tia-tag-exporter``
    gelösten Problem).

    Kein ``MultilingualTextItem`` für ``language`` vorhanden (oder das
    ``MultilingualText``-Objekt selbst ist ``None``) -> ``""``, der Kommentar
    fehlt für diese Sprache dann wirklich, statt dass die Prüfung abstürzt.
    """
    if value is None:
        return ""
    items = getattr(value, "Items", None)
    if items is None:
        return ""
    try:
        item = items.Find(language)
    except Exception:  # noqa: BLE001 — .NET-Exception, z. B. Sprache nicht im Projekt
        logger.debug("MultilingualTextItem für Sprache '%s' nicht auffindbar.", language, exc_info=True)
        return ""
    if item is None:
        return ""
    text = getattr(item, "Text", None)
    return str(text).strip() if text else ""


def read_comment(obj: Any, language: Any) -> str:
    """Liest das (mehrsprachige) ``Comment``-Attribut eines Openness-Objekts
    für ``language`` (siehe ``multilingual_text``/``reference_language``).

    ``Comment`` wird als typisierte .NET-Property gelesen (nicht über
    ``GetAttribute`` — das liefert für ``MultilingualText``-Properties nicht
    zuverlässig den erwarteten Wert, siehe ``multilingual_text``). Objekte
    ohne ``Comment``-Attribut liefern ``""`` statt einer Exception."""
    try:
        comment = obj.Comment
    except Exception:  # noqa: BLE001 — Objekttyp hat evtl. kein Comment-Attribut
        logger.debug("Kein 'Comment'-Attribut auf Objekt vom Typ %s.", type(obj).__name__, exc_info=True)
        return ""
    return multilingual_text(comment, language)


def read_title(obj: Any, language: Any) -> str:
    """Liest das (mehrsprachige) ``Title``-Attribut eines Openness-Objekts
    für ``language`` (siehe ``multilingual_text``/``reference_language``).

    User-Meldung, live an FC ``40Org`` verifiziert: ``PlcBlock`` hat laut
    V21-Openness-Referenz ("Mehrsprachige Titel und Kommentare") zwei
    unabhängige mehrsprachige Attribute, ``Title`` **und** ``Comment`` — im
    TIA-UI beide im Bausteinkopf sichtbar, aber getrennt gepflegt. In der
    Praxis steht die eigentliche Kurzbeschreibung eines Bausteins oft im
    ``Title`` (z. B. ``40Org``: ``Comment`` leer für jede Sprache, ``Title``
    trägt "Organisation Störungen Allgemein"), nicht im ``Comment``. Objekte
    ohne ``Title``-Attribut liefern ``""`` statt einer Exception."""
    try:
        title = obj.Title
    except Exception:  # noqa: BLE001 — Objekttyp hat evtl. kein Title-Attribut
        logger.debug("Kein 'Title'-Attribut auf Objekt vom Typ %s.", type(obj).__name__, exc_info=True)
        return ""
    return multilingual_text(title, language)


def normalize_member_path(name: str) -> str:
    """Entfernt Anführungszeichen, die TIA um Namenssegmente setzt, die keine
    gültigen "einfachen" Bezeichner sind (z. B. weil sie mit einer Ziffer
    beginnen — ``member.Name`` liefert dann z. B. ``Alm."4805_15A1"`` statt
    ``Alm.4805_15A1``, live an einem verschachtelten Struct-Member im
    Salzmaschine-Projekt verifiziert).

    Jedes Punkt-getrennte Segment eines Member-Pfads wird unabhängig
    behandelt, da bei verschachtelten Struct-Membern immer nur einzelne
    Segmente betroffen sein können. Die ``ViewPath``-Segmente aus
    ``Project.ExportProjectTexts()`` (siehe ``project_texts.py``) sind dagegen
    immer unquotiert — ohne diese Normalisierung matcht ein quotiertes
    Namenssegment nie einen Kommentar aus den Projekttexten, obwohl einer
    hinterlegt ist. Identisches, bereits im Schwesterprojekt
    ``tia-tag-exporter`` gelöstes Problem (dort
    ``extractor.py::_normalize_member_path``), hier zusätzlich auf PLC-/
    DB-Namen anwendbar (nicht nur auf Member-Pfade), da dieselbe
    Quotierungsregel für jeden nicht "einfachen" Bezeichner gilt.
    """
    return ".".join(segment.strip('"') for segment in name.split("."))


def _local_name(tag: str) -> str:
    """Elementname ohne XML-Namespace-Präfix (``{ns}Tag`` -> ``Tag``)."""
    return tag.rsplit("}", 1)[-1]


def release_dotnet_objects() -> None:
    """Erzwingt eine .NET-Garbage-Collection.

    Beim ersten Testlauf gegen ein echtes Projekt (288 Bausteine) ist
    ``run_lint`` bei Check 31/40 mit
    ``Siemens.Engineering.EngineeringOutOfMemoryException: The maximum
    number (500000) of instances for this TIA-Portal has been exceeded``
    abgestürzt — außerhalb der Per-Check-Fehlerisolation, da die Exception
    tief in pythonnet selbst auftrat. Ursache: TIA Portal Openness zählt
    intern offene Instanz-Handles (RCW-gewrappte Engineering-Objekte, z. B.
    aus ``CrossReferenceService``-Ergebnisbäumen oder Baustein-Exports) pro
    Session und wirft ab diesem harten Limit die Exception — Pythons eigenes
    Referenzcounting reicht nicht, die zugrunde liegenden .NET-Objekte werden
    erst bei einem tatsächlichen .NET-GC-Lauf freigegeben, den ein langer
    Headless-Prozess von sich aus zu selten auslöst, um mit der Anzahl der
    erzeugten Objekte Schritt zu halten.

    ``runner.py`` ruft dies nach jedem einzelnen Check auf. Zusätzlich rufen
    Checks mit projektweiten CrossReference-Schleifen (Prüfpunkte 11a/11b/
    12a/12b/13, siehe ``structure.py``) dies **innerhalb** der Schleife alle
    ``gc_interval`` verarbeitete Objekte auf — bei großen Projekten (mehrere
    Tausend Tags/Bausteine) kann sonst bereits ein einzelner Check das
    500.000-Handle-Limit reißen, bevor der Check zu Ende ist und der äußere
    Aufruf überhaupt greift (live beobachtet, siehe Analysebericht
    ``Review-Performance.md``).
    """
    try:
        from System import GC

        GC.Collect()
        GC.WaitForPendingFinalizers()
        GC.Collect()
    except Exception:  # noqa: BLE001 — reine Aufräum-Maßnahme, darf den Lauf nicht gefährden
        logger.debug("GC.Collect() fehlgeschlagen (evtl. kein .NET-Kontext) — ignoriert.", exc_info=True)


_export_cache: "OrderedDict[tuple[str, str], Any]" = OrderedDict()
_export_cache_max_size = 500


def set_export_cache_max_size(max_size: int) -> None:
    """Setzt die maximale Anzahl gleichzeitig gecachter Baustein-XML-Exporte
    (LRU-Verdrängung, siehe ``export_block_xml``) — von ``runner.py`` einmalig
    zu Lauf-Beginn aus der Config (``xml_cache_max_size``) gesetzt.

    Ohne Begrenzung wächst der Cache unbeschränkt mit der Anzahl exportierter
    Bausteine — bei sehr großen Projekten (mehrere Tausend Bausteine) kann
    der geparste ``ElementTree`` jedes Bausteins mehrere MB belegen, in Summe
    also mehrere GB RAM (siehe ``Review-Performance.md``, Befund 2.1)."""
    global _export_cache_max_size
    _export_cache_max_size = max(1, max_size)


def reset_export_cache() -> None:
    """Leert den lauf-gebundenen Cache von ``export_block_xml``.

    Siehe ``XML-Optimierung-Analysebericht.md`` (Option B/C): Ohne diesen
    Cache exportiert jeder Prüfpunkt, der den XML-Inhalt eines Bausteins
    braucht, denselben Baustein unabhängig erneut — bei einem typischen FB
    bis zu 8-mal pro Lauf. Der Cache ist bewusst **kein** Modul-globaler
    Zustand, der über die Prozesslaufzeit hinweg bestehen bleibt, sondern
    muss von ``runner.py`` explizit zu Beginn jedes Lint-Laufs geleert
    werden (sonst "leakt" er zwischen zwei unabhängigen Läufen in der GUI).

    **Nicht** mehr bei jedem TIA-Portal-Reconnect aufrufen (siehe
    ``Review-Performance.md``, Maßnahme 2): Der Cache enthält ausschließlich
    einen geparsten, rein Python-seitigen ``ElementTree`` ohne .NET-
    Objektreferenz — er bleibt nach einem Reconnect gültig. Ein
    zwischenzeitlich fehlgeschlagener Export wird ohnehin nie gecacht (siehe
    ``export_block_xml``) und beim nächsten Zugriff automatisch erneut
    versucht, unabhängig davon, ob der Cache dazwischen geleert wurde.
    """
    _export_cache.clear()


def export_block_xml(block: Any, plc_software: Any) -> Element | None:
    """Exportiert einen Baustein nach SIMATIC ML (XML) und liefert die
    Wurzel des geparsten Dokuments (oder ``None`` bei Exportfehler).

    Die Openness-API bietet für LAD/FBD/GRAPH-Bausteine keinen dokumentierten
    Objektzugriff auf einzelne Netzwerke (Titel, Kommentar, Elementanzahl) —
    das ist nur über den XML-Export erreichbar. ``block.Export(FileInfo,
    ExportOptions.WithDefaults)`` ist gegen die TIA Portal V21 Openness-Referenz
    verifiziert (Manual 03/2026, z. B. Abschnitt zum Baustein-Export, exakt
    dieses Aufrufmuster in mehreren Codebeispielen). Die exakten
    XML-Elementnamen pro Netzwerk (angenommen: ``SW.Blocks.CompileUnit`` mit
    ``ProgrammingLanguage``/``Title``/``Comment``) sind dagegen **nicht**
    anhand eines echten Exports verifiziert — die Interface-Sections
    (``<Interface><Sections><Section Name="Static">...``) hingegen schon,
    siehe ``interface_section_members``.

    Lauf-gebundener Cache (siehe ``reset_export_cache``/
    ``XML-Optimierung-Analysebericht.md``): Bis zu 10 Prüfpunkte exportieren
    denselben Baustein unabhängig voneinander; der zurückgegebene
    ``ElementTree``-Baum ändert sich innerhalb eines Lint-Laufs nicht (kein
    Check schreibt Bausteine), Caching ist daher inhaltlich sicher. Der
    Cache-Key ist absichtlich ``(plc_software.Name, block.Name)`` — ein
    stabiler String statt des ``block``-Objekts selbst, da ``block`` nach
    einem TIA-Portal-Reconnect ein neues, den alten Handles nicht mehr
    entsprechendes .NET-Objekt ist. Der PLC-Software-Name ist Teil des Keys,
    weil Blocknamen nur innerhalb einer PLC eindeutig sind, nicht projektweit
    über mehrere PLC-Geräte hinweg.

    LRU-begrenzt auf ``_export_cache_max_size`` Einträge (siehe
    ``set_export_cache_max_size``/``Review-Performance.md``, Maßnahme 2) —
    ohne Begrenzung würde der Cache bei sehr großen Projekten (mehrere
    Tausend Bausteine) unbeschränkt wachsen, da jeder Check dieselben
    Prüfpunkte in derselben Baustein-Reihenfolge durchläuft und der Cache
    bis dahin nie geleert wird.
    """
    cache_key = (str(getattr(plc_software, "Name", "")), str(block.Name))
    if cache_key in _export_cache:
        _export_cache.move_to_end(cache_key)  # zuletzt verwendet -> ans LRU-Ende
        return _export_cache[cache_key]

    import xml.etree.ElementTree as ET

    from Siemens.Engineering import ExportOptions
    from System.IO import FileInfo

    with tempfile.TemporaryDirectory() as tmp_dir:
        export_path = Path(tmp_dir) / f"{block.Name}.xml"
        try:
            block.Export(FileInfo(str(export_path)), ExportOptions.WithDefaults)
            xml_root = ET.parse(export_path).getroot()
        except Exception as exc:  # noqa: BLE001 — .NET-/XML-Fehler, Check soll nicht abbrechen
            logger.warning("Baustein '%s' konnte nicht für die Netzwerkanalyse exportiert werden: %s", block.Name, exc)
            return None  # bewusst nicht gecacht — nächster Zugriff versucht erneut zu exportieren

    _export_cache[cache_key] = xml_root
    if len(_export_cache) > _export_cache_max_size:
        _export_cache.popitem(last=False)  # ältesten (am längsten unbenutzten) Eintrag verdrängen
    return xml_root


def iter_compile_units(xml_root: Any) -> Iterator[Any]:
    """Liefert alle ``SW.Blocks.CompileUnit``-Elemente (= Netzwerke) aus dem
    XML-Export eines Bausteins, unabhängig vom XML-Namespace-Präfix."""
    if xml_root is None:
        return
    for elem in xml_root.iter():
        if _local_name(elem.tag) == "SW.Blocks.CompileUnit":
            yield elem


def compile_unit_attribute(compile_unit: Any, name: str) -> str | None:
    """Liest ein Attribut (z. B. ``ProgrammingLanguage``) aus der
    ``AttributeList`` eines ``CompileUnit``-XML-Elements."""
    for attribute_list in compile_unit:
        if _local_name(attribute_list.tag) != "AttributeList":
            continue
        for child in attribute_list:
            if _local_name(child.tag) == name:
                return child.text
    return None


def compile_unit_multilingual_text(compile_unit: Any, composition_name: str, culture: str) -> str:
    """Liest ein mehrsprachiges Textfeld (``"Title"`` oder ``"Comment"``)
    eines ``CompileUnit``-XML-Elements (= Netzwerk) für eine bestimmte
    Kultur (z. B. ``"de-DE"``).

    User-Meldung, live an Netzwerk-Titeln verifiziert: Anders als einfache
    Attribute wie ``ProgrammingLanguage`` (siehe ``compile_unit_attribute``)
    liegen Netzwerk-``Title``/``Comment`` nicht in der ``AttributeList``,
    sondern als eigene ``MultilingualText``-Komposition im ``ObjectList`` —
    strukturell identisch zu ``PlcBlock.Title``/``.Comment`` (siehe
    ``read_title``/``read_comment``), nur eben im XML-Export statt als
    Openness-Objekt:
    ``<ObjectList><MultilingualText CompositionName="Title"><ObjectList>
    <MultilingualTextItem CompositionName="Items"><AttributeList>
    <Culture>de-DE</Culture><Text>...</Text></AttributeList>
    </MultilingualTextItem>...</ObjectList></MultilingualText></ObjectList>``.
    ``compile_unit_attribute(compile_unit, "Title")`` suchte bislang nur in
    der ``AttributeList`` und lieferte dadurch **immer** ``None`` — unabhängig
    davon, ob ein Titel gepflegt war (Prüfpunkt 3 meldete dadurch fast jedes
    Netzwerk fälschlich als "kein Titel"). Liefert ``""``, wenn keine
    passende Kultur gefunden wird oder kein Text hinterlegt ist."""
    for object_list in compile_unit:
        if _local_name(object_list.tag) != "ObjectList":
            continue
        for mlt in object_list:
            if _local_name(mlt.tag) != "MultilingualText" or mlt.attrib.get("CompositionName") != composition_name:
                continue
            for inner_object_list in mlt:
                if _local_name(inner_object_list.tag) != "ObjectList":
                    continue
                for item in inner_object_list:
                    if _local_name(item.tag) != "MultilingualTextItem":
                        continue
                    item_culture = None
                    item_text = None
                    for attribute_list in item:
                        if _local_name(attribute_list.tag) != "AttributeList":
                            continue
                        for child in attribute_list:
                            if _local_name(child.tag) == "Culture":
                                item_culture = child.text
                            elif _local_name(child.tag) == "Text":
                                item_text = child.text
                    if item_culture == culture:
                        return (item_text or "").strip()
    return ""


# STEP-7-Objekttypen, für die GetService[CrossReferenceService]() laut V21-
# Openness-Referenz (Manual 03/2026, "Unter STEP 7 auf Cross Reference Service
# zugreifen") bestätigt unterstützt ist: OB, FB, FC, DB, Instanz-DB, Globaler
# DB, Array-DB, PLC-Variable, PLC-Systemkonstante, PLC-Anwenderdatentyp.
# Interface-Member (DB-/FB-/FC-Mitglieder) sind explizit NICHT in dieser
# Liste — sie tauchen aber als texbasierte (UnderlyingObject == null)
# Kind-Objekte unter ``SourceObject.Children`` auf, siehe
# ``find_source_child_by_name``.
def cross_reference_root_source(engineering_object: Any, cross_reference_filter: Any = None) -> Any | None:
    """Ruft ``CrossReferenceService`` auf einem unterstützten STEP-7-Objekt ab
    und liefert dessen (einziges) Root-``SourceObject``, oder ``None`` wenn
    der Dienst für diesen Objekttyp nicht verfügbar ist.

    ``cross_reference_filter`` ist optional und defaultet auf
    ``CrossReferenceFilter.AllObjects`` (bisheriges Verhalten, unverändert für
    alle bestehenden Aufrufer) — ``cached_cross_reference_locations`` übergibt
    hier gezielt einen anderen Filter, ohne dass Aufrufer mit dem
    Standardfilter etwas anpassen müssen."""
    from Siemens.Engineering.CrossReference import CrossReferenceFilter, CrossReferenceService

    try:
        service = engineering_object.GetService[CrossReferenceService]()
    except Exception:  # noqa: BLE001 — Service evtl. für diesen Objekttyp nicht verfügbar
        # Review-Security-Robustheit.md, Befund 3.1: ein hier verschluckter
        # Fehler sieht für den Aufrufer identisch aus wie "keine Referenzen
        # gefunden" -- ohne diesen Log-Eintrag wäre ein daraus entstehender
        # Fehlalarm (z. B. Prüfpunkt 11a/11b/12a/12b/13) im Nachhinein nicht
        # von einem echten Befund zu unterscheiden.
        logger.warning(
            "CrossReferenceService nicht verfügbar für '%s' — Ergebnis 'keine Referenzen' kann ein Fehlalarm sein.",
            getattr(engineering_object, "Name", engineering_object),
            exc_info=True,
        )
        return None
    if service is None:
        return None
    if cross_reference_filter is None:
        cross_reference_filter = CrossReferenceFilter.AllObjects
    result = service.GetCrossReferences(cross_reference_filter)
    sources = list(getattr(result, "Sources", []) or [])
    return sources[0] if sources else None


_xref_cache: "OrderedDict[tuple[str, str, str], list[tuple[str, str]]]" = OrderedDict()
_xref_cache_max_size = 1000


def set_xref_cache_max_size(max_size: int) -> None:
    """Setzt die maximale Anzahl gleichzeitig gecachter CrossReference-
    Abfragen (LRU-Verdrängung, siehe ``cached_cross_reference_locations``) —
    von ``runner.py`` einmalig zu Lauf-Beginn aus der Config
    (``xref_cache_max_size``) gesetzt (siehe ``Review-Performance.md``,
    Maßnahme 4, analog zu ``set_export_cache_max_size``/Maßnahme 2)."""
    global _xref_cache_max_size
    _xref_cache_max_size = max(1, max_size)


def reset_xref_cache() -> None:
    """Leert die lauf-gebundenen Caches von ``cached_cross_reference_locations``
    und ``cross_reference_referenced_top_level_names``.

    Wie beim XML-Cache (``reset_export_cache``, Maßnahme 2) **nicht** bei
    jedem Reconnect aufrufen, nur einmalig zu Lauf-Beginn: Beide Caches
    enthalten ausschließlich extrahierte Python-Strings (``Access``/
    ``ReferenceType``/Membernamen als Text), keine .NET-Objektreferenzen —
    sie bleiben nach einem Reconnect gültig, da sich die tatsächliche
    Verwendung eines Tags/Bausteins während eines rein lesenden Lint-Laufs
    nicht ändert."""
    _xref_cache.clear()
    _xref_top_level_cache.clear()


def cached_cross_reference_locations(
    engineering_object: Any, cross_reference_filter: Any, plc_name: str
) -> list[tuple[str, str]]:
    """LRU-gecachte CrossReference-Abfrage für ein einzelnes STEP-7-Objekt
    (Tag oder Baustein) mit einem bestimmten Filter — liefert je Location ein
    ``(access, reference_type)``-Tupel aus reinen Python-Strings statt roher
    .NET-``Location``-Objekte (siehe ``Review-Performance.md``, Befund 4.2/
    Maßnahme 4: **keine** .NET-Objekte cachen, das würde das Handle-Problem
    nur in den Cache verlagern statt es zu lösen).

    Der Cache-Key ``(plc_name, obj_name, filter)`` ist — analog zu
    ``export_block_xml``, Maßnahme 2 — ein stabiler String statt des
    Objekts selbst, bleibt also über einen TIA-Portal-Reconnect hinweg
    gültig. Das deckt echte Mehrfachabfragen ab, die bislang unabhängig
    voneinander erfolgten: Prüfpunkt 11a fragt z. B. **jedes** Tag mit dem
    Filter ``AllObjects`` ab, bevor 12a/12b/13 (dieselben Tags, derselbe
    Filter, jeweils nur für Ein- bzw. Ausgänge) erneut abfragen — nach dieser
    Umstellung trifft der zweite und jeder weitere Zugriff auf denselben
    Cache-Eintrag.

    ``access``/``reference_type`` sind ``str(...)`` des jeweiligen .NET-Enum-
    Werts (``Location.Access``/``.ReferenceType``) — noch nicht live gegen
    ein echtes TIA-Portal-Projekt verifiziert, dass ``str()`` eines
    pythonnet-.NET-Enums exakt den Member-Namen liefert (z. B. ``"Read"``
    statt eines vollqualifizierten Strings); Aufrufer vergleichen entsprechend
    gegen die erwarteten Namen (``"Read"``/``"Write"``/``"InstanceType"``)
    statt gegen die ursprünglichen Enum-Konstanten.
    """
    obj_name = str(getattr(engineering_object, "Name", ""))
    filter_key = str(cross_reference_filter)
    cache_key = (plc_name, obj_name, filter_key)
    if cache_key in _xref_cache:
        _xref_cache.move_to_end(cache_key)
        return _xref_cache[cache_key]

    source = cross_reference_root_source(engineering_object, cross_reference_filter)
    extracted: list[tuple[str, str]] = []
    if source is not None:
        for reference in getattr(source, "References", []) or []:
            for location in getattr(reference, "Locations", []) or []:
                access = str(getattr(location, "Access", "") or "")
                reference_type = str(getattr(location, "ReferenceType", "") or "")
                extracted.append((access, reference_type))

    _xref_cache[cache_key] = extracted
    if len(_xref_cache) > _xref_cache_max_size:
        _xref_cache.popitem(last=False)  # ältesten (am längsten unbenutzten) Eintrag verdrängen
    return extracted


def unused_cross_reference_leaf_names(sources: Iterable[Any]) -> Iterator[str]:
    """Durchläuft rekursiv den von ``CrossReferenceService.GetCrossReferences``
    zurückgelieferten ``Sources``-Baum und liefert die Namen aller
    Blatt-Objekte (``SourceObject``s ohne eigene ``Children``).

    User-Meldung, live an Instanz-DB ``DB_PrgFieldbusOkDb`` verifiziert,
    zusätzlich bestätigt durch den offiziellen Beispielcode der
    V21-Openness-Referenz (Manual 03/2026, "Querverweise für STEP 7
    abrufen", Abschnitt ``PrintSourceObjects``): ``CrossReferenceResult.Sources``
    ist **kein** flacher Treffer pro unbenutztem Objekt, sondern die Wurzel
    eines Baums — jedes ``SourceObject`` kann über ``.Children`` weitere,
    tiefer verschachtelte ``SourceObject``s enthalten. Fragt man
    ``UnusedObjects`` auf einer Instanz-DB ab, liefert ``Sources`` in der
    Praxis genau einen Wurzelknoten (die DB selbst, ``TypeName`` "Instance DB
    of ..."), dessen ``Children`` — rekursiv — die tatsächlich unbenutzten
    Member enthalten (z. B. ``DB_PrgFieldbusOkDb`` → ``DiagCpu`` (UDT-Struct,
    selbst kein Blatt) → ``DiagCpu.DNNmode`` (echtes unbenutztes Blatt-Member).
    Nur Blattknoten (ohne eigene ``Children``) werden geliefert — ein
    Zwischenknoten wie ein UDT-typisiertes Struct-Member wird nicht separat
    gemeldet, nur was am Ende des Pfads tatsächlich unbenutzt ist.

    Array-Elemente (Name enthält ``[...]``) werden übersprungen — live
    verifiziert, dass ein einziges großes Array-Member sonst tausende
    Einzelindizes als separate Blattknoten liefert (analog zum bereits
    bestehenden Array-Skip bei Prüfpunkt 1a)."""
    for source in sources:
        children = list(getattr(source, "Children", None) or [])
        if children:
            yield from unused_cross_reference_leaf_names(children)
            continue
        name = getattr(source, "Name", None)
        if name and "[" not in name:
            yield name


def strip_cross_reference_prefix(name: str, root_name: str) -> str:
    """Entfernt das qualifizierende Präfix, das ``SourceObject.Name`` im
    Kreuzreferenzbaum gegenüber dem unqualifizierten Namen aus dem
    XML-Export/der Deklaration trägt (``'"01PrgDb".lx_30M1StopGap'`` bzw.
    ``'DB_X.DiagCpu.DNNmode'`` statt ``lx_30M1StopGap``/``DiagCpu.DNNmode``
    -- ``root_name`` ist der Name des abgefragten Wurzelobjekts, als
    ``"<root_name>".`` oder ``<root_name>.`` quotiert oder unquotiert.
    Extrahiert aus ``find_source_child_by_name`` (dort ursprünglich eine
    lokale Closure), zusätzlich von ``cross_reference_referenced_top_level_names``
    und Prüfpunkt 11a (``structure.py``) genutzt. Ohne Präfix-Treffer wird
    ``name`` unverändert zurückgegeben."""
    if root_name:
        for prefix in (f'"{root_name}".', f"{root_name}."):
            if name.startswith(prefix):
                return name[len(prefix):]
    return name


_xref_top_level_cache: "OrderedDict[tuple[str, str], set[str]]" = OrderedDict()


def cross_reference_referenced_top_level_names(engineering_object: Any, plc_name: str) -> set[str]:
    """Liefert die (unqualifizierten) Namen aller direkten Kind-Member eines
    DB/Bausteins, die laut ``CrossReferenceService`` irgendeine Referenz
    tragen (``CrossReferenceFilter.ObjectsWithReferences`` -- laut
    V21-Openness-Referenz das dokumentierte Gegenstück zu
    ``CrossReferenceFilter.UnusedObjects``, siehe
    ``unused_cross_reference_leaf_names``). Noch nicht live verifiziert
    (weder die grundsätzliche Baumform noch, dass ``ObjectsWithReferences``
    dieselbe Struktur wie ``UnusedObjects`` liefert).

    LRU-gecacht nach demselben Muster wie ``cached_cross_reference_locations``
    (Review-Performance.md, Befund 3.2, Cache-Key ``(plc_name, obj_name)`` --
    der Filter ist hier immer ``ObjectsWithReferences``, daher kein dritter
    Key-Bestandteil nötig, anders als beim allgemeineren XRef-Cache). Ohne
    diesen Cache fragen Prüfpunkt 11a (für jeden Global-/Array-DB mit
    ``UnusedObjects``-Befunden) und Prüfpunkt 11b (für **jeden**
    Global-/Array-DB, unbedingt) denselben DB mit demselben Filter zweimal
    ab, sobald beide Checks aktiv sind -- eine echte, vermeidbare
    Verdopplung. Die *andere* in Befund 3.2 beschriebene Verdopplung (11a
    fragt pro DB sowohl ``UnusedObjects`` als auch, bei Treffern,
    ``ObjectsWithReferences`` ab) bleibt bestehen und ist nicht vermeidbar:
    beide Filter liefern inhaltlich unterschiedliche Information (unbenutzte
    Blattmember vs. referenzierte Top-Level-Member) und lassen sich nicht
    aus derselben Abfrage ableiten. Teilt sich den Größenparameter
    (``xref_cache_max_size``) mit dem allgemeinen XRef-Cache -- eigener
    Config-Schlüssel wäre für diesen deutlich kleineren Zusatzcache
    unverhältnismäßig.

    Zwanzigster Bug/Feature (User-Auftrag, PP11 in der betrieblichen Praxis):
    Wird eine UDT-/Struct-typisierte DB-Variable als Ganzes an einen anderen
    Baustein übergeben (z. B. ``MeinFb(duStruct := "MeinDb".MeinStruct)``),
    markiert ``CrossReferenceService`` typischerweise nur den Struct-Knoten
    selbst als referenziert -- einzelne, nicht separat angefasste
    Unterfelder bleiben in ``UnusedObjects`` weiterhin als "unbenutzt"
    gelistet, obwohl die Variable in der Praxis sehr wohl verwendet wird
    und ein Melden jedes einzelnen Unterfelds als Fehlalarm empfunden wird.
    Diese Funktion liefert bewusst nur die **oberste** Ebene (keine
    rekursive Blattauflösung) -- ist der Top-Level-Name hier vorhanden,
    gilt die Variable als Ganzes als verwendet, unabhängig davon, auf
    welcher Tiefe die tatsächliche Referenz saß. Für skalare (nicht
    UDT-/Struct-typisierte) Variablen ist "oberste Ebene" gleichbedeutend
    mit dem einzigen Blatt selbst -- eine explizite Typunterscheidung
    UDT/Struct vs. Skalar ist deshalb beim Aufrufer nicht nötig, das
    Verhalten reduziert sich für Skalare automatisch auf den bisherigen,
    unveränderten Fall."""
    obj_name = str(getattr(engineering_object, "Name", ""))
    cache_key = (plc_name, obj_name)
    if cache_key in _xref_top_level_cache:
        _xref_top_level_cache.move_to_end(cache_key)
        return _xref_top_level_cache[cache_key]

    from Siemens.Engineering.CrossReference import CrossReferenceFilter, CrossReferenceService

    names: set[str] = set()
    try:
        service = engineering_object.GetService[CrossReferenceService]()
    except Exception:  # noqa: BLE001 — Service evtl. für diesen Objekttyp nicht verfügbar
        # Review-Security-Robustheit.md, Befund 3.1/3.2: ein leeres Set ist
        # hier ununterscheidbar vom legitimen Ergebnis "kein Member
        # referenziert" -- Prüfpunkt 11b liest genau das als "Baustein
        # unbenutzt" (structure.py, UnbenutzteBausteineCheck). Ohne diesen
        # Log-Eintrag wäre ein daraus entstehender Fehlalarm im Nachhinein
        # nicht von einem echten Befund zu unterscheiden.
        logger.warning(
            "CrossReferenceService nicht verfügbar für '%s' — Ergebnis 'keine referenzierten Member' kann ein Fehlalarm sein.",
            getattr(engineering_object, "Name", engineering_object),
            exc_info=True,
        )
        service = None
    if service is not None:
        result = service.GetCrossReferences(CrossReferenceFilter.ObjectsWithReferences)
        for source in getattr(result, "Sources", None) or []:
            root_name = getattr(source, "Name", None) or ""
            for child in getattr(source, "Children", None) or []:
                child_name = getattr(child, "Name", None)
                if not child_name:
                    continue
                name = normalize_member_path(strip_cross_reference_prefix(child_name, root_name))
                if name and name != root_name:
                    names.add(name)

    _xref_top_level_cache[cache_key] = names
    if len(_xref_top_level_cache) > _xref_cache_max_size:
        _xref_top_level_cache.popitem(last=False)  # ältesten (am längsten unbenutzten) Eintrag verdrängen
    return names


def find_source_child_by_name(source_object: Any, name: str) -> Any | None:
    """Durchsucht rekursiv ``SourceObject.Children`` nach einem Kind mit
    gegebenem Namen.

    Laut V21-Openness-Referenz tauchen Interface-Member (DB-/FB-/FC-
    Mitglieder) als Kind-``SourceObject``s auf, deren ``UnderlyingObject``
    ``null`` ist ("Currently, the EOM support is NOT available for Member
    objects... In such cases, the source.UnderlyingObject will be null.") —
    Name/Address/TypeName/Path bleiben aber als Textinformation verfügbar.
    Damit lässt sich ein einzelnes Interface-Mitglied im Kreuzreferenzbaum
    seines Bausteins/DBs anhand des Namens wiederfinden.

    ``name`` kommt aus ``interface_section_members()`` (XML-Export der
    Interface-Section, unquotierte, unqualifizierte Namen). ``child.Name``
    aus dem Kreuzreferenzbaum trägt dagegen live verifiziert (Salzmaschine,
    Instanz-DB ``01PrgDb``) immer den Namen des abgefragten Wurzelobjekts als
    qualifizierendes Präfix — z. B. ``'"01PrgDb".lx_30M1StopGap'`` statt
    ``'lx_30M1StopGap'`` (Präfix als ``"<Name>".`` oder ``<Name>.``, analog
    zum bereits in Prüfpunkt 11a behandelten Fall bei
    ``unused_cross_reference_leaf_names``). Ohne diesen Präfix-Abgleich fand
    diese Funktion **kein einziges** einfaches (nicht verschachteltes)
    Interface-Member — betraf Prüfpunkt 25 (``static_zugriff_extern``), das
    dadurch trotz des separaten ``ReferenceLocation``-Fixes weiterhin nie
    einen Treffer meldete. Für Namen, die keine gültigen "einfachen"
    Bezeichner sind (z. B. Ziffernbeginn), ist der Rest nach dem Präfix
    zusätzlich quotiert (``"4805_15A1"`` statt ``4805_15A1`` — dasselbe
    Verhalten wie bei ``ProjectTextComments``, siehe ``normalize_member_path``),
    daher zusätzlich der Normalisierungs-Fallback.
    """
    root_name = getattr(source_object, "Name", None) or ""

    def _walk(node: Any) -> Any | None:
        for child in getattr(node, "Children", []) or []:
            child_name = getattr(child, "Name", None)
            if child_name is not None:
                candidate = strip_cross_reference_prefix(child_name, root_name)
                if candidate == name or normalize_member_path(candidate) == name:
                    return child
            found = _walk(child)
            if found is not None:
                return found
        return None

    return _walk(source_object)


def interface_section_members(xml_root: Any, section_name: str) -> set[str]:
    """Liefert die Namen aller Mitglieder einer Interface-Section (z. B.
    ``"Static"``, ``"Output"``) aus dem XML-Export eines Bausteins.

    Bestätigt durch die V21-Openness-Referenz (Manual 03/2026, SIMATIC-ML-
    Beispiele): ``<Interface><Sections><Section Name="Static">
    <Member Name="...">...</Member></Section></Sections></Interface>``.

    User-Meldung, live an FB ``01OrgPrg`` (Multi-Instanz ``lu_RcpReq`` in der
    Static-Section) verifiziert: Ein ``<Member>``, dessen Datentyp selbst ein
    FB/UDT mit eigenem Interface ist (Multi-Instanz bzw. UDT-typisiertes
    Struct-Member), trägt im XML-Export ein eigenes verschachteltes
    ``<Sections><Section Name="...">...`` mit der Struktur *dieses* Typs
    (z. B. eine eigene ``Static``-Section mit dessen Sub-Membern). Die
    ursprüngliche Implementierung suchte mit ``xml_root.iter()`` nach *jeder*
    ``Section`` mit passendem Namen im gesamten Dokument — dadurch wurden
    auch diese verschachtelten, zum Multi-Instanz-Typ gehörenden Sub-Member
    fälschlich als direkte Interface-Member des exportierten Bausteins selbst
    behandelt (betraf Prüfpunkt 1c sowie ``libraries.py``s
    ``static_zugriff_extern``/``output_mehrfach_beschrieben``, die denselben
    Mechanismus nutzen). Fix: Ein manueller Baumdurchlauf, der beim
    Abstieg nicht in ``<Member>``-Elemente hinein rekursiert — nur die
    Sections auf dem direkten Pfad ``Interface > Sections > Section`` des
    Bausteins selbst zählen, ein verschachteltes Interface eines
    Multi-Instanz-/Struct-Members wird ignoriert (dieser Typ wird ohnehin
    eigenständig geprüft, wenn die äußere Schleife bei ihm ankommt).
    """
    if xml_root is None:
        return set()
    names: set[str] = set()

    def _walk(elem: Any) -> None:
        for child in elem:
            tag = _local_name(child.tag)
            if tag == "Member":
                continue  # nicht in verschachtelte Sub-Interfaces absteigen
            if tag == "Section" and child.attrib.get("Name") == section_name:
                for member in child:
                    if _local_name(member.tag) == "Member":
                        member_name = member.attrib.get("Name")
                        if member_name:
                            names.add(member_name)
            _walk(child)

    _walk(xml_root)
    return names


def interface_section_member_paths(xml_root: Any, section_name: str) -> dict[str, list[str]]:
    """Wie ``interface_section_members``, aber mit vollständiger
    Blattpfad-Auflösung je direktem Member: liefert ``{membername:
    [blattpfad, ...]}`` -- bei einem skalaren Member ist das genau
    ``[membername]`` selbst, bei einem UDT-/Multiinstanz-typisierten Member
    die dotted Pfade aller (rekursiv) verschachtelten Blattfelder (z. B.
    ``{"MeinStruct": ["MeinStruct.a", "MeinStruct.b.c"]}``), gelesen aus dem
    verschachtelten ``<Sections>`` innerhalb des ``<Member>``-Elements
    selbst (siehe ``interface_section_members``, Absatz zu
    Multiinstanz-/UDT-Membern -- dort bewusst übersprungen, hier gezielt
    ausgewertet). Grundlage für Prüfpunkt 11as Unterelement-Detailprüfung
    bei FB/FC/OB (``unterelemente_pruefen``, siehe ``structure.py``)."""
    if xml_root is None:
        return {}
    result: dict[str, list[str]] = {}

    def _leaf_paths(member_elem: Any, prefix: str) -> list[str]:
        leaves: list[str] = []
        for child in member_elem:
            if _local_name(child.tag) != "Sections":
                continue
            for section in child:
                if _local_name(section.tag) != "Section":
                    continue
                for sub_member in section:
                    if _local_name(sub_member.tag) != "Member":
                        continue
                    sub_name = sub_member.attrib.get("Name")
                    if sub_name:
                        leaves.extend(_leaf_paths(sub_member, f"{prefix}.{sub_name}"))
        return leaves or [prefix]

    def _walk(elem: Any) -> None:
        for child in elem:
            tag = _local_name(child.tag)
            if tag == "Member":
                continue  # nicht in verschachtelte Sub-Interfaces absteigen
            if tag == "Section" and child.attrib.get("Name") == section_name:
                for member in child:
                    if _local_name(member.tag) != "Member":
                        continue
                    name = member.attrib.get("Name")
                    if name:
                        result[name] = _leaf_paths(member, name)
            _walk(child)

    _walk(xml_root)
    return result


def _symbol_component_chain(symbol_or_instance_elem: Any) -> list[str]:
    """Liest die Namen aller direkten ``Component``-Kinder von ``Symbol``
    (bzw. ``Instance``) in Dokumentreihenfolge.

    Live an FB ``PrgFieldbusOk`` verifiziert: TIA exportiert einen
    mehrstufigen Struct-/UDT-Zugriff (z. B. ``DiagCpu.SubordinateIOState``)
    **nicht** wie ursprünglich angenommen als ineinander verschachtelte
    ``Component``-Elemente, sondern als flache Geschwister-Liste direkt
    unter ``Symbol``::

        <Symbol>
          <Component Name="DiagCpu" />
          <Component Name="SubordinateIOState" />
        </Symbol>

    (analog auch an FC ``CtrFcParaRdWr`` bestätigt, z. B. ``lx_Step.Sc``).
    Fortsetzung von ``_first_symbol_component_name``, das bewusst nur die
    erste ``Component`` liefert; Grundlage für ``local_variable_access_paths``
    (Prüfpunkt 11as Unterelement-Detailprüfung)."""
    return [
        name
        for component in symbol_or_instance_elem
        if _local_name(component.tag) == "Component" and (name := component.attrib.get("Name"))
    ]


def local_variable_access_paths(xml_root: Any) -> set[str]:
    """Liefert die Namen aller eigenen Interface-Member (Input/Output/InOut/
    Static/Temp), die im Netzwerk-Code eines Bausteins (FB/FC/OB) tatsächlich
    referenziert werden — unabhängig von der Programmiersprache — als dotted
    Zugriffspfade auf beliebiger Verschachtelungstiefe (z. B.
    ``"DiagCpu.SubordinateIOState"`` statt nur ``"DiagCpu"``) für
    Prüfpunkt 11as Unterelement-Detailprüfung bei FB/FC/OB
    (``unterelemente_pruefen: true`` in der Config, siehe ``structure.py``).
    Ein Zugriff auf ein UDT-/Struct-Member als Ganzes (z. B. als
    Aufrufparameter einer anderen Bausteininstanz) liefert nur den
    kürzeren Pfad bis zu dieser Tiefe -- tiefer verschachtelte, dabei nicht
    separat angefasste Blattfelder erscheinen dann nicht als eigener,
    längerer Pfad (bewusst exakt, ohne Ableitung "Elternpfad zugegriffen
    => Kind auch", analog zur echten Feld-Granularität von
    ``CrossReferenceService`` bei DB-Variablen). Live an FB
    ``PrgFieldbusOk``/FC ``CtrFcParaRdWr`` verifiziert, siehe
    ``_symbol_component_chain``."""
    if xml_root is None:
        return set()
    paths: set[str] = set()

    for compile_unit in iter_compile_units(xml_root):
        for elem in compile_unit.iter():
            tag = _local_name(elem.tag)
            if elem.attrib.get("Scope") != "LocalVariable":
                continue
            if tag == "Access":
                for symbol in elem:
                    if _local_name(symbol.tag) != "Symbol":
                        continue
                    chain = _symbol_component_chain(symbol)
                    if chain:
                        paths.add(".".join(chain))
                    break
            elif tag == "Instance":
                chain = _symbol_component_chain(elem)
                if chain:
                    paths.add(".".join(chain))
    return paths


def _first_symbol_component_name(access_elem: Any) -> str | None:
    """Liefert den Namen der ersten ``Component`` unter ``Symbol`` eines
    ``Access``-Elements (das direkt deklarierte Interface-Member)."""
    for symbol in access_elem:
        if _local_name(symbol.tag) != "Symbol":
            continue
        for component in symbol:
            if _local_name(component.tag) == "Component":
                return component.attrib.get("Name")
        break
    return None


_FBD_WRITE_PIN_NAMES = frozenset({"operand", "out", "out1", "q", "et"})


def _scan_scl_assignment_writes(elem: Any, counts: dict[str, int]) -> None:
    """Rekursiver Teil von ``local_variable_write_counts`` für SCL: erkennt
    Zuweisungsziele anhand der Token-Nachbarschaft eines ``Access``-Elements
    (siehe Docstring dort für die live verifizierte Struktur)."""
    children = list(elem)
    parent_tag = _local_name(elem.tag)

    def _next_non_blank(start: int) -> Any | None:
        for i in range(start, len(children)):
            if _local_name(children[i].tag) not in ("Blank", "NewLine"):
                return children[i]
        return None

    def _prev_non_blank(start: int) -> Any | None:
        for i in range(start, -1, -1):
            if _local_name(children[i].tag) not in ("Blank", "NewLine"):
                return children[i]
        return None

    for index, child in enumerate(children):
        if _local_name(child.tag) == "Access" and child.attrib.get("Scope") == "LocalVariable":
            is_write = False
            following = _next_non_blank(index + 1)
            if following is not None and _local_name(following.tag) == "Token" and following.attrib.get("Text") == ":=":
                is_write = True  # einfache Zuweisung: Access direkt vor ":="
            elif parent_tag == "Parameter":
                preceding = _prev_non_blank(index - 1)
                if preceding is not None and _local_name(preceding.tag) == "Token" and preceding.attrib.get("Text") == "=>":
                    is_write = True  # Aufruf-Ausgangsparameter: Access nach "=>"
            if is_write:
                name = _first_symbol_component_name(child)
                if name:
                    counts[name] = counts.get(name, 0) + 1
        _scan_scl_assignment_writes(child, counts)


def local_variable_write_counts(xml_root: Any) -> dict[str, int]:
    """Zählt, wie oft eigene Interface-Member (Input/Output/InOut/Static/Temp)
    im Netzwerk-Code eines Bausteins (FB/FC/OB) tatsächlich **beschrieben**
    (nicht nur gelesen) werden — sprachunabhängig (SCL und FBD/LAD).

    Anders als ``local_variable_access_paths`` (das nur "wird überhaupt
    verwendet" beantwortet) ist hier die Lese-/Schreibrichtung nötig
    (Prüfpunkt 26: mehrfach beschriebene Output-Parameter). Live an
    Salzmaschine erarbeitet (FB ``LSNTP_Server``, FC ``CtrFcParaRdWr``,
    OB1 ``OrgPrg``, FC ``DiagnosticErrorInterrupt`` als Move-Beispiel):

    **FBD/LAD**: Eine ``Access Scope="LocalVariable"``-Referenz ist ein
    Schreibzugriff, wenn sie über ihre ``IdentCon`` mit demselben ``Wire``
    verbunden ist wie ein ``NameCon``, dessen ``Name``-Attribut ein
    "schreibender" Pin ist (``operand`` bei Coil/SCoil/RCoil/PCoil/NCoil/
    ResetIECTimerCoil, ``out``/``out1`` bei Logikgattern/Move/Vergleichs-
    und Rechenboxen, ``q``/``et`` bei TON/TOF) — alle anderen Pins
    (``in``/``in1``/``in2``/``bit``/``en``/...) sind lesend. Live bestätigt
    an ``SCoil`` (Pin ``operand``, Beispiel ``CtrFcParaRdWr``), ``Coil``
    unter einem AND-Gatter (``OrgPrg``) und ``Move`` (Pin ``out1``,
    ``DiagnosticErrorInterrupt``). Diese Zuordnung ist auf die in diesem
    Projekt tatsächlich vorkommenden Part-Typen begrenzt — ein hier nicht
    gelisteter Part-Typ wird konservativ nicht als Schreibzugriff gewertet
    (lieber ein Treffer zu wenig als ein Fehlalarm).

    **SCL**: Ein ``Access Scope="LocalVariable"`` ist ein Schreibzugriff,
    wenn es (a) als direktes Geschwisterelement unmittelbar vor einem
    ``Token Text=":="`` steht (einfache Zuweisung, z. B. ``error := TRUE;``
    — live an genau dieser Zeile in ``LSNTP_Server`` verifiziert), oder
    (b) innerhalb eines ``Parameter``-Elements unmittelbar nach einem
    ``Token Text="=>"`` steht (benannter Ausgangsparameter eines Aufrufs,
    z. B. ``RD_SYS_T(OUT => tempSysTime)``). Der spiegelbildliche Fall
    (``Token Text=":="`` gefolgt von ``Access`` innerhalb eines
    ``Parameter``) ist ein *lesender* Eingangsparameter, kein Schreibzugriff.

    Kreuzvalidiert gegen ``CrossReferenceService`` (``Location.Access ==
    Write``) an ``LSNTP_ServerDb``: beide Wege liefern für ``status``,
    ``error`` und ``statusID`` übereinstimmend je 4 Schreibzugriffe.
    """
    counts: dict[str, int] = {}
    if xml_root is None:
        return counts

    for compile_unit in iter_compile_units(xml_root):
        access_by_uid: dict[str, Any] = {}
        for elem in compile_unit.iter():
            if _local_name(elem.tag) == "Access" and elem.attrib.get("Scope") == "LocalVariable":
                uid = elem.attrib.get("UId")
                if uid:
                    access_by_uid[uid] = elem

        for wire in compile_unit.iter():
            if _local_name(wire.tag) != "Wire":
                continue
            write_pin_present = False
            ident_uids: list[str] = []
            for endpoint in wire:
                endpoint_tag = _local_name(endpoint.tag)
                if endpoint_tag == "NameCon":
                    if (endpoint.attrib.get("Name") or "").lower() in _FBD_WRITE_PIN_NAMES:
                        write_pin_present = True
                elif endpoint_tag == "IdentCon":
                    uid = endpoint.attrib.get("UId")
                    if uid:
                        ident_uids.append(uid)
            if not write_pin_present:
                continue
            for uid in ident_uids:
                access = access_by_uid.get(uid)
                if access is None:
                    continue
                name = _first_symbol_component_name(access)
                if name:
                    counts[name] = counts.get(name, 0) + 1

        _scan_scl_assignment_writes(compile_unit, counts)

    return counts


def compile_unit_element_count(compile_unit: Any) -> int:
    """Zählt die Programmelemente (Kontakte, Spulen, Bausteinaufrufe, ...)
    eines Netzwerks anhand der ``Part``- und ``Call``-Elemente in seiner
    ``NetworkSource``.

    User-Meldung, live an FC ``OrgPrg`` verifiziert (Netzwerke 9/12/13/14/15):
    Ein Bausteinaufruf (FB-/FC-Call) wird im XML-Export **nicht** als
    ``<Part>`` dargestellt, sondern als eigenes ``<Call>``-Element —
    ein Netzwerk, das ausschließlich einen einzigen Bausteinaufruf enthält
    (kein Kontakt, keine Spule), wurde dadurch bislang mit Elementanzahl 0
    gezählt, obwohl es klar nicht leer ist (betraf vor allem Prüfpunkt 10,
    ``leere_netzwerke``). Fix: ``<Call>`` zählt jetzt ebenfalls als Element.
    """
    count = 0
    for child in compile_unit.iter():
        if _local_name(child.tag) in ("Part", "Call"):
            count += 1
    return count


def compile_unit_scl_line_count(compile_unit: Any) -> int:
    """Zählt die Code-Zeilen eines SCL-Netzwerks.

    ``compile_unit_element_count`` zählt ausschließlich grafische
    ``<Part>``/``<Call>``-Elemente und liefert für SCL-Text (der als Folge
    von ``<Token>``/``<Access>``/``<NewLine>``-Elementen exportiert wird,
    siehe ``_scan_scl_assignment_writes``) immer 0 — unabhängig von der
    tatsächlichen Zeilenzahl. Diese Funktion zählt stattdessen die
    ``<NewLine>``-Elemente: ``N`` Zeilenumbrüche ergeben ``N + 1`` Zeilen.
    Ein Netzwerk ganz ohne Code (kein ``Token``/``Access``) gilt als leer
    (``0``), nicht als eine Zeile.
    """
    newline_count = 0
    has_content = False
    for child in compile_unit.iter():
        tag = _local_name(child.tag)
        if tag == "NewLine":
            newline_count += 1
        elif tag in ("Token", "Access"):
            has_content = True
    return newline_count + 1 if has_content else 0
