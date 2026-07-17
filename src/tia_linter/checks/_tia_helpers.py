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


def iter_plc_targets(project: Any) -> Iterator[tuple[Any, Any]]:
    """Liefert ``(plc_software, device_item)``-Paare — ``device_item`` ist das
    Hardware-Objekt (CPU), das die jeweilige PLC-Software hostet. Für
    Hardware-/Safety-/Zertifikats-Prüfungen, die am ``DeviceItem`` statt an
    der Software ansetzen (``GetService[SafetyAdministration]()`` u. Ä.)."""
    from Siemens.Engineering.HW.Features import SoftwareContainer
    from Siemens.Engineering.SW import PlcSoftware

    for device in project.Devices:
        for device_item in device.DeviceItems:
            container = device_item.GetService[SoftwareContainer]()
            if container is not None and isinstance(container.Software, PlcSoftware):
                yield container.Software, device_item


def iter_devices_with_items(project: Any) -> Iterator[tuple[Any, Any]]:
    """Liefert alle ``(device, device_item)``-Paare des Projekts — Basis für
    Hardware-bezogene Prüfungen (I/O-Adressen, Safety, Zertifikate, ...)."""
    for device in project.Devices:
        for device_item in device.DeviceItems:
            yield device, device_item


def iter_blocks(plc_software: Any) -> Iterator[tuple[Any, list[str]]]:
    """Durchläuft rekursiv alle Bausteine (FB/FC/OB/DB) einer PLC-Software und
    liefert je Baustein ein Tupel ``(block, gruppenpfad)``. ``gruppenpfad``
    sind die Namen der durchlaufenen Ordner/Gruppen (ohne den Baustein selbst,
    ohne den PLC-Namen) — für die Root-Ebene eine leere Liste."""

    def _walk(block_group: Any, path: list[str]) -> Iterator[tuple[Any, list[str]]]:
        for block in block_group.Blocks:
            yield block, path
        for subgroup in getattr(block_group, "Groups", []):
            yield from _walk(subgroup, [*path, subgroup.Name])

    yield from _walk(plc_software.BlockGroup, [])


def iter_data_blocks(plc_software: Any) -> Iterator[tuple[Any, list[str]]]:
    """Wie ``iter_blocks``, aber nur Datenbausteine (Global-DB, Instanz-DB,
    Array-DB) — Openness kennt keine gemeinsame Klasse ``DB``, alle drei
    leiten von ``Siemens.Engineering.SW.Blocks.DataBlock`` ab."""
    from Siemens.Engineering.SW.Blocks import DataBlock

    for block, path in iter_blocks(plc_software):
        if isinstance(block, DataBlock):
            yield block, path


def iter_tag_tables(plc_software: Any) -> Iterator[Any]:
    """Durchläuft rekursiv alle Variablentabellen einer PLC-Software (inkl. Untergruppen)."""

    def _walk(tag_table_group: Any) -> Iterator[Any]:
        for tag_table in tag_table_group.TagTables:
            yield tag_table
        for subgroup in getattr(tag_table_group, "Groups", []):
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
    das ist nur über den XML-Export erreichbar (``Block.Export()``, in der
    Referenzdokumentation als reguläre Openness-Funktion belegt). Die
    Netzwerk-Checks in ``structure.py`` und ``libraries.py`` gehen davon aus,
    dass jedes Netzwerk als ``SW.Blocks.CompileUnit``-Element mit
    ``ProgrammingLanguage``/``Title``/``Comment``-Kindelementen auftaucht
    (öffentlich bekanntes SIMATIC-ML-Schema) — das ist **nicht** gegen einen
    echten Export in TIA Portal V21 verifiziert (siehe README, "Bekannte
    Einschränkungen") und sollte vor produktivem Einsatz an einem realen
    Projekt geprüft werden.
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


def cross_reference_locations(engineering_object: Any) -> list[Any]:
    """Liefert alle ``Location``-Objekte (mit ``Access``: Lesen/Schreiben)
    über alle Kreuzreferenzen eines Openness-Objekts (Tag, Baustein, ggf.
    Interface-Member — Letzteres laut Referenzdokumentation nicht
    abschließend belegt, siehe ``structure.py``/``libraries.py``)."""
    from Siemens.Engineering.CrossReference import CrossReferenceFilter, CrossReferenceService

    try:
        service = engineering_object.GetService[CrossReferenceService]()
    except Exception:  # noqa: BLE001 — Service evtl. für diesen Objekttyp nicht verfügbar
        return []
    if service is None:
        return []
    result = service.GetCrossReferences(CrossReferenceFilter.AllObjects)
    locations = []
    for reference in getattr(result, "References", []) or []:
        for location in getattr(reference, "Locations", []) or []:
            locations.append(location)
    return locations


def compile_unit_element_count(compile_unit: Any) -> int:
    """Zählt die Programmelemente (Kontakte, Spulen, Bausteinaufrufe, ...)
    eines Netzwerks anhand der ``Parts`` in seiner ``NetworkSource``."""
    count = 0
    for child in compile_unit.iter():
        if _local_name(child.tag) == "Part":
            count += 1
    return count
