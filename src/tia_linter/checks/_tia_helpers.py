"""Interne Hilfsfunktionen zum Traversieren eines TIA-Openness-Projekts.

Wird von allen ``checks/*.py``-Modulen verwendet — die Projekt-Objektstruktur
ist über die Kategorien hinweg identisch (PLC-Software-Container finden, alle
Bausteine/Tag-Tabellen rekursiv durchlaufen, Pfade einheitlich formatieren).
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)


def format_path(*parts: str) -> str:
    """Baut einen Befund-Pfad im projektweit einheitlichen Format
    ``Teil1 > Teil2 > ...`` (siehe README, Abschnitt "Pfad-Format")."""
    return " > ".join(str(p) for p in parts if p)


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


def iter_devices_with_items(project: Any) -> Iterator[tuple[Any, Any]]:
    """Liefert alle ``(device, device_item)``-Paare des Projekts — Basis für
    Hardware-bezogene Prüfungen (I/O-Adressen, Safety, Zertifikate, ...)."""
    for device in project.Devices:
        for device_item in device.DeviceItems:
            yield device, device_item


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
        return default
    return default if value is None else value


def _local_name(tag: str) -> str:
    """Elementname ohne XML-Namespace-Präfix (``{ns}Tag`` -> ``Tag``)."""
    return tag.rsplit("}", 1)[-1]


def export_block_xml(block: Any):
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
    """
    import xml.etree.ElementTree as ET

    from Siemens.Engineering import ExportOptions
    from System.IO import FileInfo

    with tempfile.TemporaryDirectory() as tmp_dir:
        export_path = Path(tmp_dir) / f"{block.Name}.xml"
        try:
            block.Export(FileInfo(str(export_path)), ExportOptions.WithDefaults)
            return ET.parse(export_path).getroot()
        except Exception as exc:  # noqa: BLE001 — .NET-/XML-Fehler, Check soll nicht abbrechen
            logger.warning("Baustein '%s' konnte nicht für die Netzwerkanalyse exportiert werden: %s", block.Name, exc)
            return None


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


# STEP-7-Objekttypen, für die GetService[CrossReferenceService]() laut V21-
# Openness-Referenz (Manual 03/2026, "Unter STEP 7 auf Cross Reference Service
# zugreifen") bestätigt unterstützt ist: OB, FB, FC, DB, Instanz-DB, Globaler
# DB, Array-DB, PLC-Variable, PLC-Systemkonstante, PLC-Anwenderdatentyp.
# Interface-Member (DB-/FB-/FC-Mitglieder) sind explizit NICHT in dieser
# Liste — sie tauchen aber als texbasierte (UnderlyingObject == null)
# Kind-Objekte unter ``SourceObject.Children`` auf, siehe
# ``find_source_child_by_name``.
def cross_reference_root_source(engineering_object: Any) -> Any | None:
    """Ruft ``CrossReferenceService`` auf einem unterstützten STEP-7-Objekt ab
    und liefert dessen (einziges) Root-``SourceObject``, oder ``None`` wenn
    der Dienst für diesen Objekttyp nicht verfügbar ist."""
    from Siemens.Engineering.CrossReference import CrossReferenceFilter, CrossReferenceService

    try:
        service = engineering_object.GetService[CrossReferenceService]()
    except Exception:  # noqa: BLE001 — Service evtl. für diesen Objekttyp nicht verfügbar
        return None
    if service is None:
        return None
    result = service.GetCrossReferences(CrossReferenceFilter.AllObjects)
    sources = list(getattr(result, "Sources", []) or [])
    return sources[0] if sources else None


def cross_reference_locations(engineering_object: Any) -> list[Any]:
    """Liefert alle ``Location``-Objekte (mit ``Access``: Lesen/Schreiben)
    über alle Kreuzreferenzen eines Openness-Objekts — nur für die laut
    V21-Referenz bestätigt unterstützten Objekttypen sinnvoll (siehe
    ``cross_reference_root_source``); bei nicht unterstützten Typen liefert
    der Dienst ``None`` zurück und diese Funktion entsprechend eine leere
    Liste, statt abzustürzen."""
    source = cross_reference_root_source(engineering_object)
    if source is None:
        return []
    locations = []
    for reference in getattr(source, "References", []) or []:
        for location in getattr(reference, "Locations", []) or []:
            locations.append(location)
    return locations


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
    """
    for child in getattr(source_object, "Children", []) or []:
        if getattr(child, "Name", None) == name:
            return child
        found = find_source_child_by_name(child, name)
        if found is not None:
            return found
    return None


def interface_section_members(xml_root: Any, section_name: str) -> set[str]:
    """Liefert die Namen aller Mitglieder einer Interface-Section (z. B.
    ``"Static"``, ``"Output"``) aus dem XML-Export eines Bausteins.

    Bestätigt durch die V21-Openness-Referenz (Manual 03/2026, SIMATIC-ML-
    Beispiele): ``<Interface><Sections><Section Name="Static">
    <Member Name="...">...</Member></Section></Sections></Interface>``.
    """
    if xml_root is None:
        return set()
    names: set[str] = set()
    for section in xml_root.iter():
        if _local_name(section.tag) != "Section" or section.attrib.get("Name") != section_name:
            continue
        for member in section:
            if _local_name(member.tag) == "Member":
                member_name = member.attrib.get("Name")
                if member_name:
                    names.add(member_name)
    return names


def compile_unit_element_count(compile_unit: Any) -> int:
    """Zählt die Programmelemente (Kontakte, Spulen, Bausteinaufrufe, ...)
    eines Netzwerks anhand der ``Parts`` in seiner ``NetworkSource``."""
    count = 0
    for child in compile_unit.iter():
        if _local_name(child.tag) == "Part":
            count += 1
    return count
