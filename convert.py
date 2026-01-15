"""Scheme-B converter (2026-01-12): teaser.ply -> converted0112.ply

Goal
- Keep storage small while improving compatibility.
- Output PLY contains ONLY `vertex` element (drops teaser extra elements).

Output vertex schema (17 float32 properties, in this exact order):
- x, y, z
- nx, ny, nz           (filled with 0)
- f_dc_0, f_dc_1, f_dc_2
- opacity
- scale_0, scale_1, scale_2
- rot_0, rot_1, rot_2, rot_3

Notes
- No SH high-order terms: f_rest_* are NOT written.
- Output is binary_little_endian 1.0.
"""

from __future__ import annotations

import argparse
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class PlyHeader:
    format: str
    version: str
    vertex_count: int
    vertex_properties: List[Tuple[str, str]]  # (type, name)
    header_lines: List[str]
    data_start_offset: int


_PLY_TYPE_TO_STRUCT = {
    "char": "b",
    "int8": "b",
    "uchar": "B",
    "uint8": "B",
    "short": "h",
    "int16": "h",
    "ushort": "H",
    "uint16": "H",
    "int": "i",
    "int32": "i",
    "uint": "I",
    "uint32": "I",
    "float": "f",
    "float32": "f",
    "double": "d",
    "float64": "d",
}


def _readline_ascii(f) -> bytes:
    line = f.readline()
    if not line:
        raise EOFError("Unexpected EOF while reading PLY header")
    return line


def parse_ply_header(path: Path) -> PlyHeader:
    with path.open("rb") as f:
        header_lines: List[str] = []

        first = _readline_ascii(f)
        first_s = first.decode("ascii", errors="strict").rstrip("\r\n")
        header_lines.append(first_s)
        if first_s.strip() != "ply":
            raise ValueError(f"Not a PLY file: {path}")

        fmt_line = _readline_ascii(f)
        fmt_s = fmt_line.decode("ascii", errors="strict").rstrip("\r\n")
        header_lines.append(fmt_s)
        fmt_parts = fmt_s.strip().split()
        if len(fmt_parts) != 3 or fmt_parts[0] != "format":
            raise ValueError(f"Invalid format line in header: {fmt_s}")
        fmt, version = fmt_parts[1], fmt_parts[2]

        vertex_count = None
        vertex_properties: List[Tuple[str, str]] = []
        in_vertex = False

        while True:
            bline = _readline_ascii(f)
            line = bline.decode("ascii", errors="strict").rstrip("\r\n")
            header_lines.append(line)

            stripped = line.strip()
            if stripped == "end_header":
                data_start = f.tell()
                break

            parts = stripped.split()
            if not parts:
                continue

            if parts[0] == "element":
                if len(parts) != 3:
                    raise ValueError(f"Invalid element line: {line}")
                elem_name = parts[1]
                elem_count = int(parts[2])
                in_vertex = elem_name == "vertex"
                if in_vertex:
                    vertex_count = elem_count
                continue

            if parts[0] == "property":
                if in_vertex:
                    if len(parts) == 3:
                        p_type, p_name = parts[1], parts[2]
                    elif len(parts) >= 5 and parts[1] == "list":
                        raise ValueError(
                            "List properties are not supported for vertex in this converter. "
                            f"Found: {line}"
                        )
                    else:
                        raise ValueError(f"Invalid property line: {line}")
                    vertex_properties.append((p_type, p_name))
                continue

        if vertex_count is None:
            raise ValueError(f"No vertex element found in header: {path}")

        return PlyHeader(
            format=fmt,
            version=version,
            vertex_count=vertex_count,
            vertex_properties=vertex_properties,
            header_lines=header_lines,
            data_start_offset=data_start,
        )


def _endian_for_format(fmt: str) -> str:
    if fmt == "binary_little_endian":
        return "<"
    if fmt == "binary_big_endian":
        return ">"
    raise ValueError(f"Unsupported PLY format for binary parsing: {fmt}")


def _struct_for_vertex(props: Sequence[Tuple[str, str]], endian: str) -> struct.Struct:
    try:
        fmt = endian + "".join(_PLY_TYPE_TO_STRUCT[t] for t, _ in props)
    except KeyError as e:
        raise ValueError(f"Unsupported PLY scalar type: {e}") from e
    return struct.Struct(fmt)


