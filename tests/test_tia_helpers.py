"""Tests für die Ordner-Traversierung in tia_linter.checks._tia_helpers.

``iter_blocks``/``iter_tag_tables`` haben keine .NET-/pythonnet-Importe auf
Modulebene (nur lokal innerhalb einzelner Funktionen wie ``iter_data_blocks``
oder ``export_block_xml``) und lassen sich daher mit einfachen Fake-Objekten
testen, ohne TIA Portal oder Windows zu benötigen.
"""

from __future__ import annotations

import logging
import sys
import types
from pathlib import Path

import pytest

import xml.etree.ElementTree as ET

from tia_linter.checks._tia_helpers import (
    export_block_xml,
    find_source_child_by_name,
    interface_section_member_paths,
    iter_blocks,
    iter_tag_tables,
    local_variable_access_paths,
    multilingual_text,
    normalize_member_path,
    cached_cross_reference_locations,
    cross_reference_referenced_top_level_names,
    cross_reference_root_source,
    cross_reference_tree_has_real_usage,
    read_comment,
    reset_export_cache,
    reset_xref_cache,
    set_export_cache_max_size,
    set_xref_cache_max_size,
    strip_cross_reference_prefix,
)


class FakeBlock:
    def __init__(self, name: str) -> None:
        self.Name = name


class FakeBlockGroup:
    def __init__(self, name: str = "", blocks: list | None = None, groups: list | None = None) -> None:
        self.Name = name
        self.Blocks = blocks or []
        self.Groups = groups or []


class FakePlcSoftwareBlocks:
    def __init__(self, block_group: FakeBlockGroup) -> None:
        self.BlockGroup = block_group


class FakeTagTable:
    def __init__(self, name: str) -> None:
        self.Name = name


class FakeTagTableGroup:
    def __init__(self, name: str = "", tag_tables: list | None = None, groups: list | None = None) -> None:
        self.Name = name
        self.TagTables = tag_tables or []
        self.Groups = groups or []


class FakePlcSoftwareTagTables:
    def __init__(self, tag_table_group: FakeTagTableGroup) -> None:
        self.TagTableGroup = tag_table_group


def _sample_block_tree() -> FakePlcSoftwareBlocks:
    #  Root
    #  ├── FB_A
    #  ├── Lib/
    #  │   ├── FB_B
    #  │   └── Old/
    #  │       └── FB_C
    #  └── Normal/
    #      └── FB_D
    old_group = FakeBlockGroup("Old", blocks=[FakeBlock("FB_C")])
    lib_group = FakeBlockGroup("Lib", blocks=[FakeBlock("FB_B")], groups=[old_group])
    normal_group = FakeBlockGroup("Normal", blocks=[FakeBlock("FB_D")])
    root = FakeBlockGroup("", blocks=[FakeBlock("FB_A")], groups=[lib_group, normal_group])
    return FakePlcSoftwareBlocks(root)


class TestIterBlocksExcludedFolders:
    def test_without_exclusion_returns_all_blocks(self) -> None:
        plc = _sample_block_tree()
        names = {block.Name for block, _ in iter_blocks(plc)}
        assert names == {"FB_A", "FB_B", "FB_C", "FB_D"}

    def test_excludes_named_folder_and_its_subfolders(self) -> None:
        plc = _sample_block_tree()
        names = {block.Name for block, _ in iter_blocks(plc, excluded_folders=["Lib"])}
        # FB_B (direkt in Lib) und FB_C (in Lib/Old, einem Unterordner von Lib)
        # muessen beide verschwinden -- die Kaskadierung auf Unterordner ist
        # der ganze Sinn des Features.
        assert names == {"FB_A", "FB_D"}

    def test_exclusion_is_case_insensitive(self) -> None:
        plc = _sample_block_tree()
        names = {block.Name for block, _ in iter_blocks(plc, excluded_folders=["lib"])}
        assert names == {"FB_A", "FB_D"}

    def test_excluding_unrelated_name_changes_nothing(self) -> None:
        plc = _sample_block_tree()
        names = {block.Name for block, _ in iter_blocks(plc, excluded_folders=["Nicht Vorhanden"])}
        assert names == {"FB_A", "FB_B", "FB_C", "FB_D"}

    def test_group_path_excludes_skipped_group(self) -> None:
        plc = _sample_block_tree()
        paths = {block.Name: path for block, path in iter_blocks(plc, excluded_folders=["Old"])}
        assert paths["FB_B"] == ["Lib"]
        assert "FB_C" not in paths  # lag in Lib/Old, Old ist ausgeschlossen


class TestIterBlocksExcludedBlocks:
    def test_without_exclusion_returns_all_blocks(self) -> None:
        plc = _sample_block_tree()
        names = {block.Name for block, _ in iter_blocks(plc, excluded_blocks=[])}
        assert names == {"FB_A", "FB_B", "FB_C", "FB_D"}

    def test_excludes_single_named_block_regardless_of_folder(self) -> None:
        plc = _sample_block_tree()
        # FB_C liegt tief verschachtelt in Lib/Old -- der Ordner selbst
        # bleibt erlaubt, nur der eine Baustein wird per Name ausgeschlossen.
        names = {block.Name for block, _ in iter_blocks(plc, excluded_blocks=["FB_C"])}
        assert names == {"FB_A", "FB_B", "FB_D"}

    def test_exclusion_is_case_insensitive(self) -> None:
        plc = _sample_block_tree()
        names = {block.Name for block, _ in iter_blocks(plc, excluded_blocks=["fb_c"])}
        assert names == {"FB_A", "FB_B", "FB_D"}

    def test_excluding_unrelated_name_changes_nothing(self) -> None:
        plc = _sample_block_tree()
        names = {block.Name for block, _ in iter_blocks(plc, excluded_blocks=["FB_Nicht_Vorhanden"])}
        assert names == {"FB_A", "FB_B", "FB_C", "FB_D"}

    def test_folder_and_block_exclusion_combine(self) -> None:
        plc = _sample_block_tree()
        # "Normal"-Ordner komplett raus, zusaetzlich FB_A einzeln per Name.
        names = {
            block.Name
            for block, _ in iter_blocks(plc, excluded_folders=["Normal"], excluded_blocks=["FB_A"])
        }
        assert names == {"FB_B", "FB_C"}


