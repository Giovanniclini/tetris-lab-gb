#!/usr/bin/env python3
"""Generate TREP metadata from the build's symbol and map files.

TREP is Tolstoj's ROM editor (https://tolstoj-82.github.io/apps/trep/): it opens a
built ROM and shows its tilesets and background maps as editable pictures. It reads
the ROM, the .sym, the .map and this metadata; it writes back exported map data, never
a ROM. Nothing here runs TREP - the build simply publishes a map of itself.

Written by Tolstoj and adapted, 2026-08-23. Note this only works because build.py
assembles with -E, which exports single-colon labels into the .sym.
"""

import json
import re
import sys
from pathlib import Path


def rom_offset(bank, address):
    if bank == 0:
        return address if address < 0x4000 else None
    if 0x4000 <= address <= 0x7FFF:
        return bank * 0x4000 + address - 0x4000
    return None


def parse_symbols(sym_text, map_text):
    symbols = {}
    for line in sym_text.splitlines():
        match = re.match(r"\s*([0-9A-Fa-f]+):([0-9A-Fa-f]{4})\s+([^;\s]+)", line)
        if match:
            offset = rom_offset(int(match[1], 16), int(match[2], 16))
            if offset is not None:
                symbols.setdefault(match[3], offset)

    bank = None
    for line in map_text.splitlines():
        bank_match = re.match(r"ROM(?:0|X) bank #(\d+):", line, re.IGNORECASE)
        if bank_match:
            bank = int(bank_match[1])
        label_match = re.match(r"\s*\$([0-9A-Fa-f]{4})\s*=\s*([^\s]+)", line)
        if label_match and bank is not None and label_match[2] not in symbols:
            offset = rom_offset(bank, int(label_match[1], 16))
            if offset is not None:
                symbols[label_match[2]] = offset
    return symbols


def generate(source_path, sym_path, map_path, output_path):
    """Resolve every symbol in the manifest and write the metadata TREP reads."""
    source_path, sym_path, map_path, output_path = map(
        Path, (source_path, sym_path, map_path, output_path))
    source = json.loads(source_path.read_text(encoding="utf-8"))
    if (
        source.get("format") != "trep-source"
        or source.get("version") != 1
        or not isinstance(source.get("backgroundMaps"), list)
    ):
        raise ValueError(
            "Source definition must use trep-source version 1 "
            "and contain backgroundMaps"
        )

    symbols = parse_symbols(
        sym_path.read_text(encoding="utf-8"),
        map_path.read_text(encoding="utf-8"),
    )

    tile_regions = []
    for definition in source.get("tileRegions", []):
        if definition["symbol"] not in symbols:
            raise ValueError(f"Missing symbol: {definition['symbol']}")
        bits_per_pixel = int(definition["bitsPerPixel"])
        if bits_per_pixel not in (1, 2):
            raise ValueError(
                f"Invalid bitsPerPixel for tile region: {definition['name']}"
            )
        start = symbols[definition["symbol"]]
        bytes_per_tile = 8 if bits_per_pixel == 1 else 16
        end_symbol = definition.get("endSymbol")
        if end_symbol:
            if end_symbol not in symbols:
                raise ValueError(f"Missing end symbol: {end_symbol}")
            end = symbols[end_symbol]
            if end <= start or (end - start) % bytes_per_tile:
                raise ValueError(f"Tile region is not tile-aligned: {definition['name']}")
            tile_count = (end - start) // bytes_per_tile
        else:
            tile_count = int(definition.get("tileCount", 0))
            if tile_count < 1:
                raise ValueError(
                    f"Tile region needs an endSymbol or tileCount: {definition['name']}"
                )
            end = start + tile_count * bytes_per_tile
        result = dict(definition)
        result["start"] = f"0x{start:04X}"
        result["end"] = f"0x{end:04X}"
        result["tileCount"] = tile_count
        tile_regions.append(result)

    tile_sets = source.get("tileSets", [])
    region_names = {definition["name"] for definition in tile_regions}
    for definition in tile_sets:
        if not definition.get("name") or not isinstance(definition.get("regions"), list):
            raise ValueError("Each tile set must have a name and regions array")
        missing = [name for name in definition["regions"] if name not in region_names]
        if missing:
            raise ValueError(
                f"Tile set {definition['name']} refers to missing regions: "
                f"{', '.join(missing)}"
            )

    maps = []
    for definition in source["backgroundMaps"]:
        if definition["symbol"] not in symbols:
            raise ValueError(f"Missing symbol: {definition['symbol']}")
        result = dict(definition)
        result["start"] = f"0x{symbols[definition['symbol']]:04X}"
        if definition.get("endSymbol"):
            if definition["endSymbol"] not in symbols:
                raise ValueError(f"Missing end symbol: {definition['endSymbol']}")
            result["end"] = f"0x{symbols[definition['endSymbol']]:04X}"
        maps.append(result)

    metadata = {
        "format": "trep-metadata",
        "version": 1,
        "project": source.get("project")
        or source_path.name.removesuffix(".trep-source.json"),
        "generatedFrom": {"symbols": sym_path.name, "map": map_path.name},
        "tileRegions": tile_regions,
        "tileSets": tile_sets,
        "backgroundMaps": maps,
    }
    output_path.write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    return len(maps)


def main():
    if len(sys.argv) != 5:
        raise SystemExit(
            "Usage: trep.py <source.json> <file.sym> <file.map> <output.trep.json>"
        )
    generate(*sys.argv[1:])


if __name__ == "__main__":
    main()
