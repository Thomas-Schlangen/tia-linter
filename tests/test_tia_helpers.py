"""Tests für die Ordner-Traversierung in tia_linter.checks._tia_helpers.

``iter_blocks``/``iter_tag_tables`` haben keine .NET-/pythonnet-Importe auf
Modulebene (nur lokal innerhalb einzelner Funktionen wie ``iter_data_blocks``
oder ``export_block_xml``) und lassen sich daher mit einfachen Fake-Objekten
testen, ohne TIA Portal oder Windows zu benötigen.
"""

from __future__ import annotations

import pytest

from tia_linter.checks._tia_helpers import iter_blocks, iter_tag_tables


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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