class TestIterTagTablesExcludedFolders:
    def _sample_tree(self) -> FakePlcSoftwareTagTables:
        #  Root (unbenannt)
        #  ├── Tags_Root
        #  └── Lib/
        #      ├── Tags_Lib
        #      └── Alt/
        #          └── Tags_Alt
        old_group = FakeTagTableGroup("Alt", tag_tables=[FakeTagTable("Tags_Alt")])
        lib_group = FakeTagTableGroup("Lib", tag_tables=[FakeTagTable("Tags_Lib")], groups=[old_group])
        root = FakeTagTableGroup("", tag_tables=[FakeTagTable("Tags_Root")], groups=[lib_group])
        return FakePlcSoftwareTagTables(root)

    def test_without_exclusion_returns_all_tag_tables(self) -> None:
        plc = self._sample_tree()
        names = {t.Name for t in iter_tag_tables(plc)}
        assert names == {"Tags_Root", "Tags_Lib", "Tags_Alt"}

    def test_excludes_named_folder_and_its_subfolders(self) -> None:
        plc = self._sample_tree()
        names = {t.Name for t in iter_tag_tables(plc, excluded_folders=["Lib"])}
        # Tags_Lib (direkt in Lib) und Tags_Alt (in Lib/Alt) muessen beide
        # verschwinden -- Kaskadierung auf Unterordner.
        assert names == {"Tags_Root"}

    def test_exclusion_is_case_insensitive(self) -> None:
        plc = self._sample_tree()
        names = {t.Name for t in iter_tag_tables(plc, excluded_folders=["LIB"])}
        assert names == {"Tags_Root"}