def read_vertex_table_binary(path: Path, header: PlyHeader) -> dict[str, np.ndarray]:
    if header.format not in ("binary_little_endian", "binary_big_endian"):
        raise ValueError(f"Only binary PLY is supported. Got: {header.format}")

    endian = _endian_for_format(header.format)
    st = _struct_for_vertex(header.vertex_properties, endian)

    arrays: dict[str, np.ndarray] = {}
    for _ptype, pname in header.vertex_properties:
        arrays[pname] = np.empty((header.vertex_count,), dtype=np.float32)

    with path.open("rb") as f:
        f.seek(header.data_start_offset)
        for i in range(header.vertex_count):
            chunk = f.read(st.size)
            if len(chunk) != st.size:
                raise EOFError(
                    f"Unexpected EOF while reading vertex data at {i}/{header.vertex_count}"
                )
            values = st.unpack(chunk)
            for (_ptype, pname), v in zip(header.vertex_properties, values):
                arrays[pname][i] = float(v)

    return arrays


def write_ply_binary_vertex_only(
    path: Path,
    vertex_count: int,
    schema: Sequence[Tuple[str, str]],
    columns: dict[str, np.ndarray],
) -> None:
    header_lines: List[str] = [
        "ply",
        "format binary_little_endian 1.0",
        f"element vertex {vertex_count}",
    ]
    for p_type, p_name in schema:
        header_lines.append(f"property {p_type} {p_name}")
    header_lines.append("end_header")
    header = "\n".join(header_lines) + "\n"

    st = _struct_for_vertex(schema, "<")

    for _t, name in schema:
        if name not in columns:
            raise KeyError(f"Missing column for output: {name}")
        if columns[name].shape[0] != vertex_count:
            raise ValueError(
                f"Column {name} has {columns[name].shape[0]} rows, expected {vertex_count}"
            )

    with path.open("wb") as f:
        f.write(header.encode("ascii"))
        for i in range(vertex_count):
            row = [columns[name][i] for _t, name in schema]
            f.write(st.pack(*row))


def target_schema_scheme_b() -> List[Tuple[str, str]]:
    # All float32 to match typical gaussian-splatting PLY exports
    names = [
        "x",
        "y",
        "z",
        "nx",
        "ny",
        "nz",
        "f_dc_0",
        "f_dc_1",
        "f_dc_2",
        "opacity",
        "scale_0",
        "scale_1",
        "scale_2",
        "rot_0",
        "rot_1",
        "rot_2",
        "rot_3",
    ]
    return [("float", n) for n in names]


def convert(teaser_path: Path, output_path: Path) -> None:
    teaser_header = parse_ply_header(teaser_path)
    teaser_cols = read_vertex_table_binary(teaser_path, teaser_header)

    schema = target_schema_scheme_b()
    n = teaser_header.vertex_count

    out_cols: dict[str, np.ndarray] = {}
    for _t, name in schema:
        if name in teaser_cols:
            out_cols[name] = teaser_cols[name].astype(np.float32, copy=False)
        else:
            out_cols[name] = np.zeros((n,), dtype=np.float32)

    # normals forced to 0 per scheme-B
    out_cols["nx"].fill(0.0)
    out_cols["ny"].fill(0.0)
    out_cols["nz"].fill(0.0)

    write_ply_binary_vertex_only(output_path, n, schema, out_cols)


def _summarize_header(path: Path) -> str:
    h = parse_ply_header(path)
    props = ", ".join([name for _t, name in h.vertex_properties])
    return (
        f"{path.name}: format={h.format} vertex={h.vertex_count} props={len(h.vertex_properties)}\n"
        f"  [{props}]"
    )


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Scheme-B: teaser.ply -> converted0112.ply")
    ap.add_argument(
        "--teaser",
        type=Path,
        default=Path("PLY") / "teaser.ply",
        help="Input teaser.ply path",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("PLY") / "converted0112.ply",
        help="Output converted0112.ply path",
    )
    args = ap.parse_args(argv)

    convert(args.teaser, args.out)
    print(_summarize_header(args.teaser))
    print(_summarize_header(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