class FakeLanguage:
    """Simuliert ``Siemens.Engineering.Language`` — Gleichheit über den Namen,
    wie ``Language.Equals`` es für ``MultilingualTextItemComposition.Find``
    bräuchte."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other: object) -> bool:
        return isinstance(other, FakeLanguage) and other.name == self.name

    def __hash__(self) -> int:
        return hash(self.name)


class FakeMultilingualTextItem:
    def __init__(self, language: FakeLanguage, text: str) -> None:
        self.Language = language
        self.Text = text


class FakeMultilingualTextItemComposition:
    def __init__(self, items: list[FakeMultilingualTextItem]) -> None:
        self._items = items

    def Find(self, language: FakeLanguage) -> FakeMultilingualTextItem | None:
        return next((item for item in self._items if item.Language == language), None)


class FakeMultilingualText:
    def __init__(self, items: list[FakeMultilingualTextItem]) -> None:
        self.Items = FakeMultilingualTextItemComposition(items)


class FakeCommentedObject:
    """Simuliert ein Openness-Objekt mit typisierter ``Comment``-Property
    (z. B. ``PlcTag``/``PlcBlock``) — ``Comment`` liefert ein
    ``MultilingualText``-Objekt, keinen einfachen String."""

    def __init__(self, comment: FakeMultilingualText | None) -> None:
        self.Comment = comment


class FakeObjectWithoutComment:
    """Simuliert einen Openness-Objekttyp ganz ohne ``Comment``-Attribut."""


DE = FakeLanguage("de-DE")
EN = FakeLanguage("en-US")


class TestMultilingualText:
    def test_returns_text_for_matching_language(self) -> None:
        text = FakeMultilingualText(
            [FakeMultilingualTextItem(DE, "Hallo"), FakeMultilingualTextItem(EN, "Hello")]
        )
        assert multilingual_text(text, DE) == "Hallo"
        assert multilingual_text(text, EN) == "Hello"

    def test_returns_empty_string_when_language_missing(self) -> None:
        text = FakeMultilingualText([FakeMultilingualTextItem(EN, "Hello")])
        assert multilingual_text(text, DE) == ""

    def test_returns_empty_string_when_item_text_is_blank(self) -> None:
        text = FakeMultilingualText([FakeMultilingualTextItem(DE, "   ")])
        assert multilingual_text(text, DE) == ""

    def test_returns_empty_string_for_none_value(self) -> None:
        assert multilingual_text(None, DE) == ""

    def test_returns_empty_string_when_items_attribute_missing(self) -> None:
        class NoItems:
            pass

        assert multilingual_text(NoItems(), DE) == ""


class TestReadComment:
    """Deckt den ursprünglichen Bug ab: ``PlcTag.Comment``/``PlcBlock.Comment``
    sind mehrsprachig (``MultilingualText``) — ein naiver ``GetAttribute``-
    oder ``str(...)``-Zugriff darauf fand nie den Text der gewünschten
    Sprache, wodurch jede Variable fälschlich als unkommentiert galt."""

    def test_reads_comment_for_reference_language(self) -> None:
        obj = FakeCommentedObject(FakeMultilingualText([FakeMultilingualTextItem(DE, "Motorstart")]))
        assert read_comment(obj, DE) == "Motorstart"

    def test_comment_only_in_other_language_counts_as_missing(self) -> None:
        # Kommentar existiert nur auf Englisch, geprüft wird Deutsch (Referenzsprache)
        # -- das entspricht "Kommentar fehlt wirklich fuer diese Sprache", nicht einem Fehler.
        obj = FakeCommentedObject(FakeMultilingualText([FakeMultilingualTextItem(EN, "Motor start")]))
        assert read_comment(obj, DE) == ""

    def test_object_without_comment_attribute_returns_empty_string(self) -> None:
        assert read_comment(FakeObjectWithoutComment(), DE) == ""

    def test_object_with_none_comment_returns_empty_string(self) -> None:
        assert read_comment(FakeCommentedObject(None), DE) == ""


class TestNormalizeMemberPath:
    """Deckt den zweiten, unabhängigen Bug ab (User-Meldung, live an
    ``_Org > DDb > Fieldbus > Alm.4805_15A1`` im Salzmaschine-Projekt
    verifiziert): TIA quotet Namenssegmente, die keine gültigen "einfachen"
    Bezeichner sind (z. B. Ziffernbeginn), z. B. ``Alm."4805_15A1"`` statt
    ``Alm.4805_15A1`` -- ohne Normalisierung matcht das nie einen Eintrag aus
    den (immer unquotierten) Projekttexten."""

    def test_strips_quotes_from_single_segment(self) -> None:
        assert normalize_member_path('"4805_15A1"') == "4805_15A1"

    def test_strips_quotes_from_nested_segment_only(self) -> None:
        assert normalize_member_path('Alm."4805_15A1"') == "Alm.4805_15A1"

    def test_leaves_unquoted_segments_unchanged(self) -> None:
        assert normalize_member_path("Alm.Station_1") == "Alm.Station_1"

    def test_leaves_plain_name_unchanged(self) -> None:
        assert normalize_member_path("Fieldbus") == "Fieldbus"

    def test_strips_quotes_from_multiple_segments(self) -> None:
        assert normalize_member_path('"1Foo"."2Bar"') == "1Foo.2Bar"


class FakeSourceObject:
    def __init__(self, name: str, children: list["FakeSourceObject"] | None = None) -> None:
        self.Name = name
        self.Children = children or []


class TestFindSourceChildByName:
    """Prüfpunkte 26/27 (``static_zugriff_extern``/``output_mehrfach_beschrieben``)
    suchen Interface-Member im Kreuzreferenzbaum anhand eines aus dem
    XML-Export gewonnenen (unquotierten) Namens -- ``child.Name`` kann für
    Namen mit Ziffernbeginn quotiert sein, analog zum DB-Member-Kommentar-Bug."""

    def test_finds_direct_child_by_exact_name(self) -> None:
        root = FakeSourceObject("root", [FakeSourceObject("Foo")])
        found = find_source_child_by_name(root, "Foo")
        assert found is not None
        assert found.Name == "Foo"

    def test_finds_child_with_quoted_digit_prefixed_name(self) -> None:
        root = FakeSourceObject("root", [FakeSourceObject('"4805_15A1"')])
        found = find_source_child_by_name(root, "4805_15A1")
        assert found is not None
        assert found.Name == '"4805_15A1"'

    def test_finds_nested_child_with_quoted_name(self) -> None:
        nested = FakeSourceObject('"4805_15A1"')
        root = FakeSourceObject("root", [FakeSourceObject("Alm", [nested])])
        found = find_source_child_by_name(root, "4805_15A1")
        assert found is nested

    def test_returns_none_when_not_found(self) -> None:
        root = FakeSourceObject("root", [FakeSourceObject("Foo")])
        assert find_source_child_by_name(root, "Bar") is None


class TestStripCrossReferencePrefix:
    """Prüfpunkt 11a (DB-Zweig): das DB-Namenspräfix, das SourceObject.Name im
    Kreuzreferenzbaum gegenüber dem unqualifizierten Namen trägt."""

    def test_strips_unquoted_prefix(self) -> None:
        assert strip_cross_reference_prefix("DB_X.DiagCpu.DNNmode", "DB_X") == "DiagCpu.DNNmode"

    def test_strips_quoted_prefix(self) -> None:
        assert strip_cross_reference_prefix('"01PrgDb".lx_30M1StopGap', "01PrgDb") == "lx_30M1StopGap"

    def test_leaves_unmatched_name_unchanged(self) -> None:
        assert strip_cross_reference_prefix("Foo", "DB_X") == "Foo"

    def test_empty_root_name_leaves_name_unchanged(self) -> None:
        assert strip_cross_reference_prefix("DB_X.Foo", "") == "DB_X.Foo"


class TestInterfaceSectionMemberPaths:
    """Prüfpunkt 11a (FB/FC/OB-Zweig, ``unterelemente_pruefen``): vollständige
    Blattpfad-Auflösung je Top-Level-Member aus der Interface-Deklaration."""

    def test_scalar_member_is_its_own_single_leaf(self) -> None:
        xml_root = ET.fromstring(
            "<Document><Interface><Sections>"
            '<Section Name="Static"><Member Name="Scalar"/></Section>'
            "</Sections></Interface></Document>"
        )
        assert interface_section_member_paths(xml_root, "Static") == {"Scalar": ["Scalar"]}

    def test_nested_struct_member_resolves_dotted_leaf_paths(self) -> None:
        xml_root = ET.fromstring(
            "<Document><Interface><Sections><Section Name=\"Static\">"
            '<Member Name="Scalar"/>'
            '<Member Name="MyStruct"><Sections><Section Name="Static">'
            '<Member Name="a"/>'
            '<Member Name="b"><Sections><Section Name="Static">'
            '<Member Name="c"/>'
            "</Section></Sections></Member>"
            "</Section></Sections></Member>"
            "</Section></Sections></Interface></Document>"
        )
        result = interface_section_member_paths(xml_root, "Static")
        assert result == {
            "Scalar": ["Scalar"],
            "MyStruct": ["MyStruct.a", "MyStruct.b.c"],
        }

    def test_ignores_other_sections(self) -> None:
        xml_root = ET.fromstring(
            "<Document><Interface><Sections>"
            '<Section Name="Input"><Member Name="InVar"/></Section>'
            '<Section Name="Static"><Member Name="StaticVar"/></Section>'
            "</Sections></Interface></Document>"
        )
        assert interface_section_member_paths(xml_root, "Static") == {"StaticVar": ["StaticVar"]}

    def test_none_xml_root_returns_empty_dict(self) -> None:
        assert interface_section_member_paths(None, "Static") == {}


class TestLocalVariableAccessPaths:
    """Prüfpunkt 11a (FB/FC/OB-Zweig): dotted Zugriffspfade auf beliebiger
    Verschachtelungstiefe aus verschachtelten ``Component``-Zugriffsketten."""

    def test_scalar_access_yields_top_level_name(self) -> None:
        xml_root = ET.fromstring(
            "<Document><SW.Blocks.CompileUnit><NetworkSource><StructuredText>"
            '<Access Scope="LocalVariable"><Symbol><Component Name="Scalar"/></Symbol></Access>'
            "</StructuredText></NetworkSource></SW.Blocks.CompileUnit></Document>"
        )
        assert local_variable_access_paths(xml_root) == {"Scalar"}

    def test_nested_struct_access_yields_dotted_path(self) -> None:
        """Live an FB ``PrgFieldbusOk`` verifiziert: TIA exportiert
        ``DiagCpu.SubordinateIOState`` als Geschwister-``Component``-Elemente
        direkt unter ``Symbol``, nicht ineinander verschachtelt."""
        xml_root = ET.fromstring(
            "<Document><SW.Blocks.CompileUnit><NetworkSource><StructuredText>"
            '<Access Scope="LocalVariable"><Symbol>'
            '<Component Name="MyStruct"/><Component Name="a"/>'
            "</Symbol></Access>"
            "</StructuredText></NetworkSource></SW.Blocks.CompileUnit></Document>"
        )
        assert local_variable_access_paths(xml_root) == {"MyStruct.a"}

    def test_multi_instance_call_yields_instance_name(self) -> None:
        xml_root = ET.fromstring(
            "<Document><SW.Blocks.CompileUnit><NetworkSource><StructuredText>"
            '<Instance Scope="LocalVariable"><Component Name="lu_Inst"/></Instance>'
            "</StructuredText></NetworkSource></SW.Blocks.CompileUnit></Document>"
        )
        assert local_variable_access_paths(xml_root) == {"lu_Inst"}

    def test_ignores_non_local_variable_scope(self) -> None:
        xml_root = ET.fromstring(
            "<Document><SW.Blocks.CompileUnit><NetworkSource><StructuredText>"
            '<Access Scope="GlobalVariable"><Symbol><Component Name="Tag"/></Symbol></Access>'
            "</StructuredText></NetworkSource></SW.Blocks.CompileUnit></Document>"
        )
        assert local_variable_access_paths(xml_root) == set()

    def test_none_xml_root_returns_empty_set(self) -> None:
        assert local_variable_access_paths(None) == set()


class _FakeExportOptions:
    WithDefaults = object()


class _FakeFileInfo:
    def __init__(self, path: str) -> None:
        self.path = path


def _install_fake_dotnet_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ersetzt ``Siemens.Engineering``/``System.IO`` durch reine Python-Fakes
    in ``sys.modules``, damit ``export_block_xml`` (siehe ``_tia_helpers.py``)
    ohne echtes TIA Portal/pythonnet getestet werden kann — die beiden lokalen
    Imports in ``export_block_xml`` greifen dadurch auf die Fakes statt auf
    echte .NET-Assemblies zu."""
    siemens_engineering = types.ModuleType("Siemens.Engineering")
    siemens_engineering.ExportOptions = _FakeExportOptions
    siemens_pkg = types.ModuleType("Siemens")
    siemens_pkg.Engineering = siemens_engineering

    system_io = types.ModuleType("System.IO")
    system_io.FileInfo = _FakeFileInfo
    system_pkg = types.ModuleType("System")
    system_pkg.IO = system_io

    monkeypatch.setitem(sys.modules, "Siemens", siemens_pkg)
    monkeypatch.setitem(sys.modules, "Siemens.Engineering", siemens_engineering)
    monkeypatch.setitem(sys.modules, "System", system_pkg)
    monkeypatch.setitem(sys.modules, "System.IO", system_io)


class FakeExportableBlock:
    """Simuliert einen Baustein mit ``.Export()`` — zählt Aufrufe und
    schreibt bei Erfolg eine minimale, gültige XML-Datei an den übergebenen
    Pfad, analog zum echten ``block.Export(FileInfo, ExportOptions)``."""

    def __init__(self, name: str) -> None:
        self.Name = name
        self.export_call_count = 0

    def Export(self, file_info: _FakeFileInfo, options: object) -> None:
        self.export_call_count += 1
        Path(file_info.path).write_text("<Document/>")


class FakePlcSoftwareForExport:
    def __init__(self, name: str) -> None:
        self.Name = name


class TestExportBlockXmlCache:
    """Bis zu 10 Prüfpunkte riefen ``export_block_xml()`` für denselben
    Baustein bisher unabhängig voneinander auf (siehe
    ``XML-Optimierung-Analysebericht.md``, Schritt 1/2) — ein typischer FB
    wurde dadurch pro Lint-Lauf bis zu 8-mal exportiert. Der lauf-gebundene
    Cache muss zwei Aufrufe mit demselben Baustein auf genau einen echten
    ``block.Export()``-Aufruf reduzieren, dabei aber verschiedene Bausteine
    (auch bei gleichem Namen auf unterschiedlichen PLCs) weiterhin
    unabhängig behandeln und nach einem expliziten Reset erneut exportieren."""

    def setup_method(self) -> None:
        reset_export_cache()

    def teardown_method(self) -> None:
        reset_export_cache()
        set_export_cache_max_size(500)  # Standardwert aus default.yaml wiederherstellen

    def test_second_call_with_same_block_uses_cache(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_dotnet_modules(monkeypatch)
        block = FakeExportableBlock("FB_A")
        plc = FakePlcSoftwareForExport("PLC_1")

        first = export_block_xml(block, plc)
        second = export_block_xml(block, plc)

        assert block.export_call_count == 1
        assert first is second

    def test_different_blocks_are_exported_independently(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_dotnet_modules(monkeypatch)
        block_a = FakeExportableBlock("FB_A")
        block_b = FakeExportableBlock("FB_B")
        plc = FakePlcSoftwareForExport("PLC_1")

        export_block_xml(block_a, plc)
        export_block_xml(block_b, plc)

        assert block_a.export_call_count == 1
        assert block_b.export_call_count == 1

    def test_same_block_name_on_different_plc_is_exported_separately(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Blocknamen sind nur innerhalb einer PLC eindeutig, siehe Docstring
        # von export_block_xml -- der Cache-Key muss die PLC mit einbeziehen.
        _install_fake_dotnet_modules(monkeypatch)
        block_1 = FakeExportableBlock("FB_A")
        block_2 = FakeExportableBlock("FB_A")
        plc_1 = FakePlcSoftwareForExport("PLC_1")
        plc_2 = FakePlcSoftwareForExport("PLC_2")

        export_block_xml(block_1, plc_1)
        export_block_xml(block_2, plc_2)

        assert block_1.export_call_count == 1
        assert block_2.export_call_count == 1

    def test_reset_export_cache_forces_reexport(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Simuliert einen TIA-Portal-Reconnect: runner.py ruft
        # reset_export_cache() auf, danach muss derselbe Baustein erneut
        # exportiert werden, weil er ein neues .NET-Objekt ist.
        _install_fake_dotnet_modules(monkeypatch)
        block = FakeExportableBlock("FB_A")
        plc = FakePlcSoftwareForExport("PLC_1")

        export_block_xml(block, plc)
        reset_export_cache()
        export_block_xml(block, plc)

        assert block.export_call_count == 2

    def test_failed_export_is_not_cached_and_is_retried(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_dotnet_modules(monkeypatch)

        class FailingThenSucceedingBlock(FakeExportableBlock):
            def Export(self, file_info: _FakeFileInfo, options: object) -> None:
                self.export_call_count += 1
                if self.export_call_count == 1:
                    raise RuntimeError("simulierter Exportfehler")
                Path(file_info.path).write_text("<Document/>")

        block = FailingThenSucceedingBlock("FB_A")
        plc = FakePlcSoftwareForExport("PLC_1")

        assert export_block_xml(block, plc) is None
        assert export_block_xml(block, plc) is not None
        assert block.export_call_count == 2

    def test_lru_eviction_drops_oldest_unused_entry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Maßnahme 2 (Review-Performance.md): Cache-Größe begrenzt, damit er
        # bei sehr großen Projekten (mehrere Tausend Bausteine) nicht
        # unbeschränkt wächst — das am längsten unbenutzte Element muss beim
        # Erreichen der Maxgröße verdrängt werden.
        _install_fake_dotnet_modules(monkeypatch)
        set_export_cache_max_size(2)
        block_a = FakeExportableBlock("FB_A")
        block_b = FakeExportableBlock("FB_B")
        block_c = FakeExportableBlock("FB_C")
        plc = FakePlcSoftwareForExport("PLC_1")

        export_block_xml(block_a, plc)
        export_block_xml(block_b, plc)
        export_block_xml(block_c, plc)  # verdrängt FB_A (ältester Eintrag, Cache voll)

        export_block_xml(block_b, plc)
        assert block_b.export_call_count == 1  # war noch im Cache

        export_block_xml(block_a, plc)
        assert block_a.export_call_count == 2  # musste erneut exportiert werden (wurde verdrängt)

    def test_lru_access_refreshes_entry_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_dotnet_modules(monkeypatch)
        set_export_cache_max_size(2)
        block_a = FakeExportableBlock("FB_A")
        block_b = FakeExportableBlock("FB_B")
        block_c = FakeExportableBlock("FB_C")
        plc = FakePlcSoftwareForExport("PLC_1")

        export_block_xml(block_a, plc)
        export_block_xml(block_b, plc)
        export_block_xml(block_a, plc)  # FB_A erneut zugegriffen -> jetzt zuletzt verwendet
        export_block_xml(block_c, plc)  # verdrängt FB_B, nicht FB_A

        export_block_xml(block_a, plc)
        assert block_a.export_call_count == 1  # war noch im Cache

        export_block_xml(block_b, plc)
        assert block_b.export_call_count == 2  # musste erneut exportiert werden


class _FakeGenericMethod:
    """Simuliert pythonnets generische Methodensyntax ``obj.Method[Type]()``
    (hier: ``obj.GetService[CrossReferenceService]()``) — ``__getitem__``
    ignoriert den Typ-Parameter und liefert immer denselben gebundenen
    Rückgabewert, das reicht für die Tests hier."""

    def __init__(self, return_value: object) -> None:
        self._return_value = return_value

    def __getitem__(self, _type: object) -> object:
        return lambda: self._return_value


class FakeXrefLocation:
    def __init__(self, access: str, reference_type: str, reference_location: str = "") -> None:
        self.Access = access
        self.ReferenceType = reference_type
        self.ReferenceLocation = reference_location


class FakeXrefReference:
    def __init__(self, locations: list[FakeXrefLocation]) -> None:
        self.Locations = locations


class FakeXrefSourceObject:
    def __init__(
        self, references: list[FakeXrefReference], children: list["FakeXrefSourceObject"] | None = None
    ) -> None:
        self.References = references
        self.Children = children or []


class FakeXrefResult:
    def __init__(self, sources: list[FakeXrefSourceObject]) -> None:
        self.Sources = sources


class FakeCrossReferenceService:
    def __init__(self, sources: list[FakeXrefSourceObject]) -> None:
        self._sources = sources
        self.call_count = 0

    def GetCrossReferences(self, cross_reference_filter: object) -> FakeXrefResult:
        self.call_count += 1
        return FakeXrefResult(self._sources)


class FakeXrefObject:
    def __init__(self, name: str, service: FakeCrossReferenceService) -> None:
        self.Name = name
        self.GetService = _FakeGenericMethod(service)


def _install_fake_cross_reference_module(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ersetzt ``Siemens.Engineering.CrossReference`` durch ein Fake-Modul,
    damit ``cross_reference_root_source``/``cached_cross_reference_locations``
    (lokaler Import von ``CrossReferenceFilter``/``CrossReferenceService``)
    ohne echtes TIA Portal getestet werden können."""
    cross_reference = types.ModuleType("Siemens.Engineering.CrossReference")
    cross_reference.CrossReferenceService = object()
    cross_reference.CrossReferenceFilter = types.SimpleNamespace(
        AllObjects="AllObjects", UnusedObjects="UnusedObjects", ObjectsWithReferences="ObjectsWithReferences"
    )
    engineering = types.ModuleType("Siemens.Engineering")
    engineering.CrossReference = cross_reference
    siemens = types.ModuleType("Siemens")
    siemens.Engineering = engineering

    monkeypatch.setitem(sys.modules, "Siemens", siemens)
    monkeypatch.setitem(sys.modules, "Siemens.Engineering", engineering)
    monkeypatch.setitem(sys.modules, "Siemens.Engineering.CrossReference", cross_reference)


class TestCachedCrossReferenceLocations:
    """Maßnahme 4 (Review-Performance.md, Befund 4.2): CrossReference-
    Abfragen wurden bislang unabhängig voneinander wiederholt, obwohl
    mehrere Prüfpunkte (11a, 12a/12b, 13) dieselben Tags mit demselben
    Filter abfragen. Der Cache muss zwei Aufrufe mit identischem
    (plc_name, obj_name, filter) auf genau einen echten
    ``GetCrossReferences()``-Aufruf reduzieren, dabei aber unterschiedliche
    PLCs/Filter weiterhin unabhängig behandeln, extrahierte Python-Strings
    statt roher .NET-Objekte liefern und nach einem expliziten Reset erneut
    abfragen."""

    def setup_method(self) -> None:
        reset_xref_cache()

    def teardown_method(self) -> None:
        reset_xref_cache()
        set_xref_cache_max_size(1000)  # Standardwert aus default.yaml wiederherstellen

    def test_extracts_access_and_reference_type_as_strings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_cross_reference_module(monkeypatch)
        source = FakeXrefSourceObject([FakeXrefReference([FakeXrefLocation("Read", "UsedBy")])])
        service = FakeCrossReferenceService([source])
        obj = FakeXrefObject("Sensor1", service)

        result = cached_cross_reference_locations(obj, "AllObjects", "PLC_1")

        assert result == [("Read", "UsedBy")]

    def test_second_call_with_same_key_uses_cache(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_cross_reference_module(monkeypatch)
        source = FakeXrefSourceObject([FakeXrefReference([FakeXrefLocation("Write", "UsedBy")])])
        service = FakeCrossReferenceService([source])
        obj = FakeXrefObject("Sensor1", service)

        first = cached_cross_reference_locations(obj, "AllObjects", "PLC_1")
        second = cached_cross_reference_locations(obj, "AllObjects", "PLC_1")

        assert service.call_count == 1
        assert first == second == [("Write", "UsedBy")]

    def test_different_plc_name_is_queried_separately(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Objektnamen sind nur innerhalb einer PLC eindeutig, siehe Docstring
        # von cached_cross_reference_locations -- der Cache-Key muss die PLC
        # mit einbeziehen (analog zu export_block_xml, Maßnahme 2).
        _install_fake_cross_reference_module(monkeypatch)
        source = FakeXrefSourceObject([FakeXrefReference([FakeXrefLocation("Read", "UsedBy")])])
        service = FakeCrossReferenceService([source])
        obj = FakeXrefObject("Sensor1", service)

        cached_cross_reference_locations(obj, "AllObjects", "PLC_1")
        cached_cross_reference_locations(obj, "AllObjects", "PLC_2")

        assert service.call_count == 2

    def test_different_filter_is_queried_separately(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_cross_reference_module(monkeypatch)
        source = FakeXrefSourceObject([FakeXrefReference([FakeXrefLocation("Read", "UsedBy")])])
        service = FakeCrossReferenceService([source])
        obj = FakeXrefObject("Sensor1", service)

        cached_cross_reference_locations(obj, "AllObjects", "PLC_1")
        cached_cross_reference_locations(obj, "UnusedObjects", "PLC_1")

        assert service.call_count == 2

    def test_reset_xref_cache_forces_requery(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_cross_reference_module(monkeypatch)
        source = FakeXrefSourceObject([FakeXrefReference([FakeXrefLocation("Read", "UsedBy")])])
        service = FakeCrossReferenceService([source])
        obj = FakeXrefObject("Sensor1", service)

        cached_cross_reference_locations(obj, "AllObjects", "PLC_1")
        reset_xref_cache()
        cached_cross_reference_locations(obj, "AllObjects", "PLC_1")

        assert service.call_count == 2

    def test_lru_eviction_drops_oldest_unused_entry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_cross_reference_module(monkeypatch)
        set_xref_cache_max_size(2)
        service_a = FakeCrossReferenceService([FakeXrefSourceObject([])])
        service_b = FakeCrossReferenceService([FakeXrefSourceObject([])])
        service_c = FakeCrossReferenceService([FakeXrefSourceObject([])])
        obj_a = FakeXrefObject("Sensor_A", service_a)
        obj_b = FakeXrefObject("Sensor_B", service_b)
        obj_c = FakeXrefObject("Sensor_C", service_c)

        cached_cross_reference_locations(obj_a, "AllObjects", "PLC_1")
        cached_cross_reference_locations(obj_b, "AllObjects", "PLC_1")
        cached_cross_reference_locations(obj_c, "AllObjects", "PLC_1")  # verdrängt Sensor_A (ältester Eintrag)

        cached_cross_reference_locations(obj_b, "AllObjects", "PLC_1")
        assert service_b.call_count == 1  # war noch im Cache

        cached_cross_reference_locations(obj_a, "AllObjects", "PLC_1")
        assert service_a.call_count == 2  # musste erneut abgefragt werden (wurde verdrängt)


class FakeTopLevelChild:
    def __init__(
        self,
        name: str,
        references: list[FakeXrefReference] | None = None,
        children: list["FakeTopLevelChild"] | None = None,
    ) -> None:
        self.Name = name
        # Default: eine echte Nutzung (ReferenceType != InstanceType) -- die
        # meisten bestehenden Tests prüfen das Cache-Verhalten, nicht die
        # Referenz-Filterung selbst, daher default auf "wird verwendet".
        self.References = (
            references if references is not None else [FakeXrefReference([FakeXrefLocation("Undefined", "UsedBy")])]
        )
        self.Children = children if children is not None else []


class FakeTopLevelSource:
    def __init__(self, name: str, children: list[FakeTopLevelChild]) -> None:
        self.Name = name
        self.Children = children


class TestCrossReferenceTreeHasRealUsage:
    """Dreiunddreißigster/Vierunddreißigster/Sechsunddreißigster Bug:
    ``cross_reference_tree_has_real_usage()`` muss rekursiv den ganzen Baum
    prüfen, ``InstanceType``-Meta-Referenzen ignorieren, und optional
    Referenzen ausblenden, die vom eigenen Quell-FB selbst kommen (Instanz-
    DB-Fall, ``LSNTP_ServerDb_1``)."""

    def test_direct_reference_is_detected(self) -> None:
        node = FakeXrefSourceObject([FakeXrefReference([FakeXrefLocation("Read", "UsedBy")])])

        assert cross_reference_tree_has_real_usage(node) is True

    def test_no_reference_anywhere_is_not_used(self) -> None:
        node = FakeXrefSourceObject([])

        assert cross_reference_tree_has_real_usage(node) is False

    def test_only_instancetype_reference_is_not_used(self) -> None:
        node = FakeXrefSourceObject([FakeXrefReference([FakeXrefLocation("Declaration", "InstanceType")])])

        assert cross_reference_tree_has_real_usage(node) is False

    def test_reference_on_grandchild_is_detected(self) -> None:
        """Vierunddreißigster Bug (ConfigDb): das Kind selbst hat 0 eigene
        References, das Enkelkind traegt die echte Referenz."""
        leaf = FakeXrefSourceObject([FakeXrefReference([FakeXrefLocation("Read", "UsedBy")])])
        child = FakeXrefSourceObject([], children=[leaf])
        root = FakeXrefSourceObject([], children=[child])

        assert cross_reference_tree_has_real_usage(root) is True

    def test_self_reference_from_own_fb_is_excluded(self) -> None:
        """Sechsunddreißigster Bug (LSNTP_ServerDb_1): eine Referenz, deren
        ReferenceLocation auf den eigenen Quell-FB zeigt, zaehlt nicht als
        Verwendung, wenn exclude_referencing_block gesetzt ist."""
        node = FakeXrefSourceObject(
            [FakeXrefReference([FakeXrefLocation("Read", "UsedBy", "@LSNTP_Server ▶ Ln: 1   Cl: 1")])]
        )

        assert cross_reference_tree_has_real_usage(node, exclude_referencing_block="LSNTP_Server") is False

    def test_quoted_self_reference_with_member_path_is_excluded(self) -> None:
        """Sechsunddreißigster Bug, zweiter Teil (live an
        LSNTP_ServerDb_1.lastTimeSet gefunden): ReferenceLocation tritt auch
        im Format '@"Block".Member ▶ Beschreibung' auf (z. B. bei
        Access=DefaultValue/'Default value') -- der urspruengliche Regex
        erkannte den Blocknamen hier nicht, weil vor '▶' kein Leerzeichen
        steht."""
        node = FakeXrefSourceObject(
            [FakeXrefReference([FakeXrefLocation("DefaultValue", "Uses", '@"LSNTP_Server".lastTimeSet ▶ Default value')])]
        )

        assert cross_reference_tree_has_real_usage(node, exclude_referencing_block="LSNTP_Server") is False

    def test_self_reference_without_exclude_parameter_still_counts(self) -> None:
        """Ohne exclude_referencing_block (Global-/Array-DB-Fall) bleibt das
        bisherige Verhalten unveraendert -- jede Nicht-InstanceType-Referenz
        zaehlt."""
        node = FakeXrefSourceObject(
            [FakeXrefReference([FakeXrefLocation("Read", "UsedBy", "@LSNTP_Server ▶ Ln: 1   Cl: 1")])]
        )

        assert cross_reference_tree_has_real_usage(node) is True

    def test_reference_from_different_block_is_not_excluded(self) -> None:
        """Ein echter externer Zugriff (anderer Baustein als der Quell-FB,
        z. B. ein genereller Aufruf oder externer Static-Zugriff wie bei
        01TestOrgPrgDb) zaehlt weiterhin als Verwendung."""
        node = FakeXrefSourceObject(
            [FakeXrefReference([FakeXrefLocation("Undefined", "UsedBy", "@OrgPrg ▶ NW12")])]
        )

        assert cross_reference_tree_has_real_usage(node, exclude_referencing_block="LSNTP_Server") is True

    def test_self_reference_excluded_but_external_reference_on_sibling_detected(self) -> None:
        """Realistischer Mischfall: die meisten Member zeigen nur interne
        Selbstreferenzen (ausgeblendet), aber ein einzelnes Member wird
        zusaetzlich echt von aussen verwendet -- muss trotzdem als benutzt
        erkannt werden."""
        internal_only = FakeXrefSourceObject(
            [FakeXrefReference([FakeXrefLocation("Read", "UsedBy", "@LSNTP_Server ▶ Ln: 1   Cl: 1")])]
        )
        externally_used = FakeXrefSourceObject(
            [FakeXrefReference([FakeXrefLocation("Undefined", "UsedBy", "@OrgPrg ▶ NW12")])]
        )
        root = FakeXrefSourceObject([], children=[internal_only, externally_used])

        assert cross_reference_tree_has_real_usage(root, exclude_referencing_block="LSNTP_Server") is True


class TestCrossReferenceReferencedTopLevelNamesCache:
    """Maßnahme (Review-Performance.md, Befund 3.2): Prüfpunkt 11a (bei
    Unused-Objects-Befunden) und Prüfpunkt 11b (unbedingt) fragen für
    denselben Global-/Array-DB denselben ``ObjectsWithReferences``-Filter ab
    -- eine echte Verdopplung, wenn beide Checks aktiv sind. Der Cache muss
    das auf einen echten ``GetCrossReferences()``-Aufruf reduzieren, dabei
    aber verschiedene PLCs weiterhin unabhängig behandeln und sich denselben
    Reset/dieselbe LRU-Größe wie ``cached_cross_reference_locations`` teilen
    (siehe Docstring der Funktion)."""

    def setup_method(self) -> None:
        reset_xref_cache()

    def teardown_method(self) -> None:
        reset_xref_cache()
        set_xref_cache_max_size(1000)  # Standardwert aus default.yaml wiederherstellen

    def test_extracts_child_names(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_cross_reference_module(monkeypatch)
        source = FakeTopLevelSource("DB_X", [FakeTopLevelChild('"DB_X".Member1')])
        service = FakeCrossReferenceService([source])
        obj = FakeXrefObject("DB_X", service)

        result = cross_reference_referenced_top_level_names(obj, "PLC_1")

        assert result == {"Member1"}

    def test_second_call_with_same_key_uses_cache(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_cross_reference_module(monkeypatch)
        source = FakeTopLevelSource("DB_X", [FakeTopLevelChild('"DB_X".Member1')])
        service = FakeCrossReferenceService([source])
        obj = FakeXrefObject("DB_X", service)

        first = cross_reference_referenced_top_level_names(obj, "PLC_1")
        second = cross_reference_referenced_top_level_names(obj, "PLC_1")

        assert service.call_count == 1
        assert first == second == {"Member1"}

    def test_child_without_any_reference_is_not_counted_as_used(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Dreiunddreißigster Bug (live an Global-DB 'A03' verifiziert):
        ObjectsWithReferences listete Kinder ganz ohne echte References."""
        _install_fake_cross_reference_module(monkeypatch)
        source = FakeTopLevelSource("DB_X", [FakeTopLevelChild('"DB_X".Member1', references=[])])
        service = FakeCrossReferenceService([source])
        obj = FakeXrefObject("DB_X", service)

        result = cross_reference_referenced_top_level_names(obj, "PLC_1")

        assert result == set()

    def test_child_with_only_instancetype_reference_is_not_counted_as_used(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Dreiunddreißigster Bug: dieselbe permanente InstanceType-Meta-
        Referenz, die schon beim Siebenundzwanzigster-Bug-Fix (Instanz-DB-
        Root) gefiltert wurde, tritt auch auf FB-instanztypisierten
        Struct-Membern auf und darf nicht als echte Nutzung zählen."""
        _install_fake_cross_reference_module(monkeypatch)
        child = FakeTopLevelChild(
            '"DB_X".Member1', references=[FakeXrefReference([FakeXrefLocation("Declaration", "InstanceType")])]
        )
        source = FakeTopLevelSource("DB_X", [child])
        service = FakeCrossReferenceService([source])
        obj = FakeXrefObject("DB_X", service)

        result = cross_reference_referenced_top_level_names(obj, "PLC_1")

        assert result == set()

    def test_child_with_real_reference_alongside_instancetype_is_counted_as_used(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ein tatsächlich genutzter FB-instanztypisierter Member trägt neben
        der permanenten InstanceType-Referenz mindestens eine echte
        Uses/UsedBy-Referenz -- die muss weiterhin als Nutzung erkannt
        werden."""
        _install_fake_cross_reference_module(monkeypatch)
        child = FakeTopLevelChild(
            '"DB_X".Member1',
            references=[
                FakeXrefReference([FakeXrefLocation("Declaration", "InstanceType")]),
                FakeXrefReference([FakeXrefLocation("Undefined", "UsedBy")]),
            ],
        )
        source = FakeTopLevelSource("DB_X", [child])
        service = FakeCrossReferenceService([source])
        obj = FakeXrefObject("DB_X", service)

        result = cross_reference_referenced_top_level_names(obj, "PLC_1")

        assert result == {"Member1"}

    def test_grandchild_reference_is_detected_recursively(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Vierunddreißigster Bug (live an Global-DB 'ConfigDb' verifiziert):
        das Top-Level-Kind selbst kann 0 eigene References haben, während
        die echte Nutzung erst an einem Enkel-Blatt sichtbar wird (z. B.
        "ConfigDb".Exists.BlowOff bei einem Top-Level-Struct "Exists")."""
        _install_fake_cross_reference_module(monkeypatch)
        leaf = FakeTopLevelChild(
            '"DB_X".Member1.Leaf', references=[FakeXrefReference([FakeXrefLocation("Read", "UsedBy")])]
        )
        child = FakeTopLevelChild('"DB_X".Member1', references=[], children=[leaf])
        source = FakeTopLevelSource("DB_X", [child])
        service = FakeCrossReferenceService([source])
        obj = FakeXrefObject("DB_X", service)

        result = cross_reference_referenced_top_level_names(obj, "PLC_1")

        assert result == {"Member1"}

    def test_grandchild_with_only_instancetype_reference_is_not_counted_as_used(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_fake_cross_reference_module(monkeypatch)
        leaf = FakeTopLevelChild(
            '"DB_X".Member1.Leaf', references=[FakeXrefReference([FakeXrefLocation("Declaration", "InstanceType")])]
        )
        child = FakeTopLevelChild('"DB_X".Member1', references=[], children=[leaf])
        source = FakeTopLevelSource("DB_X", [child])
        service = FakeCrossReferenceService([source])
        obj = FakeXrefObject("DB_X", service)

        result = cross_reference_referenced_top_level_names(obj, "PLC_1")

        assert result == set()

    def test_different_plc_name_is_queried_separately(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_cross_reference_module(monkeypatch)
        source = FakeTopLevelSource("DB_X", [FakeTopLevelChild('"DB_X".Member1')])
        service = FakeCrossReferenceService([source])
        obj = FakeXrefObject("DB_X", service)

        cross_reference_referenced_top_level_names(obj, "PLC_1")
        cross_reference_referenced_top_level_names(obj, "PLC_2")

        assert service.call_count == 2

    def test_reset_xref_cache_forces_requery(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_cross_reference_module(monkeypatch)
        source = FakeTopLevelSource("DB_X", [FakeTopLevelChild('"DB_X".Member1')])
        service = FakeCrossReferenceService([source])
        obj = FakeXrefObject("DB_X", service)

        cross_reference_referenced_top_level_names(obj, "PLC_1")
        reset_xref_cache()
        cross_reference_referenced_top_level_names(obj, "PLC_1")

        assert service.call_count == 2

    def test_shares_lru_max_size_with_cached_cross_reference_locations(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # set_xref_cache_max_size() setzt einen gemeinsamen Größenparameter
        # (siehe Docstring von cross_reference_referenced_top_level_names) --
        # belegt hier, dass er auch für diesen (separaten) Cache greift.
        _install_fake_cross_reference_module(monkeypatch)
        set_xref_cache_max_size(1)
        service_a = FakeCrossReferenceService([FakeTopLevelSource("DB_A", [])])
        service_b = FakeCrossReferenceService([FakeTopLevelSource("DB_B", [])])
        obj_a = FakeXrefObject("DB_A", service_a)
        obj_b = FakeXrefObject("DB_B", service_b)

        cross_reference_referenced_top_level_names(obj_a, "PLC_1")
        cross_reference_referenced_top_level_names(obj_b, "PLC_1")  # verdrängt DB_A (Cache-Größe 1)

        cross_reference_referenced_top_level_names(obj_a, "PLC_1")
        assert service_a.call_count == 2  # wurde verdrängt, musste erneut abgefragt werden


class _FakeRaisingGenericMethod:
    """Wie ``_FakeGenericMethod``, aber ``__getitem__`` liefert einen
    Aufrufer, der beim Aufruf eine .NET-Exception simuliert (``GetService``
    für einen nicht unterstützten Objekttyp)."""

    def __getitem__(self, _type: object) -> object:
        def _raise() -> None:
            raise RuntimeError("GetService nicht unterstützt für diesen Objekttyp")

        return _raise


class TestCrossReferenceServiceUnavailableLogsWarning:
    """Review-Security-Robustheit.md, Befund 3.1/3.2: Schlägt
    ``GetService[CrossReferenceService]()`` fehl, lieferten
    ``cross_reference_root_source``/``cross_reference_referenced_top_level_names``
    bisher stillschweigend ein leeres Ergebnis -- ununterscheidbar vom
    legitimen "keine Referenzen". Jetzt muss mindestens ein ``WARNING``
    geloggt werden, damit ein daraus resultierender Fehlalarm in der Logdatei
    nachvollziehbar ist."""

    def test_root_source_logs_warning_on_service_error(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        _install_fake_cross_reference_module(monkeypatch)
        obj = types.SimpleNamespace(Name="Sensor1", GetService=_FakeRaisingGenericMethod())

        with caplog.at_level(logging.WARNING):
            result = cross_reference_root_source(obj)

        assert result is None
        assert any(record.levelno == logging.WARNING and "Sensor1" in record.message for record in caplog.records)

    def test_top_level_names_logs_warning_on_service_error(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        _install_fake_cross_reference_module(monkeypatch)
        obj = types.SimpleNamespace(Name="DB_X", GetService=_FakeRaisingGenericMethod())

        with caplog.at_level(logging.WARNING):
            result = cross_reference_referenced_top_level_names(obj, "PLC_1")

        assert result == set()
        assert any(record.levelno == logging.WARNING and "DB_X" in record.message for record in caplog.records)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
